"""Independent arithmetic and uncertainty contracts; fixtures are never real fills."""

import copy
import json
from dataclasses import replace
from decimal import Decimal as D

import pytest
from midas.reality.calibrated_kernel import sample
from midas.reality.calibration import (
    distribution,
    measure,
    persistence,
    summary,
    synthetic_comparison,
)
from midas.reality.execution_research import compare_decision, evaluate, families, fee_reserve
from midas.reality.quote_dynamics import collect
from midas.reality.research_schema import digest


def decision(horizon=300):
    return dict(
        id="labeled_fixture",
        condition="fixture_condition",
        decision_ordinal=1,
        feature_sha256="frozen_fixture_features",
        horizon_ms=horizon,
        hypothetical_context=dict(quantity="5", capital="100"),
        features=dict(
            market=dict(
                condition="fixture_condition",
                protocol="v1",
                minimum_order_size_reported="5",
                fee_regime=dict(
                    enabled=True, schedule=dict(rate="0.04", exponent=1, takerOnly=True)
                ),
            ),
            legs={
                leg: dict(
                    asset_id=leg,
                    best_ask=p,
                    best_bid=str(D(p) - D("0.01")),
                    age_ns=0,
                    quote_age_ns=1000000,
                    spread="0.01",
                    total_ask_quantity="20",
                    displayed_depth=dict(asks=[[p, "20"]]),
                    lookback_ns=10**10,
                    recent_book_update_frames=3,
                    best_ask_change="0.02",
                    ask_quantity_change="-5",
                )
                for leg, p in (("yes", "0.4"), ("no", "0.5"))
            },
            cross_outcome_skew_ns=0,
            theoretical_edge_per_unit_before_fees="0.1",
            quantity_supported=True,
            displayed_acquisition_cost="4.5",
            best_ask_pair_sum="0.9",
        ),
        labels=dict(
            status="observed_public_measurement",
            reason=None,
            quote_persistence=True,
            opportunity_persistence=True,
            displayed_quantity_supported=True,
            depth_at_original_quotes=dict(yes="3", no="5"),
            adverse_ask_movement="0.01",
            best_ask_pair_movement="0.01",
            displayed_acquisition_cost="4.6",
            quoted_exit_value_change="-0.2",
        ),
        effective_delays_ms=dict(yes=310, no=315),
    )


def compact(label, family="a", group="1"):
    return dict(labels=label, family_id=family, dependence_group=group, initial_opportunity=True)


def test_missingness_bounds_do_not_assume_censoring_is_negative():
    rows = [
        compact(dict(quote_persistence=True)),
        compact(dict(quote_persistence=False)),
        compact(dict(quote_persistence=None)),
    ]
    r = persistence(rows, "quote_persistence")
    assert r["conditional_measured_rate"] == 0.5
    assert r["missing_outcome_identification_bounds"] == [1 / 3, 2 / 3]
    assert r["exploratory_cluster_bootstrap_95"] is None
    assert r["time_block_count"] == 1


def test_horizon_duplicates_do_not_inflate_initial_distribution():
    r = decision()
    rows = [
        dict(
            anchor="same",
            market_id="m",
            family_id="f",
            day_utc="day",
            dependence_group="g",
            labels=r["labels"],
            initial_opportunity=True,
            measurements=measure(r),
        )
        for _ in range(4)
    ]
    s = summary(rows)
    assert s["metrics"]["spread"]["count"] == 2
    assert s["anchors"] == 1
    assert s["quote_persistence"]["time_block_count"] == 1
    assert s["metrics"]["original_quote_depth_retention"]["quantiles"]["0"] == 0.15


def test_public_fee_curve_and_rounding_are_charged_once():
    assert fee_reserve(D(100), D("0.5"), D("0.04")) == D("1.00001")
    assert fee_reserve(D(100), D("0.5"), D(0)) == 0
    result = evaluate(decision(100), families()[0])
    assert D(result["fee_reserve"]) == D("0.09802")
    assert D(result["acquisition_cost"]) == D("4.5")
    assert D(result["matched_quantity"]) == 5
    expected = D(5) - D("4.5") - D("0.09802") - D("0.01") - D("4.5") * D(".1") * 7 / 365
    assert abs(D(result["hypothetical_pnl_bounds"][0]) - expected) < D("1e-25")
    assert result["fill_probability"] is None
    assert result["actual_fills"] == "unknown_counterfactual"


