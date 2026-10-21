"""Deployment guards must fail before mutating the recorder or its observations."""

import hashlib
import json
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import call, patch

import pytest
from midas.reality.config import Config

from scripts.reality_deployment import (
    PRODUCTION_CONFIG,
    PRODUCTION_PYTHON,
    PRODUCTION_WORKSPACE,
    SERVICE_UNIT_SOURCE,
    _validate_service_configuration,
    apply,
    deployment_tool_hash,
    preflight,
    recovery_monitor_paths,
    service_unit_hash,
    source_hash,
    storage_capacity,
    validate_recovery_prefix,
    verification_environment,
    verification_tool,
    verify,
)


def _service_state(tmp_path, monkeypatch):
    fragment = tmp_path / "home/.config/systemd/user/midas-reality.service"
    fragment.parent.mkdir(parents=True)
    fragment.write_bytes(SERVICE_UNIT_SOURCE.read_bytes())
    drop_in = tmp_path / "home/.config/systemd/user.control/midas-reality.service.d/limits.conf"
    drop_in.parent.mkdir(parents=True)
    drop_in.write_text("[Service]\nMemorySwapMax=0\n")
    monkeypatch.setattr("scripts.reality_deployment.SERVICE_UNIT_TARGET", fragment)
    return dict(
        FragmentPath=str(fragment),
        DropInPaths=str(drop_in),
        MemoryHigh=str(1152 * 1024**2),
        MemoryMax=str(1280 * 1024**2),
        MemorySwapMax="0",
        CPUQuotaPerSecUSec="250ms",
        TasksMax="32",
        Restart="on-failure",
        ExecStart=(
            f"{{ path={PRODUCTION_PYTHON} ; argv[]={PRODUCTION_PYTHON} -m midas.reality "
            f"record --config {PRODUCTION_CONFIG} ; ignore_errors=no }}"
        ),
        WorkingDirectory=str(PRODUCTION_WORKSPACE),
        Environment="PYTHONUNBUFFERED=1",
        EnvironmentFiles="",
        User="",
    )


def test_unverified_or_changed_implementation_rejected_first():
    current = Config()
    canary = replace(current, root=current.root + "-canary")
    for receipt in ({}, dict(passed=False), dict(passed=True, source_sha256="wrong")):
        with pytest.raises(ValueError, match="Checks missing"):
            preflight(current, canary, receipt, 1024, current.reserve_bytes)


def test_recovery_monitor_paths_accept_any_attempt_and_reject_symlinks(tmp_path):
    attempt = tmp_path / "cold-attempt-1-monitor.jsonl"
    attempt.write_text('{"event":"sample"}\n')
    assert recovery_monitor_paths(tmp_path) == [attempt]

    unsafe = tmp_path / "cold-attempt-2-monitor.jsonl"
    unsafe.symlink_to(attempt)
    with pytest.raises(ValueError, match="monitor receipt is unsafe"):
        recovery_monitor_paths(tmp_path)


def test_verification_environment_prioritizes_disposable_worktree(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.reality_deployment.WORKSPACE", tmp_path)
    monkeypatch.setenv("PYTHONPATH", "/production:/production/packages")
    paths = verification_environment()["PYTHONPATH"].split(":")
    assert paths[:2] == [str(tmp_path), str(tmp_path / "packages")]
    assert paths[2:] == ["/production", "/production/packages"]


def test_verification_tool_uses_interpreter_sibling_before_path(tmp_path, monkeypatch):
    interpreter = tmp_path / "venv/bin/python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\nexit 0\n")
    ruff = interpreter.with_name("ruff")
    ruff.write_text("#!/bin/sh\nexit 0\n")
    ruff.chmod(0o755)
    monkeypatch.setattr("scripts.reality_deployment.sys.executable", str(interpreter))
    monkeypatch.setattr("scripts.reality_deployment.shutil.which", lambda _name: None)
    assert verification_tool("ruff") == str(ruff)

    with pytest.raises(ValueError, match="unavailable"):
        verification_tool("mypy")
    mypy_found = "/opt/verified-env/bin/mypy"
    monkeypatch.setattr("scripts.reality_deployment.shutil.which", lambda _name: mypy_found)
    assert verification_tool("mypy") == mypy_found
    with pytest.raises(ValueError, match="single executable name"):
        verification_tool("../mypy")


