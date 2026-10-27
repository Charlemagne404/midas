from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext

from midas.frontier.analytics import (
    MARKET_SAMPLE_LIMIT,
    StoredBookEvidence,
    summarize_frontier_coverage,
)
from midas.frontier.models import (
    BookLevel,
    SettlementAssetIdentity,
    SettlementAssetKind,
    Venue,
)

from tests.frontier.builders import T0, book, market

D = Decimal


def _stored_book(book_value, received_at, raw_sha256):
    provenance = book_value.provenance.model_copy(
        update={
            "request_started_at_utc": received_at - timedelta(milliseconds=10),
            "response_received_at_utc": received_at,
            "processed_at_utc": received_at,
            "raw_sha256": raw_sha256,
        }
    )
    saved_book = book_value.model_copy(
        update={"received_at_utc": received_at, "provenance": provenance}
    )
    return StoredBookEvidence(
        venue=saved_book.venue.value,
        raw_sha256=raw_sha256,
        received_at_utc=received_at,
        book=saved_book,
    )


def _candidate(
    *,
    book_ids: tuple[str, str],
    observed_at: str,
    classification: str = "CONDITIONAL ECONOMIC OPPORTUNITY",
) -> dict[str, object]:
    left = market(Venue.POLYMARKET, "analytics-left")
    right = market(Venue.KALSHI, "analytics-right")
    return {
        "family": "cross_venue_complete_coverage",
        "relationship_id": "relationship-1",
        "market_ids": [left.canonical_id, right.canonical_id],
        "venues": ["kalshi", "polymarket"],
        "classification": classification,
        "worst_case_gross_pnl": "0.1",
        "observed_at_utc": observed_at,
        "reasons": ["candidate uses a controlled fixture", "candidate uses a controlled fixture"],
        "independent_audit": {
            "disposition": "verified",
            "recomputed_worst_case_gross_pnl": "0.1",
            "recomputed_received_skew_ms": 12,
            "recomputed_exchange_skew_ms": 8,
            "recomputed_timing_verified": True,
        },
        "legs": [
            {
                "venue": "polymarket",
                "market_id": left.canonical_id,
                "instrument_id": left.instruments[0].native_instrument_id,
                "outcome_id": "yes",
                "quantity": "1",
                "book_observation_id": book_ids[0],
            },
            {
                "venue": "kalshi",
                "market_id": right.canonical_id,
                "instrument_id": right.instruments[0].native_instrument_id,
                "outcome_id": "yes",
                "quantity": "1",
                "book_observation_id": book_ids[1],
            },
        ],
    }


def test_empty_analytics_are_bounded_and_have_explicit_sample_scope():
    result = summarize_frontier_coverage(
        market_records=(),
        book_records=(),
        replay_rows=(),
        as_of_utc=T0,
    )

    assert result["samples"]["distinct_markets"] == 0
    assert result["samples"]["market_record_limit"] == MARKET_SAMPLE_LIMIT
    assert result["market_mix"] == []
    assert result["pricing"] == []
    assert result["candidate_research"]["counts_by_classification"] == {}
    assert {item["venue"] for item in result["source_quality"]} == {
        "polymarket",
        "kalshi",
        "kraken",
        "coinbase_exchange",
    }
    assert all(item["quality_valid_pricing_books"] == 0 for item in result["source_quality"])
    assert any("not venue-wide coverage" in item for item in result["limitations"])


def test_pricing_summary_uses_latest_joined_book_and_preserves_unit_denominators():
    source_market = market(Venue.POLYMARKET, "analytics-book")
    yes = source_market.instruments[0]
    old = _stored_book(book(source_market, yes.native_instrument_id, "0.60"), T0, "1" * 64)
    latest = _stored_book(
        book(source_market, yes.native_instrument_id, "0.51"),
        T0 + timedelta(seconds=4),
        "2" * 64,
    )
    result = summarize_frontier_coverage(
        market_records=((source_market, "market-observation"),),
        book_records=(old, latest),
        replay_rows=(),
        as_of_utc=T0 + timedelta(seconds=5),
    )

    assert result["samples"]["book_observation_records"] == 2
    assert result["samples"]["unique_instrument_books"] == 1
    assert result["market_mix"] == [
        {
            "venue": "polymarket",
            "market_kind": "binary_event",
            "market_count": 1,
            "instrument_count": 2,
            "event_count": 1,
        }
    ]
    quality = next(item for item in result["source_quality"] if item["venue"] == "polymarket")
    assert quality["quality_valid_pricing_books"] == 1
    assert quality["median_receipt_age_ms"] == "1000"
    pricing = result["pricing"][0]
    assert pricing["quantity_unit"] == "share"
    assert pricing["quote_asset_identity"] == "fiat:USD::"
    assert pricing["instrument_count"] == 1
    with localcontext() as context:
        context.prec = 96
        expected_spread = D("0.01") / D("0.505") * D(10_000)
    assert D(pricing["median_relative_spread_bps"]) == expected_spread