def test_non_atomic_partial_economics_have_terminal_payoff_bounds():
    r = evaluate(decision(), families()[1])
    assert r["imposed_quantities"] == {"yes": "2.4", "no": "4.0"}
    assert D(r["matched_quantity"]) == D("2.4")
    assert D(r["unmatched_quantity"]) == D("1.6")
    low, high = map(D, r["hypothetical_pnl_bounds"])
    assert high - low == D("1.6")
    assert low < 0 < high
    assert D(r["capital_committed"]) == D(r["acquisition_cost"]) + D(r["fee_reserve"]) + D(
        r["friction_redemption_financing"]
    )


def test_stress_is_explicit_loss_assumption_not_fabricated_observation():
    r = evaluate(decision(5000), families()[3])
    assert r["imposed_quantities"]["yes"] == "0"
    assert D(r["unmatched_quantity"]) == D("1.25")
    assert D(r["hypothetical_pnl_bounds"][0]) < 0
    assert r["orders_submitted"] is False
    assert "recovery failure" in r["recovery"]


def test_future_changes_cannot_change_candidate_decision():
    original = decision()
    changed = copy.deepcopy(original)
    changed["labels"] = dict(status="censored")
    a, b = (evaluate(r, families()[1]) for r in (original, changed))
    assert a["decision"] == b["decision"] == "hypothetical_candidate"
    assert b["status"] == "unknown_followup"
    assert b["hypothetical_pnl_bounds"] is None


def test_no_imposed_inventory_has_no_redemption_or_fee_charge():
    row = decision()
    row["labels"]["depth_at_original_quotes"] = {"yes": "0", "no": "0"}
    result = evaluate(row, families()[1])
    assert list(map(D, result["hypothetical_pnl_bounds"])) == [D(0), D(0)]
    assert D(result["capital_committed"]) == 0


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (
            lambda r: r["features"]["market"].update(
                fee_regime=dict(enabled=True, schedule=dict(rate=1000, exponent=1, takerOnly=True))
            ),
            "unsupported_fee_or_minimum",
        ),
        (
            lambda r: r["features"]["market"].update(minimum_order_size_reported=None),
            "unsupported_fee_or_minimum",
        ),
        (lambda r: r["features"].update(cross_outcome_skew_ns=1000 * 10**6), "timing_limit"),
        (lambda r: r["hypothetical_context"].update(capital="1"), "initial_depth_or_capital"),
    ],
)
def test_unknown_or_unsupported_inputs_fail_closed(mutate, reason):
    r = decision()
    mutate(r)
    assert evaluate(r, families()[1])["reason"] == reason


def test_sizes_and_fractions_are_bounded_and_unknown_fee_not_zero():
    with pytest.raises(ValueError):
        evaluate(decision(), families()[0], quantity="NaN")
    with pytest.raises(ValueError):
        replace(families()[0], depth_fraction="1.1")
    assert evaluate(decision(), families()[0], quantity="1")["reason"] == "below_reported_minimum"
    assert (
        evaluate(decision(), families()[0], quantity="100")["reason"] == "initial_depth_or_capital"
    )


def test_matched_delay_scenarios_reject_different_decisions():
    rows = [decision(h) for h in (100, 300, 1000, 5000)]
    results = compare_decision(rows)
    assert len({r["assumption_id"] for r in results}) == 4
    assert all(r["status"] == "hypothetical_bounds" for r in results)
    rows[1]["feature_sha256"] = "changed"
    with pytest.raises(ValueError, match="Unmatched"):
        compare_decision(rows)


def test_synthetic_comparison_is_bounded_reproducible_and_labeled():
    a = synthetic_comparison([100, 300, 1000, 5000])
    assert a == synthetic_comparison([100, 300, 1000, 5000])
    assert a["source"] == "SYNTHETIC_REGENERATED_CONTROLS"
    assert a["scenarios"] == 19 * 16
    assert a["metrics"]["spread"]["count"] == 608
    assert a["horizons"]["1000"]["liquidity_disappearance"] > 0
    assert a["protected_historical_artifacts_modified"] is False
    assert distribution([])["quantiles"] is None


