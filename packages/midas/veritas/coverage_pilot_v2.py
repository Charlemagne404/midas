"""Versioned prospective measurement-yield pilot with a narrow code pin.

This study reuses the v1 event and summary primitives, but owns a separate
plan, state directory, event chain, and protocol identity. Its implementation
pin covers only this module and the v1 helper module. Observer, fee-model, and
continuous-analysis changes are recorded per scan through their source hashes
and do not invalidate the pilot protocol.
"""

from __future__ import annotations

import copy
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import coverage_pilot as _shared

VERSION = "veritas-coverage-pilot-v2"
STUDY_ID = "VERITAS-M2-COVERAGE-PILOT-002"
MAX_STUDY_SECONDS = _shared.MAX_STUDY_SECONDS
MAX_STUDY_SCANS = _shared.MAX_STUDY_SCANS
MAX_EVENT_BYTES = _shared.MAX_EVENT_BYTES
MAX_STATE_BYTES = _shared.MAX_STATE_BYTES
MAX_SUMMARY_BYTES = _shared.MAX_SUMMARY_BYTES

_LIMITATIONS = [
    "The bounded Gamma query-response union is selected and is not the venue-wide universe.",
    "Stable controls were frozen from an earlier bounded discovery union and are not randomized against rotating markets.",
    "The same-scan role comparison is descriptive; market composition and availability differ by role.",
    "Intermittent public snapshots do not establish continuous coverage, quote lifetime, fills, or profitability.",
    "Reported update timestamps do not establish venue sequence freshness, upstream queue age, or batch atomicity.",
    "Repeated market and scan observations are dependent and are not independent trials.",
]


def build_plan() -> dict[str, Any]:
    """Return the frozen v2 protocol; v1's historical plan remains untouched."""
    plan = copy.deepcopy(_shared.build_plan())
    plan["study_id"] = STUDY_ID
    plan["protocol_version"] = VERSION
    plan["implementation_pin"] = {
        "files": ["coverage_pilot_v2.py", "coverage_pilot.py"],
        "scope": "v2 protocol and the shared immutable event/summary primitives",
        "excluded_from_implementation_pin": [
            "observatory.py",
            "continuous_analysis.py",
            "opportunity_audit.py",
            "economic_feasibility_v3.py",
        ],
        "per_scan_source_evidence": [
            "snapshot_source_code_sha256",
            "analysis_event_file_sha256",
            "analysis_event_sha256",
            "analysis_source_code_sha256",
        ],
    }
    plan["primary_outcome"]["secondary_measurements"] = [
        "strict reported-age freshness sensitivity from the finalized v4 analysis event",
        "reported cross-outcome timestamp skew",
        "verified batch atomicity and venue sequence counts",
    ]
    plan["limitations"] = list(_LIMITATIONS)
    return plan


def _canonical(value: Any) -> bytes:
    return _shared._canonical(value)


def _sha256(value: bytes) -> str:
    return _shared._sha256(value)


def _implementation_files() -> dict[str, str]:
    module_dir = Path(__file__).resolve().parent
    paths = {
        "coverage_pilot.py": module_dir / "coverage_pilot.py",
        "coverage_pilot_v2.py": Path(__file__).resolve(),
    }
    result: dict[str, str] = {}
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Coverage pilot v2 implementation file is unavailable: {name}")
        result[name] = _sha256(path.read_bytes())
    return result


def _implementation_sha256(files: dict[str, str]) -> str:
    return _sha256(_canonical(files))


def _read_events(
    events_dir: Path, plan_sha256: str, implementation_sha256: str
) -> list[dict[str, Any]]:
    paths = sorted(events_dir.glob("scan-*.json"), key=lambda item: item.name)
    if len(paths) > MAX_STUDY_SCANS:
        raise ValueError("Coverage pilot v2 event count exceeds its bound")
    events: list[dict[str, Any]] = []
    previous: str | None = None
    for path in paths:
        event = _shared._read_json(path, maximum_bytes=MAX_EVENT_BYTES)
        digest = _shared._verify_digest(event, "event_sha256")
        if (
            event.get("study_id") != STUDY_ID
            or event.get("protocol_version") != VERSION
            or event.get("plan_sha256") != plan_sha256
            or event.get("implementation_sha256") != implementation_sha256
            or event.get("scan_id") != path.stem
            or event.get("previous_event_sha256") != previous
        ):
            raise ValueError(f"Coverage pilot v2 event lineage mismatch: {path.name}")
        previous = digest
        events.append(event)
    return events


