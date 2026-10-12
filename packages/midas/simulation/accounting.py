"""Independent ledger audit: rebuild balances and inventory from journal facts."""

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from midas.simulation.exchange import Exchange, SellOrder

D = Decimal


def reconcile(exchange: Exchange) -> list[str]:
    p = exchange.portfolio
    errors = []
    cash, reserved, basis, fees, proceeds, pnl = p.starting, D(0), D(0), D(0), D(0), D(0)
    inventory: dict[str, Decimal] = {}
    asset_basis: dict[str, Decimal] = {}
    sale_proceeds = D(0)
    reserved_shares: dict[str, Decimal] = {}
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
            asset_basis[e.asset_id] = asset_basis.get(e.asset_id, D(0)) + expected_charge
            fees += e.fee
        if e.kind in {"reserve_sell", "release_sell"}:
            assert e.asset_id is not None
            order_id = e.order_id or ""
            order = exchange.orders.get(order_id)
            if not isinstance(order, SellOrder) or order.asset_id != e.asset_id:
                errors.append(f"Share reservation has invalid sell order at {e.id}")
            if e.quantity <= 0 or any((e.available_delta, e.reserved_delta, e.locked_delta, e.fee)):
                errors.append(f"Share reservation arithmetic mismatch at {e.id}")
            reserved_shares[order_id] = reserved_shares.get(order_id, D(0)) + (
                e.quantity if e.kind == "reserve_sell" else -e.quantity
            )
        if e.kind == "sell_fill":
            assert e.asset_id is not None
            order = exchange.orders.get(e.order_id or "")
            if not isinstance(order, SellOrder) or order.asset_id != e.asset_id:
                errors.append(f"Sell fill has invalid order at {e.id}")
            owned = inventory.get(e.asset_id, D(0))
            cost = asset_basis.get(e.asset_id, D(0))
            if owned <= 0 or not D(0) < e.quantity <= owned:
                errors.append(f"Sell quantity exceeds inventory at {e.id}")
                released = D(0)
            else:
                released = (
                    cost
                    if e.quantity == owned
                    else (cost * e.quantity / owned).quantize(D(".000001"), rounding=ROUND_FLOOR)
                )
            expected_fee = (
                e.quantity * exchange.market.fee.rate * e.price * (1 - e.price)
            ).quantize(D(".00001"), rounding=ROUND_HALF_UP)
            expected_net = (e.quantity * e.price).quantize(
                D(".000001"), rounding=ROUND_FLOOR
            ) - expected_fee
            if (
                expected_net < 0
                or e.available_delta != expected_net
                or e.reserved_delta != 0
                or e.locked_delta != -released
                or e.fee != expected_fee
            ):
                errors.append(f"Sell arithmetic mismatch at {e.id}")
            inventory[e.asset_id] = owned - e.quantity
            asset_basis[e.asset_id] = cost - released
            reserved_shares[e.order_id or ""] = (
                reserved_shares.get(e.order_id or "", D(0)) - e.quantity
            )
            fees += expected_fee
            sale_proceeds += expected_net
            pnl += expected_net - released
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
            if exchange.sales_enabled and e.locked_delta != -asset_basis.get(e.asset_id, D(0)):
                errors.append(f"Settlement remaining basis mismatch at {e.id}")
            asset_basis[e.asset_id] = D(0)
            proceeds += e.available_delta
            pnl += e.available_delta + e.locked_delta
        if any(q < 0 for q in inventory.values()):
            errors.append(f"Negative inventory at {e.id}")
        if any(q < 0 for q in reserved_shares.values()):
            errors.append(f"Negative share reservation at {e.id}")
        for asset, owned in inventory.items():
            held = sum(
                (
                    q
                    for key, q in reserved_shares.items()
                    if key in exchange.orders and exchange.orders[key].asset_id == asset
                ),
                D(0),
            )
            if held > owned:
                errors.append(f"Share reservations exceed inventory at {e.id}")
    expected = (cash, reserved, basis, fees, proceeds, pnl)
    actual = (p.available, p.reserved, p.locked, p.fees, p.proceeds, p.realized_pnl)
    if expected != actual:
        errors.append("Portfolio differs from independently reconstructed journal")
    if {a: q for a, q in inventory.items() if q} != {a: q for a, q in p.positions.items() if q}:
        errors.append("Inventory differs from journal")
    total_spend = sum((e.locked_delta for e in p.ledger if e.kind == "fill"), D(0))
    if cash + reserved != p.starting - total_spend + sale_proceeds + proceeds:
        errors.append("Collateral conservation failed")
    if sale_proceeds != p.sale_proceeds:
        errors.append("Sale proceeds differ from independent ledger")
    if exchange.sales_enabled and any(
        exchange.asset_costs.get(a, D(0)) != cost for a, cost in asset_basis.items()
    ):
        errors.append("Remaining asset basis differs from independent ledger")
    if sum((o.reservation for o in exchange.orders.values()), D(0)) != reserved:
        errors.append("Open-order reservations do not reconcile")
    for o in exchange.orders.values():
        if isinstance(o, SellOrder) and reserved_shares.get(o.id, D(0)) != o.inventory_reservation:
            errors.append(f"Share reservation differs from order: {o.id}")
        filled = sum(
            (
                e.quantity
                for e in p.ledger
                if e.kind == ("sell_fill" if isinstance(o, SellOrder) else "fill")
                and e.order_id == o.id
            ),
            D(0),
        )
        if filled + o.remaining != o.quantity:
            errors.append(f"Order quantity conservation failed: {o.id}")
    return errors
