from __future__ import annotations

from midas.frontier.entity_graph import (
    MAX_ENTITY_CONTEXT_MARKETS,
    EntityContextKind,
    EntityContextLinkType,
    project_market_entity_context,
)
from midas.frontier.models import Venue

from .builders import market


def test_entity_context_is_deterministic_and_keeps_native_semantics_scoped() -> None:
    polymarket_a = market(Venue.POLYMARKET, "event-a").model_copy(
        update={"native_event_id": "shared-event", "base_asset": "BTC"}
    )
    polymarket_b = market(Venue.POLYMARKET, "event-b").model_copy(
        update={"native_event_id": "other-event", "base_asset": "BTC"}
    )
    kalshi = market(Venue.KALSHI, "event-c").model_copy(
        update={"native_event_id": "shared-event", "base_asset": "BTC"}
    )
    records = (
        (polymarket_a.canonical_id, polymarket_a, "observation-a"),
        (polymarket_b.canonical_id, polymarket_b, "observation-b"),
        (kalshi.canonical_id, kalshi, "observation-c"),
    )

    graph = project_market_entity_context(records)
    permuted = project_market_entity_context(tuple(reversed(records)))
    nodes = {node.entity_id: node for node in graph.nodes}
    events = [node for node in graph.nodes if node.kind == EntityContextKind.EVENT]
    usd_assets = [node for node in graph.nodes if node.kind == EntityContextKind.SETTLEMENT_ASSET]
    btc_assets = [
        node
        for node in graph.nodes
        if node.kind == EntityContextKind.ASSET_REFERENCE and node.native_id == "BTC"
    ]
    market_node = next(
        node
        for node in graph.nodes
        if node.kind == EntityContextKind.MARKET and node.native_id == "event-a"
    )

    assert graph.model_dump(mode="json") == permuted.model_dump(mode="json")
    assert len(events) == 3
    assert len({node.entity_id for node in events if node.native_id == "shared-event"}) == 2
    assert len(usd_assets) == 1
    assert set(usd_assets[0].market_ids) == {
        polymarket_a.canonical_id,
        polymarket_b.canonical_id,
        kalshi.canonical_id,
    }
    assert len(btc_assets) == 2
    assert any(
        set(node.market_ids) == {polymarket_a.canonical_id, polymarket_b.canonical_id}
        for node in btc_assets
    )
    assert market_node.resolution_authority == "Official election authority"
    assert market_node.resolution_closes_at_utc is not None
    assert market_node.payoff_state_ids == ("yes", "no")
    assert market_node.payoff_exhaustive is True
    assert {link.link_type for link in graph.links} >= {
        EntityContextLinkType.LISTED_ON,
        EntityContextLinkType.PART_OF_EVENT,
        EntityContextLinkType.OFFERS_CONTRACT,
        EntityContextLinkType.DEFINES_OUTCOME,
        EntityContextLinkType.PAYS_IN_STATE,
        EntityContextLinkType.SETTLES_IN_ASSET,
    }
    assert all(link.economic_equivalence_asserted is False for link in graph.links)
    assert all(
        observation_id in {"observation-a", "observation-b", "observation-c"}
        for node in nodes.values()
        for observation_id in node.source_observation_ids
    )


def test_entity_context_retains_missing_records_and_reports_bounded_truncation() -> None:
    present = market(Venue.POLYMARKET, "z-present")
    records = [
        (f"missing:{index:04d}", None, f"missing-observation-{index}")
        for index in range(MAX_ENTITY_CONTEXT_MARKETS - 1)
    ]
    records.extend(
        [
            (present.canonical_id, present, "present-observation"),
            ("zzzz-extra", None, "extra-observation"),
        ]
    )

    graph = project_market_entity_context(records)
    missing_nodes = [
        node
        for node in graph.nodes
        if node.kind == EntityContextKind.MARKET and not node.record_available
    ]

    assert graph.source_market_count == MAX_ENTITY_CONTEXT_MARKETS + 1
    assert graph.represented_market_count == 1
    assert graph.truncated is True
    assert "market_input_limit" in graph.truncation_reasons
    assert len(missing_nodes) == MAX_ENTITY_CONTEXT_MARKETS - 1
    assert any(node.native_id == "z-present" for node in graph.nodes)
