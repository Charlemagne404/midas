"""Public GET discovery; explicit protocol-specific identifier mapping."""

import json
import re
from decimal import Decimal
from typing import Any

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def array(value: Any) -> list[Any]:
    value = json.loads(value) if isinstance(value, str) else value
    if not isinstance(value, list):
        raise ValueError("Expected outcome array")
    return value


def candidate(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("version") != "v1":
        raise ValueError("Unsupported market protocol; V2 position IDs are not CTF token IDs")
    if not all(
        raw.get(k) is v
        for k, v in [
            ("active", True),
            ("closed", False),
            ("enableOrderBook", True),
            ("acceptingOrders", True),
        ]
    ):
        raise ValueError("Inactive or unavailable order book")
    condition = raw.get("conditionId", "")
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", condition):
        raise ValueError("Invalid condition identifier")
    ids, outcomes = array(raw.get("clobTokenIds")), array(raw.get("outcomes"))
    if len(ids) != 2 or len(outcomes) != 2 or len(set(ids)) != 2 or len(set(outcomes)) != 2:
        raise ValueError("Invalid outcome relationship")
    if any(not isinstance(x, str) or not x.isdecimal() or int(x) <= 0 for x in ids):
        raise ValueError("Invalid CTF token identifier")
    volume = Decimal(str(raw.get("volume24hr", 0)))
    if not volume.is_finite() or volume < 0:
        raise ValueError("Invalid volume")
    return dict(
        id=str(raw["id"]),
        condition=condition,
        protocol="v1",
        tokens=dict(zip(ids, outcomes, strict=True)),
        question=raw["question"],
        volume24hr=str(volume),
    )


def select(
    raw: list[dict[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates, rejected = [], []
    tokens: set[str] = set()
    for market in raw:
        try:
            candidates.append(candidate(market))
        except (ValueError, TypeError, KeyError) as e:
            rejected.append(dict(id=market.get("id"), reason=str(e)))
    chosen = []
    for market in sorted(candidates, key=lambda m: (-Decimal(m["volume24hr"]), m["id"])):
        if set(market["tokens"]) & tokens:
            rejected.append(dict(id=market["id"], reason="Duplicate token mapping"))
            continue
        chosen.append(market)
        tokens.update(market["tokens"])
        if len(chosen) == limit:
            break
    return chosen, rejected
