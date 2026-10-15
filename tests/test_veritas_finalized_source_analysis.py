from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from midas.reality.research_schema import FEATURE_VERSION, LABEL_VERSION, digest
from midas.reality.shadow_campaign import source_files
from midas.reality.storage import MAGIC, Store, describe, file_hash
from midas.veritas import finalized_source_analysis as analysis
from midas.veritas.raw_funnel import analyze_raw_opportunity_funnel

START = 1_792_000_000_000_000_000
CONDITION = "0x" + "1" * 64
PRODUCER_HASH = "a" * 64


def _market() -> dict[str, Any]:
    return dict(
        id="1",
        condition=CONDITION,
        protocol="v1",
        tokens={"11": "Yes", "12": "No"},
        payoff=dict(
            pair="same_condition_yes_no_ctf", combined_terminal_claim="1", unit="collateral_unit"
        ),
        fee_regime=dict(enabled=True, schedule=dict(rate=0.04, exponent=1, takerOnly=True)),
        event_ids=["fixture-event"],
        categories=["Fixture"],
        negative_risk=False,
        negative_risk_group=None,
        liquidity="5000",
        minimum_order_size="2",
        tick_size=".01",
        end_ns=START + 10**12,
        metadata_ordinal=2,
        public_market_constraints=dict(minimum_tick_size=".01"),
    )


def _frame(yes_ask: str) -> str:
    events = []
    for token, bid, ask in (("11", ".35", yes_ask), ("12", ".50", ".55")):
        events.append(
            dict(
                event_type="book",
                asset_id=token,
                market=CONDITION,
                timestamp=str(START // 10**6),
                hash=f"fixture-{token}-{ask}",
                bids=[dict(price=bid, size="100")],
                asks=[dict(price=ask, size="20")],
            )
        )
    return json.dumps(events)


def _fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    raw = tmp_path / "raw"
    raw.mkdir()
    store = Store(raw, reserve=1, segment_bytes=32 * 1024**2)
    store.rotate()
    store.append(
        "gap",
        dict(reason="process_start", reconstruction_version=4, implementation_sha256=PRODUCER_HASH),
        received_ns=START - 1_000_000_000,
        monotonic_ns=0,
    )
    store.append("public_market_metadata", "fixture metadata", received_ns=START, market_id="1")
    store.rotate()
    store.append("discovery", "fixture universe", received_ns=START, cohort=[_market()])
    store.rotate()
    store.append(
        "frame",
        _frame(".40"),
        received_ns=START + 1_000_000,
        monotonic_ns=1_000_000,
    )
    store.rotate()
    store.append(
        "frame",
        _frame(".50"),
        received_ns=START + 2_000_000,
        monotonic_ns=2_000_000,
    )
    store.close()

    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    identity = dict(
        version="reality-forward-campaign-v1",
        frozen_ns=START - 2 * 10**9,
        start_ns=START,
        end_ns=START + 100 * 10**6,
        raw_root=str(raw.resolve()),
        allowed_producer_hashes=[PRODUCER_HASH],
        allowed_reconstruction_versions=[4],
        feature_version=FEATURE_VERSION,
        label_version=LABEL_VERSION,
        horizons_ms=[100, 300, 1000, 5000],
        future_tolerance_ms=500,
        max_freshness_ms=5000,
        max_skew_ms=250,
        quantity="5",
        capital="100",
        code={name: file_hash(path) for name, path in source_files().items()},
    )
    plan = dict(campaign_id=digest(identity), identity=identity)
    campaign_path = campaign_dir / "campaign.json"
    campaign_path.write_text(json.dumps(plan))
    return campaign_dir, raw, file_hash(campaign_path)


def _run(
    root: Path, campaign_dir: Path, raw: Path, campaign_hash: str, **kwargs: Any
) -> dict[str, Any]:
    return analysis.update_finalized_source_analysis(
        root,
        campaign_path=campaign_dir / "campaign.json",
        expected_campaign_sha256=campaign_hash,
        expected_campaign_id=None,
        expected_source_root=raw,
        **kwargs,
    )


def test_finalized_source_analysis_is_bounded_resumable_and_matches_one_pass(tmp_path):
    campaign_dir, raw, campaign_hash = _fixture(tmp_path)
    output = tmp_path / "observatory"
    (raw / f"{'9' * 20}-{'b' * 32}.open").write_bytes(b"must remain unopened")
    expected = analyze_raw_opportunity_funnel(campaign_dir)

    first = _run(output, campaign_dir, raw, campaign_hash, max_segments=1)
    assert first["batch_processed_segment_count"] == 1
    assert first["pending_segment_count"] == 3
    assert first["active_segment_read"] is False

    summary = first
    for _ in range(3):
        summary = _run(output, campaign_dir, raw, campaign_hash, max_segments=1)

    assert summary["processed_segment_count"] == summary["catalog_segment_count"] == 4
    assert summary["empty_finalized_segment_count"] == 1
    assert summary["pending_segment_count"] == 0
    assert summary["cumulative"]["period_frame_records"] == expected["period_frame_records"]
    assert (
        summary["cumulative"]["touched_market_frame_states"]
        == expected["touched_market_frame_states"]
    )
    assert summary["cumulative"]["quality_valid_states"] == expected["quality_valid_states"]
    assert (
        summary["cumulative"]["positive_top_ask_pair_states"]
        == expected["positive_top_ask_pair_states"]
    )
    assert (
        summary["cumulative"]["positive_full_depth_pre_fee_states"]
        == expected["positive_full_depth_pre_fee_states"]
    )
    assert len(list((output / "source-analysis-events" / "v1").glob("*.json"))) == 4

    repeated = _run(output, campaign_dir, raw, campaign_hash)
    assert repeated["batch_processed_segment_count"] == 0
    assert repeated["cumulative"] == summary["cumulative"]
    assert len(list((output / "source-analysis-events" / "v1").glob("*.json"))) == 4


def test_finalized_source_prefix_catalog_mutation_is_rejected(tmp_path):
    campaign_dir, raw, campaign_hash = _fixture(tmp_path)
    output = tmp_path / "observatory"
    _run(output, campaign_dir, raw, campaign_hash, max_segments=1)

    sidecar = next(
        path
        for path in sorted(raw.glob("*.json"))
        if json.loads(path.read_text()).get("count") > 0
    )
    catalog = json.loads(sidecar.read_text())
    catalog["sha256"] = "f" * 64
    sidecar.write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match="catalog prefix changed"):
        _run(output, campaign_dir, raw, campaign_hash, max_segments=1)


