from copy import deepcopy
from decimal import Decimal

import pytest

from scripts.attribute_arena_losses import amount, analyze, position_components


def position():
    return {
        "settled": True,
        "orders": [
            {"asset_id": "yes", "quantity": "10", "remaining": "0"},
            {"asset_id": "no", "quantity": "10", "remaining": "5"},
        ],
        "ledger": [
            {"kind": "fill", "asset_id": "yes", "quantity": "10", "locked_delta": "4.1"},
            {"kind": "fill", "asset_id": "no", "quantity": "5", "locked_delta": "3.05"},
            {"kind": "settlement", "asset_id": "yes", "available_delta": "0"},
            {"kind": "settlement", "asset_id": "no", "available_delta": "5"},
        ],
        "portfolio": {"realized_pnl": "-2.15"},
    }


def test_proportional_allocation_includes_fill_fees_and_reconciles():
    report = position_components(position())
    assert amount(report["matched_position_pnl"]) == Decimal("-0.10")
    assert amount(report["residual_position_pnl"]) == Decimal("-2.05")
    assert amount(report["residual_shares"]) == 5
    assert amount(report["matched_shares"]) == 5


def test_one_leg_loss_has_no_matched_cash_flow():
    p = position()
    p["orders"][1]["remaining"] = "10"
    p["ledger"] = [p["ledger"][0], p["ledger"][2]]
    p["portfolio"]["realized_pnl"] = "-4.1"
    report = position_components(p)
    assert amount(report["matched_position_pnl"]) == 0
    assert amount(report["residual_position_pnl"]) == Decimal("-4.1")


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda p: p.update(settled=False), "settled"),
        (lambda p: p["portfolio"].update(realized_pnl="0"), "reconcile"),
        (lambda p: p["ledger"][0].update(quantity="9"), "order quantities"),
        (lambda p: p["ledger"][0].update(locked_delta="NaN"), "Nonfinite"),
    ],
)
def test_rejects_incomplete_or_inconsistent_accounting(mutation, match):
    p = deepcopy(position())
    mutation(p)
    with pytest.raises(ValueError, match=match):
        position_components(p)


def test_tournament_replays_are_verified_and_changed_rows_rejected(tmp_path):
    import json
    import subprocess
    import sys

    from midas.arena.datasets import DatasetSpec, build
    from midas.arena.tournaments import TournamentSpec, run_tournament

    dataset = build(tmp_path, DatasetSpec(episodes=30))
    tournament = run_tournament(
        tmp_path, TournamentSpec(dataset_id=dataset["dataset_id"], max_episodes=2)
    )
    identity = tournament["tournament_id"]
    report = analyze(tmp_path, identity, "arbitrage")
    assert report["source_groups"] == 2
    assert report["correlated_variants"] == 6
    assert len(report["episodes"]) == 6
    directory = tmp_path / "tournaments" / identity
    audit_path = tmp_path / "audit.json"
    audit_command = [
        sys.executable,
        "scripts/verify_arena.py",
        "--root",
        str(tmp_path),
        "--full-replays",
        "--progress",
        "--output",
        str(audit_path),
    ]
    completed = subprocess.run(audit_command, capture_output=True, text=True, check=True)
    assert f"Verified {identity}" in completed.stderr
    published_audit = audit_path.read_bytes()
    assert json.loads(published_audit)["full_replay_verification"]
    rows = directory / "rows.json"
    original = rows.read_bytes()
    rows.write_text("[]")
    with pytest.raises(ValueError, match="rows changed"):
        analyze(tmp_path, identity, "arbitrage")
    failed_audit = subprocess.run(audit_command, capture_output=True, text=True)
    assert failed_audit.returncode != 0
    assert audit_path.read_bytes() == published_audit
    rows.write_bytes(original)
    from midas.arena.artifacts import atomic_replay, read_replay

    selected = next(r for r in json.loads(original) if r["policy"] == "arbitrage")
    replay_path = directory / "replays" / (selected["id"] + ".json")
    replay = read_replay(replay_path)
    replay["result"]["journal"][0]["kind"] = "changed"
    atomic_replay(replay_path, replay)
    with pytest.raises(ValueError, match="Replay integrity"):
        analyze(tmp_path, identity, "arbitrage")
