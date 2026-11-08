from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/midas_resource_preflight.py"
SPEC = importlib.util.spec_from_file_location("midas_resource_preflight", SCRIPT)
assert SPEC and SPEC.loader
midas_resource_preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(midas_resource_preflight)


def evidence() -> dict:
    pressure = {
        "memory": {
            "some": {"avg10": 0.0, "avg60": 0.0},
            "full": {"avg10": 0.0, "avg60": 0.0},
        },
        "cpu": {"some": {"avg10": 0.0, "avg60": 0.0}},
        "io": {
            "some": {"avg10": 0.0, "avg60": 0.0},
            "full": {"avg10": 0.0, "avg60": 0.0},
        },
    }
    return {
        "host_memory": {
            "available_bytes": 12 * 1024 * midas_resource_preflight.MIB,
            "swap_free_bytes": 2 * midas_resource_preflight.MIB,
            "swap_activity_pages_during_sample": {"pswpin": 0, "pswpout": 0},
        },
        "pressure": pressure,
        "pressure_samples": [
            {"elapsed_seconds": float(index * 10), "pressure": pressure} for index in range(4)
        ],
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


def test_veritas_profile_admits_full_inactive_swap_with_strict_pressure_bounds() -> None:
    observed = evidence()
    observed["host_memory"].update(swap_free_bytes=0)
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="veritas",
            memory_budget_bytes=128 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )
    assert midas_resource_preflight.PROFILES["heavy"]["min_swap_free_mib"] == 256
    assert (
        midas_resource_preflight.PROFILES["veritas"]["io_full_avg10"]
        == midas_resource_preflight.PROFILES["heavy"]["io_full_avg10"]
    )
    assert (
        midas_resource_preflight.PROFILES["veritas"]["io_full_avg60"]
        == midas_resource_preflight.PROFILES["heavy"]["io_full_avg60"]
    )


def _set_io_full_samples(
    observed: dict,
    avg10_values: list[float],
    avg60_values: list[float],
) -> None:
    samples = []
    for index, (avg10, avg60) in enumerate(zip(avg10_values, avg60_values, strict=True)):
        pressure = copy.deepcopy(observed["pressure"])
        pressure["io"]["full"].update(avg10=avg10, avg60=avg60)
        samples.append({"elapsed_seconds": float(index * 10), "pressure": pressure})
    observed["pressure_samples"] = samples
    observed["pressure"] = samples[-1]["pressure"]


def test_veritas_admission_accepts_measured_idle_psi_and_one_short_excursion() -> None:
    observed = evidence()
    observed["host_memory"].update(swap_free_bytes=0)
    _set_io_full_samples(observed, [0.52, 0.62, 0.29, 0.88], [0.63, 0.62, 0.55, 0.75])
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="veritas",
            memory_budget_bytes=128 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )

    _set_io_full_samples(observed, [1.2, 0.8, 0.8, 0.8], [0.7, 0.7, 0.7, 0.7])
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="veritas",
            memory_budget_bytes=128 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )


@pytest.mark.parametrize(
    ("avg10_values", "avg60_values", "expected"),
    [
        (
            [0.8, 1.1, 1.2, 0.8],
            [0.7, 0.8, 0.8, 0.8],
            "io_full_avg10_pressure_sustained_above_profile_limit",
        ),
        (
            [0.8, 0.8, 0.8, 0.8],
            [1.4, 1.6, 1.7, 1.4],
            "io_full_avg60_pressure_sustained_above_profile_limit",
        ),
        (
            [0.8, 0.8, 3.1, 0.8],
            [0.7, 0.7, 0.7, 0.7],
            "io_full_pressure_above_veritas_hard_limit",
        ),
    ],
)
def test_veritas_admission_rejects_sustained_or_severe_io_pressure(
    avg10_values: list[float], avg60_values: list[float], expected: str
) -> None:
    observed = evidence()
    observed["host_memory"].update(swap_free_bytes=0)
    _set_io_full_samples(observed, avg10_values, avg60_values)
    reasons = midas_resource_preflight.evaluate_evidence(
        observed,
        profile="veritas",
        memory_budget_bytes=128 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )
    assert expected in reasons