def _build_event(
    root: Path,
    report: dict[str, Any],
    *,
    plan_sha256: str,
    implementation_sha256: str,
    previous_event_sha256: str | None,
) -> dict[str, Any]:
    event = _shared._build_event(
        root,
        report,
        plan_sha256=plan_sha256,
        implementation_sha256=implementation_sha256,
        previous_event_sha256=previous_event_sha256,
    )
    analysis, analysis_file_sha256 = _shared._analysis_event(
        root, str(report.get("scan_id") or ""), report
    )
    if event.get("analysis_event_file_sha256") != analysis_file_sha256:
        raise ValueError("Coverage pilot v2 analysis event digest changed during read")
    counts = report.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    observations = report.get("market_observations")
    observations = observations if isinstance(observations, list) else []
    atomicity_verified = 0
    sequence_verified = 0
    for row in observations:
        if not isinstance(row, dict):
            continue
        audit = row.get("audit")
        quality = audit.get("quality") if isinstance(audit, dict) else None
        if not isinstance(quality, dict):
            continue
        atomicity_verified += int(quality.get("batch_atomicity_verified") is True)
        sequence_verified += int(quality.get("sequence_verified") is True)

    event.update(
        {
            "study_id": STUDY_ID,
            "protocol_version": VERSION,
            "implementation_sha256": implementation_sha256,
            "implementation_files": _implementation_files(),
            "analysis_source_code_sha256": analysis.get("analysis_source_code_sha256"),
            "measurement_diagnostics": {
                "strict_reported_fresh_pairs": int(analysis.get("legacy_freshness_valid_pairs", 0)),
                "reported_update_age_above_5s_by_leg": counts.get(
                    "reported_update_age_above_5s_by_leg", {}
                ),
                "reported_update_age_bands_by_leg": counts.get(
                    "reported_update_age_bands_by_leg", {}
                ),
                "reported_update_timestamp_skew_above_250ms_pairs": int(
                    counts.get("reported_update_timestamp_skew_above_250ms_pairs", 0)
                ),
                "reported_update_timestamp_skew_bands": counts.get(
                    "reported_update_timestamp_skew_bands", {}
                ),
                "batch_atomicity_verified_pairs": atomicity_verified,
                "sequence_verified_pairs": sequence_verified,
            },
        }
    )
    event["event_sha256"] = _sha256(
        _canonical({k: v for k, v in event.items() if k != "event_sha256"})
    )
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
    implementation_files: dict[str, str],
    control_cohort_sha256: str | None,
) -> dict[str, Any]:
    summary = _shared._summarize(
        events,
        status=status,
        completion_reason=completion_reason,
        start_at=start_at,
        end_at=end_at,
        plan_sha256=plan_sha256,
        implementation_sha256=implementation_sha256,
        control_cohort_sha256=control_cohort_sha256,
    )
    summary["study_id"] = STUDY_ID
    summary["protocol_version"] = VERSION
    summary["limitations"] = list(_LIMITATIONS)
    age_above_5s: Counter[str] = Counter()
    skew_bands: Counter[str] = Counter()
    strict_fresh = 0
    skew_above_250ms = 0
    atomicity_verified = 0
    sequence_verified = 0
    for event in events:
        diagnostics = event.get("measurement_diagnostics", {})
        if not isinstance(diagnostics, dict):
            continue
        strict_fresh += int(diagnostics.get("strict_reported_fresh_pairs", 0))
        skew_above_250ms += int(
            diagnostics.get("reported_update_timestamp_skew_above_250ms_pairs", 0)
        )
        atomicity_verified += int(diagnostics.get("batch_atomicity_verified_pairs", 0))
        sequence_verified += int(diagnostics.get("sequence_verified_pairs", 0))
        by_leg = diagnostics.get("reported_update_age_above_5s_by_leg", {})
        if isinstance(by_leg, dict):
            for side, count in by_leg.items():
                age_above_5s[str(side)] += int(count)
        bands = diagnostics.get("reported_update_timestamp_skew_bands", {})
        if isinstance(bands, dict):
            for band, count in bands.items():
                skew_bands[str(band)] += int(count)
    summary["measurement_diagnostics"] = {
        "strict_reported_fresh_pairs": strict_fresh,
        "reported_update_age_above_5s_by_leg": dict(sorted(age_above_5s.items())),
        "reported_update_timestamp_skew_above_250ms_pairs": skew_above_250ms,
        "reported_update_timestamp_skew_bands": dict(sorted(skew_bands.items())),
        "batch_atomicity_verified_pairs": atomicity_verified,
        "sequence_verified_pairs": sequence_verified,
    }
    summary["implementation_files"] = implementation_files
    summary["source_lineage"]["implementation_files"] = implementation_files
    summary.pop("summary_sha256", None)
    summary["summary_sha256"] = _sha256(_canonical(summary))
    return summary


