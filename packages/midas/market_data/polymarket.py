"""Public GET-only transport and strict version-aware normalization."""

import asyncio
import json
import re
import time
from decimal import Decimal
from typing import Any

import httpx

from midas.core.models import Book, Fee, Instrument, Level, Market, Source

D = Decimal
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com"
WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def array(value: Any) -> list[Any]:
    decoded = json.loads(value) if isinstance(value, str) else value
    if not isinstance(decoded, list):
        raise ValueError("Expected an array")
    return decoded


def normalize_market(raw: dict[str, Any]) -> Market:
    version = raw.get("version", "unknown")
    labels = array(raw.get("outcomes", []))
    ids = array(
        raw.get("positionIds", [])
        if version == "v2"
        else raw.get("clobTokenIds", [])
        if version == "v1"
        else []
    )
    instruments: tuple[Instrument, ...] = ()
    if version in {"v1", "v2"}:
        if len(ids) != len(labels) or any(not isinstance(i, str) or not i.isdecimal() for i in ids):
            raise ValueError("Missing or malformed protocol-specific outcome IDs")
        instruments = tuple(
            Instrument(asset_id=i, label=str(label)) for i, label in zip(ids, labels, strict=True)
        )
    fee = Fee()
    schedule = raw.get("feeSchedule")
    if raw.get("feesEnabled") is False:
        fee = Fee(verified=True, evidence="Gamma feesEnabled explicitly false")
    elif raw.get("feesEnabled") is True and isinstance(schedule, dict):
        if (
            schedule.get("exponent") == 1
            and not isinstance(schedule.get("exponent"), bool)
            and schedule.get("takerOnly") is True
            and "rate" in schedule
        ):
            fee = Fee(
                rate=D(str(schedule["rate"])),
                exponent=1,
                verified=True,
                evidence="Gamma feeSchedule, exponent 1; public Fees formula, verified 2026-10-11",
            )
    if fee.verified:
        ts = now_ms()
        fee = fee.model_copy(update={"verified_ts_ms": ts, "expires_ts_ms": ts + 300_000})
    events = raw.get("events") or []
    event_id = str(events[0]["id"]) if events and "id" in events[0] else f"market:{raw['id']}"
    return Market(
        id=str(raw["id"]),
        event_id=event_id,
        question=str(raw["question"]),
        condition_id=str(raw.get("conditionId") or ""),
        protocol=str(version),
        instruments=instruments,
        source=Source.LIVE,
        active=raw.get("active") is True,
        closed=raw.get("closed") is not False,
        accepting_orders=raw.get("acceptingOrders") is True,
        negative_risk=raw.get("negRisk") is not False,
        augmented_negative_risk=raw.get("negRiskAugmented") is True
        or any(e.get("negRiskAugmented") for e in events),
        complementary_verified=len(instruments) == 2
        and labels == ["Yes", "No"]
        and bool(raw.get("conditionId")),
        # Gamma maps outcome IDs, but does not prove onchain redemption economics
        # for this specific condition. No positive live classification without attestation.
        payout_verified=False,
        payout_evidence="Awaiting deployed CTF structural verification",
        fee=fee,
        description=str(raw.get("description") or ""),
        execution_delay_ms=raw["secondsDelay"] * 1000
        if isinstance(raw.get("secondsDelay"), int)
        and not isinstance(raw.get("secondsDelay"), bool)
        and raw["secondsDelay"] >= 0
        else None,
        resolution_source=str(raw.get("resolutionSource") or ""),
        resolution_metadata={
            k: raw.get(k)
            for k in (
                "questionID",
                "resolutionStatus",
                "umaResolutionStatus",
                "umaResolutionStatuses",
            )
        },
    )