def test_veritas_admission_fails_closed_without_repeated_psi_samples() -> None:
    observed = evidence()
    observed["pressure_samples"] = []
    reasons = midas_resource_preflight.evaluate_evidence(
        observed,
        profile="veritas",
        memory_budget_bytes=128 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )
    assert "missing_repeated_io_pressure_samples" in reasons


def test_veritas_runtime_psi_guard_has_hysteresis_and_a_hard_stop() -> None:
    guard = midas_resource_preflight.veritas_runtime_io_cancel_reason
    idle = [{"avg10": 0.88, "avg60": 0.75} for _ in range(5)]
    assert guard(idle) is None
    elevated = [{"avg10": 2.1, "avg60": 1.6} for _ in range(4)]
    assert guard(elevated) is None
    assert guard(elevated + [{"avg10": 2.1, "avg60": 1.6}]) == (
        "io_full_avg10_pressure_sustained_during_veritas_run"
    )
    assert guard([{"avg10": 3.1, "avg60": 0.8}]) == (
        "io_full_avg10_pressure_above_runtime_hard_limit"
    )
    assert guard([{"avg10": float("nan"), "avg60": 0.8}]) == "io_pressure_sample_invalid"
    assert guard([{"avg10": "unavailable", "avg60": 0.8}]) == "io_pressure_sample_invalid"


@pytest.mark.parametrize("value", ["nan", "inf", "-0.1"])
def test_psi_parser_rejects_invalid_averages(value: str) -> None:
    with pytest.raises(midas_resource_preflight.AdmissionError):
        midas_resource_preflight.parse_psi(f"some avg10={value} avg60=0.1 avg300=0.1 total=1\n")


def test_veritas_runtime_pressure_cancels_once_without_retry(monkeypatch) -> None:
    calls = []
    reports = []

    class RunningProcess:
        def poll(self):
            return None

        def wait(self, timeout=None):
            return -15

    process = RunningProcess()
    monkeypatch.setattr(
        midas_resource_preflight,
        "_read_veritas_runtime_io_pressure",
        lambda: {"avg10": 2.1, "avg60": 1.6},
    )
    monkeypatch.setattr(
        midas_resource_preflight, "_kill_unit", lambda unit, grace: calls.append(unit)
    )
    monkeypatch.setattr(midas_resource_preflight, "_print_evidence", reports.append)
    monkeypatch.setattr(midas_resource_preflight.time, "sleep", lambda _seconds: None)
    status = midas_resource_preflight._wait_for_veritas_process(
        process,
        "midas-heavy-veritas-test.service",
        timeout_seconds=30,
        termination_grace_seconds=2,
    )
    assert status == midas_resource_preflight.VERITAS_RUNTIME_PRESSURE_CANCELLED
    assert calls == ["midas-heavy-veritas-test.service"]
    assert len(reports) == 1
    assert reports[0]["decision"] == "CANCEL"


