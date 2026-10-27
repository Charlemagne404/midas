"""Bounded source-aware summaries over saved Frontier evidence.

These metrics describe the recent, locally recorded sample. They do not estimate
venue-wide prevalence, executable liquidity, or independent opportunity counts.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal, InvalidOperation, localcontext
from typing import Any

from midas.frontier.economics import OpportunityClassification
from midas.frontier.models import BookSnapshot, FrontierMarket, MarketInstrument, Venue

D = Decimal
_BPS = D(10_000)
MAX_CANDIDATE_ROWS = 5_000
_REJECTED_CLASSIFICATIONS = frozenset(
    {
        OpportunityClassification.INCOMPLETE_EVIDENCE.value,
        OpportunityClassification.INVALID_RELATIONSHIP.value,
        OpportunityClassification.NEGATIVE_AFTER_MODELED_COSTS.value,
        OpportunityClassification.UNSUPPORTED_ECONOMICS.value,
    }
)
_GROSS_CANDIDATE_CLASSIFICATIONS = frozenset(
    {
        OpportunityClassification.VERIFIED_MATHEMATICAL_INCONSISTENCY.value,
        OpportunityClassification.CONDITIONAL_ECONOMIC_OPPORTUNITY.value,
    }
)
MARKET_SAMPLE_LIMIT = 50
BOOK_SAMPLE_LIMIT = 50
REPLAY_SAMPLE_LIMIT = 20


@dataclass(frozen=True, slots=True)
class StoredBookEvidence:
    """A normalized book joined to its hash-checked observation row."""

    venue: str
    raw_sha256: str
    received_at_utc: datetime
    book: BookSnapshot


def _decimal_text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / D(2)


def _percentile(values: list[Decimal], percentile: Decimal) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int((D(len(ordered)) * percentile).to_integral_value(rounding=ROUND_CEILING)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _elapsed_ms(start: datetime, end: datetime) -> Decimal:
    delta = end.astimezone(UTC) - start.astimezone(UTC)
    microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    return D(microseconds) / D(1000)


def _quote_identity_key(instrument: MarketInstrument) -> str:
    identity = instrument.price_currency_identity
    if identity is None:
        return f"unresolved:{instrument.price_currency or 'unknown'}"

    def escape(value: str) -> str:
        return value.replace("%", "%25").replace(":", "%3A")

    parts = (
        identity.kind.value,
        identity.code,
        escape(identity.network_id or ""),
        escape(identity.asset_reference or ""),
    )
    return ":".join(parts)


def _integer(value: Any) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _candidate_signature(candidate: dict[str, Any]) -> tuple[str, ...] | None:
    legs = candidate.get("legs")
    if not isinstance(legs, list) or not 1 <= len(legs) <= 16:
        return None
    leg_signatures: list[str] = []
    for leg in legs:
        if not isinstance(leg, dict):
            return None
        fields = (
            leg.get("venue"),
            leg.get("market_id"),
            leg.get("native_market_id"),
            leg.get("instrument_id"),
            leg.get("outcome_id"),
            leg.get("quantity"),
            leg.get("market_observation_id"),
        )
        if any(not isinstance(value, (str, int)) or isinstance(value, bool) for value in fields):
            return None
        quote_currency = leg.get("quote_currency")
        if quote_currency is not None and not isinstance(quote_currency, str):
            return None
        quote_identity = leg.get("quote_currency_identity")
        if quote_identity is None:
            quote_identity_text = ""
        elif isinstance(quote_identity, dict):
            try:
                quote_identity_text = json.dumps(
                    quote_identity,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                    allow_nan=False,
                )
            except (TypeError, ValueError):
                return None
        else:
            return None
        normalized_fields = (
            *tuple(str(value) for value in fields),
            quote_currency or "",
            quote_identity_text,
        )
        if any(len(value) > 512 for value in normalized_fields):
            return None
        leg_signatures.append("\x00".join(normalized_fields))
    family = str(candidate.get("family", ""))
    relationship_id = str(candidate.get("relationship_id") or "")
    if len(family) > 80 or len(relationship_id) > 512:
        return None
    return (
        family,
        relationship_id,
        *sorted(leg_signatures),
    )


def summarize_frontier_coverage(
    *,
    market_records: tuple[tuple[FrontierMarket, str], ...],
    book_records: tuple[StoredBookEvidence, ...],
    replay_rows: tuple[dict[str, Any], ...],
    as_of_utc: datetime,
    invalid_book_record_count: int = 0,
    stored_market_counts_by_venue: tuple[tuple[str, int, int], ...] = (),
) -> dict[str, Any]:
    """Summarize bounded latest markets, books, and eligible replay results."""
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise ValueError("Coverage analytics as-of time must be timezone-aware")
    if (
        len(market_records) > MARKET_SAMPLE_LIMIT
        or len(book_records) > BOOK_SAMPLE_LIMIT
        or len(replay_rows) > REPLAY_SAMPLE_LIMIT
    ):
        raise ValueError("Coverage analytics inputs exceed their bounded sample windows")
    if invalid_book_record_count < 0:
        raise ValueError("Invalid book-record count must be nonnegative")
    if any(
        item.received_at_utc.tzinfo is None or item.received_at_utc.utcoffset() is None
        for item in book_records
    ):
        raise ValueError("Stored book record timestamps must be timezone-aware")

    with localcontext() as context:
        context.prec = 96
        markets_by_native: dict[tuple[str, str], FrontierMarket] = {}
        unique_markets: dict[str, FrontierMarket] = {}
        for market_value, _observation_id in market_records:
            previous_market = unique_markets.get(market_value.canonical_id)
            if previous_market is None or (
                market_value.provenance.response_received_at_utc,
                market_value.provenance.observation_id,
            ) > (
                previous_market.provenance.response_received_at_utc,
                previous_market.provenance.observation_id,
            ):
                unique_markets[market_value.canonical_id] = market_value

        ambiguous_native_markets: set[tuple[str, str]] = set()
        for market_value in unique_markets.values():
            native_key = (market_value.venue.value, market_value.native_market_id)
            previous_native_market = markets_by_native.get(native_key)
            if (
                previous_native_market is not None
                and previous_native_market.canonical_id != market_value.canonical_id
            ):
                ambiguous_native_markets.add(native_key)
                markets_by_native.pop(native_key, None)
            elif native_key not in ambiguous_native_markets:
                markets_by_native[native_key] = market_value

        market_groups: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"markets": 0, "instruments": 0, "events": 0}
        )
        event_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
        for market_value in unique_markets.values():
            market_group_key = (market_value.venue.value, market_value.market_kind.value)
            market_groups[market_group_key]["markets"] += 1
            market_groups[market_group_key]["instruments"] += len(market_value.instruments)
            if market_value.native_event_id:
                event_ids[market_group_key].add(market_value.native_event_id)
        for market_group_key, values in market_groups.items():
            values["events"] = len(event_ids[market_group_key])

        # Preserve only the newest well-joined snapshot per native instrument.
        latest_books: dict[
            tuple[str, str, str], tuple[StoredBookEvidence, MarketInstrument, str]
        ] = {}
        book_record_issues: Counter[str] = Counter()
        for stored in book_records:
            book = stored.book
            venue = stored.venue
            if (
                venue != book.venue.value
                or stored.raw_sha256 != book.provenance.raw_sha256
                or stored.received_at_utc.astimezone(UTC) != book.received_at_utc.astimezone(UTC)
                or book.provenance.response_received_at_utc.astimezone(UTC)
                != stored.received_at_utc.astimezone(UTC)
            ):
                book_record_issues[venue] += 1
                continue
            native_key = (venue, book.native_market_id)
            if native_key in ambiguous_native_markets:
                book_record_issues[venue] += 1
                continue
            joined_market = markets_by_native.get(native_key)
            matched_instrument = (
                next(
                    (
                        item
                        for item in joined_market.instruments
                        if item.native_instrument_id == book.native_instrument_id
                    ),
                    None,
                )
                if joined_market is not None
                else None
            )
            if joined_market is None or matched_instrument is None:
                book_record_issues[venue] += 1
                continue
            if (
                book.quantity_unit != matched_instrument.quantity_unit
                or book.price_currency != matched_instrument.price_currency
                or book.price_currency_identity != matched_instrument.price_currency_identity
                or joined_market.venue != book.venue
            ):
                book_record_issues[venue] += 1
                continue
            book_key = (venue, book.native_market_id, book.native_instrument_id)
            previous_book = latest_books.get(book_key)
            if previous_book is None or (
                stored.received_at_utc,
                book.provenance.observation_id,
            ) > (
                previous_book[0].received_at_utc,
                previous_book[0].book.provenance.observation_id,
            ):
                latest_books[book_key] = (
                    stored,
                    matched_instrument,
                    joined_market.market_kind.value,
                )

        quality: dict[str, Counter[str]] = {venue.value: Counter() for venue in Venue}
        ages_by_venue: dict[str, list[Decimal]] = defaultdict(list)
        spreads: dict[tuple[str, str, str, str], list[Decimal]] = defaultdict(list)
        bid_depths: dict[tuple[str, str, str, str], list[Decimal]] = defaultdict(list)
        ask_depths: dict[tuple[str, str, str, str], list[Decimal]] = defaultdict(list)
        for (venue, _market_id, _instrument_id), (
            stored,
            instrument,
            market_kind,
        ) in latest_books.items():
            book = stored.book
            counts = quality.setdefault(venue, Counter())
            counts["latest_instrument_books"] += 1
            if book.asks and book.bids:
                counts["two_sided_books"] += 1
            else:
                counts["one_sided_or_empty_books"] += 1
            if book.crossed:
                counts["crossed_books"] += 1
            if book.quality_flags:
                counts["flagged_books"] += 1
            else:
                counts["unflagged_books"] += 1
            if book.exchange_timestamp_utc is not None:
                counts["with_exchange_timestamp"] += 1
            if book.provenance.clock_uncertainty_ms is not None:
                counts["with_clock_uncertainty"] += 1
            age = _elapsed_ms(book.received_at_utc, as_of_utc)
            if age < 0:
                counts["future_received_timestamp"] += 1
            else:
                ages_by_venue[venue].append(age)
            if book.freshness_limit_ms is not None:
                counts["with_declared_freshness_limit"] += 1
                if age >= 0:
                    if age > D(book.freshness_limit_ms):
                        counts["stale_by_declared_freshness_limit"] += 1
                    else:
                        counts["within_declared_freshness_limit"] += 1
            else:
                counts["without_declared_freshness_limit"] += 1

            if (
                not book.asks
                or not book.bids
                or book.crossed
                or book.quality_flags
                or instrument.price_currency_identity is None
            ):
                continue
            bid = max(book.bids, key=lambda level: level.price)
            ask = min(book.asks, key=lambda level: level.price)
            midpoint = (bid.price + ask.price) / D(2)
            if midpoint <= 0 or ask.price < bid.price:
                continue
            pricing_key = (
                venue,
                market_kind,
                instrument.quantity_unit.value,
                _quote_identity_key(instrument),
            )
            counts["quality_valid_pricing_books"] += 1
            spreads[pricing_key].append((ask.price - bid.price) / midpoint * _BPS)
            bid_depths[pricing_key].append(bid.quantity)
            ask_depths[pricing_key].append(ask.quantity)

        source_quality = []
        for venue in sorted({item.value for item in Venue} | set(quality)):
            counts = quality.get(venue, Counter())
            ages = ages_by_venue.get(venue, [])
            source_quality.append(
                {
                    "venue": venue,
                    "latest_instrument_books": counts["latest_instrument_books"],
                    "quality_valid_pricing_books": counts["quality_valid_pricing_books"],
                    "two_sided_books": counts["two_sided_books"],
                    "one_sided_or_empty_books": counts["one_sided_or_empty_books"],
                    "crossed_books": counts["crossed_books"],
                    "flagged_books": counts["flagged_books"],
                    "unflagged_books": counts["unflagged_books"],
                    "unjoined_or_provenance_mismatch_records": book_record_issues[venue],
                    "with_exchange_timestamp": counts["with_exchange_timestamp"],
                    "with_clock_uncertainty": counts["with_clock_uncertainty"],
                    "with_declared_freshness_limit": counts["with_declared_freshness_limit"],
                    "without_declared_freshness_limit": counts["without_declared_freshness_limit"],
                    "within_declared_freshness_limit": counts["within_declared_freshness_limit"],
                    "stale_by_declared_freshness_limit": counts[
                        "stale_by_declared_freshness_limit"
                    ],
                    "future_received_timestamp": counts["future_received_timestamp"],
                    "median_receipt_age_ms": _decimal_text(_median(ages)),
                    "p90_receipt_age_ms": _decimal_text(_percentile(ages, D("0.90"))),
                }
            )

        pricing = []
        for pricing_key in sorted(spreads):
            venue, market_kind, quantity_unit, quote_identity = pricing_key
            pricing.append(
                {
                    "venue": venue,
                    "market_kind": market_kind,
                    "quantity_unit": quantity_unit,
                    "quote_asset_identity": quote_identity,
                    "instrument_count": len(spreads[pricing_key]),
                    "median_relative_spread_bps": _decimal_text(_median(spreads[pricing_key])),
                    "p90_relative_spread_bps": _decimal_text(
                        _percentile(spreads[pricing_key], D("0.90"))
                    ),
                    "median_best_bid_depth": _decimal_text(_median(bid_depths[pricing_key])),
                    "median_best_ask_depth": _decimal_text(_median(ask_depths[pricing_key])),
                }
            )

        candidate_classifications: Counter[str] = Counter()
        rejection_reasons: Counter[str] = Counter()
        receive_skews: list[Decimal] = []
        exchange_skews: list[Decimal] = []
        independently_audited = 0
        timing_verified = 0
        candidate_rows = 0
        candidate_scan_truncated = False
        repeated_gross_positive: dict[tuple[str, ...], dict[str, Any]] = {}
        for row in replay_rows:
            result = row.get("result")
            candidates = result.get("candidates", []) if isinstance(result, dict) else []
            if not isinstance(candidates, (list, tuple)):
                continue
            for candidate in candidates:
                if candidate_rows >= MAX_CANDIDATE_ROWS:
                    candidate_scan_truncated = True
                    break
                if not isinstance(candidate, dict):
                    continue
                candidate_rows += 1
                classification = candidate.get("classification")
                if isinstance(classification, str) and len(classification) <= 100:
                    candidate_classifications[classification] += 1
                reasons = candidate.get("reasons", ())
                if classification in _REJECTED_CLASSIFICATIONS and isinstance(
                    reasons, (list, tuple)
                ):
                    candidate_reasons: set[str] = set()
                    for reason in reasons[:32]:
                        if isinstance(reason, str) and reason.strip():
                            candidate_reasons.add(reason.strip()[:200])
                    for reason in candidate_reasons:
                        rejection_reasons[reason] += 1
                audit = candidate.get("independent_audit")
                if not isinstance(audit, dict) or audit.get("disposition") != "verified":
                    continue
                independently_audited += 1
                receipt_skew = _integer(audit.get("recomputed_received_skew_ms"))
                exchange_skew = _integer(audit.get("recomputed_exchange_skew_ms"))
                if receipt_skew is not None:
                    receive_skews.append(D(receipt_skew))
                if exchange_skew is not None:
                    exchange_skews.append(D(exchange_skew))
                audit_timing = audit.get("recomputed_timing_verified") is True
                if audit_timing:
                    timing_verified += 1
                gross = audit.get("recomputed_worst_case_gross_pnl")
                try:
                    gross_value = D(str(gross))
                except (InvalidOperation, TypeError, ValueError):
                    continue
                signature = _candidate_signature(candidate)
                legs = candidate.get("legs")
                if (
                    not audit_timing
                    or not gross_value.is_finite()
                    or gross_value <= 0
                    or classification not in _GROSS_CANDIDATE_CLASSIFICATIONS
                    or signature is None
                    or not isinstance(legs, list)
                ):
                    continue
                book_ids = tuple(
                    sorted(
                        str(item.get("book_observation_id"))
                        for item in legs
                        if isinstance(item, dict)
                        and isinstance(item.get("book_observation_id"), str)
                    )
                )
                observed_at = candidate.get("observed_at_utc")
                if len(book_ids) != len(legs) or not isinstance(observed_at, str):
                    continue
                try:
                    observed_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if observed_time.tzinfo is None or observed_time.utcoffset() is None:
                    continue
                group = repeated_gross_positive.setdefault(
                    signature, {"books": set(), "times": set()}
                )
                group["books"].add(book_ids)
                group["times"].add(observed_time.astimezone(UTC).isoformat())
            if candidate_scan_truncated:
                break

        recurring = [
            value
            for value in repeated_gross_positive.values()
            if len(value["books"]) > 1 and len(value["times"]) > 1
        ]
        reason_rows = [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                rejection_reasons.items(), key=lambda item: (-item[1], item[0])
            )[:20]
        ]
        return {
            "schema_version": 1,
            "as_of_utc": as_of_utc.astimezone(UTC).isoformat(),
            "scope": "Latest bounded hash-checked stored market, book, and eligible replay samples.",
            "samples": {
                "distinct_markets": len(unique_markets),
                "market_records": len(market_records),
                "book_observation_records": len(book_records) + invalid_book_record_count,
                "invalid_normalized_book_records": invalid_book_record_count,
                "unique_instrument_books": len(latest_books),
                "eligible_replay_runs": len(replay_rows),
                "candidate_records": candidate_rows,
                "candidate_scan_truncated": candidate_scan_truncated,
                "market_record_limit": MARKET_SAMPLE_LIMIT,
                "book_record_limit": BOOK_SAMPLE_LIMIT,
                "replay_run_limit": REPLAY_SAMPLE_LIMIT,
                "candidate_record_limit": MAX_CANDIDATE_ROWS,
            },
            "stored_market_counts_by_venue": [
                {
                    "venue": venue,
                    "market_count": market_count,
                    "instrument_count": instrument_count,
                }
                for venue, market_count, instrument_count in stored_market_counts_by_venue
            ],
            "market_mix": [
                {
                    "venue": venue,
                    "market_kind": kind,
                    "market_count": values["markets"],
                    "instrument_count": values["instruments"],
                    "event_count": values["events"],
                }
                for (venue, kind), values in sorted(market_groups.items())
            ],
            "source_quality": source_quality,
            "pricing": pricing,
            "candidate_research": {
                "counts_by_classification": dict(sorted(candidate_classifications.items())),
                "independently_audited_candidates": independently_audited,
                "audited_timing_verified_candidates": timing_verified,
                "median_audited_received_skew_ms": _decimal_text(_median(receive_skews)),
                "p90_audited_received_skew_ms": _decimal_text(
                    _percentile(receive_skews, D("0.90"))
                ),
                "median_audited_exchange_skew_ms": _decimal_text(_median(exchange_skews)),
                "p90_audited_exchange_skew_ms": _decimal_text(
                    _percentile(exchange_skews, D("0.90"))
                ),
                "gross_positive_audited_timing_verified_constructions_repeated_across_distinct_books": len(
                    recurring
                ),
                "gross_positive_candidate_construction_signatures": len(repeated_gross_positive),
                "rejection_reasons": reason_rows,
            },
            "network_called": False,
            "limitations": [
                "Counts describe bounded recorded samples, not venue-wide coverage or opportunity prevalence.",
                "Pricing summaries include only latest per-instrument two-sided, uncrossed, unflagged books with matching market units and exact quote-asset identity.",
                "Receipt age is measured at this API response; a missing venue freshness limit remains unknown.",
                "Cross-market timing summaries use independently verified replay audits; missing exchange timestamps or clock uncertainty are not inferred.",
                "Candidate counts are replay records and may repeat overlapping inputs; they are not independent opportunities.",
                "Rejection-reason frequencies count each distinct reason once per candidate classified as incomplete, invalid, negative after modeled costs, or unsupported.",
                "Repeated gross-positive construction counts require verified audit, verified timing, distinct pinned book sets, and distinct replay times; they do not establish positive net economics, continuous persistence, or executable profit.",
            ],
        }
