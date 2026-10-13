import json

import pytest
from midas.arena.jobs import JobSpec, create, run
from midas.arena.observations import ObservationSpec, build, windows
from midas.core.models import MarketEvent, Source
from midas.laboratory.datasets import create_manifest
from midas.simulation.fixtures import binary_fixture


def sample(polls=20):
    market, books = binary_fixture("profitable")
    market = market.model_copy(update={"source": Source.LIVE})
    epoch = min(b.received_ts_ms for b in books.values())
    events = [
        MarketEvent(
            event_id="public-test:metadata",
            kind="public_metadata",
            source=Source.LIVE,
            received_ts_ms=epoch,
            raw={"market": market.model_dump(mode="json")},
        )
    ]
    for i in range(polls):
        for j, (asset, book) in enumerate(books.items()):
            received = epoch + i * 5000 + 100 + j * 100
            value = book.model_copy(
                update={
                    "source": Source.LIVE,
                    "received_ts_ms": received,
                    "exchange_ts_ms": received - 10,
                }
            )
            events.append(
                MarketEvent(
                    event_id=f"public-test:poll:{i}:{asset}",
                    kind="book",
                    source=Source.LIVE,
                    asset_id=asset,
                    book=value,
                    raw={"fixture": True},
                    received_ts_ms=received,
                    exchange_ts_ms=received - 10,
                )
            )
    return market, events


def recording(tmp_path):
    market, events = sample()
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    source = datasets / "public-test.jsonl"
    source.write_text("".join(e.model_dump_json() + "\n" for e in events))
    manifest = create_manifest(
        source, "public-test", "Mock public fixture", (market,), ("Fixture only",)
    )
    (datasets / "public-test.manifest.json").write_text(manifest.model_dump_json())
    return tmp_path / "arena", source


def test_chronological_pairs_embargo_and_repeated_shapes():
    market, events = sample()
    rows, quality = windows(
        events,
        tuple(i.asset_id for i in market.instruments),
        ObservationSpec(source_id="public-test"),
    )
    assert len(rows) == 20
    assert all(len(r["event_ids"]) == 2 for r in rows)
    assert quality["partition_windows"] == {"train": 14, "embargo": 4, "validation": 1, "test": 1}
    bounds = quality["partition_bounds"]
    assert bounds["validation"]["first_received_ms"] > bounds["train"]["last_available_ms"] + 10000
    assert bounds["test"]["first_received_ms"] > bounds["validation"]["last_available_ms"] + 10000
    assert quality["unique_quote_shapes"] == quality["cross_partition_repeated_quote_shapes"] == 1


def test_economically_identical_decimal_formats_share_shape():
    from decimal import Decimal

    market, events = sample()
    event = events[1]
    book = event.book
    revised = book.model_copy(
        update={
            "asks": tuple(
                level.model_copy(
                    update={
                        "price": Decimal(str(level.price) + "0"),
                        "size": Decimal(str(level.size) + ".0"),
                    }
                )
                for level in book.asks
            ),
            "tick_size": Decimal(str(book.tick_size) + "0"),
            "min_order_size": Decimal(str(book.min_order_size) + ".0"),
        }
    )
    events[1] = event.model_copy(update={"book": revised})
    _, quality = windows(
        events,
        tuple(i.asset_id for i in market.instruments),
        ObservationSpec(source_id="public-test"),
    )
    assert quality["unique_quote_shapes"] == 1


@pytest.mark.parametrize("problem", ["duplicate", "receipt", "poll", "short"])
def test_rejects_ambiguous_or_insufficient_sources(problem):
    market, events = sample(6 if problem == "short" else 20)
    if problem == "duplicate":
        events.append(events[-1])
    elif problem == "receipt":
        events[-1], events[-2] = events[-2], events[-1]
    elif problem == "poll":
        for index in (1, 2):
            events[index] = events[index].model_copy(
                update={"event_id": events[index].event_id.replace(":poll:0:", ":poll:21:")}
            )
    with pytest.raises(ValueError):
        windows(
            events,
            tuple(i.asset_id for i in market.instruments),
            ObservationSpec(source_id="public-test"),
        )


def test_invalid_window_quarantine_preserves_other_pairs():
    market, events = sample(40)
    events.pop(2)
    event = events[10]
    events[10] = event.model_copy(update={"exchange_ts_ms": event.received_ts_ms + 100})
    rows, quality = windows(
        events,
        tuple(i.asset_id for i in market.instruments),
        ObservationSpec(source_id="public-test"),
    )
    assert len(rows) == 38
    assert quality["quarantine_reasons"] == {
        "missing_or_duplicate_instrument": 1,
        "future_exchange_timestamp": 1,
    }


def test_source_frozen_and_no_execution_training(tmp_path):
    root, source = recording(tmp_path)
    original = source.read_bytes()
    spec = ObservationSpec(source_id="public-test")
    result = build(root, spec)
    assert result["provenance"] == "RECORDED_PUBLIC" and result["label_definition"] is None
    assert not result["eligible_for_execution_training"]
    assert source.read_bytes() == original
    assert build(root, spec) == result
    path = root / "observations" / result["observation_id"] / "rows.json"
    path.write_text("[]")
    with pytest.raises(ValueError, match="Frozen"):
        build(root, spec)


def test_native_bounded_observation_job(tmp_path):
    root, _ = recording(tmp_path)
    job = create(
        root,
        JobSpec(
            kind="observations",
            observations=ObservationSpec(source_id="public-test"),
            max_wall_seconds=30,
        ),
        launch=False,
    )
    run(root, job["job_id"])
    result = json.loads((root / "jobs" / job["job_id"] / "job.json").read_text())
    assert result["state"] == "COMPLETED" and result["exit_status"] == 0
    assert result["result"]["observation_id"].startswith("observations-")


def test_observation_api_catalog_paging_and_frozen_source(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from apps.api.arena import router

    root, _ = recording(tmp_path)
    record = build(root, ObservationSpec(source_id="public-test"))
    identity = record["observation_id"]
    app = FastAPI()
    app.include_router(router(root))
    with TestClient(app) as client:
        overview = client.get("/api/arena").json()
        assert overview["datasets"] == []
        assert overview["observations"][0]["observation_id"] == identity
        response = client.get(f"/api/arena/observations/{identity}/rows?offset=3&limit=2")
        assert response.status_code == 200 and len(response.json()) == 2
        assert response.json()[0]["poll"] == 3
        assert client.get(f"/api/arena/observations/{identity}/rows?limit=201").status_code == 422
        path = root / "observations" / identity / "source.jsonl"
        path.write_text("{}\n")
        assert client.get(f"/api/arena/observations/{identity}").status_code == 409


def test_standalone_verifier_recomputes_windows_and_rejects_changed_availability(tmp_path):
    from midas.arena.artifacts import atomic_json, sha256

    from scripts.verify_observation_windows import verify

    root, _ = recording(tmp_path)
    record = build(root, ObservationSpec(source_id="public-test"))
    identity = record["observation_id"]
    assert verify(root, identity)["windows_verified"] == 20
    directory = root / "observations" / identity
    rows = json.loads((directory / "rows.json").read_text())
    rows[0]["available_at_ms"] = 0
    atomic_json(directory / "rows.json", rows)
    record["rows_sha256"] = sha256(directory / "rows.json")
    atomic_json(directory / "manifest.json", record)
    with pytest.raises(ValueError, match="differ"):
        verify(root, identity)