def test_veritas_runtime_watchdog_fails_closed_when_psi_is_unavailable(monkeypatch) -> None:
    calls = []
    reports = []

    def fail_pressure_read() -> dict[str, float]:
        raise midas_resource_preflight.AdmissionError("synthetic PSI read failure")

    class RunningProcess:
        def poll(self):
            return None

        def wait(self, timeout=None):
            return -15

    monkeypatch.setattr(
        midas_resource_preflight,
        "_read_veritas_runtime_io_pressure",
        fail_pressure_read,
    )
    monkeypatch.setattr(
        midas_resource_preflight, "_kill_unit", lambda unit, grace: calls.append(unit)
    )
    monkeypatch.setattr(midas_resource_preflight, "_print_evidence", reports.append)
    status = midas_resource_preflight._wait_for_veritas_process(
        RunningProcess(),
        "midas-heavy-veritas-test.service",
        timeout_seconds=30,
        termination_grace_seconds=2,
    )
    assert status == midas_resource_preflight.VERITAS_RUNTIME_PRESSURE_CANCELLED
    assert calls == ["midas-heavy-veritas-test.service"]
    assert len(reports) == 1
    assert reports[0]["reason"] == "runtime_io_pressure_unavailable"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda e: e["host_memory"].update(
                available_bytes=(6144 + 128) * midas_resource_preflight.MIB - 1
            ),
            "host_memavailable_below_floor_plus_task_budget",
        ),
        (
            lambda e: e["host_memory"]["swap_activity_pages_during_sample"].update(pswpin=1),
            "swap_activity_above_profile_limit",
        ),
        (
            lambda e: e["pressure"]["memory"]["full"].update(avg10=0.26),
            "memory_full_avg10_pressure_above_profile_limit",
        ),
        (
            lambda e: e["pressure"]["io"]["full"].update(avg10=1.01),
            "io_full_avg10_pressure_sustained_above_profile_limit",
        ),
        (
            lambda e: e["pressure"]["io"]["full"].update(avg60=1.51),
            "io_full_avg60_pressure_sustained_above_profile_limit",
        ),
        (
            lambda e: e["protected_service_cgroups"]["midas-reality.service"].update(
                memory_headroom_bytes=127 * midas_resource_preflight.MIB
            ),
            "midas-reality_service_memory_headroom_below_profile_floor",
        ),
        (
            lambda e: e["user_manager_cgroup"]["pressure"]["full"].update(avg60=1.01),
            "user_manager_memory_full_avg60_pressure_above_profile_limit",
        ),
    ],
)
def test_veritas_profile_fails_closed_on_pressure_or_insufficient_headroom(
    mutation, expected: str
) -> None:
    observed = evidence()
    observed["host_memory"].update(swap_free_bytes=0)
    mutation(observed)
    reasons = midas_resource_preflight.evaluate_evidence(
        observed,
        profile="veritas",
        memory_budget_bytes=128 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )
    assert expected in reasons


def test_veritas_profile_requires_a_full_30_second_sample() -> None:
    from argparse import Namespace

    args = Namespace(profile="veritas", sample_seconds=29)
    with pytest.raises(midas_resource_preflight.AdmissionError, match="30-second"):
        midas_resource_preflight._gate(args, include_task_cgroup=False, lock_held=True)


def test_veritas_runtime_context_requires_disabled_timers_and_original_service_limits(
    monkeypatch,
) -> None:
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_SERVICE_ROOT", Path("/tmp"))
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_OUTPUT_ROOT", Path("/tmp"))
    properties = {
        "midas-veritas-source-analysis.timer": "ActiveState=inactive\nUnitFileState=disabled\n",
        "midas-reality-capacity.timer": "ActiveState=inactive\nUnitFileState=disabled\n",
        "midas-veritas-source-analysis.service": "\n".join(
            [
                "ActiveState=failed",
                "MainPID=0",
                "ControlPID=0",
                f"MemoryMax={256 * midas_resource_preflight.MIB}",
                "CPUQuotaPerSecUSec=1s",
                "Nice=19",
                "IOSchedulingClass=3",
                "TimeoutStartUSec=10min",
                "MemoryHigh=infinity",
                "MemorySwapMax=infinity",
                "ProtectSystem=strict",
                "ProtectHome=read-only",
                "ReadWritePaths=/tmp",
                "WorkingDirectory=/tmp",
                "PrivateTmp=yes",
                "NoNewPrivileges=yes",
                "Restart=no",
            ]
        ),
    }

    def show(*args: str, **_kwargs: object):
        unit = args[1]
        return type("Result", (), {"stdout": properties[unit]})()

    monkeypatch.setattr(midas_resource_preflight, "_systemctl", show)

    midas_resource_preflight._validate_veritas_runtime_context()

    properties["midas-reality-capacity.timer"] = "ActiveState=active\nUnitFileState=enabled\n"
    with pytest.raises(midas_resource_preflight.AdmissionError, match="must remain disabled"):
        midas_resource_preflight._validate_veritas_runtime_context()


