"""Storage operations fixtures are artificial, never market evidence."""

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import midas.reality.operations as operations
import midas.reality.storage as storage
import pytest
from midas.reality.config import Config
from midas.reality.operations import (
    archive,
    archive_capacity,
    capacity,
    wait_for_archive_io_window,
)
from midas.reality.replay import replay
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
    assert result["capacity_builder_version"] == (
        "receipt-aware-capacity-v5-sustained-growth-windows"
    )
    expected_bytes = sum(
        s["bytes"] + (tmp_path / s["file"]).with_suffix(".json").stat().st_size
        for s in value["segments"]
    )
    assert result["sample"]["raw_frames"] == 2
    assert result["sample"]["raw_frame_payload_bytes"] == 8
    assert result["compressed_bytes_per_second"] == expected_bytes / 120
    assert result["raw_root_bytes"] == sum(p.stat().st_size for p in tmp_path.iterdir())
    assert result["retention_seconds_remaining"] == 30 * 86400 - 120
    assert result["configured_retention_seconds_remaining"] == 30 * 86400 - 120
    assert result["configured_capacity_runway_seconds"] == 30 * 86400 - 120
    assert (
        result["effective_capacity_runway_days"]
        == result["effective_capacity_runway_seconds"] / 86400
    )
    assert result["collector_status_age_seconds"] == 0
    assert result["estimated_action_deadline_ns"] > 121_000_000_000


def test_capacity_forecast_separates_sustained_windows_from_short_sample_burst(tmp_path):
    now = time.time_ns()
    store = Store(tmp_path, reserve=1)
    store.append("frame", "PONG", received_ns=now - 120 * 10**9)
    store.rotate()
    store.append("frame", "PONG", received_ns=now)
    store.rotate()
    store.close()
    atomic_json(tmp_path / "status.json", dict(updated_ns=now, state="RECORDING_UNSEQUENCED"))
    value = manifest(tmp_path)
    ages_hours = [
        25 if index == 0 else 12 if index == 1 else 5 for index in range(len(value["segments"]))
    ]
    for info, age_hours in zip(value["segments"], ages_hours, strict=True):
        segment = tmp_path / info["file"]
        catalog = segment.with_suffix(".json")
        stamp = now - age_hours * 3600 * 10**9
        os.utime(segment, ns=(stamp, stamp))
        os.utime(catalog, ns=(stamp, stamp))

    floor = 100
    result = capacity(
        config(tmp_path, budget_bytes=10_000, reserve_bytes=1, retention_days=100),
        now_ns=now,
        forecast_floor_bytes_per_day=floor,
    )
    six_hour = result["growth_windows"]["trailing_six_hours"]
    twenty_four_hour = result["growth_windows"]["trailing_twenty_four_hours"]
    window_bytes = [
        info["bytes"] + (tmp_path / info["file"]).with_suffix(".json").stat().st_size
        for info in value["segments"]
    ]
    six_hour_bytes = sum(
        size for size, age in zip(window_bytes, ages_hours, strict=True) if age <= 6
    )
    twenty_four_hour_bytes = sum(
        size for size, age in zip(window_bytes, ages_hours, strict=True) if age <= 24
    )
    assert six_hour["bytes"] == six_hour_bytes
    assert six_hour["coverage_seconds"] == 6 * 3600
    assert six_hour["bytes_per_day"] == six_hour_bytes * 4
    assert twenty_four_hour["bytes"] == twenty_four_hour_bytes
    assert twenty_four_hour["coverage_seconds"] == 24 * 3600
    assert twenty_four_hour["bytes_per_day"] == twenty_four_hour_bytes
    assert result["forecast_bytes_per_day"] == max(
        six_hour_bytes * 4, twenty_four_hour_bytes, floor
    )
    assert result["forecast_basis"] == (
        "maximum_of_trailing_six_hour_twenty_four_hour_and_configured_floor"
    )
    assert result["short_window_capacity_runway_days"] < result["configured_capacity_runway_days"]
    assert "SHORT_WINDOW_CAPACITY_WARNING_WITHIN_THIRTY_DAYS" in result["alerts"]
    assert "SHORT_WINDOW_CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS" in result["alerts"]
    assert "SHORT_WINDOW_CAPACITY_ACTION_WITHIN_SEVEN_DAYS" in result["alerts"]


