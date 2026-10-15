"""Deployment guards must fail before mutating the recorder or its observations."""

import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from midas.reality.config import Config

from scripts.reality_deployment import apply, preflight, source_hash


def fixture_config() -> Config:
    root = Path(__file__).resolve().parents[1] / "data" / "recordings" / "reality-test-fixture"
    return Config(root=str(root))


def test_unverified_or_changed_implementation_rejected_first():
    current = fixture_config()
    canary = replace(current, root=current.root + "-canary")
    for receipt in ({}, dict(passed=False), dict(passed=True, source_sha256="wrong")):
        with pytest.raises(ValueError, match="Checks missing"):
            preflight(current, canary, receipt, 1024, current.reserve_bytes)


def test_unisolated_and_unexercised_settings_rejected():
    config = fixture_config()
    receipt = dict(passed=True, source_sha256=source_hash(), completed_ns=time.time_ns())
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
    config = fixture_config()
    gate = dict(passed=True, source_sha256=source_hash(), candidate=config.dump(), checked_ns=0)
    with (
        patch("scripts.reality_deployment.atomic_json") as write,
        patch("scripts.reality_deployment.subprocess.run") as restart,
    ):
        with pytest.raises(ValueError, match="expired"):
            apply(config, gate, tmp_path / "config.json", tmp_path / "result.json")
    write.assert_not_called()
    restart.assert_not_called()


def test_apply_changed_process_never_writes_or_restarts(tmp_path):
    config = fixture_config()
    gate = dict(
        passed=True,
        source_sha256=source_hash(),
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
        with pytest.raises(ValueError, match="health window"):
            apply(
                fixture_config(),
                {},
                tmp_path / "config.json",
                tmp_path / "result.json",
                health_timeout_seconds=0,
            )
    write.assert_not_called()
    restart.assert_not_called()
