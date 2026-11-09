#!/usr/bin/env python3
"""Run the packaged Veritas oneshot through a disposable real user manager."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import midas_resource_preflight as preflight  # noqa: E402

HOME = Path.home()
RELEASE = preflight.VERITAS_RELEASE_ROOT
CONFIG = json.loads((preflight.VERITAS_CI_ROOT / "fixture.json").read_text(encoding="utf-8"))
UNIT = preflight.VERITAS_CI_SERVICE_UNIT
UNIT_DIR = HOME / ".config" / "systemd" / "user"
DROPIN = UNIT_DIR / f"{UNIT}.d" / "10-systemd-ci.conf"
RECEIPTS = preflight.GUARDED_RECEIPT_DIR


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["systemctl", "--user", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if check and result.returncode:
        raise RuntimeError(f"systemctl --user {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def digest_tree(root: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            result.update(path.relative_to(root).as_posix().encode())
            result.update(b"\0")
            result.update(path.read_bytes())
    return result.hexdigest()


def configure_scenario(scenario: str) -> None:
    DROPIN.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    values = {
        "MIDAS_VERITAS_CI_TEST": preflight.VERITAS_CI_TEST_MARKER,
        "MIDAS_VERITAS_CI_CAMPAIGN_PATH": CONFIG["campaign_path"],
        "MIDAS_VERITAS_CI_CAMPAIGN_SHA256": CONFIG["campaign_sha256"],
        "MIDAS_VERITAS_CI_CAMPAIGN_ID": CONFIG["campaign_id"],
        "MIDAS_VERITAS_CI_SOURCE_ROOT": CONFIG["source_root"],
        "MIDAS_VERITAS_CI_PSI_FILE": CONFIG["pressure_file"],
        "MIDAS_VERITAS_CI_SCENARIO": scenario,
    }
    DROPIN.write_text(
        "[Service]\n"
        "ReadWritePaths=\n"
        f"ReadWritePaths={CONFIG['output_root']}\n"
        f"ReadWritePaths={RECEIPTS}\n"
        "RestrictAddressFamilies=AF_UNIX\n"
        + "".join(f"Environment={key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )
    command("daemon-reload")


def latest_receipt(
    before: set[Path], *, require_started: bool, timeout: float = 90
) -> tuple[Path, dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        candidates = [path for path in RECEIPTS.glob("*.json") if path not in before]
        for path in sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not require_started or receipt.get("worker", {}).get("start_confirmed"):
                return path, receipt
        time.sleep(0.1)
    raise TimeoutError("guarded execution receipt did not reach the expected worker phase")


def wait_unit(timeout: float = 180) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        props = preflight._properties(
            command(
                "show",
                UNIT,
                "-p",
                "ActiveState",
                "-p",
                "Result",
                "-p",
                "ExecMainStatus",
                "-p",
                "ExecMainCode",
                "-p",
                "InvocationID",
                "-p",
                "ExecStart",
            ).stdout
        )
        if props.get("InvocationID") and props.get("ActiveState") in {"inactive", "failed"}:
            return props
        time.sleep(0.2)
    raise TimeoutError("Veritas test oneshot did not terminate within the bound")


def run_scenario(
    scenario: str, *, expected_classification: str, require_started: bool
) -> tuple[Path, dict]:
    configure_scenario(scenario)
    command("reset-failed", UNIT, check=False)
    before = set(RECEIPTS.glob("*.json"))
    start = command("start", "--no-block", UNIT, check=False)
    if start.returncode:
        raise RuntimeError(f"could not queue {scenario} service: {start.stderr.strip()}")
    receipt_path, receipt = latest_receipt(before, require_started=require_started)
    if scenario == "watchdog":
        Path(CONFIG["pressure_file"]).write_text(
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
            "full avg10=4.00 avg60=4.00 avg300=4.00 total=0\n",
            encoding="ascii",
        )
    status = wait_unit()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("final_classification") != expected_classification:
        raise AssertionError(
            f"{scenario} classified as {receipt.get('final_classification')!r}, expected "
            f"{expected_classification!r}; receipt={receipt_path}"
        )
    if status.get("InvocationID") != receipt.get("service_owner", {}).get("invocation_id"):
        raise AssertionError("permanent service invocation and durable receipt identity differ")
    if not status.get("ExecMainStatus"):
        raise AssertionError("systemd did not retain the permanent unit exit status")
    result = receipt.get("result", {})
    expected_status = result.get("runner_exit_code")
    if not isinstance(expected_status, int) or status.get("ExecMainStatus") != str(expected_status):
        raise AssertionError("permanent service did not propagate the guarded worker exit status")
    expected_result = "success" if expected_status == 0 else "exit-code"
    if status.get("Result") != expected_result or status.get("ExecMainCode") != "exited":
        raise AssertionError("systemd parent result contradicts the durable guarded receipt")
    return receipt_path, receipt


def restore_pristine_state() -> None:
    output = Path(CONFIG["output_root"])
    shutil.rmtree(output)
    shutil.copytree(CONFIG["pristine_root"], output)


def install_test_manager_units() -> None:
    UNIT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copy2(RELEASE / "service" / "midas-veritas-source-analysis.service", UNIT_DIR / UNIT)
    shutil.copy2(
        REPO_ROOT / "deploy/systemd/user/midas-veritas-source-analysis.timer",
        UNIT_DIR / "midas-veritas-source-analysis.timer",
    )
    shutil.copy2(
        REPO_ROOT / "deploy/systemd/user/midas-reality-capacity.timer",
        UNIT_DIR / "midas-reality-capacity.timer",
    )
    command("daemon-reload")
    for timer in ("midas-veritas-source-analysis.timer", "midas-reality-capacity.timer"):
        props = preflight._properties(
            command("show", timer, "-p", "ActiveState", "-p", "UnitFileState").stdout
        )
        if props.get("ActiveState") != "inactive" or props.get("UnitFileState") != "disabled":
            raise AssertionError(f"test timer is not disabled and inactive: {timer}: {props}")


def start_protected_fixtures() -> None:
    for unit in ("midas-api.service", "midas-reality.service"):
        command(
            "reset-failed",
            unit,
            check=False,
        )
        result = subprocess.run(
            [
                "systemd-run",
                "--user",
                f"--unit={unit}",
                "--service-type=exec",
                "--property=MemoryHigh=1G",
                "--property=MemoryMax=2G",
                "--property=CPUQuota=100%",
                "--",
                "/usr/bin/sleep",
                "infinity",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode:
            raise RuntimeError(
                f"could not start disposable protected fixture {unit}: {result.stderr}"
            )
        command("is-active", "--quiet", unit)


def verify_receipt(path: Path, receipt: dict, *, worker_started: bool) -> None:
    if not path.is_file():
        raise AssertionError("durable receipt disappeared")
    if receipt.get("release_verification", {}).get("passed") is not True:
        raise AssertionError("receipt does not contain successful immutable release verification")
    if (
        receipt.get("release_verification", {}).get("module_sha256")
        != preflight.VERITAS_APPROVED_MODULE_SHA256
    ):
        raise AssertionError("receipt does not identify the approved Veritas module")
    if (
        receipt.get("validation_mode") != "isolated_systemd_ci"
        or receipt.get("execution_scope") != "isolated_systemd_ci_synthetic_research_fixture"
        or receipt.get("production_admission") is not False
    ):
        raise AssertionError(
            "synthetic execution receipt is not distinguished from production work"
        )
    if receipt.get("worker", {}).get("start_confirmed") is not worker_started:
        raise AssertionError("worker-start classification differs from the expected execution")
    cleanup = receipt.get("transient_unit", {}).get("cleanup", {})
    if worker_started and (
        cleanup.get("confirmed") is not True or cleanup.get("unit_absent") is not True
    ):
        raise AssertionError("transient unit cleanup was not verified")
    if worker_started:
        metrics = receipt.get("cgroup_metrics", {})
        limits = metrics.get("limits", {})
        expected = {
            "memory.high": str(192 * 1024 * 1024),
            "memory.max": str(256 * 1024 * 1024),
            "memory.swap.max": "0",
            "pids.max": "256",
        }
        if any(limits.get(key) != value for key, value in expected.items()):
            raise AssertionError(f"effective cgroup limits were not retained: {limits}")
        cpu_max = limits.get("cpu.max", "").split()
        if len(cpu_max) != 2 or cpu_max[0] != cpu_max[1]:
            raise AssertionError(f"effective CPU quota was not verified: {cpu_max}")
        if not metrics.get("io_weight_enforced"):
            raise AssertionError("IOWeight=10 was not verified in cgroup metrics")
        systemd_properties = metrics.get("systemd_properties", {})
        if systemd_properties.get("RestrictAddressFamilies") != "AF_UNIX":
            raise AssertionError("worker network address families were not restricted")


def main() -> int:
    install_test_manager_units()
    start_protected_fixtures()
    fixture = json.loads((preflight.VERITAS_CI_ROOT / "fixture.json").read_text())
    baseline_hash = digest_tree(Path(fixture["output_root"]))
    try:
        success_path, success = run_scenario(
            "success", expected_classification="worker_succeeded", require_started=True
        )
        verify_receipt(success_path, success, worker_started=True)
        before = success["checkpoint_before"]
        post = preflight.verify_veritas_post_execution_state(
            Path(fixture["output_root"]),
            success["release_verification"],
            before,
            expected_campaign_sha256=fixture["campaign_sha256"],
        )
        if post["schema_version"] != 2:
            raise AssertionError(
                "successful production service path did not migrate the v1 fixture"
            )

        restore_pristine_state()
        failure_path, failure = run_scenario(
            "worker_failure", expected_classification="worker_failed", require_started=True
        )
        verify_receipt(failure_path, failure, worker_started=True)
        if digest_tree(Path(fixture["output_root"])) != baseline_hash:
            raise AssertionError("nonzero worker changed the disposable checkpoint or ledger")

        command("set-property", "--runtime", "midas-reality.service", "MemoryHigh=16M")
        denial_path, denial = run_scenario(
            "admission_denied", expected_classification="admission_denied", require_started=False
        )
        verify_receipt(denial_path, denial, worker_started=False)
        if denial.get("transient_unit", {}).get("last_observed_state") != "not_requested":
            raise AssertionError("outer admission denial created a transient worker")
        command("set-property", "--runtime", "midas-reality.service", "MemoryHigh=1G")

        restore_pristine_state()
        Path(fixture["pressure_file"]).write_text(
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n",
            encoding="ascii",
        )
        watchdog_path, watchdog = run_scenario(
            "watchdog", expected_classification="psi_watchdog_cancelled", require_started=True
        )
        verify_receipt(watchdog_path, watchdog, worker_started=True)
        if not watchdog.get("watchdog_interventions"):
            raise AssertionError("PSI watchdog intervention is missing from the receipt")
        if digest_tree(Path(fixture["output_root"])) != baseline_hash:
            raise AssertionError(
                "watchdog cancellation changed the disposable checkpoint or ledger"
            )

        active = command(
            "list-units",
            "--type=service",
            "--state=running",
            "--no-legend",
            "--no-pager",
            "midas-heavy-veritas-*.service",
        ).stdout.strip()
        if active:
            raise AssertionError(f"orphaned Veritas worker remains after test: {active}")
        report = {
            "release_identity": preflight.VERITAS_RELEASE_ID,
            "module_sha256": preflight.VERITAS_APPROVED_MODULE_SHA256,
            "success": {
                "receipt": str(success_path),
                "classification": success["final_classification"],
                "migration": post,
            },
            "worker_failure": {
                "receipt": str(failure_path),
                "classification": failure["final_classification"],
            },
            "admission_denial": {
                "receipt": str(denial_path),
                "classification": denial["final_classification"],
            },
            "watchdog": {
                "receipt": str(watchdog_path),
                "classification": watchdog["final_classification"],
            },
        }
        print(json.dumps(report, sort_keys=True))
        return 0
    finally:
        command("stop", UNIT, check=False)
        command("stop", "midas-api.service", "midas-reality.service", check=False)
        command("reset-failed", UNIT, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
