"""Replay stored Gamma frames to quantify the marginal discovery value of each.

The analysis uses immutable public response payloads. It reports counts only;
it does not write to the observatory, request new market data, or qualify an
economic candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from typing import Any

from .observatory import _identity_fields
from .opportunity_audit import normalize_market

ANALYSIS_VERSION = "veritas-discovery-frame-marginal-v1"
EXPECTED_FRAME_COUNT = 6


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _decode_pages(
    pages: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]], set[str]]:
    if len(pages) != EXPECTED_FRAME_COUNT:
        raise ValueError(f"Expected exactly {EXPECTED_FRAME_COUNT} Gamma frames")
    rows_by_frame: dict[str, list[dict[str, Any]]] = {}
    ids_by_frame: dict[str, set[str]] = {}
    rows_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page in pages:
        frame = page.get("query_id")
        payload = page.get("response_payload")
        if not isinstance(frame, str) or not frame or frame in rows_by_frame:
            raise ValueError("Gamma frame names must be present and unique")
        if not isinstance(payload, str):
            raise ValueError("Gamma frame is missing its retained response payload")
        body = payload.encode("utf-8")
        if _sha256(body) != page.get("response_sha256"):
            raise ValueError("Gamma response payload digest mismatch")
        if page.get("response_bytes") != len(body):
            raise ValueError("Gamma response byte count mismatch")
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError("Gamma response payload is not valid JSON") from error
        if not isinstance(decoded, list) or any(not isinstance(row, dict) for row in decoded):
            raise ValueError("Gamma response payload must be an array of market objects")
        if page.get("candidate_count") != len(decoded):
            raise ValueError("Gamma frame candidate count mismatch")
        rows_by_frame[frame] = decoded
        ids: set[str] = set()
        for row in decoded:
            raw_id = row.get("id")
            if raw_id is None or not str(raw_id):
                continue
            market_id = str(raw_id)
            ids.add(market_id)
            rows_by_id[market_id].append(row)
        ids_by_frame[frame] = ids

    conflicts = {
        market_id
        for market_id, rows in rows_by_id.items()
        if any(_identity_fields(rows[0]) != _identity_fields(row) for row in rows[1:])
    }
    return rows_by_frame, ids_by_frame, conflicts


def _eligible_ids(rows: dict[str, dict[str, Any]], conflicts: set[str]) -> set[str]:
    eligible: set[str] = set()
    for market_id, raw in rows.items():
        if market_id not in conflicts and normalize_market(raw)[0] is not None:
            eligible.add(market_id)
    return eligible


def analyze_snapshot_frames(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate six raw page receipts and compute leave-one-frame-out counts."""
    rows_by_frame, ids_by_frame, conflicts = _decode_pages(pages)
    rows_by_id: dict[str, dict[str, Any]] = {}
    for page in pages:
        frame = str(page["query_id"])
        for row in rows_by_frame[frame]:
            if row.get("id") is not None:
                rows_by_id.setdefault(str(row["id"]), row)
    all_ids = set().union(*ids_by_frame.values())
    eligible = _eligible_ids(rows_by_id, conflicts)
    marginal: list[dict[str, Any]] = []
    for frame in sorted(ids_by_frame):
        other_frames = [ids for name, ids in ids_by_frame.items() if name != frame]
        remaining = set().union(*other_frames)
        exclusive = ids_by_frame[frame] - remaining
        marginal.append(
            {
                "frame": frame,
                "response_rows": len(rows_by_frame[frame]),
                "unique_ids_exclusive_to_frame": len(exclusive),
                "eligible_ids_exclusive_to_frame": len(exclusive & eligible),
                "unique_ids_if_removed": len(remaining),
                "eligible_ids_if_removed": len(remaining & eligible),
            }
        )
    return {
        "candidate_records": sum(len(rows) for rows in rows_by_frame.values()),
        "unique_ids": len(all_ids),
        "eligible_ids": len(eligible),
        "identity_conflicts": len(conflicts),
        "marginal_by_frame": marginal,
    }