def test_verify_creates_receipt_directory_and_binds_tool_identity(tmp_path):
    from types import SimpleNamespace

    output = tmp_path / "new/reliability/checks.json"
    with patch(
        "scripts.reality_deployment.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    ) as run:
        receipt = verify(output)
    assert receipt["passed"] is True
    assert len(run.call_args_list) == 4
    assert json.loads(output.read_text())["deployment_tool_sha256"] == deployment_tool_hash()


def test_storage_capacity_enforces_raw_and_archive_reserves_separately(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    mount = tmp_path / "archive-volume"
    archive = mount / "reality"
    raw.mkdir()
    archive.mkdir(parents=True)
    (raw / "0001.seg").write_bytes(b"x" * 100)
    monkeypatch.setattr("scripts.reality_deployment.os.path.ismount", lambda path: True)
    monkeypatch.setattr(
        "scripts.reality_deployment.shutil.disk_usage",
        lambda path: type("Usage", (), {"free": 2000 if Path(path) == raw else 500})(),
    )
    value = storage_capacity(
        raw,
        archive,
        mount,
        raw_budget_bytes=1000,
        raw_reserve_bytes=900,
        archive_budget_bytes=200,
        archive_reserve_bytes=300,
    )
    assert value["raw_remaining_budget_bytes"] == 900
    assert value["archive_free_bytes"] == 500

    monkeypatch.setattr(
        "scripts.reality_deployment.shutil.disk_usage",
        lambda path: type("Usage", (), {"free": 2000 if Path(path) == raw else 499})(),
    )
    with pytest.raises(ValueError, match="archive commitment"):
        storage_capacity(
            raw,
            archive,
            mount,
            raw_budget_bytes=1000,
            raw_reserve_bytes=900,
            archive_budget_bytes=200,
            archive_reserve_bytes=300,
        )


def test_unisolated_and_unexercised_settings_rejected():
    config = Config()
    receipt = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        completed_ns=time.time_ns(),
    )
    with pytest.raises(ValueError, match="isolated"):
        preflight(config, config, receipt, 1024, config.reserve_bytes)
    with pytest.raises(ValueError, match="settings"):
        preflight(
            config,
            replace(config, root=config.root + "-canary", markets=8),
            receipt,
            1024,
            config.reserve_bytes,
        )


def test_preflight_requires_source_unit_and_effective_limits(tmp_path, monkeypatch):
    unit = _service_state(tmp_path, monkeypatch)
    identity = _validate_service_configuration(unit)
    assert identity["fragment_sha256"] == service_unit_hash()
    unit["ExecStart"] = "{ path=/tmp/other-python ; argv[]=/tmp/other-python -m other }"
    with pytest.raises(ValueError, match="executable or module arguments"):
        _validate_service_configuration(unit)
    unit["ExecStart"] = (
        f"{{ path={PRODUCTION_PYTHON} ; argv[]={PRODUCTION_PYTHON} -m midas.reality "
        f"record --config {PRODUCTION_CONFIG} ; ignore_errors=no }}"
    )
    unit["MemoryMax"] = str(512 * 1024**2)
    with pytest.raises(ValueError, match="resource limits"):
        _validate_service_configuration(unit)
    unit["MemoryMax"] = str(1280 * 1024**2)
    fragment = tmp_path / "home/.config/systemd/user/midas-reality.service"
    fragment.write_text("[Service]\nMemoryMax=512M\n")
    with pytest.raises(ValueError, match="differs from verified source"):
        _validate_service_configuration(unit)


def test_preflight_allows_isolated_candidate_when_production_source_is_older(tmp_path, monkeypatch):
    current = Config()
    canary = replace(current, root=current.root + "-canary")
    receipt = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        completed_ns=time.time_ns(),
    )
    service_state = _service_state(tmp_path, monkeypatch)
    with (
        patch("scripts.reality_deployment.service", return_value=service_state),
        patch("scripts.reality_deployment.production_source_hash", return_value="older-production"),
        patch(
            "scripts.reality_deployment.runtime_release_evidence",
            return_value={"source_sha256": source_hash()},
        ),
    ):
        with pytest.raises(ValueError, match="Full-scale recovery evidence is required"):
            preflight(current, canary, receipt, 1024, current.reserve_bytes)


