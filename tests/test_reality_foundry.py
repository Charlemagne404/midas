"""Artificial tapes and independent arithmetic; no execution evidence fixtures."""

import json
from collections import Counter
from decimal import Decimal

import pytest
from midas.reality.foundry import build, examples, source_records
from midas.reality.reconstruction import Engine
from midas.reality.research_measurements import censor, depth_cost, features, labels, pair_quality
from midas.reality.research_schema import DatasetSpec, digest
from midas.reality.research_validation import verify_rows
from midas.reality.storage import Store, file_hash, manifest

START = 1792000000000000000
CONDITION = "0x" + "1" * 64


def market(event_id="family-1"):
    return dict(
        id="1",
        condition=CONDITION,
        protocol="v1",
        tokens={"11": "Yes", "12": "No"},
        payoff=dict(
            pair="same_condition_yes_no_ctf", combined_terminal_claim="1", unit="collateral_unit"
        ),
        fee_regime=dict(enabled=True, schedule=dict(rate=0.04, exponent=1, takerOnly=True)),
        event_ids=[event_id],
        categories=["Fixture"],
        negative_risk=False,
        negative_risk_group=None,
        liquidity="5000",
        minimum_order_size="5",
        tick_size=".01",
        end_ns=START + 10**13,
        metadata_ordinal=2,
        public_market_constraints=dict(minimum_tick_size=".01"),
    )


