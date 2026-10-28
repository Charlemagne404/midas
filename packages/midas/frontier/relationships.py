"""Conservative relationship proposals and explicit payoff-equivalence verification."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from midas.frontier.models import (
    FrontierMarket,
    FrontierModel,
    MarketKind,
    Venue,
)

D = Decimal
MATCHER_VERSION = "frontier-relationship-matcher-5"
SAME_PAYOFF_VERIFIER_VERSION = "frontier-equivalence-verifier-5"
LOGICAL_IMPLICATION_VERIFIER_VERSION = "frontier-logical-implication-verifier-2"
MAX_LOGICAL_IMPLICATION_STATES = 1024
MAX_LOGICAL_STATE_ID_CHARS = 128
DEFAULT_MINIMUM_JACCARD = D("0.45")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "will",
    "with",
    "who",
    "what",
    "when",
    "which",
    "yes",
    "no",
}
_EVENT_CONTEXT_STOP_WORDS = {
    "control",
    "election",
    "elections",
    "midterm",
    "party",
    "united",
    "states",
    "u",
    "us",
    "win",
}
_TEXT_ALIASES = {
    "democratic": "democrat",
    "democrats": "democrat",
    "republicans": "republican",
}


class RelationshipType(StrEnum):
    SOURCE_COMPONENT_REFERENCE = "source_component_reference"
    SAME_EVENT = "same_event"
    SAME_PAYOFF = "same_payoff"
    COMPLEMENTARY = "complementary_outcomes"
    MUTUALLY_EXCLUSIVE = "mutually_exclusive"
    EXHAUSTIVE_OUTCOMES = "exhaustive_outcomes"
    LOGICAL_IMPLICATION = "logical_implication"
    SHARED_UNDERLYING = "shared_underlying"
    TEXT_CANDIDATE = "text_candidate"


class VerificationState(StrEnum):
    HYPOTHESIS = "hypothesis"
    VERIFIED = "verified"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    SUPERSEDED = "superseded"


class ReviewDecision(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


class RelationshipReview(FrontierModel):
    """Immutable, self-attributed review of a stored relationship hypothesis."""

    schema_version: int = 1
    review_id: str
    relationship_id: str
    adjudicated_relationship_id: str
    decision: ReviewDecision
    reviewer_label: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=5, max_length=1000)
    evidence_observation_ids: tuple[str, ...] = Field(min_length=1, max_length=10)
    external_assertion_id: str | None = Field(default=None, max_length=120)
    supersedes_review_id: str | None = None
    created_at_utc: datetime

    @field_validator("created_at_utc")
    @classmethod
    def normalize_review_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Relationship review time must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_review_evidence(self) -> RelationshipReview:
        if len(set(self.evidence_observation_ids)) != len(self.evidence_observation_ids):
            raise ValueError("Relationship review evidence IDs must be unique")
        for observation_id in self.evidence_observation_ids:
            if len(observation_id) != 64 or any(
                character not in "0123456789abcdef" for character in observation_id
            ):
                raise ValueError("Relationship review evidence must use lowercase SHA-256 IDs")
        if self.decision == ReviewDecision.VERIFIED and not self.external_assertion_id:
            raise ValueError("A verified relationship review requires an external assertion ID")
        for digest in (self.review_id, self.adjudicated_relationship_id):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError("Review identities must be lowercase SHA-256 digests")
        return self


class RelationshipEvidence(FrontierModel):
    method: str
    matcher_version: str = MATCHER_VERSION
    verifier_version: str | None = None
    observation_ids: tuple[str, ...] = ()
    source_fields: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    external_assertion_id: str | None = None
    created_at_utc: datetime


class Relationship(FrontierModel):
    schema_version: int = 1
    relationship_id: str
    left_market_id: str
    right_market_id: str
    relationship_type: RelationshipType
    state: VerificationState
    confidence: Decimal = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str
    evidence: tuple[RelationshipEvidence, ...]
    supersedes: str | None = None

    @model_validator(mode="after")
    def stable_pair_order(self) -> Relationship:
        if self.left_market_id >= self.right_market_id:
            raise ValueError("Relationship market IDs must be stored in stable lexical order")
        if not self.relationship_id or not self.reason:
            raise ValueError("Relationship identity and reason are required")
        return self


def normalize_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def title_tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalize_title(value).split()
        if len(token) > 2 and token not in _STOP_WORDS and not token.isdecimal()
    )


def _event_context_tokens(value: str) -> frozenset[str]:
    return frozenset(_TEXT_ALIASES.get(token, token) for token in title_tokens(value))


def _event_context_years(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"\b(?:19|20)\d{2}\b", normalize_title(value)))


def _market_year_context(market: FrontierMarket) -> tuple[frozenset[str], bool]:
    parent_years = _event_context_years(market.native_event_title or "")
    market_years = _event_context_years(market.title)
    contradictory = bool(parent_years and market_years and not parent_years & market_years)
    return parent_years or market_years, contradictory


def _market_years_conflict(left: FrontierMarket, right: FrontierMarket) -> bool:
    left_years, left_contradictory = _market_year_context(left)
    right_years, right_contradictory = _market_year_context(right)
    return (
        left_contradictory
        or right_contradictory
        or bool(left_years and right_years and not left_years & right_years)
    )


def _outcome_context_tokens(market: FrontierMarket) -> frozenset[str]:
    if market.outcome_label:
        values = title_tokens(market.outcome_label)
    else:
        title = _event_context_tokens(market.title)
        event = _event_context_tokens(market.native_event_title or "")
        values = title - event
    return frozenset(
        _TEXT_ALIASES.get(token, token)
        for token in values
        if token not in _EVENT_CONTEXT_STOP_WORDS
    )


def _identity(
    left: str,
    right: str,
    rel_type: RelationshipType,
    version: str,
    evidence_ids: tuple[str, ...] = (),
) -> tuple[str, str]:
    a, b = sorted((left, right))
    raw = "|".join((version, rel_type.value, a, b, *sorted(set(evidence_ids))))
    return a, hashlib.sha256(raw.encode()).hexdigest()


def propose_relationships(
    markets: tuple[FrontierMarket, ...] | list[FrontierMarket],
    *,
    max_pairs: int = 1000,
    minimum_jaccard: Decimal = DEFAULT_MINIMUM_JACCARD,
    source_observation_ids: Mapping[str, str] | None = None,
) -> tuple[Relationship, ...]:
    """Produce bounded source-reference and text-based relationship proposals.

    Every result remains a HYPOTHESIS. Exact source-selected component references
    describe a native metadata link only; they never imply payoff equivalence.
    Text features cannot mark economic equivalence.
    """
    if not 1 <= max_pairs <= 20_000:
        raise ValueError("Relationship pair bound must be within 1..20000")
    if not D(0) <= minimum_jaccard <= D(1):
        raise ValueError("Minimum Jaccard threshold must be between zero and one")
    by_id = {market.canonical_id: market for market in markets}
    if len(by_id) != len(markets):
        raise ValueError("Duplicate canonical market identity")
    evidence_ids = source_observation_ids or {}
    for market_id in by_id:
        observation_id = evidence_ids.get(market_id)
        if observation_id is not None and (
            len(observation_id) != 64
            or any(character not in "0123456789abcdef" for character in observation_id)
        ):
            raise ValueError("Source observation IDs must be lowercase SHA-256 hex digests")
    created_at = max(
        (market.provenance.response_received_at_utc for market in markets),
        default=datetime(1970, 1, 1, tzinfo=UTC),
    )
    exact_events: dict[tuple[Venue, str], list[str]] = defaultdict(list)
    inverted: dict[str, list[str]] = defaultdict(list)
    token_map: dict[str, frozenset[str]] = {}
    for market in sorted(markets, key=lambda item: item.canonical_id):
        if market.native_event_id:
            exact_events[(market.venue, market.native_event_id)].append(market.canonical_id)
        tokens = title_tokens(market.title)
        token_map[market.canonical_id] = tokens
        for token in sorted(tokens):
            inverted[token].append(market.canonical_id)

    candidates: dict[
        tuple[str, str, RelationshipType], tuple[str, Decimal, tuple[str, ...], tuple[str, ...]]
    ] = {}

    # A combo's selected-leg list is an explicit source assertion, but its payout
    # logic may be more complex than those listed legs. Link it only when the
    # exact native child record is also present and its event identity agrees.
    native_index: dict[tuple[Venue, str], list[FrontierMarket]] = defaultdict(list)
    for market in sorted(markets, key=lambda item: item.canonical_id):
        native_index[(market.venue, market.native_market_id)].append(market)
    for parent in sorted(markets, key=lambda item: item.canonical_id):
        for component in sorted(
            set(parent.selected_components),
            key=lambda item: (
                item.venue.value,
                item.native_market_id,
                item.native_event_id or "",
                item.selected_side,
            ),
        ):
            if len(candidates) >= max_pairs:
                break
            if component.venue != parent.venue:
                continue
            matches = native_index.get((component.venue, component.native_market_id), [])
            if len(matches) != 1:
                continue
            child = matches[0]
            if child.canonical_id == parent.canonical_id:
                continue
            if component.native_event_id is not None and (
                child.native_event_id != component.native_event_id
            ):
                continue
            left, right = sorted((parent.canonical_id, child.canonical_id))
            component_details: tuple[str, ...] = (
                f"The parent source metadata lists {component.native_market_id} on the {component.selected_side.upper()} side.",
                "The recorded child metadata has the exact referenced market ticker; its event ID also agrees when the parent supplied one.",
                "This source link does not verify the child payoff, combo payout, event logic, or settlement equivalence.",
            )
            if component.yes_settlement_value_dollars is not None:
                component_details += (
                    "The parent source also reports YES settlement value "
                    f"{component.yes_settlement_value_dollars}; Frontier preserves it as source metadata and does not infer combo payout from it.",
                )
            candidates[(left, right, RelationshipType.SOURCE_COMPONENT_REFERENCE)] = (
                "Source-declared selected-component reference; exact native market ID matches and any supplied event ID agrees",
                D(1),
                (
                    "selected_components",
                    "native_market_id",
                    "native_event_id",
                    "yes_settlement_value_dollars",
                ),
                component_details,
            )

    for (venue, _), identities in sorted(
        exact_events.items(), key=lambda item: (item[0][0].value, item[0][1])
    ):
        for i, left in enumerate(identities):
            for right in identities[i + 1 :]:
                pair = (left, right) if left < right else (right, left)
                candidates[(pair[0], pair[1], RelationshipType.SAME_EVENT)] = (
                    "Exact venue-local native event identifier",
                    D(1),
                    ("native_event_id",),
                    (f"Both markets declare venue {venue.value} and the same native event ID.",),
                )
                if len(candidates) >= max_pairs:
                    break
            if len(candidates) >= max_pairs:
                break
        if len(candidates) >= max_pairs:
            break

    compared: set[tuple[str, str]] = set()
    comparison_budget = min(50_000, max_pairs * 50)
    for token in sorted(inverted):
        identities = inverted[token]
        for i, left in enumerate(identities):
            for right in identities[i + 1 :]:
                pair = (left, right) if left < right else (right, left)
                if pair in compared:
                    continue
                compared.add(pair)
                if len(compared) > comparison_budget:
                    break
                a, b = by_id[pair[0]], by_id[pair[1]]
                if a.venue == b.venue or _market_years_conflict(a, b):
                    continue
                ta, tb = token_map[pair[0]], token_map[pair[1]]
                union = ta | tb
                overlap = ta & tb
                score = D(len(overlap)) / D(len(union)) if union else D(0)
                if len(overlap) < 2 or score < minimum_jaccard:
                    continue
                candidates[(pair[0], pair[1], RelationshipType.TEXT_CANDIDATE)] = (
                    "Conservative shared title terms; dates, rules, outcomes, and authorities still require review",
                    score,
                    ("title",),
                    ("shared_terms=" + ",".join(sorted(overlap)),),
                )
                if len(candidates) >= max_pairs:
                    break
            if len(candidates) >= max_pairs:
                break
            if len(compared) > comparison_budget:
                break
        if len(candidates) >= max_pairs:
            break
        if len(compared) > comparison_budget:
            break

    # Event context supplies a second, still-hypothetical cross-venue route.
    # It requires both a similar parent event title and a market-specific outcome term.
    event_index: dict[str, list[str]] = defaultdict(list)
    event_tokens: dict[str, frozenset[str]] = {}
    outcome_tokens: dict[str, frozenset[str]] = {}
    for market in sorted(markets, key=lambda item: item.canonical_id):
        if not market.native_event_title:
            continue
        tokens = _event_context_tokens(market.native_event_title)
        if len(tokens) < 2:
            continue
        event_tokens[market.canonical_id] = tokens
        outcome_tokens[market.canonical_id] = _outcome_context_tokens(market)
        for token in sorted(tokens):
            event_index[token].append(market.canonical_id)

    event_pairs: set[tuple[str, str]] = set()
    event_comparison_budget = min(20_000, max_pairs * 20)
    for token in sorted(event_index):
        if len(candidates) >= max_pairs:
            break
        identities = event_index[token]
        for i, first in enumerate(identities):
            for second in identities[i + 1 :]:
                if len(candidates) >= max_pairs:
                    break
                pair = (first, second) if first < second else (second, first)
                if pair in event_pairs:
                    continue
                event_pairs.add(pair)
                if len(event_pairs) > event_comparison_budget:
                    break
                left_market, right_market = by_id[pair[0]], by_id[pair[1]]
                if left_market.venue == right_market.venue:
                    continue
                left_events, right_events = event_tokens[pair[0]], event_tokens[pair[1]]
                shared_events = left_events & right_events
                event_union = left_events | right_events
                event_score = D(len(shared_events)) / D(len(event_union))
                shared_outcomes = outcome_tokens[pair[0]] & outcome_tokens[pair[1]]
                if (
                    len(shared_events) < 2
                    or event_score < D("0.4")
                    or _market_years_conflict(left_market, right_market)
                    or not shared_outcomes
                ):
                    continue
                candidates[(pair[0], pair[1], RelationshipType.TEXT_CANDIDATE)] = (
                    "Shared parent-event context and market-specific outcome text; source rules, timing, and payoff equivalence require review",
                    event_score,
                    ("native_event_title", "outcome_label", "title"),
                    (
                        "shared_event_terms=" + ",".join(sorted(shared_events)),
                        "shared_outcome_terms=" + ",".join(sorted(shared_outcomes)),
                        "This text match is a hypothesis only; no outcome mapping or payoff equivalence is asserted.",
                    ),
                )
                if len(candidates) >= max_pairs:
                    break
            if len(candidates) >= max_pairs or len(event_pairs) > event_comparison_budget:
                break
        if len(candidates) >= max_pairs or len(event_pairs) > event_comparison_budget:
            break

    output = []
    ordered_candidates = sorted(
        candidates.items(),
        key=lambda item: (
            item[0][2] != RelationshipType.SOURCE_COMPONENT_REFERENCE,
            item[0],
        ),
    )
    for (left, right, rel_type), (reason, score, fields, details) in ordered_candidates[:max_pairs]:
        observation_ids = tuple(
            sorted(
                {
                    evidence_ids.get(left, by_id[left].provenance.observation_id),
                    evidence_ids.get(right, by_id[right].provenance.observation_id),
                }
            )
        )
        _, relationship_id = _identity(left, right, rel_type, MATCHER_VERSION, observation_ids)
        output.append(
            Relationship(
                relationship_id=relationship_id,
                left_market_id=left,
                right_market_id=right,
                relationship_type=rel_type,
                state=VerificationState.HYPOTHESIS,
                confidence=score,
                reason=reason,
                evidence=(
                    RelationshipEvidence(
                        method=(
                            "source-selected-component-identifiers-v1"
                            if rel_type == RelationshipType.SOURCE_COMPONENT_REFERENCE
                            else "deterministic-indexed-metadata-v3"
                        ),
                        observation_ids=observation_ids,
                        source_fields=fields,
                        details=details,
                        created_at_utc=created_at,
                    ),
                ),
            )
        )
    return tuple(output)


def verify_same_payoff(
    left: FrontierMarket,
    right: FrontierMarket,
    *,
    state_mapping: dict[str, str],
    instrument_mapping: dict[str, str],
    external_assertion_id: str,
    evidence_observation_ids: tuple[str, ...],
    asserted_at_utc: datetime | None = None,
) -> Relationship:
    """Verify economic equivalence only from explicit, independently attested inputs."""
    if not external_assertion_id.strip() or len(external_assertion_id) > 120:
        raise ValueError("A bounded verification assertion identity is required")
    checks: list[str] = []
    if not evidence_observation_ids:
        checks.append("Source observation identities are required")
    elif (
        len(evidence_observation_ids) < 2
        or len(evidence_observation_ids) > 10
        or any(not observation_id.strip() for observation_id in evidence_observation_ids)
    ):
        checks.append("Source evidence must contain two to ten nonempty observation identities")
    if len(set(evidence_observation_ids)) != len(evidence_observation_ids):
        checks.append("Source observation identities must be unique")
    required_observations = {
        left.provenance.observation_id,
        right.provenance.observation_id,
    }
    if len(required_observations) != 2:
        checks.append("Each supplied market must have a distinct pinned observation identity")
    if not required_observations.issubset(set(evidence_observation_ids)):
        checks.append("Evidence must cite the pinned observation for each supplied market")
    if left.canonical_id == right.canonical_id:
        checks.append("Markets must have distinct canonical identities")
    if left.venue == right.venue:
        checks.append("Cross-venue equivalence requires different venues")
    supported_kinds = {MarketKind.BINARY_EVENT, MarketKind.MULTI_OUTCOME_EVENT}
    if left.market_kind not in supported_kinds or right.market_kind not in supported_kinds:
        checks.append("Only verified event contract structures are supported")
    for name, market in (("left", left), ("right", right)):
        if not market.payoff.verified or not market.payoff.exhaustive:
            checks.append(f"{name} payoff is not verified and exhaustive")
        if not market.has_consistent_settlement_asset_identity():
            checks.append(f"{name} canonical settlement asset identity is missing or inconsistent")
        if market.payoff.payout_currency != market.payoff.settlement_asset:
            checks.append(
                f"{name} payout currency differs from its settlement asset; no valuation bridge is modeled"
            )
        if market.settlement_asset != market.payoff.settlement_asset:
            checks.append(f"{name} market settlement asset differs from its verified payoff")
        if not market.resolution.verified or not market.resolution.resolution_fingerprint:
            checks.append(f"{name} resolution is not verified or fingerprinted")
        if market.resolution.evidence_sha256 is None:
            checks.append(f"{name} resolution evidence hash is absent")
    if left.payoff.payout_currency != right.payoff.payout_currency:
        checks.append("Payout currencies differ")
    if left.payoff.settlement_asset != right.payoff.settlement_asset:
        checks.append("Settlement assets differ")
    if (
        left.payoff.settlement_asset_identity is None
        or right.payoff.settlement_asset_identity is None
        or left.payoff.settlement_asset_identity != right.payoff.settlement_asset_identity
    ):
        checks.append("Canonical settlement asset identities are absent or differ")
    if left.resolution.resolution_fingerprint != right.resolution.resolution_fingerprint:
        checks.append("Verified resolution fingerprints differ")
    if (left.resolution.authority or "").strip().casefold() != (
        right.resolution.authority or ""
    ).strip().casefold():
        checks.append("Resolution authorities differ")
    if left.resolution.closes_at_utc != right.resolution.closes_at_utc:
        checks.append("Resolution close times differ")
    if left.resolution.settles_at_utc != right.resolution.settles_at_utc:
        checks.append("Settlement times differ")

    left_states = set(left.payoff.state_ids)
    right_states = set(right.payoff.state_ids)
    if set(state_mapping) != left_states or set(state_mapping.values()) != right_states:
        checks.append("State mapping is not a bijection over both exhaustive state sets")
    left_instruments = {item.native_instrument_id: item for item in left.instruments}
    right_instruments = {item.native_instrument_id: item for item in right.instruments}
    if set(instrument_mapping) != set(left_instruments) or set(instrument_mapping.values()) != set(
        right_instruments
    ):
        checks.append("Instrument mapping is not a bijection over both markets")
    else:
        for left_id, right_id in sorted(instrument_mapping.items()):
            left_item = left_instruments[left_id]
            right_item = right_instruments[right_id]
            if left_item.outcome_id is None or right_item.outcome_id is None:
                checks.append("Mapped event instrument is missing an outcome identity")
                continue
            left_payouts = {item.state_id: item.amount for item in left_item.payouts}
            right_payouts = {item.state_id: item.amount for item in right_item.payouts}
            if set(left_payouts) != left_states or set(right_payouts) != right_states:
                checks.append(f"Mapped instrument {left_id} does not define every payoff state")
                continue
            if any(
                left_payouts[state] != right_payouts[mapped]
                for state, mapped in state_mapping.items()
            ):
                checks.append(f"Mapped instrument {left_id} has a different payout vector")

    a, b = sorted((left.canonical_id, right.canonical_id))
    if left.canonical_id == a:
        canonical_state_mapping = state_mapping
        canonical_instrument_mapping = instrument_mapping
    else:
        canonical_state_mapping = {value: key for key, value in state_mapping.items()}
        canonical_instrument_mapping = {value: key for key, value in instrument_mapping.items()}
    market_by_id = {left.canonical_id: left, right.canonical_id: right}
    canonical_asset_identities: dict[str, str] = {}
    for market_id in (a, b):
        identity = market_by_id[market_id].payoff.settlement_asset_identity
        canonical_asset_identities[market_id] = (
            identity.canonical_id if identity is not None else "missing"
        )
    assertion_evidence = tuple(sorted(set(evidence_observation_ids)))
    assertion_time = asserted_at_utc or max(
        left.provenance.response_received_at_utc,
        right.provenance.response_received_at_utc,
    )
    if assertion_time.tzinfo is None or assertion_time.utcoffset() is None:
        raise ValueError("Assertion time must include a timezone")
    assertion_time = assertion_time.astimezone(UTC)
    if assertion_time < max(
        left.provenance.response_received_at_utc,
        right.provenance.response_received_at_utc,
    ):
        checks.append("External assertion predates one or more source observations")
    verifier_version = (
        f"{SAME_PAYOFF_VERIFIER_VERSION}|{external_assertion_id}|{assertion_time.isoformat()}|"
        f"{json_compact(canonical_state_mapping)}|{json_compact(canonical_instrument_mapping)}|"
        f"{json_compact(canonical_asset_identities)}"
    )
    _, relationship_id = _identity(
        a,
        b,
        RelationshipType.SAME_PAYOFF,
        verifier_version,
        (*assertion_evidence, external_assertion_id),
    )
    verified = not checks
    return Relationship(
        relationship_id=relationship_id,
        left_market_id=a,
        right_market_id=b,
        relationship_type=RelationshipType.SAME_PAYOFF,
        state=VerificationState.VERIFIED if verified else VerificationState.REJECTED,
        confidence=D(1) if verified else D(0),
        reason=(
            "Payoff, settlement units, resolution identity, timing, and outcome mapping verified by an external assertion"
            if verified
            else "; ".join(checks)
        ),
        evidence=(
            RelationshipEvidence(
                method="independent-payoff-equivalence-v2",
                verifier_version=SAME_PAYOFF_VERIFIER_VERSION,
                source_fields=(
                    "payoff",
                    "resolution",
                    "outcome_mapping",
                    "settlement_asset_identity",
                ),
                observation_ids=assertion_evidence,
                details=(
                    "state_mapping=" + json_compact(canonical_state_mapping),
                    "instrument_mapping=" + json_compact(canonical_instrument_mapping),
                    "settlement_asset_identities=" + json_compact(canonical_asset_identities),
                ),
                external_assertion_id=external_assertion_id,
                created_at_utc=assertion_time,
            ),
        ),
    )


def verify_logical_implication(
    left: FrontierMarket,
    right: FrontierMarket,
    *,
    implication_from_market_id: str,
    implication_to_market_id: str,
    state_mapping: dict[str, str],
    external_assertion_id: str,
    evidence_observation_ids: tuple[str, ...],
    asserted_at_utc: datetime | None = None,
) -> Relationship:
    """Check a directed implication over an explicitly mapped joint state space.

    The payout vectors establish the bounded arithmetic claim. The supplied
    assertion and source identities remain necessary to support the semantic
    claim that the mapped state spaces describe the same world.
    """
    if not external_assertion_id.strip():
        raise ValueError("A logical implication assertion identity is required")
    if left.canonical_id == right.canonical_id:
        raise ValueError("Logical implication requires two distinct markets")
    if len(external_assertion_id) > 120:
        raise ValueError("Logical implication assertion identity exceeds 120 characters")
    if len(evidence_observation_ids) > 10 or any(
        len(item) > 256 for item in evidence_observation_ids
    ):
        raise ValueError("Logical implication source evidence exceeds its bounded identity limit")
    checks: list[str] = []
    markets = {left.canonical_id: left, right.canonical_id: right}
    if implication_from_market_id not in markets or implication_to_market_id not in markets:
        checks.append("Implication direction must name both supplied markets")
    elif implication_from_market_id == implication_to_market_id:
        checks.append("Implication direction must connect distinct markets")
    if len(set(evidence_observation_ids)) < 2 or any(
        not item.strip() for item in evidence_observation_ids
    ):
        checks.append("Distinct source observation identities for both markets are required")
    required_observations = {
        left.provenance.observation_id,
        right.provenance.observation_id,
    }
    if not required_observations.issubset(set(evidence_observation_ids)):
        checks.append("Evidence must cite the pinned observation for each supplied market")
    if any(market.market_kind != MarketKind.BINARY_EVENT for market in markets.values()):
        checks.append("Only binary event contracts are supported")

    for name, market_value in (("left", left), ("right", right)):
        if not market_value.payoff.verified or not market_value.payoff.exhaustive:
            checks.append(f"{name} payoff is not verified and exhaustive")
        if (
            not market_value.resolution.verified
            or not market_value.resolution.resolution_fingerprint
        ):
            checks.append(f"{name} resolution is not verified or fingerprinted")
        if market_value.resolution.evidence_sha256 is None:
            checks.append(f"{name} resolution evidence hash is absent")

    source_market = markets.get(implication_from_market_id)
    target_market = markets.get(implication_to_market_id)
    state_bound_exceeded = (
        len(state_mapping) > MAX_LOGICAL_IMPLICATION_STATES
        or any(
            len(market_value.payoff.state_ids) > MAX_LOGICAL_IMPLICATION_STATES
            for market_value in (left, right)
        )
        or any(
            len(state_id) > MAX_LOGICAL_STATE_ID_CHARS
            for state_id in (
                *state_mapping.keys(),
                *state_mapping.values(),
                *left.payoff.state_ids,
                *right.payoff.state_ids,
            )
        )
    )
    if state_bound_exceeded:
        checks.append(
            "Joint state mapping exceeds the verification bounds of "
            f"{MAX_LOGICAL_IMPLICATION_STATES} states and {MAX_LOGICAL_STATE_ID_CHARS} characters per state ID"
        )
    if source_market is None or target_market is None:
        source_states: set[str] = set()
        target_states: set[str] = set()
    elif state_bound_exceeded:
        source_states = set()
        target_states = set()
    else:
        source_states = set(source_market.payoff.state_ids)
        target_states = set(target_market.payoff.state_ids)
    if set(state_mapping) != source_states or set(state_mapping.values()) != target_states:
        checks.append("State mapping is not a bijection over both exhaustive state sets")

    def binary_outcome_payouts(
        market_value: FrontierMarket, name: str
    ) -> dict[str, dict[str, Decimal]]:
        instruments = {item.outcome_id: item for item in market_value.instruments}
        if len(market_value.instruments) != 2 or set(instruments) != {"yes", "no"}:
            checks.append(f"{name} market does not define exactly one YES and one NO instrument")
            return {}
        payouts_by_outcome: dict[str, dict[str, Decimal]] = {}
        expected_states = set(market_value.payoff.state_ids)
        for outcome in ("yes", "no"):
            instrument = instruments[outcome]
            payout_values = {payout.state_id: payout.amount for payout in instrument.payouts}
            if (
                len(payout_values) != len(instrument.payouts)
                or set(payout_values) != expected_states
            ):
                checks.append(
                    f"{name} {outcome.upper()} instrument lacks a unique payout for every state"
                )
                return {}
            if any(value not in (D(0), D(1)) for value in payout_values.values()):
                checks.append(f"{name} {outcome.upper()} payout is not binary")
                return {}
            payouts_by_outcome[outcome] = payout_values
        if any(
            payouts_by_outcome["yes"][state] + payouts_by_outcome["no"][state] != D(1)
            for state in expected_states
        ):
            checks.append(f"{name} YES and NO payout vectors are not complementary")
        return payouts_by_outcome

    source_payouts = (
        (binary_outcome_payouts(source_market, "implication source") if source_market else {})
        if not state_bound_exceeded
        else {}
    )
    target_payouts = (
        (binary_outcome_payouts(target_market, "implication target") if target_market else {})
        if not state_bound_exceeded
        else {}
    )
    if (
        source_market is not None
        and target_market is not None
        and set(state_mapping) == source_states
        and set(state_mapping.values()) == target_states
        and "yes" in source_payouts
        and "yes" in target_payouts
        and any(
            source_payouts["yes"][source_state] > target_payouts["yes"][target_state]
            for source_state, target_state in state_mapping.items()
        )
    ):
        checks.append("Source YES payout does not imply target YES in every mapped state")

    a, b = sorted((left.canonical_id, right.canonical_id))
    if state_bound_exceeded:
        canonical_state_mapping = {}
    elif implication_from_market_id == a and implication_to_market_id == b:
        canonical_state_mapping = state_mapping
    elif implication_from_market_id == b and implication_to_market_id == a:
        canonical_state_mapping = {value: key for key, value in state_mapping.items()}
    else:
        canonical_state_mapping = {}
    assertion_evidence = tuple(sorted(set(evidence_observation_ids)))
    assertion_time = asserted_at_utc or max(
        left.provenance.response_received_at_utc,
        right.provenance.response_received_at_utc,
    )
    if assertion_time.tzinfo is None or assertion_time.utcoffset() is None:
        raise ValueError("Assertion time must include a timezone")
    assertion_time = assertion_time.astimezone(UTC)
    if assertion_time < max(
        left.provenance.response_received_at_utc,
        right.provenance.response_received_at_utc,
    ):
        checks.append("External assertion predates one or more source observations")
    settlement_metadata = {
        market_id: (
            f"{market_value.payoff.settlement_asset_identity.canonical_id if market_value.payoff.settlement_asset_identity else 'unknown-asset'}|"
            f"{market_value.resolution.settles_at_utc.isoformat() if market_value.resolution.settles_at_utc else 'unknown-time'}"
        )
        for market_id, market_value in sorted(markets.items())
    }
    identity_version = (
        f"{LOGICAL_IMPLICATION_VERIFIER_VERSION}|{external_assertion_id}|"
        f"{assertion_time.isoformat()}|{implication_from_market_id}|"
        f"{implication_to_market_id}|{json_compact(canonical_state_mapping)}|"
        f"{json_compact(settlement_metadata)}"
    )
    _, relationship_id = _identity(
        a,
        b,
        RelationshipType.LOGICAL_IMPLICATION,
        identity_version,
        (*assertion_evidence, external_assertion_id),
    )
    verified = not checks
    return Relationship(
        relationship_id=relationship_id,
        left_market_id=a,
        right_market_id=b,
        relationship_type=RelationshipType.LOGICAL_IMPLICATION,
        state=VerificationState.VERIFIED if verified else VerificationState.REJECTED,
        confidence=D(1) if verified else D(0),
        reason=(
            "Directed YES implication holds across every mapped binary payout state; semantic mapping remains externally asserted and settlement differences are not economically bridged"
            if verified
            else "; ".join(checks)
        ),
        evidence=(
            RelationshipEvidence(
                method="explicit-joint-state-payout-implication-v1",
                verifier_version=LOGICAL_IMPLICATION_VERIFIER_VERSION,
                source_fields=(
                    "payoff",
                    "resolution",
                    "joint_state_mapping",
                    "yes_no_payout_vectors",
                ),
                observation_ids=assertion_evidence,
                details=(
                    f"implication_from_market_id={implication_from_market_id}",
                    f"implication_to_market_id={implication_to_market_id}",
                    "state_mapping=" + json_compact(canonical_state_mapping),
                    "settlement_units_and_times=" + json_compact(settlement_metadata),
                ),
                external_assertion_id=external_assertion_id,
                created_at_utc=assertion_time,
            ),
        ),
    )


def evidence_mapping(relationship: Relationship, name: str) -> dict[str, str]:
    if name not in {"state_mapping", "instrument_mapping"}:
        raise ValueError("Unsupported relationship evidence mapping")
    raw_value = evidence_detail(relationship, name)
    if raw_value is None:
        return {}
    import json

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(target, str) for key, target in value.items()
    ):
        return value
    return {}


def evidence_detail(relationship: Relationship, name: str) -> str | None:
    """Return one unambiguous scalar detail from a relationship evidence record."""
    if not name or not name.replace("_", "").isalnum():
        raise ValueError("Invalid relationship evidence detail name")
    prefix = f"{name}="
    matches = [
        detail.removeprefix(prefix)
        for evidence in relationship.evidence
        for detail in evidence.details
        if detail.startswith(prefix)
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def json_compact(value: dict[str, str]) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))