def test_preflight_rejects_recovery_receipt_for_stale_source_boundary(tmp_path):
    current = Config()
    canary = replace(current, root=current.root + "-canary")
    catalog = dict(
        schema_version=1,
        format="midas-reality-framed-zlib-v1",
        ordering="durable ordinal then frame array index",
        segments=[],
    )
    receipt = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        completed_ns=time.time_ns(),
    )
    with (
        patch("scripts.reality_deployment.service", return_value={"ActiveState": "active"}),
        patch("scripts.reality_deployment._validate_service_configuration", return_value={}),
        patch("scripts.reality_deployment.production_source_hash", return_value="older-production"),
        patch(
            "scripts.reality_deployment.runtime_release_evidence",
            return_value={"source_sha256": source_hash()},
        ),
        patch(
            "scripts.reality_deployment.recovery_resource_evidence",
            return_value={"source_root": current.root, "catalog_sha256": "stale-boundary"},
        ),
        patch("scripts.reality_deployment.manifest", return_value=catalog),
        patch(
            "scripts.reality_deployment.validate_recovery_prefix",
            side_effect=ValueError("Full-scale recovery source prefix differs"),
        ),
    ):
        with pytest.raises(ValueError, match="source prefix differs"):
            preflight(
                current,
                canary,
                receipt,
                1024,
                current.reserve_bytes,
                recovery_evidence_root=tmp_path,
            )


def test_recovery_evidence_must_match_an_unchanged_source_prefix(tmp_path):
    from midas.reality.storage import canonical

    first = dict(
        schema_version=1,
        file="00000000000000000001-fixture.seg",
        sha256=hashlib.sha256(b"data").hexdigest(),
        bytes=4,
        first=1,
        last=1,
        count=1,
        kinds={"frame": 1},
    )

    def add_segment(info, payload):
        path = tmp_path / info["file"]
        path.write_bytes(payload)
        path.with_suffix(".json").write_text(json.dumps(info, separators=(",", ":")))
        return path

    first_path = add_segment(first, b"data")
    stat = first_path.stat()
    sidecar_bytes = first_path.with_suffix(".json").read_bytes()
    identities = [
        dict(
            file=first["file"],
            device=stat.st_dev,
            inode=stat.st_ino,
            size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            sidecar_sha256=hashlib.sha256(sidecar_bytes).hexdigest(),
        )
    ]
    catalog = dict(
        schema_version=1,
        format="midas-reality-framed-zlib-v1",
        ordering="durable ordinal then frame array index",
        segments=[first],
    )
    evidence = dict(
        source_root=str(tmp_path),
        segment_count=1,
        last_ordinal=1,
        archive_bytes=4,
        catalog_sha256=hashlib.sha256(canonical(catalog)).hexdigest(),
        identities_sha256=hashlib.sha256(canonical(identities)).hexdigest(),
    )
    assert validate_recovery_prefix(tmp_path, catalog, evidence)["appended_finalized_segments"] == 0

    second = dict(first, file="00000000000000000002-fixture.seg", first=2, last=2)
    add_segment(second, b"next")
    extended_catalog = dict(catalog, segments=[first, second])
    assert (
        validate_recovery_prefix(tmp_path, extended_catalog, evidence)[
            "appended_finalized_segments"
        ]
        == 1
    )
    first_path.write_bytes(b"edit")
    with pytest.raises(ValueError, match="files changed"):
        validate_recovery_prefix(tmp_path, extended_catalog, evidence)


def test_apply_expired_gate_never_writes_or_restarts(tmp_path):
    config = Config()
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        production_source_sha256=source_hash(),
        candidate_runtime={"source_sha256": source_hash()},
        candidate=config.dump(),
        checked_ns=0,
        production_before={},
        production_unit_config={},
    )
    with (
        patch("scripts.reality_deployment.production_source_hash", return_value=source_hash()),
        patch(
            "scripts.reality_deployment.runtime_release_evidence",
            return_value=gate["candidate_runtime"],
        ),
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="expired"):
            apply(
                config,
                gate,
                tmp_path / "config.json",
                tmp_path / "result.json",
                protected_restart_approved=True,
            )
    write.assert_not_called()
    restart.assert_not_called()