def normalize_book(
    raw: dict[str, Any],
    source: Source,
    received: int,
    expected_asset: str | None = None,
    expected_condition: str | None = None,
) -> Book:
    asset = str(raw["asset_id"])
    condition = str(raw["market"])
    if expected_asset is not None and asset != expected_asset:
        raise ValueError("Snapshot asset ID mismatch")
    if expected_condition is not None and condition != expected_condition:
        raise ValueError("Snapshot condition ID mismatch")
    return Book(
        asset_id=asset,
        condition_id=condition,
        asks=tuple(Level.model_validate(x) for x in raw["asks"]),
        bids=tuple(Level.model_validate(x) for x in raw["bids"]),
        tick_size=D(str(raw["tick_size"])),
        min_order_size=D(str(raw["min_order_size"])),
        exchange_ts_ms=int(raw["timestamp"]) if raw.get("timestamp") else None,
        received_ts_ms=received,
        source=source,
        hash=raw.get("hash"),
        minimum_unit="notional" if source == Source.LIVE else "shares",
    )


class PublicClient:
    """Every reachable REST operation is an allowlisted public GET.

    At most 5 requests/sec total, single pacing lock, bounded retries and timeouts.
    No SDK secure client, credentials, POST, DELETE, wallet, or orders route exists.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.client = httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "midas-readonly/0.1"},
            transport=transport,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
        self.lock = asyncio.Lock()
        self.last_request = 0.0

    async def get(self, base: str, path: str, params: dict[str, Any] | None = None) -> Any:
        parsed, _ = await self.get_wire(base, path, params)
        return parsed

    async def get_wire(
        self, base: str, path: str, params: dict[str, Any] | None = None
    ) -> tuple[Any, str]:
        details_read = (
            base == CLOB and re.fullmatch(r"/clob-markets/0x[0-9a-fA-F]{64}", path) is not None
        )
        if not details_read and (base, path) not in {
            (GAMMA, "/markets"),
            (GAMMA, "/events"),
            (CLOB, "/book"),
            (DATA, "/v2/status"),
        }:
            raise ValueError("Endpoint is outside the public read allowlist")
        for attempt in range(3):
            async with self.lock:
                await asyncio.sleep(max(0, 0.2 - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
            response = await self.client.get(base + path, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    try:
                        delay = float(response.headers.get("Retry-After", 2**attempt))
                    except ValueError:
                        delay = float(2**attempt)
                    await asyncio.sleep(min(10, max(0.2, delay)))
                    continue
            response.raise_for_status()
            # Avoid float conversion of source monetary JSON literals.
            return json.loads(response.text, parse_float=D), response.text
        raise RuntimeError("Retry budget exhausted")

    async def discover(self, limit: int = 20) -> list[dict[str, Any]]:
        result, _ = await self.discover_wire(limit)
        return result

    async def discover_wire(self, limit: int = 20) -> tuple[list[dict[str, Any]], str]:
        result, wire = await self.get_wire(
            GAMMA,
            "/markets",
            {
                "active": "true",
                "closed": "false",
                "limit": limit,
                "order": "liquidity",
                "ascending": "false",
            },
        )
        if not isinstance(result, list):
            raise ValueError("Unexpected Gamma discovery envelope")
        return result, wire

    async def book(self, asset_id: str, condition_id: str) -> tuple[Book, dict[str, Any], str]:
        raw, wire = await self.get_wire(CLOB, "/book", {"token_id": asset_id})
        return normalize_book(raw, Source.LIVE, now_ms(), asset_id, condition_id), raw, wire

    async def enrich(self, market: Market) -> tuple[Market, dict[str, Any]]:
        raw = await self.get(CLOB, f"/clob-markets/{market.condition_id}")
        if (
            raw.get("c") != market.condition_id
            or raw.get("v") != market.protocol
            or tuple(x.get("t") for x in raw.get("t", []))
            != tuple(i.asset_id for i in market.instruments)
            or raw.get("ao") is not True
        ):
            raise ValueError("CLOB/Gamma market identity, version or trading state contradiction")
        fee = raw.get("fd")
        if (
            not isinstance(fee, dict)
            or "r" not in fee
            or fee.get("e") != 1
            or fee.get("to") is not True
        ):
            raise ValueError("Missing supported CLOB fee parameters")
        if not market.fee.verified or D(str(fee["r"])) != market.fee.rate:
            raise ValueError("CLOB/Gamma fee contradiction")
        delay = market.execution_delay_ms
        if delay is None:
            raise ValueError("Missing or invalid market delay")
        return market.model_copy(
            update={"execution_delay_ms": delay + (250 if raw.get("itode") is True else 0)}
        ), raw

    async def close(self) -> None:
        await self.client.aclose()
