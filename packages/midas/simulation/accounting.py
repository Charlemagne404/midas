"""Independent ledger audit: rebuild balances and inventory from journal facts."""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from midas.simulation.exchange import Exchange

D = Decimal


def reconcile(exchange: Exchange) -> list[str]:
    p = exchange.portfolio
    errors = []
    cash, reserved, basis, fees, proceeds, pnl = p.starting, D(0), D(0), D(0), D(0), D(0)
    inventory: dict[str, Decimal] = {}
    ids = set()
    for e in p.ledger:
        if e.id in ids:
            errors.append(f"Duplicate journal event {e.id}")
        ids.add(e.id)
        cash += e.available_delta
        reserved += e.reserved_delta
        basis += e.locked_delta
        if min(cash, reserved, basis) < 0:
            errors.append(f"Negative collateral at {e.id}")
        if e.kind in {"reserve", "release"} and e.available_delta + e.reserved_delta != 0:
            errors.append(f"Reservation does not conserve cash at {e.id}")
        if e.kind == "fill":
            assert e.asset_id is not None
            expected_fee = (
                e.quantity * exchange.market.fee.rate * e.price * (1 - e.price)
            ).quantize(D("0.00001"), rounding=ROUND_HALF_UP)
            expected_charge = (e.quantity * e.price).quantize(
                D("0.000001"), rounding=ROUND_CEILING
            ) + expected_fee
            if (
                e.locked_delta != expected_charge
                or e.reserved_delta != -expected_charge
                or e.fee != expected_fee
                or e.available_delta != 0
            ):
                errors.append(f"Fill arithmetic mismatch at {e.id}")
            inventory[e.asset_id] = inventory.get(e.asset_id, D(0)) + e.quantity
            fees += e.fee
        if e.kind == "settlement":
            assert e.asset_id is not None
            expected_proceeds = (
                (
                    D(int(e.quantity * 1_000_000) * e.payout_numerator // e.payout_denominator)
                    / 1_000_000
                )
                if e.payout_denominator
                else e.quantity * e.price
            )
            if e.available_delta != expected_proceeds:
                errors.append(f"Settlement arithmetic mismatch at {e.id}")
            inventory[e.asset_id] = inventory.get(e.asset_id, D(0)) - e.quantity
            proceeds += e.available_delta
            pnl += e.available_delta + e.locked_delta
        if any(q < 0 for q in inventory.values()):
            errors.append(f"Negative inventory at {e.id}")
    expected = (cash, reserved, basis, fees, proceeds, pnl)
    actual = (p.available, p.reserved, p.locked, p.fees, p.proceeds, p.realized_pnl)
    if expected != actual:
        errors.append("Portfolio differs from independently reconstructed journal")
    if {a: q for a, q in inventory.items() if q} != {a: q for a, q in p.positions.items() if q}:
        errors.append("Inventory differs from journal")
    total_spend = sum((e.locked_delta for e in p.ledger if e.kind == "fill"), D(0))
    if cash + reserved != p.starting - total_spend + proceeds:
        errors.append("Collateral conservation failed")
    if sum((o.reservation for o in exchange.orders.values()), D(0)) != reserved:
        errors.append("Open-order reservations do not reconcile")
    for o in exchange.orders.values():
        filled = sum(
            (e.quantity for e in p.ledger if e.kind == "fill" and e.order_id == o.id), D(0)
        )
        if filled + o.remaining != o.quantity:
            errors.append(f"Order quantity conservation failed: {o.id}")
    return errors
