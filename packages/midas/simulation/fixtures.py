from decimal import Decimal

from midas.core.models import Book, Fee, Instrument, Level, Market, Source

D = Decimal
DEMO_EPOCH = 1791720000000


def binary_fixture(
    name: str = "profitable", ts: int = DEMO_EPOCH
) -> tuple[Market, dict[str, Book]]:
    market = Market(
        id=name,
        event_id=f"event:{name}",
        question=f"Synthetic binary • {name.replace('_', ' ')}",
        condition_id=f"synthetic:{name}",
        protocol="v1",
        instruments=(
            Instrument(asset_id=f"{name}:yes", label="Yes"),
            Instrument(asset_id=f"{name}:no", label="No"),
        ),
        source=Source.SYNTHETIC,
        complementary_verified=True,
        payout_verified=True,
        payout_evidence="Synthetic scenario contract: Yes + No pays 1 virtual USD, including split payouts",
        fee=Fee(verified=True, evidence="Synthetic exchange configuration; zero taker fee"),
    )
    asks = [("0.42", "10"), ("0.53", "10")]
    if name in {"unprofitable", "break_even", "fee_erased", "rounding_erased"}:
        asks = [
            ("0.50", "10"),
            (
                {
                    "unprofitable": "0.53",
                    "break_even": "0.50",
                    "fee_erased": "0.49",
                    "rounding_erased": "0.4999",
                }[name],
                "10",
            ),
        ]
    books = {}
    for instrument, (price, size) in zip(market.instruments, asks, strict=True):
        tick = D("0.0001") if name == "rounding_erased" else D("0.01")
        books[instrument.asset_id] = Book(
            asset_id=instrument.asset_id,
            condition_id=market.condition_id,
            asks=(Level(price=D(price), size=D(size)),),
            bids=(Level(price=D(price) - tick, size=D("100")),),
            tick_size=tick,
            received_ts_ms=ts,
            exchange_ts_ms=ts,
            source=Source.SYNTHETIC,
        )
    return market, books
