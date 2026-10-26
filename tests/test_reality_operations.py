"""Storage operations fixtures are artificial, never market evidence."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from midas.reality.config import Config
from midas.reality.operations import archive, capacity
from midas.reality.storage import Store, atomic_json, file_hash, manifest


def sample(root):
    with_store = Store(root, reserve=1)
    for ns in (1_000_000_000, 121_000_000_000):
        with_store.append("frame", "PONG", received_ns=ns)
        with_store.rotate()
    with_store.close()
    atomic_json(
        root / "status.json", dict(updated_ns=121_000_000_000, state="RECORDING_UNSEQUENCED")
    )
    return manifest(root)


def config(root, **kwargs):
    # Config's production path guard remains intact; patch only fixture construction.
    with patch.object(Config, "__post_init__"):
        return Config(root=str(root), **kwargs)


def test_capacity_real_bytes_rates_and_horizon(tmp_path):
    value = sample(tmp_path)
    cfg = config(tmp_path)
    result = capacity(cfg, now_ns=121_000_000_000)
    expected_bytes = sum(
        s["bytes"] + (tmp_path / s["file"]).with_suffix(".json").stat().st_size
        for s in value["segments"]
    )
    assert result["sample"]["raw_frames"] == 2
    assert result["sample"]["raw_frame_payload_bytes"] == 8
    assert result["compressed_bytes_per_second"] == expected_bytes / 120
    assert result["raw_root_bytes"] == sum(p.stat().st_size for p in tmp_path.iterdir())
    assert result["retention_seconds_remaining"] == 30 * 86400 - 120
    assert result["collector_status_age_seconds"] == 0
    assert result["estimated_action_deadline_ns"] > 121_000_000_000


def test_capacity_alerts_unknown_clock_and_corruption(tmp_path):
    sample(tmp_path)
    result = capacity(
        config(tmp_path, budget_bytes=1, retention_days=1), now_ns=200_000_000_000_000
    )
    assert "CAPACITY_EXHAUSTED" in result["alerts"]
    assert "RETENTION_HORIZON_REACHED" in result["alerts"]
    assert "COLLECTOR_STATUS_STALE" in result["alerts"]
    segment = next(tmp_path.glob("*.seg"))
    segment.write_bytes(b"damaged")
    with pytest.raises(ValueError):
        capacity(config(tmp_path))


def test_short_sample_is_unknown(tmp_path):
    store = Store(tmp_path, reserve=1)
    store.append("frame", "PONG", received_ns=1)
    store.close()
    result = capacity(config(tmp_path))
    assert result["compressed_bytes_per_second"] is None
    assert "RATE_INSUFFICIENT_EVIDENCE" in result["alerts"]


def test_archive_incremental_integrity_and_originals(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    original_hashes = {s["file"]: file_hash(root / s["file"]) for s in value["segments"]}
    result = archive(root, target, budget=1_000_000, reserve=1)
    assert result["archival_provenance"]["originals_deleted"] is False
    assert result["segments"] == value["segments"]
    again = archive(root, target, budget=1_000_000, reserve=1)
    assert again["segments"] == result["segments"]
    for name, digest in original_hashes.items():
        assert file_hash(root / name) == file_hash(target / name) == digest
    (target / value["segments"][0]["file"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        archive(root, target, budget=1_000_000, reserve=1)
    assert json.loads((target / "manifest.json").read_text())["segments"] == value["segments"]


def test_archive_resume_counts_destination_once_for_many_missing_segments(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    store = Store(root, reserve=1)
    for index in range(24):
        store.append("frame", "PONG", received_ns=(index + 1) * 60_000_000_000)
        store.rotate()
    store.close()
    value = manifest(root)
    original_hashes = {s["file"]: file_hash(root / s["file"]) for s in value["segments"]}
    archive(root, target, budget=1_000_000, reserve=1)

    missing = value["segments"][:12]
    for info in missing:
        (target / info["file"]).unlink()

    original_iterdir = Path.iterdir
    destination_iterdir_calls = 0

    def counted_iterdir(path):
        nonlocal destination_iterdir_calls
        if path == target:
            destination_iterdir_calls += 1
        yield from original_iterdir(path)

    with patch.object(Path, "iterdir", counted_iterdir):
        result = archive(root, target, budget=1_000_000, reserve=1)

    assert destination_iterdir_calls == 1
    assert result["segments"] == value["segments"]
    for name, digest in original_hashes.items():
        assert file_hash(root / name) == file_hash(target / name) == digest


def test_archive_incremental_publication_survives_empty_segment_reordering(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    sample(root)
    before = archive(root, target, budget=1_000_000, reserve=1)
    writer = Store(root, reserve=1)
    writer.append("frame", "PONG", received_ns=241_000_000_000)
    writer.rotate()
    writer.close()
    updated = manifest(root)
    assert len(updated["segments"]) > len(before["segments"])

    result = archive(root, target, budget=1_000_000, reserve=1)

    assert result["segments"] == updated["segments"]
    assert json.loads((target / "manifest.json").read_text())["segments"] == updated["segments"]


def test_archive_budget_failure_resumes_without_publishing(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    with pytest.raises(OSError, match="budget"):
        archive(root, target, budget=1, reserve=1)
    assert not (target / "manifest.json").exists()
    name = value["segments"][0]["file"]
    partial = target / Path(name).with_suffix(".copying")
    partial.write_bytes(b"interrupted")
    with pytest.raises(ValueError, match="provenance review"):
        archive(root, target, budget=1_000_000, reserve=1)
    assert partial.read_bytes() == b"interrupted"
    # The fixture explicitly disposes its own synthetic interrupted copy.
    partial.unlink()
    result = archive(root, target, budget=1_000_000, reserve=1)
    assert len(result["segments"]) == len(value["segments"])
    assert not list(target.glob("*.copying"))


def test_archive_rejects_conflicting_manifest_without_overwrite(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    sample(root)
    archive(root, target, budget=1_000_000, reserve=1)
    manifest_path = target / "manifest.json"
    saved = json.loads(manifest_path.read_text())
    saved["archival_provenance"]["source_manifest_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(saved))
    before = manifest_path.read_bytes()
    with pytest.raises(ValueError, match="conflicts with source provenance"):
        archive(root, target, budget=1_000_000, reserve=1)
    assert manifest_path.read_bytes() == before


def test_archive_rejects_source_segment_without_published_manifest(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    target.mkdir()
    atomic_json(target / "source.json", dict(schema_version=1, recording_root=str(root.resolve())))
    info = value["segments"][0]
    archived = target / info["file"]
    archived.write_bytes((root / info["file"]).read_bytes())
    before = file_hash(archived)

    with pytest.raises(ValueError, match="no published manifest"):
        archive(root, target, budget=1_000_000, reserve=1)

    assert file_hash(archived) == before
    assert not (target / "manifest.json").exists()


def test_archive_rejects_unpublished_source_segment_without_adopting_it(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    sample(root)
    published = archive(root, target, budget=1_000_000, reserve=1)
    writer = Store(root, reserve=1)
    writer.append("frame", "PONG", received_ns=241_000_000_000)
    writer.rotate()
    writer.close()
    updated = manifest(root)
    assert len(updated["segments"]) > len(published["segments"])
    extra = updated["segments"][-1]
    orphan = target / extra["file"]
    orphan.write_bytes((root / extra["file"]).read_bytes())
    before_segment = file_hash(orphan)
    before_manifest = (target / "manifest.json").read_bytes()

    with pytest.raises(ValueError, match="absent from the published manifest"):
        archive(root, target, budget=1_000_000, reserve=1)

    assert file_hash(orphan) == before_segment
    assert (target / "manifest.json").read_bytes() == before_manifest


def test_archive_separation_and_identity(tmp_path):
    root = tmp_path / "raw"
    sample(root)
    with pytest.raises(ValueError, match="separate"):
        archive(root, root / "archive", budget=100_000, reserve=1)
    target = tmp_path / "archive"
    archive(root, target, budget=100_000, reserve=1)
    other = tmp_path / "other"
    sample(other)
    with pytest.raises(ValueError, match="different recording root"):
        archive(other, target, budget=100_000, reserve=1)


def test_archive_global_order_corruption_never_published(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    store = Store(root, reserve=1)
    store.ordinal = 3
    store.append("frame", "PONG")
    store.close()
    with pytest.raises(ValueError, match="ordinal"):
        archive(root, target, budget=100_000, reserve=1)
    assert not (target / "manifest.json").exists()


def test_clock_regression_prevents_capacity_forecast(tmp_path):
    store = Store(tmp_path, reserve=1)
    for ns in (121_000_000_000, 1_000_000_000, 241_000_000_000):
        store.append("frame", "PONG", received_ns=ns)
        store.rotate()
    store.close()
    result = capacity(config(tmp_path))
    assert result["sample"]["clock_regressions"] == 1
    assert result["compressed_bytes_per_second"] is None


def test_archive_reserve_preserves_originals(tmp_path):
    from collections import namedtuple

    root, target = tmp_path / "raw", tmp_path / "archive"
    sample(root)
    disk = namedtuple("Disk", "total used free")(10000, 9999, 1)
    with patch("midas.reality.operations.shutil.disk_usage", return_value=disk):
        with pytest.raises(OSError, match="reserve"):
            archive(root, target, budget=1_000_000, reserve=100)
    assert list(root.glob("*.seg"))
    assert not (target / "manifest.json").exists()


def test_capacity_status_clock_is_read_after_slow_sampling(tmp_path):
    from midas.reality.storage import records

    sample(tmp_path)
    clock = [121_000_000_000]

    def slow_records(*args, **kwargs):
        clock[0] += 2_000_000_000
        atomic_json(
            tmp_path / "status.json", dict(updated_ns=clock[0], state="RECORDING_UNSEQUENCED")
        )
        yield from records(*args, **kwargs)

    with (
        patch("midas.reality.operations.records", side_effect=slow_records),
        patch("midas.reality.operations.time.time_ns", side_effect=lambda: clock[0]),
    ):
        result = capacity(config(tmp_path))
    assert result["collector_status_age_seconds"] == 0
    assert "COLLECTOR_STATUS_STALE" not in result["alerts"]


def test_partial_storage_failure_remains_recoverable_open_tail(tmp_path):
    store = Store(tmp_path, reserve=1)
    store.append("frame", "PONG")
    original = store.file

    class FailingFile:
        def write(self, value):
            original.write(value[:10])
            original.flush()
            raise OSError("injected partial device write")

        def close(self):
            original.close()

    store.file = FailingFile()
    with pytest.raises(OSError, match="partial device"):
        store.append("frame", "never fully persisted")
    with pytest.raises(OSError, match="previously failed"):
        store.append("frame", "must not continue")
    store.close()
    assert list(tmp_path.glob("*.open"))
    assert not list(tmp_path.glob("*.seg"))
    recovered = Store(tmp_path, reserve=1)
    assert recovered.ordinal == 1
    assert recovered.recovered[0]["discarded_partial_bytes"] == 10
    recovered.close()
    assert list(tmp_path.glob("*.tail"))


def test_deferred_http_arrival_does_not_suppress_storage_forecast(tmp_path):
    store = Store(tmp_path, reserve=1)
    for kind, stamp in [
        ("frame", 1_000_000_000),
        ("frame", 121_000_000_000),
        ("independent_book", 120_000_000_000),
        ("frame", 181_000_000_000),
    ]:
        store.append(kind, "PONG", received_ns=stamp)
        store.rotate()
    store.close()
    result = capacity(config(tmp_path))
    assert result["sample"]["clock_regressions"] == 0
    assert result["sample"]["record_receipt_regressions"] == 1
    assert result["sample"]["seconds"] == 180
    assert result["compressed_bytes_per_second"] > 0
    assert "RATE_INSUFFICIENT_EVIDENCE" not in result["alerts"]