def test_veritas_inner_gate_ignores_only_its_own_transient_service(monkeypatch) -> None:
    from types import SimpleNamespace

    current = "midas-heavy-veritas-1234-abcd1234.service"
    monkeypatch.setattr(
        midas_resource_preflight,
        "_systemctl",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=f"{current} loaded running validation\nmidas-other-worker.service loaded running other\n"
        ),
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_current_cgroup",
        lambda: Path(f"/sys/fs/cgroup/user.slice/app.slice/{current}"),
    )

    assert midas_resource_preflight._active_midas_workers(allow_current_veritas_service=True) == [
        "midas-other-worker.service"
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"memory_high_mib": 193},
        {"memory_max_mib": 257},
        {"memory_budget_mib": 129},
        {"cpu_quota_percent": 101},
        {"timeout_seconds": 601},
        {"sample_seconds": 29},
    ],
)
def test_veritas_run_cannot_exceed_its_fixed_scope_limits(overrides: dict) -> None:
    from argparse import Namespace

    values = {
        "profile": "veritas",
        "command": ["/usr/bin/true"],
        "memory_high_mib": 192,
        "memory_max_mib": 256,
        "memory_budget_mib": 128,
        "cpu_quota_percent": 100,
        "timeout_seconds": 600,
        "sample_seconds": 30,
    }
    values.update(overrides)
    with pytest.raises(midas_resource_preflight.AdmissionError, match="Veritas service"):
        midas_resource_preflight._run_command(Namespace(**values))


def test_veritas_run_uses_sandboxed_service_and_existing_resource_limits(
    monkeypatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    commands: list[list[str]] = []

    class Lock:
        def close(self) -> None:
            pass

    class Process:
        def poll(self) -> int:
            return 0

        def wait(self, *, timeout: float) -> int:
            assert timeout == 600
            return 0

    monkeypatch.setattr(midas_resource_preflight, "_acquire_lock", Lock)
    monkeypatch.setattr(midas_resource_preflight, "_validate_veritas_runtime_context", lambda: None)
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_SERVICE_ROOT", tmp_path)
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(
        midas_resource_preflight,
        "_gate",
        lambda *_args, **_kwargs: ({"decision": "ADMIT"}, []),
    )
    monkeypatch.setattr(midas_resource_preflight, "_print_evidence", lambda _evidence: None)
    monkeypatch.setattr(midas_resource_preflight.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        midas_resource_preflight.subprocess,
        "Popen",
        lambda command: commands.append(command) or Process(),
    )
    args = Namespace(
        profile="veritas",
        command=["--", "/usr/bin/true"],
        memory_high_mib=192,
        memory_max_mib=256,
        memory_budget_mib=128,
        cpu_quota_percent=100,
        timeout_seconds=600,
        sample_seconds=30,
        label="test",
        storage_path=["/tmp"],
        storage_required_mib=0,
        storage_reserve_mib=0,
        termination_grace_seconds=2,
    )

    assert midas_resource_preflight._run_command(args) == 0
    command = commands[0]
    assert "--property=MemoryHigh=192M" in command
    assert "--property=MemoryMax=256M" in command
    assert "--property=MemorySwapMax=0" in command
    assert "--property=CPUQuota=100%" in command
    assert "--property=IOWeight=10" in command
    assert "--property=TasksMax=256" in command
    assert "--property=Nice=19" in command
    assert "--property=IOSchedulingClass=idle" in command
    assert "--property=ProtectSystem=strict" in command
    assert "--property=ProtectHome=read-only" in command
    assert f"--property=ReadWritePaths={tmp_path}" in command
    assert "--property=PrivateTmp=yes" in command
    assert "--property=NoNewPrivileges=yes" in command
    assert "--property=Restart=no" in command
    assert f"--property=WorkingDirectory={tmp_path}" in command
    assert "--service-type=exec" in command
    assert "--wait" in command
    assert "--scope" not in command
    assert command[-1] == "/usr/bin/true"