def test_capacity_growth_clock_mismatch_falls_back_to_short_sample(tmp_path):
    value = sample(tmp_path)
    now = time.time_ns()
    for info in value["segments"]:
        segment = tmp_path / info["file"]
        stamp = now + 120 * 10**9
        os.utime(segment, ns=(stamp, stamp))
        os.utime(segment.with_suffix(".json"), ns=(stamp, stamp))

    result = capacity(
        config(tmp_path, reserve_bytes=1),
        now_ns=now,
    )
    assert result["growth_windows"]["trailing_six_hours"]["timestamp_state"] == (
        "future_timestamp_detected"
    )
    assert result["growth_windows"]["trailing_six_hours"]["bytes_per_day"] is None
    assert result["forecast_bytes_per_day"] == result["estimated_bytes_per_day"]
    assert result["forecast_basis"] == "recent_sample_fallback_no_valid_growth_windows"


def _archive_cgroup_tree(tmp_path, monkeypatch, services):
    archive_cgroup = (
        tmp_path
        / "user.slice"
        / "user-1000.slice"
        / "user@1000.service"
        / "app.slice"
        / "midas-reality-archive.service"
    )
    archive_cgroup.mkdir(parents=True)
    for name, (populated, pressure) in services.items():
        cgroup = archive_cgroup.parent / name
        cgroup.mkdir()
        (cgroup / "cgroup.events").write_text(f"populated {int(populated)}\nfrozen 0\n")
        if pressure is not None:
            (cgroup / "io.pressure").write_text(
                f"some avg10={pressure[0]} avg60={pressure[1]} avg300=0 total=0\n"
                f"full avg10={pressure[0]} avg60={pressure[1]} avg300=0 total=0\n"
            )
    monkeypatch.setattr(
        "midas.reality.operations._current_cgroup_directory", lambda: archive_cgroup
    )
    return archive_cgroup


def test_archive_io_admission_waits_for_a_stable_quiet_window(monkeypatch):
    values = iter(
        (
            {"midas-reality.service": (4.1, 3.0)},
            {"midas-reality.service": (1.9, 1.9)},
            {"midas-reality.service": (1.8, 1.7)},
        )
    )
    sleeps = []
    host_values = iter(((5.0, 5.0), (1.9, 1.9), (1.8, 1.7)))
    monkeypatch.setattr(
        "midas.reality.operations._active_midas_service_io_pressure", lambda: next(values)
    )
    monkeypatch.setattr(
        "midas.reality.operations._host_io_full_pressure", lambda: next(host_values)
    )
    monkeypatch.setattr("midas.reality.operations.time.sleep", sleeps.append)
    wait_for_archive_io_window(time.monotonic() + 30, stable_seconds=10)
    assert sleeps == [5.0, 5.0]


def test_archive_io_admission_fails_closed_at_deadline(monkeypatch):
    monkeypatch.setattr(
        "midas.reality.operations._active_midas_service_io_pressure",
        lambda: {"midas-reality.service": (3.0, 3.0)},
    )
    monkeypatch.setattr("midas.reality.operations._host_io_full_pressure", lambda: (0.0, 0.0))
    with pytest.raises(TimeoutError, match="did not clear"):
        wait_for_archive_io_window(time.monotonic() - 1)


def test_archive_io_admission_treats_host_pressure_as_advisory(monkeypatch):
    sleeps = []
    monkeypatch.setattr(
        "midas.reality.operations._active_midas_service_io_pressure",
        lambda: {"midas-reality.service": (0.0, 0.0)},
    )
    monkeypatch.setattr("midas.reality.operations._host_io_full_pressure", lambda: (3.0, 2.5))
    monkeypatch.setattr("midas.reality.operations.time.sleep", sleeps.append)

    wait_for_archive_io_window(time.monotonic() + 30)

    assert sleeps == []


def test_archive_io_admission_continues_when_advisory_host_telemetry_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "midas.reality.operations._active_midas_service_io_pressure",
        lambda: {"midas-reality.service": (0.0, 0.0)},
    )
    monkeypatch.setattr(
        "midas.reality.operations._host_io_full_pressure",
        lambda: (_ for _ in ()).throw(RuntimeError("host PSI unavailable")),
    )
    wait_for_archive_io_window(time.monotonic() + 30)


