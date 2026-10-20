"""Deployment guards must fail before mutating the recorder or its observations."""

import json
import time
from dataclasses import replace
from unittest.mock import patch

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
    service_unit_hash,
    source_hash,
    verification_environment,
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
        MemoryHigh=str(704 * 1024**2),
        MemoryMax=str(768 * 1024**2),
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


def test_verification_environment_prioritizes_disposable_worktree(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.reality_deployment.WORKSPACE", tmp_path)
    monkeypatch.setenv("PYTHONPATH", "/production:/production/packages")
    paths = verification_environment()["PYTHONPATH"].split(":")
    assert paths[:2] == [str(tmp_path), str(tmp_path / "packages")]
    assert paths[2:] == ["/production", "/production/packages"]


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
    unit["MemoryMax"] = str(768 * 1024**2)
    fragment = tmp_path / "home/.config/systemd/user/midas-reality.service"
    fragment.write_text("[Service]\nMemoryMax=512M\n")
    with pytest.raises(ValueError, match="differs from verified source"):
        _validate_service_configuration(unit)


def test_preflight_rejects_production_package_source_drift(tmp_path, monkeypatch):
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
        patch("scripts.reality_deployment.production_source_hash", return_value="drifted"),
    ):
        with pytest.raises(ValueError, match="package source differs"):
            preflight(current, canary, receipt, 1024, current.reserve_bytes)


def test_apply_expired_gate_never_writes_or_restarts(tmp_path):
    config = Config()
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        systemd_unit_sha256=service_unit_hash(),
        production_source_sha256=source_hash(),
        candidate=config.dump(),
        checked_ns=0,
        production_before={},
        production_unit_config={},
    )
    with (
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="expired"):
            apply(config, gate, tmp_path / "config.json", tmp_path / "result.json")
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
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=dict(MainPID="123"),
        production_unit_config={},
    )
    with (
        patch("scripts.reality_deployment.production_source_hash", return_value=source_hash()),
        patch("scripts.reality_deployment.service", return_value=dict(MainPID="124")),
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="process changed"):
            apply(config, gate, tmp_path / "config.json", tmp_path / "result.json")
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
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=initial_service_state,
        production_unit_config=_validate_service_configuration(initial_service_state),
    )
    service_state = dict(
        initial_service_state,
        MainPID="456",
        NRestarts="0",
        ActiveState="active",
        Restart="no",
    )
    with (
        patch("scripts.reality_deployment.production_source_hash", return_value=source_hash()),
        patch("scripts.reality_deployment.service", side_effect=[
            dict(service_state, MainPID="123", Restart="on-failure"),
            service_state,
            service_state,
            service_state,
        ]),
        patch("scripts.reality_deployment._install_restart_guard", return_value=tmp_path / "guard"),
        patch("scripts.reality_deployment._remove_restart_guard") as remove_guard,
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
            patch("scripts.reality_deployment.time.monotonic", side_effect=[0, 0, 2401]),
        patch("scripts.reality_deployment.time.sleep"),
    ):
        with pytest.raises(ValueError, match="no retry or rollback"):
            apply(config, gate, config_path, output, health_timeout_seconds=2400)

    restart.assert_called_once_with(
        ["systemctl", "--user", "restart", "midas-reality.service"], check=True
    )
    remove_guard.assert_not_called()
    config_writes = [call for call in write.call_args_list if call.args[0] == config_path]
    assert len(config_writes) == 1
    assert config_writes[0].args[1] == config.dump()
