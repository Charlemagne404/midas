"""Synthetic raw-funnel checks; no live Reality quote data is embedded."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from midas.reality.research_schema import FEATURE_VERSION, LABEL_VERSION, digest
from midas.reality.shadow_campaign import source_files
from midas.reality.storage import Store, file_hash
from midas.veritas.raw_funnel import MAX_SOURCE_BYTES, analyze_raw_opportunity_funnel

START = 1_792_000_000_000_000_000
CONDITION = "0x" + "1" * 64


def _market(minimum_order_size: str = "5") -> dict[str, Any]:
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
        minimum_order_size=minimum_order_size,
        tick_size=".01",
        end_ns=START + 10**12,
        metadata_ordinal=2,
        public_market_constraints=dict(minimum_tick_size=".01"),
    )


def _frame(yes_ask: str) -> str:
    events = []
    for token, bid, ask, size in (
        ("11", ".35", yes_ask, "10"),
        ("12", ".50", ".55", "20"),
    ):
        events.append(
            dict(
                event_type="book",
                asset_id=token,
                market=CONDITION,
                timestamp=str(START // 10**6),
                hash="fixture-native-" + token + ask,
                bids=[dict(price=bid, size="100")],
                asks=[dict(price=ask, size=size)],
            )
        )
    return json.dumps(events)


def _fixture(tmp_path: Path, *, minimum_order_size: str = "5") -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    store = Store(raw, reserve=1)
    store.append(
        "gap",
        dict(reason="process_start", reconstruction_version=4, implementation_sha256="a" * 64),
        received_ns=START,
        monotonic_ns=0,
    )
    store.append(
        "public_market_metadata",
        "fixture metadata",
        received_ns=START,
        monotonic_ns=0,
        market_id="1",
    )
    store.append(
        "discovery",
        "fixture universe",
        received_ns=START,
        monotonic_ns=0,
        cohort=[_market(minimum_order_size)],
    )
    for index, yes_ask in enumerate((".40", ".50"), 1):
        store.append(
            "frame",
            _frame(yes_ask),
            received_ns=START + index * 10**6,
            monotonic_ns=index * 10**6,
        )
    store.close()

    campaign = tmp_path / "campaign"
    campaign.mkdir()
    identity = dict(
        version="reality-forward-campaign-v1",
        frozen_ns=START - 2 * 10**9,
        start_ns=START,
        end_ns=START + 100 * 10**6,
        raw_root=str(raw.resolve()),
        allowed_producer_hashes=["a" * 64],
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
    (campaign / "campaign.json").write_text(json.dumps(plan))
    return campaign


def test_counts_quality_states_and_full_depth_without_opening_active_segment(tmp_path):
    campaign = _fixture(tmp_path)
    raw = tmp_path / "raw"
    (raw / "99999999999999999999-active.open").write_bytes(b"do not open")

    report = analyze_raw_opportunity_funnel(campaign)

    assert report["analysis_version"] == "veritas-raw-opportunity-funnel-v2"
    assert report["active_segment_read"] is False
    assert report["period_frame_records"] == 2
    assert report["touched_market_frame_states"] == 2
    assert report["quality_valid_states"] == 2
    assert report["quality_invalid_reason_counts"] == {}
    assert report["positive_top_ask_pair_states"] == 1
    assert report["quantity_depth_complete_states"] == 2
    assert report["positive_full_depth_pre_fee_states"] == 1
    assert report["pre_fee_top_edge_distribution"]["positive_count"] == 1
    assert report["markets"][0]["counts"]["touched_market_frame_states"] == 2


def test_minimum_order_size_is_checked_in_usdc_notional(tmp_path):
    report = analyze_raw_opportunity_funnel(_fixture(tmp_path, minimum_order_size="2"))

    assert report["positive_full_depth_pre_fee_states"] == 1
    assert report["positive_full_depth_minimum_notional_satisfied_states"] == 1


def test_share_quantity_above_minimum_does_not_satisfy_usdc_notional(tmp_path):
    report = analyze_raw_opportunity_funnel(_fixture(tmp_path, minimum_order_size="5"))

    assert report["quantity_requested"] == "5"
    assert report["positive_full_depth_pre_fee_states"] == 1
    assert report["positive_full_depth_minimum_notional_satisfied_states"] == 0


def test_source_byte_bound_is_checked(tmp_path):
    campaign = _fixture(tmp_path)
    with pytest.raises(ValueError, match="must be in 1..20 GiB"):
        analyze_raw_opportunity_funnel(campaign, max_source_bytes=MAX_SOURCE_BYTES + 1)
