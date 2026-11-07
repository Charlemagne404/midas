from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path

import pytest

from scripts import midas_local_backup as local_backup
from scripts import midas_veritas_snapshot as snapshot


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _seal(value: dict) -> dict:
    return {**value, "state_sha256": _digest(_canonical(value))}


def _write_checkpoint(path: Path, value: dict) -> bytes:
    sealed = _seal(value)
    data = _canonical(sealed)
    path.write_bytes(data)
    return data


def _fixture(tmp_path: Path, *, both_versions: bool = False) -> dict[str, Path | bytes | dict]:
    root = tmp_path / "observatory"
    events = root / "source-analysis-events" / "v1"
    events.mkdir(parents=True)
    (root / "source-analysis.lock").touch()
    module_root = tmp_path / "modules"
    module_file = module_root / "veritas" / "finalized_source_analysis.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_bytes(b"fixture runtime v2\n" if both_versions else b"fixture runtime v1\n")
    old_code = b"fixture runtime v1\n"
    new_code = module_file.read_bytes()
    script_root = tmp_path / "frozen-scripts"
    script_source_root = tmp_path / "runtime-scripts"
    script_root.mkdir()
    script_source_root.mkdir()
    script_data = b"fixture runtime entry script\n"
    script_target = script_source_root / "veritas_source_analysis.py"
    script_target.write_bytes(script_data)
    (script_root / "veritas_source_analysis.py").symlink_to(script_target)
    campaign = tmp_path / "campaign.json"
    campaign.write_text('{"campaign":"fixture"}\n')
    campaign_sha = _digest(campaign.read_bytes())
    old_files = {
        "finalized_source_analysis.py": _digest(old_code),
        "scripts/veritas_source_analysis.py": _digest(script_data),
    }
    new_files = {
        "finalized_source_analysis.py": _digest(new_code),
        "scripts/veritas_source_analysis.py": _digest(script_data),
    }
    old_code_sha = _digest(_canonical(old_files))
    new_code_sha = _digest(_canonical(new_files))
    chain = "0" * 64
    event_chain: list[str] = []
    for index in range(1, 3 if both_versions else 2):
        event = {
            "schema_version": 1,
            "analysis_version": "veritas-fixture-v1",
            "campaign_id": "campaign-fixture",
            "campaign_sha256": campaign_sha,
            "segment_index": index,
            "source_segment": f"segment-{index}",
        }
        event["analysis_event_sha256"] = _digest(_canonical(event))
        data = _canonical(event)
        (events / f"{index:020d}.json").write_bytes(data)
        chain = _digest(bytes.fromhex(chain) + bytes.fromhex(event["analysis_event_sha256"]))
        event_chain.append(chain)

    legacy_value = {
        "schema_version": 1,
        "analysis_version": "veritas-fixture-v1",
        "campaign_id": "campaign-fixture",
        "campaign_sha256": campaign_sha,
        "analysis_code_sha256": old_code_sha,
        "analysis_code_files": old_files,
        "processed_segment_count": 1 if both_versions else len(event_chain),
        "last_ordinal": 10,
        "last_segment_file": "fixture.seg",
        "processed_source_bytes": 100,
        "prefix_catalog_sha256": "a" * 64,
        "last_event_sha256": event_chain[0] if both_versions else event_chain[-1],
        "cumulative": {"fixture": True},
    }
    legacy_bytes = _write_checkpoint(root / "source-analysis-state-v1.json", legacy_value)
    if both_versions:
        new_value = {
            **legacy_value,
            "schema_version": 2,
            "analysis_code_sha256": new_code_sha,
            "analysis_code_files": new_files,
            "processed_segment_count": 2,
            "last_ordinal": 20,
            "last_event_sha256": event_chain[-1],
            "migration": {
                "from_state_schema_version": 1,
                "from_state_sha256": json.loads(legacy_bytes)["state_sha256"],
                "from_processed_segment_count": 1,
                "from_analysis_code_sha256": old_code_sha,
            },
        }
        _write_checkpoint(root / "source-analysis-state-v2.json", new_value)

    return {
        "root": root,
        "events": events,
        "module_root": module_root,
        "script_root": script_root,
        "script_source_root": script_source_root,
        "script_data": script_data,
        "campaign": campaign,
        "legacy_bytes": legacy_bytes,
        "old_code": old_code,
        "new_code": new_code,
        "event_chain": event_chain,
    }


def _capture(fixture: dict, destination: Path) -> dict:
    return snapshot.create_snapshot(
        source_root=fixture["root"],
        destination=destination,
        module_root=fixture["module_root"],
        script_root=fixture["script_root"],
        script_source_root=fixture["script_source_root"],
        campaign_path=fixture["campaign"],
        systemd_units=[],
        systemd_config_paths=[],
        minimum_timer_gap_seconds=0,
    )


