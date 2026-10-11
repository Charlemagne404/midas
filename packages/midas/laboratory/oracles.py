"""Reference arithmetic uses rational integers, independent of venue Decimal helpers."""

from fractions import Fraction
from typing import Any


def rational(value: Any) -> Fraction:
    return Fraction(str(value))


def ceil_units(value: Fraction, scale: int) -> Fraction:
    scaled = value * scale
    return Fraction(-(-scaled.numerator // scaled.denominator), scale)


def fee(quantity: Any, price: Any, rate: Any) -> Fraction:
    q, p, r = rational(quantity), rational(price), rational(rate)
    scaled = q * r * p * (1 - p) * 100_000
    # Nonnegative half-up rounding, implemented with integer division.
    return Fraction(
        (2 * scaled.numerator + scaled.denominator) // (2 * scaled.denominator), 100_000
    )


def payout(quantity: Any, numerator: int, denominator: int) -> Fraction:
    if denominator <= 0 or not 0 <= numerator <= denominator:
        raise ValueError("Invalid payout vector component")
    return Fraction((rational(quantity) * 1_000_000 * numerator // denominator), 1_000_000)


def verify(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    total_cash = rational(state["config"]["capital"])
    total_reserved = total_basis = total_pnl = Fraction(0)
    for position_id, position in state["positions"].items():
        x = position["exchange"]
        cash = rational(x["starting"])
        reserved = basis = proceeds = spent = Fraction(0)
        quantities: dict[str, Fraction] = {}
        order_fills: dict[str, Fraction] = {}
        asset_basis: dict[str, Fraction] = {}
        identities: set[str] = set()
        for e in x["ledger"]:
            label = f"{position_id}/{e['id']}"
            if e["id"] in identities:
                errors.append(f"idempotency: duplicate ledger identity {label}")
            identities.add(e["id"])
            a, r, b = (
                rational(e[k]) for k in ("available_delta", "reserved_delta", "locked_delta")
            )
            cash, reserved, basis = cash + a, reserved + r, basis + b
            if min(cash, reserved, basis) < 0:
                errors.append(f"capital_conservation: negative bucket {label}")
            if e["kind"] in {"reserve", "release"} and (a + r != 0 or b != 0):
                errors.append(f"independent_ledger: nonconserving reservation {label}")
            asset = e.get("asset_id")
            q = rational(e["quantity"])
            if e["kind"] == "fill":
                expected_fee = fee(q, e["price"], x["market"]["fee"]["rate"])
                charge = ceil_units(q * rational(e["price"]), 1_000_000) + expected_fee
                if (a, r, b, rational(e["fee"])) != (Fraction(0), -charge, charge, expected_fee):
                    errors.append(f"independent_ledger: fill charge mismatch {label}")
                quantities[asset] = quantities.get(asset, Fraction(0)) + q
                order_fills[e["order_id"]] = order_fills.get(e["order_id"], Fraction(0)) + q
                asset_basis[asset] = asset_basis.get(asset, Fraction(0)) + charge
                spent += charge
            if e["kind"] == "settlement":
                expected = (
                    payout(q, e["payout_numerator"], e["payout_denominator"])
                    if e["payout_denominator"]
                    else q * rational(e["price"])
                )
                if a != expected or r != 0 or b != -asset_basis.get(asset, Fraction(0)):
                    errors.append(f"independent_ledger: settlement mismatch {label}")
                quantities[asset] = quantities.get(asset, Fraction(0)) - q
                proceeds += expected
            if any(qty < 0 for qty in quantities.values()):
                errors.append(f"independent_ledger: negative inventory {label}")
        if cash + reserved != rational(x["starting"]) - spent + proceeds:
            errors.append(f"capital_conservation: {position_id}")
        if reserved != sum((rational(o["reservation"]) for o in x["orders"]), Fraction(0)):
            errors.append(f"independent_ledger: reservations {position_id}")
        for o in x["orders"]:
            if order_fills.get(o["id"], 0) + rational(o["remaining"]) != rational(o["quantity"]):
                errors.append(f"independent_ledger: order quantity {o['id']}")
        if asset_basis != {a: rational(v) for a, v in x["asset_costs"].items()}:
            errors.append(f"independent_ledger: position basis {position_id}")
        total_cash += cash - rational(x["starting"])
        total_reserved += reserved
        total_basis += basis
        total_pnl += proceeds - spent + basis
    if min(total_cash, total_reserved, total_basis) < 0:
        errors.append("capital_conservation: negative shared bucket")
    if (
        total_cash + total_reserved + total_basis
        != rational(state["config"]["capital"]) + total_pnl
    ):
        errors.append("capital_conservation: shared account")
    for decision in state["decisions"]:
        if decision["risk"]["allowed"]:
            limits = decision["risk"]["limits"]
            evaluation = decision["evaluation"]
            if rational(decision["reserved_envelope"]) > rational(limits["max_capital"]):
                errors.append("risk_admission: per-trade budget")
            if rational(evaluation["net_edge"]) < rational(limits["min_edge"]):
                errors.append("risk_admission: edge floor")
            if any(b["received_ts_ms"] > decision["ts"] for b in evaluation["books"]):
                errors.append("no_future_observation: future book")
    return errors