def dynamics_tape(monkeypatch, *, gap=False, deferred=False, empty=False):
    start = 1792000000000000000
    records = []

    def add(kind, payload, ms, **extra):
        records.append(
            dict(
                kind=kind,
                payload=payload,
                ordinal=len(records) + 1,
                received_ns=start + ms * 10**6,
                monotonic_ns=ms * 10**6,
                **extra,
            )
        )

    add(
        "gap",
        dict(reason="process_start", reconstruction_version=4, implementation_sha256="a" * 64),
        0,
    )
    add("discovery", {}, 0, cohort=[dict(condition="c", tokens={"a": "Yes"})])
    add(
        "frame",
        json.dumps(
            dict(
                event_type="book",
                asset_id="a",
                market="c",
                timestamp=str(start // 10**6),
                asks=[dict(price=".4", size="10"), dict(price=".5", size="20")],
                bids=[dict(price=".3", size="10")],
            )
        ),
        0,
    )
    if deferred:
        add("public_fee_metadata", {}, -50)
    if gap:
        add("gap", dict(reason="disconnect"), 50)
    changes = [dict(asset_id="a", price=".4", size="0", side="SELL")]
    if empty:
        changes.append(dict(asset_id="a", price=".5", size="0", side="SELL"))
    add(
        "frame",
        json.dumps(
            dict(
                event_type="price_change",
                market="c",
                timestamp=str(start // 10**6 + 100),
                price_changes=changes,
            )
        ),
        100,
    )
    monkeypatch.setattr(
        "midas.reality.quote_dynamics.source_records", lambda *args: iter((r, {}) for r in records)
    )
    manifest = dict(
        source_root="labeled_fixture",
        boundaries=dict(train_end_ns=start + 200 * 10**6),
        identity=dict(spec=dict(max_freshness_ms=5000), source_manifest={}),
    )
    return collect(manifest, {"c"})


def test_receiver_spell_lifetime_is_not_snapshot_age_and_deferred_http_is_not_clock_regression(
    monkeypatch,
):
    r = dynamics_tape(monkeypatch, deferred=True)
    assert r["completed_quote_spells_ms"] == [100]
    assert r["right_censored_quote_spells_ms"] == [100]
    assert "receiver_clock_regression" not in r["censor_reasons"]
    assert r["aggregate_ask_depth_changes"] == [-10]
    assert r["spread_changes"] == pytest.approx([0.1])


def test_gap_censors_quote_spell_instead_of_manufacturing_disappearance(monkeypatch):
    r = dynamics_tape(monkeypatch, gap=True)
    assert r["completed_quote_spells_ms"] == []
    assert r["right_censored_quote_spells_ms"] == [50]
    assert r["censor_reasons"] == {"recorded_gap": 1}


def test_empty_ask_interval_is_not_a_quote_lifetime(monkeypatch):
    r = dynamics_tape(monkeypatch, empty=True)
    assert r["completed_quote_spells_ms"] == [100]
    assert r["right_censored_quote_spells_ms"] == []


def test_joint_kernel_keeps_unknowns_and_does_not_interpolate():
    identity = dict(partition="chronological train AND market-generalization train")
    report = dict(
        identity=identity,
        calibration_id=digest(identity),
        horizons={"300": dict(rows=1, statuses={"observed_public_measurement": 1})},
        empirical_joint_kernel=[
            dict(
                id="fixture",
                horizon_ms=300,
                family_id="family",
                dependence_group="block",
                labels=decision()["labels"],
            )
        ],
    )
    result = sample(report, 300, 19)
    assert result == sample(report, 300, 19)
    assert result["measurement"]["depth_at_original_quotes"] == {"yes": "3", "no": "5"}
    assert result["fill_probability"] is None
    report["horizons"]["300"] = dict(rows=10**9, statuses={"observed_public_measurement": 1})
    assert sample(report, 300, 19)["status"] == "censored_draw"
    with pytest.raises(ValueError, match="interpolation"):
        sample(report, 200, 19)
    report["calibration_id"] = "corrupt"
    with pytest.raises(ValueError, match="corruption"):
        sample(report, 300, 19)