def record_coverage_pilot_v2(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Record one prospective scan under an isolated v2 study identity."""
    root = root.expanduser()
    if root.is_symlink():
        raise ValueError("Coverage pilot v2 root cannot be a symlink")
    root = root.resolve()
    pilot_parent = root / "measurement-pilots"
    if pilot_parent.is_symlink():
        raise ValueError("Coverage pilot v2 parent cannot be a symlink")
    pilot_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    study_root = pilot_parent / STUDY_ID
    events_dir = study_root / "events"
    if study_root.is_symlink():
        raise ValueError("Coverage pilot v2 study directory cannot be a symlink")
    study_root.mkdir(mode=0o700, exist_ok=True)
    if events_dir.is_symlink():
        raise ValueError("Coverage pilot v2 event directory cannot be a symlink")
    events_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if study_root.is_symlink() or events_dir.is_symlink():
        raise ValueError("Coverage pilot v2 output path cannot be a symlink")

    plan = build_plan()
    plan_sha256 = _sha256(_canonical(plan))
    implementation_files = _implementation_files()
    implementation_sha256 = _implementation_sha256(implementation_files)
    plan_path = study_root / "plan.json"
    if plan_path.exists():
        saved_plan = _shared._read_json(plan_path, maximum_bytes=MAX_EVENT_BYTES)
        saved_hash = saved_plan.pop("plan_sha256", None)
        if saved_hash != plan_sha256 or saved_plan != plan:
            raise ValueError("Persisted coverage pilot v2 plan differs from frozen protocol")
    else:
        _shared._atomic_json(
            plan_path, {**plan, "plan_sha256": plan_sha256}, maximum_bytes=MAX_EVENT_BYTES
        )

    scan_id = str(report.get("scan_id") or "")
    if not scan_id.startswith("scan-"):
        raise ValueError("Coverage pilot v2 requires a finalized scan identity")
    captured_at = _shared._timestamp(report.get("captured_at_utc"))
    state_path = study_root / "state.json"
    if state_path.exists():
        state = _shared._read_json(state_path, maximum_bytes=MAX_STATE_BYTES)
        if (
            state.get("study_id") != STUDY_ID
            or state.get("protocol_version") != VERSION
            or state.get("plan_sha256") != plan_sha256
            or state.get("implementation_sha256") != implementation_sha256
            or state.get("implementation_files") != implementation_files
        ):
            raise ValueError("Coverage pilot v2 state does not match frozen protocol or code")
        start_at = _shared._timestamp(state.get("started_at_utc"))
        end_at = _shared._timestamp(state.get("ends_at_utc"))
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
            "implementation_files": implementation_files,
            "started_at_utc": start_at.isoformat(),
            "started_by_scan_id": scan_id,
            "ends_at_utc": end_at.isoformat(),
            "control_cohort_sha256": control_cohort_sha256,
            "status": status,
            "completion_reason": None,
        }
        _shared._atomic_json(state_path, state, maximum_bytes=MAX_STATE_BYTES)

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
            if not _shared._write_event(event_path, event):
                existing = _shared._read_json(event_path, maximum_bytes=MAX_EVENT_BYTES)
                _shared._verify_digest(existing, "event_sha256")
                if existing != event:
                    raise ValueError("Duplicate v2 scan has conflicting coverage evidence")
            events = _read_events(events_dir, plan_sha256, implementation_sha256)
        else:
            if already_recorded.get("snapshot_evidence_sha256") != report.get(
                "snapshot_evidence_sha256"
            ):
                raise ValueError("Duplicate v2 scan has conflicting snapshot evidence")
        if len(events) >= MAX_STUDY_SCANS:
            status = "completed"
            completion_reason = "48_scan_cap_reached"
    if status not in {"running", "completed"}:
        raise ValueError("Coverage pilot v2 state has an unsupported status")

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
        implementation_files=implementation_files,
        control_cohort_sha256=control_cohort_sha256,
    )
    _shared._atomic_json(state_path, state, maximum_bytes=MAX_STATE_BYTES)
    _shared._atomic_json(study_root / "summary.json", summary, maximum_bytes=MAX_SUMMARY_BYTES)
    return summary
