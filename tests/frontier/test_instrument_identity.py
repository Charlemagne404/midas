from __future__ import annotations

import pytest
from midas.frontier.models import FrontierMarket, Venue, stable_instrument_id
from pydantic import ValidationError

from tests.frontier.builders import market


def test_market_assigns_deterministic_venue_scoped_instrument_ids():
    first = market(Venue.POLYMARKET, "same-native-market")
    repeated = market(Venue.POLYMARKET, "same-native-market")
    first_yes = first.instruments[0]
    repeated_yes = repeated.instruments[0]

    assert first.schema_version == 5
    assert first_yes.canonical_id == stable_instrument_id(
        first.venue, first.native_market_id, first_yes.native_instrument_id
    )
    assert first_yes.canonical_id == repeated_yes.canonical_id
    assert first_yes.canonical_id != first.instruments[1].canonical_id


def test_instrument_identity_distinguishes_venue_market_and_instrument_fields():
    source = market(Venue.POLYMARKET, "same-native-market")
    native_instrument_id = "same-native-instrument"
    identity = stable_instrument_id(source.venue, source.native_market_id, native_instrument_id)

    assert identity != stable_instrument_id(
        Venue.KALSHI, source.native_market_id, native_instrument_id
    )
    assert identity != stable_instrument_id(source.venue, "different-market", native_instrument_id)
    assert identity != stable_instrument_id(
        source.venue, source.native_market_id, "different-instrument"
    )


@pytest.mark.parametrize("schema_version", [1, 2, 3, 4])
def test_legacy_market_payload_derives_instrument_identity_without_rewriting_version(
    schema_version: int,
):
    payload = market(Venue.KALSHI, f"legacy-v{schema_version}").model_dump(mode="python")
    payload["schema_version"] = schema_version
    for instrument in payload["instruments"]:
        instrument.pop("canonical_id")

    normalized = FrontierMarket.model_validate(payload)

    assert normalized.schema_version == schema_version
    assert all(item.canonical_id is not None for item in normalized.instruments)
    assert normalized.has_valid_structure


def test_market_rejects_instrument_id_bound_to_other_native_identity():
    payload = market(Venue.POLYMARKET, "identity-mismatch").model_dump(mode="python")
    payload["instruments"][0]["canonical_id"] = "instrument-v1:" + "0" * 64

    with pytest.raises(
        ValidationError, match="Canonical instrument identity differs from its venue"
    ):
        FrontierMarket.model_validate(payload)


def test_copied_market_with_a_tampered_instrument_id_fails_revalidation():
    source = market(Venue.POLYMARKET, "copied-identity-mismatch")
    instruments = list(source.instruments)
    instruments[0] = instruments[0].model_copy(update={"canonical_id": "instrument-v1:" + "0" * 64})

    assert not source.model_copy(update={"instruments": tuple(instruments)}).has_valid_structure
