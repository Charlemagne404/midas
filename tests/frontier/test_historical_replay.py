from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from midas.frontier.historical_replay import (
    MAX_PRICE_HISTORY_REPLAY_SERIES,
    PriceHistoryReplayInput,
    deterministic_price_history_replay,
)
from midas.frontier.models import HistoricalPricePoint, PriceHistorySeries, Venue
from midas.frontier.storage import FrontierStore, FrontierStoreError
from pydantic import ValidationError

from tests.frontier.builders import T0, market


def _evidence(index: int, prices: tuple[str, ...] = ("0.25", "0.55", "0.90")):
    observation_id = f"{index:064x}"
    raw_sha256 = hashlib.sha256(f"history-raw-{index}".encode()).hexdigest()
    source_market = market(Venue.POLYMARKET, f"history-{index}")
    received_at = T0 + timedelta(seconds=1900 + index)
    provenance = source_market.provenance.model_copy(
        update={
            "request_started_at_utc": T0 - timedelta(seconds=1),
            "response_received_at_utc": received_at,
            "processed_at_utc": received_at + timedelta(milliseconds=1),
            "raw_sha256": raw_sha256,
            "observation_id": hashlib.sha256(f"normalized-{index}".encode()).hexdigest(),
        }
    )
    start_ts = int(T0.timestamp())
    points = tuple(
        HistoricalPricePoint(
            timestamp_utc=T0 + timedelta(seconds=offset),
            price=Decimal(price),
        )
        for offset, price in zip((100, 500, 1800), prices, strict=True)
    )
    series = PriceHistorySeries(
        venue=Venue.POLYMARKET,
        native_instrument_id=f"{10_000 + index}",
        interval="1d",
        fidelity_minutes=60,
        requested_start_ts=start_ts,
        requested_end_ts=start_ts + 3600,
        bound_market_observation_id="f" * 64,
        points=points,
        source_limit_note="Observed source point samples only.",
        provenance=provenance,
    )
    return PriceHistoryReplayInput(
        observation_id=observation_id,
        venue=Venue.POLYMARKET,
        raw_sha256=raw_sha256,
        received_at_utc=received_at,
        series=series,
    )


def test_price_history_replay_is_order_independent_and_descriptive_only():
    first = _evidence(1)
    second = _evidence(2, ("0.10", "0.40", "0.70"))

    forward = deterministic_price_history_replay(
        (first, second), code_version="frontier-test-history-v1"
    )
    reverse = deterministic_price_history_replay(
        (second, first), code_version="frontier-test-history-v1"
    )

    assert forward == reverse
    assert forward.run_id == reverse.run_id
    assert forward.result_sha256 == reverse.result_sha256
    assert forward.candidate_generation == "not_performed"
    assert forward.manifest.observation_ids == tuple(
        sorted((first.observation_id, second.observation_id))
    )
    assert forward.series[0].point_count == 3
    assert forward.series[0].observed_point_span_seconds == 1700
    assert forward.series[0].largest_adjacent_sample_gap_seconds == 1300
    assert forward.series[0].minimum_sampled_price == Decimal("0.25")
    assert forward.series[0].maximum_sampled_price == Decimal("0.90")
    assert all(item.future_point_timestamp_count == 0 for item in forward.series)


def test_price_history_replay_rejects_capture_mismatch_duplicate_and_unbounded_inputs():
    first = _evidence(1)
    with pytest.raises(ValidationError, match="does not match its capture"):
        PriceHistoryReplayInput.model_validate(
            {
                **first.model_dump(mode="python"),
                "raw_sha256": "0" * 64,
            }
        )
    with pytest.raises(ValueError, match="duplicate observation"):
        deterministic_price_history_replay((first, first), code_version="frontier-test-history-v1")
    too_many = tuple(_evidence(index) for index in range(1, MAX_PRICE_HISTORY_REPLAY_SERIES + 2))
    with pytest.raises(ValueError, match="requires 1..8 captures"):
        deterministic_price_history_replay(too_many, code_version="frontier-test-history-v1")


def test_price_history_replay_revalidates_reconstructed_nested_timestamps():
    evidence = _evidence(4)
    first_point = evidence.series.points[0]
    naive_point = first_point.model_copy(update={"timestamp_utc": datetime(2026, 10, 26, 20, 0)})
    naive_series = evidence.series.model_copy(
        update={"points": (naive_point, *evidence.series.points[1:])}
    )
    reconstructed = evidence.model_copy(update={"series": naive_series})

    with pytest.raises(ValidationError, match="Price-history time must include a timezone"):
        deterministic_price_history_replay(
            (reconstructed,), code_version="frontier-test-history-v2"
        )


def test_price_history_series_revalidates_nested_point_models():
    evidence = _evidence(5)
    series_payload = evidence.series.model_dump(mode="python")
    naive_point = evidence.series.points[0].model_copy(
        update={"timestamp_utc": datetime(2026, 10, 26, 20, 0)}
    )

    with pytest.raises(ValidationError, match="Price-history time must include a timezone"):
        PriceHistorySeries.model_validate(
            {**series_payload, "points": (naive_point, *evidence.series.points[1:])}
        )

    out_of_range_point = evidence.series.points[0].model_copy(update={"price": Decimal("1.1")})
    with pytest.raises(ValidationError):
        PriceHistorySeries.model_validate(
            {**series_payload, "points": (out_of_range_point, *evidence.series.points[1:])}
        )


def test_price_history_replay_store_is_append_only_and_hash_checked(tmp_path):
    evidence = _evidence(3)
    result = deterministic_price_history_replay(
        (evidence,), code_version="frontier-test-history-storage-v1"
    )
    store = FrontierStore(tmp_path / "evidence", max_bytes=2 * 1024 * 1024)

    assert store.append_price_history_replay(result) == result.run_id
    assert store.append_price_history_replay(result) == result.run_id
    loaded = store.price_history_replay(result.run_id)
    assert loaded is not None
    assert loaded["result"] == result.model_dump(mode="json")
    assert store.price_history_replays(limit=10)[0]["run_id"] == result.run_id

    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE price_history_replays SET result_json='{}' WHERE run_id=?",
                (result.run_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM price_history_replays WHERE run_id=?",
                (result.run_id,),
            )

        connection.execute("DROP TRIGGER price_history_replays_no_update")
        connection.execute(
            "UPDATE price_history_replays SET result_json='{}' WHERE run_id=?",
            (result.run_id,),
        )
    with pytest.raises(FrontierStoreError, match="payload is invalid"):
        store.price_history_replay(result.run_id)


def test_price_history_replay_store_migrates_schema_six(tmp_path):
    store = FrontierStore(tmp_path / "migration", max_bytes=2 * 1024 * 1024)
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TABLE price_history_replays")
        connection.execute("UPDATE frontier_meta SET value='6' WHERE key='schema_version'")

    store.initialize()
    assert store.summary()["schema_version"] == 7
    with sqlite3.connect(store.path) as connection:
        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')"
            )
        }
    assert "price_history_replays" in objects
    assert "price_history_replays_no_update" in objects
