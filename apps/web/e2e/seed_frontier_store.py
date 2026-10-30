"""Seed an isolated Playwright Frontier store with deterministic price history."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
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
ARENA_JOB_ID = "job-e2e0123456789abcdef01234"


def seed_store(root: Path) -> None:
    if root.is_symlink():
        raise RuntimeError("Refusing to seed a symlinked Frontier root")
    browser_root = root.parent.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if browser_root.parent != temporary_root or not browser_root.name.startswith("midas-browser-"):
        raise RuntimeError("Frontier E2E fixtures require a fresh isolated temporary browser root")
    store = FrontierStore(root, max_bytes=8 * 1024 * 1024)
    if store.path.exists():
        raise RuntimeError(f"Refusing to seed an existing Frontier store: {store.path}")
    arena_root = browser_root / "arena"
    if arena_root.exists() or arena_root.is_symlink():
        raise RuntimeError(f"Refusing to seed an existing Arena root: {arena_root}")
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
        request_url = (
            "https://clob.polymarket.com/prices-history"
            f"?market={native_instrument_id}&interval=1d&fidelity=60"
            f"&startTs={requested_start_ts}&endTs={requested_end_ts}"
        )
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
                source_schema_version="CLOB GET /prices-history",
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

    seed_arena_discovery(arena_root)
    print(
        f"Seeded {CAPTURE_COUNT} fixture captures and replay artifacts in {store.path}; "
        f"seeded one fixture-only Arena discovery job in {arena_root}"
    )


def seed_arena_discovery(root: Path) -> None:
    """Create one completed, hash-verified discovery artifact without a worker or source call."""
    repository = Path(__file__).resolve().parents[3]
    if str(repository) not in sys.path:
        sys.path.insert(0, str(repository))

    from midas.arena.artifacts import atomic_json
    from midas.arena.frontier_discovery import (
        FrontierDiscoveryJobSpec,
        execute_frontier_discovery_job,
        make_snapshot,
        store_snapshot,
    )
    from midas.arena.jobs import JobSpec
    from midas.frontier.economics import ExecutionScenario
    from midas.frontier.models import Venue

    from tests.frontier.builders import T0, book, market

    fixture_market = market(Venue.POLYMARKET, "seeded-browser-study")
    snapshot = make_snapshot(
        code_version="frontier-seeded-arena-browser-fixture-v1",
        as_of_utc=T0,
        relationship_limit=500,
        scenario=ExecutionScenario(name="seeded browser fixture"),
        markets=(fixture_market,),
        books=(
            book(fixture_market, fixture_market.instruments[0].native_instrument_id, "0.40"),
            book(fixture_market, fixture_market.instruments[1].native_instrument_id, "0.65"),
        ),
        verified_relationships=(),
    )
    snapshot_sha256 = store_snapshot(root, snapshot)
    discovery_spec = FrontierDiscoveryJobSpec(
        snapshot_id=snapshot.snapshot_id,
        snapshot_sha256=snapshot_sha256,
    )
    configuration = JobSpec(
        kind="frontier_discovery",
        frontier_discovery=discovery_spec,
        max_wall_seconds=300,
        memory_limit_mb=512,
        cpu_quota_percent=50,
        nice=15,
        io_scheduling_class="idle",
    )
    job_directory = root / "jobs" / ARENA_JOB_ID
    job_directory.mkdir(parents=True)

    class SeedProgress:
        def phase(self, value: str) -> None:
            del value

        def __call__(self, current: int, total: int) -> None:
            del current, total

    progress = SeedProgress()
    artifact = execute_frontier_discovery_job(root, ARENA_JOB_ID, discovery_spec, progress)
    atomic_json(
        job_directory / "job.json",
        {
            "job_id": ARENA_JOB_ID,
            "configuration": configuration.model_dump(mode="json"),
            "state": "COMPLETED",
            "exit_status": 0,
            "created_at": T0.timestamp(),
            "updated_at": T0.timestamp() + 1,
            "elapsed_seconds": 0.0,
            "progress": {"done": 3, "total": 3},
            "phase": "complete",
            "error": None,
            "result": {
                "frontier_discovery_sha256": artifact.result_sha256,
                "comparison_id": artifact.comparison.comparison_id,
                "snapshot_id": artifact.snapshot_id,
                "artifact": "frontier-discovery-result.json",
            },
        },
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: seed_frontier_store.py FRONTIER_ROOT")
    seed_store(Path(sys.argv[1]))
