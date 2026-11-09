from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
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


def test_synthetic_validation_profile_is_separate_and_keeps_production_veritas_policy() -> None:
    veritas_before = copy.deepcopy(midas_resource_preflight.PROFILES["veritas"])
    observed = evidence()
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="synthetic-validation",
            memory_budget_bytes=8 * midas_resource_preflight.MIB,
            require_task_cgroup=False,
        )
        == []
    )
    assert midas_resource_preflight.PROFILES["veritas"] == veritas_before
    assert midas_resource_preflight.PROFILES["synthetic-validation"]["min_swap_free_mib"] == 0
    assert (
        midas_resource_preflight.PROFILES["synthetic-validation"]["max_swap_activity_pages"] == 64
    )
    assert midas_resource_preflight.PROFILES["synthetic-validation"]["max_swap_activity_pages"] > 0


def test_veritas_ci_fixture_overrides_are_bound_to_the_disposable_service(monkeypatch, tmp_path):
    root = tmp_path / "midas-veritas-ci"
    campaign_dir = root / "campaign"
    source_root = root / "raw"
    pressure_dir = root / "pressure"
    campaign_dir.mkdir(parents=True)
    source_root.mkdir()
    pressure_dir.mkdir()
    (root / "output").mkdir()
    pressure_file = pressure_dir / "io"
    pressure_file.write_text(
        "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    )
    campaign = {"campaign_id": "a" * 64, "identity": {"raw_root": str(source_root)}}
    campaign_path = campaign_dir / "campaign.json"
    campaign_path.write_text(json.dumps(campaign))
    campaign_sha = midas_resource_preflight._sha256_bytes(campaign_path.read_bytes())
    values = {
        "MIDAS_VERITAS_CI_TEST": midas_resource_preflight.VERITAS_CI_TEST_MARKER,
        "MIDAS_VERITAS_CI_CAMPAIGN_PATH": str(campaign_path),
        "MIDAS_VERITAS_CI_CAMPAIGN_SHA256": campaign_sha,
        "MIDAS_VERITAS_CI_CAMPAIGN_ID": campaign["campaign_id"],
        "MIDAS_VERITAS_CI_SOURCE_ROOT": str(source_root),
        "MIDAS_VERITAS_CI_PSI_FILE": str(pressure_file),
        "MIDAS_VERITAS_CI_SCENARIO": "success",
    }
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_CI_ROOT", root)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    properties = (
        "ActiveState=active\n"
        f"InvocationID={'b' * 32}\n"
        "Environment=" + " ".join(f"{key}={value}" for key, value in values.items()) + "\n"
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, properties, ""),
    )
    context = midas_resource_preflight._veritas_ci_test_context(
        unit_name=midas_resource_preflight.VERITAS_CI_SERVICE_UNIT,
        invocation_id="b" * 32,
    )
    assert context is not None
    assert context["campaign_sha256"] == campaign_sha
    assert context["scenario"] == "success"
    assert Path(context["output_root"]) == root / "output"
    assert Path(context["output_root"]) != midas_resource_preflight.VERITAS_OUTPUT_ROOT
    assert Path(context["output_root"]).is_relative_to(root)
    (root / "output").rmdir()
    outside_output = tmp_path / "outside-output"
    outside_output.mkdir()
    (root / "output").symlink_to(outside_output, target_is_directory=True)
    with pytest.raises(midas_resource_preflight.AdmissionError, match="missing or unsafe"):
        midas_resource_preflight._veritas_ci_test_context(
            unit_name=midas_resource_preflight.VERITAS_CI_SERVICE_UNIT,
            invocation_id="b" * 32,
        )
    assert midas_resource_preflight.PROFILES["veritas"]["protected_headroom_mib"] == 128


def test_veritas_ci_test_environment_cannot_be_selected_by_production_service(monkeypatch):
    monkeypatch.setenv("MIDAS_VERITAS_CI_TEST", midas_resource_preflight.VERITAS_CI_TEST_MARKER)
    with pytest.raises(midas_resource_preflight.AdmissionError, match="restricted"):
        midas_resource_preflight._veritas_ci_test_context(
            unit_name=midas_resource_preflight.VERITAS_SERVICE_UNIT,
            invocation_id="c" * 32,
        )
    assert midas_resource_preflight.SYNTHETIC_RUN_LIMITS["memory_budget_mib"] == 8


def test_veritas_ci_worker_command_is_confined_to_the_test_output_root(tmp_path):
    output_root = tmp_path / "midas-veritas-ci" / "output"
    command = midas_resource_preflight._veritas_worker_command(
        midas_resource_preflight.VERITAS_RELEASE_ROOT, output_root=output_root
    )
    assert command[command.index("--root") + 1] == str(output_root)
    assert str(midas_resource_preflight.VERITAS_OUTPUT_ROOT) not in command


def test_synthetic_validation_allows_only_bounded_incidental_swap_movement() -> None:
    observed = evidence()
    observed["host_memory"]["swap_activity_pages_during_sample"].update(pswpin=64)
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="synthetic-validation",
            memory_budget_bytes=8 * midas_resource_preflight.MIB,
            require_task_cgroup=False,
        )
        == []
    )
    observed["host_memory"]["swap_activity_pages_during_sample"]["pswpin"] = 65
    assert "swap_activity_above_profile_limit" in midas_resource_preflight.evaluate_evidence(
        observed,
        profile="synthetic-validation",
        memory_budget_bytes=8 * midas_resource_preflight.MIB,
        require_task_cgroup=False,
    )


def test_synthetic_inner_reserve_fits_its_fixed_cgroup_headroom() -> None:
    observed = evidence()
    observed["task_cgroup"] = {"memory_headroom_bytes": 8 * midas_resource_preflight.MIB}
    assert (
        midas_resource_preflight.evaluate_evidence(
            observed,
            profile="synthetic-validation",
            memory_budget_bytes=8 * midas_resource_preflight.MIB,
            require_task_cgroup=True,
        )
        == []
    )
    observed["task_cgroup"]["memory_headroom_bytes"] -= 1
    assert "task_cgroup_headroom_below_task_budget" in midas_resource_preflight.evaluate_evidence(
        observed,
        profile="synthetic-validation",
        memory_budget_bytes=8 * midas_resource_preflight.MIB,
        require_task_cgroup=True,
    )


