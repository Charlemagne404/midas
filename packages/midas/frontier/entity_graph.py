"""Bounded structural entity graph derived from pinned normalized markets.

This projection exposes venue, event, instrument, outcome, and asset context.
Its links are source-metadata relationships and never certify payoff equivalence.
"""

from __future__ import annotations

import hashlib
import heapq
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from midas.frontier.models import (
    FrontierMarket,
    FrontierModel,
    Lifecycle,
    MarketKind,
    QuantityUnit,
    SettlementAssetIdentity,
    Venue,
    stable_instrument_id,
)

ENTITY_CONTEXT_MODEL_VERSION = "frontier-market-entity-context-v1"
MAX_ENTITY_CONTEXT_MARKETS = 512
MAX_ENTITY_CONTEXT_INSTRUMENTS = 512
MAX_ENTITY_CONTEXT_COMPONENTS = 256
MAX_ENTITY_CONTEXT_PAYOUT_STATES = 512
MAX_ENTITY_CONTEXT_NODES = 2048
MAX_ENTITY_CONTEXT_LINKS = 4096
MAX_ENTITY_LABEL_CHARS = 512


class EntityContextKind(StrEnum):
    VENUE = "venue"
    EVENT = "event"
    MARKET = "market"
    CONTRACT = "contract"
    INSTRUMENT = "instrument"
    COMPONENT_CONTRACT = "component_contract"
    OUTCOME = "outcome"
    PAYOFF_STATE = "payoff_state"
    ASSET_REFERENCE = "asset_reference"
    SETTLEMENT_ASSET = "settlement_asset"


class EntityContextLinkType(StrEnum):
    LISTED_ON = "listed_on"
    PART_OF_EVENT = "part_of_event"
    OFFERS_CONTRACT = "offers_contract"
    OFFERS_INSTRUMENT = "offers_instrument"
    SELECTS_COMPONENT = "selects_component"
    DEFINES_OUTCOME = "defines_outcome"
    PAYS_IN_STATE = "pays_in_state"
    REFERENCES_BASE_ASSET = "references_base_asset"
    QUOTES_IN_ASSET = "quotes_in_asset"
    SETTLES_IN_ASSET = "settles_in_asset"


class EntityContextNode(FrontierModel):
    entity_id: str = Field(pattern=r"^frontier-entity-v1:[a-z_]+:[0-9a-f]{64}$")
    kind: EntityContextKind
    label: str = Field(min_length=1, max_length=MAX_ENTITY_LABEL_CHARS)
    venue: Venue | None = None
    native_id: str | None = Field(default=None, max_length=MAX_ENTITY_LABEL_CHARS)
    native_id_truncated: bool = False
    market_kind: MarketKind | None = None
    lifecycle: Lifecycle | None = None
    quantity_unit: QuantityUnit | None = None
    outcome_id: str | None = Field(default=None, max_length=MAX_ENTITY_LABEL_CHARS)
    selected_side: Literal["yes", "no"] | None = None
    identity_scope: (
        Literal["venue_scoped", "market_scoped", "canonical_settlement_asset"] | None
    ) = None
    value: str | None = Field(default=None, max_length=128)
    resolution_authority: str | None = Field(default=None, max_length=512)
    resolution_primary_rule: str | None = Field(default=None, max_length=512)
    resolution_secondary_rule: str | None = Field(default=None, max_length=512)
    resolution_closes_at_utc: datetime | None = None
    resolution_settles_at_utc: datetime | None = None
    resolution_fingerprint: str | None = Field(default=None, max_length=512)
    resolution_verified: bool | None = None
    payoff_state_ids: tuple[str, ...] = Field(default=(), max_length=128)
    payoff_exhaustive: bool | None = None
    payoff_verified: bool | None = None
    record_available: bool = True
    market_ids: tuple[str, ...] = Field(default=(), max_length=MAX_ENTITY_CONTEXT_MARKETS)
    source_observation_ids: tuple[str, ...] = Field(
        default=(), max_length=MAX_ENTITY_CONTEXT_MARKETS
    )


