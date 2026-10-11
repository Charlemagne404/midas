"""Immutable declarative inputs and reproducible scenario families."""

import random
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.core.models import Book, Level, Market, Model, Nonnegative
from midas.paper.broker import AccountConfig, ExecutionModel
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

D = Decimal
FAMILIES = (
    "calm",
    "volatile",
    "thin",
    "deep",
    "disappearing",
    "liquidity_shock",
    "oscillating",
    "divergent",
    "near_resolution",
    "unresolved",
    "rounding",
    "fees",
    "low_capital",
    "one_sided",
    "network_partition",
    "metadata_conflict",
    "cancel_race",
    "uncertain_order",
    "ledger_mutation",
)
STRATEGIES = ("arbitrage", "conservative", "no_trade")


class Costs(Model):
    version: str = "explicit-costs-1"
    operating_per_fill: Nonnegative = D("0")
    redemption_cost: Nonnegative = D("0")
    annual_financing_rate: Nonnegative = D("0")
    collateral_value_factor: Decimal = Field(default=D(1), ge=0, le=1, allow_inf_nan=False)
    collateral_route_verified: bool = False
    assumptions: tuple[str, ...] = (
        "Costs are user estimates, not observed charges",
        "No automatic complete-set merge",
        "Resolution and spendable proceeds are separated by configured delay",
        "No empirically calibrated fill probability or queue priority",
    )


class ScenarioEvent(Model):
    id: str
    time_ms: int = Field(ge=0)
    priority: int = Field(default=0, ge=-100, le=100)
    kind: Literal[
        "market",
        "observe",
        "fault",
        "cancel",
        "expire",
        "settle",
        "control",
        "duplicate",
        "checkpoint",
        "mutate",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)


class Scenario(Model):
    schema_version: int = 1
    id: str
    family: str
    provenance: Literal["GENERATED", "HAND_AUTHORED", "RECORDED"] = "GENERATED"
    seed: int = Field(ge=0, le=2**32 - 1)
    market: Market
    books: dict[str, Book]
    account: AccountConfig = AccountConfig()
    strategy: Literal["arbitrage", "conservative", "no_trade"] = "arbitrage"
    observation_latency_ms: int = Field(default=0, ge=0, le=60_000)
    strategy_latency_ms: int = Field(default=0, ge=0, le=60_000)
    epoch_ms: int = Field(default=DEMO_EPOCH, ge=0)
    horizon_ms: int = Field(default=10_000, ge=0, le=365 * 86_400_000)
    events: tuple[ScenarioEvent, ...] = ()
    costs: Costs = Costs()
    dataset_id: str | None = None
    dataset_hash: str | None = None
    warnings: tuple[str, ...] = ()
    expected_invariants: tuple[str, ...] = (
        "capital_conservation",
        "independent_ledger",
        "no_future_observation",
        "risk_admission",
        "idempotency",
    )

    @model_validator(mode="after")
    def valid_events(self) -> "Scenario":
        if len({e.id for e in self.events}) != len(self.events):
            raise ValueError("Scenario event identities must be unique")
        if not self.books or any(k != b.asset_id for k, b in self.books.items()):
            raise ValueError("Scenario books require matching instrument identities")
        if self.provenance == "RECORDED" and not (self.dataset_id and self.dataset_hash):
            raise ValueError("Recorded scenarios require dataset identity and hash")
        return self


def generate(family: str, seed: int, execution: ExecutionModel | None = None) -> Scenario:
    if family not in FAMILIES:
        raise ValueError("Unknown scenario family")
    rng = random.Random(seed)
    market, books = binary_fixture("rounding_erased" if family == "rounding" else "profitable")
    prices = [D(rng.randint(20, 55)) / 100, D(rng.randint(25, 55)) / 100]
    depth = D(rng.randint(5, 25))
    if family == "thin":
        depth = D(rng.randint(1, 6))
    if family == "deep":
        depth = D(rng.randint(500, 2000))
    if family == "divergent":
        prices = [D(".15"), D(".90")]
    if family != "rounding":
        for i, asset in enumerate(books):
            book = books[asset]
            price = prices[i]
            books[asset] = book.model_copy(
                update={
                    "asks": (
                        Level(price=price, size=depth),
                        Level(price=price + D(".02"), size=depth),
                    ),
                    "bids": (Level(price=price - D(".01"), size=depth),),
                }
            )
    if family == "fees":
        market = market.model_copy(
            update={"fee": market.fee.model_copy(update={"rate": D(rng.randint(1, 15)) / 100})}
        )
    account = AccountConfig(execution=execution or ExecutionModel())
    if family == "low_capital":
        account = account.model_copy(update={"capital": D(rng.randint(1, 5))})
    events: list[ScenarioEvent] = [ScenarioEvent(id="initial", time_ms=0, kind="observe")]
    if family in {"volatile", "oscillating", "disappearing", "liquidity_shock", "one_sided"}:
        count = 6 if family in {"volatile", "oscillating"} else 1
        for index in range(count):
            changed = {}
            t = (index + 1) * rng.randint(50, 300)
            for i, (a, b) in enumerate(books.items()):
                price = D(rng.randint(30, 85)) / 100
                withdrawn = family in {"liquidity_shock", "one_sided"} and (
                    i == 1 or family == "liquidity_shock"
                )
                changed[a] = b.model_copy(
                    update={
                        "asks": () if withdrawn else (Level(price=price, size=depth),),
                        "bids": (Level(price=price - D(".01"), size=depth),),
                        "received_ts_ms": DEMO_EPOCH + t,
                        "exchange_ts_ms": DEMO_EPOCH + t,
                    }
                ).model_dump(mode="json")
            events.append(
                ScenarioEvent(
                    id=f"market:{index}", time_ms=t, kind="market", payload={"books": changed}
                )
            )
    if family in {"network_partition", "uncertain_order"}:
        events.append(
            ScenarioEvent(
                id="lost-ack",
                time_ms=1,
                kind="fault",
                payload={"action_kind": "ack", "fault": "lost_ack"},
            )
        )
    if family == "metadata_conflict":
        events.append(
            ScenarioEvent(
                id="rules-change",
                time_ms=100,
                kind="market",
                payload={
                    "market": market.model_copy(
                        update={"description": "Conflicting rules"}
                    ).model_dump(mode="json")
                },
            )
        )
    if family == "cancel_race":
        events.append(
            ScenarioEvent(
                id="cancel-request",
                time_ms=220,
                kind="cancel",
                payload={"delay_ms": rng.randint(0, 100)},
            )
        )
    if family == "ledger_mutation":
        events.append(
            ScenarioEvent(
                id="controlled-defect",
                time_ms=1000,
                kind="mutate",
                payload={"mutation": "fill_charge"},
            )
        )
    settle_time = 2000 if family == "near_resolution" else 8000
    horizon = 86_400_000 if family == "unresolved" else 10_000
    if family != "unresolved":
        events.append(
            ScenarioEvent(
                id="settlement-confirmed",
                time_ms=settle_time,
                kind="settle",
                payload={"payout": {a: str(int(i == seed % 2)) for i, a in enumerate(books)}},
            )
        )
    return Scenario(
        id=f"{family}:{seed}",
        family=family,
        seed=seed,
        market=market,
        books=books,
        account=account,
        horizon_ms=horizon,
        events=tuple(events),
        warnings=("Synthetic behavior; not a sample of real fill probability",),
    )