def test_capture_preserves_checkpoint_chain_campaign_and_runtime_code(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()

    manifest = _capture(fixture, destination)

    restored_checkpoint = destination / "checkpoints/source-analysis-state-v1.json"
    assert restored_checkpoint.read_bytes() == fixture["legacy_bytes"]
    assert manifest["ledger"]["event_count"] == 1
    assert manifest["ledger"]["last_chain_sha256"] == fixture["event_chain"][0]
    assert snapshot.verify_snapshot(destination) == manifest
    assert (
        destination / "provenance/runtime-code/veritas/finalized_source_analysis.py"
    ).read_bytes() == fixture["old_code"]
    assert (
        destination / "provenance/runtime-code/scripts/veritas_source_analysis.py"
    ).read_bytes() == fixture["script_data"]
    origin = next(
        item
        for item in manifest["runtime_code_origins"]
        if item["identity"] == "scripts/veritas_source_analysis.py"
    )
    assert origin["symlink_target"] == str(
        fixture["script_source_root"] / "veritas_source_analysis.py"
    )
    assert origin["resolved_source_path"] == str(
        fixture["script_source_root"] / "veritas_source_analysis.py"
    )
    assert manifest["credentials_included"] is False


def test_capture_preserves_v1_to_v2_migration_lineage(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, both_versions=True)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()

    manifest = _capture(fixture, destination)

    assert manifest["authoritative_checkpoint"] == "source-analysis-state-v2.json"
    assert set(manifest["checkpoints"]) == {
        "source-analysis-state-v1.json",
        "source-analysis-state-v2.json",
    }
    assert manifest["ledger"]["event_count"] == 2
    assert (destination / "checkpoints/source-analysis-state-v1.json").read_bytes() == fixture[
        "legacy_bytes"
    ]
    assert (
        snapshot.verify_snapshot(destination)["ledger"]["last_chain_sha256"]
        == fixture["event_chain"][-1]
    )


def test_systemd_configuration_redacts_secret_like_values(tmp_path: Path) -> None:
    unit = tmp_path / "capacity.service"
    unit.write_text(
        "[Service]\n"
        "Environment=API_TOKEN=fixture-secret\n"
        "ExecStart=/usr/bin/tool --password fixture-password\n"
        "LoadCredential=midas-restic-password:/private/credential/path\n"
    )

    records, contents = snapshot._capture_systemd_config([unit])

    archived = contents["000-capacity.service"].decode()
    assert "fixture-secret" not in archived
    assert "fixture-password" not in archived
    assert "/private/credential/path" not in archived
    assert records[0]["redacted_secret_material"] is True


def test_event_ledger_uses_one_sequential_archive_sync(tmp_path: Path, monkeypatch) -> None:
    fixture = _fixture(tmp_path)
    sync_calls = []
    monkeypatch.setattr(snapshot.os, "fsync", lambda descriptor: sync_calls.append(descriptor))
    state = snapshot._read_checkpoint(fixture["root"] / "source-analysis-state-v1.json")[0]
    event_bytes, chain, _stats = snapshot._write_event_archive(
        event_root=fixture["events"],
        archive_path=tmp_path / "ledger.tar",
        max_count=1,
        latest=state,
        checkpoint_counts={1: ("source-analysis-state-v1.json", state["last_event_sha256"])},
    )
    assert event_bytes > 0
    assert chain == fixture["event_chain"][0]
    assert len(sync_calls) == 1


def test_missing_event_rejects_capture_without_publishing_partial_snapshot(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    (fixture["events"] / f"{1:020d}.json").unlink()
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()

    with pytest.raises(snapshot.SnapshotError, match="event ledger contains missing"):
        _capture(fixture, destination)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_interrupted_capture_cleans_its_private_partial_directory(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = _fixture(tmp_path)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()

    def interrupted_archive(**kwargs) -> None:
        kwargs["archive_path"].write_bytes(b"partial event archive")
        raise OSError("simulated interrupted event capture")

    monkeypatch.setattr(snapshot, "_write_event_archive", interrupted_archive)
    with pytest.raises(OSError, match="interrupted"):
        _capture(fixture, destination)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_event_change_during_capture_is_rejected(tmp_path: Path, monkeypatch) -> None:
    fixture = _fixture(tmp_path)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()
    original = snapshot._capture_systemd_config

    def mutate_event(paths: list[Path]):
        result = original(paths)
        event = fixture["events"] / f"{1:020d}.json"
        event.write_bytes(event.read_bytes() + b" ")
        return result

    monkeypatch.setattr(snapshot, "_capture_systemd_config", mutate_event)
    with pytest.raises(snapshot.SnapshotError, match="event ledger changed during capture"):
        _capture(fixture, destination)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_runtime_code_symlink_cannot_escape_approved_root(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_bytes(fixture["script_data"])
    link = fixture["script_root"] / "veritas_source_analysis.py"
    link.unlink()
    link.symlink_to(outside)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()

    with pytest.raises(snapshot.SnapshotError, match="escapes its approved source root"):
        _capture(fixture, destination)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_checkpoint_change_during_capture_is_rejected(tmp_path: Path, monkeypatch) -> None:
    fixture = _fixture(tmp_path)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()
    original = snapshot._capture_systemd_config

    def mutate_checkpoint(paths: list[Path]):
        result = original(paths)
        checkpoint = fixture["root"] / "source-analysis-state-v1.json"
        checkpoint.write_bytes(checkpoint.read_bytes() + b" ")
        return result

    monkeypatch.setattr(snapshot, "_capture_systemd_config", mutate_checkpoint)
    with pytest.raises(snapshot.SnapshotError, match="checkpoint changed during capture"):
        _capture(fixture, destination)

    assert not destination.exists()
    assert list(destination.parent.iterdir()) == []


def test_busy_writer_lock_and_active_service_fail_closed(tmp_path: Path, monkeypatch) -> None:
    fixture = _fixture(tmp_path)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()
    descriptor = os.open(fixture["root"] / "source-analysis.lock", os.O_RDONLY)
    try:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(snapshot.SnapshotError, match="writer currently owns"):
            _capture(fixture, destination)
    finally:
        os.close(descriptor)

    monkeypatch.setattr(
        snapshot,
        "_unit_properties",
        lambda units: {
            "midas-veritas-source-analysis.service": {
                "Id": "midas-veritas-source-analysis.service",
                "ActiveState": "active",
                "ExecMainStartTimestampMonotonic": "123",
            }
        },
    )
    with pytest.raises(snapshot.SnapshotError, match="service is active"):
        snapshot.create_snapshot(
            source_root=fixture["root"],
            destination=destination,
            module_root=fixture["module_root"],
            script_root=destination.parent / "scripts",
            campaign_path=fixture["campaign"],
            systemd_units=["midas-veritas-source-analysis.service"],
            systemd_config_paths=[],
            minimum_timer_gap_seconds=0,
        )


def test_snapshot_verification_rejects_corrupted_archive_file(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()
    _capture(fixture, destination)
    archive = destination / snapshot.LEDGER_ARCHIVE_PATH
    damaged = bytearray(archive.read_bytes())
    damaged[len(damaged) // 2] ^= 1
    archive.write_bytes(damaged)

    with pytest.raises(snapshot.SnapshotError, match="checksum mismatch"):
        snapshot.verify_snapshot(destination)


def test_snapshot_verification_rejects_missing_event_archive_member(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path, both_versions=True)
    destination = tmp_path / "backup" / "veritas"
    destination.parent.mkdir()
    _capture(fixture, destination)
    archive_path = destination / snapshot.LEDGER_ARCHIVE_PATH
    replacement = destination / "ledger.partial.tar"
    with (
        tarfile.open(archive_path, "r:") as original,
        tarfile.open(replacement, "w:", format=tarfile.USTAR_FORMAT) as changed,
    ):
        members = original.getmembers()
        for member in members[:-1]:
            stream = original.extractfile(member)
            assert stream is not None
            with stream:
                changed.addfile(member, stream)
    replacement.replace(archive_path)
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    archive_record = next(
        item for item in manifest["files"] if item["path"] == snapshot.LEDGER_ARCHIVE_PATH
    )
    archive_bytes = archive_path.read_bytes()
    archive_record["bytes"] = len(archive_bytes)
    archive_record["sha256"] = _digest(archive_bytes)
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    (destination / "manifest.sha256").write_text(_digest(manifest_bytes) + "\n")

    with pytest.raises(snapshot.SnapshotError, match="event count differs from its checkpoint"):
        snapshot.verify_snapshot(destination)


def test_disposable_restic_restore_verifies_veritas_checkpoint_and_ledger(
    tmp_path: Path, monkeypatch
) -> None:
    if shutil.which("restic") is None:
        pytest.skip("Restic executable is required for the disposable integration test")
    fixture = _fixture(tmp_path)
    payload = tmp_path / "input" / "veritas"
    payload.parent.mkdir()
    _capture(fixture, payload)
    root = tmp_path / "backup-root"
    root.mkdir()
    repository = root / "repository"
    password = tmp_path / "restic-password"
    password.write_text("fixture-password\n")
    password.chmod(0o600)
    monkeypatch.setenv("RESTIC_PASSWORD_FILE", str(password))
    local_backup._restic(repository, password, "init")
    result = local_backup._restic(
        repository,
        password,
        "backup",
        "--json",
        "--tag",
        "midas-veritas-source-analysis",
        str(payload),
    )
    summary = next(
        json.loads(line)
        for line in result.stdout.splitlines()
        if json.loads(line).get("message_type") == "summary"
    )
    restored = tmp_path / "restore"
    restored.mkdir()
    local_backup._restic(
        repository,
        password,
        "restore",
        summary["snapshot_id"],
        "--target",
        str(restored),
        "--verify",
    )
    archived = next(restored.rglob("manifest.json")).parent
    assert snapshot.verify_snapshot(archived)["ledger"]["event_count"] == 1
