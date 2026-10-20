from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from reality_staging_admission import validate_staging_admission


def _sample() -> dict:
    return {
        "memory_current_bytes": 700 * 1024**2,
        "memory_high_bytes": 704 * 1024**2,
        "memory_high_margin_bytes": 4 * 1024**2,
        "memory_max_bytes": 768 * 1024**2,
        "memory_max_margin_bytes": 68 * 1024**2,
        "memory_events": {
            "low": 0,
            "high": 10_000,
            "max": 0,
            "oom": 0,
            "oom_kill": 0,
            "oom_group_kill": 0,
        },
        "host_mem_available_bytes": 8 * 1024**3,
        "available_cpu_count": 6,
        "host_load_avg1": 1.0,
        "critical_service_cpu_pressure": {
            service: {
                "available": True,
                "pressure": {"some": {"avg10": 0.0, "avg60": 0.0}},
            }
            for service in (
                "midas-reality.service",
                "midas-api.service",
                "midas-reality-api.service",
            )
        },
        "host_pressure": {
            "cpu": {"some": {"avg10": "2.0"}},
            "memory": {
                "some": {"avg10": "0.0", "avg60": "0.0"},
                "full": {"avg10": "0.0", "avg60": "0.0"},
            },
            "io": {"full": {"avg10": "0.5", "avg60": "0.5"}},
        },
    }


def test_isolated_staging_uses_host_and_hard_limit_reserve_not_recorder_high_margin():
    sample = _sample()
    sample["memory_high_margin_bytes"] = 1 * 1024**2

    assert validate_staging_admission(sample) is sample


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("memory_max_margin_bytes", 31 * 1024**2, "below MemoryMax"),
        ("host_mem_available_bytes", 3 * 1024**3 - 1, "below 3 GiB floor"),
    ],
)
def test_isolated_staging_requires_protected_hard_limit_and_host_reserve(field, value, message):
    sample = _sample()
    sample[field] = value

    with pytest.raises(ValueError, match=message):
        validate_staging_admission(sample)


def test_critical_service_telemetry_transition_fails_closed_with_retryable_reason():
    sample = _sample()
    service = next(iter(sample["critical_service_cpu_pressure"]))
    sample["critical_service_cpu_pressure"][service] = {
        "available": False,
        "active_state": "deactivating",
        "pressure": {},
    }

    with pytest.raises(ValueError, match="unavailable during unit transition"):
        validate_staging_admission(sample)

    sample["critical_service_cpu_pressure"][service]["active_state"] = "failed"
    with pytest.raises(ValueError, match="CPU pressure is unavailable"):
        validate_staging_admission(sample)


@pytest.mark.parametrize(
    ("resource", "kind", "value", "message"),
    [
        ("memory", "some", "2.0", "memory some PSI"),
    ],
)
def test_isolated_staging_rejects_host_pressure(resource, kind, value, message):
    sample = _sample()
    sample["host_pressure"][resource][kind]["avg10"] = value

    with pytest.raises(ValueError, match=message):
        validate_staging_admission(sample)


def test_isolated_staging_allows_short_io_spike_when_sustained_pressure_is_low():
    sample = _sample()
    sample["host_pressure"]["io"]["full"].update(avg10="3.0", avg60="1.9")

    assert validate_staging_admission(sample) is sample


def test_isolated_staging_allows_short_memory_spike_when_sustained_pressure_is_low():
    sample = _sample()
    sample["host_pressure"]["memory"]["some"].update(avg10="1.5", avg60="0.4")
    sample["host_pressure"]["memory"]["full"].update(avg10="0.8", avg60="0.4")

    assert validate_staging_admission(sample) is sample


def test_quota_distorted_host_cpu_psi_does_not_gate_low_load_when_critical_services_are_clear():
    sample = _sample()
    sample["host_pressure"]["cpu"]["some"]["avg10"] = "28.0"
    sample["host_load_avg1"] = 1.25

    assert validate_staging_admission(sample) is sample


def test_host_load_at_cpu_capacity_gates_even_when_host_cpu_psi_is_low():
    sample = _sample()
    sample["host_pressure"]["cpu"]["some"]["avg10"] = "2.0"
    sample["host_load_avg1"] = 6.0

    with pytest.raises(ValueError, match="host 1-minute load reached available CPU capacity"):
        validate_staging_admission(sample)


def test_critical_service_cpu_psi_gates_even_when_host_load_is_low():
    sample = _sample()
    sample["critical_service_cpu_pressure"]["midas-reality.service"]["pressure"]["some"] = {
        "avg10": 10.0,
        "avg60": 2.0,
    }

    with pytest.raises(
        ValueError, match="critical service cpu some PSI above 10.0%.*midas-reality"
    ):
        validate_staging_admission(sample)


def test_unavailable_critical_service_pressure_fails_closed():
    sample = _sample()
    sample["critical_service_cpu_pressure"]["midas-api.service"]["available"] = False

    with pytest.raises(
        ValueError, match="critical service midas-api.service CPU pressure is unavailable"
    ):
        validate_staging_admission(sample)


@pytest.mark.parametrize(
    ("resource", "kind", "field", "value", "message"),
    [
        ("memory", "some", "avg60", "0.5", "memory some PSI above 0.5% over 60 seconds"),
        ("memory", "full", "avg10", "1.0", "memory full PSI above 1.0% over 10 seconds"),
        ("memory", "full", "avg60", "0.5", "memory full PSI above 0.5% over 60 seconds"),
    ],
)
def test_isolated_staging_rejects_sustained_or_full_memory_pressure(
    resource, kind, field, value, message
):
    sample = _sample()
    sample["host_pressure"][resource][kind][field] = value

    with pytest.raises(ValueError, match=message):
        validate_staging_admission(sample)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("avg10", "4.0", "above 4.0% over 10 seconds"),
        ("avg60", "2.0", "above 2.0% over 60 seconds"),
    ],
)
def test_isolated_staging_rejects_sustained_or_severe_io_pressure(field, value, message):
    sample = _sample()
    sample["host_pressure"]["io"]["full"][field] = value

    with pytest.raises(ValueError, match=message):
        validate_staging_admission(sample)


def test_isolated_staging_aborts_on_new_protected_max_or_oom_event():
    sample = _sample()
    baseline = dict(sample["memory_events"])
    sample["memory_events"]["max"] += 1

    with pytest.raises(ValueError, match="memory.events.max increased"):
        validate_staging_admission(sample, baseline)
