from __future__ import annotations

from decimal import Decimal

from midas.frontier.entity_graph import (
    MAX_ENTITY_CONTEXT_MARKETS,
    EntityContextKind,
    EntityContextLinkType,
    project_market_entity_context,
)
from midas.frontier.models import MarketInstrument, PayoffSpec, StatePayout, Venue

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


def test_entity_context_keeps_labels_valid_for_empty_native_labels() -> None:
    market_with_empty_native_labels = market(Venue.POLYMARKET, "empty-labels").model_copy(
        update={
            "instruments": (
                MarketInstrument.model_construct(
                    native_instrument_id="",
                    label="",
                    payouts=(StatePayout.model_construct(state_id="", amount=Decimal("0")),),
                ),
            )
        }
    )

    graph = project_market_entity_context(
        ((market_with_empty_native_labels.canonical_id, market_with_empty_native_labels, "obs"),)
    )

    assert all(node.label for node in graph.nodes)
    assert any(node.label.startswith("instrument-v1:") for node in graph.nodes)
    assert any(node.label == "Unlabelled payout state" for node in graph.nodes)


def test_entity_context_marks_clipped_external_display_fields() -> None:
    oversized = "x" * 600
    source = market(Venue.POLYMARKET, "oversized-context").model_copy(
        update={
            "instruments": (
                MarketInstrument.model_construct(
                    native_instrument_id="native-id",
                    label=oversized,
                    outcome_id=oversized,
                    payouts=(StatePayout.model_construct(state_id=oversized, amount=Decimal("1")),),
                ),
            ),
            "payoff": PayoffSpec.model_construct(state_ids=(oversized,)),
        }
    )

    graph = project_market_entity_context(((source.canonical_id, source, "observation"),))
    market_node = next(node for node in graph.nodes if node.kind == EntityContextKind.MARKET)
    instrument_node = next(node for node in graph.nodes if node.kind == EntityContextKind.CONTRACT)
    outcome_node = next(node for node in graph.nodes if node.kind == EntityContextKind.OUTCOME)
    payout_node = next(node for node in graph.nodes if node.kind == EntityContextKind.PAYOFF_STATE)

    assert instrument_node.label == oversized[:512]
    assert instrument_node.label_truncated is True
    assert instrument_node.outcome_id == oversized[:512]
    assert instrument_node.outcome_id_truncated is True
    assert outcome_node.native_id_truncated is True
    assert payout_node.native_id == oversized[:512]
    assert payout_node.native_id_truncated is True
    assert market_node.payoff_state_ids == (oversized[:512],)
    assert market_node.payoff_state_ids_truncated is True
    assert source.instruments[0].label == oversized
    assert source.instruments[0].outcome_id == oversized
    assert source.instruments[0].payouts[0].state_id == oversized
    assert source.payoff.state_ids == (oversized,)
    assert graph.truncated is True
    assert "entity_field_length_limit" in graph.truncation_reasons
