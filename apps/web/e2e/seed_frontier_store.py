"""Seed an isolated Playwright Frontier store with deterministic price history."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from midas.frontier.historical_replay import (
    PriceHistoryReplayInput,
    deterministic_price_history_replay,
)
from midas.frontier.models import (
    HistoricalPricePoint,
    PriceHistorySeries,
    Provenance,
    RawObservation,
    Venue,
)
from midas.frontier.storage import FrontierStore

CAPTURE_COUNT = 21
BASE_RECEIVED_AT = datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
CODE_VERSION = "frontier-seeded-browser-fixture-v1"


def seed_store(root: Path) -> None:
    store = FrontierStore(root, max_bytes=8 * 1024 * 1024)
    if store.path.exists():
        raise RuntimeError(f"Refusing to seed an existing Frontier store: {store.path}")
    store.initialize()

    for index in range(CAPTURE_COUNT):
        received_at = BASE_RECEIVED_AT + timedelta(seconds=index)
        request_started_at = received_at - timedelta(seconds=2)
        requested_end_ts = int(received_at.timestamp())
        requested_start_ts = requested_end_ts - 7 * 24 * 60 * 60
        point_ts = requested_end_ts - 60 * 60
        native_instrument_id = f"frontier-e2e-token-{index:02d}"
        raw_body = json.dumps(
            {
                "fixture_only": True,
                "index": index,
                "history": [{"t": point_ts, "p": f"0.{40 + index % 10}"}],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        raw_sha256 = hashlib.sha256(raw_body.encode("utf-8")).hexdigest()
        request_url = f"https://clob.polymarket.com/prices-history?market={native_instrument_id}"
        raw = RawObservation(
            venue=Venue.POLYMARKET,
            observation_kind="historical_price_points",
            request_url=request_url,
            http_status=200,
            request_started_at_utc=request_started_at,
            received_at_utc=received_at,
            raw_body=raw_body,
            raw_sha256=raw_sha256,
            adapter_version=CODE_VERSION,
        )
        observation_id = hashlib.sha256(
            "|".join(
                (
                    raw.venue.value,
                    raw.observation_kind,
                    raw.request_url,
                    raw.raw_sha256,
                    raw.request_started_at_utc.isoformat(),
                    raw.received_at_utc.isoformat(),
                )
            ).encode("utf-8")
        ).hexdigest()
        series = PriceHistorySeries(
            venue=Venue.POLYMARKET,
            native_instrument_id=native_instrument_id,
            interval="1d",
            fidelity_minutes=60,
            requested_start_ts=requested_start_ts,
            requested_end_ts=requested_end_ts,
            bound_market_observation_id=None,
            points=(
                HistoricalPricePoint(
                    timestamp_utc=datetime.fromtimestamp(point_ts, UTC),
                    price=f"0.{40 + index % 10}",
                ),
            ),
            source_limit_note="Deterministic browser fixture only; not source validation.",
            provenance=Provenance(
                source_url=request_url,
                adapter_version=CODE_VERSION,
                source_schema_version="fixture-v1",
                request_started_at_utc=request_started_at,
                response_received_at_utc=received_at,
                processed_at_utc=received_at + timedelta(milliseconds=1),
                raw_sha256=raw_sha256,
                observation_id=observation_id,
            ),
        )
        store.append_observation(raw, series)
        replay_input = PriceHistoryReplayInput(
            observation_id=observation_id,
            venue=Venue.POLYMARKET,
            raw_sha256=raw_sha256,
            received_at_utc=received_at,
            series=series,
        )
        result = deterministic_price_history_replay((replay_input,), code_version=CODE_VERSION)
        store.append_price_history_replay(result)

    print(f"Seeded {CAPTURE_COUNT} fixture captures and replay artifacts in {store.path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: seed_frontier_store.py FRONTIER_ROOT")
    seed_store(Path(sys.argv[1]))