def test_archive_admission_tracks_active_midas_service_cgroups(tmp_path, monkeypatch):
    _archive_cgroup_tree(
        tmp_path,
        monkeypatch,
        {
            "midas-reality.service": (True, (0.2, 0.1)),
            "midas-api.service": (True, (0.4, 0.3)),
            "midas-web.service": (False, (0.0, 0.0)),
        },
    )
    assert operations._active_midas_service_io_pressure() == {
        "midas-reality.service": (0.2, 0.1),
        "midas-api.service": (0.4, 0.3),
    }


def test_archive_admission_requires_live_recorder_telemetry(tmp_path, monkeypatch):
    archive_cgroup = _archive_cgroup_tree(
        tmp_path,
        monkeypatch,
        {"midas-reality.service": (False, (0.0, 0.0))},
    )
    with pytest.raises(RuntimeError, match="not populated"):
        operations._active_midas_service_io_pressure()
    (archive_cgroup.parent / "midas-reality.service" / "cgroup.events").write_text(
        "populated 1\nfrozen 0\n"
    )
    (archive_cgroup.parent / "midas-reality.service" / "io.pressure").unlink()
    with pytest.raises(FileNotFoundError):
        operations._active_midas_service_io_pressure()


def test_archive_admission_wait_gets_fresh_per_window_deadline(tmp_path, monkeypatch):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    clock = [100.0]
    deadlines = []

    def monotonic():
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr("midas.reality.operations.time.monotonic", monotonic)
    monkeypatch.setattr(
        "midas.reality.operations.wait_for_archive_io_window",
        lambda deadline, **kwargs: deadlines.append(deadline),
    )
    archive(
        root,
        target,
        budget=1_000_000,
        reserve=1,
        resource_admission_timeout_seconds=100,
        operation_timeout_seconds=1_000,
    )

    assert len(deadlines) == 2 + 3 * len(value["segments"])
    assert all(deadlines[index + 1] > deadlines[index] for index in range(len(deadlines) - 1))


def test_replay_checks_resource_window_before_each_segment(tmp_path):
    value = sample(tmp_path)
    windows = []
    replay(tmp_path, value, before_segment=lambda: windows.append(True))
    assert windows == [True] * len(value["segments"])


def test_capacity_reports_last_started_budget_until_recorder_confirms_restart(tmp_path):
    sample(tmp_path)
    old_budget = 2 * 1024**2
    new_budget = 64 * 1024**2
    atomic_json(tmp_path / "config.json", {"budget_bytes": old_budget})
    atomic_json(
        tmp_path / "status.json",
        dict(
            updated_ns=121_000_000_000,
            state="RECORDING_UNSEQUENCED",
            config={"budget_bytes": old_budget},
        ),
    )

    pending = capacity(config(tmp_path, budget_bytes=new_budget), now_ns=121_000_000_000)
    assert pending["budget_bytes"] == old_budget
    assert pending["effective_budget_bytes"] == old_budget
    assert pending["configured_budget_bytes"] == new_budget
    assert pending["budget_change_pending_restart"] is True
    assert pending["configured_available_headroom_bytes"] > pending["available_headroom_bytes"]
    assert pending["configured_capacity_runway_days"] >= pending["effective_capacity_runway_days"]
    assert pending["budget_source"] == "collector_status+startup_config"
    assert "BUDGET_CHANGE_PENDING_RESTART" in pending["alerts"]

    atomic_json(tmp_path / "config.json", {"budget_bytes": new_budget})
    atomic_json(
        tmp_path / "status.json",
        dict(
            updated_ns=121_000_000_000,
            state="RECORDING_UNSEQUENCED",
            config={"budget_bytes": new_budget},
        ),
    )
    active = capacity(config(tmp_path, budget_bytes=new_budget), now_ns=121_000_000_000)
    assert active["budget_bytes"] == new_budget
    assert active["budget_change_pending_restart"] is False
    assert "BUDGET_CHANGE_PENDING_RESTART" not in active["alerts"]


