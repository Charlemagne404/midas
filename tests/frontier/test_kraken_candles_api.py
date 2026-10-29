from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from midas.frontier.adapters.kraken import ADAPTER_VERSION, KrakenSpotAdapter, KrakenSpotConfig
from midas.frontier.adapters.transport import HTTPObservation, PublicReadTransport
from midas.frontier.models import CandleSeries, RawObservation, Venue
from midas.frontier.registry import AdapterRegistry
from midas.frontier.storage import FrontierStore

from apps.api.frontier import _validate_kraken_candle_raw_body, router
from tests.frontier.builders import T0

PAIR_ID = "XXBTZUSD"
PAIR_METADATA = {
    "wsname": "XBT/USD",
    "altname": "XBTUSD",
    "base": "XXBT",
    "quote": "ZUSD",
    "pair_decimals": 1,
    "lot_decimals": 8,
    "ordermin": "0.0001",
    "costmin": "0.50",
    "status": "online",
    "tick_size": "0.1",
}
MARKET_BODY = json.dumps({"error": [], "result": {PAIR_ID: PAIR_METADATA}}, separators=(",", ":"))


def _store_saved_pair(adapter: KrakenSpotAdapter, store: FrontierStore) -> str:
    market_response = HTTPObservation(
        url="https://api.kraken.com/0/public/AssetPairs?pair=XBTUSD",
        status_code=200,
        raw_body=MARKET_BODY,
        request_started_at_utc=T0,
        response_received_at_utc=T0 + timedelta(milliseconds=2),
        request_elapsed_monotonic_ns=2_000_000,
        payload=json.loads(MARKET_BODY),
    )
    market = adapter._normalize_pair(PAIR_ID, PAIR_METADATA, market_response)
    raw = RawObservation(
        venue=Venue.KRAKEN,
        observation_kind="instrument_metadata",
        request_url=market_response.url,
        http_status=200,
        request_started_at_utc=market_response.request_started_at_utc,
        received_at_utc=market_response.response_received_at_utc,
        request_elapsed_monotonic_ns=market_response.request_elapsed_monotonic_ns,
        raw_body=MARKET_BODY,
        raw_sha256=hashlib.sha256(MARKET_BODY.encode()).hexdigest(),
        adapter_version=ADAPTER_VERSION,
    )
    return store.append_observation(raw, market)


def _configured_adapter(
    handler,
    *,
    enabled: bool = True,
    hold_reason: str | None = None,
) -> tuple[KrakenSpotAdapter, AdapterRegistry]:
    config = KrakenSpotConfig(
        enabled=enabled,
        live_public_probe_enabled=enabled,
        probe_policy_block_reason=hold_reason,
        requests_per_second=1,
        retries=0,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = PublicReadTransport({"api.kraken.com"}, config, client=client)
    adapter = KrakenSpotAdapter(config, transport=transport)
    return adapter, AdapterRegistry((adapter,))


def test_kraken_candle_capture_is_market_bound_hash_checked_and_listed(tmp_path):
    requests: list[httpx.Request] = []
    since = int(datetime.now(UTC).timestamp()) - 7200
    body = json.dumps(
        {
            "error": [],
            "result": {
                PAIR_ID: [[since + 3600, "60000", "61000", "59000", "60500", "60000", "1.5", 23]],
                "last": since + 7200,
            },
        },
        separators=(",", ":"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=body, request=request)

    adapter, registry = _configured_adapter(handler)
    store = FrontierStore(tmp_path / "frontier.sqlite3")
    market_observation_id = _store_saved_pair(adapter, store)
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        captured = client.post(
            "/api/frontier/probe/kraken/candles",
            json={
                "native_market_id": PAIR_ID,
                "interval_minutes": 60,
                "since_epoch_seconds": since,
            },
        )
        assert captured.status_code == 200, captured.text
        result = captured.json()
        assert result["market_id"]
        assert result["bound_market_observation_id"] == market_observation_id
        assert result["series"]["bound_market_observation_id"] == market_observation_id
        assert result["series"]["requested_since_epoch_seconds"] == since
        assert result["candle_count"] == 1
        assert result["spot_context_only"] is True
        assert result["hypothetical_only"] is True
        assert result["request_count_delta"] == 1
        assert result["network_calls_bounded_by"] == 1
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert requests[0].url.host == "api.kraken.com"
        assert requests[0].url.path == "/0/public/OHLC"
        assert requests[0].url.params["pair"] == PAIR_ID
        assert requests[0].url.params["interval"] == "60"
        assert requests[0].url.params["since"] == str(since)
        assert "authorization" not in requests[0].headers

        saved = store.observation(result["observation_id"])
        assert saved is not None
        assert saved["raw_sha256"] == result["raw_sha256"]
        assert saved["raw"]["observation_kind"] == "historical_candles"
        listed = client.get(
            "/api/frontier/candles",
            params={"venue": "kraken", "native_market_id": PAIR_ID},
        )
        assert listed.status_code == 200, listed.text
        page = listed.json()
        assert page["network_called"] is False
        assert page["returned"] == 1
        assert page["has_more"] is False
        assert page["items"][0]["observation_id"] == result["observation_id"]
        assert page["items"][0]["series"]["candles"][0]["close"] == "60500"

        normalized = page["items"][0]["series"]
        normalized["candles"][0]["close"] = "60600"
        mismatched = CandleSeries.model_validate(normalized)
        raw = RawObservation.model_validate(saved["raw"])
        with pytest.raises(ValueError, match="differ from normalized candles"):
            _validate_kraken_candle_raw_body(raw, mismatched)
        assert len(requests) == 1
    finally:
        client.close()
        asyncio.run(registry.aclose())


def test_kraken_candle_source_hold_and_future_time_fail_before_request(tmp_path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"error": [], "result": {PAIR_ID: []}}, request=request)

    adapter, registry = _configured_adapter(
        handler,
        hold_reason="Kraken source-use review is pending",
    )
    store = FrontierStore(tmp_path / "frontier.sqlite3")
    _store_saved_pair(adapter, store)
    app = FastAPI()
    app.include_router(router(store, registry))
    client = TestClient(app)
    try:
        held = client.post(
            "/api/frontier/probe/kraken/candles",
            json={"native_market_id": PAIR_ID},
        )
        assert held.status_code == 409
        assert held.json()["detail"] == "Kraken source-use review is pending"

        future = client.post(
            "/api/frontier/probe/kraken/candles",
            json={
                "native_market_id": PAIR_ID,
                "since_epoch_seconds": int(datetime.now(UTC).timestamp()) + 3600,
            },
        )
        assert future.status_code == 422
        assert requests == []
    finally:
        client.close()
        asyncio.run(registry.aclose())