def test_apply_changed_process_never_writes_or_restarts(tmp_path):
    config = Config()
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        production_source_sha256=source_hash(),
        candidate_runtime={"source_sha256": source_hash()},
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=dict(MainPID="123"),
        production_unit_config={},
        recovery_prefix={},
        recovery_evidence=dict(
            root=str(tmp_path),
            evidence_sha256="fixture",
            measured_startup_peak_bytes=1024,
            checkpoint_sha256="fixture-checkpoint",
        ),
    )
    with (
        patch("scripts.reality_deployment.production_source_hash", return_value=source_hash()),
        patch(
            "scripts.reality_deployment.runtime_release_evidence",
            return_value=gate["candidate_runtime"],
        ),
        patch("scripts.reality_deployment.service", return_value=dict(MainPID="124")),
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="process changed"):
            apply(
                config,
                gate,
                tmp_path / "config.json",
                tmp_path / "result.json",
                protected_restart_approved=True,
            )
    write.assert_not_called()
    restart.assert_not_called()


def test_apply_invalid_health_window_cannot_mutate(tmp_path):
    with (
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="readiness window"):
            apply(
                Config(),
                {},
                tmp_path / "config.json",
                tmp_path / "result.json",
                health_timeout_seconds=0,
            )
    write.assert_not_called()
    restart.assert_not_called()


def test_apply_requires_explicit_protected_restart_approval(tmp_path):
    with (
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="requires explicit approval"):
            apply(Config(), {}, tmp_path / "config.json", tmp_path / "result.json")
    write.assert_not_called()
    restart.assert_not_called()


def test_apply_timeout_keeps_one_shot_guard_and_never_restarts_back(tmp_path, monkeypatch):
    config = Config()
    config_path = tmp_path / "reality.json"
    config_path.write_text(json.dumps(config.dump()))
    output = tmp_path / "deployment.json"
    initial_service_state = _service_state(tmp_path, monkeypatch)
    initial_service_state.update(MainPID="123", ActiveState="active", ControlGroup="")
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        production_source_sha256=source_hash(),
        candidate_runtime={"source_sha256": source_hash()},
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=initial_service_state,
        production_unit_config=_validate_service_configuration(initial_service_state),
        production_runtime_config=config.dump(),
        recovery_prefix={},
        recovery_evidence=dict(
            root=str(tmp_path),
            evidence_sha256="fixture",
            measured_startup_peak_bytes=1024,
            checkpoint_sha256="fixture-checkpoint",
        ),
        protected_disk_reserve_bytes=config.reserve_bytes,
        storage_capacity=dict(
            raw_root=str(config.root),
            archive_root=str(tmp_path),
            archive_mountpoint=str(tmp_path),
            raw_budget_bytes=config.budget_bytes,
            raw_reserve_bytes=config.reserve_bytes,
            archive_budget_bytes=1024,
            archive_reserve_bytes=1024,
        ),
    )
    service_state = dict(
        initial_service_state,
        MainPID="456",
        NRestarts="0",
        ActiveState="active",
        Restart="no",
    )
    events = []

    def record_write(path, _value):
        events.append(("write", path))

    def record_systemctl(args, *, check):
        assert check
        events.append(("systemctl", args[-1]))

    with (
        patch("scripts.reality_deployment.production_source_hash", return_value=source_hash()),
        patch(
            "scripts.reality_deployment.runtime_release_evidence",
            return_value=gate["candidate_runtime"],
        ),
        patch(
            "scripts.reality_deployment.service",
            side_effect=[
                dict(service_state, MainPID="123", Restart="on-failure"),
                dict(service_state, MainPID="0", ActiveState="inactive"),
                dict(service_state, MainPID="0", ActiveState="inactive"),
                service_state,
                service_state,
                service_state,
            ],
        ),
        patch(
            "scripts.reality_deployment.recovery_resource_evidence",
            return_value=gate["recovery_evidence"],
        ),
        patch("scripts.reality_deployment.validate_recovery_prefix", return_value={}),
        patch("scripts.reality_deployment.require_restart_safe", return_value={}),
        patch(
            "scripts.reality_deployment.storage_capacity",
            return_value=gate["storage_capacity"],
        ),
        patch(
            "scripts.reality_deployment._install_recovery_checkpoint",
            return_value=tmp_path / "installed-checkpoint",
        ),
        patch(
            "scripts.reality_deployment._install_candidate_runtime_dropin",
            return_value=tmp_path / "runtime-dropin",
        ),
        patch(
            "scripts.reality_deployment._validate_candidate_runtime_configuration",
            return_value={},
        ),
        patch(
            "scripts.reality_deployment._load_runtime_status",
            return_value={"config": config.dump()},
        ),
        patch("scripts.reality_deployment._install_restart_guard", return_value=tmp_path / "guard"),
        patch("scripts.reality_deployment._remove_restart_guard") as remove_guard,
        patch("scripts.reality_deployment.atomic_json", side_effect=record_write) as write,
        patch("scripts.reality_deployment.subprocess.run", side_effect=record_systemctl) as restart,
        patch("scripts.reality_deployment.time.monotonic", side_effect=[0, 0, 2401]),
        patch("scripts.reality_deployment.time.sleep"),
    ):
        with pytest.raises(ValueError, match="no retry or rollback"):
            apply(
                config,
                gate,
                config_path,
                output,
                protected_restart_approved=True,
                health_timeout_seconds=2400,
            )

    assert restart.call_args_list == [
        call(["systemctl", "--user", "stop", "midas-reality.service"], check=True),
        call(["systemctl", "--user", "start", "midas-reality.service"], check=True),
    ]
    remove_guard.assert_not_called()
    config_writes = [call for call in write.call_args_list if call.args[0] == config_path]
    assert len(config_writes) == 1
    assert config_writes[0].args[1] == config.dump()
    stop_index = events.index(("systemctl", "midas-reality.service"))
    config_index = events.index(("write", config_path))
    start_index = len(events) - 1 - events[::-1].index(("systemctl", "midas-reality.service"))
    assert stop_index < config_index < start_index


