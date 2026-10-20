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
        "memory_events": {"low": 0, "high": 10_000, "max": 0, "oom": 0,
                          "oom_kill": 0, "oom_group_kill": 0},
        "host_mem_available_bytes": 8 * 1024**3,
        "host_pressure": {
            "cpu": {"some": {"avg10": "2.0"}},
            "memory": {"some": {"avg10": "0.0"}},
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


@pytest.mark.parametrize(
    ("resource", "kind", "value", "message"),
    [
        ("cpu", "some", "20.0", "cpu some PSI"),
        ("memory", "some", "0.5", "memory some PSI"),
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
