from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from midas.reality.storage import Store, manifest, read_manifest

from scripts import midas_recording_snapshot as snapshots


@pytest.fixture
def admitted_snapshot_scope(monkeypatch):
    monkeypatch.setattr(
        snapshots,
        "_require_heavy_scope",
        lambda: {
            "cgroup": "/fixture",
            "memory_current_bytes": 0,
            "memory_high_bytes": 1024**3,
            "memory_max_bytes": 2 * 1024**3,
            "preflight_at_utc": "fixture",
            "preflight_profile": "heavy",
        },
    )


def _record_fixture(root: Path) -> list[dict]:
    store = Store(root, budget=1024**2, reserve=0, segment_bytes=1024**2)
    expected = [
        store.append("fixture", {"index": index, "value": f"record-{index}"}) for index in range(3)
    ]
    store.rotate(reopen=False)
    store.close()
    return expected


def test_recording_snapshot_verifies_and_restores_exact_finalized_records(
    tmp_path: Path, admitted_snapshot_scope
) -> None:
    source = tmp_path / "source"
    expected = _record_fixture(source)
    snapshot = tmp_path / "backups" / "recording-20261105T120000Z"
    snapshot.parent.mkdir()

    created = snapshots.create_snapshot(source, snapshot, reserve_mib=0)
    assert created["decision"] == "CREATED"
    assert created["segment_count"] == 1
    assert created["file_count"] == 2
    assert snapshots.verify_snapshot(snapshot)["decision"] == "VERIFIED"

    restored = tmp_path / "restore"
    result = snapshots.restore_snapshot(snapshot, restored)
    assert result["decision"] == "RESTORED"
    assert result["record_count"] == 3
    assert manifest(restored) == manifest(source)
    assert list(read_manifest(restored, manifest(restored))) == expected


def test_active_writer_is_never_blocked_or_copied(tmp_path: Path, admitted_snapshot_scope) -> None:
    source = tmp_path / "source"
    writer = Store(source, budget=1024**2, reserve=0)
    writer.append("fixture", {"value": "active"})
    destination = tmp_path / "snapshot"
    with pytest.raises(snapshots.RecordingSnapshotError, match="writer still owns"):
        snapshots.create_snapshot(source, destination, reserve_mib=0)
    assert not destination.exists()
    writer.close()


def test_active_writer_failure_is_captured_in_private_receipt(
    tmp_path: Path, admitted_snapshot_scope, capsys
) -> None:
    source = tmp_path / "source"
    writer = Store(source, budget=1024**2, reserve=0)
    writer.append("fixture", {"value": "active"})
    receipt = tmp_path / "receipts" / "failure.json"
    receipt.parent.mkdir()

    assert (
        snapshots.main(
            [
                "backup",
                "--source-root",
                str(source),
                "--destination",
                str(tmp_path / "snapshot"),
                "--receipt",
                str(receipt),
            ]
        )
        == 1
    )
    capsys.readouterr()
    assert json.loads(receipt.read_text())["decision"] == "FAILED"
    writer.close()


def test_orphan_open_segment_fails_closed(tmp_path: Path, admitted_snapshot_scope) -> None:
    source = tmp_path / "source"
    writer = Store(source, budget=1024**2, reserve=0)
    writer.append("fixture", {"value": "unfinished"})
    writer.file.close()
    writer.file = None
    writer.lock.close()
    open_segment = next(source.glob("*.open"))
    before = open_segment.read_bytes()

    with pytest.raises(snapshots.RecordingSnapshotError, match="open segments"):
        snapshots.create_snapshot(source, tmp_path / "snapshot", reserve_mib=0)
    assert open_segment.read_bytes() == before
    assert not (tmp_path / "snapshot").exists()


def test_snapshot_detects_segment_or_sidecar_tampering(
    tmp_path: Path, admitted_snapshot_scope
) -> None:
    source = tmp_path / "source"
    _record_fixture(source)
    snapshot = tmp_path / "snapshot"
    snapshots.create_snapshot(source, snapshot, reserve_mib=0)
    sidecar = next((snapshot / "segments").glob("*.json"))
    sidecar.write_text(json.dumps({"tampered": True}))

    with pytest.raises(snapshots.RecordingSnapshotError, match="sidecar checksum"):
        snapshots.verify_snapshot(snapshot)


def test_snapshot_detects_segment_byte_tampering(tmp_path: Path, admitted_snapshot_scope) -> None:
    source = tmp_path / "source"
    _record_fixture(source)
    snapshot = tmp_path / "snapshot"
    snapshots.create_snapshot(source, snapshot, reserve_mib=0)
    segment = next((snapshot / "segments").glob("*.seg"))
    original = segment.read_bytes()
    segment.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))

    with pytest.raises(ValueError):
        snapshots.verify_snapshot(snapshot)


def test_snapshot_inventory_digest_must_match_recording_manifest(
    tmp_path: Path, admitted_snapshot_scope
) -> None:
    source = tmp_path / "source"
    _record_fixture(source)
    snapshot = tmp_path / "snapshot"
    snapshots.create_snapshot(source, snapshot, reserve_mib=0)
    manifest_path = snapshot / snapshots.MANIFEST_NAME
    manifest_value = json.loads(manifest_path.read_text())
    segment_entry = next(item for item in manifest_value["files"] if item["kind"] == "segment")
    segment_entry["sha256"] = "0" * 64
    manifest_bytes = (json.dumps(manifest_value, sort_keys=True, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    (snapshot / snapshots.MANIFEST_HASH_NAME).write_text(
        hashlib.sha256(manifest_bytes).hexdigest() + "\n"
    )

    with pytest.raises(snapshots.RecordingSnapshotError, match="segment metadata differs"):
        snapshots.verify_snapshot(snapshot)
