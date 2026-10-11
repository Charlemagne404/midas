import json
from pathlib import Path

import pytest
from midas.core.models import MarketEvent
from midas.laboratory.datasets import create_manifest, load_dataset, replay_scenario, validate
from midas.laboratory.runtime import execute
from midas.paper.broker import AccountConfig, ExecutionModel

DATASETS = Path(__file__).resolve().parents[2] / "data/datasets"


def test_recorded_capture_hash_validation_and_negative_opportunity_replay():
    path, manifest = load_dataset(DATASETS, "ctf-4024677")
    assert validate(path, manifest)["valid"]
    result = execute(
        replay_scenario(
            path, manifest, AccountConfig(execution=ExecutionModel.preset("optimistic"))
        )
    )
    assert result["passed"]
    assert result["data_source"] == "RECORDED"
    assert result["final_portfolio"]["hypothetical_fills"] == 0
    decisions = [e for e in result["journal"] if e["kind"] == "decision"]
    assert len(decisions) == 3
    # Earlier callbacks cannot inspect the future second instrument snapshot.
    assert all(not e["after"]["decisions"][-1]["risk"]["allowed"] for e in decisions[:2])
    assert decisions[-1]["after"]["decisions"][-1]["evaluation"]["status"] == "NEGATIVE_EDGE"
    assert result["dataset_hash"] == manifest.content_sha256


def test_tampered_recording_and_manifest_rejected(tmp_path):
    original, manifest = load_dataset(DATASETS, "ctf-4024677")
    path = tmp_path / "tampered.jsonl"
    path.write_bytes(original.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash"):
        validate(path, manifest)
    with pytest.raises(ValueError, match="count"):
        validate(original, manifest.model_copy(update={"event_count": 999}))
    with pytest.raises(ValueError, match="coverage"):
        validate(
            original, manifest.model_copy(update={"capture_end_ms": manifest.capture_end_ms + 1})
        )


def test_future_receipt_and_latency_do_not_leak_to_earlier_decisions(tmp_path):
    path, original = load_dataset(DATASETS, "ctf-4024677")
    events = [MarketEvent.model_validate_json(line) for line in path.read_text().splitlines()]
    latest = events[-1]
    ts = latest.received_ts_ms + 500
    events[-1] = latest.model_copy(
        update={"received_ts_ms": ts, "book": latest.book.model_copy(update={"received_ts_ms": ts})}
    )
    delayed = tmp_path / "delayed.jsonl"
    delayed.write_text("".join(e.model_dump_json() + "\n" for e in events))
    manifest = create_manifest(
        delayed,
        "delayed",
        "recorded fixture",
        original.market_metadata,
        original.completeness_limitations,
    )
    result = execute(replay_scenario(delayed, manifest, latency_ms=100))
    asset = latest.asset_id
    for event in result["journal"]:
        if event["time_ms"] < ts + 100:
            book = event["observation"]["books"].get(asset)
            assert book is None or not book["valid"]
        if event["kind"] == "decision":
            assert all(
                b["received_ts_ms"] <= event["time_ms"]
                for b in event["after"]["decisions"][-1]["evaluation"]["books"]
            )
    assert result["passed"]


def test_out_of_order_exchange_snapshots_do_not_replace_newer_observation(tmp_path):
    path, original = load_dataset(DATASETS, "ctf-4024677")
    events = [MarketEvent.model_validate_json(line) for line in path.read_text().splitlines()]
    snapshot = events[1]
    late = snapshot.model_copy(
        update={
            "event_id": "late",
            "received_ts_ms": snapshot.received_ts_ms + 10,
            "exchange_ts_ms": snapshot.exchange_ts_ms - 10,
            "book": snapshot.book.model_copy(
                update={
                    "received_ts_ms": snapshot.received_ts_ms + 10,
                    "exchange_ts_ms": snapshot.exchange_ts_ms - 10,
                }
            ),
        }
    )
    events.append(late)
    copied = tmp_path / "late.jsonl"
    copied.write_text("".join(e.model_dump_json() + "\n" for e in events))
    manifest = create_manifest(
        copied,
        "late",
        "public captured fixture",
        original.market_metadata,
        original.completeness_limitations,
    )
    assert validate(copied, manifest)["late_exchange_snapshots"] == 1
    result = execute(replay_scenario(copied, manifest))
    assert (
        result["journal"][-1]["observation"]["books"][snapshot.asset_id]["exchange_ts_ms"]
        == snapshot.exchange_ts_ms
    )


def test_conflicting_duplicate_and_mixed_provenance_are_quarantined(tmp_path):
    path, original = load_dataset(DATASETS, "ctf-4024677")
    raw = [json.loads(line) for line in path.read_text().splitlines()]
    conflicting = dict(raw[0], received_ts_ms=raw[0]["received_ts_ms"] + 1)
    raw.append(conflicting)
    target = tmp_path / "conflict.jsonl"
    target.write_text("".join(json.dumps(e) + "\n" for e in raw))
    manifest = create_manifest(
        target, "conflict", "fixture", original.market_metadata, original.completeness_limitations
    )
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        validate(target, manifest)
    raw = raw[:-1]
    raw[0]["source"] = "SYNTHETIC"
    target.write_text("".join(json.dumps(e) + "\n" for e in raw))
    manifest = create_manifest(
        target, "mixed", "fixture", original.market_metadata, original.completeness_limitations
    )
    with pytest.raises(ValueError, match="provenance"):
        validate(target, manifest)


def test_raw_unsequenced_delta_invalidates_reconstructed_book(tmp_path):
    path, original = load_dataset(DATASETS, "ctf-4024677")
    events = [MarketEvent.model_validate_json(line) for line in path.read_text().splitlines()]
    asset = events[1].asset_id
    events.append(
        MarketEvent(
            event_id="delta",
            kind="price_change",
            source="LIVE",
            received_ts_ms=events[-1].received_ts_ms + 1,
            raw={"price_changes": [{"asset_id": asset, "price": ".5"}]},
        )
    )
    target = tmp_path / "delta.jsonl"
    target.write_text("".join(e.model_dump_json() + "\n" for e in events))
    manifest = create_manifest(
        target, "delta", "fixture", original.market_metadata, original.completeness_limitations
    )
    result = execute(replay_scenario(target, manifest))
    assert result["passed"]
    assert result["journal"][-1]["observation"]["books"][asset]["valid"] is False


def test_updates_do_not_refresh_unchanged_instrument_receipt_clock(tmp_path):
    path, original = load_dataset(DATASETS, "ctf-4024677")
    events = [MarketEvent.model_validate_json(line) for line in path.read_text().splitlines()]
    first = events[1]
    update = first.model_copy(
        update={
            "event_id": "newer",
            "received_ts_ms": first.received_ts_ms + 100,
            "exchange_ts_ms": first.exchange_ts_ms + 100,
            "book": first.book.model_copy(
                update={
                    "received_ts_ms": first.received_ts_ms + 100,
                    "exchange_ts_ms": first.exchange_ts_ms + 100,
                }
            ),
        }
    )
    events.append(update)
    target = tmp_path / "updates.jsonl"
    target.write_text("".join(e.model_dump_json() + "\n" for e in events))
    manifest = create_manifest(
        target, "updates", "fixture", original.market_metadata, original.completeness_limitations
    )
    result = execute(replay_scenario(target, manifest))
    second = events[2]
    assert (
        result["journal"][-1]["observation"]["books"][second.asset_id]["received_ts_ms"]
        == second.received_ts_ms
    )
