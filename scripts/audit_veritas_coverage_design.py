#!/usr/bin/env python3
"""Independently audit selection-probability support in the Veritas coverage pilot.

This offline audit verifies the pilot's append-only event chain and its snapshot
and v4-analysis lineage, then checks the rotating cohort's recorded within-scan
inclusion probabilities. Estimates are conditional on each scan's bounded
Gamma-response union; the script makes no network requests and submits no orders.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "VERITAS-M2-COVERAGE-DESIGN-AUDIT-002"
ANALYSIS_VERSION = "veritas-coverage-design-audit-v2"
PILOT_ID = "VERITAS-M2-COVERAGE-PILOT-001"
PILOT_PROTOCOL = "veritas-coverage-pilot-v1"
MAX_EVENTS = 48
MAX_EVENT_BYTES = 64 * 1024
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_SNAPSHOT_BYTES = 96 * 1024 * 1024
MAX_DECOMPRESSED_SNAPSHOT_BYTES = 32 * 1024 * 1024
MAX_ANALYSIS_EVENT_BYTES = 2 * 1024 * 1024
MAX_SUMMARY_BYTES = 4 * 1024 * 1024
SELECTION_PROBABILITY_TOLERANCE = Decimal("0.000000000001")
SCAN_ID = re.compile(r"scan-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path, *, maximum_bytes: int) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Evidence file is missing or unsafe: {path.name}")
    size = path.stat().st_size
    if size > maximum_bytes:
        raise ValueError(f"Evidence file exceeds its bound: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest(), size


def _read_json(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    _file_sha256(path, maximum_bytes=maximum_bytes)
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid JSON evidence: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Evidence must be an object: {path.name}")
    return value


def _verify_digest(value: dict[str, Any], field: str) -> str:
    digest = value.get(field)
    payload = dict(value)
    payload.pop(field, None)
    if not isinstance(digest, str) or digest != _sha256(_canonical(payload)):
        raise ValueError(f"Evidence digest mismatch: {field}")
    return digest


def _read_snapshot(path: Path) -> tuple[dict[str, Any], str, int]:
    snapshot_sha256, compressed_size = _file_sha256(path, maximum_bytes=MAX_SNAPSHOT_BYTES)
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read(MAX_DECOMPRESSED_SNAPSHOT_BYTES + 1)
    except (OSError, EOFError, gzip.BadGzipFile) as error:
        raise ValueError(f"Snapshot is not a valid gzip stream: {path.name}") from error
    if len(raw) > MAX_DECOMPRESSED_SNAPSHOT_BYTES:
        raise ValueError("Snapshot decompressed bytes exceed the audit bound")
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Snapshot JSON is invalid: {path.name}") from error
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must contain a JSON object")
    return snapshot, snapshot_sha256, compressed_size


def _safe_relative(root: Path, value: Any, *, field: str) -> Path:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"{field} is not a safe relative path")
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError(f"{field} points through a symlink")
        current = current.parent
    if not path.resolve(strict=True).is_relative_to(root):
        raise ValueError(f"{field} escapes its evidence root")
    return path


def _int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer >= {minimum}")
    return value


def _verify_event_source(event: dict[str, Any], observatory_root: Path) -> dict[str, Any]:
    scan_id = event.get("scan_id")
    if not isinstance(scan_id, str) or not SCAN_ID.fullmatch(scan_id):
        raise ValueError("Coverage event has an invalid scan ID")

    snapshot_directory = observatory_root / "snapshots"
    if snapshot_directory.is_symlink() or not snapshot_directory.is_dir():
        raise ValueError("Snapshot directory is missing or unsafe")
    snapshot_path = _safe_relative(
        observatory_root, event.get("snapshot_file"), field="snapshot_file"
    )
    snapshot, snapshot_sha256, compressed_size = _read_snapshot(snapshot_path)
    if snapshot_sha256 != event.get("snapshot_file_sha256"):
        raise ValueError(f"Snapshot file hash mismatch: {scan_id}")
    if (
        snapshot.get("scan_id") != scan_id
        or snapshot.get("snapshot_evidence_sha256") != event.get("snapshot_evidence_sha256")
        or snapshot.get("source_code_sha256") != event.get("snapshot_source_code_sha256")
    ):
        raise ValueError(f"Snapshot identity or evidence lineage mismatch: {scan_id}")

    analysis_dir = observatory_root / "analysis-events" / "v4"
    if observatory_root.joinpath("analysis-events").is_symlink() or analysis_dir.is_symlink():
        raise ValueError("Analysis event directory is unsafe")
    analysis_path = analysis_dir / f"{scan_id}.json"
    analysis_file_sha256, _ = _file_sha256(analysis_path, maximum_bytes=MAX_ANALYSIS_EVENT_BYTES)
    if analysis_file_sha256 != event.get("analysis_event_file_sha256"):
        raise ValueError(f"Analysis event file hash mismatch: {scan_id}")
    analysis_event = _read_json(analysis_path, maximum_bytes=MAX_ANALYSIS_EVENT_BYTES)
    analysis_sha256 = _verify_digest(analysis_event, "analysis_event_sha256")
    if (
        analysis_sha256 != event.get("analysis_event_sha256")
        or analysis_event.get("analysis_version") != "veritas-finalized-snapshot-analysis-v4"
        or analysis_event.get("scan_id") != scan_id
        or analysis_event.get("snapshot_evidence_sha256")
        != snapshot.get("snapshot_evidence_sha256")
    ):
        raise ValueError(f"Analysis event identity or snapshot lineage mismatch: {scan_id}")

    selection = snapshot.get("selection")
    discovery = snapshot.get("discovery")
    observations = snapshot.get("market_observations")
    analysis_rows = analysis_event.get("market_rows")
    if (
        not isinstance(selection, dict)
        or not isinstance(discovery, dict)
        or not isinstance(observations, list)
        or not isinstance(analysis_rows, list)
        or not isinstance(selection.get("selected_markets"), list)
        or not isinstance(selection.get("plan"), dict)
    ):
        raise ValueError(f"Snapshot market-selection evidence is incomplete: {scan_id}")

    selected_rows = selection["selected_markets"]
    selected_by_id = {
        str(row.get("market_id")): row for row in selected_rows if isinstance(row, dict)
    }
    observation_by_id = {
        str(row.get("market_id")): row for row in observations if isinstance(row, dict)
    }
    analysis_by_id = {
        str(row.get("market_id")): row for row in analysis_rows if isinstance(row, dict)
    }
    if (
        len(selected_by_id) != len(selected_rows)
        or len(observation_by_id) != len(observations)
        or len(analysis_by_id) != len(analysis_rows)
        or not selected_by_id
        or set(selected_by_id) != set(observation_by_id)
        or set(selected_by_id) != set(analysis_by_id)
    ):
        raise ValueError(f"Selected, observed, and analyzed market identities disagree: {scan_id}")

    expected_rows: list[dict[str, Any]] = []
    for market_id, selected in selected_by_id.items():
        analyzed = analysis_by_id[market_id]
        valid = analyzed.get("valid")
        if not isinstance(valid, bool):
            raise ValueError(f"Analysis validity is not boolean: {scan_id}")
        expected_rows.append(
            {
                "market_id": market_id,
                "cohort_role": str(selected.get("cohort_role") or "unknown"),
                "selection_stratum": str(selected.get("selection_stratum") or "unclassified"),
                "selection_probability": selected.get("selection_probability"),
                "primary_category": str(selected.get("primary_category") or "unknown"),
                "quality_valid": valid,
                "invalid_reason": analyzed.get("invalid_reason"),
            }
        )
    claimed_rows = event.get("market_rows")
    if not isinstance(claimed_rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("market_id"), str)
        for row in claimed_rows
    ):
        raise ValueError(f"Coverage-pilot rows are malformed: {scan_id}")
    if sorted(claimed_rows, key=lambda row: row["market_id"]) != sorted(
        expected_rows, key=lambda row: row["market_id"]
    ):
        raise ValueError(f"Coverage-pilot rows disagree with source evidence: {scan_id}")

    plan = selection["plan"]
    expected_event_fields = {
        "phase": plan.get("phase"),
        "selection_sequence": plan.get("sequence"),
        "bounded_eligible_markets": discovery.get("eligible_pair_markets"),
        "discovered_unique_market_ids": discovery.get("unique_market_ids"),
        "excluded_market_ids": discovery.get("excluded_market_ids"),
        "stable_control_available": plan.get("stable_control_available_this_scan"),
        "stable_control_missing": plan.get("stable_control_missing_this_scan"),
        "rotating_strata": plan.get("rotation_strata"),
    }
    for field, expected in expected_event_fields.items():
        if event.get(field) != expected:
            raise ValueError(f"Coverage event {field} disagrees with snapshot: {scan_id}")
    if (
        event.get("selected_market_pairs") != len(expected_rows)
        or event.get("quality_valid_pairs") != sum(row["quality_valid"] for row in expected_rows)
        or analysis_event.get("attempted_market_pairs") != len(expected_rows)
        or analysis_event.get("valid_quality_pairs")
        != sum(row["quality_valid"] for row in expected_rows)
    ):
        raise ValueError(f"Coverage-pilot counts disagree with source rows: {scan_id}")
    if (
        event.get("orders_submitted") is not False
        or event.get("authenticated_requests") is not False
    ):
        raise ValueError("Coverage pilot must remain read-only")
    return {"snapshot_bytes": compressed_size, "analysis_event_path": str(analysis_path)}


def _selection_probability(value: Any, field: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a decimal string")
    try:
        probability = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} must be a decimal string") from error
    if not probability.is_finite() or probability <= 0 or probability > 1:
        raise ValueError(f"{field} must be in (0, 1]")
    return probability


def audit_selection_design(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Check rotating inclusion probabilities and estimate yield on supported strata."""
    if not events or len(events) > MAX_EVENTS:
        raise ValueError("Coverage pilot must contain 1 to 48 events")

    role_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"selected": 0, "valid": 0})
    scans: list[dict[str, Any]] = []
    represented_population = 0
    supported_population = 0
    supported_scan_count = 0
    partially_supported_scan_count = 0
    previous_sequence = 0
    skipped_sequences = 0

    for event in events:
        scan_id = str(event.get("scan_id") or "")
        sequence = _int(event.get("selection_sequence"), "selection_sequence", minimum=1)
        if sequence <= previous_sequence:
            raise ValueError("Coverage pilot selection sequences must strictly increase")
        if previous_sequence:
            skipped_sequences += sequence - previous_sequence - 1
        previous_sequence = sequence

        strata = event.get("rotating_strata")
        rows = event.get("market_rows")
        if not isinstance(strata, dict) or not isinstance(rows, list):
            raise ValueError(f"Coverage design fields are missing: {scan_id}")
        eligible = _int(event.get("bounded_eligible_markets"), "bounded_eligible_markets")
        control_count = _int(event.get("stable_control_available"), "stable_control_available")
        selected_total = _int(event.get("selected_market_pairs"), "selected_market_pairs")
        valid_total = _int(event.get("quality_valid_pairs"), "quality_valid_pairs")

        populations: dict[str, int] = {}
        quotas: dict[str, int] = {}
        for stratum, record in strata.items():
            if not isinstance(stratum, str) or not isinstance(record, dict):
                raise ValueError(f"Invalid rotation stratum: {scan_id}")
            population = _int(record.get("population"), f"{stratum}.population")
            quota = _int(record.get("quota"), f"{stratum}.quota")
            if population == 0 or quota > population:
                raise ValueError(f"Invalid rotation population or quota: {scan_id}/{stratum}")
            populations[stratum] = population
            quotas[stratum] = quota

        if sum(populations.values()) + control_count != eligible:
            raise ValueError(f"Rotation and control populations do not reconcile: {scan_id}")
        if sum(quotas.values()) + control_count != selected_total:
            raise ValueError(f"Rotation quotas do not reconcile with selected count: {scan_id}")

        seen_ids: set[str] = set()
        rotating_counts: Counter[str] = Counter()
        rotating_valid: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        role_valid: Counter[str] = Counter()
        weighted_valid_total = 0.0
        scan_support = 0
        scan_rotation_population = sum(populations.values())
        unsupported_strata: list[str] = []

        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Invalid market row: {scan_id}")
            market_id = str(row.get("market_id") or "")
            if not market_id or market_id in seen_ids:
                raise ValueError(f"Duplicate or missing market ID: {scan_id}")
            seen_ids.add(market_id)
            role = row.get("cohort_role")
            valid = row.get("quality_valid")
            if role not in {"rotating_stratified", "stable_random_control"}:
                raise ValueError(f"Unknown cohort role: {scan_id}")
            if not isinstance(valid, bool):
                raise ValueError(f"Quality validity is not boolean: {scan_id}")
            role_counts[str(role)] += 1
            role_valid[str(role)] += int(valid)
            if role == "stable_random_control":
                continue

            stratum = row.get("selection_stratum")
            if not isinstance(stratum, str) or stratum not in populations:
                raise ValueError(f"Rotating market has an unknown stratum: {scan_id}")
            population = populations[stratum]
            quota = quotas[stratum]
            if quota == 0:
                raise ValueError(f"A market was selected from a zero-quota stratum: {scan_id}")
            probability = _selection_probability(
                row.get("selection_probability"), "selection_probability"
            )
            expected_probability = Decimal(quota) / Decimal(population)
            if abs(probability - expected_probability) > SELECTION_PROBABILITY_TOLERANCE:
                raise ValueError(f"Selection probability mismatch: {scan_id}/{stratum}")
            rotating_counts[stratum] += 1
            rotating_valid[stratum] += int(valid)
            if valid:
                weighted_valid_total += 1.0 / float(probability)

        for stratum, quota in quotas.items():
            if rotating_counts[stratum] != quota:
                raise ValueError(
                    f"Selected count does not match stratum quota: {scan_id}/{stratum}"
                )
            if quota > 0:
                scan_support += populations[stratum]
            elif populations[stratum] > 0:
                unsupported_strata.append(stratum)

        if role_counts["stable_random_control"] != control_count:
            raise ValueError(f"Stable-control count does not reconcile: {scan_id}")
        if role_counts["rotating_stratified"] != sum(quotas.values()):
            raise ValueError(f"Rotating count does not reconcile: {scan_id}")
        if sum(role_valid.values()) != valid_total:
            raise ValueError(f"Quality-valid count does not reconcile: {scan_id}")

        scan_support_fraction = (
            scan_support / scan_rotation_population if scan_rotation_population else None
        )
        design_weighted_yield = weighted_valid_total / scan_support if scan_support else None
        if scan_support == scan_rotation_population:
            supported_scan_count += 1
        elif scan_support:
            partially_supported_scan_count += 1
        represented_population += scan_rotation_population
        supported_population += scan_support
        scans.append(
            {
                "scan_id": scan_id,
                "captured_at_utc": event.get("captured_at_utc"),
                "selection_sequence": sequence,
                "phase": event.get("phase"),
                "eligible_population": eligible,
                "stable_control_available": control_count,
                "rotating_population": scan_rotation_population,
                "rotating_selected": role_counts["rotating_stratified"],
                "rotating_quality_valid": role_valid["rotating_stratified"],
                "rotating_unweighted_yield": (
                    role_valid["rotating_stratified"] / role_counts["rotating_stratified"]
                    if role_counts["rotating_stratified"]
                    else None
                ),
                "rotating_supported_population": scan_support,
                "rotating_population_support_fraction": scan_support_fraction,
                "design_weighted_valid_count_estimate_on_supported_population": (
                    round(weighted_valid_total, 6) if scan_support else None
                ),
                "design_weighted_quality_yield_on_supported_population": (
                    round(design_weighted_yield, 8) if design_weighted_yield is not None else None
                ),
                "unsupported_positive_population_strata": unsupported_strata,
                "stable_control_selected": role_counts["stable_random_control"],
                "stable_control_quality_valid": role_valid["stable_random_control"],
            }
        )
        for role in ("rotating_stratified", "stable_random_control"):
            role_totals[role]["selected"] += role_counts[role]
            role_totals[role]["valid"] += role_valid[role]

    for counts in role_totals.values():
        counts["yield"] = counts["valid"] / counts["selected"] if counts["selected"] else 0

    fully_supported_yields = [
        row["design_weighted_quality_yield_on_supported_population"]
        for row in scans
        if row["rotating_population_support_fraction"] == 1.0
    ]
    supported_yields = [
        row["design_weighted_quality_yield_on_supported_population"]
        for row in scans
        if row["design_weighted_quality_yield_on_supported_population"] is not None
    ]
    return {
        "scan_count": len(scans),
        "skipped_selection_sequences": skipped_sequences,
        "role_totals": dict(sorted(role_totals.items())),
        "fully_supported_scan_count": supported_scan_count,
        "partially_supported_scan_count": partially_supported_scan_count,
        "unsupported_scan_count": len(scans)
        - supported_scan_count
        - partially_supported_scan_count,
        "mean_rotating_population_support_fraction": (
            round(supported_population / represented_population, 8)
            if represented_population
            else None
        ),
        "fully_supported_scan_weighted_yield_mean": (
            round(sum(fully_supported_yields) / len(fully_supported_yields), 8)
            if fully_supported_yields
            else None
        ),
        "supported_population_scan_yield_range": (
            {
                "minimum": min(supported_yields),
                "maximum": max(supported_yields),
            }
            if supported_yields
            else None
        ),
        "inference": "descriptive only; scans and markets are repeated and dependent",
        "scans": scans,
    }


