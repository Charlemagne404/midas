"""Artificial metadata and localhost frames verify panel/quality invariants."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from midas.reality.config import Config
from midas.reality.observation import discover
from midas.reality.panel import enriched, queries, select_panel
from midas.reality.quality import clock_health, compare, depth_state
from midas.reality.reconstruction import Engine

NOW = 1791984000000000000


def market(i, liquidity=20000, change=0.02, category="Politics", end="2026-10-15T00:00:00Z"):
    return dict(
        id=str(i),
        question=f"Question {i}",
        version="v1",
        active=True,
        closed=False,
        acceptingOrders=True,
        enableOrderBook=True,
        conditionId=f"0x{i:064x}",
        clobTokenIds=json.dumps([str(i * 2), str(i * 2 + 1)]),
        outcomes='["Yes","No"]',
        volume24hr=1000,
        liquidityNum=liquidity,
        oneDayPriceChange=change,
        category=category,
        endDate=end,
        negRisk=False,
        negRiskOther=False,
        feesEnabled=True,
        feeSchedule=dict(rate=0.04, exponent=1, takerOnly=True),
        orderPriceMinTickSize=0.01,
        orderMinSize=5,
        events=[dict(id=str(i // 2))],
    )


def test_panel_coverage_and_all_decisions_no_edge_filter():
    raw = [
        market(1, liquidity=50000),
        market(2, liquidity=5000),
        market(3, liquidity=100),
        market(4, change=0.8),
        market(5, change=0),
        market(6, end="2026-10-14T14:00:00Z"),
        market(7, category="Weather", end="2026-10-20T00:00:00Z"),
        market(8),
        market(9),
        dict(market(10), version="v2"),
    ]
    cohort, audit = select_panel(raw, 8, now_ns=NOW, seed=42)
    assert len(cohort) == 8
    assert len(audit["decisions"]) == len(raw)
    assert [m["selection_role"] for m in cohort] == [
        "high",
        "medium",
        "thin",
        "fast",
        "stable",
        "near_expiry",
        "category",
        "random",
    ]
    assert cohort[1]["id"] == "2" and cohort[2]["id"] == "3"
    assert cohort[3]["id"] == "4" and cohort[4]["id"] == "5"
    assert cohort[6]["id"] == "7"
    assert not audit["decisions"][-1]["eligible"]
    changed = [dict(m, bestBid=1, bestAsk=0, outcomePrices='["0.001","0.001"]') for m in raw]
    assert [m["id"] for m in select_panel(changed, 8, now_ns=NOW, seed=42)[0]] == [
        m["id"] for m in cohort
    ]
    assert cohort == select_panel(list(reversed(raw)), 8, now_ns=NOW, seed=42)[0]


@pytest.mark.parametrize(
    "change",
    [
        dict(version="v2"),
        dict(positionIds=["1", "2"]),
        dict(outcomes='["Yes","Yes"]'),
        dict(negRisk=None),
        dict(negRiskOther=True),
        dict(orderMinSize=0),
        dict(orderPriceMinTickSize=2),
        dict(feesEnabled=None),
        dict(feeSchedule=None),
        dict(endDate="2026-10-15"),
        dict(liquidityNum="NaN"),
    ],
)
def test_ambiguous_and_invalid_market_exclusion(change):
    cohort, audit = select_panel([dict(market(1), **change)], 1, now_ns=NOW, seed=1)
    assert cohort == []
    assert not audit["decisions"][0]["eligible"]
    assert audit["decisions"][0]["reason"]


def test_random_control_reproducible_unique_tokens_and_missing_roles():
    raw = [market(i) for i in range(1, 25)]
    first, _ = select_panel(raw, 4, now_ns=NOW, seed=5, roles=("random",))
    repeated, _ = select_panel(raw, 4, now_ns=NOW, seed=5, roles=("random",))
    assert first == repeated
    assert first != select_panel(raw, 4, now_ns=NOW, seed=6, roles=("random",))[0]
    duplicate = dict(market(100), clobTokenIds=raw[0]["clobTokenIds"])
    chosen, audit = select_panel(
        [raw[0], raw[0], duplicate], 3, now_ns=NOW, seed=5, roles=("random",)
    )
    assert len(chosen) == 1
    assert "duplicate_market_response" in [d["reason"] for d in audit["decisions"]]
    assert audit["unfilled_roles"] == ["random", "random"]


def test_observed_rates_used_without_unknown_becoming_zero():
    cohort, audit = select_panel(
        [market(i) for i in range(1, 5)],
        1,
        now_ns=NOW,
        seed=1,
        roles=("stable",),
        update_rates={"1": 0.2, "2": 5},
    )
    assert cohort[0]["id"] == "1"
    assert cohort[0]["activity_selection_basis"] == "prior_observed_book_updates_per_second"
    assert audit["update_rates_observed_before_selection"] == {"1": 0.2, "2": 5}


def test_bounded_queries_and_metadata_units():
    specs = queries(50, NOW, 42)
    assert len(specs) == 6 and all(p["limit"] == 50 for _, p in specs)
    assert 0 <= specs[-1][1]["offset"] < 1000
    item = enriched(market(1))
    assert item["payoff"]["unit"] == "collateral_unit"
    assert item["fee_regime"]["status"] == "discovery_reported_not_execution_verified"
    assert item["event_ids"] == ["0"]


def local_book():
    return dict(
        bids={Decimal(".3"): Decimal("10")},
        asks={Decimal(".4"): Decimal("12")},
        last=[2, 0],
        snapshot=[1, 0],
        issue=None,
        received_ns=NOW,
    )


def compare_args():
    return dict(
        asset="2",
        condition="0x1",
        before=depth_state(local_book()),
        after=depth_state(local_book()),
        request_ns=NOW,
        response_ns=NOW + 1_000_000,
        stale_ns=60_000_000_000,
    )


def rest_book():
    return dict(
        asset_id="2",
        market="0x1",
        timestamp=str(NOW // 10**6),
        hash="opaque-native",
        bids=[dict(price="0.30", size="10.00")],
        asks=[dict(price="0.4", size="12")],
    )


def test_independent_depth_agreement_and_concurrent_uncertainty():
    args = compare_args()
    result = compare(rest_book(), **args)
    assert result["assessment"] == "stable_local_lineage_match_unsequenced"
    assert result["sequence_verified"] is False
    assert result["source_native_hash"] == "opaque-native"
    assert result["round_trip_ns"] == 1_000_000
    assert result["local_depth_sha256"]
    assert result["depth_difference_counts"] == {"bids": 0, "asks": 0}
    args["after"]["last"] = [3, 0]
    assert compare(rest_book(), **args)["assessment"] == "concurrent_updates_ambiguous"
    args["after"] = None
    assert compare(rest_book(), **args)["assessment"] == "ineligible_local_state"


def test_independent_divergence_stale_and_invalid_ids():
    raw, args = rest_book(), compare_args()
    raw["asks"][0]["size"] = "1"
    divergence = compare(raw, **args)
    assert divergence["assessment"] == "stable_local_lineage_divergence"
    assert divergence["depth_difference_counts"] == {"bids": 0, "asks": 1}
    assert divergence["local_depth_sha256"] != divergence["independent_depth_sha256"]
    args["response_ns"] += 61_000_000_000
    assert compare(raw, **args)["assessment"] == "stale_local_state"
    with pytest.raises(ValueError, match="mismatch"):
        compare(dict(raw, asset_id="3"), **args)
    raw["bids"].append(raw["bids"][0])
    with pytest.raises(ValueError, match="Duplicate"):
        compare(raw, **args)
    assert clock_health()["status"] in {
        "unknown",
        "kernel_synchronized",
        "kernel_unsynchronized_or_leap",
    }


async def test_discovery_records_every_page_and_verifies_exact_mapping(tmp_path):
    future_end = (datetime.now(UTC) + timedelta(days=2)).isoformat().replace("+00:00", "Z")
    raw = [
        market(
            i,
            liquidity=([20000, 5000, 100][(i - 1) % 3]),
            category=f"Category {i}",
            end=future_end,
        )
        for i in range(1, 10)
    ]
    captured = []

    def append(kind, payload, **kwargs):
        record = dict(kind=kind, payload=payload, ordinal=len(captured) + 1, **kwargs)
        captured.append(record)
        return record

    def handle(request):
        if request.url.host == "gamma-api.polymarket.com":
            return httpx.Response(200, json=raw)
        if request.url.path == "/fee-rate":
            return httpx.Response(200, json=dict(base_fee=1000))
        m = next(m for m in raw if m["conditionId"] == request.url.path.split("/")[-1])
        return httpx.Response(
            200,
            json=dict(
                version="v1",
                condition_id=m["conditionId"],
                tokens=[
                    dict(token_id=t, outcome=o)
                    for t, o in zip(json.loads(m["clobTokenIds"]), ["Yes", "No"], strict=True)
                ],
                closed=False,
                accepting_orders=True,
                neg_risk=False,
                tags=[m["category"]],
            ),
        )

    class FixtureConfig(Config):
        def __post_init__(self):
            pass

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        cohort, audit = await discover(
            client, FixtureConfig(root=str(tmp_path), markets=8), append, update_rates={}
        )
    assert len(cohort) == 8
    assert len(audit["page_ordinals"]) == 6
    assert len(audit["decisions"]) == 54
    assert len([r for r in captured if r["kind"] == "public_fee_metadata"]) == 16
    assert all(m["metadata_ordinal"] > audit["page_ordinals"][-1] for m in cohort)
    assert not audit["verification_rejections"]


def test_empty_side_revision_preserves_legacy_and_never_creates_liquidity():
    engine = Engine()
    book = local_book()
    book["asks"] = {}
    engine.check_top(book, dict(best_bid="0.3", best_ask="1"))
    assert book["issue"] == "top_divergence"  # legacy replay deliberately unchanged
    book["issue"] = None
    engine.consume(
        dict(
            ordinal=1,
            kind="gap",
            received_ns=NOW,
            payload=dict(reason="process_start", reconstruction_version=2),
        )
    )
    engine.check_top(book, dict(best_bid="0.3", best_ask="1"))
    assert book["issue"] is None
    assert Engine.top(book) == (Decimal(".3"), None)
    assert book["asks"] == {}
    engine.check_top(book, dict(best_bid="0.2", best_ask="1"))
    assert book["issue"] == "top_divergence"  # real differences still invalidate
    with pytest.raises(ValueError, match="reconstruction"):
        engine.consume(
            dict(
                ordinal=2,
                kind="gap",
                received_ns=NOW,
                payload=dict(reason="process_start", reconstruction_version=99),
            )
        )


def test_independent_comparison_does_not_round_away_real_depth_difference():
    args, raw = compare_args(), rest_book()
    args["before"]["bids"] = {"0.3": "10.00000000000000000000000000000000001"}
    args["after"]["bids"] = dict(args["before"]["bids"])
    assert compare(raw, **args)["assessment"] == "stable_local_lineage_divergence"


def test_genuine_empty_side_capture_and_rest_agree_without_invented_depth():
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "fixtures/reality/observed-empty-side.json").read_text()
    )
    observations = fixture["observations"]
    results = []
    for revision in (1, 2):
        engine = Engine()
        engine.reconstruction_version = (
            revision  # labeled test control, not modified source observations
        )
        engine.consume(observations["discovery"])
        engine.consume(observations["snapshot"])
        engine.consume(observations["update"])
        results.append(engine)
    assert results[0].counts["top_divergence"] == 2
    assert results[1].counts["top_divergence"] == 0
    for response in fixture["independent_rest_reads"]:
        raw = response["payload"]
        book = results[1].books[raw["asset_id"]]
        assert (not raw["asks"] and not book["asks"]) or (not raw["bids"] and not book["bids"])
        assert fixture["provenance"]["update"]["ordinal"] == observations["update"]["ordinal"]


def test_revision_three_advertisement_needs_confirming_depth_and_keeps_uncertainty():
    engine = Engine()
    engine.reconstruction_version = 3
    engine.tokens = {"2": "0x1"}
    book = local_book()
    book.update(
        exchange_ms=NOW // 10**6, quote_since_ns=NOW, quote_lifetimes=dict(count=0, total_ns=0)
    )
    engine.books["2"] = book
    advert = dict(
        event_type="best_bid_ask",
        market="0x1",
        asset_id="2",
        timestamp=str(NOW // 10**6),
        best_bid="0.3",
        best_ask="0.5",
    )
    engine.consume(dict(ordinal=3, kind="frame", received_ns=NOW + 1, payload=json.dumps(advert)))
    assert book["issue"] == "advertised_top_pending"
    assert engine.top(book) == (Decimal(".3"), Decimal(".4"))
    # A later advertisement alone is never invented as a depth correction.
    engine.consume(
        dict(
            ordinal=4,
            kind="frame",
            received_ns=NOW + 2,
            payload=json.dumps(dict(advert, best_ask="0.4")),
        )
    )
    assert book["issue"] == "advertised_top_pending"
    update = dict(
        event_type="price_change",
        market="0x1",
        timestamp=str(NOW // 10**6),
        price_changes=[
            dict(asset_id="2", side="SELL", price="0.4", size="0", best_bid="0.3", best_ask="0.5"),
            dict(asset_id="2", side="SELL", price="0.5", size="12", best_bid="0.3", best_ask="0.5"),
        ],
    )
    engine.consume(dict(ordinal=5, kind="frame", received_ns=NOW + 3, payload=json.dumps(update)))
    assert book["issue"] is None
    assert "pending_top_advertisement" not in book
    assert engine.top(book) == (Decimal(".3"), Decimal(".5"))
    engine.consume(
        dict(
            ordinal=6,
            kind="frame",
            received_ns=NOW + 4,
            payload=json.dumps(
                dict(
                    update,
                    price_changes=[
                        dict(
                            asset_id="2",
                            side="BUY",
                            price="0.1",
                            size="1",
                            best_bid="0.2",
                            best_ask="0.5",
                        )
                    ],
                )
            ),
        )
    )
    assert book["issue"] == "top_divergence"


def test_cached_snapshot_after_gap_is_observed_with_timing_qualifier_until_confirmation():
    engine = Engine()
    engine.reconstruction_version = 4
    engine.tokens = {"2": "0x1"}
    book = local_book()
    book.update(
        exchange_ms=2000,
        quote_since_ns=NOW,
        quote_lifetimes=dict(count=0, total_ns=0),
        hash="old",
        continuity="unsequenced_observed_lineage",
        tick=".01",
    )
    engine.books["2"] = book
    engine.consume(dict(ordinal=10, kind="gap", received_ns=NOW, payload=dict(reason="disconnect")))
    snapshot = dict(
        event_type="book",
        asset_id="2",
        market="0x1",
        timestamp="1000",
        hash="new",
        bids=[dict(price=".3", size="10")],
        asks=[dict(price=".4", size="12")],
    )
    engine.consume(
        dict(ordinal=11, kind="frame", received_ns=NOW + 1, payload=json.dumps(snapshot))
    )
    updated = engine.books["2"]
    assert updated["snapshot"] == [11, 0]
    assert updated["issue"] is None
    assert updated["source_timestamp_floor_ms"] == 2000
    assert updated["timing_uncertainty"] == "snapshot_source_timestamp_regressed_after_gap"
    # A later but still historically older snapshot cannot erase the qualification.
    engine.consume(
        dict(
            ordinal=12,
            kind="frame",
            received_ns=NOW + 2,
            payload=json.dumps(dict(snapshot, timestamp="1500")),
        )
    )
    updated = engine.books["2"]
    assert updated["source_timestamp_floor_ms"] == 2000
    change = dict(
        event_type="price_change",
        market="0x1",
        timestamp="2500",
        price_changes=[
            dict(asset_id="2", price=".3", size="11", side="BUY", best_bid=".3", best_ask=".4")
        ],
    )
    engine.consume(dict(ordinal=13, kind="frame", received_ns=NOW + 3, payload=json.dumps(change)))
    assert "timing_uncertainty" not in updated
    assert "source_timestamp_floor_ms" not in updated
    # Regressing a snapshot within uninterrupted observed lineage remains a failure.
    engine.consume(
        dict(ordinal=14, kind="frame", received_ns=NOW + 4, payload=json.dumps(snapshot))
    )
    assert updated["issue"] == "timestamp_regression"


def test_genuine_cached_snapshot_can_start_qualified_lineage_without_rewriting_legacy():
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent / "fixtures/reality/observed-cached-snapshot.json").read_text()
    )
    prior = fixture["prior_derived_book"]
    target = next(t for m in fixture["cohort"] for t in m["tokens"] if t.startswith("115563279943"))
    for revision in (3, 4):
        engine = Engine()
        engine.reconstruction_version = revision
        engine.tokens = {t: m["condition"] for m in fixture["cohort"] for t in m["tokens"]}
        engine.books[target] = dict(
            prior,
            bids={Decimal(p): Decimal(q) for p, q in prior["bids"]},
            asks={Decimal(p): Decimal(q) for p, q in prior["asks"]},
        )
        engine.consume(fixture["gap_record"])
        engine.consume(fixture["snapshot_record"])
        book = engine.books[target]
        if revision == 3:
            assert book["snapshot"] == prior["snapshot"]
            assert engine.counts["timestamp_regression"] >= 1
            assert book["issue"] in {"timestamp_regression", "stale"}
        else:
            assert book["snapshot"][0] == fixture["snapshot_record"]["ordinal"]
            assert book["source_timestamp_floor_ms"] == prior["exchange_ms"]
            assert book["timing_uncertainty"] == "snapshot_source_timestamp_regressed_after_gap"
            assert book["issue"] is None