def test_capacity_reports_last_started_retention_until_recorder_confirms_restart(tmp_path):
    sample(tmp_path)
    atomic_json(tmp_path / "config.json", {"retention_days": 90})
    atomic_json(
        tmp_path / "status.json",
        dict(
            updated_ns=121_000_000_000,
            state="RECORDING_UNSEQUENCED",
            config={"retention_days": 90},
        ),
    )

    pending = capacity(config(tmp_path, retention_days=105), now_ns=121_000_000_000)
    assert pending["retention_days"] == 90
    assert pending["effective_retention_days"] == 90
    assert pending["configured_retention_days"] == 105
    assert pending["retention_change_pending_restart"] is True
    assert pending["retention_seconds_remaining"] == 90 * 86400 - 120
    assert pending["configured_retention_seconds_remaining"] == 105 * 86400 - 120
    assert pending["configured_capacity_runway_seconds"] == 105 * 86400 - 120
    assert pending["retention_source"] == "collector_status+startup_config"
    assert "RETENTION_CHANGE_PENDING_RESTART" in pending["alerts"]
    assert pending["estimated_action_deadline_ns"] == 121_000_000_000 + int(
        (90 * 86400 - 120) * 1e9
    )

    atomic_json(tmp_path / "config.json", {"retention_days": 105})
    atomic_json(
        tmp_path / "status.json",
        dict(
            updated_ns=121_000_000_000,
            state="RECORDING_UNSEQUENCED",
            config={"retention_days": 105},
        ),
    )
    active = capacity(config(tmp_path, retention_days=105), now_ns=121_000_000_000)
    assert active["retention_days"] == 105
    assert active["retention_change_pending_restart"] is False
    assert active["retention_seconds_remaining"] == 105 * 86400 - 120
    assert active["configured_capacity_runway_seconds"] == 105 * 86400 - 120
    assert "RETENTION_CHANGE_PENDING_RESTART" not in active["alerts"]


