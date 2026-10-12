from decimal import Decimal

import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, sha256
from midas.laboratory.runtime import Environment
from midas.laboratory.spec import Costs, generate

from scripts.arena_economics import YEAR_MS, analyze, publish, reprice, summarize


def test_overlay_matches_actual_laboratory_costs_and_monotonicity():
    costs = Costs(
        operating_per_fill=".1",
        redemption_cost=".2",
        annual_financing_rate=".2",
        collateral_value_factor=".95",
    )
    result = Environment(generate("calm", 8).model_copy(update={"costs": costs})).run()
    assert abs(reprice(result, costs) - Decimal(result["metrics"]["net_simulated_pnl"])) < Decimal(
        "1e-18"
    )
    assert reprice(result, Costs(operating_per_fill=".5")) <= reprice(result, Costs())
    assert reprice(result, Costs(collateral_value_factor=".5")) <= reprice(result, Costs())
    fixture = {
        "metrics": {
            "gross_settled_virtual_pnl": "3",
            "capital_time_integral_ms": str(100 * YEAR_MS),
            "fill_count": 0,
        },
        "final_portfolio": {},
    }
    assert reprice(fixture, Costs(annual_financing_rate=".1")) == -7


def test_economic_uncertainty_groups_execution_variants():
    result = summarize([{"base_episode_id": "one"}] * 3, [3, 0, 0])
    assert result["base_episodes"] == 1
    assert result["mean_pnl_episode_bootstrap_95"] == [1, 1]


def test_real_replay_overlay_refuses_changed_source_rows(tmp_path):
    directory = tmp_path / "tournaments" / "example"
    result = Environment(generate("calm", 8).model_copy(update={"strategy": "no_trade"})).run()
    row = {
        "id": "one",
        "policy": "no_trade",
        "base_episode_id": "one",
        "execution_model": "standard",
        "passed": result["passed"],
        "result_hash": result["result_hash"],
    }
    atomic_replay(directory / "replays" / "one.json", {"row": row, "result": result})
    atomic_json(directory / "rows.json", [row])
    atomic_json(
        directory / "manifest.json",
        {"variants": 1, "rows_sha256": sha256(directory / "rows.json"), "configuration": {}},
    )
    report = analyze(tmp_path, "example")
    assert len(report["policies"][0]["points"]) == 20
    assert report["policies"][0]["baseline_zero_extra_costs"]["base_episodes"] == 1
    output = directory / "economics.json"
    publish(output, report)
    snapshot = directory / f"economics-source-{report['analysis_source_sha256']}.py"
    assert sha256(snapshot) == report["analysis_source_sha256"]
    original_hash = sha256(output)
    with pytest.raises(ValueError, match="Preserve"):
        publish(output, report)
    assert sha256(output) == original_hash
    (directory / "rows.json").write_text("[]")
    with pytest.raises(ValueError, match="rows changed"):
        analyze(tmp_path, "example")