def analyze_control_adjusted_frame_drop(
    pages: list[dict[str, Any]], control_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Sensitivity only: remove one frame, add later direct-control metadata."""
    rows_by_frame, ids_by_frame, conflicts = _decode_pages(pages)
    base_rows: dict[str, dict[str, Any]] = {}
    for frame_rows in rows_by_frame.values():
        for row in frame_rows:
            if row.get("id") is not None:
                base_rows.setdefault(str(row["id"]), row)
    all_ids = set().union(*ids_by_frame.values())
    base_eligible = _eligible_ids(base_rows, conflicts)

    controls_by_id: dict[str, dict[str, Any]] = {}
    for row in control_rows:
        raw_id = row.get("id")
        if raw_id is None or not str(raw_id):
            continue
        market_id = str(raw_id)
        if market_id in controls_by_id:
            raise ValueError("Direct control response contains duplicate market IDs")
        controls_by_id[market_id] = row
    control_ids = set(controls_by_id)
    eligible_controls = _eligible_ids(controls_by_id, set())
    results: list[dict[str, Any]] = []

    for frame in sorted(ids_by_frame):
        remaining_frames = [name for name in rows_by_frame if name != frame]
        remaining_ids = set().union(*(ids_by_frame[name] for name in remaining_frames))
        remaining_rows: dict[str, dict[str, Any]] = {}
        remaining_conflicts: set[str] = set()
        for name in remaining_frames:
            for row in rows_by_frame[name]:
                raw_id = row.get("id")
                if raw_id is None or not str(raw_id):
                    continue
                market_id = str(raw_id)
                prior = remaining_rows.get(market_id)
                if prior is not None and _identity_fields(prior) != _identity_fields(row):
                    remaining_conflicts.add(market_id)
                else:
                    remaining_rows.setdefault(market_id, row)

        for market_id, row in controls_by_id.items():
            prior = remaining_rows.get(market_id)
            if prior is not None and _identity_fields(prior) != _identity_fields(row):
                remaining_conflicts.add(market_id)
            else:
                # Prefer the direct response for control lifecycle metadata.
                remaining_rows[market_id] = row

        remaining_eligible = _eligible_ids(remaining_rows, remaining_conflicts)
        combined_ids = remaining_ids | control_ids
        results.append(
            {
                "frame_removed": frame,
                "frame_unique_ids_lost": len(ids_by_frame[frame] - remaining_ids),
                "frame_eligible_ids_lost": len(
                    (ids_by_frame[frame] - remaining_ids) & base_eligible
                ),
                "five_frame_unique_union": len(remaining_ids),
                "combined_unique_union_with_controls": len(combined_ids),
                "direct_controls_already_in_five_frame_union": len(control_ids & remaining_ids),
                "direct_control_count": len(control_ids),
                "direct_eligible_control_count": len(eligible_controls),
                "combined_eligible_union": len(remaining_eligible),
                "eligible_delta_vs_six_frame_baseline": len(remaining_eligible)
                - len(base_eligible),
            }
        )

    return {
        "six_frame_unique_union": len(all_ids),
        "six_frame_eligible_union": len(base_eligible),
        "direct_control_count": len(control_ids),
        "direct_eligible_control_count": len(eligible_controls),
        "sensitivity_by_removed_frame": results,
        "interpretation_limit": (
            "The direct-control response may be later than the six-frame snapshot; "
            "these counts are a bounded design sensitivity, not an observed scan."
        ),
    }


def summarize_frame_marginals(scan_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize repeated leave-one-frame-out results without exposing IDs."""
    if not scan_results:
        raise ValueError("At least one scan result is required")
    frame_names = {entry["frame"] for entry in scan_results[0]["marginal_by_frame"]}
    if any(
        {entry["frame"] for entry in result["marginal_by_frame"]} != frame_names
        for result in scan_results
    ):
        raise ValueError("Discovery frame set changed within the analyzed panel")

    all_unique = [result["unique_ids"] for result in scan_results]
    all_eligible = [result["eligible_ids"] for result in scan_results]
    per_frame: list[dict[str, Any]] = []
    for frame in sorted(frame_names):
        values = [
            next(entry for entry in result["marginal_by_frame"] if entry["frame"] == frame)
            for result in scan_results
        ]
        unique_lost = [entry["unique_ids_exclusive_to_frame"] for entry in values]
        eligible_lost = [entry["eligible_ids_exclusive_to_frame"] for entry in values]
        ordered = sorted(eligible_lost)
        per_frame.append(
            {
                "frame": frame,
                "scans": len(values),
                "mean_response_rows": round(
                    statistics.mean(entry["response_rows"] for entry in values), 2
                ),
                "mean_unique_ids_lost_if_removed": round(statistics.mean(unique_lost), 2),
                "mean_eligible_ids_lost_if_removed": round(statistics.mean(eligible_lost), 2),
                "median_eligible_ids_lost_if_removed": statistics.median(eligible_lost),
                "p90_eligible_ids_lost_if_removed": ordered[math.ceil(0.9 * len(ordered)) - 1],
                "scans_with_zero_eligible_ids_lost": sum(value == 0 for value in eligible_lost),
            }
        )
    return {
        "scan_count": len(scan_results),
        "mean_six_frame_unique_union": round(statistics.mean(all_unique), 2),
        "mean_six_frame_eligible_union": round(statistics.mean(all_eligible), 2),
        "marginal_by_frame": per_frame,
    }
