"""Conservative relationship proposals and explicit payoff-equivalence verification."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field, model_validator

from midas.frontier.models import FrontierMarket, FrontierModel, MarketKind, Venue

D = Decimal
MATCHER_VERSION = "frontier-relationship-matcher-2"
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


class RelationshipType(StrEnum):
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


class RelationshipEvidence(FrontierModel):
    method: str
    matcher_version: str = MATCHER_VERSION
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
) -> tuple[Relationship, ...]:
    """Produce reviewable candidates using indexed native event IDs and title terms.

    Text features only create HYPOTHESIS edges. They can never mark economic equivalence.
    """
    if not 1 <= max_pairs <= 20_000:
        raise ValueError("Relationship pair bound must be within 1..20000")
    if not D(0) <= minimum_jaccard <= D(1):
        raise ValueError("Minimum Jaccard threshold must be between zero and one")
    by_id = {market.canonical_id: market for market in markets}
    if len(by_id) != len(markets):
        raise ValueError("Duplicate canonical market identity")
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
                if a.venue == b.venue:
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

    output = []
    for (left, right, rel_type), (reason, score, fields, details) in sorted(
        candidates.items(), key=lambda item: item[0]
    )[:max_pairs]:
        observation_ids = tuple(
            sorted(
                (
                    by_id[left].provenance.observation_id,
                    by_id[right].provenance.observation_id,
                )
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
                        method="deterministic-indexed-metadata-v1",
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
    if not external_assertion_id.strip():
        raise ValueError("A verification assertion identity is required")
    checks: list[str] = []
    if not evidence_observation_ids:
        checks.append("Source observation identities are required")
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
        if not market.resolution.verified or not market.resolution.resolution_fingerprint:
            checks.append(f"{name} resolution is not verified or fingerprinted")
        if market.resolution.evidence_sha256 is None:
            checks.append(f"{name} resolution evidence hash is absent")
    if left.payoff.payout_currency != right.payoff.payout_currency:
        checks.append("Payout currencies differ")
    if left.payoff.settlement_asset != right.payoff.settlement_asset:
        checks.append("Settlement assets differ")
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
    assertion_evidence = tuple(sorted(set(evidence_observation_ids)))
    assertion_time = asserted_at_utc or max(
        left.provenance.response_received_at_utc,
        right.provenance.response_received_at_utc,
    )
    if assertion_time.tzinfo is None or assertion_time.utcoffset() is None:
        raise ValueError("Assertion time must include a timezone")
    assertion_time = assertion_time.astimezone(UTC)
    verifier_version = (
        f"frontier-equivalence-verifier-1|{external_assertion_id}|{assertion_time.isoformat()}"
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
                method="independent-payoff-equivalence-v1",
                source_fields=("payoff", "resolution", "outcome_mapping"),
                observation_ids=assertion_evidence,
                details=(
                    "state_mapping=" + json_compact(state_mapping),
                    "instrument_mapping=" + json_compact(instrument_mapping),
                ),
                external_assertion_id=external_assertion_id,
                created_at_utc=assertion_time,
            ),
        ),
    )


def evidence_mapping(relationship: Relationship, name: str) -> dict[str, str]:
    if name not in {"state_mapping", "instrument_mapping"}:
        raise ValueError("Unsupported relationship evidence mapping")
    prefix = f"{name}="
    for item in relationship.evidence:
        for detail in item.details:
            if detail.startswith(prefix):
                import json

                try:
                    value = json.loads(detail.removeprefix(prefix))
                except json.JSONDecodeError:
                    return {}
                if isinstance(value, dict) and all(
                    isinstance(key, str) and isinstance(target, str)
                    for key, target in value.items()
                ):
                    return value
                return {}
    return {}


def json_compact(value: dict[str, str]) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))
