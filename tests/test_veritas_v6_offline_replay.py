from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest

from scripts import veritas_v6_offline_replay as replay


def _source(root: Path, names: tuple[str, ...] = ("scan-001",)) -> Path:
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True)
    for name in names:
        content = gzip.compress(json.dumps({"scan_id": name}).encode(), mtime=0)
        (snapshots / f"{name}.json.gz").write_bytes(content)
    return root


def test_copy_resumes_after_a_snapshot_rename_interruption(tmp_path, monkeypatch):
    source = _source(tmp_path / "source")
    output = tmp_path / "output"
    snapshot = source / "snapshots" / "scan-001.json.gz"
    original_replace = replay.os.replace

    def interrupt_final_snapshot_rename(source_path, destination_path):
        if Path(destination_path).name == "scan-001.json.gz":
            raise OSError("simulated interruption before final rename")
        original_replace(source_path, destination_path)

    monkeypatch.setattr(replay.os, "replace", interrupt_final_snapshot_rename)
    with pytest.raises(OSError, match="simulated interruption"):
        replay.copy_snapshot_set(source, output)

    monkeypatch.undo()
    state = replay._read_state(output)
    assert state["phase"] == "COPYING"
    assert state["in_progress_file"] == snapshot.name
    assert (output / "snapshots" / f"{snapshot.name}.copying").is_file()

    manifest = replay.copy_snapshot_set(source, output, resume=True)

    copied = output / "snapshots" / snapshot.name
    assert replay.sha256_file(copied) == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert manifest["snapshot_count"] == 1
    assert replay._read_state(output)["phase"] == "CATALOGS"
    assert (
        replay._read_state(output)["copy_rate_bytes_per_second"]
        == replay.DEFAULT_COPY_RATE_BYTES_PER_SECOND
    )
    with pytest.raises(replay.ReplayError, match="copy rate differs"):
        replay.copy_snapshot_set(
            source,
            output,
            resume=True,
            copy_rate_bytes_per_second=replay.DEFAULT_COPY_RATE_BYTES_PER_SECOND // 2,
        )


def test_resume_rejects_changed_source_and_corrupted_copy(tmp_path):
    source = _source(tmp_path / "source", ("scan-001", "scan-002"))
    output = tmp_path / "output"
    calls = 0

    def interrupt_between_files():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise replay.ReplayError("simulated stop between snapshots")

    with pytest.raises(replay.ReplayError, match="simulated stop"):
        replay.copy_snapshot_set(source, output, admit=interrupt_between_files)

    first_source = source / "snapshots" / "scan-001.json.gz"
    first_source.write_bytes(first_source.read_bytes() + b"changed")
    with pytest.raises(replay.ReplayError, match="identity changed"):
        replay.copy_snapshot_set(source, output, resume=True)

    # A completed copy is also re-hashed before catalog-phase resume.
    source2 = _source(tmp_path / "source2")
    output2 = tmp_path / "output2"
    replay.copy_snapshot_set(source2, output2)
    copied = output2 / "snapshots" / "scan-001.json.gz"
    copied.write_bytes(copied.read_bytes() + b"corrupt")
    with pytest.raises(replay.ReplayError, match="checksum mismatch"):
        replay.copy_snapshot_set(source2, output2, resume=True)


def test_source_output_overlap_and_symlink_paths_are_rejected(tmp_path):
    source = _source(tmp_path / "source")
    with pytest.raises(replay.ReplayError, match="inside the source"):
        replay.copy_snapshot_set(source, source / "derived")

    source_link = tmp_path / "source-link"
    source_link.symlink_to(source, target_is_directory=True)
    with pytest.raises(replay.ReplayError, match="Source root cannot be a symlink"):
        replay.copy_snapshot_set(source_link, tmp_path / "other-output")

    output_link = tmp_path / "output-link"
    output_link.symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(replay.ReplayError, match="Output root cannot be a symlink"):
        replay.copy_snapshot_set(source, output_link)


def test_admission_rejection_is_durable_in_the_resume_checkpoint(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    state_path = output / replay.STATE_NAME
    replay.atomic_json(
        state_path,
        {"schema_version": 1, "phase": "COPYING", "completed_files": {}},
    )

    def reject():
        raise ValueError("simulated transient host I/O pressure")

    with pytest.raises(ValueError, match="host I/O pressure"):
        replay._checkpoint_admission_check(output, state_path, reject)

    checkpoint = replay._read_state(output)
    assert checkpoint["admission_rejections"][-1]["phase"] == "COPYING"
    assert "host I/O pressure" in checkpoint["admission_rejections"][-1]["reason"]