def test_apply_resource_rejection_precedes_config_or_service_mutation(tmp_path, monkeypatch):
    initial = _service_state(tmp_path, monkeypatch)
    initial.update(MainPID="123", ActiveState="active", ControlGroup="/fixture")
    config = Config()
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        production_source_sha256=source_hash(),
        candidate_runtime={"source_sha256": source_hash()},
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=initial,
        production_unit_config=_validate_service_configuration(initial),
        production_runtime_config=config.dump(),
        recovery_prefix={},
        recovery_evidence=dict(
            root=str(tmp_path),
            evidence_sha256="fixture",
            measured_startup_peak_bytes=1024,
            checkpoint_sha256="fixture-checkpoint",
        ),
        protected_disk_reserve_bytes=config.reserve_bytes,
        storage_capacity=dict(
            raw_root=str(config.root),
            archive_root=str(tmp_path),
            archive_mountpoint=str(tmp_path),
            raw_budget_bytes=config.budget_bytes,
            raw_reserve_bytes=config.reserve_bytes,
            archive_budget_bytes=1024,
            archive_reserve_bytes=1024,
        ),
    )
    with (
        patch("scripts.reality_deployment.production_source_hash", return_value=source_hash()),
        patch(
            "scripts.reality_deployment.runtime_release_evidence",
            return_value=gate["candidate_runtime"],
        ),
        patch("scripts.reality_deployment.service", return_value=initial),
        patch(
            "scripts.reality_deployment.recovery_resource_evidence",
            return_value=gate["recovery_evidence"],
        ),
        patch("scripts.reality_deployment.validate_recovery_prefix", return_value={}),
        patch(
            "scripts.reality_deployment.require_restart_safe",
            side_effect=ValueError("resource gate"),
        ),
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as mutate,
    ):
        with pytest.raises(ValueError, match="resource gate"):
            apply(
                config,
                gate,
                tmp_path / "missing-config.json",
                tmp_path / "result.json",
                protected_restart_approved=True,
            )
    write.assert_not_called()
    mutate.assert_not_called()