def test_archive_capacity_checks_mount_budget_and_reserve(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    archive = tmp_path / "hdd" / "archive"
    raw.mkdir()
    archive.mkdir(parents=True)
    mountpoint = archive.parent

    class StatProxy:
        def __init__(self, value, device):
            self.value = value
            self.st_dev = device

        def __getattr__(self, name):
            return getattr(self.value, name)

    original_stat = Path.stat

    def separate_devices(path, *args, **kwargs):
        value = original_stat(path, *args, **kwargs)
        if path == raw:
            return StatProxy(value, 1)
        if path in {mountpoint, archive}:
            return StatProxy(value, 2)
        return value

    monkeypatch.setattr(Path, "stat", separate_devices)
    monkeypatch.setattr(Path, "is_mount", lambda path: path == mountpoint)

    class Disk:
        total = used = 0
        free = 500

    monkeypatch.setattr("midas.reality.operations.shutil.disk_usage", lambda _path: Disk())
    result = archive_capacity(
        raw,
        archive,
        mountpoint,
        budget=100,
        reserve=400,
        bytes_per_second=2,
        segment_bytes=8,
    )
    assert result["available_headroom_bytes"] == 100
    assert result["estimated_storage_seconds_remaining"] == 50
    assert result["destination_state"] == "NOT_YET_VERIFIED"
    assert "ARCHIVE_CAPACITY_WARNING_WITHIN_THIRTY_DAYS" in result["alerts"]
    assert "ARCHIVE_CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS" in result["alerts"]
    assert "ARCHIVE_CAPACITY_ACTION_WITHIN_SEVEN_DAYS" in result["alerts"]

    monkeypatch.setattr(Path, "is_mount", lambda _path: False)
    missing = archive_capacity(
        raw,
        archive,
        mountpoint,
        budget=100,
        reserve=400,
        bytes_per_second=2,
        segment_bytes=8,
    )
    assert missing["filesystem_free_bytes"] is None
    assert "ARCHIVE_MOUNT_UNAVAILABLE" in missing["alerts"]


def test_archive_capacity_uses_verified_catalog_sizes_without_statting_segments(
    tmp_path, monkeypatch
):
    raw = tmp_path / "raw"
    target = tmp_path / "hdd" / "archive"
    target.mkdir(parents=True)
    mountpoint = target.parent
    source = sample(raw)
    archived = archive(raw, target, budget=1_000_000, reserve=1)
    expected_segment_bytes = sum(info["bytes"] for info in source["segments"])
    expected_other_bytes = sum(
        path.stat().st_size for path in target.iterdir() if path.suffix != ".seg"
    )

    class StatProxy:
        def __init__(self, value, device):
            self.value = value
            self.st_dev = device

        def __getattr__(self, name):
            return getattr(self.value, name)

    original_stat = Path.stat

    def guarded_stat(path, *args, **kwargs):
        if path.parent == target and path.suffix == ".seg":
            raise AssertionError("capacity check statted a finalized archive segment")
        value = original_stat(path, *args, **kwargs)
        if path == raw:
            return StatProxy(value, 1)
        if path in {mountpoint, target}:
            return StatProxy(value, 2)
        return value

    monkeypatch.setattr(Path, "stat", guarded_stat)
    monkeypatch.setattr(Path, "is_mount", lambda path: path == mountpoint)

    class Disk:
        total = used = 0
        free = 2_000_000

    monkeypatch.setattr("midas.reality.operations.shutil.disk_usage", lambda _path: Disk())
    result = archive_capacity(
        raw,
        target,
        mountpoint,
        budget=1_000_000,
        reserve=1,
        bytes_per_second=2,
        segment_bytes=8,
    )

    assert archived["archival_provenance"]["verification_mode"] == "full_replay"
    assert result["destination_state"] == "MANIFEST_PRESENT"
    assert result["raw_archive_bytes"] == expected_segment_bytes + expected_other_bytes


def test_capacity_warns_thirty_days_ahead_and_marks_fourteen_day_critical(tmp_path):
    sample(tmp_path)
    used = sum(p.stat().st_size for p in tmp_path.iterdir() if p.is_file())
    sample_bytes = sum(
        segment["bytes"] + (tmp_path / segment["file"]).with_suffix(".json").stat().st_size
        for segment in manifest(tmp_path)["segments"][-120:]
    )
    rate = sample_bytes / 120

    warning = capacity(
        config(tmp_path, budget_bytes=used + int(rate * 25 * 86400), reserve_bytes=1),
        now_ns=121_000_000_000,
    )
    assert "CAPACITY_WARNING_WITHIN_THIRTY_DAYS" in warning["alerts"]
    assert "CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS" not in warning["alerts"]

    critical = capacity(
        config(tmp_path, budget_bytes=used + int(rate * 10 * 86400), reserve_bytes=1),
        now_ns=121_000_000_000,
    )
    assert "CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS" in critical["alerts"]


def test_capacity_forecast_floor_keeps_warning_when_recent_sample_falls(tmp_path):
    sample(tmp_path)
    used = sum(p.stat().st_size for p in tmp_path.iterdir() if p.is_file())
    sample_bytes = sum(
        segment["bytes"] + (tmp_path / segment["file"]).with_suffix(".json").stat().st_size
        for segment in manifest(tmp_path)["segments"][-120:]
    )
    measured_rate = sample_bytes / 120
    budget = used + int(measured_rate * 40 * 86400)

    result = capacity(
        config(tmp_path, budget_bytes=budget, reserve_bytes=1),
        now_ns=121_000_000_000,
        forecast_floor_bytes_per_day=int(measured_rate * 86400 * 2),
    )

    assert result["estimated_bytes_per_day"] == pytest.approx(measured_rate * 86400)
    assert result["forecast_bytes_per_day"] == pytest.approx(measured_rate * 86400 * 2)
    assert result["measured_storage_seconds_remaining"] == pytest.approx(40 * 86400)
    assert result["estimated_storage_seconds_remaining"] == pytest.approx(20 * 86400)
    assert "CAPACITY_WARNING_WITHIN_THIRTY_DAYS" in result["alerts"]


def test_capacity_floor_forecasts_when_recent_sample_is_too_short(tmp_path):
    store = Store(tmp_path, reserve=1)
    store.append("frame", "PONG", received_ns=1)
    store.close()

    result = capacity(
        config(tmp_path, budget_bytes=2_000_000_000, retention_days=30),
        forecast_floor_bytes_per_day=500_000_000,
    )

    assert result["estimated_bytes_per_day"] is None
    assert result["forecast_bytes_per_day"] == pytest.approx(500_000_000)
    assert result["estimated_storage_seconds_remaining"] is not None
    assert "RATE_INSUFFICIENT_EVIDENCE" in result["alerts"]


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
    before_full_check = json.loads((target / "manifest.json").read_text())
    incremental = archive(root, target, budget=1_000_000, reserve=1)
    assert incremental["archival_provenance"]["verification_mode"] == "incremental_suffix"
    current_manifest = json.loads((target / "manifest.json").read_text())
    assert current_manifest["segments"] == before_full_check["segments"]
    with pytest.raises(ValueError):
        archive(root, target, budget=1_000_000, reserve=1, full_verify=True)
    assert json.loads((target / "manifest.json").read_text()) == current_manifest


def test_archive_daily_append_verifies_only_new_suffix_and_retains_full_receipt(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    first_source = sample(root)
    first = archive(root, target, budget=1_000_000, reserve=1)
    original_full_verification = first["archival_provenance"]["full_verified_ns"]
    extended_source = sample(root)
    original_stat = Path.stat

    def no_old_archive_segment_stat(path, *args, **kwargs):
        if path.parent == target and path.suffix == ".seg":
            raise AssertionError("daily append statted the verified archive prefix")
        return original_stat(path, *args, **kwargs)

    with (
        patch.object(operations, "replay", side_effect=AssertionError("full replay repeated")),
        patch.object(Path, "stat", no_old_archive_segment_stat),
    ):
        extended = archive(root, target, budget=1_000_000, reserve=1)

    provenance = extended["archival_provenance"]
    prior_files = {info["file"] for info in first_source["segments"]}
    new_segments = [info for info in extended_source["segments"] if info["file"] not in prior_files]
    assert extended["segments"] == extended_source["segments"]
    assert provenance["verification_mode"] == "incremental_suffix"
    assert provenance["full_verified_ns"] == original_full_verification
    assert provenance["incremental_verified_segments"] == len(new_segments)
    assert provenance["incremental_verified_bytes"] == sum(info["bytes"] for info in new_segments)
    assert (
        provenance["full_verified_manifest_sha256"]
        == first["archival_provenance"]["full_verified_manifest_sha256"]
    )

    replay_roots = []
    actual_replay = operations.replay

    def track_replay(path, value, *args, **kwargs):
        replay_roots.append(path.resolve())
        return actual_replay(path, value, *args, **kwargs)

    with patch.object(operations, "replay", side_effect=track_replay):
        forced_full = archive(root, target, budget=1_000_000, reserve=1, full_verify=True)
    assert forced_full["archival_provenance"]["verification_mode"] == "full_replay"
    assert forced_full["archival_provenance"]["full_verified_ns"] >= original_full_verification
    assert replay_roots == [root.resolve(), target.resolve()]


def test_archive_migrates_legacy_full_manifest_to_incremental_identity_receipt(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    old_ids = iter(("1" * 32, "2" * 32, "f" * 32))
    with patch.object(
        storage.uuid,
        "uuid4",
        side_effect=lambda: SimpleNamespace(hex=next(old_ids)),
    ):
        sample(root)
    full = archive(root, target, budget=1_000_000, reserve=1)
    legacy = json.loads((target / "manifest.json").read_text())
    for field in (
        "full_verified_ns",
        "incremental_verified_ns",
        "incremental_verified_segments",
        "incremental_verified_bytes",
        "verification_mode",
    ):
        legacy["archival_provenance"].pop(field, None)
    atomic_json(target / "manifest.json", legacy)
    with patch.object(storage.uuid, "uuid4", return_value=SimpleNamespace(hex="0" * 32)):
        source = sample(root)
    newly_inserted = next(
        info for info in source["segments"] if info["count"] and info["first"] == 3
    )
    prior_empty = next(info for info in full["segments"] if info["count"] == 0)
    assert newly_inserted["file"] < prior_empty["file"]

    with patch.object(operations, "replay", side_effect=AssertionError("legacy prefix replayed")):
        extended = archive(root, target, budget=1_000_000, reserve=1)

    provenance = extended["archival_provenance"]
    assert extended["segments"] == source["segments"]
    assert provenance["full_verified_ns"] == full["archival_provenance"]["verified_ns"]
    assert provenance["verification_mode"] == "incremental_suffix"
    assert (
        provenance["full_verified_manifest_sha256"]
        == full["archival_provenance"]["source_manifest_sha256"]
    )


def test_archive_retains_full_receipt_after_incremental_manifest_ages(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    sample(root)
    archive(root, target, budget=1_000_000, reserve=1)
    legacy = json.loads((target / "manifest.json").read_text())
    for field in (
        "full_verified_ns",
        "incremental_verified_ns",
        "incremental_verified_segments",
        "incremental_verified_bytes",
        "verification_mode",
    ):
        legacy["archival_provenance"].pop(field, None)
    legacy["archival_provenance"]["verified_ns"] = time.time_ns() - 2 * 24 * 60 * 60 * 1_000_000_000
    atomic_json(target / "manifest.json", legacy)

    extended = archive(root, target, budget=1_000_000, reserve=1)
    provenance = extended["archival_provenance"]
    assert provenance["verification_mode"] == "incremental_suffix"
    assert provenance["full_verified_ns"] == legacy["archival_provenance"]["verified_ns"]


def test_archive_replay_verifies_source_and_destination_without_per_segment_sync(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    sample(root)
    replay_roots = []
    sync_roots = []
    actual_replay = operations.replay
    actual_sync = storage.sync_dir

    def track_replay(path, value, *args, **kwargs):
        replay_roots.append(path.resolve())
        return actual_replay(path, value, *args, **kwargs)

    def track_sync(path):
        sync_roots.append(path.resolve())
        actual_sync(path)

    with (
        patch.object(operations, "replay", side_effect=track_replay),
        patch.object(operations, "describe", side_effect=AssertionError("redundant segment scan")),
        patch.object(storage, "sync_dir", side_effect=track_sync),
    ):
        archive(root, target, budget=1_000_000, reserve=1)

    assert replay_roots == [root.resolve(), target.resolve()]
    # The source identity and final manifest each sync the directory. Individual
    # segment renames do not issue a journal commit; final replay validates them.
    assert sync_roots == [target.resolve(), target.resolve()]


def test_archive_flushes_copied_segments_in_bounded_filesystem_batches(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    flushes = []

    with patch.object(operations, "sync_filesystem", side_effect=flushes.append):
        archive(root, target, budget=1_000_000, reserve=1)

    assert flushes == [target.resolve()]
    assert not list(target.glob("*.copying"))
    assert json.loads((target / "manifest.json").read_text())["segments"] == value["segments"]


def test_archive_resume_after_filesystem_flush_failure_keeps_source_and_retries(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    with patch.object(operations, "sync_filesystem", side_effect=OSError("flush interrupted")):
        with pytest.raises(OSError, match="flush interrupted"):
            archive(root, target, budget=1_000_000, reserve=1)

    assert not (target / "manifest.json").exists()
    assert not any((target / segment["file"]).exists() for segment in value["segments"])
    assert list(target.glob("*.copying"))

    with patch.object(operations, "sync_filesystem") as flush:
        result = archive(root, target, budget=1_000_000, reserve=1)

    assert flush.call_count == 1
    assert result["segments"] == value["segments"]
    assert not list(target.glob("*.copying"))


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

    original_scandir = os.scandir
    destination_scandir_calls = 0

    def counted_scandir(path):
        nonlocal destination_scandir_calls
        if Path(path) == target:
            destination_scandir_calls += 1
        return original_scandir(path)

    with patch.object(operations.os, "scandir", counted_scandir):
        result = archive(root, target, budget=1_000_000, reserve=1)

    assert destination_scandir_calls == 1
    assert result["segments"] == value["segments"]
    for name, digest in original_hashes.items():
        assert file_hash(root / name) == file_hash(target / name) == digest


def test_archive_budget_failure_resumes_without_publishing(tmp_path):
    root, target = tmp_path / "raw", tmp_path / "archive"
    value = sample(root)
    with pytest.raises(OSError, match="budget"):
        archive(root, target, budget=1, reserve=1)
    assert not (target / "manifest.json").exists()
    name = value["segments"][0]["file"]
    (target / Path(name).with_suffix(".copying")).write_bytes(b"interrupted")
    result = archive(root, target, budget=1_000_000, reserve=1)
    assert len(result["segments"]) == len(value["segments"])
    assert not list(target.glob("*.copying"))


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
