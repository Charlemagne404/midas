"""Bounded, prospective measurement-yield pilot over scheduled snapshots."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

VERSION = "veritas-coverage-pilot-v1"
STUDY_ID = "VERITAS-M2-COVERAGE-PILOT-001"
MAX_STUDY_SECONDS = 24 * 60 * 60
MAX_STUDY_SCANS = 48
MAX_EVENT_BYTES = 256 * 1024
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_SUMMARY_BYTES = 2 * 1024 * 1024

_PLAN: dict[str, Any] = {
    "schema_version": 1,
    "study_id": STUDY_ID,
    "protocol_version": VERSION,
    "study_type": "prospective measurement-only coverage pilot",
    "activation": "first scheduled observer snapshot after this implementation is deployed; no historical snapshots are backfilled",
    "window": {
        "maximum_elapsed_hours": 24,
        "maximum_completed_scans": MAX_STUDY_SCANS,
        "early_stopping": False,
        "missed_scans": "remain visible as coverage gaps; do not extend the fixed elapsed-time window",
    },
    "observation_frame": {
        "source": "existing six-query bounded Gamma union and one batched public CLOB books read",
        "target_markets_per_scan": 40,
        "configured_market_range": [30, 50],
        "stable_control_count": 8,
        "rotating_selection": "existing stratified phase rotation with recorded conditional inclusion probabilities",
        "additional_public_requests": 0,
        "selection_uses_price_edge": False,
        "coverage_kind": "intermittent_public_snapshots",
    },
    "primary_outcome": {
        "name": "complete quality-valid paired-book yield per selected pair slot",
        "numerator": "selected V1 same-condition pairs passing the existing finalized v4 request/receipt, identity, and paired-book quality checks",
        "denominator": "all selected pair slots; invalid and unavailable pairs remain in the denominator",
        "comparison": "stable_random_control versus rotating_stratified roles within the same scheduled scan",
    },
    "secondary_outcomes": [
        "per-scan and cumulative quality yield by role, phase, and selection stratum",
        "distinct selected market IDs and market revisit counts",
        "bounded discovery population, exclusions, missing controls, and skipped scan sequences",
        "source response and analysis-event lineage for every included scan",
        "observed candidate gate counts, without treating absence as a strategy result",
    ],
    "analysis": {
        "role_comparison_is_descriptive": True,
        "causal_claim_permitted": False,
        "venue_wide_prevalence_estimated": False,
        "dependent_repeated_observations_are_independent_trials": False,
        "no_strategy_or_model_promotion": True,
    },
    "safety": {
        "read_only_public_market_data": True,
        "orders_submitted": False,
        "authenticated_requests": False,
        "does_not_modify_reality_campaigns": True,
        "writes_only_versioned_aggregates_under_observatory_root": True,
        "maximum_pilot_artifact_bytes": 4 * 1024 * 1024,
    },
    "limitations": [
        "The bounded query-response union is selected and is not the venue-wide universe.",
        "Stable controls were frozen from an earlier bounded discovery union and are not randomized against rotating markets.",
        "The same-scan role comparison is descriptive; market composition and availability differ by role.",
        "Intermittent public snapshots do not establish continuous coverage, quote lifetime, fills, or profitability.",
        "Reported timestamp age is an update-recency diagnostic; the pilot does not claim venue sequence or upstream freshness.",
    ],
}


def build_plan() -> dict[str, Any]:
    """Return a fresh copy of the preregistered protocol."""
    return copy.deepcopy(_PLAN)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _code_sha256() -> str:
    module_dir = Path(__file__).resolve().parent
    files = (
        Path(__file__),
        module_dir / "observatory.py",
        module_dir / "continuous_analysis.py",
        module_dir / "opportunity_audit.py",
        module_dir / "economic_feasibility_v3.py",
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict[str, Any], *, maximum_bytes: int) -> None:
    data = _canonical(value)
    if len(data) > maximum_bytes:
        raise ValueError(f"Coverage pilot artifact exceeds its bound: {path.name}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError(f"Unsafe coverage pilot path: {path.name}")
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_event(path: Path, event: dict[str, Any]) -> bool:
    data = _canonical(event)
    if len(data) > MAX_EVENT_BYTES:
        raise ValueError("Coverage pilot event exceeds its byte bound")
    fd, name = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum_bytes:
        raise ValueError(f"Unsafe or oversized coverage pilot artifact: {path.name}")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid coverage pilot artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Invalid coverage pilot object: {path.name}")
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Coverage pilot requires a captured UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Coverage pilot timestamp is invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("Coverage pilot timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _verify_digest(value: dict[str, Any], field: str) -> str:
    digest = value.get(field)
    payload = dict(value)
    payload.pop(field, None)
    if not isinstance(digest, str) or digest != _sha256(_canonical(payload)):
        raise ValueError(f"Coverage pilot digest mismatch: {field}")
    return digest


def _read_events(
    events_dir: Path, plan_sha256: str, implementation_sha256: str
) -> list[dict[str, Any]]:
    paths = sorted(events_dir.glob("scan-*.json"), key=lambda item: item.name)
    if len(paths) > MAX_STUDY_SCANS:
        raise ValueError("Coverage pilot event count exceeds its bound")
    events: list[dict[str, Any]] = []
    previous: str | None = None
    for path in paths:
        event = _read_json(path, maximum_bytes=MAX_EVENT_BYTES)
        digest = _verify_digest(event, "event_sha256")
        if (
            event.get("study_id") != STUDY_ID
            or event.get("protocol_version") != VERSION
            or event.get("plan_sha256") != plan_sha256
            or event.get("implementation_sha256") != implementation_sha256
            or event.get("scan_id") != path.stem
            or event.get("previous_event_sha256") != previous
        ):
            raise ValueError(f"Coverage pilot event lineage mismatch: {path.name}")
        previous = digest
        events.append(event)
    return events


def _analysis_event(
    root: Path, scan_id: str, snapshot: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    path = root / "analysis-events" / "v4" / f"{scan_id}.json"
    event = _read_json(path, maximum_bytes=2 * 1024 * 1024)
    _verify_digest(event, "analysis_event_sha256")
    if (
        event.get("analysis_version") != "veritas-finalized-snapshot-analysis-v4"
        or event.get("scan_id") != scan_id
        or event.get("snapshot_evidence_sha256") != snapshot.get("snapshot_evidence_sha256")
    ):
        raise ValueError("Coverage pilot source-analysis event does not match its snapshot")
    rows = event.get("market_rows")
    observations = snapshot.get("market_observations")
    if not isinstance(rows, list) or not isinstance(observations, list):
        raise ValueError("Coverage pilot source-analysis rows are missing")
    by_id = {str(row.get("market_id")): row for row in rows if isinstance(row, dict)}
    if len(by_id) != len(rows) or len(by_id) != len(observations):
        raise ValueError("Coverage pilot source-analysis market rows are not one-to-one")
    for row in observations:
        market_id = str(row.get("market_id") or "")
        source = by_id.get(market_id)
        if (
            source is None
            or bool(source.get("valid")) != bool(row.get("audit", {}).get("valid"))
            or str(source.get("cohort_role")) != str(row.get("cohort_role"))
        ):
            raise ValueError("Coverage pilot source-analysis market row disagrees with snapshot")
    if int(event.get("attempted_market_pairs", -1)) != len(observations):
        raise ValueError("Coverage pilot source-analysis denominator mismatch")
    if int(event.get("valid_quality_pairs", -1)) != sum(bool(row.get("valid")) for row in rows):
        raise ValueError("Coverage pilot source-analysis numerator mismatch")
    return event, _sha256(path.read_bytes())


def _build_event(
    root: Path,
    report: dict[str, Any],
    *,
    plan_sha256: str,
    implementation_sha256: str,
    previous_event_sha256: str | None,
) -> dict[str, Any]:
    scan_id = str(report.get("scan_id") or "")
    snapshot_name = str(report.get("snapshot_file") or "")
    snapshot_relative = Path(snapshot_name)
    if snapshot_relative.is_absolute() or ".." in snapshot_relative.parts:
        raise ValueError("Coverage pilot snapshot path is not relative to the observatory root")
    snapshot_path = root / snapshot_relative
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise ValueError("Coverage pilot finalized snapshot is missing or unsafe")
    snapshot_sha256 = _sha256(snapshot_path.read_bytes())
    source_event, source_event_file_sha256 = _analysis_event(root, scan_id, report)
    selected = report.get("selection", {}).get("selected_markets")
    observations = report.get("market_observations")
    if not isinstance(selected, list) or not isinstance(observations, list):
        raise ValueError("Coverage pilot snapshot selection or observations are missing")
    selected_by_id = {str(row.get("market_id")): row for row in selected if isinstance(row, dict)}
    if len(selected_by_id) != len(selected) or set(selected_by_id) != {
        str(row.get("market_id")) for row in observations if isinstance(row, dict)
    }:
        raise ValueError("Coverage pilot selection and observed market sets differ")
    analyzed = {str(row["market_id"]): row for row in source_event["market_rows"]}
    market_rows: list[dict[str, Any]] = []
    for observation in observations:
        market_id = str(observation["market_id"])
        selection = selected_by_id[market_id]
        analysis = analyzed[market_id]
        role = str(selection.get("cohort_role") or "unknown")
        market_rows.append(
            {
                "market_id": market_id,
                "cohort_role": role,
                "selection_stratum": str(selection.get("selection_stratum") or "unclassified"),
                "selection_probability": selection.get("selection_probability"),
                "primary_category": str(selection.get("primary_category") or "unknown"),
                "quality_valid": bool(analysis["valid"]),
                "invalid_reason": analysis.get("invalid_reason"),
            }
        )
    role_counts: dict[str, dict[str, Any]] = {}
    for row in market_rows:
        role = row["cohort_role"]
        target = role_counts.setdefault(
            role, {"selected": 0, "quality_valid": 0, "invalid_reasons": {}}
        )
        target["selected"] += 1
        target["quality_valid"] += int(row["quality_valid"])
        if not row["quality_valid"]:
            reason = str(row.get("invalid_reason") or "unknown_invalidity")
            target["invalid_reasons"][reason] = int(target["invalid_reasons"].get(reason, 0)) + 1
    phase_plan = report.get("selection", {}).get("plan", {})
    event: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "protocol_version": VERSION,
        "plan_sha256": plan_sha256,
        "implementation_sha256": implementation_sha256,
        "scan_id": scan_id,
        "captured_at_utc": report.get("captured_at_utc"),
        "snapshot_file": report.get("snapshot_file"),
        "snapshot_file_sha256": snapshot_sha256,
        "snapshot_evidence_sha256": report.get("snapshot_evidence_sha256"),
        "snapshot_source_code_sha256": report.get("source_code_sha256"),
        "analysis_event_file_sha256": source_event_file_sha256,
        "analysis_event_sha256": source_event.get("analysis_event_sha256"),
        "phase": str(phase_plan.get("phase") or "unknown"),
        "selection_sequence": int(phase_plan.get("sequence", 0)),
        "bounded_eligible_markets": int(
            report.get("discovery", {}).get("eligible_pair_markets", 0)
        ),
        "discovered_unique_market_ids": int(
            report.get("discovery", {}).get("unique_market_ids", 0)
        ),
        "excluded_market_ids": int(report.get("discovery", {}).get("excluded_market_ids", 0)),
        "exclusion_reasons": report.get("discovery", {}).get("exclusion_reasons", {}),
        "selected_market_pairs": len(market_rows),
        "quality_valid_pairs": int(source_event["valid_quality_pairs"]),
        "invalid_reasons": source_event.get("counts", {}).get("invalid_reasons", {}),
        "role_counts": role_counts,
        "stable_control_available": int(phase_plan.get("stable_control_available_this_scan", 0)),
        "stable_control_missing": list(phase_plan.get("stable_control_missing_this_scan", [])),
        "rotating_strata": phase_plan.get("rotation_strata", {}),
        "positive_top_gross_pairs": int(source_event.get("positive_top_gross_pairs", 0)),
        "positive_full_depth_gross_by_quantity": source_event.get("counts", {}).get(
            "positive_full_depth_gross_by_quantity", {}
        ),
        "positive_minimum_notional_by_quantity": source_event.get("counts", {}).get(
            "positive_minimum_notional_by_quantity", {}
        ),
        "orders_submitted": False,
        "authenticated_requests": False,
        "previous_event_sha256": previous_event_sha256,
        "market_rows": market_rows,
    }
    event["event_sha256"] = _sha256(_canonical(event))
    return event


def _summarize(
    events: list[dict[str, Any]],
    *,
    status: str,
    completion_reason: str | None,
    start_at: datetime,
    end_at: datetime,
    plan_sha256: str,
    implementation_sha256: str,
    control_cohort_sha256: str | None,
) -> dict[str, Any]:
    selected = sum(int(event["selected_market_pairs"]) for event in events)
    valid = sum(int(event["quality_valid_pairs"]) for event in events)
    by_role: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"selected": 0, "quality_valid": 0, "invalid_reasons": {}}
    )
    by_stratum: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"selected": 0, "quality_valid": 0, "distinct_market_ids": []}
    )
    by_phase: dict[str, dict[str, int]] = defaultdict(
        lambda: {"scans": 0, "selected": 0, "quality_valid": 0}
    )
    markets: dict[str, dict[str, Any]] = {}
    invalid_reasons: Counter[str] = Counter()
    skipped_sequences = 0
    previous_sequence: int | None = None
    for event in events:
        phase = str(event["phase"])
        by_phase[phase]["scans"] += 1
        by_phase[phase]["selected"] += int(event["selected_market_pairs"])
        by_phase[phase]["quality_valid"] += int(event["quality_valid_pairs"])
        sequence = int(event["selection_sequence"])
        if previous_sequence is not None:
            skipped_sequences += max(0, sequence - previous_sequence - 1)
        previous_sequence = sequence
        for reason, count in event.get("invalid_reasons", {}).items():
            invalid_reasons[str(reason)] += int(count)
        for row in event["market_rows"]:
            market_id = str(row["market_id"])
            role = str(row["cohort_role"])
            stratum = str(row["selection_stratum"])
            role_row = by_role[role]
            role_row["selected"] += 1
            role_row["quality_valid"] += int(row["quality_valid"])
            if not row["quality_valid"]:
                reason = str(row.get("invalid_reason") or "unknown_invalidity")
                role_row["invalid_reasons"][reason] = (
                    int(role_row["invalid_reasons"].get(reason, 0)) + 1
                )
            stratum_row = by_stratum[stratum]
            stratum_row["selected"] += 1
            stratum_row["quality_valid"] += int(row["quality_valid"])
            ids = set(stratum_row["distinct_market_ids"])
            ids.add(market_id)
            stratum_row["distinct_market_ids"] = sorted(ids)
            market = markets.setdefault(market_id, {"selected": 0, "quality_valid": 0, "roles": {}})
            market["selected"] += 1
            market["quality_valid"] += int(row["quality_valid"])
            market["roles"][role] = int(market["roles"].get(role, 0)) + 1
    for row in by_stratum.values():
        row["distinct_market_count"] = len(row["distinct_market_ids"])
        del row["distinct_market_ids"]
        row["quality_valid_yield"] = (
            row["quality_valid"] / row["selected"] if row["selected"] else None
        )
    for row in by_role.values():
        row["quality_valid_yield"] = (
            row["quality_valid"] / row["selected"] if row["selected"] else None
        )
    rows = [
        {
            "scan_id": event["scan_id"],
            "captured_at_utc": event["captured_at_utc"],
            "selection_sequence": event["selection_sequence"],
            "phase": event["phase"],
            "selected_market_pairs": event["selected_market_pairs"],
            "quality_valid_pairs": event["quality_valid_pairs"],
            "stable_control_available": event["stable_control_available"],
            "stable_control_missing_count": len(event["stable_control_missing"]),
            "discovered_unique_market_ids": event["discovered_unique_market_ids"],
            "bounded_eligible_markets": event["bounded_eligible_markets"],
            "positive_top_gross_pairs": event["positive_top_gross_pairs"],
        }
        for event in events
    ]
    summary: dict[str, Any] = {
        "schema_version": 1,
        "study_id": STUDY_ID,
        "protocol_version": VERSION,
        "status": status,
        "completion_reason": completion_reason,
        "started_at_utc": start_at.isoformat(),
        "ends_at_utc": end_at.isoformat(),
        "maximum_elapsed_hours": 24,
        "maximum_completed_scans": MAX_STUDY_SCANS,
        "completed_scans": len(events),
        "selected_market_pair_slots": selected,
        "quality_valid_pairs": valid,
        "invalid_pairs": selected - valid,
        "quality_valid_yield": valid / selected if selected else None,
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "distinct_selected_market_ids": len(markets),
        "markets": markets,
        "by_cohort_role": dict(sorted(by_role.items())),
        "by_selection_stratum": dict(sorted(by_stratum.items())),
        "by_phase": dict(sorted(by_phase.items())),
        "skipped_scan_sequences": skipped_sequences,
        "scans": rows,
        "source_lineage": {
            "first_scan_id": events[0]["scan_id"] if events else None,
            "last_scan_id": events[-1]["scan_id"] if events else None,
            "plan_sha256": plan_sha256,
            "implementation_sha256": implementation_sha256,
            "control_cohort_sha256": control_cohort_sha256,
        },
        "comparison_interpretation": "same-scan control versus rotating yield is descriptive and non-randomized; no causal or venue-wide inference",
        "orders_submitted": False,
        "authenticated_requests": False,
        "limitations": _PLAN["limitations"],
    }
    summary["summary_sha256"] = _sha256(_canonical(summary))
    return summary


def record_coverage_pilot(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Persist one source-verified scan and return the bounded current summary."""
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("Coverage pilot root cannot be a symlink")
    root = root.resolve()
    pilot_parent = root / "measurement-pilots"
    if pilot_parent.is_symlink():
        raise ValueError("Coverage pilot parent directory cannot be a symlink")
    pilot_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    study_root = root / "measurement-pilots" / STUDY_ID
    events_dir = study_root / "events"
    if study_root.is_symlink():
        raise ValueError("Coverage pilot study directory cannot be a symlink")
    study_root.mkdir(mode=0o700, exist_ok=True)
    if events_dir.is_symlink():
        raise ValueError("Coverage pilot event directory cannot be a symlink")
    events_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if study_root.is_symlink() or events_dir.is_symlink():
        raise ValueError("Coverage pilot output path cannot be a symlink")
    plan = build_plan()
    plan_sha256 = _sha256(_canonical(plan))
    implementation_sha256 = _code_sha256()
    plan_path = study_root / "plan.json"
    if plan_path.exists():
        saved_plan = _read_json(plan_path, maximum_bytes=MAX_EVENT_BYTES)
        saved_hash = saved_plan.pop("plan_sha256", None)
        if saved_hash != plan_sha256 or saved_plan != plan:
            raise ValueError("Persisted coverage pilot plan differs from the frozen protocol")
    else:
        _atomic_json(plan_path, {**plan, "plan_sha256": plan_sha256}, maximum_bytes=MAX_EVENT_BYTES)

    scan_id = str(report.get("scan_id") or "")
    if not scan_id.startswith("scan-"):
        raise ValueError("Coverage pilot requires a finalized scan identity")
    captured_at = _timestamp(report.get("captured_at_utc"))
    state_path = study_root / "state.json"
    if state_path.exists():
        state = _read_json(state_path, maximum_bytes=MAX_STATE_BYTES)
        if (
            state.get("study_id") != STUDY_ID
            or state.get("protocol_version") != VERSION
            or state.get("plan_sha256") != plan_sha256
            or state.get("implementation_sha256") != implementation_sha256
        ):
            raise ValueError("Coverage pilot state does not match the frozen protocol or code")
        start_at = _timestamp(state.get("started_at_utc"))
        end_at = _timestamp(state.get("ends_at_utc"))
        control_cohort_sha256 = state.get("control_cohort_sha256")
        status = str(state.get("status"))
        completion_reason = state.get("completion_reason")
    else:
        start_at = captured_at
        end_at = start_at + timedelta(seconds=MAX_STUDY_SECONDS)
        control_path = root / "control-cohort.json"
        control_cohort_sha256 = (
            _sha256(control_path.read_bytes()) if control_path.is_file() else None
        )
        status = "running"
        completion_reason = None
        state = {
            "schema_version": 1,
            "study_id": STUDY_ID,
            "protocol_version": VERSION,
            "plan_sha256": plan_sha256,
            "implementation_sha256": implementation_sha256,
            "started_at_utc": start_at.isoformat(),
            "started_by_scan_id": scan_id,
            "ends_at_utc": end_at.isoformat(),
            "control_cohort_sha256": control_cohort_sha256,
            "status": status,
            "completion_reason": None,
        }
        # Persist the enrollment boundary before writing its first event so a
        # crash can recover the same start time from immutable scan evidence.
        _atomic_json(state_path, state, maximum_bytes=MAX_STATE_BYTES)

    events = _read_events(events_dir, plan_sha256, implementation_sha256)
    event_path = events_dir / f"{scan_id}.json"
    already_recorded = next((event for event in events if event.get("scan_id") == scan_id), None)
    if status == "running" and captured_at > end_at:
        status = "completed"
        completion_reason = "fixed_24_hour_window_elapsed"
    elif status == "running" and len(events) < MAX_STUDY_SCANS:
        if already_recorded is None:
            previous_digest = events[-1]["event_sha256"] if events else None
            event = _build_event(
                root,
                report,
                plan_sha256=plan_sha256,
                implementation_sha256=implementation_sha256,
                previous_event_sha256=previous_digest,
            )
            if not _write_event(event_path, event):
                existing = _read_json(event_path, maximum_bytes=MAX_EVENT_BYTES)
                _verify_digest(existing, "event_sha256")
                if existing != event:
                    raise ValueError("Duplicate scan has conflicting coverage pilot evidence")
            events = _read_events(events_dir, plan_sha256, implementation_sha256)
        if len(events) >= MAX_STUDY_SCANS:
            status = "completed"
            completion_reason = "48_scan_cap_reached"
    if status not in {"running", "completed"}:
        raise ValueError("Coverage pilot state has an unsupported status")

    state.update(
        {
            "status": status,
            "completion_reason": completion_reason,
            "processed_scan_ids": [event["scan_id"] for event in events],
            "last_event_sha256": events[-1]["event_sha256"] if events else None,
            "updated_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    summary = _summarize(
        events,
        status=status,
        completion_reason=completion_reason,
        start_at=start_at,
        end_at=end_at,
        plan_sha256=plan_sha256,
        implementation_sha256=implementation_sha256,
        control_cohort_sha256=control_cohort_sha256,
    )
    _atomic_json(state_path, state, maximum_bytes=MAX_STATE_BYTES)
    _atomic_json(study_root / "summary.json", summary, maximum_bytes=MAX_SUMMARY_BYTES)
    return summary
