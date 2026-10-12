"""Future venue quotes are labels only; decision features remain observable."""

import copy
from decimal import Decimal, localcontext
from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Book, Market, Source, Status
from midas.economics.attestation import digest
from midas.laboratory.runtime import Environment

LABEL_VERSION = "original-quote-first-arrival-1"
LABEL_DEFINITION = (
    "Original risk-admitted quantity remains mathematically VERIFIED within its allocated "
    "capital and both original order limits at its earliest scheduled submission arrival. "
    "Uses private synthetic venue quotes only for the label, before any initial order submits. "
    "Neither actual fills nor later second-leg availability are guaranteed."
)


def quote_label(env: Environment, position_id: str, arrival_ms: int) -> dict[str, Any]:
    if env.scenario.provenance != "GENERATED" or env.scenario.market.source != Source.SYNTHETIC:
        raise ValueError("Persistence labels require generated synthetic venue states")
    position = env.state["positions"][position_id]
    proposal = position["decision"]["evaluation"]
    quantity = Decimal(proposal["quantity"])
    budget = Decimal(position["exchange"]["starting"])
    pending = [
        a for a in env.state["pending"] if a["position"] == position_id and a["kind"] == "submit"
    ]
    if len(pending) != 2 or min(a["due"] for a in pending) != arrival_ms:
        raise ValueError("Label must precede both original submits at the first arrival")
    event = env.clock.peek()
    if (
        event is None
        or event.kind != "action"
        or event.time != arrival_ms
        or event.payload["action_id"] not in {a["id"] for a in pending}
    ):
        raise ValueError("Advance all earlier venue events before labeling arrival")
    limits = {a["asset"]: Decimal(a["limit"]) for a in pending}
    if (
        len(limits) != 2
        or quantity <= 0
        or not quantity.is_finite()
        or not budget.is_finite()
        or budget <= 0
    ):
        raise ValueError("Invalid original binary proposal")
    books = {a: Book.model_validate(copy.deepcopy(b)) for a, b in env.books.items() if a in limits}
    future = any(b.exchange_ts_ms is None or b.exchange_ts_ms > arrival_ms for b in books.values())
    # A private venue does not wait for delayed observer receipt. Its timestamp
    # basis is the exchange clock, recorded explicitly in label provenance.
    venue_books = (
        {a: b.model_copy(update={"received_ts_ms": b.exchange_ts_ms}) for a, b in books.items()}
        if not future
        else books
    )
    with localcontext() as context:
        context.prec = 28
        result = (
            None
            if future
            else BinaryStrategy(
                env.scenario.account.limits.max_age_ms, env.scenario.account.limits.min_edge
            ).evaluate(
                Market.model_validate(env.market),
                venue_books,
                arrival_ms,
                budget,
                quantity=quantity,
            )
        )
    within_limits = result is not None and all(
        s.asset_id in limits and s.price <= limits[s.asset_id] for s in result.slices
    )
    return {
        "label_version": LABEL_VERSION,
        "label": int(result is not None and result.status == Status.VERIFIED and within_limits),
        "arrival_time_ms": arrival_ms,
        "quantity": str(quantity),
        "allocated_capital": str(budget),
        "original_limits": {a: str(v) for a, v in limits.items()},
        "quote_status": "INVALID_FUTURE_VENUE_TIMESTAMP" if future else result.status.value,
        "within_original_limits": within_limits,
        "venue_state_sha256": digest([env.market, env.books]),
        "venue_clock_basis": "exchange timestamp; delayed observer receipt is not a venue timestamp",
        "definition": LABEL_DEFINITION,
    }


def first_arrival_label(env: Environment, position_id: str) -> dict[str, Any]:
    while not env.finished:
        event = env.clock.peek()
        if event is None or event.time > env.scenario.epoch_ms + env.scenario.horizon_ms:
            break
        if event.kind == "action":
            action = next(
                (a for a in env.state["pending"] if a["id"] == event.payload["action_id"]), None
            )
            if action and action["position"] == position_id and action["kind"] == "submit":
                return quote_label(env, position_id, event.time)
        env.step()
        if env.errors:
            raise ValueError("Invalid simulation while constructing persistence label")
    return {
        "label_version": LABEL_VERSION,
        "label": 0,
        "arrival_time_ms": None,
        "quote_status": "NO_ARRIVAL_WITHIN_HORIZON",
        "definition": LABEL_DEFINITION,
    }
