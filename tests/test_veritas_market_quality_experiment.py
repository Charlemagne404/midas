from __future__ import annotations

import gzip
import json
from datetime import UTC, datetime, timedelta

from midas.veritas.market_quality_experiment import (
    DATA_CUTOFF_SCAN_ID,
    DISCOVERY_FRAME_PROTOCOL,
    SOURCE_ANALYSIS_VERSION,
    SOURCE_CODE_SHA256,
    chronological_unseen_market_split,
    run_market_quality_experiment,
)


def test_chronological_split_excludes_repeated_and_seen_market_ids(monkeypatch) -> None:
    import midas.veritas.market_quality_experiment as experiment

    monkeypatch.setattr(experiment, "MIN_TRAIN_MARKETS", 1)
    monkeypatch.setattr(experiment, "MIN_TEST_MARKETS", 1)
    scan_ids = [f"scan-{index}" for index in range(10)]
    rows = []
    for index, scan_id in enumerate(scan_ids):
        rows.append({"scan_id": scan_id, "scan_index": index, "market_id": f"market-{index}"})
    rows.extend(
        [
            {"scan_id": "scan-8", "scan_index": 8, "market_id": "market-0"},
            {"scan_id": "scan-9", "scan_index": 9, "market_id": "market-8"},
            {"scan_id": "scan-9", "scan_index": 9, "market_id": "new-market"},
        ]
    )

    train, evaluation, split = chronological_unseen_market_split(rows, scan_ids)

    assert split["training_scan_count"] == 7
    assert {row["market_id"] for row in train} == {f"market-{index}" for index in range(7)}
    assert {row["market_id"] for row in evaluation} == {
        "market-7",
        "market-8",
        "market-9",
        "new-market",
    }
    assert not ({row["market_id"] for row in train} & {row["market_id"] for row in evaluation})


def _write_snapshot(
    root, scan_index: int, captured_at: datetime, *, include_market: bool = True
) -> str:
    scan_id = (
        DATA_CUTOFF_SCAN_ID
        if scan_index == 22
        else ("scan-" + (captured_at.strftime("%Y%m%dT%H%M%SZ")) + f"-fixture{scan_index:02d}")
    )
    selected_markets = []
    market_observations = []
    if include_market:
        for market_index in range(40):
            market_id = f"market-{scan_index}-{market_index}"
            valid = (scan_index + market_index) % 4 != 0
            selected_markets.append(
                {
                    "market_id": market_id,
                    "cohort_role": "rotating_stratified",
                    "selection_probability": "0.5",
                    "liquidity_usdc": "2500",
                    "volume_24h_usdc": "120",
                    "end_ns": int((captured_at + timedelta(days=21)).timestamp() * 1_000_000_000),
                    "spread_per_share": "0.02",
                    "primary_category": "fixture-category",
                    "primary_category_source": "market.category",
                    "liquidity_band": "medium",
                    "expiry_band": "medium_90d",
                    "spread_band": "medium_le_0.05",
                }
            )
            market_observations.append(
                {
                    "market_id": market_id,
                    "audit": {"valid": valid, "positive_top_pair_gross": False},
                }
            )
    payload = {
        "analysis_version": SOURCE_ANALYSIS_VERSION,
        "source_code_sha256": SOURCE_CODE_SHA256,
        "discovery_frame_protocol": DISCOVERY_FRAME_PROTOCOL,
        "scan_id": scan_id,
        "captured_ns": int(captured_at.timestamp() * 1_000_000_000),
        "selection": {
            "plan": {"phase": "liquidity"},
            "selected_markets": selected_markets,
        },
        "market_observations": market_observations,
    }
    path = root / "snapshots" / f"{scan_id}.json.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps(payload).encode()))
    return scan_id


def test_preregistered_experiment_uses_pinned_unseen_market_holdout(tmp_path) -> None:
    start = datetime(2026, 10, 16, 10, 30, tzinfo=UTC)
    for index in range(23):
        _write_snapshot(tmp_path, index, start + timedelta(minutes=30 * index))
    # This later scan must remain outside the frozen data cutoff.
    _write_snapshot(tmp_path, 23, start + timedelta(minutes=30 * 23), include_market=False)
    preregistration = tmp_path / "preregistered.md"
    preregistration.write_text("frozen protocol\n")

    artifact = run_market_quality_experiment(tmp_path, preregistration)

    assert artifact["source"]["snapshot_count"] == 23
    assert artifact["source"]["last_scan_id"] == DATA_CUTOFF_SCAN_ID
    assert artifact["split"]["evaluation_unseen_market_count"] == 280
    assert artifact["sampling"]["evaluation_market_ids_disjoint_from_training"] is True
    assert artifact["model"]["not_deployed"] is True
    assert artifact["evaluation"]["positive_gross_candidates_in_held_out_markets"] == 0
    assert artifact["evaluation"]["model_top_quartile"]["selected_markets"] == 70