class EntityContextLink(FrontierModel):
    link_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_entity_id: str = Field(pattern=r"^frontier-entity-v1:[a-z_]+:[0-9a-f]{64}$")
    target_entity_id: str = Field(pattern=r"^frontier-entity-v1:[a-z_]+:[0-9a-f]{64}$")
    link_type: EntityContextLinkType
    source_market_id: str = Field(min_length=1, max_length=512)
    source_observation_id: str | None = Field(default=None, max_length=128)
    source_field: str = Field(min_length=1, max_length=128)
    semantic_basis: Literal["normalized_source_metadata"] = "normalized_source_metadata"
    economic_equivalence_asserted: Literal[False] = False


class EntityContextGraph(FrontierModel):
    schema_version: Literal[1] = 1
    model_version: str = ENTITY_CONTEXT_MODEL_VERSION
    scope: Literal["loaded_relationship_market_nodes"] = "loaded_relationship_market_nodes"
    semantics: Literal["structural_metadata_only"] = "structural_metadata_only"
    economic_equivalence_asserted: Literal[False] = False
    source_market_count: int = Field(ge=0)
    represented_market_count: int = Field(ge=0, le=MAX_ENTITY_CONTEXT_MARKETS)
    nodes: tuple[EntityContextNode, ...] = Field(max_length=MAX_ENTITY_CONTEXT_NODES)
    links: tuple[EntityContextLink, ...] = Field(max_length=MAX_ENTITY_CONTEXT_LINKS)
    truncated: bool = False
    truncation_reasons: tuple[str, ...] = Field(default=(), max_length=8)
    limitations: tuple[str, ...] = (
        "Event identifiers are venue-scoped; similar titles do not merge events.",
        "Underlying asset tickers remain venue-scoped references without canonical identity evidence.",
        "Structural metadata links do not certify payoff equivalence, hedges, or executable opportunities.",
    )


@dataclass
class _NodeAccumulator:
    kind: EntityContextKind
    label: str
    venue: Venue | None
    native_id: str | None
    native_id_truncated: bool = False
    market_kind: MarketKind | None = None
    lifecycle: Lifecycle | None = None
    quantity_unit: QuantityUnit | None = None
    outcome_id: str | None = None
    selected_side: Literal["yes", "no"] | None = None
    identity_scope: (
        Literal["venue_scoped", "market_scoped", "canonical_settlement_asset"] | None
    ) = None
    value: str | None = None
    resolution_authority: str | None = None
    resolution_primary_rule: str | None = None
    resolution_secondary_rule: str | None = None
    resolution_closes_at_utc: datetime | None = None
    resolution_settles_at_utc: datetime | None = None
    resolution_fingerprint: str | None = None
    resolution_verified: bool | None = None
    payoff_state_ids: tuple[str, ...] = ()
    payoff_exhaustive: bool | None = None
    payoff_verified: bool | None = None
    record_available: bool = True
    market_ids: set[str] = field(default_factory=set)
    source_observation_ids: set[str] = field(default_factory=set)


