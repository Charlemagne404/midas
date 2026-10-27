"""Virtual, assumption-driven capital carry sensitivity for saved candidates.

This is a research sensitivity, not an exchange fee schedule or an execution
model. It requires every position leg to retain its pinned market observation
and verified future settlement metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from midas.frontier.economics import OpportunityCandidate
from midas.frontier.models import FrontierMarket, FrontierModel, SettlementAssetIdentity

_D = Decimal
_YEAR_SECONDS = _D(365 * 24 * 60 * 60)
_BPS_DENOMINATOR = _D(10_000)
_MODEL_VERSION = "frontier-virtual-capital-carry-1"
_RATE_TEXT = re.compile(r"^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _bounded_decimal(value: Decimal, name: str) -> Decimal:
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    parts = value.as_tuple()
    exponent = parts.exponent
    adjusted = value.adjusted()
    if (
        len(parts.digits) > 64
        or not isinstance(exponent, int)
        or not -64 <= exponent <= 64
        or not isinstance(adjusted, int)
        or not -64 <= adjusted <= 64
    ):
        raise ValueError(f"{name} exceeds the exact arithmetic bound")
    return value


class CapitalCarryRequest(FrontierModel):
    """A bounded set of user-entered annual funding assumptions, in basis points."""

    run_id: str = Field(pattern=_SHA256.pattern)
    run_sha256: str = Field(pattern=_SHA256.pattern)
    candidate_id: str = Field(pattern=_SHA256.pattern)
    annual_rate_bps_by_venue: dict[str, str] = Field(min_length=1, max_length=8)

    @field_validator("annual_rate_bps_by_venue")
    @classmethod
    def validate_annual_rates(cls, values: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for venue, text in values.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", venue):
                raise ValueError("Venue identifiers must be normalized lowercase names")
            if not isinstance(text, str) or len(text) > 16 or not _RATE_TEXT.fullmatch(text):
                raise ValueError(
                    "Annual carry rates must be decimal strings from 0 to 999999.999999 bps"
                )
            try:
                rate = _D(text)
            except InvalidOperation as error:
                raise ValueError("Annual carry rate is not a decimal number") from error
            if not rate.is_finite() or rate < 0:
                raise ValueError("Annual carry rates must be finite and nonnegative")
            normalized[venue] = text
        return normalized


class MarketSettlementEvidence(FrontierModel):
    market_id: str = Field(min_length=1, max_length=512)
    venue: str = Field(min_length=1, max_length=80)
    observation_id: str = Field(pattern=_SHA256.pattern)
    observation_row_sha256: str = Field(pattern=_SHA256.pattern)
    raw_sha256: str = Field(pattern=_SHA256.pattern)
    resolution_fingerprint: str = Field(min_length=1, max_length=512)
    resolution_evidence_sha256: str = Field(pattern=_SHA256.pattern)
    settles_at_utc: datetime

    @field_validator("settles_at_utc")
    @classmethod
    def settlement_timestamp_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Settlement timestamps must include a timezone")
        return value.astimezone(UTC)


class VenueCapitalCarry(FrontierModel):
    venue: str = Field(min_length=1, max_length=80)
    capital: Decimal = Field(ge=0, allow_inf_nan=False)
    annual_rate_bps: Decimal = Field(ge=0, le=999999.999999, allow_inf_nan=False)
    start_at_utc: datetime
    capital_released_at_utc: datetime
    duration_seconds: Decimal = Field(gt=0, allow_inf_nan=False)
    carry_cost: Decimal = Field(ge=0, allow_inf_nan=False)
    settlement_evidence: tuple[MarketSettlementEvidence, ...] = Field(min_length=1, max_length=16)

    @field_validator("start_at_utc", "capital_released_at_utc")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Capital duration timestamps must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def release_after_start(self) -> VenueCapitalCarry:
        if self.capital_released_at_utc <= self.start_at_utc:
            raise ValueError("Capital release time must follow the sensitivity start")
        if any(item.venue != self.venue for item in self.settlement_evidence):
            raise ValueError("Venue carry evidence contains a different venue")
        if len({item.market_id for item in self.settlement_evidence}) != len(
            self.settlement_evidence
        ):
            raise ValueError("Venue settlement evidence market identities must be unique")
        return self


class CapitalCarryAudit(FrontierModel):
    algorithm_version: str = "frontier-independent-capital-carry-audit-1"
    disposition: Literal["verified", "disagreement"]
    input_sha256: str = Field(pattern=_SHA256.pattern)
    recomputed_total_carry_cost: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    recomputed_worst_case_gross_pnl_after_carry: Decimal | None = None
    recomputed_worst_case_net_pnl_after_carry: Decimal | None = None
    checks: tuple[str, ...] = ()
    message: str


class CapitalCarrySensitivity(FrontierModel):
    schema_version: int = 1
    model_version: str = _MODEL_VERSION
    run_id: str = Field(pattern=_SHA256.pattern)
    run_sha256: str = Field(pattern=_SHA256.pattern)
    candidate_id: str = Field(pattern=_SHA256.pattern)
    candidate_evidence_sha256: str = Field(pattern=_SHA256.pattern)
    candidate_classification: str
    classification_unchanged: bool = True
    hypothetical_only: bool = True
    capital_currency_identity: SettlementAssetIdentity
    venues: tuple[VenueCapitalCarry, ...] = Field(min_length=1, max_length=8)
    total_carry_cost: Decimal = Field(ge=0, allow_inf_nan=False)
    worst_case_gross_pnl_before_carry: Decimal | None = None
    worst_case_gross_pnl_after_carry: Decimal | None = None
    worst_case_net_pnl_before_carry: Decimal | None = None
    worst_case_net_pnl_after_carry: Decimal | None = None
    input_sha256: str = Field(pattern=_SHA256.pattern)
    result_sha256: str = Field(pattern=_SHA256.pattern)
    audit: CapitalCarryAudit
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def sensitivity_is_non_classifying(self) -> CapitalCarrySensitivity:
        if not self.hypothetical_only or not self.classification_unchanged:
            raise ValueError("Capital carry sensitivity cannot change candidate classification")
        if self.audit.input_sha256 != self.input_sha256:
            raise ValueError("Independent capital audit is bound to different inputs")
        if len({item.venue for item in self.venues}) != len(self.venues):
            raise ValueError("Capital carry venue entries must be unique")
        expected_result_sha256 = _digest(self.model_dump(mode="json", exclude={"result_sha256"}))
        if expected_result_sha256 != self.result_sha256:
            raise ValueError("Capital carry result hash does not match its payload")
        return self


def _duration_seconds(start: datetime, end: datetime) -> Decimal:
    delta = end.astimezone(UTC) - start.astimezone(UTC)
    return _D(delta.days * 86_400 + delta.seconds) + _D(delta.microseconds) / _D(1_000_000)


def _input_payload(
    candidate: OpportunityCandidate,
    *,
    run_id: str,
    run_sha256: str,
    venues: tuple[VenueCapitalCarry, ...],
) -> dict[str, Any]:
    return {
        "model_version": _MODEL_VERSION,
        "run_id": run_id,
        "run_sha256": run_sha256,
        "candidate_id": candidate.candidate_id,
        "candidate_evidence_sha256": candidate.evidence_sha256,
        "candidate_observed_at_utc": candidate.observed_at_utc.astimezone(UTC).isoformat(),
        "capital_currency_identity": candidate.capital_currency_identity.model_dump(mode="json")
        if candidate.capital_currency_identity is not None
        else None,
        "venue_inputs": [
            {
                "venue": item.venue,
                "capital": str(item.capital),
                "annual_rate_bps": str(item.annual_rate_bps),
                "start_at_utc": item.start_at_utc.isoformat(),
                "capital_released_at_utc": item.capital_released_at_utc.isoformat(),
                "settlement_evidence": [
                    evidence.model_dump(mode="json") for evidence in item.settlement_evidence
                ],
            }
            for item in venues
        ],
    }


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def prepare_capital_carry_inputs(
    candidate: OpportunityCandidate,
    *,
    rates_by_venue: dict[str, str],
    markets_by_id: dict[str, FrontierMarket],
    observation_row_hashes: dict[str, str],
) -> tuple[VenueCapitalCarry, ...]:
    """Validate replay-pinned contracts and conservatively hold venue capital to latest settlement."""
    if not candidate.hypothetical or not candidate.legs:
        raise ValueError(
            "Capital carry requires a complete hypothetical candidate with position legs"
        )
    if len(candidate.legs) > 16 or len(candidate.market_ids) > 16 or len(candidate.venues) > 8:
        raise ValueError("Candidate exceeds the bounded capital carry input size")
    if candidate.observed_at_utc.tzinfo is None or candidate.observed_at_utc.utcoffset() is None:
        raise ValueError("Candidate observation time must include a timezone")
    if candidate.capital_currency_identity is None:
        raise ValueError("Candidate capital denomination identity is incomplete")
    if len(candidate.market_ids) != len(set(candidate.market_ids)) or len(candidate.venues) != len(
        set(candidate.venues)
    ):
        raise ValueError("Candidate market and venue identities must be unique")
    if {leg.venue for leg in candidate.legs} != set(candidate.venues):
        raise ValueError("Position legs do not cover exactly the candidate venues")
    for amount in candidate.capital_by_venue.values():
        _bounded_decimal(amount, "Candidate virtual capital")
        if amount < 0:
            raise ValueError("Candidate virtual capital must be nonnegative")
    for value in (candidate.worst_case_gross_pnl, candidate.worst_case_net_pnl):
        if value is not None:
            _bounded_decimal(value, "Candidate worst-case P&L")
    expected_venues = set(candidate.capital_by_venue)
    if expected_venues != set(candidate.venues) or set(rates_by_venue) != expected_venues:
        raise ValueError("A separate carry rate is required for every candidate venue")
    parsed_rates: dict[str, Decimal] = {}
    for venue, rate_text in rates_by_venue.items():
        if not isinstance(rate_text, str) or not _RATE_TEXT.fullmatch(rate_text):
            raise ValueError(f"{venue} annual carry rate is not a bounded decimal string")
        parsed_rates[venue] = _bounded_decimal(_D(rate_text), "Annual carry rate")
    leg_market_ids = {leg.market_id for leg in candidate.legs}
    if leg_market_ids != set(candidate.market_ids) or set(markets_by_id) != leg_market_ids:
        raise ValueError("Pinned market records do not cover exactly the candidate's position legs")
    expected_observation_ids = {leg.market_observation_id for leg in candidate.legs}
    if set(observation_row_hashes) != expected_observation_ids or any(
        not _SHA256.fullmatch(value) for value in observation_row_hashes.values()
    ):
        raise ValueError("Pinned market observation row hashes are incomplete or invalid")

    evidence_by_venue: dict[str, dict[str, MarketSettlementEvidence]] = {
        venue: {} for venue in sorted(expected_venues)
    }
    for leg in candidate.legs:
        market = markets_by_id.get(leg.market_id)
        if market is None:
            raise ValueError("A pinned position market record is unavailable")
        if (
            market.canonical_id != leg.market_id
            or market.native_market_id != leg.native_market_id
            or market.venue.value != leg.venue
            or market.provenance.observation_id != leg.market_observation_id
        ):
            raise ValueError("A pinned market record does not match its candidate position leg")
        if not market.has_consistent_settlement_asset_identity() or (
            market.payoff.settlement_asset_identity != candidate.capital_currency_identity
        ):
            raise ValueError(
                "Candidate and pinned market settlement denominations differ or are unknown"
            )
        resolution = market.resolution
        settles_at = resolution.settles_at_utc
        resolution_fingerprint = resolution.resolution_fingerprint
        resolution_evidence_sha256 = resolution.evidence_sha256
        if not (
            resolution.verified
            and settles_at is not None
            and resolution.primary_rule
            and resolution.authority
            and resolution_evidence_sha256 is not None
            and _SHA256.fullmatch(resolution_evidence_sha256)
            and resolution_fingerprint is not None
            and resolution_fingerprint.strip()
        ):
            raise ValueError(
                "Pinned market lacks verified, hash-identified settlement timing evidence"
            )
        if settles_at <= candidate.observed_at_utc:
            raise ValueError("Pinned settlement must occur after the candidate observation time")
        if not _SHA256.fullmatch(market.provenance.raw_sha256):
            raise ValueError("Pinned market source observation has no valid raw evidence hash")
        evidence = MarketSettlementEvidence(
            market_id=market.canonical_id,
            venue=market.venue.value,
            observation_id=leg.market_observation_id,
            observation_row_sha256=observation_row_hashes[leg.market_observation_id],
            raw_sha256=market.provenance.raw_sha256,
            resolution_fingerprint=resolution_fingerprint,
            resolution_evidence_sha256=resolution_evidence_sha256,
            settles_at_utc=settles_at,
        )
        evidence_by_venue[leg.venue][market.canonical_id] = evidence

    inputs: list[VenueCapitalCarry] = []
    with localcontext() as context:
        context.prec = 96
        for venue in sorted(expected_venues):
            venue_evidence = tuple(
                sorted(evidence_by_venue[venue].values(), key=lambda item: item.market_id)
            )
            if not venue_evidence:
                raise ValueError("Candidate venue has no pinned settlement evidence")
            settles_at = max(item.settles_at_utc for item in venue_evidence)
            seconds = _duration_seconds(candidate.observed_at_utc, settles_at)
            rate = parsed_rates[venue]
            capital = candidate.capital_by_venue[venue]
            carry = capital * rate * seconds / (_BPS_DENOMINATOR * _YEAR_SECONDS)
            inputs.append(
                VenueCapitalCarry(
                    venue=venue,
                    capital=capital,
                    annual_rate_bps=rate,
                    start_at_utc=candidate.observed_at_utc,
                    capital_released_at_utc=settles_at,
                    duration_seconds=seconds,
                    carry_cost=carry,
                    settlement_evidence=venue_evidence,
                )
            )
    return tuple(inputs)


def evaluate_capital_carry(
    candidate: OpportunityCandidate,
    *,
    run_id: str,
    run_sha256: str,
    rates_by_venue: dict[str, str],
    markets_by_id: dict[str, FrontierMarket],
    observation_row_hashes: dict[str, str],
) -> CapitalCarrySensitivity:
    """Calculate unrounded simple-interest carry under explicit virtual assumptions."""
    capital_identity = candidate.capital_currency_identity
    if capital_identity is None:
        raise ValueError("Candidate capital denomination identity is incomplete")
    inputs = prepare_capital_carry_inputs(
        candidate,
        rates_by_venue=rates_by_venue,
        markets_by_id=markets_by_id,
        observation_row_hashes=observation_row_hashes,
    )
    with localcontext() as context:
        context.prec = 96
        total = sum((item.carry_cost for item in inputs), _D(0))
        gross_after = (
            candidate.worst_case_gross_pnl - total
            if candidate.worst_case_gross_pnl is not None
            else None
        )
        net_after = (
            candidate.worst_case_net_pnl - total
            if candidate.worst_case_net_pnl is not None
            else None
        )
    input_sha256 = _digest(
        _input_payload(candidate, run_id=run_id, run_sha256=run_sha256, venues=inputs)
    )
    audit = independently_audit_capital_carry(
        candidate,
        run_id=run_id,
        run_sha256=run_sha256,
        venues=inputs,
        markets_by_id=markets_by_id,
        observation_row_hashes=observation_row_hashes,
        expected_input_sha256=input_sha256,
        expected_total=total,
        expected_gross_after=gross_after,
        expected_net_after=net_after,
    )
    body = {
        "schema_version": 1,
        "model_version": _MODEL_VERSION,
        "run_id": run_id,
        "run_sha256": run_sha256,
        "candidate_id": candidate.candidate_id,
        "candidate_evidence_sha256": candidate.evidence_sha256,
        "candidate_classification": candidate.classification.value,
        "classification_unchanged": True,
        "hypothetical_only": True,
        "capital_currency_identity": capital_identity.model_dump(mode="json"),
        "venues": [item.model_dump(mode="json") for item in inputs],
        "total_carry_cost": str(total),
        "worst_case_gross_pnl_before_carry": str(candidate.worst_case_gross_pnl)
        if candidate.worst_case_gross_pnl is not None
        else None,
        "worst_case_gross_pnl_after_carry": str(gross_after) if gross_after is not None else None,
        "worst_case_net_pnl_before_carry": str(candidate.worst_case_net_pnl)
        if candidate.worst_case_net_pnl is not None
        else None,
        "worst_case_net_pnl_after_carry": str(net_after) if net_after is not None else None,
        "input_sha256": input_sha256,
        "audit": audit.model_dump(mode="json"),
        "assumptions": (
            "User-entered annual carry rates are hypothetical assumptions, not exchange fee schedules.",
            "Simple interest uses an actual-seconds/365-day year without compounding or currency rounding.",
            "The evaluation starts at the recorded candidate observation time, as if venue capital were committed then.",
            "All capital at a venue is conservatively held until the latest verified settlement among its candidate markets.",
            "Capital remains isolated by venue; this calculation assumes no transfers or shared collateral.",
        ),
        "limitations": (
            "The saved source observation and resolution evidence hashes are recorded, but this arithmetic audit does not authenticate their real-world settlement claim.",
            "This does not model jurisdiction, custody, collateral eligibility, financing availability, transfer, withdrawal, redemption, or execution costs.",
            "Recorded venue capital may exclude unknown fees; carry sensitivity does not establish fee completeness.",
            "A displayed public book and this sensitivity do not establish executable or realized returns.",
            "Existing candidate classification and practical-eligibility state are unchanged.",
        ),
    }
    result_sha256 = _digest(body)
    return CapitalCarrySensitivity.model_validate({**body, "result_sha256": result_sha256})


def independently_audit_capital_carry(
    candidate: OpportunityCandidate,
    *,
    run_id: str,
    run_sha256: str,
    venues: tuple[VenueCapitalCarry, ...],
    markets_by_id: dict[str, FrontierMarket],
    observation_row_hashes: dict[str, str],
    expected_input_sha256: str,
    expected_total: Decimal,
    expected_gross_after: Decimal | None,
    expected_net_after: Decimal | None,
) -> CapitalCarryAudit:
    """Independent reconstruction from the candidate, settlement records, and user assumptions."""
    mismatches: list[str] = []
    candidate_time_aware = (
        candidate.observed_at_utc.tzinfo is not None
        and candidate.observed_at_utc.utcoffset() is not None
    )
    if not candidate_time_aware:
        mismatches.append("Candidate observation timestamp is not timezone-aware")
    evidence_by_market: dict[str, MarketSettlementEvidence] = {}
    for item in venues:
        for evidence in item.settlement_evidence:
            evidence_by_market[evidence.market_id] = evidence
    if set(markets_by_id) != set(candidate.market_ids) or set(evidence_by_market) != set(
        candidate.market_ids
    ):
        mismatches.append("Pinned settlement evidence does not cover exactly the candidate markets")
    if candidate.capital_currency_identity is None:
        mismatches.append("Candidate settlement denomination is missing")
    if set(item.venue for item in venues) != set(candidate.capital_by_venue):
        mismatches.append("Venue assumptions do not cover candidate capital exactly")
    expected_observation_ids = {leg.market_observation_id for leg in candidate.legs}
    if set(observation_row_hashes) != expected_observation_ids:
        mismatches.append("Store-row hashes do not cover exactly the pinned market observations")
    for evidence in evidence_by_market.values():
        if observation_row_hashes.get(evidence.observation_id) != evidence.observation_row_sha256:
            mismatches.append("A settlement evidence row hash differs from the validated store row")

    recomputed: list[Decimal] = []
    with localcontext() as context:
        context.prec = 96
        for item in sorted(venues, key=lambda value: value.venue):
            expected_market_ids = {
                leg.market_id for leg in candidate.legs if leg.venue == item.venue
            }
            source_rows = [
                markets_by_id.get(market_id) for market_id in sorted(expected_market_ids)
            ]
            if not expected_market_ids or any(market is None for market in source_rows):
                mismatches.append(f"{item.venue} has incomplete pinned market inputs")
                continue
            valid_rows = [market for market in source_rows if market is not None]
            if item.capital != candidate.capital_by_venue.get(item.venue):
                mismatches.append(f"{item.venue} capital differs from the stored candidate")
            if item.start_at_utc != candidate.observed_at_utc:
                mismatches.append(
                    f"{item.venue} duration start differs from the candidate observation"
                )
            expected_end = max(
                (
                    market.resolution.settles_at_utc
                    for market in valid_rows
                    if market.resolution.settles_at_utc is not None
                ),
                default=None,
            )
            if expected_end is None or item.capital_released_at_utc != expected_end:
                mismatches.append(
                    f"{item.venue} release time differs from pinned market settlement"
                )
            if (
                set(evidence.market_id for evidence in item.settlement_evidence)
                != expected_market_ids
            ):
                mismatches.append(f"{item.venue} source markets differ from candidate legs")
            for market in valid_rows:
                matching_legs = [
                    leg for leg in candidate.legs if leg.market_id == market.canonical_id
                ]
                resolution = market.resolution
                if not matching_legs or any(
                    leg.native_market_id != market.native_market_id
                    or leg.venue != market.venue.value
                    or leg.market_observation_id != market.provenance.observation_id
                    for leg in matching_legs
                ):
                    mismatches.append(
                        f"{market.canonical_id} identity differs from candidate position legs"
                    )
                if (
                    market.venue.value != item.venue
                    or market.canonical_id not in candidate.market_ids
                    or not market.has_consistent_settlement_asset_identity()
                    or market.payoff.settlement_asset_identity
                    != candidate.capital_currency_identity
                ):
                    mismatches.append(
                        f"{market.canonical_id} settlement denomination or venue is inconsistent"
                    )
                if not (
                    resolution.verified
                    and resolution.primary_rule
                    and resolution.primary_rule.strip()
                    and resolution.authority
                    and resolution.authority.strip()
                    and resolution.evidence_sha256 is not None
                    and _SHA256.fullmatch(resolution.evidence_sha256)
                    and resolution.resolution_fingerprint is not None
                    and resolution.resolution_fingerprint.strip()
                    and resolution.settles_at_utc is not None
                    and resolution.settles_at_utc.tzinfo is not None
                    and resolution.settles_at_utc.utcoffset() is not None
                    and candidate_time_aware
                    and resolution.settles_at_utc > candidate.observed_at_utc
                    and _SHA256.fullmatch(market.provenance.raw_sha256)
                ):
                    mismatches.append(
                        f"{market.canonical_id} settlement metadata is not verified and hash identified"
                    )
                matched_evidence = evidence_by_market.get(market.canonical_id)
                if matched_evidence is None or (
                    matched_evidence.observation_id != market.provenance.observation_id
                    or matched_evidence.raw_sha256 != market.provenance.raw_sha256
                    or matched_evidence.resolution_fingerprint
                    != market.resolution.resolution_fingerprint
                    or matched_evidence.resolution_evidence_sha256
                    != market.resolution.evidence_sha256
                    or matched_evidence.settles_at_utc != market.resolution.settles_at_utc
                    or matched_evidence.venue != market.venue.value
                ):
                    mismatches.append(
                        f"{market.canonical_id} settlement provenance differs from pinned source"
                    )
            if not candidate_time_aware:
                continue
            if expected_end is None or expected_end <= candidate.observed_at_utc:
                mismatches.append(f"{item.venue} settlement does not follow candidate observation")
                continue
            delta = expected_end.astimezone(UTC) - candidate.observed_at_utc.astimezone(UTC)
            exact_seconds = Fraction(delta.days * 86_400 + delta.seconds, 1) + Fraction(
                delta.microseconds, 1_000_000
            )
            seconds = _D(exact_seconds.numerator) / _D(exact_seconds.denominator)
            if item.duration_seconds != seconds:
                mismatches.append(f"{item.venue} duration does not match settlement timestamps")
            exact_carry = (
                Fraction(candidate.capital_by_venue.get(item.venue, _D(-1)))
                * Fraction(item.annual_rate_bps)
                * exact_seconds
                / (10_000 * 365 * 24 * 60 * 60)
            )
            carry = _D(exact_carry.numerator) / _D(exact_carry.denominator)
            if item.carry_cost != carry:
                mismatches.append(
                    f"{item.venue} carry arithmetic differs from independent recomputation"
                )
            recomputed.append(carry)
        total = sum(recomputed, _D(0))
        gross_after = (
            candidate.worst_case_gross_pnl - total
            if candidate.worst_case_gross_pnl is not None
            else None
        )
        net_after = (
            candidate.worst_case_net_pnl - total
            if candidate.worst_case_net_pnl is not None
            else None
        )
    payload = _input_payload(candidate, run_id=run_id, run_sha256=run_sha256, venues=venues)
    input_sha256 = _digest(payload)
    if input_sha256 != expected_input_sha256:
        mismatches.append(
            "Input digest does not match candidate, assumptions, and pinned settlement evidence"
        )
    if total != expected_total:
        mismatches.append("Total carry cost differs from independent recomputation")
    if gross_after != expected_gross_after:
        mismatches.append("Gross P&L sensitivity differs from independent recomputation")
    if net_after != expected_net_after:
        mismatches.append("Net P&L sensitivity differs from independent recomputation")
    return CapitalCarryAudit(
        disposition="disagreement" if mismatches else "verified",
        input_sha256=input_sha256,
        recomputed_total_carry_cost=total,
        recomputed_worst_case_gross_pnl_after_carry=gross_after,
        recomputed_worst_case_net_pnl_after_carry=net_after,
        checks=(
            "Candidate venue capital amounts are preserved.",
            "Settlement times and source hashes match the candidate-pinned market observations.",
            "Actual-seconds/365 simple-interest arithmetic is independently recomputed.",
            "Candidate classification is not included in this calculation and cannot be changed by it.",
        ),
        message=(
            "Independent carry arithmetic matches the candidate, user assumptions, and pinned settlement metadata."
            if not mismatches
            else "; ".join(mismatches)
        ),
    )