def test_late_empty_finalized_segment_does_not_reorder_source_prefix(tmp_path):
    campaign_dir, raw, campaign_hash = _fixture(tmp_path)
    output = tmp_path / "observatory"
    first = _run(output, campaign_dir, raw, campaign_hash, max_segments=1)

    next_ordinal = first["last_processed_ordinal"] + 1
    empty = raw / f"{next_ordinal:020d}-{'c' * 32}.seg"
    empty.write_bytes(MAGIC)
    (raw / empty.with_suffix(".json").name).write_text(json.dumps(describe(empty)))
    resumed = _run(output, campaign_dir, raw, campaign_hash, max_segments=1)

    assert resumed["processed_segment_count"] == 2
    assert resumed["empty_finalized_segment_count"] == 2


def test_finalized_source_per_run_byte_bound_stops_oversized_next_segment(tmp_path):
    campaign_dir, raw, campaign_hash = _fixture(tmp_path)
    output = tmp_path / "observatory"

    with pytest.raises(ValueError, match="exceeds the per-run byte bound"):
        _run(output, campaign_dir, raw, campaign_hash, max_source_bytes=1)


def test_orphan_event_from_crash_is_replayed_once_and_then_committed(tmp_path, monkeypatch):
    campaign_dir, raw, campaign_hash = _fixture(tmp_path)
    output = tmp_path / "observatory"
    original_atomic_json = analysis._atomic_json
    failed = False

    def fail_state_once(path: Path, value: dict[str, Any], *, maximum: int) -> int:
        nonlocal failed
        if path.name == "source-analysis-state-v1.json" and not failed:
            failed = True
            raise OSError("simulated state commit interruption")
        return original_atomic_json(path, value, maximum=maximum)

    monkeypatch.setattr(analysis, "_atomic_json", fail_state_once)
    with pytest.raises(OSError, match="simulated"):
        _run(output, campaign_dir, raw, campaign_hash, max_segments=1)
    event_dir = output / "source-analysis-events" / "v1"
    assert len(list(event_dir.glob("*.json"))) == 1

    monkeypatch.setattr(analysis, "_atomic_json", original_atomic_json)
    summary = _run(output, campaign_dir, raw, campaign_hash, max_segments=1)
    assert summary["processed_segment_count"] == 1
    assert len(list(event_dir.glob("*.json"))) == 1
