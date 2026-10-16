from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import zlib
from pathlib import Path

import pytest
from midas.reality.storage import MAGIC
from midas.veritas.shadow_runtime_snapshot import (
    canonical,
    capture_shadow_runtime_snapshot,
    stable_digest,
    write_snapshot_once,
)


def make_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    raw_root = tmp_path / "source"
    raw_root.mkdir()
    stem = "00000000000000000001-0123456789abcdef0123456789abcdef"
    segment = raw_root / f"{stem}.seg"
    raw_record = canonical(
        {
            "schema_version": 1,
            "ordinal": 1,
            "received_ns": 10,
            "monotonic_ns": 20,
            "kind": "gap",
            "payload": {"reason": "fixture"},
        }
    )
    compressed_record = zlib.compress(raw_record)
    framed_record = (
        struct.pack(">I32s", len(compressed_record), hashlib.sha256(compressed_record).digest())
        + compressed_record
    )
    segment.write_bytes(MAGIC + framed_record)
    segment_sha = hashlib.sha256(segment.read_bytes()).hexdigest()
    catalog = {
        "schema_version": 1,
        "file": segment.name,
        "sha256": segment_sha,
        "bytes": segment.stat().st_size,
        "first": 1,
        "last": 1,
        "count": 1,
    }
    (raw_root / f"{stem}.json").write_text(json.dumps(catalog), encoding="utf-8")

    identity: dict[str, object] = {"raw_root": str(raw_root)}
    campaign_id = hashlib.sha256(canonical(identity)).hexdigest()
    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps({"campaign_id": campaign_id, "identity": identity}), encoding="utf-8"
    )
    runtime: dict[str, object] = {
        "campaign_id": campaign_id,
        "context": {},
        "cursor": {"segment": stem, "offset": len(MAGIC), "ordinal": 0},
        "next_decision": {},
        "next_observation": {},
        "counters": {},
    }
    runtime_bytes = canonical(runtime)
    database_path = tmp_path / "shadow.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("create table runtime(key text primary key,body blob,sha text)")
        connection.execute(
            "insert into runtime values('checkpoint',?,?)",
            (zlib.compress(runtime_bytes), hashlib.sha256(runtime_bytes).hexdigest()),
        )
    return campaign_path, database_path, runtime


def store_runtime(database_path: Path, runtime: dict[str, object]) -> None:
    runtime_bytes = canonical(runtime)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "update runtime set body=?,sha=? where key='checkpoint'",
            (zlib.compress(runtime_bytes), hashlib.sha256(runtime_bytes).hexdigest()),
        )


def test_captures_runtime_from_read_only_database_and_pins_source(tmp_path: Path) -> None:
    campaign, database, runtime = make_inputs(tmp_path)
    before = database.read_bytes()

    snapshot = capture_shadow_runtime_snapshot(campaign, database, captured_ns=123)

    assert snapshot["runtime"] == runtime
    assert snapshot["runtime_sha256"] == stable_digest(runtime)
    assert snapshot["persisted_runtime_sha256"] == hashlib.sha256(canonical(runtime)).hexdigest()
    assert snapshot["source_cursor_evidence"]["ordinal"] == 0
    assert database.read_bytes() == before


def test_rejects_runtime_digest_mismatch(tmp_path: Path) -> None:
    campaign, database, _ = make_inputs(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("update runtime set sha=?", ("0" * 64,))

    with pytest.raises(ValueError, match="Runtime checkpoint digest mismatch"):
        capture_shadow_runtime_snapshot(campaign, database)


def test_rejects_cursor_offset_inside_record(tmp_path: Path) -> None:
    campaign, database, runtime = make_inputs(tmp_path)
    cursor = runtime["cursor"]
    assert isinstance(cursor, dict)
    cursor["offset"] = len(MAGIC) + 1
    store_runtime(database, runtime)

    with pytest.raises(ValueError, match="does not align"):
        capture_shadow_runtime_snapshot(campaign, database)


def test_rejects_cursor_ordinal_that_disagrees_with_record_boundary(tmp_path: Path) -> None:
    campaign, database, runtime = make_inputs(tmp_path)
    cursor = runtime["cursor"]
    assert isinstance(cursor, dict)
    segment = Path(json.loads(campaign.read_text())["identity"]["raw_root"]) / (
        cursor["segment"] + ".seg"
    )
    cursor["offset"] = segment.stat().st_size
    cursor["ordinal"] = 0
    store_runtime(database, runtime)

    with pytest.raises(ValueError, match="offset and source ordinal disagree"):
        capture_shadow_runtime_snapshot(campaign, database)


def test_rejects_open_cursor_segment_and_refuses_snapshot_overwrite(
    tmp_path: Path,
) -> None:
    campaign, database, runtime = make_inputs(tmp_path)
    cursor = runtime["cursor"]
    assert isinstance(cursor, dict)
    raw_root = Path(json.loads(campaign.read_text())["identity"]["raw_root"])
    (raw_root / f"{cursor['segment']}.open").write_bytes(b"open")

    with pytest.raises(ValueError, match="still open"):
        capture_shadow_runtime_snapshot(campaign, database)

    output = tmp_path / "snapshot.json"
    write_snapshot_once(output, {"first": True})
    with pytest.raises(FileExistsError):
        write_snapshot_once(output, {"second": True})
    assert json.loads(output.read_text()) == {"first": True}