class _EntityContextBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, _NodeAccumulator] = {}
        self.links: dict[str, EntityContextLink] = {}
        self.truncation_reasons: set[str] = set()

    def _entity_id(self, kind: EntityContextKind, key: tuple[str, ...]) -> str:
        encoded_key = json.dumps(
            [ENTITY_CONTEXT_MODEL_VERSION, kind.value, *key],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(encoded_key).hexdigest()
        return f"frontier-entity-v1:{kind.value}:{digest}"

    def add_node(
        self,
        kind: EntityContextKind,
        key: tuple[str, ...],
        *,
        label: str,
        venue: Venue | None,
        native_id: str | None,
        market_id: str,
        source_observation_id: str | None,
        market_kind: MarketKind | None = None,
        lifecycle: Lifecycle | None = None,
        quantity_unit: QuantityUnit | None = None,
        outcome_id: str | None = None,
        selected_side: Literal["yes", "no"] | None = None,
        identity_scope: Literal["venue_scoped", "market_scoped", "canonical_settlement_asset"]
        | None = None,
        value: str | None = None,
        resolution_authority: str | None = None,
        resolution_primary_rule: str | None = None,
        resolution_secondary_rule: str | None = None,
        resolution_closes_at_utc: datetime | None = None,
        resolution_settles_at_utc: datetime | None = None,
        resolution_fingerprint: str | None = None,
        resolution_verified: bool | None = None,
        payoff_state_ids: tuple[str, ...] = (),
        payoff_exhaustive: bool | None = None,
        payoff_verified: bool | None = None,
        record_available: bool = True,
    ) -> str | None:
        entity_id = self._entity_id(kind, key)
        accumulator = self.nodes.get(entity_id)
        if accumulator is None:
            if len(self.nodes) >= MAX_ENTITY_CONTEXT_NODES:
                self.truncation_reasons.add("entity_node_limit")
                return None
            accumulator = _NodeAccumulator(
                kind=kind,
                label=label[:MAX_ENTITY_LABEL_CHARS],
                venue=venue,
                native_id=native_id[:MAX_ENTITY_LABEL_CHARS] if native_id else None,
                native_id_truncated=(
                    native_id is not None and len(native_id) > MAX_ENTITY_LABEL_CHARS
                ),
                market_kind=market_kind,
                lifecycle=lifecycle,
                quantity_unit=quantity_unit,
                outcome_id=outcome_id[:MAX_ENTITY_LABEL_CHARS] if outcome_id else None,
                selected_side=selected_side,
                identity_scope=identity_scope,
                value=value[:128] if value else None,
                resolution_authority=(resolution_authority[:512] if resolution_authority else None),
                resolution_primary_rule=(
                    resolution_primary_rule[:512] if resolution_primary_rule else None
                ),
                resolution_secondary_rule=(
                    resolution_secondary_rule[:512] if resolution_secondary_rule else None
                ),
                resolution_closes_at_utc=resolution_closes_at_utc,
                resolution_settles_at_utc=resolution_settles_at_utc,
                resolution_fingerprint=(
                    resolution_fingerprint[:512] if resolution_fingerprint else None
                ),
                resolution_verified=resolution_verified,
                payoff_state_ids=payoff_state_ids[:128],
                payoff_exhaustive=payoff_exhaustive,
                payoff_verified=payoff_verified,
                record_available=record_available,
            )
            self.nodes[entity_id] = accumulator
        accumulator.market_ids.add(market_id[:512])
        if source_observation_id:
            accumulator.source_observation_ids.add(source_observation_id[:128])
        return entity_id

    def add_link(
        self,
        source_entity_id: str | None,
        target_entity_id: str | None,
        link_type: EntityContextLinkType,
        *,
        market_id: str,
        source_observation_id: str | None,
        source_field: str,
    ) -> None:
        if source_entity_id is None or target_entity_id is None:
            return
        link_key = json.dumps(
            [
                source_entity_id,
                target_entity_id,
                link_type.value,
                market_id,
                source_observation_id,
                source_field,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        link_id = hashlib.sha256(link_key).hexdigest()
        if link_id in self.links:
            return
        if len(self.links) >= MAX_ENTITY_CONTEXT_LINKS:
            self.truncation_reasons.add("entity_link_limit")
            return
        self.links[link_id] = EntityContextLink(
            link_id=link_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            link_type=link_type,
            source_market_id=market_id[:512],
            source_observation_id=source_observation_id[:128] if source_observation_id else None,
            source_field=source_field[:128],
        )

    def finish(self, source_market_count: int, represented_market_count: int) -> EntityContextGraph:
        nodes = tuple(
            EntityContextNode(
                entity_id=entity_id,
                kind=node.kind,
                label=node.label,
                venue=node.venue,
                native_id=node.native_id,
                native_id_truncated=node.native_id_truncated,
                market_kind=node.market_kind,
                lifecycle=node.lifecycle,
                quantity_unit=node.quantity_unit,
                outcome_id=node.outcome_id,
                selected_side=node.selected_side,
                identity_scope=node.identity_scope,
                value=node.value,
                resolution_authority=node.resolution_authority,
                resolution_primary_rule=node.resolution_primary_rule,
                resolution_secondary_rule=node.resolution_secondary_rule,
                resolution_closes_at_utc=node.resolution_closes_at_utc,
                resolution_settles_at_utc=node.resolution_settles_at_utc,
                resolution_fingerprint=node.resolution_fingerprint,
                resolution_verified=node.resolution_verified,
                payoff_state_ids=node.payoff_state_ids,
                payoff_exhaustive=node.payoff_exhaustive,
                payoff_verified=node.payoff_verified,
                record_available=node.record_available,
                market_ids=tuple(sorted(node.market_ids)),
                source_observation_ids=tuple(sorted(node.source_observation_ids)),
            )
            for entity_id, node in sorted(self.nodes.items())
        )
        return EntityContextGraph(
            source_market_count=source_market_count,
            represented_market_count=represented_market_count,
            nodes=nodes,
            links=tuple(self.links[key] for key in sorted(self.links)),
            truncated=bool(self.truncation_reasons),
            truncation_reasons=tuple(sorted(self.truncation_reasons)),
        )


def _add_asset_reference(
    builder: _EntityContextBuilder,
    *,
    market: FrontierMarket,
    market_node_id: str | None,
    observation_id: str | None,
    asset_value: str,
    field_name: str,
    link_type: EntityContextLinkType,
    instrument_key: str | None = None,
    identity: SettlementAssetIdentity | None = None,
) -> None:
    if market_node_id is None:
        return
    key: tuple[str, ...]
    if identity is not None:
        identity_key = json.dumps(
            identity.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        node_kind = EntityContextKind.SETTLEMENT_ASSET
        key = (identity_key,)
        scope: Literal["venue_scoped", "market_scoped", "canonical_settlement_asset"] = (
            "canonical_settlement_asset"
        )
        venue = None
        label = f"{identity.kind.value}:{identity.code}"
        if identity.network_id is not None:
            label += f" · {identity.network_id}"
        if identity.asset_reference is not None:
            label += f" · {identity.asset_reference}"
    else:
        node_kind = EntityContextKind.ASSET_REFERENCE
        scope = (
            "market_scoped"
            if instrument_key or field_name == "settlement_asset"
            else "venue_scoped"
        )
        key = (
            (market.venue.value, market.canonical_id, instrument_key or "", field_name, asset_value)
            if scope == "market_scoped"
            else (market.venue.value, asset_value)
        )
        venue = market.venue
        label = f"{asset_value} · {market.venue.value}"
    asset_node_id = builder.add_node(
        node_kind,
        key,
        label=label,
        venue=venue,
        native_id=asset_value,
        market_id=market.canonical_id,
        source_observation_id=observation_id,
        identity_scope=scope,
    )
    builder.add_link(
        market_node_id,
        asset_node_id,
        link_type,
        market_id=market.canonical_id,
        source_observation_id=observation_id,
        source_field=field_name,
    )


def project_market_entity_context(
    records: Sequence[tuple[str, FrontierMarket | None, str | None]],
) -> EntityContextGraph:
    """Build a deterministic, size-bounded context graph from pinned market records.

    ``records`` contains (canonical market ID, market-or-missing, observation ID).
    Event IDs are scoped by venue; outcomes are scoped by market; asset tickers are
    scoped by venue or market unless a complete settlement identity is present.
    """
    builder = _EntityContextBuilder()
    source_market_count = len(records)
    ordered_records = heapq.nsmallest(
        MAX_ENTITY_CONTEXT_MARKETS + 1, records, key=lambda item: item[0]
    )
    if len(ordered_records) > MAX_ENTITY_CONTEXT_MARKETS:
        ordered_records = ordered_records[:MAX_ENTITY_CONTEXT_MARKETS]
        builder.truncation_reasons.add("market_input_limit")
    instrument_count = 0
    component_count = 0
    payout_state_count = 0
    represented_market_count = 0

    # Seed every market vertex first so any capped structural leaves remain joinable.
    market_node_ids: dict[str, str | None] = {}
    for market_id, market, observation_id in ordered_records:
        if market is not None:
            represented_market_count += 1
            if len(market.payoff.state_ids) > 128:
                builder.truncation_reasons.add("market_payoff_state_context_limit")
            label = market.title or market.native_market_id or market_id
            venue = market.venue
            market_kind = market.market_kind
            lifecycle = market.lifecycle
            native_id = market.native_market_id
        else:
            label = market_id
            venue = None
            market_kind = None
            lifecycle = None
            native_id = None
        resolution = market.resolution if market is not None else None
        payoff = market.payoff if market is not None else None
        market_node_ids[market_id] = builder.add_node(
            EntityContextKind.MARKET,
            (market_id,),
            label=label,
            venue=venue,
            native_id=native_id,
            market_id=market_id,
            source_observation_id=observation_id,
            market_kind=market_kind,
            lifecycle=lifecycle,
            resolution_authority=resolution.authority if resolution else None,
            resolution_primary_rule=resolution.primary_rule if resolution else None,
            resolution_secondary_rule=resolution.secondary_rule if resolution else None,
            resolution_closes_at_utc=resolution.closes_at_utc if resolution else None,
            resolution_settles_at_utc=resolution.settles_at_utc if resolution else None,
            resolution_fingerprint=resolution.resolution_fingerprint if resolution else None,
            resolution_verified=resolution.verified if resolution else None,
            payoff_state_ids=payoff.state_ids[:128] if payoff else (),
            payoff_exhaustive=payoff.exhaustive if payoff else None,
            payoff_verified=payoff.verified if payoff else None,
            record_available=market is not None,
        )

    for market_id, market, observation_id in ordered_records:
        market_node_id = market_node_ids.get(market_id)
        if market is None or market_node_id is None:
            continue
        venue_node_id = builder.add_node(
            EntityContextKind.VENUE,
            (market.venue.value,),
            label=market.venue.value,
            venue=market.venue,
            native_id=market.venue.value,
            market_id=market.canonical_id,
            source_observation_id=observation_id,
        )
        builder.add_link(
            market_node_id,
            venue_node_id,
            EntityContextLinkType.LISTED_ON,
            market_id=market.canonical_id,
            source_observation_id=observation_id,
            source_field="venue",
        )

        if market.native_event_id:
            event_node_id = builder.add_node(
                EntityContextKind.EVENT,
                (market.venue.value, market.native_event_id),
                label=market.native_event_title or market.native_event_id,
                venue=market.venue,
                native_id=market.native_event_id,
                market_id=market.canonical_id,
                source_observation_id=observation_id,
            )
            builder.add_link(
                market_node_id,
                event_node_id,
                EntityContextLinkType.PART_OF_EVENT,
                market_id=market.canonical_id,
                source_observation_id=observation_id,
                source_field="native_event_id",
            )

        event_contract = market.market_kind in {
            MarketKind.BINARY_EVENT,
            MarketKind.MULTI_OUTCOME_EVENT,
            MarketKind.CONDITIONAL_EVENT,
        }
        for instrument in market.instruments:
            if instrument_count >= MAX_ENTITY_CONTEXT_INSTRUMENTS:
                builder.truncation_reasons.add("instrument_context_limit")
                break
            instrument_count += 1
            canonical_instrument_id = instrument.canonical_id or stable_instrument_id(
                market.venue, market.native_market_id, instrument.native_instrument_id
            )
            instrument_kind = (
                EntityContextKind.CONTRACT if event_contract else EntityContextKind.INSTRUMENT
            )
            instrument_node_id = builder.add_node(
                instrument_kind,
                (canonical_instrument_id,),
                label=instrument.label or instrument.native_instrument_id,
                venue=market.venue,
                native_id=instrument.native_instrument_id,
                market_id=market.canonical_id,
                source_observation_id=observation_id,
                market_kind=market.market_kind,
                quantity_unit=instrument.quantity_unit,
                outcome_id=instrument.outcome_id,
            )
            builder.add_link(
                market_node_id,
                instrument_node_id,
                EntityContextLinkType.OFFERS_CONTRACT
                if event_contract
                else EntityContextLinkType.OFFERS_INSTRUMENT,
                market_id=market.canonical_id,
                source_observation_id=observation_id,
                source_field="instruments",
            )

            if instrument.outcome_id:
                outcome_node_id = builder.add_node(
                    EntityContextKind.OUTCOME,
                    (market.canonical_id, instrument.outcome_id),
                    label=market.outcome_label or instrument.label or instrument.outcome_id,
                    venue=market.venue,
                    native_id=instrument.outcome_id,
                    market_id=market.canonical_id,
                    source_observation_id=observation_id,
                    market_kind=market.market_kind,
                    outcome_id=instrument.outcome_id,
                )
                builder.add_link(
                    instrument_node_id,
                    outcome_node_id,
                    EntityContextLinkType.DEFINES_OUTCOME,
                    market_id=market.canonical_id,
                    source_observation_id=observation_id,
                    source_field="instruments[].outcome_id",
                )

            for payout in instrument.payouts:
                if payout_state_count >= MAX_ENTITY_CONTEXT_PAYOUT_STATES:
                    builder.truncation_reasons.add("payoff_state_context_limit")
                    break
                payout_state_count += 1
                state_node_id = builder.add_node(
                    EntityContextKind.PAYOFF_STATE,
                    (market.canonical_id, canonical_instrument_id, payout.state_id),
                    label=payout.state_id,
                    venue=market.venue,
                    native_id=payout.state_id,
                    market_id=market.canonical_id,
                    source_observation_id=observation_id,
                    market_kind=market.market_kind,
                    value=str(payout.amount),
                )
                builder.add_link(
                    instrument_node_id,
                    state_node_id,
                    EntityContextLinkType.PAYS_IN_STATE,
                    market_id=market.canonical_id,
                    source_observation_id=observation_id,
                    source_field="instruments[].payouts",
                )

            if instrument.price_currency_identity is not None:
                _add_asset_reference(
                    builder,
                    market=market,
                    market_node_id=instrument_node_id,
                    observation_id=observation_id,
                    asset_value=instrument.price_currency_identity.code,
                    field_name="instruments[].price_currency_identity",
                    link_type=EntityContextLinkType.QUOTES_IN_ASSET,
                    instrument_key=canonical_instrument_id,
                    identity=instrument.price_currency_identity,
                )
            elif instrument.price_currency:
                _add_asset_reference(
                    builder,
                    market=market,
                    market_node_id=instrument_node_id,
                    observation_id=observation_id,
                    asset_value=instrument.price_currency,
                    field_name="instruments[].price_currency",
                    link_type=EntityContextLinkType.QUOTES_IN_ASSET,
                    instrument_key=canonical_instrument_id,
                )

        for component in market.selected_components:
            if component_count >= MAX_ENTITY_CONTEXT_COMPONENTS:
                builder.truncation_reasons.add("component_contract_context_limit")
                break
            component_count += 1
            component_node_id = builder.add_node(
                EntityContextKind.COMPONENT_CONTRACT,
                (
                    market.canonical_id,
                    component.venue.value,
                    component.native_event_id or "",
                    component.native_market_id,
                    component.selected_side,
                ),
                label=component.native_market_id,
                venue=component.venue,
                native_id=component.native_market_id,
                market_id=market.canonical_id,
                source_observation_id=observation_id,
                selected_side=component.selected_side,
                value=(
                    str(component.yes_settlement_value_dollars)
                    if component.yes_settlement_value_dollars is not None
                    else None
                ),
            )
            builder.add_link(
                market_node_id,
                component_node_id,
                EntityContextLinkType.SELECTS_COMPONENT,
                market_id=market.canonical_id,
                source_observation_id=observation_id,
                source_field="selected_components",
            )

        if market.base_asset:
            _add_asset_reference(
                builder,
                market=market,
                market_node_id=market_node_id,
                observation_id=observation_id,
                asset_value=market.base_asset,
                field_name="base_asset",
                link_type=EntityContextLinkType.REFERENCES_BASE_ASSET,
            )
        if market.quote_asset:
            _add_asset_reference(
                builder,
                market=market,
                market_node_id=market_node_id,
                observation_id=observation_id,
                asset_value=market.quote_asset,
                field_name="quote_asset",
                link_type=EntityContextLinkType.QUOTES_IN_ASSET,
            )
        if market.settlement_asset_identity is not None:
            _add_asset_reference(
                builder,
                market=market,
                market_node_id=market_node_id,
                observation_id=observation_id,
                asset_value=market.settlement_asset_identity.code,
                field_name="settlement_asset_identity",
                link_type=EntityContextLinkType.SETTLES_IN_ASSET,
                identity=market.settlement_asset_identity,
            )
        elif market.settlement_asset:
            _add_asset_reference(
                builder,
                market=market,
                market_node_id=market_node_id,
                observation_id=observation_id,
                asset_value=market.settlement_asset,
                field_name="settlement_asset",
                link_type=EntityContextLinkType.SETTLES_IN_ASSET,
            )

    return builder.finish(
        source_market_count=source_market_count,
        represented_market_count=represented_market_count,
    )
