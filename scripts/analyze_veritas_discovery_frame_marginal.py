"""Replay saved Gamma responses and compare their marginal coverage."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.veritas.control_retrieval import CONTROL_RETRIEVAL_VERSION
from midas.veritas.discovery_frame_analysis import (
    ANALYSIS_VERSION,
    analyze_control_adjusted_frame_drop,
    analyze_snapshot_frames,
    summarize_frame_marginals,
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_gzip_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Analysis inputs must be regular, non-symlink files")
    value = json.loads(gzip.decompress(path.read_bytes()))
    if not isinstance(value, dict):
        raise ValueError("Compressed analysis input must contain a JSON object")
    return value


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Analysis output must be a new file in a non-symlink directory")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(
                json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"
            )
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


def run_analysis(
    *, root: Path, probe_path: Path, control_path: Path, output_path: Path
) -> dict[str, Any]:
    snapshots_dir = root / "snapshots"
    if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        raise ValueError("Snapshot input must be a real directory")
    paths = sorted(snapshots_dir.glob("*.json.gz"))
    if not paths:
        raise ValueError("No finalized public snapshots were found")

    scan_results: list[dict[str, Any]] = []
    snapshot_manifest: list[dict[str, Any]] = []
    response_manifest: list[dict[str, str]] = []
    latest_pages: list[dict[str, Any]] | None = None
    latest_snapshot: dict[str, Any] | None = None
    total_source_bytes = 0
    seen_scan_ids: set[str] = set()
    for path in paths:
        snapshot = _read_gzip_json(path)
        scan_id = snapshot.get("scan_id")
        if not isinstance(scan_id, str) or scan_id in seen_scan_ids:
            raise ValueError("Finalized snapshot IDs must be present and unique")
        seen_scan_ids.add(scan_id)
        source_requests = snapshot.get("source_requests")
        pages = source_requests.get("gamma_pages") if isinstance(source_requests, dict) else None
        if not isinstance(pages, list):
            raise ValueError("Snapshot is missing retained Gamma pages")
        result = analyze_snapshot_frames(pages)
        scan_results.append(result)
        for page in pages:
            response_manifest.append(
                {
                    "scan_id": scan_id,
                    "query_id": str(page["query_id"]),
                    "response_sha256": str(page["response_sha256"]),
                }
            )
        snapshot_manifest.append(
            {
                "scan_id": scan_id,
                "captured_at_utc": str(snapshot.get("captured_at_utc") or "unknown"),
                "snapshot_evidence_sha256": str(
                    snapshot.get("snapshot_evidence_sha256") or "unknown"
                ),
                "snapshot_file_sha256": _sha256(path.read_bytes()),
            }
        )
        total_source_bytes += path.stat().st_size
        capture_ns = snapshot.get("captured_ns")
        if isinstance(capture_ns, int) and capture_ns > 0:
            if latest_snapshot is None or capture_ns > int(latest_snapshot["captured_ns"]):
                latest_snapshot = snapshot
                latest_pages = pages

    if latest_snapshot is None or latest_pages is None:
        raise ValueError("Snapshots do not provide a comparable capture timestamp")

    probe = _read_gzip_json(probe_path)
    if probe.get("version") != CONTROL_RETRIEVAL_VERSION:
        raise ValueError("Unsupported direct-control probe version")
    if control_path.is_symlink() or not control_path.is_file():
        raise ValueError("Frozen control cohort must be a regular, non-symlink file")
    control_bytes = control_path.read_bytes()
    controls = json.loads(control_bytes)
    if (
        not isinstance(controls, dict)
        or controls.get("version")
        not in {"veritas-control-cohort-v1", "veritas-public-observatory-v1"}
        or not isinstance(controls.get("market_ids"), list)
    ):
        raise ValueError("Frozen control cohort is malformed")
    control_ids = [str(value) for value in controls["market_ids"]]
    if (
        len(control_ids) != 8
        or len(set(control_ids)) != 8
        or any(not market_id.isdecimal() for market_id in control_ids)
    ):
        raise ValueError("Expected the unchanged eight-control cohort")
    if hashlib.sha256(control_bytes).hexdigest() != probe.get("evidence", {}).get(
        "control_cohort_sha256"
    ):
        raise ValueError("Probe cohort digest does not match the frozen cohort file")
    probe_query = probe.get("query")
    if (
        not isinstance(probe_query, dict)
        or probe_query.get("requested_market_count") != len(control_ids)
        or probe_query.get("requested_market_ids_set_sha256")
        != _sha256(_canonical(sorted(control_ids)))
    ):
        raise ValueError("Probe query does not match the frozen control cohort")

    receipt = probe.get("response", {}).get("request_receipt")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("response_payload"), str):
        raise ValueError("Probe is missing its raw Gamma response")
    response_body = receipt["response_payload"].encode()
    if _sha256(response_body) != receipt.get("response_sha256"):
        raise ValueError("Direct-control response digest mismatch")
    control_rows = json.loads(response_body)
    if not isinstance(control_rows, list) or any(not isinstance(row, dict) for row in control_rows):
        raise ValueError("Direct-control response must be an array of market objects")
    returned_ids = [str(row["id"]) for row in control_rows if row.get("id") is not None]
    if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != set(control_ids):
        raise ValueError("Direct-control response must return each frozen control exactly once")

    preceding_scans = [
        snapshot
        for path in paths
        if (snapshot := _read_gzip_json(path)).get("captured_ns", 0)
        <= int(probe.get("captured_at_ns", 0))
    ]
    if not preceding_scans:
        raise ValueError("No saved scan precedes the direct-control probe")
    comparison_snapshot = max(preceding_scans, key=lambda row: int(row.get("captured_ns", 0)))
    comparison_pages = comparison_snapshot["source_requests"]["gamma_pages"]
    response_manifest.sort(key=lambda row: (row["scan_id"], row["query_id"]))
    snapshot_manifest.sort(key=lambda row: row["scan_id"])

    result = {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "experiment_id": "VERITAS-M2-DISCOVERY-FRAME-MARGINAL-001",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "snapshot_count": len(paths),
            "gamma_response_count": len(response_manifest),
            "gamma_response_manifest_sha256": _sha256(_canonical(response_manifest)),
            "snapshot_manifest_sha256": _sha256(_canonical(snapshot_manifest)),
            "compressed_snapshot_bytes": total_source_bytes,
            "all_gamma_response_hashes_verified": True,
            "snapshots": snapshot_manifest,
        },
        "historical_frame_marginals": summarize_frame_marginals(scan_results),
        "control_lookup_sensitivity": {
            "comparison_scan_id": comparison_snapshot["scan_id"],
            "comparison_scan_captured_at_utc": comparison_snapshot["captured_at_utc"],
            "control_probe_captured_at_utc": datetime.fromtimestamp(
                int(probe["captured_at_ns"]) / 1e9, UTC
            ).isoformat(),
            "time_separation_seconds": round(
                (int(probe["captured_at_ns"]) - int(comparison_snapshot["captured_ns"])) / 1e9,
                3,
            ),
            "probe_artifact_sha256": _sha256(probe_path.read_bytes()),
            "control_cohort_sha256": hashlib.sha256(control_bytes).hexdigest(),
            "control_response_sha256": receipt["response_sha256"],
            "control_response_bytes": receipt["response_bytes"],
            "requested_controls": len(control_ids),
            "returned_unique_controls": len(returned_ids),
            "response_matches_control_cohort": True,
            "public_request_count": probe["evidence"]["public_request_count"],
            "http_attempt_count": probe["evidence"]["http_attempt_count"],
            "sensitivity": analyze_control_adjusted_frame_drop(comparison_pages, control_rows),
        },
        "interpretation": {
            "economic_outcomes_measured": False,
            "orders_submitted": False,
            "authenticated_requests": False,
            "live_requests_made_by_this_analysis": 0,
            "conclusion": (
                "All six rotating frames contributed a substantial unique-ID set. "
                "Removing one frame to fund direct control lookup has a measurable "
                "coverage cost; an eighth bounded request is the cleaner successor "
                "design if rate and resource checks remain acceptable."
            ),
            "limitations": [
                "Historical marginal counts describe the existing six-frame query protocol, not venue-wide coverage.",
                "The direct-control response was captured after its comparison snapshot; the combined results are a sensitivity, not a scan observation.",
                "The analysis measures metadata eligibility counts, not book quality, prices, depth, fees, or arbitrage.",
                "The historical snapshots are repeated and dependent observations.",
            ],
        },
    }
    _atomic_json(output_path, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/veritas-observatory"))
    parser.add_argument(
        "--probe-artifact",
        type=Path,
        default=Path(
            "data/veritas-observatory/control-retrieval-probes/"
            "control-retrieval-1792105904766378861.json.gz"
        ),
    )
    parser.add_argument(
        "--control-file", type=Path, default=Path("data/veritas-observatory/control-cohort.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/VERITAS_MISSION2_DISCOVERY_FRAME_MARGINAL_001.json"),
    )
    args = parser.parse_args()
    analysis = run_analysis(
        root=args.root,
        probe_path=args.probe_artifact,
        control_path=args.control_file,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "experiment_id": analysis["experiment_id"],
                "output_path": str(args.output),
                "snapshot_count": analysis["source"]["snapshot_count"],
                "gamma_response_count": analysis["source"]["gamma_response_count"],
                "historical_frame_marginals": analysis["historical_frame_marginals"],
                "control_lookup_sensitivity": analysis["control_lookup_sensitivity"]["sensitivity"],
                "orders_submitted": False,
            },
            sort_keys=True,
        )
    )