def run_audit(pilot_root: Path, observatory_root: Path) -> dict[str, Any]:
    if pilot_root.is_symlink() or observatory_root.is_symlink():
        raise ValueError("Audit roots cannot be symlinks")
    pilot_root = pilot_root.resolve(strict=True)
    observatory_root = observatory_root.resolve(strict=True)
    events_dir = pilot_root / "events"
    if events_dir.is_symlink() or not events_dir.is_dir():
        raise ValueError("Coverage pilot events directory is missing or unsafe")

    plan_path = pilot_root / "plan.json"
    plan = _read_json(plan_path, maximum_bytes=MAX_EVENT_BYTES)
    plan_digest = _verify_digest(plan, "plan_sha256")
    state = _read_json(pilot_root / "state.json", maximum_bytes=MAX_EVENT_BYTES)
    if (
        state.get("study_id") != PILOT_ID
        or state.get("protocol_version") != PILOT_PROTOCOL
        or state.get("plan_sha256") != plan_digest
    ):
        raise ValueError("Coverage pilot state does not match its frozen plan")
    implementation_sha256 = state.get("implementation_sha256")
    if not isinstance(implementation_sha256, str) or len(implementation_sha256) != 64:
        raise ValueError("Coverage pilot implementation identity is invalid")

    paths = sorted(events_dir.glob("scan-*.json"), key=lambda path: path.name)
    if events_dir.is_symlink() or len(paths) > MAX_EVENTS:
        raise ValueError("Coverage pilot event count exceeds its bound")
    events: list[dict[str, Any]] = []
    event_manifest: list[dict[str, Any]] = []
    snapshot_manifest: list[dict[str, Any]] = []
    analysis_manifest: list[dict[str, Any]] = []
    previous_event_sha256: str | None = None
    total_snapshot_bytes = 0
    for path in paths:
        event = _read_json(path, maximum_bytes=MAX_EVENT_BYTES)
        event_digest = _verify_digest(event, "event_sha256")
        if (
            event.get("study_id") != PILOT_ID
            or event.get("protocol_version") != PILOT_PROTOCOL
            or event.get("plan_sha256") != plan_digest
            or event.get("implementation_sha256") != implementation_sha256
            or event.get("scan_id") != path.stem
            or event.get("previous_event_sha256") != previous_event_sha256
        ):
            raise ValueError(f"Coverage pilot event lineage mismatch: {path.name}")
        lineage = _verify_event_source(event, observatory_root)
        total_snapshot_bytes += int(lineage["snapshot_bytes"])
        if total_snapshot_bytes > MAX_TOTAL_SNAPSHOT_BYTES:
            raise ValueError("Total snapshot bytes exceed the coverage audit bound")
        event_manifest.append(
            {
                "scan_id": event["scan_id"],
                "event_sha256": event_digest,
                "file_sha256": _file_sha256(path, maximum_bytes=MAX_EVENT_BYTES)[0],
            }
        )
        snapshot_manifest.append(
            {"scan_id": event["scan_id"], "snapshot_file_sha256": event["snapshot_file_sha256"]}
        )
        analysis_manifest.append(
            {
                "scan_id": event["scan_id"],
                "analysis_event_file_sha256": event["analysis_event_file_sha256"],
                "analysis_event_sha256": event["analysis_event_sha256"],
            }
        )
        events.append(event)
        previous_event_sha256 = event_digest
    if not events:
        raise ValueError("Coverage pilot has no completed scan events")

    summary_path = pilot_root / "summary.json"
    summary = _read_json(summary_path, maximum_bytes=MAX_SUMMARY_BYTES)
    summary_sha256 = _verify_digest(summary, "summary_sha256")
    analysis = audit_selection_design(events)
    if (
        summary.get("study_id") != PILOT_ID
        or summary.get("protocol_version") != PILOT_PROTOCOL
        or summary.get("completed_scans") != analysis["scan_count"]
        or summary.get("selected_market_pair_slots")
        != sum(row["selected_market_pairs"] for row in events)
        or summary.get("quality_valid_pairs") != sum(row["quality_valid_pairs"] for row in events)
    ):
        raise ValueError("Coverage pilot summary disagrees with its verified event chain")

    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "analysis_version": ANALYSIS_VERSION,
        "analysis_code_sha256": _file_sha256(
            Path(__file__).resolve(), maximum_bytes=MAX_EVENT_BYTES
        )[0],
        "created_at_utc": datetime.now(UTC).isoformat(),
        "study_status_at_audit": state.get("status"),
        "source": {
            "study_id": PILOT_ID,
            "protocol_version": PILOT_PROTOCOL,
            "plan_sha256": plan_digest,
            "implementation_sha256": implementation_sha256,
            "summary_file_sha256": _file_sha256(summary_path, maximum_bytes=MAX_SUMMARY_BYTES)[0],
            "summary_sha256": summary_sha256,
            "event_count": len(events),
            "event_manifest_sha256": _sha256(_canonical(event_manifest)),
            "snapshot_manifest_sha256": _sha256(_canonical(snapshot_manifest)),
            "analysis_event_manifest_sha256": _sha256(_canonical(analysis_manifest)),
            "compressed_snapshot_bytes": total_snapshot_bytes,
            "first_scan_id": events[0]["scan_id"],
            "last_scan_id": events[-1]["scan_id"],
        },
        "analysis": analysis,
        "interpretation": {
            "estimand": "per-scan quality-valid yield among rotating markets in strata with positive inclusion probability, conditional on the bounded Gamma response union and frozen controls",
            "selection_probability_check": "each selected rotating market must match quota divided by its eligible stratum population",
            "unsupported_strata": "strata with zero quota are excluded from the design-weighted yield and reported per scan",
            "role_comparison": "rotating versus stable controls remains descriptive and nonrandomized",
            "no_venue_wide_inference": True,
            "no_continuous_coverage_claim": True,
            "no_economic_candidate_or_profit_claim": True,
            "markets_and_scans_are_dependent": True,
        },
        "safety": {
            "live_requests": 0,
            "authenticated_requests": False,
            "orders_submitted": False,
            "campaign_modified": False,
        },
    }
    result_sha256 = _sha256(_canonical(result))
    artifact = {**result, "result_sha256": result_sha256}
    artifact["artifact_sha256"] = _sha256(_canonical(artifact))
    return artifact


def write_new_artifact(path: Path, artifact: dict[str, Any]) -> None:
    payload = json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Audit output must be a new file in a non-symlink directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    linked = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        linked = True
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        if linked:
            path.unlink(missing_ok=True)
        raise
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--observatory-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    artifact = run_audit(args.pilot_root, args.observatory_root)
    write_new_artifact(args.output, artifact)
    print(
        json.dumps(
            {"output": str(args.output), "artifact_sha256": artifact["artifact_sha256"]},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