def test_quality_counts_flagged_crossed_and_declared_stale_books_separately():
    source_market = market(Venue.POLYMARKET, "analytics-quality")
    yes, no = source_market.instruments
    valid = _stored_book(book(source_market, yes.native_instrument_id, "0.51"), T0, "3" * 64)
    no_book = book(source_market, no.native_instrument_id, "0.51")
    crossed_book = no_book.model_copy(
        update={
            "asks": (BookLevel(price=D("0.49"), quantity=D(10)),),
            "bids": (BookLevel(price=D("0.50"), quantity=D(10)),),
            "freshness_limit_ms": 500,
            "quality_flags": ("CROSSED_OR_LOCKED",),
        }
    )
    crossed = _stored_book(crossed_book, T0, "4" * 64)
    result = summarize_frontier_coverage(
        market_records=((source_market, "market-observation"),),
        book_records=(valid, crossed),
        replay_rows=(),
        as_of_utc=T0 + timedelta(seconds=1),
    )

    quality = next(item for item in result["source_quality"] if item["venue"] == "polymarket")
    assert quality["latest_instrument_books"] == 2
    assert quality["quality_valid_pricing_books"] == 1
    assert quality["crossed_books"] == 1
    assert quality["flagged_books"] == 1
    assert quality["stale_by_declared_freshness_limit"] == 1
    assert result["pricing"][0]["instrument_count"] == 1


def test_recurrence_requires_distinct_books_and_distinct_replay_times():
    first = _candidate(book_ids=("a" * 64, "b" * 64), observed_at=T0.isoformat())
    repeated_same_books = _candidate(
        book_ids=("a" * 64, "b" * 64), observed_at=(T0 + timedelta(seconds=1)).isoformat()
    )
    second_books = _candidate(
        book_ids=("c" * 64, "d" * 64), observed_at=(T0 + timedelta(seconds=2)).isoformat()
    )
    rejected = _candidate(
        book_ids=("e" * 64, "f" * 64),
        observed_at=(T0 + timedelta(seconds=3)).isoformat(),
        classification="INCOMPLETE EVIDENCE",
    )
    result = summarize_frontier_coverage(
        market_records=(),
        book_records=(),
        replay_rows=(
            {"run_id": "1", "result": {"candidates": [first]}},
            {"run_id": "2", "result": {"candidates": [repeated_same_books]}},
            {"run_id": "3", "result": {"candidates": [second_books, rejected]}},
        ),
        as_of_utc=T0 + timedelta(seconds=3),
    )

    candidate_metrics = result["candidate_research"]
    assert candidate_metrics["counts_by_classification"] == {
        "CONDITIONAL ECONOMIC OPPORTUNITY": 3,
        "INCOMPLETE EVIDENCE": 1,
    }
    assert candidate_metrics["independently_audited_candidates"] == 4
    assert candidate_metrics["audited_timing_verified_candidates"] == 4
    assert (
        candidate_metrics[
            "gross_positive_audited_timing_verified_constructions_repeated_across_distinct_books"
        ]
        == 1
    )
    assert candidate_metrics["rejection_reasons"] == [
        {"reason": "candidate uses a controlled fixture", "count": 1}
    ]


def test_bad_source_lineage_is_excluded_from_price_metrics():
    source_market = market(Venue.KALSHI, "analytics-lineage")
    source_book = book(source_market, source_market.instruments[0].native_instrument_id, "0.51")
    inconsistent = StoredBookEvidence(
        venue=Venue.KALSHI.value,
        raw_sha256="0" * 64,
        received_at_utc=T0,
        book=source_book,
    )
    result = summarize_frontier_coverage(
        market_records=((source_market, "market-observation"),),
        book_records=(inconsistent,),
        replay_rows=(),
        as_of_utc=T0,
    )

    quality = next(item for item in result["source_quality"] if item["venue"] == "kalshi")
    assert quality["unjoined_or_provenance_mismatch_records"] == 1
    assert quality["quality_valid_pricing_books"] == 0
    assert result["pricing"] == []


def test_conflicting_native_market_aliases_are_not_joined():
    source_market = market(Venue.POLYMARKET, "analytics-ambiguous-native")
    conflicting_alias = source_market.model_copy(
        update={"canonical_id": f"{source_market.canonical_id}-alias"}
    )
    source_book = _stored_book(
        book(source_market, source_market.instruments[0].native_instrument_id, "0.51"),
        T0,
        "5" * 64,
    )
    result = summarize_frontier_coverage(
        market_records=(
            (source_market, "market-observation-a"),
            (conflicting_alias, "market-observation-b"),
        ),
        book_records=(source_book,),
        replay_rows=(),
        as_of_utc=T0,
    )

    quality = next(item for item in result["source_quality"] if item["venue"] == "polymarket")
    assert quality["unjoined_or_provenance_mismatch_records"] == 1
    assert quality["quality_valid_pricing_books"] == 0
    assert result["pricing"] == []


def test_delimiter_characters_cannot_merge_distinct_quote_asset_identities():
    source_market = market(Venue.POLYMARKET, "analytics-delimiter-identities")
    first_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="TOK",
        network_id="net:chain",
        asset_reference="ref",
    )
    second_identity = SettlementAssetIdentity(
        kind=SettlementAssetKind.TOKEN,
        code="TOK",
        network_id="net",
        asset_reference="chain:ref",
    )
    instruments = tuple(
        item.model_copy(update={"price_currency": "TOK", "price_currency_identity": identity})
        for item, identity in zip(
            source_market.instruments, (first_identity, second_identity), strict=True
        )
    )
    quoted_market = source_market.model_copy(update={"instruments": instruments})
    book_records = tuple(
        _stored_book(
            book(quoted_market, item.native_instrument_id, "0.51"),
            T0,
            str(index) * 64,
        )
        for index, item in enumerate(quoted_market.instruments, start=6)
    )

    result = summarize_frontier_coverage(
        market_records=((quoted_market, "market-observation"),),
        book_records=book_records,
        replay_rows=(),
        as_of_utc=T0,
    )

    assert [item["quote_asset_identity"] for item in result["pricing"]] == [
        "token:TOK:net%3Achain:ref",
        "token:TOK:net:chain%3Aref",
    ]
    assert all(item["instrument_count"] == 1 for item in result["pricing"])
