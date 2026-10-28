from midas.frontier.discovery_comparison import (
    DiscoveryScope,
    compare_discovery_scopes,
)
from midas.frontier.models import Venue
from midas.frontier.relationships import verify_same_payoff

from tests.frontier.builders import T0, book, market


def test_discovery_scope_comparison_is_deterministic_and_exposes_cross_venue_delta():
    left = market(Venue.POLYMARKET, "discovery-left")
    right = market(Venue.KALSHI, "discovery-right")
    relationship = verify_same_payoff(
        left,
        right,
        state_mapping={"yes": "yes", "no": "no"},
        instrument_mapping={
            left.instruments[0].native_instrument_id: right.instruments[0].native_instrument_id,
            left.instruments[1].native_instrument_id: right.instruments[1].native_instrument_id,
        },
        external_assertion_id="fixture-discovery-map",
        evidence_observation_ids=(left.provenance.observation_id, right.provenance.observation_id),
        asserted_at_utc=T0,
    )
    markets = (left, right)
    books = (
        book(left, left.instruments[0].native_instrument_id, "0.40"),
        book(left, left.instruments[1].native_instrument_id, "0.65"),
        book(right, right.instruments[0].native_instrument_id, "0.55"),
        book(right, right.instruments[1].native_instrument_id, "0.45"),
    )
    kwargs = {
        "markets": markets,
        "books": books,
        "verified_relationships": (relationship,),
        "as_of_utc": T0,
        "code_version": "fixture-discovery-scope-v1",
        "relationship_limit": 500,
    }

    first, first_replays = compare_discovery_scopes(**kwargs)
    second, second_replays = compare_discovery_scopes(**kwargs)

    assert first == second
    assert first_replays == second_replays
    assert [arm.scope for arm in first.arms] == list(DiscoveryScope)
    polymarket, venue_local, cross_venue = first.arms
    assert polymarket.market_count == 1
    assert polymarket.relationship_count == 0
    assert venue_local.market_count == 2
    assert venue_local.relationship_count == 0
    assert cross_venue.market_count == 2
    assert cross_venue.relationship_count == 1
    assert polymarket.candidates == venue_local.candidates == ()
    assert len(cross_venue.candidates) == 2
    assert all(
        item.participating_venues == (Venue.KALSHI, Venue.POLYMARKET)
        for item in cross_venue.candidates
    )
    assert first.deltas[1].compared_only_candidate_count == 2
    assert first.deltas[2].compared_only_candidate_count == 2
    assert first.normalized_input_sha256 != "0" * 64
