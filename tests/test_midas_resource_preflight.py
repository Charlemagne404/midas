from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/midas_resource_preflight.py"
SPEC = importlib.util.spec_from_file_location("midas_resource_preflight", SCRIPT)
assert SPEC and SPEC.loader
midas_resource_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(midas_resource_preflight)


def evidence() -> dict:
    return {
        "host_memory": {
            "available_bytes": 12 * 1024 * midas_resource_preflight.MIB,
            "swap_free_bytes": 2 * midas_resource_preflight.MIB,
            "swap_activity_pages_during_sample": {"pswpin": 0, "pswpout": 0},
        },
        "pressure": {
            "memory": {
                "some": {"avg10": 0.0, "avg60": 0.0},
                "full": {"avg10": 0.0, "avg60": 0.0},
            },
            "cpu": {"some": {"avg10": 0.0, "avg60": 0.0}},
            "io": {
                "some": {"avg10": 0.0, "avg60": 0.0},
                "full": {"avg10": 0.0, "avg60": 0.0},
            },
        },
        "protected_service_cgroups": {
            "midas-api.service": {"memory_headroom_bytes": 1024 * midas_resource_preflight.MIB},
            "midas-reality.service": {"memory_headroom_bytes": 1024 * midas_resource_preflight.MIB},
        },
        "user_manager_cgroup": {
            "pressure": {
                "some": {"avg10": 0.0, "avg60": 0.0},
                "full": {"avg10": 0.0, "avg60": 0.0},
            }
        },
        "active_midas_worker_services": [],
        "storage": [{"pass": True}],
        "task_cgroup": {"memory_headroom_bytes": 2048 * midas_resource_preflight.MIB},
    }


def test_parse_meminfo_uses_bytes_and_requires_available_memory() -> None:
    parsed = midas_resource_preflight.parse_meminfo(
        "MemTotal: 16384 kB\nMemAvailable: 8192 kB\nSwapTotal: 4096 kB\nSwapFree: 2048 kB\n"
    )
    assert parsed["MemAvailable"] == 8192 * 1024
    with pytest.raises(midas_resource_preflight.AdmissionError):
        midas_resource_preflight.parse_meminfo("MemTotal: 1 kB\n")


def test_parse_psi_and_vmstat() -> None:
    pressure = midas_resource_preflight.parse_psi(
        "some avg10=1.20 avg60=2.30 avg300=3.40 total=55\nfull avg10=0.10 avg60=0.20 avg300=0.30 total=4\n"
    )
    assert pressure["some"]["avg10"] == 1.2
    assert pressure["full"]["avg60"] == 0.2
    assert midas_resource_preflight.parse_vmstat("pswpin 1\npswpout 2\n") == {
        "pswpin": 1,
        "pswpout": 2,
    }


def test_admits_bounded_sample_only_with_finite_cgroup_and_clear_pressure() -> None:
    assert (
        midas_resource_preflight.evaluate_evidence(
            evidence(),
            profile="bounded-test",
            memory_budget_bytes=128 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda e: e["host_memory"].update(available_bytes=1024 * midas_resource_preflight.MIB),
            "host_memavailable_below_floor_plus_task_budget",
        ),
        (
            lambda e: e["host_memory"]["swap_activity_pages_during_sample"].update(pswpin=1),
            "swap_activity_above_profile_limit",
        ),
        (
            lambda e: e["pressure"]["memory"]["full"].update(avg10=2.0),
            "memory_full_avg10_pressure_above_profile_limit",
        ),
        (
            lambda e: e["protected_service_cgroups"]["midas-reality.service"].update(
                memory_headroom_bytes=1
            ),
            "midas-reality_service_memory_headroom_below_profile_floor",
        ),
        (
            lambda e: e.update(
                active_midas_worker_services=["midas-veritas-source-analysis.service"]
            ),
            "another_midas_worker_service_is_active",
        ),
        (
            lambda e: e["storage"][0].__setitem__("pass", False),
            "storage_required_bytes_or_reserve_unavailable",
        ),
        (
            lambda e: e["task_cgroup"].update(memory_headroom_bytes=None),
            "task_cgroup_has_no_finite_memoryhigh_or_memorymax",
        ),
    ],
)
def test_fails_closed_on_missing_or_constrained_evidence(mutation, expected: str) -> None:
    observed = evidence()
    mutation(observed)
    reasons = midas_resource_preflight.evaluate_evidence(
        observed,
        profile="heavy",
        memory_budget_bytes=128 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )
    assert expected in reasons


def test_full_swap_without_activity_is_distinguished_from_thrashing() -> None:
    observed = evidence()
    observed["host_memory"].update(swap_free_bytes=0)
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="bounded-test",
            memory_budget_bytes=32 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )
    assert "swap_reserve_below_profile_floor" in midas_resource_preflight.evaluate_evidence(
        observed,
        profile="heavy",
        memory_budget_bytes=32 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )


def test_bounded_test_allows_incidental_page_but_denies_repeated_swap_activity() -> None:
    observed = evidence()
    observed["host_memory"]["swap_activity_pages_during_sample"]["pswpin"] = 1
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="bounded-test",
            memory_budget_bytes=32 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )
    observed["host_memory"]["swap_activity_pages_during_sample"]["pswpin"] = 9
    assert "swap_activity_above_profile_limit" in midas_resource_preflight.evaluate_evidence(
        observed,
        profile="bounded-test",
        memory_budget_bytes=32 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )


def test_backup_profile_ignores_occupied_inactive_swap_but_limits_movement() -> None:
    observed = evidence()
    observed["host_memory"].update(swap_free_bytes=0)
    observed["host_memory"]["swap_activity_pages_during_sample"]["pswpin"] = 1
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="backup",
            memory_budget_bytes=512 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )
    observed["host_memory"]["swap_activity_pages_during_sample"]["pswpout"] = 8
    assert "swap_activity_above_profile_limit" in midas_resource_preflight.evaluate_evidence(
        observed,
        profile="backup",
        memory_budget_bytes=512 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda e: e["pressure"]["io"]["full"].update(avg10=1.01),
            "io_full_avg10_pressure_above_profile_limit",
        ),
        (
            lambda e: e["pressure"]["io"]["full"].update(avg60=1.51),
            "io_full_avg60_pressure_above_profile_limit",
        ),
        (
            lambda e: e["user_manager_cgroup"]["pressure"]["full"].update(avg60=1.01),
            "user_manager_memory_full_avg60_pressure_above_profile_limit",
        ),
        (
            lambda e: e["protected_service_cgroups"]["midas-api.service"].update(
                memory_headroom_bytes=127 * midas_resource_preflight.MIB
            ),
            "midas-api_service_memory_headroom_below_profile_floor",
        ),
    ],
)
def test_backup_profile_fails_closed_on_io_memory_or_service_pressure(
    mutation, expected: str
) -> None:
    observed = evidence()
    mutation(observed)
    reasons = midas_resource_preflight.evaluate_evidence(
        observed,
        profile="backup",
        memory_budget_bytes=512 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )
    assert expected in reasons


def test_backup_profile_requires_a_full_30_second_sample() -> None:
    from argparse import Namespace

    args = Namespace(profile="backup", sample_seconds=29)
    with pytest.raises(midas_resource_preflight.AdmissionError, match="30-second"):
        midas_resource_preflight._gate(args, include_task_cgroup=False, lock_held=True)
