"""Durable, read-only real-source research campaign 48H-002."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPOSITORY = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY / "deploy/autonomy/midas-autonomous-research-48h-002.json"
CAMPAIGN_ID = "48H-002"
TIMER_UNIT = "midas-autonomy-48h-002.timer"
AUDIT_IMPORTS = (
    "source_opportunity_audit.py",
    "opportunity_audit_v2.py",
    "candidate_replay.py",
    "economic_feasibility_v3.py",
)
PREVIOUS_ARTIFACTS = (
    "data/autonomy/48H-001/manifest.json",
    "data/autonomy/48H-001/AUTONOMY_48H_001_FINAL_REPORT.md",
    "data/autonomy/48H-001/48H_001_COMPREHENSIVE_ASSESSMENT.md",
    "data/autonomy/48H-001/48H_001_ASSESSMENT_SUMMARY.json",
)


def iso(ns: int | None = None) -> str:
    return dt.datetime.fromtimestamp((ns or time.time_ns()) / 1e9, dt.UTC).isoformat(
        timespec="seconds"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def file_sha(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def append_jsonl_once(path: Path, key: str, row: dict[str, Any]) -> bool:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                if json.loads(line).get(key) == row.get(key):
                    return False
            except (json.JSONDecodeError, AttributeError):
                continue
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        payload = canonical(row) + b"\n"
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


def command(args: list[str], timeout: int = 6) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(args, 1, "", str(error))


def active(unit: str) -> bool:
    result = command(["systemctl", "--user", "is-active", unit])
    return result.returncode == 0 and result.stdout.strip() == "active"


def systemd_show(unit: str) -> dict[str, str]:
    result = command(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "MemoryCurrent",
            "-p",
            "MemoryHigh",
            "-p",
            "MemoryMax",
            "-p",
            "MemoryPeak",
            "-p",
            "Result",
        ]
    )
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def meminfo() -> dict[str, int]:
    result: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        items = rest.split()
        if items and items[0].isdigit():
            result[key] = int(items[0]) * (1024 if len(items) > 1 and items[1] == "kB" else 1)
    return result


def pressure() -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for resource in ("memory", "io", "cpu"):
        parsed: dict[str, float] = {}
        try:
            lines = Path(f"/proc/pressure/{resource}").read_text().splitlines()
        except OSError:
            lines = []
        for line in lines:
            label, _, rest = line.partition(" ")
            values = dict(item.split("=", 1) for item in rest.split() if "=" in item)
            if "avg10" in values:
                parsed[f"{label}_avg10"] = float(values["avg10"])
        result[resource] = parsed
    return result


def vmstat() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/vmstat").read_text().splitlines():
        if line.startswith(("pswpin ", "pswpout ")):
            key, value = line.split()
            values[key] = int(value)
    return values


def api_health(api_base: str) -> dict[str, Any]:
    try:
        request = urllib.request.Request(api_base.rstrip("/") + "/api/health", method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            value = json.loads(response.read(128 * 1024))
        return value if isinstance(value, dict) else {"error": "invalid health response"}
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
        return {"error": str(error)[:300]}


def snapshot_and_summary(veritas_root: Path, *, verify_snapshot: bool = True) -> dict[str, Any]:
    summary_path = veritas_root / "latest-summary.json"
    research_path = veritas_root / "research-summary.json"
    latest = read_json(summary_path)
    cumulative = read_json(research_path)
    if latest is None or cumulative is None:
        raise ValueError("Veritas immutable snapshot or research summary is unavailable")
    scan_id = str(latest.get("scan_id") or "")
    relative = Path(str(latest.get("snapshot_file") or ""))
    if not scan_id or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Veritas latest snapshot identity or path is invalid")
    snapshot_path = veritas_root / relative
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError("Veritas snapshot is missing or unsafe")
    snapshot_hash = file_sha(snapshot_path)
    snapshot_bytes = snapshot_path.stat().st_size
    if snapshot_bytes > 4 * 1024**2:
        raise ValueError("Veritas compressed snapshot exceeds 4 MiB campaign bound")
    if verify_snapshot:
        from midas.veritas import candidate_replay

        replayed = candidate_replay._read_snapshot(snapshot_path, scan_id)
        if (
            replayed.get("snapshot_evidence_sha256") != latest.get("snapshot_evidence_sha256")
            or replayed.get("captured_ns") != latest.get("captured_ns")
            or replayed.get("source_code_sha256") != latest.get("source_code_sha256")
        ):
            raise ValueError("Veritas summary and immutable snapshot identity differ")
    return {
        "latest": latest,
        "research": cumulative,
        "summary_sha256": file_sha(summary_path),
        "research_summary_sha256": file_sha(research_path),
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256_compressed": snapshot_hash,
        "snapshot_bytes_compressed": snapshot_bytes,
    }


def active_arena_jobs(workspace: Path, veritas_root: Path) -> list[dict[str, str]]:
    roots = (workspace / "data/arena/jobs", veritas_root.parent / "arena/jobs")
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("*/job.json"):
            record = read_json(path) or {}
            if record.get("state") not in {"QUEUED", "RUNNING"}:
                continue
            job_id = str(record.get("job_id") or path.parent.name)
            if job_id not in seen:
                found.append({"job_id": job_id, "state": str(record.get("state")), "path": str(path)})
                seen.add(job_id)
    return found


def required_services(config: dict[str, Any]) -> dict[str, bool]:
    return {unit: active(unit) for unit in config["protected_services_required_active"]}


def vm_delta(previous: dict[str, Any] | None, current: dict[str, int]) -> dict[str, int | None]:
    page_size = os.sysconf("SC_PAGE_SIZE")
    if not previous:
        return {"swap_in_bytes": None, "swap_out_bytes": None, "swap_total_bytes": None}
    delta_in = max(0, current.get("pswpin", 0) - int(previous.get("pswpin", 0))) * page_size
    delta_out = max(0, current.get("pswpout", 0) - int(previous.get("pswpout", 0))) * page_size
    return {"swap_in_bytes": delta_in, "swap_out_bytes": delta_out, "swap_total_bytes": delta_in + delta_out}


def host_snapshot(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    api_base: str,
    config: dict[str, Any],
    previous_vmstat: dict[str, Any] | None,
) -> dict[str, Any]:
    available = meminfo().get("MemAvailable", 0)
    psi = pressure()
    load1 = float(Path("/proc/loadavg").read_text().split()[0])
    disk = shutil.disk_usage(workspace)
    recorder = systemd_show("midas-reality.service")
    current_vm = vmstat()
    swap = vm_delta(previous_vmstat, current_vm)
    services = required_services(config)
    health = api_health(api_base)
    source = snapshot_and_summary(veritas_root, verify_snapshot=True)
    latest = source["latest"]
    reality_conf = read_json(reality_root / "deploy/reality.json") or {}
    reality_runtime_root = Path(str(reality_conf.get("recording_root") or reality_conf.get("root") or "data/recordings/reality"))
    if not reality_runtime_root.is_absolute():
        reality_runtime_root = reality_root / reality_runtime_root
    recorder_status = read_json(reality_runtime_root / "status.json") or {}
    active_jobs = active_arena_jobs(workspace, veritas_root)
    linger_result = command(["loginctl", "show-user", os.environ.get("USER", "charlie"), "-p", "Linger", "--value"])
    linger = linger_result.returncode == 0 and linger_result.stdout.strip() == "yes"
    try:
        scan_age = max(0.0, (time.time_ns() - int(latest["captured_ns"])) / 1e9)
    except (KeyError, TypeError, ValueError):
        scan_age = 1e9
    recorder_status_age = max(0.0, (time.time_ns() - int(recorder_status.get("updated_ns", 0))) / 1e9) if recorder_status.get("updated_ns") else 1e9
    last_observation_age = max(0.0, (time.time_ns() - int(recorder_status.get("last_observation_ns", 0))) / 1e9) if recorder_status.get("last_observation_ns") else 1e9
    current_mem = int(recorder.get("MemoryCurrent", "0") or 0)
    high_mem = int(recorder.get("MemoryHigh", "0") or 0)
    return {
        "checked_at": iso(),
        "host": {
            "mem_available_bytes": available,
            "load_average_1m": load1,
            "memory_psi": psi["memory"],
            "io_psi": psi["io"],
            "cpu_psi": psi["cpu"],
            "disk_free_bytes": disk.free,
            "swap": swap,
            "vmstat": current_vm,
            "user_manager_linger": linger,
        },
        "services": services,
        "api": {
            "reachable": "error" not in health,
            "status": health.get("status"),
            "startup_status": health.get("startup_status"),
            "live_execution": health.get("live_execution"),
            "paper_recovery": health.get("paper_recovery", {}).get("status")
            if isinstance(health.get("paper_recovery"), dict)
            else None,
        },
        "recorder": {
            "unit_state": recorder.get("ActiveState"),
            "memory_current_bytes": current_mem,
            "memory_high_bytes": high_mem,
            "memory_max_bytes": int(recorder.get("MemoryMax", "0") or 0),
            "memory_fraction_of_high": current_mem / high_mem if high_mem else None,
            "status_state": recorder_status.get("state"),
            "collection_health": recorder_status.get("collection_health"),
            "status_updated_age_seconds": recorder_status_age,
            "last_observation_age_seconds": last_observation_age,
            "fresh_books": recorder_status.get("fresh_books"),
            "expected_books": recorder_status.get("expected_books"),
            "sequence_verified": recorder_status.get("sequence_verified"),
            "status_last_ordinal": recorder_status.get("last_event_ordinal"),
            "status_process_id": recorder_status.get("pid"),
        },
        "arena_active_jobs": active_jobs,
        "source": {
            "scan_id": latest.get("scan_id"),
            "captured_at_utc": latest.get("captured_at_utc"),
            "age_seconds": scan_age,
            "snapshot_file": latest.get("snapshot_file"),
            "snapshot_evidence_sha256": latest.get("snapshot_evidence_sha256"),
            "snapshot_compressed_sha256": source["snapshot_sha256_compressed"],
            "snapshot_compressed_bytes": source["snapshot_bytes_compressed"],
            "summary_sha256": source["summary_sha256"],
            "research_summary_sha256": source["research_summary_sha256"],
            "processed_snapshot_count": source["research"].get("processed_snapshot_count"),
            "pending_snapshot_count": source["research"].get("pending_snapshot_count"),
        },
    }


def check_readiness(
    snapshot: dict[str, Any],
    config: dict[str, Any],
    *,
    allow_swap_unknown: bool,
    runtime: bool = False,
) -> dict[str, Any]:
    limits = config["resource_limits"]
    host = snapshot["host"]
    checks: list[dict[str, Any]] = []
    advisory = set(limits.get("runtime_advisory_checks", [])) if runtime else set()

    def add(name: str, ok: bool, detail: Any, *, blocking: bool = True) -> None:
        is_blocking = blocking and name not in advisory
        state = "PASS" if ok else ("BLOCK" if is_blocking else "WARN")
        checks.append({"name": name, "state": state, "blocking": not ok and is_blocking, "detail": detail})

    services_ok = all(snapshot["services"].values())
    add("protected_services_active", services_ok, snapshot["services"])
    add("user_systemd_linger", bool(host["user_manager_linger"]), host["user_manager_linger"])
    api = snapshot["api"]
    add("api_ready_and_no_live_execution", api.get("reachable") and api.get("status") == "READY" and api.get("startup_status") == "READY" and api.get("live_execution") is False, api)
    recorder = snapshot["recorder"]
    add("reality_recorder_active", recorder.get("unit_state") == "active", recorder)
    fraction = recorder.get("memory_fraction_of_high")
    add("reality_recorder_headroom", fraction is not None and fraction <= limits["maximum_recorder_memory_fraction"], {"memory_fraction_of_high": fraction, "maximum_fraction": limits["maximum_recorder_memory_fraction"]})
    recorder_age_ok = recorder.get("status_state") in {"RECORDING_UNSEQUENCED", "RECORDING_SEQUENCED"} and recorder.get("collection_health") == "active_receiving" and recorder.get("status_updated_age_seconds", 1e9) <= limits["maximum_recorder_status_age_seconds"] and recorder.get("last_observation_age_seconds", 1e9) <= limits["maximum_last_observation_age_seconds"] and recorder.get("fresh_books") == recorder.get("expected_books") and (recorder.get("expected_books") or 0) > 0
    add("reality_source_continuity", recorder_age_ok, {key: recorder.get(key) for key in ("status_state", "collection_health", "status_updated_age_seconds", "last_observation_age_seconds", "fresh_books", "expected_books", "sequence_verified")})
    add("host_memory_headroom", host["mem_available_bytes"] >= limits["minimum_available_memory_mb"] * 1024**2, {"available_bytes": host["mem_available_bytes"], "minimum_bytes": limits["minimum_available_memory_mb"] * 1024**2})
    add("disk_reserve", host["disk_free_bytes"] >= limits["minimum_disk_free_bytes"], {"free_bytes": host["disk_free_bytes"], "minimum_bytes": limits["minimum_disk_free_bytes"]})
    psi = host["memory_psi"]
    io = host["io_psi"]
    add("host_pressure", host["load_average_1m"] <= limits["maximum_load_average_1m"] and psi.get("some_avg10", 0) <= limits["maximum_memory_psi_some_avg10_percent"] and psi.get("full_avg10", 0) <= limits["maximum_memory_psi_full_avg10_percent"] and io.get("some_avg10", 0) <= limits["maximum_io_psi_some_avg10_percent"], {"load_average_1m": host["load_average_1m"], "memory_psi": psi, "io_psi": io})
    swap_total = host["swap"].get("swap_total_bytes")
    swap_ok = swap_total is None and allow_swap_unknown or swap_total is not None and swap_total <= limits["maximum_swap_activity_bytes_per_interval"]
    add("swap_activity", bool(swap_ok), host["swap"])
    source = snapshot["source"]
    add("veritas_source_fresh_and_current", source.get("age_seconds", 1e9) <= config["research"]["maximum_source_age_seconds"] and source.get("pending_snapshot_count") == 0, source)
    add("no_active_arena_jobs", not snapshot["arena_active_jobs"], snapshot["arena_active_jobs"], blocking=False)
    blockers = [check["name"] for check in checks if check["blocking"]]
    return {"state": "READY" if not blockers else "BLOCKED", "checked_at": snapshot["checked_at"], "checks": checks, "blocking_reasons": blockers}


def campaign_dir(workspace: Path) -> Path:
    return workspace / "data/autonomy" / CAMPAIGN_ID


def protected_hashes(workspace: Path, reality_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    targets = [
        ("midas-reality", reality_root / item)
        for item in config["protected_reality_campaign_paths"]
    ]
    targets.extend(("48H-001", workspace / item) for item in PREVIOUS_ARTIFACTS)
    return [
        {"group": group, "path": str(path), "exists": path.is_file(), "sha256": file_sha(path)}
        for group, path in targets
    ]


def audit_code_sha() -> str:
    root = REPOSITORY / "packages/midas/veritas"
    digest = hashlib.sha256()
    for name in AUDIT_IMPORTS:
        path = root / name
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def label_inventory(latest: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    pages = snapshot.get("source_requests", {}).get("gamma_pages", [])
    query_pairs = {
        (
            page.get("parameters", {}).get("active"),
            page.get("parameters", {}).get("closed"),
        )
        for page in pages
        if isinstance(page, dict) and isinstance(page.get("parameters"), dict)
    }
    query_flags = [
        {"active": active_flag, "closed": closed_flag}
        for active_flag, closed_flag in sorted(query_pairs, key=lambda pair: (str(pair[0]), str(pair[1])))
    ]
    observations = latest.get("market_observations", [])
    fields = sorted(set().union(*(set(row) for row in observations if isinstance(row, dict)))) if observations else []
    label_fields = [
        key for key in fields
        if any(word in key.casefold() for word in ("settle", "resolution", "outcome_price", "fill", "execution", "realized"))
    ]
    contract_mapping_fields = [key for key in fields if key.casefold() in {"outcomes", "yes_token_id", "no_token_id"}]
    source_requests = snapshot.get("source_requests")
    public_attempts = source_requests.get("public_http_attempts") if isinstance(source_requests, dict) else None
    public_attempt_count = (
        public_attempts if isinstance(public_attempts, int)
        else len(public_attempts) if isinstance(public_attempts, (list, dict))
        else 0
    )
    return {
        "study_id": "48H-002-label-availability-inventory-v1",
        "source_scan_id": latest.get("scan_id"),
        "source_snapshot_evidence_sha256": latest.get("snapshot_evidence_sha256"),
        "observation_kind": latest.get("coverage_kind"),
        "gamma_query_market_state_filters": query_flags,
        "selected_market_observation_fields": fields,
        "selected_market_observation_label_like_fields": label_fields,
        "contract_outcome_mapping_fields": contract_mapping_fields,
        "positive_candidates_in_launch_scan": len(latest.get("positive_candidates", [])),
        "orders_submitted": latest.get("orders_submitted"),
        "authenticated_requests": latest.get("authenticated_requests"),
        "real_fill_labels_available_in_this_observation_source": False,
        "settled_outcome_labels_available_in_this_observation_source": False,
        "interpretation": "This saved public snapshot sample contains active, open-market book observations and hypothetical economics. It contains no realized fills or settled outcome labels. This is a limitation of these captured inputs, not a claim that no external settlement data source exists.",
        "source_limitations": latest.get("limitations", []),
        "snapshot_source_requests_count": public_attempt_count,
    }


def summary_metrics(bundle: dict[str, Any]) -> dict[str, Any]:
    latest = bundle["latest"]
    research = bundle["research"]
    cumulative = research.get("cumulative") if isinstance(research.get("cumulative"), dict) else {}
    observation = latest.get("observation") if isinstance(latest.get("observation"), dict) else {}
    pos = latest.get("positive_candidates", [])
    return {
        "scan_id": latest.get("scan_id"),
        "captured_at_utc": latest.get("captured_at_utc"),
        "snapshot_evidence_sha256": latest.get("snapshot_evidence_sha256"),
        "selected_market_observations": cumulative.get("selected_market_observations"),
        "processed_snapshots": research.get("processed_snapshot_count"),
        "pending_snapshots": research.get("pending_snapshot_count"),
        "quality_valid_pairs": cumulative.get("quality_valid_pairs"),
        "legacy_freshness_valid_pairs": cumulative.get("legacy_freshness_valid_pairs"),
        "invalid_pairs": cumulative.get("invalid_pairs"),
        "candidate_event_count": cumulative.get("candidate_event_count"),
        "positive_top_gross_pairs": cumulative.get("positive_top_gross_pairs"),
        "positive_full_depth_gross_by_quantity": cumulative.get("positive_full_depth_gross_by_quantity"),
        "positive_fragmentation_safe_by_quantity": cumulative.get("positive_fragmentation_safe_by_quantity"),
        "maximum_top_edge_per_share": cumulative.get("maximum_top_edge_per_share"),
        "current_scan_observations": len(latest.get("market_observations", [])),
        "current_scan_quality_valid_pairs": observation.get("valid_quality_pairs"),
        "current_scan_positive_top_gross_pairs": observation.get("positive_top_gross_pairs"),
        "current_scan_positive_candidates": len(pos),
        "orders_submitted": latest.get("orders_submitted"),
    }


def protected_ok(expected: list[dict[str, Any]], workspace: Path, reality_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    current = protected_hashes(workspace, reality_root, config)
    expected_by_path = {item["path"]: item for item in expected}
    return [
        {**item, "unchanged": item["path"] in expected_by_path and item.get("sha256") == expected_by_path[item["path"]].get("sha256") and item.get("exists") == expected_by_path[item["path"]].get("exists")}
        for item in current
    ]


def readiness_report(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    api_base: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    sample = host_snapshot(workspace, reality_root, veritas_root, api_base, config, None)
    ready = check_readiness(sample, config, allow_swap_unknown=True)
    snap = snapshot_and_summary(veritas_root, verify_snapshot=True)
    research = snap["research"]
    ids = sorted(
        path.name.removesuffix(".json.gz")
        for path in (veritas_root / "snapshots").glob("scan-*.json.gz")
        if path.is_file()
        and not path.is_symlink()
        and scan_id_captured_ns(path.name.removesuffix(".json.gz")) is not None
    )
    bytes_for_window = sum((veritas_root / "snapshots" / f"{scan_id}.json.gz").stat().st_size for scan_id in ids[-int(config["research"]["baseline_scan_count"]):])
    size_ok = len(ids) >= int(config["research"]["baseline_scan_count"]) and bytes_for_window <= int(config["research"]["maximum_audit_input_bytes"])
    scan_age_ok = sample["source"]["age_seconds"] <= config["research"]["maximum_source_age_seconds"]
    summary_current = research.get("pending_snapshot_count") == 0 and research.get("processed_snapshot_count", 0) > 0
    ready["checks"].extend([
        {"name": "frozen_baseline_scan_window", "state": "PASS" if size_ok else "BLOCK", "blocking": not size_ok, "detail": {"available_snapshots": len(ids), "required_snapshots": config["research"]["baseline_scan_count"], "selected_window_compressed_bytes": bytes_for_window, "maximum_bytes": config["research"]["maximum_audit_input_bytes"]}},
        {"name": "current_veritas_summary", "state": "PASS" if summary_current else "BLOCK", "blocking": not summary_current, "detail": {"processed_snapshot_count": research.get("processed_snapshot_count"), "pending_snapshot_count": research.get("pending_snapshot_count"), "updated_at_utc": research.get("updated_at_utc")}},
        {"name": "latest_snapshot_age", "state": "PASS" if scan_age_ok else "BLOCK", "blocking": not scan_age_ok, "detail": {"age_seconds": sample["source"]["age_seconds"], "maximum_seconds": config["research"]["maximum_source_age_seconds"]}},
    ])
    ready["campaign_id"] = CAMPAIGN_ID
    ready["previous_campaign_artifacts"] = file_fingerprints(workspace)
    ready["protected_reality_campaigns"] = protected_hashes(workspace, reality_root, config)
    protected_files = ready.get("protected_reality_campaigns", [])
    previous_files = ready.get("previous_campaign_artifacts", [])
    protected_files_present = all(item.get("exists") and item.get("sha256") for item in protected_files + previous_files)
    ready["checks"].append({"name": "protected_campaign_artifacts_present", "state": "PASS" if protected_files_present else "BLOCK", "blocking": not protected_files_present, "detail": {"reality_campaigns": protected_files, "previous_campaign_artifacts": previous_files}})
    ready["blocking_reasons"] = [item["name"] for item in ready["checks"] if item["blocking"]]
    ready["state"] = "READY" if not ready["blocking_reasons"] else "BLOCKED"
    ready["source_summary_metrics"] = summary_metrics(snap)
    ready["source_analysis_status"] = {
        "path": str(veritas_root / "source-research-summary.json"),
        "sha256": file_sha(veritas_root / "source-research-summary.json"),
        "status": (read_json(veritas_root / "source-research-summary.json") or {}).get("status"),
        "readiness": (read_json(veritas_root / "source-research-summary.json") or {}).get("readiness"),
        "pending_segment_count": (read_json(veritas_root / "source-research-summary.json") or {}).get("pending_segment_count"),
        "pending_source_bytes": (read_json(veritas_root / "source-research-summary.json") or {}).get("pending_source_bytes"),
        "interpretation": "Recorded separately as a source-analysis backlog; 48H-002 does not run or alter that protected worker.",
    }
    ready["swap_policy"] = "High swap occupancy is not by itself a blocker; the campaign defers the independent audit on measured swap activity, memory PSI, or host pressure."
    return ready, sample


def file_fingerprints(workspace: Path) -> list[dict[str, Any]]:
    return [
        {"path": str(workspace / relative), "exists": (workspace / relative).is_file(), "sha256": file_sha(workspace / relative)}
        for relative in PREVIOUS_ARTIFACTS
    ]


def load_config(workspace: Path) -> dict[str, Any]:
    config = read_json(workspace / "deploy/autonomy/midas-autonomous-research-48h-002.json")
    if not config or config.get("campaign_id") != CAMPAIGN_ID:
        raise RuntimeError("48H-002 campaign configuration is missing or invalid")
    return config


def prepare_plan(veritas_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    bundle = snapshot_and_summary(veritas_root)
    latest = bundle["latest"]
    scan_ids = sorted(
        path.name.removesuffix(".json.gz")
        for path in (veritas_root / "snapshots").glob("scan-*.json.gz")
        if path.is_file()
        and not path.is_symlink()
        and scan_id_captured_ns(path.name.removesuffix(".json.gz")) is not None
    )
    count = int(config["research"]["baseline_scan_count"])
    window = scan_ids[-count:]
    if len(window) != count:
        raise RuntimeError(f"Expected {count} safe immutable baseline scans, found {len(window)}")
    latest_id = window[-1] if window else str(latest["scan_id"])
    if window:
        latest_snapshot_path = veritas_root / "snapshots" / f"{latest_id}.json.gz"
        if latest_snapshot_path.is_symlink() or not latest_snapshot_path.is_file():
            raise RuntimeError("Newest immutable source snapshot is missing or unsafe")
        latest_snapshot = json.loads(gzip.decompress(latest_snapshot_path.read_bytes()))
        if latest_snapshot.get("scan_id") != latest_id:
            raise RuntimeError("Newest immutable source snapshot does not match its filename")
    else:
        latest_snapshot = latest
    batch_size = int(config["research"]["audit_batch_size"])
    slices = []
    for offset in range(0, len(window), batch_size):
        ids = window[offset : offset + batch_size]
        if not ids:
            continue
        slices.append({"slice_id": f"source-audit-{len(slices) + 1:02d}", "scan_ids": ids, "status": "QUEUED", "result_path": f"source-audit/{len(slices) + 1:02d}.json"})
    cumulative = bundle["research"].get("cumulative", {})
    return {
        "plan_id": "real-source-96scan-freshness-and-label-feasibility-v1",
        "hypotheses": [
            "Independent source replay reproduces the recent Veritas quality, freshness, fee, and candidate gates.",
            "Market-selection snapshots provide book-quality observations but not settled outcome or real-fill labels.",
            "A prospective continuation can detect whether any new saved scan produces a fee-aware candidate that also passes strict timestamp freshness.",
        ],
        "baseline": summary_metrics(bundle),
        "baseline_source_root": str(veritas_root),
        "baseline_source_summary_sha256": bundle["research_summary_sha256"],
        "baseline_latest_scan_id": latest_id,
        "baseline_latest_snapshot_sha256": latest_snapshot.get("snapshot_evidence_sha256"),
        "indexed_latest_scan_id_at_start": str(latest.get("scan_id") or ""),
        "baseline_scan_ids": window,
        "baseline_scan_id_sha256": sha256_bytes(canonical(window)),
        "audit_source_code_sha256": audit_code_sha(),
        "audit_slices": slices,
        "extension_slice": None,
        "prospective_scan_queue": [],
        "label_inventory": label_inventory(latest_snapshot, latest_snapshot),
        "priority_mode": "independent_source_quality_audit",
        "priority_reason": "Start with a frozen, recent 96-scan replay; use prospective source evidence to redirect effort if a positive, mismatch, or freshness bottleneck appears.",
        "priority_history": [],
        "scheduler_cursor": "prospective",
        "adaptation_flags": {"extension_added": False, "no_positive_12h_shift": False},
        "source_summary_cumulative_baseline": {
            key: cumulative.get(key)
            for key in (
                "selected_market_observations",
                "quality_valid_pairs",
                "legacy_freshness_valid_pairs",
                "candidate_event_count",
                "positive_top_gross_pairs",
                "positive_full_depth_gross_by_quantity",
                "positive_fragmentation_safe_by_quantity",
                "reported_update_age_above_5s_by_leg",
                "reported_update_timestamp_skew_above_250ms_pairs",
            )
        },
    }


def initialize(workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any]) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    if (directory / "manifest.json").exists():
        raise RuntimeError("48H-002 already has a durable manifest; refusing to replace it")
    ready, sample = readiness_report(workspace, reality_root, veritas_root, api_base, config)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_json(directory / "preflight.json", ready)
    if ready["state"] != "READY":
        raise RuntimeError("Campaign preflight blocked: " + ", ".join(ready["blocking_reasons"]))
    started = time.time_ns()
    plan = prepare_plan(veritas_root, config)
    manifest = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "title": config["title"],
        "status": "RUNNING",
        "health": "READY",
        "started_at": iso(started),
        "started_at_ns": started,
        "planned_end_at": iso(started + int(config["duration_seconds"]) * 1_000_000_000),
        "deadline_ns": started + int(config["duration_seconds"]) * 1_000_000_000,
        "grace_deadline_ns": started + (int(config["duration_seconds"]) + int(config["completion_grace_seconds"])) * 1_000_000_000,
        "completed_at": None,
        "last_tick_at": iso(started),
        "last_tick_ns": started,
        "last_resource_sample": sample,
        "consecutive_healthy_checks": 0,
        "resource_samples": [],
        "resource_admitted_ticks": 0,
        "resource_deferred_ticks": 0,
        "source_scan_ids_observed": [],
        "research_plan": plan,
        "protected_artifacts_at_start": protected_hashes(workspace, reality_root, config),
        "previous_campaign_artifacts_at_start": file_fingerprints(workspace),
        "source_monitoring": {"new_scans": 0, "selected_market_observations": 0, "quality_valid_pairs": 0, "positive_top_gross_pairs": 0, "strict_positive_candidates": 0, "first_scan_at": None, "last_scan_at": None, "distinct_market_ids": []},
        "operational_incidents": [],
        "report_path": str(directory / "AUTONOMY_48H_002_FINAL_REPORT.md"),
    }
    (directory / "source-audit").mkdir(mode=0o700, parents=True, exist_ok=True)
    (directory / "prospective-scans").mkdir(mode=0o700, parents=True, exist_ok=True)
    (directory / "prospective-scans/scan-ledger.jsonl").touch(mode=0o600, exist_ok=True)
    atomic_json(directory / "research-plan.json", plan)
    atomic_json(directory / "label-inventory.json", plan["label_inventory"])
    atomic_json(directory / "manifest.json", manifest)
    write_status(directory, manifest)
    return manifest


def write_status(directory: Path, manifest: dict[str, Any]) -> None:
    plan = manifest.get("research_plan", {})
    audit_slices = plan.get("audit_slices", [])
    done = sum(item.get("status") == "COMPLETED" for item in audit_slices)
    remaining = sum(item.get("status") != "COMPLETED" for item in audit_slices)
    quarantined_slices = sum(item.get("status") == "COMPLETED_WITH_QUARANTINES" for item in audit_slices)
    monitoring = manifest.get("source_monitoring", {})
    prospective = plan.get("prospective_scan_queue", [])
    queued_scans = sum(item.get("status") == "QUEUED" for item in prospective)
    unindexed_scans = sum(item.get("published_in_latest_summary_at_discovery") is False for item in prospective)
    new_scan_result = (
        f"{monitoring.get('positive_top_gross_pairs', 0)} observed"
        if monitoring.get("new_scans", 0)
        else "NOT MEASURED (no prospective scan audit completed)"
    )
    text = "\n".join(
        [
            f"# MIDAS 48H-002 — {manifest.get('status')}",
            "",
            f"- Health: **{manifest.get('health', 'UNKNOWN')}**",
            f"- Started: {manifest.get('started_at')}",
            f"- Planned deadline: {manifest.get('planned_end_at')}",
            f"- Priority: {plan.get('priority_mode', 'not set')}",
            f"- Independent recent-source audit slices: {done} complete, {quarantined_slices} completed with quarantines, {remaining} queued, deferred, or blocked",
            f"- New saved Veritas scans independently audited: {monitoring.get('new_scans', 0)}",
            f"- Prospective scans queued: {queued_scans}; not present in the latest index at discovery: {unindexed_scans}",
            f"- Selected market observations: {monitoring.get('selected_market_observations', 0)}",
            f"- Quality-valid pairs: {monitoring.get('quality_valid_pairs', 0)}",
            f"- Positive top gross pairs in new scans: {new_scan_result}",
            f"- Strict freshness positive candidates: {monitoring.get('strict_positive_candidates', 0)}",
            f"- Resource-deferred ticks: {manifest.get('resource_deferred_ticks', 0)}",
            "",
            f"Latest finding: {plan.get('priority_reason', 'Awaiting first source audit.')}",
            "",
            "Public saved market data only. No orders, authenticated requests, real trading, or synthetic model training are admitted.",
            "",
            f"Full status: `{directory / 'manifest.json'}`",
            f"Final report: `{manifest.get('report_path')}`",
            "",
        ]
    )
    path = directory / "STATUS.md"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".STATUS.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def resource_admitted(
    workspace: Path,
    reality_root: Path,
    veritas_root: Path,
    api_base: str,
    config: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    sample = host_snapshot(workspace, reality_root, veritas_root, api_base, config, manifest.get("last_resource_sample", {}).get("host", {}).get("vmstat"))
    gate = check_readiness(sample, config, allow_swap_unknown=False, runtime=True)
    active_scan = active("midas-veritas-observatory.service")
    source_analysis_active = active("midas-veritas-source-analysis.service")
    gap_analysis_active = active("midas-veritas-gap-detail-v2.service")
    if sample["host"]["swap"].get("swap_total_bytes") is None:
        manifest["consecutive_healthy_checks"] = 0
        gate["blocking_reasons"].append("swap_stability_baseline_missing")
        gate["state"] = "BLOCKED"
    if gate["state"] == "READY" and not sample["arena_active_jobs"] and not (active_scan or source_analysis_active or gap_analysis_active):
        manifest["consecutive_healthy_checks"] = int(manifest.get("consecutive_healthy_checks", 0)) + 1
    elif gate["state"] != "READY" or sample["arena_active_jobs"] or active_scan or source_analysis_active or gap_analysis_active:
        manifest["consecutive_healthy_checks"] = 0
    if active_scan:
        gate["blocking_reasons"].append("veritas_observatory_worker_active")
    if source_analysis_active:
        gate["blocking_reasons"].append("veritas_source_analysis_worker_active")
    if gap_analysis_active:
        gate["blocking_reasons"].append("veritas_gap_analysis_worker_active")
    if sample["arena_active_jobs"]:
        gate["blocking_reasons"].append("arena_worker_active")
    stable_checks = int(config["research"]["required_consecutive_healthy_checks"])
    if manifest["consecutive_healthy_checks"] < stable_checks:
        gate["blocking_reasons"].append("host_stability_window")
    gate["blocking_reasons"] = sorted(set(gate["blocking_reasons"]))
    gate["state"] = "READY" if not gate["blocking_reasons"] else "DEFER"
    gate["consecutive_healthy_checks"] = manifest["consecutive_healthy_checks"]
    gate["required_consecutive_healthy_checks"] = stable_checks
    gate["protected_analysis_workers"] = {"veritas_observatory": active_scan, "veritas_source_analysis": source_analysis_active, "veritas_gap_analysis": gap_analysis_active}
    return gate["state"] == "READY", sample, gate


def next_audit_slice(plan: dict[str, Any]) -> dict[str, Any] | None:
    for slice_record in plan.get("audit_slices", []):
        if slice_record.get("status") == "QUEUED" and int(slice_record.get("retry_after_ns", 0) or 0) <= time.time_ns():
            return slice_record
    extension = plan.get("extension_slice")
    if isinstance(extension, dict) and extension.get("status") == "QUEUED" and int(extension.get("retry_after_ns", 0) or 0) <= time.time_ns():
        return extension
    return None


def next_prospective_scan(plan: dict[str, Any]) -> dict[str, Any] | None:
    now = time.time_ns()
    return next((item for item in plan.get("prospective_scan_queue", []) if item.get("status") == "QUEUED" and int(item.get("retry_after_ns", 0) or 0) <= now), None)


def next_research_action(plan: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, str]:
    audit_slice = next_audit_slice(plan)
    prospective_scan = next_prospective_scan(plan)
    if audit_slice is None and prospective_scan is None:
        return None, None, "no eligible research item"
    if audit_slice is None:
        return "prospective_scan", prospective_scan, "no eligible frozen audit slice"
    if prospective_scan is None:
        return "audit_slice", audit_slice, "no eligible prospective scan"
    if plan.get("priority_mode") == "independent_source_quality_audit":
        plan["scheduler_cursor"] = "prospective"
        return "audit_slice", audit_slice, "finish the frozen source baseline before adaptation"
    preferred = plan.get("scheduler_cursor", "prospective")
    if preferred == "prospective":
        plan["scheduler_cursor"] = "audit"
        return "prospective_scan", prospective_scan, "fair turn under the adaptive monitoring priority"
    plan["scheduler_cursor"] = "prospective"
    return "audit_slice", audit_slice, "fair turn for the remaining frozen baseline"


def record_task_failure(task: dict[str, Any], error: Exception, now_ns: int, config: dict[str, Any]) -> str:
    attempt = int(task.get("failure_count", 0)) + 1
    maximum = int(config["research"].get("maximum_task_failures", 5))
    task["failure_count"] = attempt
    task["last_error"] = f"{type(error).__name__}: {error}"[:400]
    task["last_failed_at"] = iso(now_ns)
    if attempt >= maximum:
        task["status"] = "BLOCKED"
        task["blocked_at"] = iso(now_ns)
        return "BLOCKED"
    base = int(config["research"].get("retry_backoff_base_seconds", 300))
    cap = int(config["research"].get("retry_backoff_max_seconds", 3600))
    delay = min(cap, base * (2 ** (attempt - 1)))
    task["retry_after_ns"] = now_ns + delay * 1_000_000_000
    task["retry_delay_seconds"] = delay
    return "RETRY_SCHEDULED"


def adapt_to_prospective_scan(plan: dict[str, Any], result: dict[str, Any], now_ns: int, started_ns: int, config: dict[str, Any]) -> None:
    mismatches = int(result.get("independent_fee_disagreement_count", 0) or 0) + int(result.get("v4_v3_validity_mismatch_count", 0) or 0) + int(result.get("v4_v3_top_edge_mismatch_count", 0) or 0)
    strict_positive = int(result.get("strict_fresh_positive_top_pair_gross_count", 0) or 0)
    gross_positive = int(result.get("positive_top_pair_gross_count", 0) or 0)
    if mismatches:
        set_priority(plan, result, now_ns, started_ns, config)
        return
    if strict_positive:
        mode = "strict_fresh_candidate_qualification"
        reason = f"A newly saved scan independently reproduced {strict_positive} strict-fresh positive gross observation(s); preserve its exact source and require a separate economics/fill study before strategy claims."
    elif gross_positive:
        mode = "freshness_gate_failure"
        reason = f"A newly saved scan had {gross_positive} gross-positive observation(s), but none passed strict reported-age/skew gates; prioritize source freshness."
    else:
        return
    old = plan.get("priority_mode")
    plan["priority_mode"] = mode
    plan["priority_reason"] = reason
    if mode != old:
        plan.setdefault("priority_history", []).append({"at": iso(now_ns), "from": old, "to": mode, "reason": reason})


def combine_audit_results(batches: list[dict[str, Any]], requested_count: int) -> dict[str, Any]:
    scalar_fields = (
        "selected_market_observation_count", "v4_stored_quality_valid_count",
        "independent_v3_valid_count", "strict_freshness_valid_count",
        "reported_age_exceedance_pair_count", "pair_skew_exceedance_count",
        "independent_fee_checked_quantity_count", "independent_fee_disagreement_count",
        "v4_v3_validity_mismatch_count", "v4_v3_top_edge_mismatch_count",
        "positive_top_pair_gross_count", "strict_fresh_positive_top_pair_gross_count",
        "compressed_source_bytes",
    )
    result: dict[str, Any] = {
        field: sum(int(batch.get(field, 0) or 0) for batch in batches)
        for field in scalar_fields
    }
    result["snapshot_count"] = sum(int(batch.get("snapshot_count", 0) or 0) for batch in batches)
    result["requested_snapshot_count"] = requested_count
    result["quarantined_snapshot_count"] = max(0, requested_count - result["snapshot_count"])
    result["coverage_complete"] = result["snapshot_count"] == requested_count
    result["complete"] = result["snapshot_count"] + result["quarantined_snapshot_count"] == requested_count
    map_fields = (
        "positive_full_depth_gross_by_quantity",
        "strict_fresh_positive_full_depth_gross_by_quantity",
        "positive_full_depth_and_both_minimums_by_quantity",
        "strict_fresh_positive_full_depth_and_both_minimums_by_quantity",
        "positive_single_match_fee_sensitivity_by_quantity",
        "strict_fresh_positive_single_match_fee_sensitivity_by_quantity",
        "positive_fragmentation_safe_fee_sensitivity_by_quantity",
        "strict_fresh_positive_fragmentation_safe_fee_sensitivity_by_quantity",
        "positive_both_fee_sensitivities_by_quantity",
        "strict_fresh_positive_both_fee_sensitivities_by_quantity",
    )
    for field in map_fields:
        quantities = set().union(*(set(batch.get(field, {})) for batch in batches)) if batches else set()
        result[field] = {
            quantity: sum(int(batch.get(field, {}).get(quantity, 0) or 0) for batch in batches)
            for quantity in sorted(quantities)
        }
    invalid: dict[str, int] = {}
    for batch in batches:
        for reason, count in batch.get("invalid_reasons", {}).items():
            invalid[reason] = invalid.get(reason, 0) + int(count)
    result["invalid_reasons"] = invalid
    result["source_manifest_sha256_by_scan"] = [batch.get("source_manifest_sha256") for batch in batches]
    result["source_manifest_sha256"] = sha256_bytes(canonical(result["source_manifest_sha256_by_scan"]))
    result["source_code_sha256"] = batches[0].get("source_code_sha256") if batches else None
    result["orders_submitted"] = any(batch.get("orders_submitted") is True for batch in batches)
    result["authenticated_requests"] = any(batch.get("authenticated_requests") is True for batch in batches)
    result["orders_submitted_false_in_all_audited_scans"] = bool(batches) and all(
        batch.get("orders_submitted") is False for batch in batches
    )
    result["authenticated_requests_false_in_all_audited_scans"] = bool(batches) and all(
        batch.get("authenticated_requests") is False for batch in batches
    )
    result["status"] = (
        "STRICT_FRESH_POSITIVE_OBSERVED"
        if result["strict_fresh_positive_top_pair_gross_count"]
        else "POSITIVE_GROSS_WITHOUT_STRICT_FRESHNESS"
        if result["positive_top_pair_gross_count"]
        else "NO_POSITIVE_GROSS_CANDIDATE_OBSERVED"
    )
    denominator = result["independent_v3_valid_count"]
    result["strict_freshness_fraction_of_independently_valid_pairs"] = (
        result["strict_freshness_valid_count"] / denominator if denominator else None
    )
    result["limitations"] = batches[0].get("limitations", []) if batches else []
    return result


def run_audit_slice(veritas_root: Path, directory: Path, plan: dict[str, Any], slice_record: dict[str, Any]) -> dict[str, Any]:
    from midas.veritas.source_opportunity_audit import audit_source_opportunities

    if audit_code_sha() != plan.get("audit_source_code_sha256"):
        raise RuntimeError("Pinned Veritas audit source changed after campaign launch")
    if veritas_root.is_symlink() or not (veritas_root / "snapshots").is_dir():
        raise RuntimeError("Pinned source snapshot directory is unavailable")
    batches: list[dict[str, Any]] = []
    quarantined: list[dict[str, str]] = []
    audited: list[dict[str, str]] = []
    for scan_id in slice_record["scan_ids"]:
        try:
            result = audit_source_opportunities(veritas_root, [scan_id])
            if result.get("complete") is not True:
                quarantined.append({"scan_id": scan_id, "reason": str(result.get("failure_reason") or "audit_incomplete")})
                continue
            batches.append(result)
            audited.append({
                "scan_id": scan_id,
                "status": "AUDITED",
                "result_sha256": str(result.get("result_sha256") or ""),
                "source_manifest_sha256": str(result.get("source_manifest_sha256") or ""),
            })
        except ValueError as error:
            quarantined.append({"scan_id": scan_id, "reason": str(error)[:300]})
    result = combine_audit_results(batches, len(slice_record["scan_ids"]))
    artifact = {
        "campaign_id": CAMPAIGN_ID,
        "campaign_study_id": "48H-002-real-source-quality-and-freshness-audit-v1",
        "slice_id": slice_record["slice_id"],
        "scan_ids": slice_record["scan_ids"],
        "audited_scans": audited,
        "quarantined_scans": quarantined,
        "scan_id_set_sha256": sha256_bytes(canonical(slice_record["scan_ids"])),
        "recorded_at_utc": iso(),
        "veritas_audit_source_code_sha256": plan["audit_source_code_sha256"],
        "result": result,
    }
    artifact["artifact_sha256"] = sha256_bytes(canonical(artifact))
    output = directory / slice_record["result_path"]
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to replace an existing source-audit artifact: {output}")
    atomic_json(output, artifact)
    slice_record.update({
        "status": "COMPLETED_WITH_QUARANTINES" if quarantined else "COMPLETED",
        "completed_at": iso(),
        "artifact_sha256": artifact["artifact_sha256"],
        "result_path": str(output),
        "audited_scan_count": len(audited),
        "quarantined_scan_count": len(quarantined),
    })
    return artifact


def scan_id_captured_ns(scan_id: str) -> int | None:
    if not scan_id.startswith("scan-"):
        return None
    try:
        captured = dt.datetime.strptime(scan_id[5:21], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC)
    except ValueError:
        return None
    return int(captured.timestamp() * 1_000_000_000)


def queue_new_source_scans(
    plan: dict[str, Any],
    veritas_root: Path,
    directory: Path,
    indexed_latest_scan_id: str,
    *,
    started_at_ns: int,
    deadline_ns: int,
    now_ns: int,
) -> int:
    baseline = str(plan.get("baseline_latest_scan_id") or "")
    queued = {str(item.get("scan_id")) for item in plan.get("prospective_scan_queue", [])}
    added = 0
    for path in sorted((veritas_root / "snapshots").glob("scan-*.json.gz")):
        if path.is_symlink() or not path.is_file():
            continue
        scan_id = path.name.removesuffix(".json.gz")
        captured_ns = scan_id_captured_ns(scan_id)
        if (
            scan_id <= baseline
            or captured_ns is None
            or captured_ns < started_at_ns
            or captured_ns > deadline_ns
            or captured_ns > now_ns
        ):
            continue
        if scan_id not in queued:
            item = {
                "scan_id": scan_id,
                "status": "QUEUED",
                "queued_at": iso(now_ns),
                "captured_ns_from_scan_id": captured_ns,
                "published_in_latest_summary_at_discovery": scan_id <= indexed_latest_scan_id,
                "result_path": f"prospective-scans/{scan_id}.json",
            }
            plan["prospective_scan_queue"].append(item)
            queued.add(scan_id)
            added += 1
        item = next(row for row in plan["prospective_scan_queue"] if row.get("scan_id") == scan_id)
        append_jsonl_once(
            directory / "prospective-scans/scan-ledger.jsonl",
            "event_id",
            {
                "event_id": f"{scan_id}:QUEUED",
                "scan_id": scan_id,
                "status": "QUEUED",
                "queued_at": item.get("queued_at"),
                "captured_ns_from_scan_id": captured_ns,
                "published_in_latest_summary_at_discovery": item.get("published_in_latest_summary_at_discovery"),
                "snapshot_path": f"snapshots/{scan_id}.json.gz",
            },
        )
    plan["prospective_scan_queue"].sort(key=lambda item: str(item.get("scan_id")))
    return added


def prospective_ledger_row(artifact: dict[str, Any]) -> dict[str, Any]:
    result = artifact.get("result", {})
    quantity = result.get("positive_full_depth_gross_by_quantity", {})
    return {
        "scan_id": artifact.get("scan_id"),
        "captured_ns": artifact.get("captured_ns"),
        "captured_at_utc": artifact.get("captured_at_utc"),
        "snapshot_file": artifact.get("snapshot_file"),
        "snapshot_evidence_sha256": artifact.get("snapshot_evidence_sha256"),
        "snapshot_compressed_sha256": artifact.get("snapshot_compressed_sha256"),
        "selected_market_ids": artifact.get("selected_market_ids", []),
        "selected_market_observation_count": result.get("selected_market_observation_count", 0),
        "quality_valid_pairs": result.get("independent_v3_valid_count", 0),
        "strict_freshness_valid_pairs": result.get("strict_freshness_valid_count", 0),
        "positive_top_gross_pairs": result.get("positive_top_pair_gross_count", 0),
        "strict_positive_candidates": result.get("strict_fresh_positive_top_pair_gross_count", 0),
        "positive_full_depth_gross_by_quantity": quantity,
        "independent_fee_disagreements": result.get("independent_fee_disagreement_count", 0),
        "validity_mismatches": result.get("v4_v3_validity_mismatch_count", 0),
        "edge_mismatches": result.get("v4_v3_top_edge_mismatch_count", 0),
        "result_sha256": result.get("result_sha256"),
        "orders_submitted": result.get("orders_submitted"),
        "authenticated_requests": result.get("authenticated_requests"),
    }


def run_prospective_scan(veritas_root: Path, directory: Path, plan: dict[str, Any], item: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    from midas.veritas import candidate_replay
    from midas.veritas.source_opportunity_audit import audit_source_opportunities

    if audit_code_sha() != plan.get("audit_source_code_sha256"):
        raise RuntimeError("Pinned Veritas audit source changed after campaign launch")
    scan_id = str(item["scan_id"])
    snapshot_path = veritas_root / "snapshots" / f"{scan_id}.json.gz"
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError("Prospective immutable snapshot is missing or unsafe")
    snapshot = candidate_replay._read_snapshot(snapshot_path, scan_id)
    captured_ns = int(snapshot.get("captured_ns") or 0)
    if captured_ns < int(manifest["started_at_ns"]) or captured_ns > int(manifest["deadline_ns"]):
        item["status"] = "OUTSIDE_CAMPAIGN_WINDOW"
        item["captured_ns"] = captured_ns
        return {"scan_id": scan_id, "status": item["status"]}
    result = audit_source_opportunities(veritas_root, [scan_id])
    if result.get("complete") is not True:
        raise RuntimeError("Prospective source audit did not complete: " + str(result.get("failure_reason")))
    selected = snapshot.get("market_observations", [])
    artifact = {
        "campaign_id": CAMPAIGN_ID,
        "study_id": "48H-002-prospective-real-source-scan-audit-v1",
        "scan_id": scan_id,
        "captured_ns": captured_ns,
        "captured_at_utc": snapshot.get("captured_at_utc"),
        "snapshot_file": f"snapshots/{scan_id}.json.gz",
        "snapshot_evidence_sha256": snapshot.get("snapshot_evidence_sha256"),
        "snapshot_compressed_sha256": file_sha(snapshot_path),
        "selected_market_ids": sorted(str(row.get("market_id")) for row in selected if isinstance(row, dict)),
        "audit_source_code_sha256": plan["audit_source_code_sha256"],
        "recorded_at_utc": iso(),
        "result": result,
    }
    artifact["artifact_sha256"] = sha256_bytes(canonical(artifact))
    output = directory / item["result_path"]
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to replace a prospective audit artifact: {output}")
    atomic_json(output, artifact)
    row = prospective_ledger_row(artifact)
    row["observed_at_utc"] = artifact["recorded_at_utc"]
    row["status"] = "AUDITED"
    row["event_id"] = f"{scan_id}:AUDITED"
    append_jsonl_once(directory / "prospective-scans/scan-ledger.jsonl", "event_id", row)
    item.update({"status": "COMPLETED", "captured_ns": captured_ns, "completed_at": artifact["recorded_at_utc"], "artifact_sha256": artifact["artifact_sha256"], "result_path": str(output)})
    return artifact


def verify_completed_artifact(path: Path, *, expected_study: str, expected_key: str, expected_value: Any) -> dict[str, Any] | None:
    artifact = read_json(path)
    if artifact is None or artifact.get("campaign_id") != CAMPAIGN_ID or artifact.get(expected_key) != expected_value:
        return None
    if artifact.get("campaign_study_id", artifact.get("study_id")) != expected_study:
        return None
    result = artifact.get("result")
    if not isinstance(result, dict) or result.get("complete") is not True:
        return None
    claimed = artifact.get("artifact_sha256")
    payload = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    if claimed != sha256_bytes(canonical(payload)):
        return None
    return artifact


def recover_completed_work(directory: Path, plan: dict[str, Any]) -> None:
    for item in plan.get("audit_slices", []):
        if item.get("status") != "QUEUED":
            continue
        artifact = verify_completed_artifact(
            Path(item["result_path"]) if Path(item["result_path"]).is_absolute() else directory / item["result_path"],
            expected_study="48H-002-real-source-quality-and-freshness-audit-v1",
            expected_key="slice_id",
            expected_value=item.get("slice_id"),
        )
        if artifact and artifact.get("scan_ids") == item.get("scan_ids"):
            quarantined = artifact.get("quarantined_scans", [])
            item.update({"status": "COMPLETED_WITH_QUARANTINES" if quarantined else "COMPLETED", "completed_at": artifact.get("recorded_at_utc"), "artifact_sha256": artifact.get("artifact_sha256"), "result_path": str(Path(item["result_path"]) if Path(item["result_path"]).is_absolute() else directory / item["result_path"]), "audited_scan_count": len(artifact.get("audited_scans", [])), "quarantined_scan_count": len(quarantined)})
    extension = plan.get("extension_slice")
    if isinstance(extension, dict) and extension.get("status") == "QUEUED":
        artifact = verify_completed_artifact(
            Path(extension["result_path"]) if Path(extension["result_path"]).is_absolute() else directory / extension["result_path"],
            expected_study="48H-002-real-source-quality-and-freshness-audit-v1",
            expected_key="slice_id",
            expected_value=extension.get("slice_id"),
        )
        if artifact and artifact.get("scan_ids") == extension.get("scan_ids"):
            quarantined = artifact.get("quarantined_scans", [])
            extension.update({"status": "COMPLETED_WITH_QUARANTINES" if quarantined else "COMPLETED", "completed_at": artifact.get("recorded_at_utc"), "artifact_sha256": artifact.get("artifact_sha256"), "result_path": str(Path(extension["result_path"]) if Path(extension["result_path"]).is_absolute() else directory / extension["result_path"]), "audited_scan_count": len(artifact.get("audited_scans", [])), "quarantined_scan_count": len(quarantined)})
    for item in plan.get("prospective_scan_queue", []):
        if item.get("status") != "QUEUED":
            continue
        artifact = verify_completed_artifact(
            Path(item["result_path"]) if Path(item["result_path"]).is_absolute() else directory / item["result_path"],
            expected_study="48H-002-prospective-real-source-scan-audit-v1",
            expected_key="scan_id",
            expected_value=item.get("scan_id"),
        )
        if artifact:
            item.update({"status": "COMPLETED", "captured_ns": artifact.get("captured_ns"), "completed_at": artifact.get("recorded_at_utc"), "artifact_sha256": artifact.get("artifact_sha256"), "result_path": str(Path(item["result_path"]) if Path(item["result_path"]).is_absolute() else directory / item["result_path"])})
            row = prospective_ledger_row(artifact)
            row["observed_at_utc"] = artifact.get("recorded_at_utc")
            row["status"] = "AUDITED"
            row["event_id"] = f"{item['scan_id']}:AUDITED"
            append_jsonl_once(directory / "prospective-scans/scan-ledger.jsonl", "event_id", row)


def rebuild_source_monitoring(directory: Path, manifest: dict[str, Any], config: dict[str, Any]) -> None:
    path = directory / "prospective-scans/scan-ledger.jsonl"
    rows: list[dict[str, Any]] = []
    if path.is_file():
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("scan_id") and row.get("status") == "AUDITED":
                rows.append(row)
    by_id = {row["scan_id"]: row for row in rows}
    unique = list(by_id.values())
    all_markets = sorted({market_id for row in unique for market_id in row.get("selected_market_ids", [])})
    unique.sort(key=lambda row: int(row.get("captured_ns") or 0))
    metrics = manifest.setdefault("source_monitoring", {})
    metrics.update({
        "new_scans": len(unique),
        "selected_market_observations": sum(int(row.get("selected_market_observation_count", 0) or 0) for row in unique),
        "quality_valid_pairs": sum(int(row.get("quality_valid_pairs", 0) or 0) for row in unique),
        "positive_top_gross_pairs": sum(int(row.get("positive_top_gross_pairs", 0) or 0) for row in unique),
        "first_scan_at": unique[0].get("captured_at_utc") if unique else None,
        "last_scan_at": unique[-1].get("captured_at_utc") if unique else None,
        "distinct_market_ids": all_markets,
    })
    plan = manifest.get("research_plan", {})
    prospective = plan.get("prospective_scan_queue", [])
    manifest["source_scan_ids_observed"] = sorted({str(item["scan_id"]) for item in prospective if item.get("scan_id")})
    metrics["discovered_scans"] = len(prospective)
    metrics["queued_scans"] = sum(item.get("status") == "QUEUED" for item in prospective)
    metrics["quarantined_scans"] = sum(item.get("status") == "QUARANTINED" for item in prospective)
    metrics["unindexed_scans_at_discovery"] = sum(item.get("published_in_latest_summary_at_discovery") is False for item in prospective)
    metrics["strict_freshness_valid_pairs"] = sum(int(row.get("strict_freshness_valid_pairs", 0) or 0) for row in unique)
    metrics["strict_positive_candidates"] = sum(int(row.get("strict_positive_candidates", 0) or 0) for row in unique)
    metrics["independent_fee_disagreements"] = sum(int(row.get("independent_fee_disagreements", 0) or 0) for row in unique)
    metrics["validity_mismatches"] = sum(int(row.get("validity_mismatches", 0) or 0) for row in unique)
    metrics["edge_mismatches"] = sum(int(row.get("edge_mismatches", 0) or 0) for row in unique)
    positive_full_depth: dict[str, int] = {}
    for row in unique:
        for quantity, count in row.get("positive_full_depth_gross_by_quantity", {}).items():
            positive_full_depth[quantity] = positive_full_depth.get(quantity, 0) + int(count or 0)
    metrics["positive_full_depth_gross_by_quantity"] = positive_full_depth


def aggregate_audits(directory: Path, plan: dict[str, Any]) -> dict[str, Any]:
    files = []
    for item in plan.get("audit_slices", []):
        if item.get("status") in {"COMPLETED", "COMPLETED_WITH_QUARANTINES"} and item.get("result_path"):
            files.append(Path(item["result_path"]))
    extension = plan.get("extension_slice")
    if isinstance(extension, dict) and extension.get("status") in {"COMPLETED", "COMPLETED_WITH_QUARANTINES"} and extension.get("result_path"):
        files.append(Path(extension["result_path"]))
    batches = []
    for path in files:
        artifact = read_json(path)
        result = artifact.get("result") if artifact else None
        if isinstance(result, dict):
            batches.append(result)
    if not batches:
        return {
            "completed_slices": 0,
            "processed_slices": 0,
            "quarantined_slices": 0,
            "snapshot_count": 0,
            "orders_submitted": None,
            "authenticated_requests": None,
        }
    scalar_fields = (
        "snapshot_count", "selected_market_observation_count", "v4_stored_quality_valid_count",
        "independent_v3_valid_count", "strict_freshness_valid_count", "reported_age_exceedance_pair_count",
        "pair_skew_exceedance_count", "independent_fee_checked_quantity_count",
        "independent_fee_disagreement_count", "v4_v3_validity_mismatch_count",
        "v4_v3_top_edge_mismatch_count", "positive_top_pair_gross_count",
        "strict_fresh_positive_top_pair_gross_count", "compressed_source_bytes",
    )
    result: dict[str, Any] = {field: sum(int(batch.get(field, 0) or 0) for batch in batches) for field in scalar_fields}
    for field in (
        "positive_full_depth_gross_by_quantity", "strict_fresh_positive_full_depth_gross_by_quantity",
        "positive_full_depth_and_both_minimums_by_quantity", "strict_fresh_positive_full_depth_and_both_minimums_by_quantity",
        "positive_single_match_fee_sensitivity_by_quantity", "strict_fresh_positive_single_match_fee_sensitivity_by_quantity",
        "positive_fragmentation_safe_fee_sensitivity_by_quantity", "strict_fresh_positive_fragmentation_safe_fee_sensitivity_by_quantity",
        "positive_both_fee_sensitivities_by_quantity", "strict_fresh_positive_both_fee_sensitivities_by_quantity",
    ):
        quantities = set().union(*(set(batch.get(field, {})) for batch in batches))
        result[field] = {quantity: sum(int(batch.get(field, {}).get(quantity, 0) or 0) for batch in batches) for quantity in sorted(quantities)}
    invalid: dict[str, int] = {}
    for batch in batches:
        for reason, count in batch.get("invalid_reasons", {}).items():
            invalid[reason] = invalid.get(reason, 0) + int(count)
    result["invalid_reasons"] = invalid
    statuses = [item.get("status") for item in plan.get("audit_slices", [])]
    extension = plan.get("extension_slice")
    if isinstance(extension, dict):
        statuses.append(extension.get("status"))
    result["processed_slices"] = len(batches)
    result["completed_slices"] = sum(status == "COMPLETED" for status in statuses)
    result["quarantined_slices"] = sum(status == "COMPLETED_WITH_QUARANTINES" for status in statuses)
    result["quarantined_snapshot_count"] = sum(int(batch.get("quarantined_snapshot_count", 0) or 0) for batch in batches)
    result["source_manifest_sha256_by_slice"] = [batch.get("source_manifest_sha256") for batch in batches]
    result["source_code_sha256"] = batches[0].get("source_code_sha256")
    for field in ("orders_submitted", "authenticated_requests"):
        values = [batch.get(field) for batch in batches]
        result[field] = True if any(value is True for value in values) else False if values and all(value is False for value in values) else None
    result["orders_submitted_false_in_all_audited_batches"] = bool(batches) and all(
        batch.get("orders_submitted") is False for batch in batches
    )
    result["authenticated_requests_false_in_all_audited_batches"] = bool(batches) and all(
        batch.get("authenticated_requests") is False for batch in batches
    )
    denominator = result["independent_v3_valid_count"]
    result["strict_freshness_fraction_of_independently_valid_pairs"] = result["strict_freshness_valid_count"] / denominator if denominator else None
    result["limitations"] = batches[0].get("limitations", [])
    return result


def set_priority(plan: dict[str, Any], audit: dict[str, Any], now_ns: int, started_ns: int, config: dict[str, Any]) -> None:
    old = plan.get("priority_mode")
    mismatches = int(audit.get("independent_fee_disagreement_count", 0)) + int(audit.get("v4_v3_validity_mismatch_count", 0)) + int(audit.get("v4_v3_top_edge_mismatch_count", 0))
    strict_positive = int(audit.get("strict_fresh_positive_top_pair_gross_count", 0))
    gross_positive = int(audit.get("positive_top_pair_gross_count", 0))
    fraction = audit.get("strict_freshness_fraction_of_independently_valid_pairs")
    if mismatches:
        mode = "source_discrepancy_extension"
        reason = f"Independent replay found {mismatches} calculation/validity disagreement(s); broaden the adjacent historical sample before making strategy claims."
    elif strict_positive:
        mode = "strict_fresh_candidate_qualification"
        reason = f"Independent replay confirmed {strict_positive} strict-fresh gross-positive observation(s); preserve exact examples and use the adaptive single-scan source audit. No strategy or fill claim follows."
    elif gross_positive:
        mode = "freshness_gate_failure"
        reason = f"Gross-positive observations appeared ({gross_positive}) but none passed strict freshness; prioritize timestamp/source-quality review."
    elif fraction is not None and fraction < float(config["research"]["freshness_extension_threshold"]):
        mode = "freshness_bottleneck_extension"
        reason = f"Only {fraction:.1%} of independently valid observations passed strict reported-age/skew gates; expand the historical slice to see whether this is persistent."
    else:
        mode = "prospective_no_positive_monitor"
        reason = "No strict-fresh economic candidate or source discrepancy was found; continue prospective scans and record the missing outcome/fill-label path rather than training on synthetic targets."
    if mode != old:
        plan.setdefault("priority_history", []).append({"at": iso(now_ns), "from": old, "to": mode, "reason": reason})
    plan["priority_mode"] = mode
    plan["priority_reason"] = reason
    if (mismatches or mode == "freshness_bottleneck_extension") and not plan["adaptation_flags"].get("extension_added"):
        base_ids = plan.get("baseline_scan_ids", [])
        all_ids = []
        # The extension uses the 32 scans immediately preceding the frozen recent 96.
        root = Path(plan["baseline_source_root"])
        available = sorted(
            path.name.removesuffix(".json.gz")
            for path in (root / "snapshots").glob("scan-*.json.gz")
            if path.is_file()
            and not path.is_symlink()
            and scan_id_captured_ns(path.name.removesuffix(".json.gz")) is not None
        )
        first_base = min((available.index(item) for item in base_ids if item in available), default=0)
        start = max(0, first_base - int(config["research"]["audit_batch_size"]))
        all_ids = available[start:first_base]
        if all_ids:
            plan["extension_slice"] = {"slice_id": "source-audit-extension-older-32", "scan_ids": all_ids, "status": "QUEUED", "result_path": "source-audit/extension-older-32.json", "reason": mode}
            plan["adaptation_flags"]["extension_added"] = True


def incident(manifest: dict[str, Any], key: str, detail: Any) -> None:
    incidents = manifest.setdefault("operational_incidents", [])
    if incidents and incidents[-1].get("key") == key and incidents[-1].get("detail") == detail:
        incidents[-1]["last_seen_at"] = iso()
        incidents[-1]["repeat_count"] = int(incidents[-1].get("repeat_count", 1)) + 1
    else:
        incidents.append({"key": key, "at": iso(), "last_seen_at": iso(), "repeat_count": 1, "detail": detail})


def activity_metrics(manifest: dict[str, Any]) -> dict[str, Any]:
    reasons: dict[str, int] = {}
    incidents = manifest.get("operational_incidents", [])
    retry_attempts = 0
    for item in incidents:
        repeats = int(item.get("repeat_count", 1) or 1)
        if item.get("key") == "research_deferred_for_health":
            detail = item.get("detail", [])
            if isinstance(detail, list):
                for reason in detail:
                    reasons[str(reason)] = reasons.get(str(reason), 0) + repeats
        elif item.get("key") == "research_step_failed_retryable":
            retry_attempts += repeats
    decisions = manifest.get("research_plan", {}).get("scheduler_decisions", [])
    by_type: dict[str, int] = {}
    for decision in decisions:
        work_type = str(decision.get("selected_work_type") or "none")
        by_type[work_type] = by_type.get(work_type, 0) + 1
    return {
        "resource_admitted_ticks": int(manifest.get("resource_admitted_ticks", 0) or 0),
        "resource_deferred_ticks": int(manifest.get("resource_deferred_ticks", 0) or 0),
        "resource_deferral_reason_occurrences_with_overlap": reasons,
        "retryable_research_step_failures": retry_attempts,
        "scheduler_decision_count": len(decisions),
        "scheduler_decisions_by_work_type": by_type,
    }


def render_report(manifest: dict[str, Any], final_checks: list[dict[str, Any]], directory: Path) -> str:
    plan = manifest.get("research_plan", {})
    audits = aggregate_audits(directory, plan)
    baseline = plan.get("baseline", {})
    monitoring = manifest.get("source_monitoring", {})
    activity = activity_metrics(manifest)
    prospective = plan.get("prospective_scan_queue", [])
    queued_scan_count = sum(item.get("status") == "QUEUED" for item in prospective)
    unindexed_scan_count = sum(item.get("published_in_latest_summary_at_discovery") is False for item in prospective)
    baseline_ids = plan.get("baseline_scan_ids", [])
    if monitoring.get("new_scans", 0):
        prospective_finding = (
            f"Newly saved scans independently audited during the campaign: {monitoring.get('new_scans')}; "
            f"selected observations: {monitoring.get('selected_market_observations')}; "
            f"quality-valid pairs: {monitoring.get('quality_valid_pairs')}; "
            f"strict-fresh pairs: {monitoring.get('strict_freshness_valid_pairs')}; "
            f"positive top-gross pairs: {monitoring.get('positive_top_gross_pairs')}; "
            f"strict-fresh positives: {monitoring.get('strict_positive_candidates')}."
        )
    else:
        prospective_finding = (
            f"New snapshots discovered: {len(prospective)}; queued at finalization: {queued_scan_count}; "
            f"not present in the latest summary index at discovery: {unindexed_scan_count}. "
            "No prospective scan completed independent replay; all candidate, fee, and mismatch outcomes are NOT MEASURED, not zero."
        )
    baseline_finding = (
        f"Independent replay found {audits.get('independent_v3_valid_count', 0)} quality-valid pairs, {audits.get('strict_freshness_valid_count', 0)} strict-fresh pairs, {audits.get('positive_top_pair_gross_count', 0)} positive top-pair gross observations, and {audits.get('strict_fresh_positive_top_pair_gross_count', 0)} strict-fresh positive observations."
        if audits.get("snapshot_count", 0)
        else "No frozen source audit completed; baseline candidate and fee outcomes are NOT MEASURED."
    )
    lines = [
        "# MIDAS Autonomous Research Campaign 48H-002 — Final Report",
        "",
        f"- Status: **{manifest.get('status')}**",
        f"- Started: {manifest.get('started_at')}",
        f"- Planned deadline: {manifest.get('planned_end_at')}",
        f"- Finalized: {manifest.get('completed_at')}",
        f"- Priority path: `{plan.get('priority_mode')}` — {plan.get('priority_reason')}",
        "",
        "## What MIDAS learned",
        "",
        f"The frozen recent-source audit covered {audits.get('snapshot_count', 0)} scans and {audits.get('selected_market_observation_count', 0)} selected market observations from `{baseline_ids[0] if baseline_ids else 'none'}` through `{baseline_ids[-1] if baseline_ids else 'none'}`.",
        baseline_finding,
        f"Independent fee disagreements: {audits.get('independent_fee_disagreement_count', 0)} across {audits.get('independent_fee_checked_quantity_count', 0)} fee checks. Stored-v4 versus independent-v3 validity mismatches: {audits.get('v4_v3_validity_mismatch_count', 0)}; edge mismatches: {audits.get('v4_v3_top_edge_mismatch_count', 0)}.",
        prospective_finding,
        "No model training or Arena tournament was admitted.",
        "",
        "These are repeated selected snapshots, not independent opportunities. Reported timestamp freshness is a conservative gate and does not establish venue sequence, continuous quote lifetime, order arrival, fills, or profitability.",
        "",
        "## Real-world data and limits",
        "",
        f"At launch, the upstream Veritas index had {baseline.get('processed_snapshots')} scans and {baseline.get('selected_market_observations')} selected observations. It reported {baseline.get('quality_valid_pairs')} quality-valid pairs, {baseline.get('legacy_freshness_valid_pairs')} pairs passing the older 5-second/250-ms freshness sensitivity, zero positive gross candidates, and a maximum top edge of {baseline.get('maximum_top_edge_per_share')} per share.",
        f"The label inventory found active/open Gamma market filters `{plan.get('label_inventory', {}).get('gamma_query_market_state_filters')}`, no settlement/fill-like fields in the selected observation records, and no submitted orders. Real outcome/fill labels were unavailable in these captured inputs.",
        "This is a limitation of the audited observation pipeline. Resolving it requires a separately sourced, timestamp-aligned settlement/outcome label series and, for execution learning, measured or independently verified fills. No such evidence is inferred here.",
        "",
        "## What changed from 48H-001",
        "",
        "48H-001 completed 32 synthetic model records but showed no new strategy advantage; 21 newly trained model leaderboard rows exactly matched the incumbent, all conservative-execution returns were zero, and 38 worker attempts included 23 non-completed attempts. Its useful next priority was real source/outcome-label feasibility.",
        "48H-002 avoided another synthetic sweep. It froze and independently replayed a recent real-source scan window, checked timestamp and fee arithmetic, followed newly saved Veritas scans, and recorded missing labels as a first-class limitation. The 48H-001 report and manifest hashes are checked in final validation.",
        "",
        "## What improved, failed, and remains open",
        "",
        f"- Audit slices: {audits.get('completed_slices', 0)} fully completed, {audits.get('quarantined_slices', 0)} completed with quarantines; {audits.get('quarantined_snapshot_count', 0)} scans quarantined.",
        f"- Resource admissions: {activity['resource_admitted_ticks']} admitted ticks, {activity['resource_deferred_ticks']} deferred ticks; reason counts overlap: {activity['resource_deferral_reason_occurrences_with_overlap']}.",
        f"- Retryable research failures: {activity['retryable_research_step_failures']}; scheduler decisions: {activity['scheduler_decision_count']} ({activity['scheduler_decisions_by_work_type']}).",
        f"- Final protected-artifact checks passed: {sum(bool(item.get('unchanged')) for item in final_checks)}/{len(final_checks)}.",
        f"- Final health: {manifest.get('health')}; the separate Reality source analyzer was catching up at launch, as recorded in preflight. 48H-002 did not modify or restart that worker.",
        "- Remaining scientific blocker: no settled real outcome or measured execution label in the input source. Synthetic training cannot bridge this gap.",
        "",
        "## Evidence and provenance",
        "",
        f"- Launch preflight: `{directory / 'preflight.json'}`",
        f"- Frozen plan and hashes: `{directory / 'research-plan.json'}`",
        f"- Label inventory: `{directory / 'label-inventory.json'}`",
        f"- Per-slice source audits: `{directory / 'source-audit'}`",
        f"- Prospective scan discovery and audit ledger: `{directory / 'prospective-scans/scan-ledger.jsonl'}`",
        f"- Final validation: `{directory / 'final-validation.json'}`",
        "",
        "The campaign was read-only with respect to Reality, Veritas inputs, paper accounts, and protected strategies. No real orders or trading credentials were used.",
        "",
    ]
    return "\n".join(lines)


def finalize(workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any], manifest: dict[str, Any], directory: Path, state: str) -> dict[str, Any]:
    checks = protected_ok(manifest.get("protected_artifacts_at_start", []), workspace, reality_root, config)
    final_source: dict[str, Any]
    try:
        bundle = snapshot_and_summary(veritas_root)
        final_source = {"state": "VALID", "scan_id": bundle["latest"].get("scan_id"), "snapshot_evidence_sha256": bundle["latest"].get("snapshot_evidence_sha256"), "summary_sha256": bundle["summary_sha256"], "research_summary_sha256": bundle["research_summary_sha256"], "metrics": summary_metrics(bundle)}
    except Exception as error:
        final_source = {"state": "INVALID", "error": str(error)[:400]}
    protected_pass = all(item.get("unchanged") for item in checks)
    manifest["status"] = state if protected_pass and final_source.get("state") == "VALID" else "PARTIAL"
    manifest["health"] = "HEALTHY" if protected_pass and final_source.get("state") == "VALID" else "DEGRADED"
    manifest["completed_at"] = iso()
    prospective = manifest.get("research_plan", {}).get("prospective_scan_queue", [])
    prospective_statuses: dict[str, int] = {}
    for item in prospective:
        status = str(item.get("status", "UNKNOWN"))
        prospective_statuses[status] = prospective_statuses.get(status, 0) + 1
    final = {
        "campaign_id": CAMPAIGN_ID,
        "validated_at": iso(),
        "status": manifest["status"],
        "protected_artifacts_unchanged": protected_pass,
        "protected_artifact_checks": checks,
        "final_latest_source": final_source,
        "final_audit_aggregate": aggregate_audits(directory, manifest.get("research_plan", {})),
        "completed_audit_slice_count": sum(item.get("status") == "COMPLETED" for item in manifest.get("research_plan", {}).get("audit_slices", [])),
        "completed_with_quarantines_audit_slice_count": sum(item.get("status") == "COMPLETED_WITH_QUARANTINES" for item in manifest.get("research_plan", {}).get("audit_slices", [])),
        "new_scan_count": manifest.get("source_monitoring", {}).get("new_scans", 0),
        "queued_new_scan_count": sum(item.get("status") == "QUEUED" for item in manifest.get("research_plan", {}).get("prospective_scan_queue", [])),
        "discovered_new_scan_count": len(prospective),
        "unindexed_new_scan_count": sum(item.get("published_in_latest_summary_at_discovery") is False for item in prospective),
        "prospective_scan_status_counts": prospective_statuses,
        "prospective_candidate_metrics_measured": bool(manifest.get("source_monitoring", {}).get("new_scans", 0)),
        "activity": activity_metrics(manifest),
        "resource_deferred_ticks": manifest.get("resource_deferred_ticks", 0),
        "remaining_audit_slices": [item.get("slice_id") for item in manifest.get("research_plan", {}).get("audit_slices", []) if item.get("status") != "COMPLETED"],
    }
    atomic_json(directory / "final-validation.json", final)
    atomic_json(directory / "manifest.json", manifest)
    report = render_report(manifest, checks, directory)
    path = directory / "AUTONOMY_48H_002_FINAL_REPORT.md"
    fd, temporary = tempfile.mkstemp(prefix=".final-report.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(report)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    manifest["final_report_sha256"] = file_sha(path)
    atomic_json(directory / "manifest.json", manifest)
    write_status(directory, manifest)
    command(["systemctl", "--user", "disable", "--now", TIMER_UNIT], timeout=15)
    return final


def tick(workspace: Path, reality_root: Path, veritas_root: Path, api_base: str, config: dict[str, Any]) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    manifest = read_json(directory / "manifest.json")
    if manifest is None:
        return {"campaign_id": CAMPAIGN_ID, "status": "NOT_STARTED", "message": "Run start after preflight."}
    lock_path = directory / "controller.lock"
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        now = time.time_ns()
        if manifest.get("status") in {"COMPLETE", "PARTIAL", "FAILED", "CANCELLED"}:
            command(["systemctl", "--user", "disable", "--now", TIMER_UNIT], timeout=15)
            return {"campaign_id": CAMPAIGN_ID, "status": manifest.get("status"), "message": "Campaign is terminal."}
        if manifest.get("status") == "CANCEL_REQUESTED":
            return finalize(workspace, reality_root, veritas_root, api_base, config, manifest, directory, "CANCELLED")
        if manifest.get("status") == "PAUSED":
            manifest["last_tick_at"] = iso(now)
            manifest["last_tick_ns"] = now
            atomic_json(directory / "manifest.json", manifest)
            write_status(directory, manifest)
            return {"campaign_id": CAMPAIGN_ID, "status": "PAUSED", "deadline_ns": manifest.get("deadline_ns")}
        recover_completed_work(directory, manifest["research_plan"])
        rebuild_source_monitoring(directory, manifest, config)
        try:
            bundle = snapshot_and_summary(veritas_root, verify_snapshot=True)
            queue_new_source_scans(
                manifest["research_plan"],
                veritas_root,
                directory,
                str(bundle["latest"].get("scan_id") or ""),
                started_at_ns=int(manifest["started_at_ns"]),
                deadline_ns=int(manifest["deadline_ns"]),
                now_ns=now,
            )
            manifest["source_scan_ids_observed"] = sorted(
                {item["scan_id"] for item in manifest["research_plan"].get("prospective_scan_queue", [])}
            )
        except Exception as error:
            incident(manifest, "source_snapshot_unavailable", str(error)[:300])
        admitted, sample, gate = resource_admitted(workspace, reality_root, veritas_root, api_base, config, manifest)
        manifest["last_resource_sample"] = sample
        manifest.setdefault("resource_samples", []).append({"at": sample["checked_at"], "admitted": admitted, "gate": gate, "memory_available_bytes": sample["host"]["mem_available_bytes"], "swap": sample["host"]["swap"], "load_average_1m": sample["host"]["load_average_1m"], "reality_memory_current_bytes": sample["recorder"]["memory_current_bytes"]})
        manifest["resource_samples"] = manifest["resource_samples"][-576:]
        deadline = int(manifest["deadline_ns"])
        grace = int(manifest["grace_deadline_ns"])
        if now >= deadline:
            manifest["status"] = "FINALIZING"
            manifest["health"] = "FINALIZING"
        elif not admitted:
            manifest["resource_deferred_ticks"] = int(manifest.get("resource_deferred_ticks", 0)) + 1
            manifest["health"] = "BACKPRESSURE"
            incident(manifest, "research_deferred_for_health", gate["blocking_reasons"])
        else:
            manifest["health"] = "HEALTHY"
            manifest["resource_admitted_ticks"] = int(manifest.get("resource_admitted_ticks", 0)) + 1
            plan = manifest["research_plan"]
            if plan.get("audit_source_code_sha256") != audit_code_sha():
                incident(manifest, "pinned_audit_source_changed", {"expected": plan.get("audit_source_code_sha256"), "current": audit_code_sha()})
            else:
                work_type, research_item, decision_reason = next_research_action(plan)
                decision = {
                    "at": iso(now),
                    "priority_mode": plan.get("priority_mode"),
                    "selected_work_type": work_type,
                    "selected_item_id": (research_item or {}).get("slice_id") or (research_item or {}).get("scan_id"),
                    "reason": decision_reason,
                    "queued_audit_slices": sum(item.get("status") == "QUEUED" for item in plan.get("audit_slices", [])),
                    "queued_prospective_scans": sum(item.get("status") == "QUEUED" for item in plan.get("prospective_scan_queue", [])),
                }
                plan.setdefault("scheduler_decisions", []).append(decision)
                plan["scheduler_decisions"] = plan["scheduler_decisions"][-576:]
                if research_item is not None:
                    try:
                        if work_type == "audit_slice":
                            run_audit_slice(veritas_root, directory, plan, research_item)
                            aggregate = aggregate_audits(directory, plan)
                            set_priority(plan, aggregate, now, int(manifest["started_at_ns"]), config)
                        elif work_type == "prospective_scan":
                            artifact = run_prospective_scan(veritas_root, directory, plan, research_item, manifest)
                            if artifact.get("status") != "OUTSIDE_CAMPAIGN_WINDOW":
                                adapt_to_prospective_scan(plan, artifact["result"], now, int(manifest["started_at_ns"]), config)
                    except ValueError as error:
                        if work_type == "prospective_scan":
                            research_item.update({"status": "QUARANTINED", "quarantined_at": iso(now), "error": str(error)[:400]})
                            append_jsonl_once(
                                directory / "prospective-scans/scan-ledger.jsonl",
                                "event_id",
                                {"event_id": f"{research_item['scan_id']}:QUARANTINED", "scan_id": research_item["scan_id"], "status": "QUARANTINED", "quarantined_at": iso(now), "error": str(error)[:400]},
                            )
                            incident(manifest, "prospective_scan_quarantined", {"scan_id": research_item["scan_id"], "error": str(error)[:300]})
                        else:
                            outcome = record_task_failure(research_item, error, now, config)
                            incident(manifest, "research_step_failed_retryable", {"item": research_item.get("slice_id"), "outcome": outcome, "error": str(error)[:300]})
                    except Exception as error:
                        outcome = record_task_failure(research_item, error, now, config)
                        incident(manifest, "research_step_failed_retryable", {"item": research_item.get("slice_id") or research_item.get("scan_id"), "outcome": outcome, "error": str(error)[:300]})
                else:
                    elapsed = now - int(manifest["started_at_ns"])
                    if elapsed >= 12 * 3600 * 1_000_000_000 and not plan["adaptation_flags"].get("no_positive_12h_shift") and aggregate_audits(directory, plan).get("strict_fresh_positive_top_pair_gross_count", 0) == 0:
                        old = plan.get("priority_mode")
                        plan["priority_mode"] = "data_quality_and_label_feasibility"
                        plan["priority_reason"] = "No strict-fresh candidate emerged in the initial audit; remaining campaign time is reserved for prospective source-quality monitoring and explicit outcome/fill-label feasibility."
                        plan["priority_history"].append({"at": iso(now), "from": old, "to": plan["priority_mode"], "reason": plan["priority_reason"]})
                        plan["adaptation_flags"]["no_positive_12h_shift"] = True
        rebuild_source_monitoring(directory, manifest, config)
        manifest["last_tick_at"] = iso(now)
        manifest["last_tick_ns"] = now
        if now >= deadline:
            atomic_json(directory / "manifest.json", manifest)
            if now >= grace:
                plan = manifest.get("research_plan", {})
                required_slices = list(plan.get("audit_slices", []))
                extension = plan.get("extension_slice")
                if isinstance(extension, dict):
                    required_slices.append(extension)
                prospective_pending = any(item.get("status") in {"QUEUED", "BLOCKED", "QUARANTINED"} for item in plan.get("prospective_scan_queue", []))
                all_complete = all(item.get("status") == "COMPLETED" for item in required_slices) and not prospective_pending
                return finalize(workspace, reality_root, veritas_root, api_base, config, manifest, directory, "COMPLETE" if all_complete else "PARTIAL")
            # The unit is a bounded read-only one-shot; the next persistent timer tick
            # reconciles the child exit and writes the final report after the grace window.
            write_status(directory, manifest)
            return {"campaign_id": CAMPAIGN_ID, "status": "FINALIZING", "deadline": iso(deadline), "grace_deadline": iso(grace)}
        atomic_json(directory / "research-plan.json", manifest["research_plan"])
        atomic_json(directory / "manifest.json", manifest)
        write_status(directory, manifest)
        return {"campaign_id": CAMPAIGN_ID, "status": manifest["status"], "health": manifest["health"], "priority": manifest["research_plan"].get("priority_mode"), "completed_audit_slices": sum(item.get("status") == "COMPLETED" for item in manifest["research_plan"].get("audit_slices", [])), "completed_with_quarantines_audit_slices": sum(item.get("status") == "COMPLETED_WITH_QUARANTINES" for item in manifest["research_plan"].get("audit_slices", [])), "audited_new_scans": manifest.get("source_monitoring", {}).get("new_scans", 0), "discovered_new_scans": len(manifest["research_plan"].get("prospective_scan_queue", [])), "queued_new_scans": sum(item.get("status") == "QUEUED" for item in manifest["research_plan"].get("prospective_scan_queue", [])), "deferred": not admitted}


def control(workspace: Path, action: str) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    manifest = read_json(directory / "manifest.json")
    if manifest is None:
        raise RuntimeError("48H-002 has not started")
    if action == "pause":
        if manifest.get("status") in {"COMPLETE", "PARTIAL", "FAILED", "CANCELLED"}:
            raise RuntimeError("Campaign is terminal")
        manifest["status"] = "PAUSED"
    elif action == "resume":
        if manifest.get("status") != "PAUSED":
            raise RuntimeError("Campaign is not paused")
        manifest["status"] = "RUNNING"
    elif action == "cancel":
        manifest["status"] = "CANCEL_REQUESTED"
    else:
        raise ValueError(action)
    atomic_json(directory / "manifest.json", manifest)
    return {"campaign_id": CAMPAIGN_ID, "status": manifest["status"], "action": action}


def status(workspace: Path) -> dict[str, Any]:
    directory = campaign_dir(workspace)
    manifest = read_json(directory / "manifest.json")
    if manifest is None:
        return {"campaign_id": CAMPAIGN_ID, "status": "NOT_STARTED", "preflight": read_json(directory / "preflight.json")}
    return {"campaign_id": CAMPAIGN_ID, "status": manifest.get("status"), "health": manifest.get("health"), "started_at": manifest.get("started_at"), "planned_end_at": manifest.get("planned_end_at"), "priority": manifest.get("research_plan", {}).get("priority_mode"), "priority_reason": manifest.get("research_plan", {}).get("priority_reason"), "audit_slices": manifest.get("research_plan", {}).get("audit_slices"), "source_monitoring": manifest.get("source_monitoring"), "resource_deferred_ticks": manifest.get("resource_deferred_ticks"), "report_path": manifest.get("report_path"), "manifest_path": str(directory / "manifest.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "start", "tick", "status", "pause", "resume", "cancel"))
    parser.add_argument("--workspace", type=Path, default=REPOSITORY)
    parser.add_argument("--reality-root", type=Path, default=None)
    parser.add_argument("--veritas-root", type=Path, default=None)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    reality_root = (args.reality_root or workspace.parent / "midas-reality").resolve()
    veritas_root = (args.veritas_root or workspace.parent / "midas-veritas" / "data/veritas-observatory").resolve()
    config = load_config(workspace)
    try:
        if args.action == "preflight":
            ready, _ = readiness_report(workspace, reality_root, veritas_root, args.api_base, config)
            directory = campaign_dir(workspace)
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            atomic_json(directory / "preflight.json", ready)
            output = ready
        elif args.action == "start":
            manifest = initialize(workspace, reality_root, veritas_root, args.api_base, config)
            output = {"campaign_id": CAMPAIGN_ID, "status": manifest["status"], "started_at": manifest["started_at"], "planned_end_at": manifest["planned_end_at"], "preflight": str(campaign_dir(workspace) / "preflight.json")}
        elif args.action == "tick":
            output = tick(workspace, reality_root, veritas_root, args.api_base, config)
        elif args.action == "status":
            output = status(workspace)
        else:
            output = control(workspace, args.action)
        print(json.dumps(output, indent=2, sort_keys=True, default=str))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"campaign_id": CAMPAIGN_ID, "action": args.action, "error": str(error)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
