"""Versioned first-position friction labels reconstructed from its monetary ledger."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from midas.laboratory.spec import Costs

D = Decimal
VERSION = "initial-position-friction-2"
LEGACY_VERSION = "initial-position-friction-1"
COMPONENTS = (
    "adverse_slippage_usd",
    "exchange_fees_usd",
    "operating_usd",
    "redemption_usd",
    "financing_usd",
)


def reconstruct(record: dict[str, Any]) -> dict[str, str]:
    costs = Costs.model_validate(record["costs"])
    benchmarks = {asset: D(value) for asset, value in record["observed_best_asks"].items()}
    if len(benchmarks) != 2 or any(not p.is_finite() or not 0 < p < 1 for p in benchmarks.values()):
        raise ValueError("Invalid decision-time price benchmark")
    ledger = record["ledger"]
    if len({e["id"] for e in ledger}) != len(ledger):
        raise ValueError("Duplicate cost ledger entry")
    last, held, integral, fees, slippage, fills = (
        record["decision_time_ms"],
        D(0),
        D(0),
        D(0),
        D(0),
        0,
    )
    terminal = record["terminal_time_ms"]
    if terminal < last:
        raise ValueError("Cost horizon precedes decision")
    for entry in ledger:
        timestamp = entry["time_ms"]
        if not last <= timestamp <= terminal:
            raise ValueError("Cost ledger timestamps outside label horizon or unordered")
        integral += held * (timestamp - last)
        last = timestamp
        delta = D(entry["locked_delta"]) + D(entry["reserved_delta"])
        if not delta.is_finite():
            raise ValueError("Nonfinite cost capital delta")
        held += delta
        if held < 0:
            raise ValueError("Negative financed capital")
        if entry["kind"] == "fill":
            quantity, price, fee = D(entry["quantity"]), D(entry["price"]), D(entry["fee"])
            if (
                entry["asset_id"] not in benchmarks
                or entry["order_id"] not in record["initial_order_ids"]
                or any(not v.is_finite() for v in (quantity, price, fee))
                or quantity <= 0
                or not 0 < price < 1
                or fee < 0
            ):
                raise ValueError("Invalid initial fill cost evidence")
            slippage += quantity * max(D(0), price - benchmarks[entry["asset_id"]])
            fees += fee
            fills += 1
    integral += held * (terminal - last)
    if record.get("version", LEGACY_VERSION) == VERSION:
        integral = financing_integral(record)
    financing = integral * costs.annual_financing_rate / D(365 * 86400000)
    if record.get("version", LEGACY_VERSION) == VERSION:
        financing = sum(
            (
                (
                    D(t["locked_usd"])
                    + D(t["reserved_usd"])
                    + (D(t["available_usd"]) if t["pending_action_ids"] else D(0))
                )
                * (t["end_ms"] - t["start_ms"])
                * costs.annual_financing_rate
                / D(365 * 86400000)
                for t in record["financing_trace"]
            ),
            D(0),
        )
    components = {
        "adverse_slippage_usd": slippage,
        "exchange_fees_usd": fees,
        "operating_usd": fills * costs.operating_per_fill,
        "redemption_usd": int(record["settled"]) * costs.redemption_cost,
        "financing_usd": financing,
    }
    return {
        **{k: str(v) for k, v in components.items()},
        "total_usd": str(sum(components.values(), D(0))),
        "locked_reserved_integral_usd_ms": str(integral),
    }


def financing_integral(record: dict[str, Any]) -> Decimal:
    """Audit held capital against ledger prefixes, including pending availability."""
    trace = record["financing_trace"]
    ledger = record["ledger"]
    last = record["decision_time_ms"]
    integral = D(0)
    for interval in trace:
        start, end = interval["start_ms"], interval["end_ms"]
        count = interval["ledger_count"]
        if (
            start != last
            or end <= start
            or end > record["terminal_time_ms"]
            or not 0 <= count <= len(ledger)
        ):
            raise ValueError("Invalid financing interval coverage or ledger prefix")
        prefix = ledger[:count]
        if any(e["time_ms"] > start for e in prefix) or any(
            e["time_ms"] < start for e in ledger[count:]
        ):
            raise ValueError("Financing prefix crosses interval boundary")
        available = D(record["starting_capital_usd"]) + sum(
            (D(e["available_delta"]) for e in prefix), D(0)
        )
        reserved = sum((D(e["reserved_delta"]) for e in prefix), D(0))
        locked = sum((D(e["locked_delta"]) for e in prefix), D(0))
        values = (available, reserved, locked)
        if any(not v.is_finite() or v < 0 for v in values) or values != tuple(
            D(interval[k]) for k in ("available_usd", "reserved_usd", "locked_usd")
        ):
            raise ValueError("Financing capital differs from monetary ledger prefix")
        pending = interval["pending_action_ids"]
        if len(set(pending)) != len(pending):
            raise ValueError("Duplicate pending action evidence")
        held = locked + reserved + (available if pending else D(0))
        integral += held * (end - start)
        last = end
    if last != record["terminal_time_ms"]:
        raise ValueError("Financing trace does not cover label horizon")
    return integral


def quote_baseline(observation: dict[str, Any], quantity: float, costs: Costs) -> str:
    """Observed-best-price fee estimate for two full fills; no assumed future prices."""
    market = observation["market"]
    if market["fee"]["exponent"] != 1:
        raise ValueError("Quoted cost baseline requires the documented simulator fee curve")
    prices = [
        D(observation["books"][i["asset_id"]]["asks"][0]["price"]) for i in market["instruments"]
    ]
    q, rate = D(str(quantity)), D(market["fee"]["rate"])
    fees = sum(
        ((q * rate * p * (1 - p)).quantize(D(".00001"), rounding=ROUND_HALF_UP) for p in prices),
        D(0),
    )
    return str(fees + 2 * costs.operating_per_fill + costs.redemption_cost)


def outcome(
    exchange: dict[str, Any],
    observation: dict[str, Any],
    costs: Costs,
    terminal_time_ms: int,
    quoted_full_fill: str,
    financing_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    assets = {o["asset_id"] for o in exchange["orders"]}
    if len(exchange["orders"]) != 2 or len(assets) != 2:
        raise ValueError("Cost target requires the first two-leg position")
    record = {
        "version": VERSION,
        "units": "virtual USD",
        "decision_time_ms": observation["time_ms"],
        "terminal_time_ms": terminal_time_ms,
        "settled": exchange["settled"],
        "initial_order_ids": [o["id"] for o in exchange["orders"]],
        "quoted_quantity": str(exchange["orders"][0]["quantity"]),
        "fee_rate": observation["market"]["fee"]["rate"],
        "observed_best_asks": {a: observation["books"][a]["asks"][0]["price"] for a in assets},
        "costs": costs.model_dump(mode="json"),
        "ledger": exchange["ledger"],
        "starting_capital_usd": exchange["starting"],
        "financing_trace": financing_trace,
        "quoted_full_fill_friction_usd": quoted_full_fill,
    }
    record.update(reconstruct(record))
    return record


def label(row: dict[str, Any]) -> float:
    record = row.get("execution_cost_outcome")
    if (
        not record
        or record["version"] not in {VERSION, LEGACY_VERSION}
        or record["units"] != "virtual USD"
    ):
        raise ValueError("Versioned execution-cost evidence required")
    if (
        record["decision_time_ms"] != row["decision_time_ms"]
        or record["costs"] != row["economic_assumptions"]
    ):
        raise ValueError("Cost label differs from decision/economic provenance")
    expected = reconstruct(record)
    if any(D(record[k]) != D(value) for k, value in expected.items()):
        raise ValueError("Cost components differ from saved ledger")
    baseline = D(record["quoted_full_fill_friction_usd"])
    if not baseline.is_finite() or baseline < 0:
        raise ValueError("Invalid quoted cost baseline")
    costs = Costs.model_validate(record["costs"])
    q, rate = D(record["quoted_quantity"]), D(record["fee_rate"])
    if not q.is_finite() or q <= 0 or not rate.is_finite() or rate < 0:
        raise ValueError("Invalid quoted cost assumptions")
    quoted_fees = sum(
        (
            (q * rate * D(p) * (1 - D(p))).quantize(D(".00001"), rounding=ROUND_HALF_UP)
            for p in record["observed_best_asks"].values()
        ),
        D(0),
    )
    if baseline != quoted_fees + 2 * costs.operating_per_fill + costs.redemption_cost:
        raise ValueError("Quoted cost baseline differs from decision prices and assumptions")
    result = float(D(expected["total_usd"]))
    import math

    if not math.isfinite(result):
        raise ValueError("Nonfinite execution-cost target")
    return result
