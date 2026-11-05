from copy import deepcopy
from decimal import Decimal

import pytest
from midas.frontier.models import FrontierMarket, MarketBatch, StatePayout, Venue
from pydantic import ValidationError

from tests.frontier.builders import market


@pytest.mark.parametrize("duplicate_amount", (Decimal("1"), Decimal("0")))
def test_verified_payoff_rejects_duplicate_state_rows(duplicate_amount: Decimal) -> None:
    payload = market(Venue.POLYMARKET, "DUPLICATE-PAYOUT").model_dump(mode="python")
    yes_instrument = payload["instruments"][0]
    payouts = list(yes_instrument["payouts"])
    duplicate = deepcopy(payouts[0])
    duplicate["amount"] = duplicate_amount
    payouts.insert(1, duplicate)
    yes_instrument["payouts"] = payouts

    with pytest.raises(ValidationError, match="payout state identifiers must be unique"):
        FrontierMarket.model_validate(payload)


def test_market_validation_revalidates_prebuilt_instrument_payouts() -> None:
    base = market(Venue.POLYMARKET, "DUPLICATE-PAYOUT-CONSTRUCT")
    yes = base.instruments[0]
    duplicate = StatePayout(state_id="yes", amount=Decimal("0"))
    unchecked_yes = yes.model_copy(
        update={"payouts": (*yes.payouts[:1], duplicate, *yes.payouts[1:])}
    )
    payload = base.model_dump(mode="python")
    payload["instruments"] = (unchecked_yes, base.instruments[1])

    with pytest.raises(ValidationError, match="payout state identifiers must be unique"):
        FrontierMarket.model_validate(payload)


def test_market_batch_rejects_a_member_from_another_venue() -> None:
    foreign_market = market(Venue.KALSHI, "FOREIGN-BATCH-MEMBER")

    with pytest.raises(ValidationError, match="Market-member venue must match its batch"):
        MarketBatch(venue=Venue.POLYMARKET, markets=(foreign_market,))
