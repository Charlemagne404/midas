from decimal import Decimal

import pytest
from midas.arena.datasets import DatasetSpec, build
from midas.arena.economic_regimes import EconomicRegime
from midas.arena.tournaments import TournamentSpec, run_tournament
from midas.core.models import Book
from midas.laboratory.runtime import execute
from midas.laboratory.spec import generate
from midas.paper.broker import ExecutionModel

from scripts.compare_arena import compare


def test_regime_scales_initial_and_future_depth_without_mutating_source():
    original = generate("volatile", 123)
    before = original.model_dump(mode="json")
    changed = EconomicRegime(
        depth_multiplier=Decimal("0.5"),
        taker_fee_rate=Decimal("0.01"),
        additional_submission_latency_ms=200,
    ).apply(original)
    assert original.model_dump(mode="json") == before
    assert changed.account.execution.latency_ms == original.account.execution.latency_ms + 200
    assert changed.market.fee.rate == Decimal("0.01")
    for asset, book in original.books.items():
        assert changed.books[asset].asks[0].size == book.asks[0].size / 2
    for first, second in zip(original.events, changed.events, strict=True):
        for asset, raw in first.payload.get("books", {}).items():
            if raw["asks"]:
                assert (
                    Book.model_validate(second.payload["books"][asset]).asks[0].size
                    == Book.model_validate(raw).asks[0].size / 2
                )
    assert EconomicRegime().apply(original) is original
    with pytest.raises(ValueError, match="recorded"):
        EconomicRegime(depth_multiplier=Decimal("0.5")).apply(
            original.model_copy(update={"provenance": "RECORDED"})
        )
    assert (
        not EconomicRegime(depth_multiplier=0)
        .apply(original)
        .books[next(iter(original.books))]
        .asks
    )


def test_fees_reach_real_simulated_orders_and_accounting():
    exercised = False
    for seed in range(1, 10):
        base = generate("calm", seed, ExecutionModel.preset("optimistic"))
        first = execute(base)
        if first["metrics"]["orders"] == 0:
            continue
        second = execute(EconomicRegime(taker_fee_rate=Decimal("0.01")).apply(base))
        assert first["passed"] and second["passed"]
        assert Decimal(second["metrics"]["net_simulated_pnl"]) < Decimal(
            first["metrics"]["net_simulated_pnl"]
        )
        exercised = True
        break
    assert exercised, "Fixture must contain an admitted execution"


def test_tournament_retains_origin_for_matched_economic_conditions(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=30))
    common = {"dataset_id": dataset["dataset_id"], "max_episodes": 2}
    first = run_tournament(tmp_path, TournamentSpec(**common))
    second = run_tournament(
        tmp_path,
        TournamentSpec(**common, economic_regime=EconomicRegime(depth_multiplier=Decimal("0.5"))),
    )
    import json

    rows = [
        json.loads((tmp_path / "tournaments" / r["tournament_id"] / "rows.json").read_text())
        for r in (first, second)
    ]
    assert [r["scenario_origin_hash"] for r in rows[0]] == [
        r["scenario_origin_hash"] for r in rows[1]
    ]
    assert all(r["passed"] for r in rows[1])
    assert any(a["scenario_hash"] != b["scenario_hash"] for a, b in zip(*rows, strict=True))
    comparison = compare(tmp_path, first["tournament_id"], second["tournament_id"])
    assert comparison["economic_regime_comparison"]
    assert all(p["base_episodes"] == 2 for p in comparison["policies"])
