"""Versioned, bounded observation panel. Selection never uses apparent edge.

Random controls are sampled within the explicitly recorded discovery universe,
not claimed to be a uniform sample of the whole venue. Daily price change and
volume are discovery proxies; they are not measured microstructure volatility.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal, DecimalException
from typing import Any

from .discovery import candidate

VERSION = "stratified-observation-v1"
ROLES = ("high", "medium", "thin", "fast", "stable", "near_expiry", "category", "random")


def numeric(value: Any, *, positive: bool = False) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise ValueError("Invalid nonnegative market metadata")
    return result


def timestamp(value: Any) -> int | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expiry timezone missing")
    return int(parsed.timestamp() * 1e9)


def enriched(raw: dict[str, Any]) -> dict[str, Any]:
    market = candidate(raw)
    if raw.get("positionIds") not in (None, []):
        raise ValueError("Ambiguous mixed protocol outcome identifiers")
    if not isinstance(raw.get("negRisk"), bool):
        raise ValueError("Unknown negative-risk semantics")
    if raw.get("negRiskOther") is True:
        raise ValueError("Augmented other outcome excluded")
    if not isinstance(raw.get("feesEnabled"), bool):
        raise ValueError("Unknown fee regime")
    tick = numeric(raw.get("orderPriceMinTickSize"), positive=True)
    minimum = numeric(raw.get("orderMinSize"), positive=True)
    if tick > 1:
        raise ValueError("Invalid tick size")
    fee = raw.get("feeSchedule")
    if raw["feesEnabled"]:
        if not isinstance(fee, dict) or not isinstance(fee.get("takerOnly"), bool):
            raise ValueError("Missing enabled fee schedule")
        numeric(fee.get("rate"))
        numeric(fee.get("exponent"))
    events = raw.get("events", [])
    if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
        raise ValueError("Malformed event identity")
    tags = raw.get("tags", [])
    labels = [str(t.get("label")) for t in tags if isinstance(t, dict) and t.get("label")]
    change = Decimal(str(raw.get("oneDayPriceChange", 0)))
    if not change.is_finite():
        raise ValueError("Invalid price-change proxy")
    return dict(
        market,
        liquidity=str(numeric(raw.get("liquidityNum", raw.get("liquidity", 0)))),
        end_ns=timestamp(raw.get("endDate")),
        event_ids=sorted({str(e["id"]) for e in events if e.get("id") is not None}),
        categories=sorted(set(labels or [raw.get("category") or "unknown"])),
        one_day_price_change=str(change),
        tick_size=str(tick),
        minimum_order_size=str(minimum),
        negative_risk=raw["negRisk"],
        negative_risk_group=raw.get("negRiskMarketID"),
        resolution_source=raw.get("resolutionSource"),
        lifecycle=dict(
            active=raw["active"],
            closed=raw["closed"],
            accepting_orders=raw["acceptingOrders"],
            resolution_status=raw.get("umaResolutionStatus"),
        ),
        fee_regime=dict(
            enabled=raw["feesEnabled"],
            schedule=fee,
            status="discovery_reported_not_execution_verified",
        ),
        payoff=dict(
            pair="same_condition_yes_no_ctf",
            unit="collateral_unit",
            combined_terminal_claim="1",
            currency_conversion_assumed=False,
            limitation="Before fees, redemption costs and settlement assumptions; not a fill.",
        ),
    )


def queries(
    limit: int, now_ns: int, seed: int, near_expiry_tag_id: int = 2
) -> list[tuple[str, dict[str, Any]]]:
    now = datetime.fromtimestamp(now_ns / 1e9, UTC)
    common = dict(active="true", closed="false", limit=limit, include_tag="true")
    return [
        ("high", dict(common, order="liquidityNum", ascending="false", liquidity_num_min=10000)),
        (
            "medium",
            dict(
                common,
                order="id",
                ascending="true",
                liquidity_num_min=1000,
                liquidity_num_max=10000,
            ),
        ),
        (
            "thin",
            dict(common, order="id", ascending="true", liquidity_num_min=1, liquidity_num_max=1000),
        ),
        (
            "near_expiry",
            dict(
                common,
                order="endDate",
                ascending="true",
                end_date_min=now.isoformat(),
                end_date_max=(now + timedelta(days=7)).isoformat(),
            ),
        ),
        (
            "near_expiry_tag",
            dict(
                common,
                order="endDate",
                ascending="true",
                tag_id=near_expiry_tag_id,
                end_date_min=now.isoformat(),
                end_date_max=(now + timedelta(days=7)).isoformat(),
            ),
        ),
        (
            "control",
            dict(
                common,
                order="id",
                ascending="true",
                offset=(seed + now_ns // 86_400_000_000_000) % 1000,
            ),
        ),
    ]


def select_panel(
    raw: list[dict[str, Any]],
    limit: int,
    *,
    now_ns: int,
    seed: int,
    update_rates: dict[str, float] | None = None,
    roles: tuple[str, ...] = ROLES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not 1 <= limit <= 10 or not roles or any(role not in ROLES for role in roles):
        raise ValueError("Invalid bounded panel roles")
    eligible: dict[str, dict[str, Any]] = {}
    decisions = []
    rates = update_rates or {}
    for index, market in enumerate(raw):
        try:
            item = enriched(market)
            if item["id"] in eligible:
                decisions.append(
                    dict(
                        index=index,
                        id=item["id"],
                        eligible=False,
                        reason="duplicate_market_response",
                    )
                )
                continue
            eligible[item["id"]] = item
            decisions.append(
                dict(
                    index=index, id=item["id"], eligible=True, selected=False, reason="not_selected"
                )
            )
        except (ValueError, TypeError, KeyError, DecimalException, OverflowError) as error:
            decisions.append(
                dict(index=index, id=market.get("id"), eligible=False, reason=str(error))
            )
    chosen: list[dict[str, Any]] = []
    tokens: set[str] = set()
    categories: set[str] = set()
    unfilled = []

    def random_key(item: dict[str, Any]) -> str:
        return hashlib.sha256(f"{VERSION}:{seed}:{item['id']}".encode()).hexdigest()

    for slot in range(limit):
        role = roles[slot % len(roles)]
        available = [m for m in eligible.values() if not tokens.intersection(m["tokens"])]
        if role in {"high", "medium", "thin"}:
            available = [
                m
                for m in available
                if (
                    Decimal(m["liquidity"]) >= 10000
                    if role == "high"
                    else 1000 <= Decimal(m["liquidity"]) < 10000
                    if role == "medium"
                    else 0 < Decimal(m["liquidity"]) < 1000
                )
            ]
        elif role == "near_expiry":
            available = [
                m
                for m in available
                if m["end_ns"] is not None and now_ns < m["end_ns"] <= now_ns + 7 * 86400 * 10**9
            ]
        elif role == "category":
            available = [m for m in available if set(m["categories"]) - categories]
        if not available:
            unfilled.append(role)
            continue
        activity_basis = "reported_daily_price_change_proxy"
        if role in {"fast", "stable"}:
            measured = [m for m in available if m["id"] in rates]
            if len(measured) >= 2:
                available = measured
                activity_basis = "prior_observed_book_updates_per_second"

        def key(
            m: dict[str, Any], role: str = role, activity_basis: str = activity_basis
        ) -> tuple[Decimal, str]:
            value = Decimal(0)
            if role == "high":
                value = -Decimal(m["liquidity"])
            elif role in {"fast", "stable"}:
                value = (
                    Decimal(str(rates[m["id"]]))
                    if activity_basis.startswith("prior")
                    else abs(Decimal(m["one_day_price_change"]))
                )
                value *= -1 if role == "fast" else 1
            elif role == "near_expiry":
                value = Decimal(m["end_ns"])
            return value, random_key(m)

        item = min(available, key=key)
        item = dict(
            item,
            selection_role=role,
            activity_selection_basis=activity_basis if role in {"fast", "stable"} else None,
            prior_observed_updates_per_second=rates.get(item["id"]),
        )
        chosen.append(item)
        tokens.update(item["tokens"])
        categories.update(item["categories"])
        for decision in decisions:
            if decision.get("eligible") and decision["id"] == item["id"]:
                decision.update(selected=True, reason=role)
    return chosen, dict(
        version=VERSION,
        seed=seed,
        roles=list(roles),
        candidate_responses=len(raw),
        distinct_eligible=len(eligible),
        decisions=decisions,
        unfilled_roles=unfilled,
        update_rates_observed_before_selection=rates,
        limitations=[
            "Bounded query universe, not entire venue or uniform global random sample.",
            "Activity roles use prior observed rates when at least two candidates have coverage, otherwise a daily change proxy.",
            "No opportunity/edge filter is used. Unavailable strata remain unfilled.",
        ],
    )
