"""Virtual funding-currency sensitivity under explicit user-entered FX assumptions.

This module does not fetch rates, assert convertibility, change candidate economics,
or pool capital across venues. Every result is a bounded research scenario.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from midas.frontier.economics import OpportunityCandidate
from midas.frontier.models import FrontierModel, SettlementAssetIdentity

_D = Decimal
_BPS = _D(10_000)
_VERSION = "frontier-virtual-funding-currency-1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VENUE = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,35})(?:\.[0-9]{1,36})?$")
_RATE = re.compile(r"^(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,12})?$")
_BPS_TEXT = re.compile(r"^(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,6})?$")


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_decimal(text: str, pattern: re.Pattern[str], name: str) -> Decimal:
    if not isinstance(text, str) or len(text) > 110 or not pattern.fullmatch(text):
        raise ValueError(f"{name} must be a bounded nonnegative decimal string")
    try:
        value = _D(text)
    except InvalidOperation as error:
        raise ValueError(f"{name} is not a decimal number") from error
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value


def _decimal_from_fraction(value: Fraction) -> Decimal:
    with localcontext() as context:
        context.prec = 96
        return _D(value.numerator) / _D(value.denominator)


def _bounded_candidate_amount(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("Candidate virtual capital must be finite")
    parts = value.as_tuple()
    if (
        len(parts.digits) > 64
        or not isinstance(parts.exponent, int)
        or not -64 <= parts.exponent <= 64
        or not isinstance(value.adjusted(), int)
        or not -64 <= value.adjusted() <= 64
    ):
        raise ValueError("Candidate virtual capital exceeds the exact arithmetic bound")
    return value


def _venue_values(
    candidate: OpportunityCandidate,
    assumptions: tuple[VenueFundingAssumption, ...],
) -> dict[str, VenueFundingResult]:
    target_identity = candidate.capital_currency_identity
    if target_identity is None:
        raise ValueError("Candidate capital denomination identity is incomplete")
    expected_venues = set(candidate.capital_by_venue)
    if (
        not candidate.hypothetical
        or not expected_venues
        or len(expected_venues) > 8
        or len(candidate.venues) != len(expected_venues)
        or len(candidate.legs) > 16
    ):
        raise ValueError("Funding sensitivity requires a bounded hypothetical candidate")
    if expected_venues != set(candidate.venues):
        raise ValueError("Candidate capital amounts do not cover its venues exactly")
    if {item.venue for item in assumptions} != expected_venues:
        raise ValueError("A virtual funding assumption is required for every candidate venue")
    if len(assumptions) != len(expected_venues):
        raise ValueError("Virtual funding assumptions must contain each venue exactly once")

    results: dict[str, VenueFundingResult] = {}
    with localcontext() as context:
        context.prec = 96
        for item in sorted(assumptions, key=lambda value: value.venue):
            target_required = _bounded_candidate_amount(candidate.capital_by_venue[item.venue])
            rate = _parse_decimal(item.target_units_per_funding_unit, _RATE, "FX rate assumption")
            fee_bps = _parse_decimal(item.conversion_fee_bps, _BPS_TEXT, "Conversion fee")
            balance = _parse_decimal(item.balance_amount, _AMOUNT, "Virtual balance")
            if rate <= 0:
                raise ValueError(f"{item.venue} FX rate must be greater than zero")
            if fee_bps >= _BPS:
                raise ValueError(f"{item.venue} conversion fee must be less than 10000 bps")
            if target_required < 0:
                raise ValueError(f"{item.venue} candidate capital cannot be negative")
            if item.funding_currency_identity == target_identity and (rate != 1 or fee_bps != 0):
                raise ValueError(
                    f"{item.venue} identical denomination requires a 1:1 rate and zero conversion fee"
                )
            fee_fraction = fee_bps / _BPS
            effective_rate = rate * (1 - fee_fraction)
            required_funding = target_required / effective_rate
            conversion_fee_target = target_required * fee_fraction / (1 - fee_fraction)
            available_target = balance * effective_rate
            target_shortfall = max(target_required - available_target, _D(0))
            funding_shortfall = max(required_funding - balance, _D(0))
            requirement_covered = Fraction(target_required) <= Fraction(effective_rate) * Fraction(
                balance
            )
            results[item.venue] = VenueFundingResult(
                venue=item.venue,
                required_capital_target=target_required,
                funding_currency_identity=item.funding_currency_identity,
                balance_amount=balance,
                target_units_per_funding_unit=rate,
                conversion_fee_bps=fee_bps,
                required_funding_amount=required_funding,
                available_capital_target_after_fee=available_target,
                conversion_fee_target_amount=conversion_fee_target,
                shortfall_target=target_shortfall,
                shortfall_funding=funding_shortfall,
                model_requirement_covered=requirement_covered,
            )
    return results


class VenueFundingAssumption(FrontierModel):
    venue: str = Field(min_length=1, max_length=80)
    funding_currency_identity: SettlementAssetIdentity
    balance_amount: str = Field(min_length=1, max_length=110)
    # Rate orientation is candidate settlement-asset units for one funding-asset unit.
    target_units_per_funding_unit: str = Field(min_length=1, max_length=110)
    conversion_fee_bps: str = Field(default="0", min_length=1, max_length=16)

    @field_validator("venue")
    @classmethod
    def valid_venue(cls, value: str) -> str:
        if not _VENUE.fullmatch(value):
            raise ValueError("Venue identifiers must be normalized lowercase names")
        return value

    @field_validator("balance_amount")
    @classmethod
    def valid_balance(cls, value: str) -> str:
        _parse_decimal(value, _AMOUNT, "Virtual balance")
        return value

    @field_validator("target_units_per_funding_unit")
    @classmethod
    def valid_rate(cls, value: str) -> str:
        if _parse_decimal(value, _RATE, "FX rate assumption") <= 0:
            raise ValueError("FX rate assumption must be greater than zero")
        return value

    @field_validator("conversion_fee_bps")
    @classmethod
    def valid_fee(cls, value: str) -> str:
        if _parse_decimal(value, _BPS_TEXT, "Conversion fee") >= _BPS:
            raise ValueError("Conversion fee must be less than 10000 bps")
        return value


class FundingCurrencySensitivityRequest(FrontierModel):
    run_id: str = Field(pattern=_SHA256.pattern)
    run_sha256: str = Field(pattern=_SHA256.pattern)
    candidate_id: str = Field(pattern=_SHA256.pattern)
    venues: tuple[VenueFundingAssumption, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_venues(self) -> FundingCurrencySensitivityRequest:
        if len({item.venue for item in self.venues}) != len(self.venues):
            raise ValueError("Virtual funding assumptions must contain each venue once")
        return self


class VenueFundingResult(FrontierModel):
    venue: str
    required_capital_target: Decimal = Field(ge=0, allow_inf_nan=False)
    funding_currency_identity: SettlementAssetIdentity
    balance_amount: Decimal = Field(ge=0, allow_inf_nan=False)
    target_units_per_funding_unit: Decimal = Field(gt=0, allow_inf_nan=False)
    conversion_fee_bps: Decimal = Field(ge=0, lt=10_000, allow_inf_nan=False)
    required_funding_amount: Decimal = Field(ge=0, allow_inf_nan=False)
    available_capital_target_after_fee: Decimal = Field(ge=0, allow_inf_nan=False)
    conversion_fee_target_amount: Decimal = Field(ge=0, allow_inf_nan=False)
    shortfall_target: Decimal = Field(ge=0, allow_inf_nan=False)
    shortfall_funding: Decimal = Field(ge=0, allow_inf_nan=False)
    model_requirement_covered: bool


class FundingCurrencyAudit(FrontierModel):
    algorithm_version: str = "frontier-independent-virtual-funding-audit-1"
    disposition: Literal["verified", "disagreement"]
    input_sha256: str = Field(pattern=_SHA256.pattern)
    recomputed_total_conversion_fee_target: Decimal | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    checks: tuple[str, ...] = ()
    message: str


class FundingCurrencySensitivity(FrontierModel):
    schema_version: int = 1
    model_version: str = _VERSION
    run_id: str = Field(pattern=_SHA256.pattern)
    run_sha256: str = Field(pattern=_SHA256.pattern)
    candidate_id: str = Field(pattern=_SHA256.pattern)
    candidate_evidence_sha256: str = Field(pattern=_SHA256.pattern)
    candidate_classification: str
    candidate_practical_eligibility: bool
    classification_unchanged: bool = True
    practical_eligibility_unchanged: bool = True
    candidate_economics_unchanged: bool = True
    hypothetical_only: bool = True
    target_currency_identity: SettlementAssetIdentity
    unresolved_candidate_fee_leg_count: int = Field(ge=0, le=16)
    venues: tuple[VenueFundingResult, ...] = Field(min_length=1, max_length=8)
    total_conversion_fee_target: Decimal = Field(ge=0, allow_inf_nan=False)
    input_sha256: str = Field(pattern=_SHA256.pattern)
    result_sha256: str = Field(pattern=_SHA256.pattern)
    audit: FundingCurrencyAudit
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def verify_non_classifying_hashes(self) -> FundingCurrencySensitivity:
        if (
            not self.classification_unchanged
            or not self.practical_eligibility_unchanged
            or not self.candidate_economics_unchanged
            or not self.hypothetical_only
        ):
            raise ValueError("Funding sensitivity cannot change candidate economics or eligibility")
        if self.audit.input_sha256 != self.input_sha256:
            raise ValueError("Independent funding audit is bound to different inputs")
        if len({item.venue for item in self.venues}) != len(self.venues):
            raise ValueError("Funding sensitivity venue entries must be unique")
        expected_hash = _digest(self.model_dump(mode="json", exclude={"result_sha256"}))
        if expected_hash != self.result_sha256:
            raise ValueError("Funding sensitivity result hash does not match its payload")
        return self


def _input_payload(
    candidate: OpportunityCandidate,
    *,
    run_id: str,
    run_sha256: str,
    assumptions: tuple[VenueFundingAssumption, ...],
) -> dict[str, Any]:
    target_identity = candidate.capital_currency_identity
    if target_identity is None:
        raise ValueError("Candidate capital denomination identity is incomplete")
    return {
        "model_version": _VERSION,
        "run_id": run_id,
        "run_sha256": run_sha256,
        "candidate_id": candidate.candidate_id,
        "candidate_evidence_sha256": candidate.evidence_sha256,
        "candidate_classification": candidate.classification.value,
        "candidate_practical_eligibility": candidate.practical_eligibility,
        "target_currency_identity": target_identity.model_dump(mode="json"),
        "candidate_capital_by_venue": {
            venue: str(amount) for venue, amount in sorted(candidate.capital_by_venue.items())
        },
        "venue_assumptions": [
            item.model_dump(mode="json") for item in sorted(assumptions, key=lambda x: x.venue)
        ],
    }


def independently_audit_funding_currency(
    candidate: OpportunityCandidate,
    *,
    run_id: str,
    run_sha256: str,
    assumptions: tuple[VenueFundingAssumption, ...],
    reported: tuple[VenueFundingResult, ...],
    expected_input_sha256: str,
    expected_total_fee: Decimal,
) -> FundingCurrencyAudit:
    """Recompute all conversions from rational inputs, independently of Decimal results."""
    mismatches: list[str] = []
    try:
        recomputed = _venue_values(candidate, assumptions)
    except ValueError as error:
        return FundingCurrencyAudit(
            disposition="disagreement",
            input_sha256="0" * 64,
            recomputed_total_conversion_fee_target=None,
            message=f"Independent input validation failed: {error}",
        )
    reported_by_venue = {item.venue: item for item in reported}
    if set(reported_by_venue) != set(recomputed):
        mismatches.append("Reported venue results differ from the candidate venue set")
    recomputed_fee_parts: list[Decimal] = []
    for assumption in assumptions:
        venue = assumption.venue
        expected = recomputed[venue]
        actual = reported_by_venue.get(venue)
        if actual is None:
            continue
        rate = Fraction(_D(assumption.target_units_per_funding_unit))
        fee = Fraction(_D(assumption.conversion_fee_bps)) / 10_000
        target = Fraction(candidate.capital_by_venue[venue])
        balance = Fraction(_D(assumption.balance_amount))
        exact_fee_target = target * fee / (1 - fee)
        exact_required_funding = target / (rate * (1 - fee))
        exact_available_target = balance * rate * (1 - fee)
        exact_target_shortfall = max(target - exact_available_target, Fraction(0))
        # The Decimal implementation rounds the required funding amount to its
        # fixed 96-digit context before subtraction. Reproduce that defined
        # rounding boundary in exact rational arithmetic before checking the
        # derived shortfall amount.
        rounded_required_funding = Fraction(_decimal_from_fraction(exact_required_funding))
        exact_funding_shortfall = max(rounded_required_funding - balance, Fraction(0))
        recomputed_fee_parts.append(_decimal_from_fraction(exact_fee_target))
        independently_computed = {
            "required_capital_target": _decimal_from_fraction(target),
            "balance_amount": _decimal_from_fraction(balance),
            "target_units_per_funding_unit": _decimal_from_fraction(rate),
            "conversion_fee_bps": _decimal_from_fraction(
                Fraction(_D(assumption.conversion_fee_bps))
            ),
            "required_funding_amount": _decimal_from_fraction(exact_required_funding),
            "available_capital_target_after_fee": _decimal_from_fraction(exact_available_target),
            "conversion_fee_target_amount": _decimal_from_fraction(exact_fee_target),
            "shortfall_target": _decimal_from_fraction(exact_target_shortfall),
            "shortfall_funding": _decimal_from_fraction(exact_funding_shortfall),
            "model_requirement_covered": target <= rate * (1 - fee) * balance,
        }
        for field_name, value in independently_computed.items():
            if getattr(actual, field_name) != value:
                mismatches.append(f"{venue} {field_name} differs from rational recomputation")
        if actual.funding_currency_identity != assumption.funding_currency_identity:
            mismatches.append(f"{venue} funding identity differs from its explicit assumption")
        if expected != actual:
            mismatches.append(f"{venue} Decimal implementation differs from the rational result")

    with localcontext() as context:
        context.prec = 96
        total_fee = sum(recomputed_fee_parts, _D(0))
    input_sha256 = _digest(
        _input_payload(
            candidate,
            run_id=run_id,
            run_sha256=run_sha256,
            assumptions=assumptions,
        )
    )
    if input_sha256 != expected_input_sha256:
        mismatches.append("Input digest differs from candidate and user assumptions")
    if total_fee != expected_total_fee:
        mismatches.append("Total conversion fee differs from rational recomputation")
    return FundingCurrencyAudit(
        disposition="disagreement" if mismatches else "verified",
        input_sha256=input_sha256,
        recomputed_total_conversion_fee_target=total_fee,
        checks=(
            "Virtual balances remain isolated by venue.",
            "Funding identities are compared as full namespaced settlement-asset identities.",
            "The rate orientation and fee calculation are recomputed with exact rational arithmetic.",
            "Candidate economics and classification are not modified.",
        ),
        message=(
            "Independent rational arithmetic matches every explicit funding assumption."
            if not mismatches
            else "; ".join(mismatches)
        ),
    )


def evaluate_funding_currency_sensitivity(
    candidate: OpportunityCandidate,
    *,
    run_id: str,
    run_sha256: str,
    assumptions: tuple[VenueFundingAssumption, ...],
) -> FundingCurrencySensitivity:
    """Evaluate venue-local virtual funding against a saved candidate's denomination."""
    if not _SHA256.fullmatch(run_id) or not _SHA256.fullmatch(run_sha256):
        raise ValueError("Saved run identities must be SHA-256 digests")
    target_identity = candidate.capital_currency_identity
    if target_identity is None:
        raise ValueError("Candidate capital denomination identity is incomplete")
    values = _venue_values(candidate, assumptions)
    ordered_results = tuple(values[venue] for venue in sorted(values))
    with localcontext() as context:
        context.prec = 96
        total_fee = sum((item.conversion_fee_target_amount for item in ordered_results), _D(0))
    input_sha256 = _digest(
        _input_payload(
            candidate,
            run_id=run_id,
            run_sha256=run_sha256,
            assumptions=assumptions,
        )
    )
    audit = independently_audit_funding_currency(
        candidate,
        run_id=run_id,
        run_sha256=run_sha256,
        assumptions=assumptions,
        reported=ordered_results,
        expected_input_sha256=input_sha256,
        expected_total_fee=total_fee,
    )
    body = {
        "schema_version": 1,
        "model_version": _VERSION,
        "run_id": run_id,
        "run_sha256": run_sha256,
        "candidate_id": candidate.candidate_id,
        "candidate_evidence_sha256": candidate.evidence_sha256,
        "candidate_classification": candidate.classification.value,
        "candidate_practical_eligibility": candidate.practical_eligibility,
        "classification_unchanged": True,
        "practical_eligibility_unchanged": True,
        "candidate_economics_unchanged": True,
        "hypothetical_only": True,
        "target_currency_identity": target_identity.model_dump(mode="json"),
        "unresolved_candidate_fee_leg_count": sum(
            leg.modeled_fee is None for leg in candidate.legs
        ),
        "venues": [item.model_dump(mode="json") for item in ordered_results],
        "total_conversion_fee_target": str(total_fee),
        "input_sha256": input_sha256,
        "audit": audit.model_dump(mode="json"),
        "assumptions": (
            "Every exchange rate, virtual balance, and conversion fee is a user-entered scenario assumption; no live FX rate is retrieved.",
            "Rate orientation is candidate settlement-asset units received per one funding-asset unit before the stated conversion fee.",
            "Conversion fee is charged against gross converted target currency; no compounding, rounding, or minimum conversion amount is modeled.",
            "Balances remain isolated by venue and are not pooled or transferred.",
            "The result reports funding coverage and modeled conversion cost without changing candidate classification or candidate P&L.",
        ),
        "limitations": (
            "Different asset identities, including fiat and network-specific tokens with the same ticker, are never treated as 1:1 unless the user explicitly supplies a conversion assumption.",
            "No source evidence establishes that conversion or transfer is available, lawful, timely, or executable at the assumed rate.",
            "Custody, jurisdiction, venue-specific collateral eligibility, FX spread, transfer rails, settlement delay, and FX movement are unresolved.",
            "Candidate capital amounts may exclude fees that the source model could not establish; this sensitivity does not make an incomplete requirement complete.",
            "This virtual funding calculation is not an order, account, wallet, deposit, withdrawal, or trading interface.",
        ),
    }
    result_sha256 = _digest(body)
    return FundingCurrencySensitivity.model_validate({**body, "result_sha256": result_sha256})