def test_synthetic_validation_rejects_budget_larger_than_tiny_worker_cap(
    monkeypatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    monkeypatch.setattr(
        midas_resource_preflight,
        "_require_host_ip_socket_support",
        lambda: None,
    )
    args = Namespace(
        memory_high_mib=32,
        memory_max_mib=64,
        memory_budget_mib=9,
        cpu_quota_percent=10,
        timeout_seconds=10,
        sample_seconds=5,
        termination_grace_seconds=1,
        storage_required_mib=0,
        storage_reserve_mib=0,
        storage_path=[str(tmp_path)],
    )
    with pytest.raises(midas_resource_preflight.AdmissionError, match="fixed short-run profile"):
        midas_resource_preflight._validate_synthetic_limits(args, ["/usr/bin/true"])


def test_synthetic_landlock_isolation_denies_host_data_and_execs_fixed_binary(
    tmp_path: Path,
) -> None:
    import platform

    if sys.platform != "linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
        "aarch64",
        "arm64",
    }:
        pytest.skip(
            "synthetic Landlock and seccomp verification requires configured Linux architectures"
        )
    status_dir = tmp_path / "receipt.control"
    status_dir.mkdir(mode=0o700)
    code = """
import ctypes, importlib.util, os, pathlib, sys
spec = importlib.util.spec_from_file_location('midas_guard', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(38, 1, 0, 0, 0) != 0:
    raise SystemExit(71)
result = module._apply_synthetic_filesystem_isolation(pathlib.Path(sys.argv[2]))
if not result['enforced'] or not {sys.argv[3], '/mnt', '/var/tmp'}.issubset(result['denied_paths']):
    raise SystemExit(72)
network = module._install_synthetic_network_filter()
if not network['restricted'] or network['mechanism'] != 'seccomp-bpf':
    raise SystemExit(73)
if set(network['probes'].values()) != {'denied'}:
    raise SystemExit(74)
os.execve('/usr/bin/true', ['/usr/bin/true'], {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C', 'LC_ALL': 'C'})
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(SCRIPT), str(status_dir), str(Path.home())],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_synthetic_cgroup_metrics_allow_only_undelegated_io_controller(
    monkeypatch, tmp_path: Path
) -> None:
    root = tmp_path / "cgroup"
    group = root / "midas-synthetic-validation-test.service"
    group.mkdir(parents=True)
    monkeypatch.setattr(midas_resource_preflight, "CGROUP_ROOT", root)
    for name, value in {
        "memory.current": "1048576",
        "memory.high": str(32 * midas_resource_preflight.MIB),
        "memory.max": str(64 * midas_resource_preflight.MIB),
        "memory.swap.max": "0",
        "memory.peak": "2097152",
        "memory.events": "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n",
        "cpu.stat": "usage_usec 1000\nuser_usec 800\nsystem_usec 200\n",
        "cpu.max": "10000 100000",
        "pids.max": "8",
    }.items():
        (group / name).write_text(value, encoding="ascii")

    metrics = midas_resource_preflight._cgroup_execution_metrics(
        group, allow_missing_io_weight=True
    )
    assert metrics["available"] is True
    assert metrics["io_weight_enforced"] is False
    assert metrics["limits"]["memory.max"] == str(64 * midas_resource_preflight.MIB)
    assert metrics["limits"]["cpu.max"] == "10000 100000"
    assert metrics["limits"]["pids.max"] == "8"
    assert midas_resource_preflight._cgroup_execution_metrics(group)["available"] is False


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (["/usr/bin/true"], 0),
        (["/usr/bin/false"], 1),
        (["/usr/bin/sleep", "1"], 0),
    ],
)
def test_synthetic_validation_accepts_only_fixed_harmless_binaries(command, expected: int) -> None:
    assert midas_resource_preflight._synthetic_expected_exit(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        ["/usr/bin/python3", "-c", "print('not a probe')"],
        ["/home/charlie/midas-veritas/scripts/veritas_source_analysis.py"],
        ["/usr/bin/true", "unexpected-argument"],
        ["/bin/true"],
    ],
)
def test_synthetic_validation_rejects_research_or_unexpected_commands(command) -> None:
    with pytest.raises(midas_resource_preflight.AdmissionError, match="synthetic-validation"):
        midas_resource_preflight._synthetic_expected_exit(command)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda e: e["host_memory"].update(available_bytes=1024 * midas_resource_preflight.MIB),
            "host_memavailable_below_floor_plus_task_budget",
        ),
        (
            lambda e: e["host_memory"]["swap_activity_pages_during_sample"].update(pswpin=65),
            "swap_activity_above_profile_limit",
        ),
        (
            lambda e: e["pressure"]["io"]["full"].update(avg10=5.1),
            "io_full_avg10_pressure_above_profile_limit",
        ),
        (
            lambda e: e["protected_service_cgroups"]["midas-reality.service"].update(
                memory_headroom_bytes=127 * midas_resource_preflight.MIB
            ),
            "midas-reality_service_memory_headroom_below_profile_floor",
        ),
        (
            lambda e: e.update(
                active_midas_worker_services=["midas-veritas-source-analysis.service"]
            ),
            "another_midas_worker_service_is_active",
        ),
    ],
)
def test_synthetic_validation_rejects_dangerous_host_conditions(mutation, expected: str) -> None:
    observed = evidence()
    mutation(observed)
    reasons = midas_resource_preflight.evaluate_evidence(
        observed,
        profile="synthetic-validation",
        memory_budget_bytes=8 * midas_resource_preflight.MIB,
        require_task_cgroup=False,
    )
    assert expected in reasons


def test_synthetic_validation_profile_cannot_be_used_by_check_action(
    tmp_path: Path, capsys
) -> None:
    code = midas_resource_preflight.main(
        [
            "check",
            "--profile",
            "synthetic-validation",
            "--storage-path",
            str(tmp_path),
        ]
    )
    assert code == 75
    assert "only through the guarded run command" in capsys.readouterr().err


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


def test_veritas_runtime_context_requires_exact_service_owner_and_pinned_execstart(
    monkeypatch, tmp_path: Path
) -> None:
    import socket

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    bus_socket = runtime_dir / "bus"
    bus_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    bus_listener.bind(str(bus_socket))
    bus_listener.close()
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_USER_MANAGER_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_USER_MANAGER_BUS_SOCKET", bus_socket)
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_SERVICE_ROOT", tmp_path)
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(midas_resource_preflight, "GUARDED_RECEIPT_DIR", tmp_path / "receipts")
    rollback_module = tmp_path / "packages/midas/veritas/finalized_source_analysis.py"
    rollback_module.parent.mkdir(parents=True)
    rollback_module.write_bytes(b"previous module")
    monkeypatch.setattr(
        midas_resource_preflight,
        "VERITAS_PRODUCTION_MODULE_SHA256",
        hashlib.sha256(b"previous module").hexdigest(),
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_current_veritas_service_unit",
        lambda: "midas-veritas-source-analysis.service",
    )
    owner_invocation_id = "a" * 32
    monkeypatch.setenv("INVOCATION_ID", owner_invocation_id)
    expected_execstart = midas_resource_preflight._expected_veritas_service_execstart()
    properties = {
        "midas-veritas-source-analysis.timer": "ActiveState=inactive\nUnitFileState=disabled\n",
        "midas-reality-capacity.timer": "ActiveState=inactive\nUnitFileState=disabled\n",
        "midas-veritas-source-analysis.service": "\n".join(
            [
                "ActiveState=activating",
                f"MainPID={os.getpid()}",
                "ControlPID=0",
                f"MemoryMax={256 * midas_resource_preflight.MIB}",
                "CPUQuotaPerSecUSec=1s",
                "Nice=19",
                "IOSchedulingClass=3",
                "TimeoutStartUSec=12min",
                "MemoryHigh=infinity",
                "MemorySwapMax=infinity",
                "ProtectSystem=strict",
                "ProtectHome=read-only",
                "ReadWritePaths="
                f"{tmp_path} {tmp_path / 'receipts'} "
                f"{midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET}",
                f"WorkingDirectory={tmp_path}",
                "PrivateTmp=yes",
                "NoNewPrivileges=yes",
                "Restart=no",
                f"InvocationID={owner_invocation_id}",
                "ExecStart={ path=/usr/bin/python3 ; argv[]="
                + " ".join(expected_execstart)
                + " ; ignore_errors=no ; }",
                "Environment=XDG_RUNTIME_DIR="
                f"{midas_resource_preflight.VERITAS_USER_MANAGER_RUNTIME_DIR} "
                "DBUS_SESSION_BUS_ADDRESS=unix:path="
                f"{midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET} "
                "OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1",
                "UnsetEnvironment=PYTHONPATH",
            ]
        ),
    }

    def show(*args: str, **_kwargs: object):
        unit = args[1]
        return type("Result", (), {"stdout": properties[unit]})()

    monkeypatch.setattr(midas_resource_preflight, "_systemctl", show)

    assert midas_resource_preflight._validate_veritas_runtime_context() == owner_invocation_id

    service_properties = properties["midas-veritas-source-analysis.service"]
    properties["midas-veritas-source-analysis.service"] = service_properties.replace(
        f" {midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET}", ""
    )
    with pytest.raises(midas_resource_preflight.AdmissionError, match="service write paths"):
        midas_resource_preflight._validate_veritas_runtime_context()
    properties["midas-veritas-source-analysis.service"] = service_properties

    properties["midas-veritas-source-analysis.service"] = service_properties.replace(
        f"DBUS_SESSION_BUS_ADDRESS=unix:path={midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET}",
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/999999/bus",
    )
    with pytest.raises(midas_resource_preflight.AdmissionError, match="manager-bus environment"):
        midas_resource_preflight._validate_veritas_runtime_context()
    properties["midas-veritas-source-analysis.service"] = service_properties

    properties["midas-veritas-source-analysis.service"] = service_properties.replace(
        "OMP_NUM_THREADS=1",
        "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/999999/systemd/private OMP_NUM_THREADS=1",
    )
    with pytest.raises(midas_resource_preflight.AdmissionError, match="exactly the validated"):
        midas_resource_preflight._validate_veritas_runtime_context()
    properties["midas-veritas-source-analysis.service"] = service_properties

    properties["midas-reality-capacity.timer"] = "ActiveState=active\nUnitFileState=enabled\n"
    with pytest.raises(midas_resource_preflight.AdmissionError, match="Reality capacity timer"):
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


def test_synthetic_inner_gate_ignores_only_its_invocation_unit(monkeypatch) -> None:
    from types import SimpleNamespace

    invocation_id = "123456789abc" + "0" * 20
    current = f"midas-synthetic-validation-smoke-{invocation_id[:12]}.service"
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

    assert midas_resource_preflight._active_midas_workers(
        allow_current_synthetic_service=True,
        invocation_id=invocation_id,
    ) == ["midas-other-worker.service"]
    assert midas_resource_preflight._active_midas_workers(
        allow_current_synthetic_service=True,
        invocation_id="f" * 32,
    ) == [current, "midas-other-worker.service"]


def test_synthetic_inner_refuses_execution_outside_matching_transient_service(
    monkeypatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    invocation_id = "a" * 32
    root = tmp_path / "synthetic"
    receipt_dir = root / "receipts"
    status_dir = receipt_dir / f"{invocation_id}.control"
    status_dir.mkdir(parents=True, mode=0o700)
    status_path = status_dir / "inner-status.json"
    monkeypatch.setattr(midas_resource_preflight, "SYNTHETIC_TEST_ROOT", root)
    monkeypatch.setattr(midas_resource_preflight, "SYNTHETIC_RECEIPT_DIR", receipt_dir)
    monkeypatch.setattr(
        midas_resource_preflight.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("worker must not start outside its transient unit"),
    )
    args = Namespace(
        invocation_id=invocation_id,
        status_path=str(status_path),
        profile="synthetic-validation",
        memory_budget_mib=8,
        storage_path=[str(root)],
        storage_required_mib=0,
        storage_reserve_mib=0,
        sample_seconds=1,
        execution_timeout_seconds=10,
        termination_grace_seconds=1,
    )

    with pytest.raises(midas_resource_preflight.AdmissionError, match="matching transient service"):
        midas_resource_preflight._run_inside(args, ["/usr/bin/true"])
    status = json.loads(status_path.read_text())
    assert status["phase"] == "inner_gate_failed"
    assert status["decision"] == "DENY"


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
def test_veritas_run_cannot_exceed_its_fixed_scope_limits(overrides: dict, tmp_path: Path) -> None:
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
        "storage_path": ["/tmp"],
        "storage_required_mib": 0,
        "storage_reserve_mib": 0,
        "termination_grace_seconds": 1,
        "label": "limit-test",
        "receipt_dir": str(tmp_path / "receipts"),
    }
    values.update(overrides)
    assert midas_resource_preflight._run_command(Namespace(**values)) == 75
    receipt = next((tmp_path / "receipts").glob("*.json"))
    assert json.loads(receipt.read_text())["final_classification"] == "preflight_denied"


@pytest.mark.parametrize(
    ("post_state_invalid", "expected_exit", "expected_classification"),
    [(False, 0, "worker_succeeded"), (True, 77, "post_execution_state_invalid")],
)
def test_veritas_run_uses_sandboxed_service_and_existing_resource_limits(
    monkeypatch,
    tmp_path: Path,
    post_state_invalid: bool,
    expected_exit: int,
    expected_classification: str,
) -> None:
    from argparse import Namespace

    commands: list[list[str]] = []

    class Lock:
        def close(self) -> None:
            pass

    class Process:
        stdout = None
        stderr = None

        def poll(self) -> int:
            return 0

        def wait(self, *, timeout: float) -> int:
            assert timeout == 600
            return 0

    monkeypatch.setattr(midas_resource_preflight, "_acquire_lock", Lock)
    monkeypatch.setattr(
        midas_resource_preflight, "_validate_veritas_runtime_context", lambda: "a" * 32
    )
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_SERVICE_ROOT", tmp_path)
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_OUTPUT_ROOT", tmp_path)
    release_root = tmp_path / "release"
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_RELEASE_ROOT", release_root)
    monkeypatch.setattr(
        midas_resource_preflight,
        "_validate_veritas_worker_command",
        lambda *_args: {"passed": True, "manifest_sha256": "c" * 64},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "verify_veritas_checkpoint",
        lambda *_args, **_kwargs: {
            "passed": True,
            "state_sha256": "b" * 64,
            "schema_version": 1,
            "processed_segment_count": 100,
            "last_ordinal": 100,
            "processed_source_bytes": 1000,
        },
    )

    def verify_post_state(*_args, **_kwargs):
        if post_state_invalid:
            raise midas_resource_preflight.AdmissionError("synthetic post-state corruption")
        return {
            "passed": True,
            "schema_version": 2,
            "processed_segment_count": 100,
            "processed_source_bytes": 1000,
        }

    monkeypatch.setattr(
        midas_resource_preflight, "verify_veritas_post_execution_state", verify_post_state
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_gate",
        lambda *_args, **_kwargs: ({"decision": "ADMIT"}, []),
    )
    monkeypatch.setattr(midas_resource_preflight, "_print_evidence", lambda _evidence: None)

    def fake_popen(command, **kwargs):
        assert kwargs["stdin"] == midas_resource_preflight.subprocess.DEVNULL
        status_index = command.index("--status-path")
        status_path = Path(command[status_index + 1])
        invocation_index = command.index("--invocation-id")
        invocation_id = command[invocation_index + 1]
        midas_resource_preflight._write_inner_status(
            status_path,
            invocation_id,
            phase="worker_finished",
            decision="ADMIT",
            worker_exit_code=0,
            worker_started_at_utc="2026-11-08T00:00:00Z",
            worker_completed_at_utc="2026-11-08T00:00:01Z",
            worker_runtime_seconds=1.0,
            cgroup_metrics={"available": True, "memory": {"oom_kill_events": 0}},
            execution_context={
                "release": {"passed": True},
                "transient_unit": {"available": True, "limits_verified": True},
            },
        )
        commands.append(command)
        return Process()

    monkeypatch.setattr(
        midas_resource_preflight,
        "_unit_snapshot",
        lambda _unit: _unit_properties(),
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_unit_snapshot_after_wait",
        lambda _unit: {"LoadState": "not-found"},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_wait_for_transient_unit_cleanup",
        lambda _unit: {"confirmed": True, "unit_absent": True},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    monkeypatch.setattr(
        midas_resource_preflight.subprocess,
        "Popen",
        fake_popen,
    )
    args = Namespace(
        profile="veritas",
        command=["--", *midas_resource_preflight._veritas_worker_command(release_root)],
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
        receipt_dir=str(tmp_path / "receipts"),
        source_revision=midas_resource_preflight.VERITAS_APPROVED_SOURCE_REVISION,
        release_identity=midas_resource_preflight.VERITAS_RELEASE_ID,
        release_root=str(release_root),
        expected_module_sha256=midas_resource_preflight.VERITAS_APPROVED_MODULE_SHA256,
    )

    assert midas_resource_preflight._run_command(args) == expected_exit
    command = commands[0]
    receipts = list((tmp_path / "receipts").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
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
    read_write_paths = next(
        item for item in command if item.startswith("--property=ReadWritePaths=")
    )
    assert read_write_paths.endswith(str(midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET))
    assert "--property=PrivateTmp=yes" in command
    assert "--property=NoNewPrivileges=yes" in command
    assert "--property=RuntimeMaxSec=600s" in command
    assert "--property=KillMode=control-group" in command
    assert "--property=Restart=no" in command
    assert "--property=StandardOutput=journal" in command
    assert "--property=StandardError=journal" in command
    assert f"--property=WorkingDirectory={tmp_path}" in command
    assert receipt["requested_systemd_properties"]["Environment"]["XDG_RUNTIME_DIR"] == str(
        midas_resource_preflight.VERITAS_USER_MANAGER_RUNTIME_DIR
    )
    assert (
        receipt["requested_systemd_properties"]["Environment"]["DBUS_SESSION_BUS_ADDRESS"]
        == f"unix:path={midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET}"
    )
    assert "--service-type=exec" in command
    assert "--wait" in command
    assert "--collect" in command
    assert "--scope" not in command
    assert (
        "--setenv=PYTHONPATH="
        f"{release_root / 'packages'}:{midas_resource_preflight.VERITAS_RUNTIME_SITE_PACKAGES}"
    ) in command
    assert (
        f"--setenv=XDG_RUNTIME_DIR={midas_resource_preflight.VERITAS_USER_MANAGER_RUNTIME_DIR}"
    ) in command
    assert (
        "--setenv=DBUS_SESSION_BUS_ADDRESS=unix:path="
        f"{midas_resource_preflight.VERITAS_USER_MANAGER_BUS_SOCKET}"
    ) in command
    assert command[-4:] == ["--max-segments", "128", "--max-source-mib", "32"]
    assert receipt["final_classification"] == expected_classification
    assert receipt["post_execution_verification"]["passed"] is not post_state_invalid
    assert receipt["source_revision"] == midas_resource_preflight.VERITAS_APPROVED_SOURCE_REVISION
    assert receipt["release_identity"] == midas_resource_preflight.VERITAS_RELEASE_ID
    assert receipt["outer_admission"]["decision"] == "ADMIT"
    assert receipt["inner_admission"]["decision"] == "ADMIT"
    assert receipt["worker"]["start_confirmed"] is True
    assert receipt["inner_status_record"]["phase"] == "worker_finished"
    assert receipt["artifacts"]["inner_status_collected"] is True
    assert Path(receipt["artifacts"]["inner_status"]).is_file()
    assert os.stat(receipts[0]).st_mode & 0o777 == 0o600


def test_inner_admission_denial_is_durable_and_never_starts_worker(
    monkeypatch, tmp_path: Path
) -> None:
    from argparse import Namespace

    invocation_id = "e" * 32
    status_dir = tmp_path / f"{invocation_id}.control"
    status_dir.mkdir(mode=0o700)
    status_path = status_dir / "inner-status.json"
    monkeypatch.setattr(
        midas_resource_preflight,
        "_gate",
        lambda *_args, **_kwargs: ({"decision": "DENY"}, ["synthetic inner denial"]),
    )
    parent_invocation = "f" * 32
    monkeypatch.setattr(
        midas_resource_preflight,
        "_validate_veritas_runtime_context",
        lambda **_kwargs: parent_invocation,
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_validate_veritas_worker_command",
        lambda *_args, **_kwargs: {"passed": True, "manifest_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "verify_veritas_checkpoint",
        lambda *_args, **_kwargs: {"passed": True, "state_sha256": "b" * 64, "schema_version": 1},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_validate_veritas_transient_unit",
        lambda **_kwargs: {"available": True, "limits_verified": True},
    )
    monkeypatch.setattr(midas_resource_preflight, "VERITAS_OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(
        midas_resource_preflight.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("worker must not start after inner denial"),
    )
    args = Namespace(
        invocation_id=invocation_id,
        status_path=str(status_path),
        profile="veritas",
        memory_budget_mib=128,
        storage_path=[str(tmp_path)],
        storage_required_mib=0,
        storage_reserve_mib=0,
        sample_seconds=30,
        execution_timeout_seconds=600,
        termination_grace_seconds=1,
        release_root=str(tmp_path / "release"),
        expected_module_sha256=midas_resource_preflight.VERITAS_APPROVED_MODULE_SHA256,
        expected_checkpoint_state_sha256="b" * 64,
        parent_service_invocation_id=parent_invocation,
        parent_service_pid=os.getpid(),
    )
    assert midas_resource_preflight._run_inside(args, [sys.executable, "-c", "pass"]) == 75
    status = json.loads(status_path.read_text())
    assert status["phase"] == "inner_admission_denied"
    assert status["decision"] == "DENY"


def test_missing_final_receipt_fails_closed_and_preserves_inner_evidence(
    monkeypatch, tmp_path: Path
) -> None:
    original_write = midas_resource_preflight._atomic_json_write

    def fail_final_write(path: Path, payload: dict, **kwargs) -> None:
        if path.name.endswith(".json") and payload.get("phase") == "completed":
            raise midas_resource_preflight.AdmissionError("synthetic interrupted collection")
        original_write(path, payload, **kwargs)

    monkeypatch.setattr(midas_resource_preflight, "_atomic_json_write", fail_final_write)
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        inner={
            "phase": "worker_finished",
            "worker_exit_code": 0,
            "worker_runtime_seconds": 0.01,
        },
        unit=_unit_properties(),
    )
    assert code == midas_resource_preflight.RUNNER_RESULT_MISSING
    assert receipt["final_classification"] == "indeterminate"
    receipt_path = next((tmp_path / "receipts").glob("*.json"))
    status_path = Path(receipt["artifacts"]["inner_status"])
    assert receipt_path.exists()
    assert status_path.exists()


def test_uncertain_final_receipt_rename_is_rewritten_as_indeterminate(
    monkeypatch, tmp_path: Path
) -> None:
    original_write = midas_resource_preflight._atomic_json_write
    failed_after_replace = False

    def fail_after_final_replace(path: Path, payload: dict, **kwargs) -> None:
        nonlocal failed_after_replace
        original_write(path, payload, **kwargs)
        if payload.get("phase") == "completed" and not failed_after_replace:
            failed_after_replace = True
            raise OSError("synthetic directory fsync failure")

    monkeypatch.setattr(midas_resource_preflight, "_atomic_json_write", fail_after_final_replace)
    code, receipt, receipt_path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        inner={"phase": "worker_finished", "worker_exit_code": 0},
        unit=_unit_properties(),
    )
    assert code == midas_resource_preflight.RUNNER_RESULT_MISSING
    assert receipt["final_classification"] == "indeterminate"
    assert json.loads(receipt_path.read_text())["final_classification"] == "indeterminate"


def _unit_properties(
    *,
    active: str = "inactive",
    result: str = "success",
    started: bool = True,
    code: str = "exited",
    status: int = 0,
) -> dict[str, str]:
    return {
        "LoadState": "loaded",
        "ActiveState": active,
        "SubState": "dead" if active == "inactive" else active,
        "Result": result,
        "InvocationID": "a" * 32,
        "MainPID": "0",
        "ControlPID": "0",
        "ExecMainCode": code,
        "ExecMainStatus": str(status),
        "ExecMainStartTimestamp": "Sun 2026-11-08 00:00:00 UTC" if started else "n/a",
        "ExecMainExitTimestamp": "Sun 2026-11-08 00:00:01 UTC",
        "ControlGroup": "/user.slice/test.service",
    }


def _fake_guarded_run(
    monkeypatch,
    tmp_path: Path,
    *,
    runner_code: int = 0,
    inner: dict | None = None,
    unit: dict[str, str] | None = None,
    stderr: str = "",
    popen_error: OSError | None = None,
    outer_reasons: list[str] | None = None,
    profile: str = "heavy",
) -> tuple[int, dict, Path]:
    from argparse import Namespace

    lock = type("Lock", (), {"close": lambda self: None})()
    monkeypatch.setattr(midas_resource_preflight, "_acquire_lock", lambda: lock)
    monkeypatch.setattr(midas_resource_preflight, "_validate_veritas_runtime_context", lambda: None)
    monkeypatch.setattr(
        midas_resource_preflight,
        "_gate",
        lambda *_args, **_kwargs: (
            {"decision": "DENY" if outer_reasons else "ADMIT"},
            outer_reasons or [],
        ),
    )
    monkeypatch.setattr(midas_resource_preflight, "_print_evidence", lambda *_args: None)
    monkeypatch.setattr(
        midas_resource_preflight,
        "_read_veritas_runtime_io_pressure",
        lambda: {"avg10": 0.0, "avg60": 0.0},
    )
    monkeypatch.setattr(midas_resource_preflight, "_unit_snapshot", lambda _unit: unit)
    monkeypatch.setattr(
        midas_resource_preflight,
        "_systemctl",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    real_popen = subprocess.Popen

    def fake_popen(command, **kwargs):
        if popen_error is not None:
            raise popen_error
        status_path = Path(command[command.index("--status-path") + 1])
        invocation_id = command[command.index("--invocation-id") + 1]
        if inner is not None:
            midas_resource_preflight._write_inner_status(
                status_path,
                invocation_id,
                phase=inner.get("phase", "worker_finished"),
                decision=inner.get("decision", "ADMIT"),
                **{key: value for key, value in inner.items() if key not in {"phase", "decision"}},
            )
        elif inner is False:
            status_path.unlink()
        runner = [
            sys.executable,
            "-c",
            "import sys,time; time.sleep(0.02); sys.exit(int(sys.argv[1]))",
            str(runner_code),
        ]
        if stderr:
            runner[2] = "import sys; sys.stderr.write(sys.argv[2]); sys.exit(int(sys.argv[1]))"
            runner.append(stderr)
        return real_popen(runner, **kwargs)

    monkeypatch.setattr(midas_resource_preflight.subprocess, "Popen", fake_popen)
    args = Namespace(
        profile=profile,
        command=["--", "/synthetic/worker", "arg"],
        memory_high_mib=192,
        memory_max_mib=256,
        memory_budget_mib=128,
        cpu_quota_percent=100,
        timeout_seconds=600,
        sample_seconds=30,
        label="synthetic",
        storage_path=[str(tmp_path)],
        storage_required_mib=0,
        storage_reserve_mib=0,
        termination_grace_seconds=0.1,
        receipt_dir=str(tmp_path / "receipts"),
        source_revision="a" * 40,
        release_identity="synthetic-release-v1",
    )
    code = midas_resource_preflight._run_command(args)
    receipt_path = next((tmp_path / "receipts").glob("*.json"))
    return code, json.loads(receipt_path.read_text()), receipt_path


def test_receipt_is_atomic_private_and_starts_indeterminate(tmp_path: Path) -> None:
    receipt_dir = midas_resource_preflight._prepare_receipt_directory(tmp_path / "state")
    args = type(
        "Args",
        (),
        {
            "profile": "veritas",
            "label": "test",
            "memory_high_mib": 192,
            "memory_max_mib": 256,
            "memory_budget_mib": 128,
            "cpu_quota_percent": 100,
            "timeout_seconds": 600,
            "source_revision": "a" * 40,
            "release_identity": "candidate-v1",
        },
    )()
    receipt, path, _status = midas_resource_preflight._new_execution_receipt(
        args, ["/usr/bin/python", "--token=private-value"], receipt_dir
    )
    second_identity = midas_resource_preflight._command_identity(
        ["/usr/bin/python", "--token=another-private-value"]
    )
    assert receipt["final_classification"] == "indeterminate"
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert "private-value" not in path.read_text()
    assert second_identity == receipt["command_identity"]
    assert not list(receipt_dir.glob("*.tmp"))


def test_atomic_receipt_write_removes_temporary_file_after_write_failure(
    monkeypatch, tmp_path: Path
) -> None:
    receipt_dir = midas_resource_preflight._prepare_receipt_directory(tmp_path / "receipts")

    def fail_fsync(_descriptor: int) -> None:
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(midas_resource_preflight.os, "fsync", fail_fsync)
    target = receipt_dir / "interrupted.json"
    with pytest.raises(OSError, match="synthetic fsync failure"):
        midas_resource_preflight._atomic_json_write(target, {"phase": "started"})
    assert not target.exists()
    assert not list(receipt_dir.glob(".*.json.*.*.tmp"))


def test_receipt_retention_keeps_recent_results_and_prunes_sidecars_with_them(
    tmp_path: Path,
) -> None:
    receipt_dir = midas_resource_preflight._prepare_receipt_directory(tmp_path / "receipts")
    oldest_receipt: Path | None = None
    oldest_control: Path | None = None
    for index in range(midas_resource_preflight.GUARDED_RECEIPT_KEEP_COMPLETED + 1):
        invocation_id = f"{index + 1:032x}"
        control_dir = receipt_dir / f"{invocation_id}.control"
        control_dir.mkdir(mode=0o700)
        status_path = control_dir / "inner-status.json"
        midas_resource_preflight._atomic_json_write(status_path, {"phase": "worker_finished"})
        receipt_path = receipt_dir / f"{invocation_id}.json"
        midas_resource_preflight._atomic_json_write(
            receipt_path,
            {
                "invocation_id": invocation_id,
                "final_classification": "worker_succeeded",
                "artifacts": {"inner_status": str(status_path)},
            },
        )
        os.utime(receipt_path, (1000 + index, 1000 + index))
        if index == 0:
            oldest_receipt = receipt_path
            oldest_control = control_dir

    midas_resource_preflight._prune_execution_receipts(receipt_dir)
    assert oldest_receipt is not None and oldest_control is not None
    assert not oldest_receipt.exists()
    assert not oldest_control.exists()
    assert (
        len(list(receipt_dir.glob("*.json")))
        == midas_resource_preflight.GUARDED_RECEIPT_KEEP_COMPLETED
    )


def test_receipt_pruning_removes_only_stale_owned_atomic_write_temporaries(
    tmp_path: Path,
) -> None:
    receipt_dir = midas_resource_preflight._prepare_receipt_directory(tmp_path / "receipts")
    stale = receipt_dir / ".old.json.123.deadbeef.tmp"
    recent = receipt_dir / ".new.json.456.deadbeef.tmp"
    stale.write_text("stale", encoding="utf-8")
    recent.write_text("active", encoding="utf-8")
    os.utime(stale, (1000, 1000))

    midas_resource_preflight._prune_execution_receipts(receipt_dir)

    assert not stale.exists()
    assert recent.exists()


def test_receipt_pool_at_hard_capacity_fails_closed(tmp_path: Path) -> None:
    receipt_dir = midas_resource_preflight._prepare_receipt_directory(tmp_path / "receipts")
    for index in range(midas_resource_preflight.GUARDED_RECEIPT_MAX_FILES):
        (receipt_dir / f"opaque-{index}.json").write_text("not a receipt", encoding="utf-8")
    with pytest.raises(midas_resource_preflight.AdmissionError, match="capacity is full"):
        midas_resource_preflight._prune_execution_receipts(receipt_dir, reserve_slot=True)


@pytest.mark.parametrize(
    ("runner_code", "inner", "unit", "expected"),
    [
        (
            0,
            {
                "phase": "worker_finished",
                "worker_exit_code": 0,
                "worker_started_at_utc": "2026-11-08T00:00:00Z",
                "worker_completed_at_utc": "2026-11-08T00:00:01Z",
                "worker_runtime_seconds": 1.0,
            },
            _unit_properties(),
            "worker_succeeded",
        ),
        (
            7,
            {
                "phase": "worker_finished",
                "worker_exit_code": 7,
                "worker_started_at_utc": "2026-11-08T00:00:00Z",
            },
            _unit_properties(result="exit-code", status=7),
            "worker_failed",
        ),
        (
            75,
            {"phase": "inner_admission_denied", "decision": "DENY"},
            _unit_properties(result="exit-code", status=75),
            "admission_denied",
        ),
        (
            127,
            {"phase": "worker_start_failed", "worker_error": "synthetic exec error"},
            _unit_properties(result="exit-code", status=127),
            "worker_startup_failed",
        ),
        (
            1,
            {
                "phase": "worker_running",
                "cgroup_metrics": {"memory": {"oom_kill_events": 1}},
            },
            _unit_properties(result="oom-kill", code="killed", status=9),
            "worker_killed_oom_or_oomd",
        ),
        (
            143,
            {"phase": "worker_finished", "worker_signal": signal.SIGTERM},
            _unit_properties(result="signal", code="killed", status=15),
            "worker_terminated_by_signal",
        ),
        (
            77,
            None,
            _unit_properties(result="exit-code", status=77),
            "result_missing_indeterminate",
        ),
    ],
)
def test_guarded_run_classifies_worker_and_gate_outcomes(
    monkeypatch,
    tmp_path: Path,
    runner_code: int,
    inner: dict | None,
    unit: dict[str, str] | None,
    expected: str,
) -> None:
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        runner_code=runner_code,
        inner=inner,
        unit=unit,
    )
    assert receipt["final_classification"] == expected
    if expected == "worker_succeeded":
        assert code == 0
    else:
        assert code != 0
    assert receipt["transient_unit"]["invocation_id"] == "a" * 32
    assert receipt["log_references"]["journal_invocation"].endswith("a" * 32)


def test_guarded_run_distinguishes_unit_start_failure_missing_bus_and_popen_failure(
    monkeypatch, tmp_path: Path
) -> None:
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path / "start-fail",
        runner_code=1,
        unit=_unit_properties(active="failed", result="resources", started=False),
    )
    assert code != 0
    assert receipt["final_classification"] == "unit_created_not_started"

    monkeypatch.undo()
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path / "bus-fail",
        runner_code=1,
        stderr=(
            "Failed to connect to bus: No medium found token=synthetic-secret "
            "/home/private/manager/path"
        ),
    )
    assert code != 0
    assert receipt["final_classification"] == "unit_creation_failed"
    assert receipt["systemd_run_client"]["output"]["stderr"]["diagnostic_type"] == (
        "systemd_bus_unavailable"
    )
    monkeypatch.undo()
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path / "popen-fail",
        popen_error=FileNotFoundError("systemd-run missing"),
    )
    assert code != 0
    assert receipt["final_classification"] == "unit_creation_failed"


def test_outer_admission_denial_is_durable_and_does_not_create_a_unit(
    monkeypatch, tmp_path: Path
) -> None:
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        outer_reasons=["synthetic outer denial"],
    )
    assert code == 75
    assert receipt["outer_admission"]["decision"] == "DENY"
    assert receipt["final_classification"] == "admission_denied"
    assert receipt["transient_unit"]["last_observed_state"] == "not_requested"


def test_runner_exit_while_transient_unit_active_cancels_and_fails_indeterminate(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        midas_resource_preflight,
        "_kill_unit",
        lambda unit, grace: calls.append((unit, str(grace))),
    )
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        runner_code=0,
        inner={"phase": "worker_running"},
        unit=_unit_properties(active="active", result="success", started=True),
    )
    assert code == midas_resource_preflight.RUNNER_RESULT_MISSING
    assert receipt["final_classification"] == "result_missing_indeterminate"
    assert calls and calls[0][0] == receipt["transient_unit"]["name"]


def test_cancellation_classification_requires_confirmed_worker_or_unit_termination() -> None:
    active_unit = _unit_properties(active="active", started=True)
    running_worker = {"phase": "worker_running"}
    common = {
        "profile": "veritas",
        "return_code": 76,
        "unit": active_unit,
        "inner": running_worker,
        "runner_error": None,
        "unit_was_active_after_client_exit": False,
    }
    assert (
        midas_resource_preflight._classify_guarded_result(
            **common,
            watchdog={"kind": "io_full_avg10_pressure_above_runtime_hard_limit"},
            parent_signal=None,
        )
        == "result_missing_indeterminate"
    )
    assert (
        midas_resource_preflight._classify_guarded_result(
            **common,
            watchdog=None,
            parent_signal=signal.SIGTERM,
        )
        == "result_missing_indeterminate"
    )

    stopped_unit = _unit_properties(active="inactive", result="signal", started=True)
    assert (
        midas_resource_preflight._classify_guarded_result(
            **{**common, "unit": stopped_unit},
            watchdog={"kind": "io_full_avg10_pressure_above_runtime_hard_limit"},
            parent_signal=None,
        )
        == "psi_watchdog_cancelled"
    )
    assert (
        midas_resource_preflight._classify_guarded_result(
            **{**common, "unit": stopped_unit},
            watchdog=None,
            parent_signal=signal.SIGTERM,
        )
        == "cancelled_by_parent_signal"
    )


def test_synthetic_classification_requires_worker_wait_limits_and_cleanup_evidence() -> None:
    unit = _unit_properties()
    inner = {"phase": "worker_exec_requested", "decision": "ADMIT"}
    common = {
        "profile": "synthetic-validation",
        "return_code": 0,
        "unit": unit,
        "inner": inner,
        "watchdog": None,
        "parent_signal": None,
        "runner_error": None,
        "unit_was_active_after_client_exit": False,
        "systemd_wait_completed": True,
        "synthetic_expected_exit": 0,
        "applied_limits_verified": True,
        "unit_cleanup_confirmed": True,
    }
    assert midas_resource_preflight._classify_guarded_result(**common) == "worker_succeeded"
    assert (
        midas_resource_preflight._classify_guarded_result(
            **{**common, "applied_limits_verified": False}
        )
        == "result_missing_indeterminate"
    )
    assert (
        midas_resource_preflight._classify_guarded_result(
            **{**common, "unit_cleanup_confirmed": False}
        )
        == "result_missing_indeterminate"
    )
    assert (
        midas_resource_preflight._classify_guarded_result(
            **{**common, "systemd_wait_completed": False}
        )
        == "result_missing_indeterminate"
    )
    assert (
        midas_resource_preflight._classify_guarded_result(**{**common, "unit": None})
        == "result_missing_indeterminate"
    )
    negative = {**common, "return_code": 1, "synthetic_expected_exit": 1}
    assert midas_resource_preflight._classify_guarded_result(**negative) == "worker_failed"
    assert (
        midas_resource_preflight._classify_guarded_result(
            **{
                **negative,
                "unit_after_wait": {
                    "LoadState": "loaded",
                    "Result": "success",
                    "ExecMainStatus": "0",
                    "ExecMainCode": "exited",
                },
            }
        )
        == "result_missing_indeterminate"
    )


@pytest.mark.parametrize(
    ("command", "runner_code", "expected_classification"),
    [
        (["/usr/bin/true"], 0, "worker_succeeded"),
        (["/usr/bin/false"], 1, "worker_failed"),
    ],
)
def test_synthetic_guarded_run_builds_isolated_service_and_keeps_receipt(
    monkeypatch,
    tmp_path: Path,
    command: list[str],
    runner_code: int,
    expected_classification: str,
) -> None:
    from argparse import Namespace

    root = tmp_path / "synthetic-root"
    root.mkdir(mode=0o700)
    launcher = root / "midas_resource_preflight.py"
    launcher.write_text("# immutable test fixture\n", encoding="utf-8")
    launcher.chmod(0o444)
    receipts = root / "receipts"
    monkeypatch.setattr(midas_resource_preflight, "SYNTHETIC_TEST_ROOT", root)
    monkeypatch.setattr(midas_resource_preflight, "SYNTHETIC_RECEIPT_DIR", receipts)
    monkeypatch.setattr(midas_resource_preflight, "__file__", str(launcher))
    monkeypatch.setattr(midas_resource_preflight, "_prepare_synthetic_test_root", lambda: root)
    monkeypatch.setattr(
        midas_resource_preflight,
        "_acquire_lock",
        lambda: type("Lock", (), {"close": lambda self: None})(),
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_gate",
        lambda *_args, **_kwargs: ({"decision": "ADMIT"}, []),
    )
    monkeypatch.setattr(midas_resource_preflight, "_print_evidence", lambda *_args: None)
    cgroup_metrics = {
        "available": True,
        "cgroup": "/sys/fs/cgroup/user.slice/test.service",
        "memory_peak_bytes": 20 * midas_resource_preflight.MIB,
        "memory": {"memory_high_bytes": 32 * midas_resource_preflight.MIB},
        "cpu": {"usage_usec": 1000},
        "io_weight": "default 10",
        "limits": {
            "memory.high": str(32 * midas_resource_preflight.MIB),
            "memory.max": str(64 * midas_resource_preflight.MIB),
            "memory.swap.max": "0",
            "cpu.max": "10000 100000",
            "pids.max": "8",
        },
    }
    monkeypatch.setattr(
        midas_resource_preflight,
        "_cgroup_execution_metrics",
        lambda *_args, **_kwargs: cgroup_metrics,
    )
    unit_properties = _unit_properties(
        result="success" if runner_code == 0 else "exit-code", status=runner_code
    )
    unit_properties.update(
        {
            "Transient": "yes",
            "MemoryHigh": str(32 * midas_resource_preflight.MIB),
            "MemoryMax": str(64 * midas_resource_preflight.MIB),
            "MemorySwapMax": "0",
            "CPUQuotaPerSecUSec": "100ms",
            "IOWeight": "10",
            "TasksMax": "8",
            "RuntimeMaxUSec": "10s",
            "NoNewPrivileges": "yes",
            "RestrictAddressFamilies": "AF_UNIX",
            "SystemCallArchitectures": "native",
        }
    )
    systemd_commands: list[list[str]] = []
    real_popen = subprocess.Popen

    def fake_popen(systemd_command, **kwargs):
        systemd_commands.append(list(systemd_command))
        unit_name = next(
            arg.partition("=")[2] for arg in systemd_command if arg.startswith("--unit=")
        )
        invocation_id = systemd_command[systemd_command.index("--invocation-id") + 1]
        status_path = Path(systemd_command[systemd_command.index("--status-path") + 1])
        unit_properties["InvocationID"] = "b" * 32
        unit_properties["ControlGroup"] = "/user.slice/test.service"
        midas_resource_preflight._write_inner_status(
            status_path,
            invocation_id,
            phase="worker_exec_requested",
            decision="ADMIT",
            worker_start_requested_at_utc="2026-11-09T00:00:00Z",
            worker_start_requested_monotonic=midas_resource_preflight.time.monotonic(),
            synthetic_context={
                "expected_worker_exit_code": runner_code,
                "unit": unit_name,
                "unit_properties": dict(unit_properties),
                "cgroup_metrics": cgroup_metrics,
                "network_isolation": {
                    "restricted": True,
                    "mechanism": "seccomp-bpf",
                    "mode": 2,
                    "probes": {
                        "AF_INET": "denied",
                        "AF_INET6": "denied",
                        "AF_UNIX": "denied",
                    },
                },
            },
            filesystem_isolation={"enforced": True, "abi": 8, "denied_paths": ["/home/charlie"]},
        )
        return real_popen(
            [
                sys.executable,
                "-c",
                "import sys,time; time.sleep(0.02); sys.exit(int(sys.argv[1]))",
                str(runner_code),
            ],
            **kwargs,
        )

    monkeypatch.setattr(midas_resource_preflight.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        midas_resource_preflight, "_unit_snapshot", lambda _unit: dict(unit_properties)
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_unit_snapshot_after_wait",
        lambda _unit: {"LoadState": "not-found"},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_wait_for_transient_unit_cleanup",
        lambda _unit: {
            "confirmed": True,
            "unit_absent": True,
            "last_properties": {"LoadState": "not-found"},
        },
    )
    args = Namespace(
        profile="synthetic-validation",
        command=["--", *command],
        memory_high_mib=32,
        memory_max_mib=64,
        memory_budget_mib=8,
        cpu_quota_percent=10,
        timeout_seconds=10,
        sample_seconds=1,
        label="smoke",
        storage_path=[str(root)],
        storage_required_mib=0,
        storage_reserve_mib=0,
        termination_grace_seconds=0.5,
        receipt_dir=None,
        source_revision="dce9bfa33deee844530f0fa1e165a4e3fd554124",
        release_identity="synthetic-systemd-smoke",
    )

    exit_code = midas_resource_preflight._run_command(args)
    receipt_path = next(receipts.glob("*.json"))
    receipt = json.loads(receipt_path.read_text())
    assert receipt["final_classification"] == expected_classification
    assert receipt["execution_scope"] == "disposable_synthetic_validation"
    assert receipt["production_admission"] is False
    assert receipt["transient_unit"]["type"] == "service"
    assert receipt["transient_unit"]["name"].startswith("midas-synthetic-validation-")
    assert receipt["worker"]["start_confirmed"] is True
    assert receipt["applied_limits_verification"]["passed"] is True
    assert receipt["transient_unit"]["cleanup"]["unit_absent"] is True
    assert receipt["cgroup_metrics"]["limits"]["memory.max"] == str(
        64 * midas_resource_preflight.MIB
    )
    assert receipt_path.is_file()
    assert exit_code == runner_code
    assert "--service-type=exec" in systemd_commands[0]
    assert "--wait" in systemd_commands[0]
    assert "--collect" in systemd_commands[0]
    assert "--scope" not in systemd_commands[0]
    assert "--property=MemoryHigh=32M" in systemd_commands[0]
    assert "--property=MemoryMax=64M" in systemd_commands[0]
    assert "--property=MemorySwapMax=0" in systemd_commands[0]
    assert "--property=CPUQuota=10%" in systemd_commands[0]
    assert "--property=TasksMax=8" in systemd_commands[0]
    assert "--property=NoNewPrivileges=yes" in systemd_commands[0]
    assert "--property=RestrictAddressFamilies=AF_UNIX" in systemd_commands[0]
    assert "--property=SystemCallArchitectures=native" in systemd_commands[0]
    assert not any("PrivateNetwork" in item for item in systemd_commands[0])


@pytest.mark.parametrize(
    ("runner_code", "expected", "start_confirmed"),
    [
        (0, "worker_succeeded", True),
        (9, "worker_failed", True),
        (127, "result_missing_indeterminate", False),
    ],
)
def test_scope_profiles_require_worker_exec_receipt_and_exit_agreement(
    monkeypatch,
    tmp_path: Path,
    runner_code: int,
    expected: str,
    start_confirmed: bool,
) -> None:
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        profile="heavy",
        runner_code=runner_code,
        inner={
            "phase": "worker_exec_requested",
            "worker_start_requested_at_utc": "2026-11-08T00:00:00Z",
            "worker_start_requested_monotonic": 100.0,
        },
        unit=None,
    )
    assert receipt["final_classification"] == expected
    assert receipt["worker"]["start_confirmed"] is start_confirmed
    assert (code == 0) is (expected == "worker_succeeded")


def test_scope_runner_timeout_records_cancellation_before_killing_unit(
    monkeypatch,
) -> None:
    class StuckProcess:
        stdout = None
        stderr = None

        def poll(self) -> None:
            return None

    process = StuckProcess()
    output = midas_resource_preflight._RunnerOutput(process, ["systemd-run"])
    events: list[dict] = []
    monkeypatch.setattr(
        midas_resource_preflight,
        "_cancel_bounded_unit",
        lambda *_args: None,
    )
    try:
        result = midas_resource_preflight._wait_for_runner_process(
            process,
            "midas-heavy-synthetic.scope",
            timeout_seconds=0.01,
            termination_grace_seconds=0.01,
            output=output,
            on_timeout=events.append,
        )
    finally:
        output.close()
    assert result == 124
    assert events and events[0]["kind"] == "timeout"


def test_cancellation_records_systemd_bus_failure_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(
        midas_resource_preflight,
        "_systemctl",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            midas_resource_preflight.AdmissionError("synthetic bus unavailable")
        ),
    )
    result = midas_resource_preflight._kill_unit("midas-heavy-test.service", 0.01)
    assert result["term_requested"] is False
    assert result["inactive_confirmed"] is False
    assert "bus unavailable" in result["error"]


def test_cancellation_reaps_local_runner_client_if_systemd_is_unavailable(monkeypatch) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"], start_new_session=True
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_kill_unit",
        lambda *_args: {"inactive_confirmed": False, "error": "synthetic bus unavailable"},
    )
    result = midas_resource_preflight._cancel_bounded_unit(
        process, "midas-heavy-test.service", 0.01
    )
    assert process.poll() is not None
    assert result["runner_client_exit_confirmed"] is True
    assert result["systemd_unit"]["inactive_confirmed"] is False


@pytest.mark.parametrize(
    ("event", "runner_code", "expected"),
    [
        ({"kind": "timeout", "at_utc": "2026-11-08T00:00:00Z"}, 124, "timed_out"),
        ({"kind": "io_full_avg10_pressure_above_runtime_hard_limit"}, 76, "psi_watchdog_cancelled"),
    ],
)
def test_parent_watchdog_events_are_durable_and_fail_closed(
    monkeypatch, tmp_path: Path, event: dict, runner_code: int, expected: str
) -> None:
    original_wait = midas_resource_preflight._wait_for_runner_process

    def wait(process, unit, *, on_timeout=None, **kwargs):
        assert on_timeout is not None
        on_timeout(event)
        return runner_code

    monkeypatch.setattr(midas_resource_preflight, "_wait_for_runner_process", wait)
    monkeypatch.setattr(midas_resource_preflight, "_kill_unit", lambda *_args: None)
    code, receipt, _path = _fake_guarded_run(
        monkeypatch,
        tmp_path,
        runner_code=0,
        inner={
            "phase": "worker_running",
            "cgroup_metrics": {"memory": {"oom_kill_events": 0}},
        },
        unit=_unit_properties(active="inactive", result="signal", code="killed", status=15),
    )
    assert receipt["final_classification"] == expected
    assert receipt["watchdog_interventions"] == [event]
    assert code != 0
    monkeypatch.setattr(midas_resource_preflight, "_wait_for_runner_process", original_wait)


def test_runner_output_receipt_never_stores_raw_worker_or_secret_text(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys;print('private research payload', file=sys.stderr)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    collector = midas_resource_preflight._RunnerOutput(process, ["python", "--token=secret-value"])
    process.wait(timeout=5)
    summary = collector.summary()
    collector.close()
    encoded = json.dumps(summary)
    assert "private research payload" not in encoded
    assert "secret-value" not in encoded
    assert summary["stderr"]["bytes"] > 0
    assert "tail" not in summary["stderr"]


def test_veritas_systemd_error_excerpt_is_opt_in_and_redacted() -> None:
    message = (
        "Failed to start transient service unit: Invalid request descriptor "
        "token=synthetic-secret /home/private/manager/path"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys;sys.stderr.write(sys.argv[1])", message],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    collector = midas_resource_preflight._RunnerOutput(
        process, ["systemd-run"], include_systemd_error=True
    )
    process.wait(timeout=5)
    summary = collector.summary()
    collector.close()
    assert summary["stderr"]["message"] == (
        "Failed to start transient service unit: Invalid request descriptor "
        "token=<redacted> <redacted-path>"
    )
    assert "synthetic-secret" not in json.dumps(summary)
    assert "/home/private/manager/path" not in json.dumps(summary)


@pytest.mark.parametrize(
    ("worker_code", "expected", "timeout"),
    [
        ("import sys;sys.exit(0)", "worker_finished", 2.0),
        ("import sys;sys.exit(9)", "worker_finished", 2.0),
        ("import os,signal;os.kill(os.getpid(),signal.SIGTERM)", "worker_finished", 2.0),
        ("import time;time.sleep(5)", "worker_finished", 0.05),
    ],
)
def test_veritas_inner_supervisor_records_success_failure_signal_and_timeout(
    monkeypatch, tmp_path: Path, worker_code: str, expected: str, timeout: float
) -> None:
    invocation_id = "b" * 32
    status_dir = tmp_path / f"{invocation_id}.control"
    status_dir.mkdir(mode=0o700)
    status_path = status_dir / "inner-status.json"
    monkeypatch.setattr(
        midas_resource_preflight,
        "_cgroup_execution_metrics",
        lambda _path=None: {"available": True, "memory": {"oom_kill_events": 0}},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_read_veritas_runtime_io_pressure",
        lambda: {"avg10": 0.0, "avg60": 0.0},
    )
    monkeypatch.setitem(midas_resource_preflight.VERITAS_IO_RUNTIME, "poll_interval_seconds", 0.01)
    code = midas_resource_preflight._supervise_veritas_worker(
        [sys.executable, "-c", worker_code],
        status_path=status_path,
        invocation_id=invocation_id,
        timeout_seconds=timeout,
        termination_grace_seconds=0.05,
    )
    status = json.loads(status_path.read_text())
    assert status["phase"] == expected
    assert status["cgroup_metrics"]["memory"]["oom_kill_events"] == 0
    if timeout < 1:
        assert code == 124
        assert status["watchdog_intervention"]["kind"] == "timeout"


def test_veritas_inner_supervisor_cancels_on_pressure_and_fails_closed_without_psi(
    monkeypatch, tmp_path: Path
) -> None:
    invocation_id = "c" * 32
    status_dir = tmp_path / f"{invocation_id}.control"
    status_dir.mkdir(mode=0o700)
    status_path = status_dir / "inner-status.json"
    monkeypatch.setattr(
        midas_resource_preflight,
        "_cgroup_execution_metrics",
        lambda _path=None: {"available": True, "memory": {"oom_kill_events": 0}},
    )
    monkeypatch.setattr(
        midas_resource_preflight,
        "_read_veritas_runtime_io_pressure",
        lambda: {"avg10": 3.5, "avg60": 1.0},
    )
    monkeypatch.setitem(midas_resource_preflight.VERITAS_IO_RUNTIME, "poll_interval_seconds", 0.01)
    code = midas_resource_preflight._supervise_veritas_worker(
        [sys.executable, "-c", "import time;time.sleep(5)"],
        status_path=status_path,
        invocation_id=invocation_id,
        timeout_seconds=3,
        termination_grace_seconds=0.05,
    )
    status = json.loads(status_path.read_text())
    assert code == midas_resource_preflight.VERITAS_RUNTIME_PRESSURE_CANCELLED
    assert status["watchdog_intervention"]["kind"] == (
        "io_full_avg10_pressure_above_runtime_hard_limit"
    )

    status_path.unlink()
    monkeypatch.setattr(
        midas_resource_preflight,
        "_read_veritas_runtime_io_pressure",
        lambda: (_ for _ in ()).throw(
            midas_resource_preflight.AdmissionError("synthetic missing PSI")
        ),
    )
    code = midas_resource_preflight._supervise_veritas_worker(
        [sys.executable, "-c", "import time;time.sleep(5)"],
        status_path=status_path,
        invocation_id=invocation_id,
        timeout_seconds=3,
        termination_grace_seconds=0.05,
    )
    status = json.loads(status_path.read_text())
    assert code == midas_resource_preflight.VERITAS_RUNTIME_PRESSURE_CANCELLED
    assert status["watchdog_intervention"]["kind"] == "runtime_io_pressure_unavailable"


def test_veritas_inner_supervisor_records_failure_before_worker_initialization(
    monkeypatch, tmp_path: Path
) -> None:
    invocation_id = "d" * 32
    status_dir = tmp_path / f"{invocation_id}.control"
    status_dir.mkdir(mode=0o700)
    status_path = status_dir / "inner-status.json"
    monkeypatch.setattr(
        midas_resource_preflight.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FileNotFoundError("synthetic missing worker")
        ),
    )
    code = midas_resource_preflight._supervise_veritas_worker(
        ["/missing/worker"],
        status_path=status_path,
        invocation_id=invocation_id,
        timeout_seconds=2,
        termination_grace_seconds=0.1,
    )
    status = json.loads(status_path.read_text())
    assert code == 127
    assert status["phase"] == "worker_start_failed"


def test_systemd_transient_veritas_properties_parse_without_launching_a_unit(
    tmp_path: Path,
) -> None:
    parser = shutil.which("systemd-analyze")
    if parser is None:
        pytest.skip("systemd-analyze is unavailable in this environment")
    unit = tmp_path / "midas-guarded-veritas-test.service"
    unit.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Disposable MIDAS guarded-run parser fixture",
                "[Service]",
                "Type=exec",
                "ExecStart=/usr/bin/true",
                "MemoryHigh=192M",
                "MemoryMax=256M",
                "MemorySwapMax=0",
                "CPUQuota=100%",
                "IOWeight=10",
                "TasksMax=256",
                "RuntimeMaxSec=600s",
                "KillMode=control-group",
                "ProtectSystem=strict",
                "ProtectHome=read-only",
                f"ReadWritePaths={tmp_path}",
                "PrivateTmp=yes",
                "NoNewPrivileges=yes",
                "Nice=19",
                "IOSchedulingClass=idle",
                "Restart=no",
                "StandardOutput=journal",
                "StandardError=journal",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [parser, "verify", str(unit)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_systemd_transient_synthetic_validation_sandbox_passes_parser(tmp_path: Path) -> None:
    parser = shutil.which("systemd-analyze")
    if parser is None:
        pytest.skip("systemd-analyze is unavailable in this environment")
    unit = tmp_path / "midas-synthetic-validation-smoke.service"
    unit.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Disposable MIDAS guarded synthetic test",
                "[Service]",
                "Type=exec",
                "ExecStart=/usr/bin/true",
                "MemoryHigh=32M",
                "MemoryMax=64M",
                "MemorySwapMax=0",
                "CPUQuota=10%",
                "IOWeight=10",
                "TasksMax=8",
                "RuntimeMaxSec=10s",
                "TimeoutStartSec=10s",
                "KillMode=control-group",
                "Restart=no",
                "NoNewPrivileges=yes",
                "RestrictAddressFamilies=AF_UNIX",
                "SystemCallArchitectures=native",
                "UMask=0077",
                "WorkingDirectory=/",
                "StandardOutput=journal",
                "StandardError=journal",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [parser, "verify", str(unit)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
