"""Deployment guards must fail before mutating the recorder or its observations."""

import json
import time
from dataclasses import replace
from unittest.mock import patch

import pytest
from midas.reality.config import Config

from scripts.reality_deployment import apply, deployment_tool_hash, preflight, source_hash


def test_unverified_or_changed_implementation_rejected_first():
    current = Config()
    canary = replace(current, root=current.root + "-canary")
    for receipt in ({}, dict(passed=False), dict(passed=True, source_sha256="wrong")):
        with pytest.raises(ValueError, match="Checks missing"):
            preflight(current, canary, receipt, 1024, current.reserve_bytes)


def test_unisolated_and_unexercised_settings_rejected():
    config = Config()
    receipt = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
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


def test_apply_expired_gate_never_writes_or_restarts(tmp_path):
    config = Config()
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        candidate=config.dump(),
        checked_ns=0,
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
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=dict(MainPID="123"),
    )
    with (
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


def test_apply_timeout_keeps_one_shot_guard_and_never_restarts_back(tmp_path):
    config = Config()
    config_path = tmp_path / "reality.json"
    config_path.write_text(json.dumps(config.dump()))
    output = tmp_path / "deployment.json"
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
        deployment_tool_sha256=deployment_tool_hash(),
        candidate=config.dump(),
        checked_ns=time.time_ns(),
        production_before=dict(MainPID="123"),
    )
    service_state = dict(
        MainPID="456",
        NRestarts="0",
        ActiveState="active",
        Restart="no",
        ControlGroup="",
    )
    with (
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