def snapshot(ms, moved=False, only_yes=False):
    result = []
    for token in ("11", "12"):
        if only_yes and token == "12":
            continue
        bid, ask, size = (
            ((".30", ".45", "9") if moved else (".35", ".40", "10"))
            if token == "11"
            else ((".48", ".55", "7") if moved else (".50", ".55", "20"))
        )
        result.append(
            dict(
                event_type="book",
                asset_id=token,
                market=CONDITION,
                timestamp=str((START + ms * 10**6) // 10**6),
                hash="fixture-native",
                bids=[dict(price=bid, size="100")],
                asks=[dict(price=ask, size=size)],
            )
        )
    return json.dumps(result)


def tape(
    root, *, times=(0, 100, 200, 300, 400, 500), gap_at=None, only_yes_at=None, known_source=True
):
    store = Store(root, reserve=1)
    engine = Engine()

    def add(kind, payload, ms, **kwargs):
        row = store.append(
            kind, payload, received_ns=START + ms * 10**6, monotonic_ns=ms * 10**6, **kwargs
        )
        engine.consume(row)
        return row

    epoch = dict(reason="process_start", reconstruction_version=4)
    if known_source:
        epoch["implementation_sha256"] = "a" * 64
    add("gap", epoch, 0)
    add("public_market_metadata", "fixture metadata", 0, market_id="1")
    add("discovery", "fixture universe", 0, cohort=[market()])
    for ms in times:
        if gap_at is not None and ms >= gap_at:
            add("gap", dict(reason="fixture_disconnect"), gap_at)
            gap_at = None
        add("frame", snapshot(ms, moved=ms > 0, only_yes=ms == only_yes_at), ms)
    add("checkpoint", dict(state_sha256=engine.digest()), times[-1])
    store.close()
    return manifest(root)


def spec(**kwargs):
    return DatasetSpec(
        horizons_ms=(100,),
        stride_ms=100,
        future_tolerance_ms=25,
        lookback_ms=100,
        embargo_ms=125,
        group_window_ms=200,
        source_kind="labeled_fixture",
        reserve_bytes=1,
        **kwargs,
    )


def test_independent_public_arithmetic_and_no_fills(tmp_path):
    source = tape(tmp_path)
    rows = list(examples(tmp_path, source, spec(), Counter()))
    first = next(row for row in rows if row["decision_ns"] == START)
    observed = first["labels"]
    assert observed["quote_persistence"] is False
    assert observed["depth_at_original_quotes"] == {"yes": "0", "no": "7"}
    # Expected values are hand-computed independently of the production measurer.
    assert Decimal(observed["adverse_ask_movement"]) == Decimal(".45") + Decimal(".55") - Decimal(
        ".40"
    ) - Decimal(".55")
    assert Decimal(observed["displayed_acquisition_cost"]) == 5 * (Decimal(".45") + Decimal(".55"))
    assert Decimal(observed["quoted_exit_value_change"]) == 5 * (
        Decimal(".30") + Decimal(".48") - Decimal(".35") - Decimal(".50")
    )
    assert observed["opportunity_persistence"] is False
    assert observed["execution_ground_truth"] == "unknown_counterfactual"
    assert first["effective_delays_ms"] == {"yes": 100.0, "no": 100.0}
    assert Decimal(first["features"]["legs"]["yes"]["best_ask"]) == Decimal(".40")


def test_future_changes_cannot_alter_historical_features(tmp_path):
    one = tmp_path / "one"
    two = tmp_path / "two"
    first = tape(one, times=(0, 100))
    second = tape(two, times=(0, 300))
    a = list(examples(one, first, spec(), Counter()))[0]
    b = list(examples(two, second, spec(), Counter()))[0]
    assert a["feature_sha256"] == b["feature_sha256"]
    assert a["features"] == b["features"]
    assert a["labels"]["status"] == "observed_public_measurement"
    assert b["labels"]["status"] == "censored"


def test_gaps_censor_not_negative_and_disruption_is_explicit(tmp_path):
    source = tape(tmp_path, times=(0, 100), gap_at=50)
    first = list(examples(tmp_path, source, spec(), Counter()))[0]
    assert first["labels"]["status"] == "censored"
    assert first["labels"]["quote_persistence"] is None
    assert first["labels"]["market_disruption"] is True
    assert first["labels"]["reason"] == "recorded_gap:fixture_disconnect"


def test_gap_after_horizon_is_not_manufactured_horizon_disruption(tmp_path):
    source = tape(tmp_path, times=(0, 1000), gap_at=800)
    first = list(examples(tmp_path, source, spec(), Counter()))[0]
    assert first["labels"]["reason"] == "future_observation_unavailable"
    assert first["labels"]["market_disruption"] is None


def test_partial_outcome_update_does_not_confirm_unchanged_other_leg(tmp_path):
    source = tape(tmp_path, times=(0, 100), only_yes_at=100)
    first = list(examples(tmp_path, source, spec(), Counter()))[0]
    assert first["labels"]["status"] == "censored"
    assert first["labels"]["quote_persistence"] is None


def test_missing_producer_provenance_is_excluded(tmp_path):
    counters = Counter()
    source = tape(tmp_path, known_source=False)
    assert list(examples(tmp_path, source, spec(), counters)) == []
    assert counters["excluded:producer_source_unknown"] > 0


def test_raw_hashes_and_offsets_reference_actual_source_bytes(tmp_path):
    source = tape(tmp_path)
    for row, ref in source_records(tmp_path, source):
        assert ref["canonical_record_sha256"] == digest(row)
        with (tmp_path / ref["segment"]).open("rb") as f:
            f.seek(ref["offset"] + 4)
            assert f.read(32).hex() == ref["compressed_record_sha256"]
        assert file_hash(tmp_path / ref["segment"]) == ref["segment_sha256"]


def test_chronological_dataset_immutability_and_reproducibility(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "derived"
    source = tape(root, times=tuple(range(0, 12000, 100)))
    result = build(root, target, spec(), source)
    rows = [
        json.loads(line)
        for line in (target / result["dataset_id"] / "examples.jsonl").read_text().splitlines()
    ]
    assert {"train", "validation", "test"} <= set(result["partition_counts"])
    assert all(row["hypothetical_context"]["orders_submitted"] is False for row in rows)
    assert result["identity"]["spec"]["source_kind"] == "labeled_fixture"
    assert verify_rows(target / result["dataset_id"] / "examples.jsonl", result)[
        "chronological_isolation"
    ]
    again = build(root, target, spec(), source)
    assert again == result
    regenerated = build(root, tmp_path / "separate-regeneration", spec(), source)
    assert regenerated["rows_sha256"] == result["rows_sha256"]
    assert regenerated["dataset_id"] == result["dataset_id"]


def test_feature_and_censored_label_corruption_rejected(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "derived"
    result = build(root, target, spec(), tape(root))
    path = target / result["dataset_id"] / "examples.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["feature_sources"]["decision"]["ordinal"] = rows[0]["decision_ordinal"] + 1
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result["rows_sha256"] = file_hash(path)
    with pytest.raises(ValueError, match="Future-information"):
        verify_rows(path, result)
    rows[0]["feature_sources"]["decision"]["ordinal"] = rows[0]["decision_ordinal"]
    rows[-1]["labels"]["quote_persistence"] = False
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result["rows_sha256"] = file_hash(path)
    with pytest.raises(ValueError, match="Censored"):
        verify_rows(path, result)


def test_storage_budget_failure_does_not_touch_raw(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "derived"
    source = tape(root)
    before = {p.name: file_hash(p) for p in root.glob("*.seg")}
    with pytest.raises(OSError, match="Derivative budget"):
        build(root, target, spec(derivative_budget_bytes=100), source)
    assert before == {p.name: file_hash(p) for p in root.glob("*.seg")}
    assert not list(target.glob(".building-*"))


def test_pair_protocol_timing_and_expiry_exclusions():
    engine = Engine()
    engine.tokens = {"11": CONDITION, "12": CONDITION}
    engine.consume(dict(ordinal=1, kind="frame", received_ns=START, payload=snapshot(0)))
    current = market()
    assert pair_quality(current, engine.books, START, spec()) is None
    assert (
        pair_quality(dict(current, protocol="v2"), engine.books, START, spec())
        == "unsupported_pair_semantics"
    )
    engine.books["11"]["timing_uncertainty"] = "ambiguous"
    assert pair_quality(current, engine.books, START, spec()) == "source_timing_uncertainty"
    assert (
        pair_quality(dict(current, end_ns=START), engine.books, START, spec())
        == "reported_expiry_reached"
    )


def test_no_initial_opportunity_not_a_negative_opportunity_label():
    engine = Engine()
    engine.tokens = {"11": CONDITION, "12": CONDITION}
    engine.consume(
        dict(ordinal=1, kind="frame", received_ns=START, payload=snapshot(100, moved=True))
    )
    _, base = features(
        market(), engine.books, decision_ns=START, spec=spec(), history={}, trades={}
    )
    assert labels(base, base["views"])["opportunity_persistence"] is None
    assert censor("missing")["quote_persistence"] is None
    assert depth_cost([[".50", "2"]], "5") == dict(
        quantity_observed="2", value="1.00", complete=False
    )


def test_spec_rejects_invalid_horizons_and_embargo():
    with pytest.raises(ValueError):
        DatasetSpec(horizons_ms=(0,))
    with pytest.raises(ValueError):
        DatasetSpec(quantity="NaN")
    with pytest.raises(ValueError):
        DatasetSpec(embargo_ms=1)
    with pytest.raises(ValueError):
        DatasetSpec(source_kind="actual_private_fills")


def test_independent_source_audit_catches_rehashed_observed_label_corruption(tmp_path):
    from midas.reality.research_validation import audit_public_labels

    root, target = tmp_path / "raw", tmp_path / "derived"
    result = build(root, target, spec(), tape(root))
    path = target / result["dataset_id"] / "examples.jsonl"
    checked = audit_public_labels(path, result, root)
    assert checked["observed_labels_independently_checked"] > 0
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["labels"]["quote_persistence"] = not rows[0]["labels"]["quote_persistence"]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result["rows_sha256"] = file_hash(path)
    with pytest.raises(ValueError, match="label corruption"):
        audit_public_labels(path, result, root)


def test_observed_empty_side_is_known_disappearance_not_missing_data():
    from midas.reality.research_measurements import book_view

    engine = Engine()
    engine.tokens = {"11": CONDITION, "12": CONDITION}
    engine.consume(dict(ordinal=1, kind="frame", received_ns=START, payload=snapshot(0)))
    _, base = features(
        market(), engine.books, decision_ns=START, spec=spec(), history={}, trades={}
    )
    future = json.loads(snapshot(100, moved=True))
    future[0]["asks"] = []
    engine.consume(
        dict(ordinal=2, kind="frame", received_ns=START + 100 * 10**6, payload=json.dumps(future))
    )
    assert (
        pair_quality(market(), engine.books, START + 100 * 10**6, spec(), allow_empty_asks=True)
        is None
    )
    result = labels(
        base,
        {
            o.lower(): book_view(engine.books[t], START + 100 * 10**6)
            for t, o in market()["tokens"].items()
        },
    )
    assert result["status"] == "observed_public_measurement"
    assert result["quote_persistence"] is False
    assert result["depth_at_original_quotes"]["yes"] == "0"
    assert result["adverse_ask_movement"] is None
    assert result["displayed_acquisition_cost"] is None
    assert result["opportunity_persistence"] is False


def test_temporal_contamination_and_execution_labels_rejected_even_if_rehashed(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "derived"
    result = build(root, target, spec(), tape(root, times=tuple(range(0, 12000, 100))))
    path = target / result["dataset_id"] / "examples.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["labels"]["actual_fill"] = True
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result["rows_sha256"] = file_hash(path)
    with pytest.raises(ValueError, match="claim fills"):
        verify_rows(path, result)
    del rows[0]["labels"]["actual_fill"]
    observed = next(row for row in rows if row["labels"]["status"] == "observed_public_measurement")
    observed["effective_delays_ms"]["yes"] = 99
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result["rows_sha256"] = file_hash(path)
    with pytest.raises(ValueError, match="Sub-event"):
        verify_rows(path, result)


def test_connected_sibling_markets_share_family_identity():
    from midas.reality.foundry import Families

    families = Families()
    families.add(["condition:one", "event:shared"])
    families.add(["condition:two", "event:shared"])
    families.add(["condition:three", "event:unrelated"])
    ids = families.identities()
    assert ids["condition:one"] == ids["condition:two"]
    assert ids["condition:one"] != ids["condition:three"]


def test_final_test_plan_freezing_resume_and_repeated_promotion_prohibition(tmp_path):
    from midas.reality.research_access import consume_final_test, open_final_test

    data = dict(
        dataset_id="dataset-a",
        partition_counts=dict(test=5),
        boundaries=dict(validation_end_ns=100),
        last_decision_ns=200,
        identity=dict(spec=dict(source_kind="labeled_fixture")),
    )
    plan = dict(
        selection_partition="validation",
        frozen_candidates=[dict(model_id="model-a", weights_sha256="a" * 64)],
        controls=["base-rate"],
    )
    entry = open_final_test(data, tmp_path, plan)
    assert open_final_test(data, tmp_path, plan) == entry
    with pytest.raises(ValueError, match="overlaps"):
        open_final_test(
            dict(data, dataset_id="other-builder-id"),
            tmp_path,
            dict(plan, controls=["retuned-control"]),
        )
    with pytest.raises(ValueError, match="validation-selected"):
        open_final_test(data, tmp_path, dict(plan, selection_partition="test"))
    consume_final_test(tmp_path, entry["evaluation_id"], "b" * 64)
    with pytest.raises(ValueError, match="consumed"):
        open_final_test(data, tmp_path, plan)
