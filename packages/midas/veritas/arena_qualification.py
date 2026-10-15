"""Bounded Arena job for replaying finalized public opportunity qualifications."""

from __future__ import annotations

import fcntl
import hashlib
import itertools
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field

from midas.arena.artifacts import artifact_path, atomic_json
from midas.core.models import Model

from .continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION
from .economic_experiment import VERSION as ECONOMIC_EXPERIMENT_VERSION
from .economic_experiment import compare_qualification_rules

MAX_EVENTS = 512
MAX_SOURCE_BYTES = 64 * 1024**2
MAX_EVENT_BYTES = 2 * 1024**2
MAX_EVENT_CATALOG_FILES = 10_000
SCAN_ID = re.compile(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}\Z")


class VeritasQualificationSpec(Model):
    version: Literal["veritas-arena-qualification-v1"] = "veritas-arena-qualification-v1"
    expected_latest_scan_id: str = Field(pattern=r"^scan-\d{8}T\d{6}Z-[0-9a-f]{12}$")
    max_events: int = Field(default=MAX_EVENTS, ge=1, le=MAX_EVENTS)
    max_source_bytes: int = Field(default=MAX_SOURCE_BYTES, ge=1, le=MAX_SOURCE_BYTES)
    quantity: Literal["20"] = "20"


def run_qualification(
    arena_root: Path,
    spec: VeritasQualificationSpec,
    progress: Any = None,
    *,
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Read only finalized v4 analysis events and persist a deterministic Arena finding."""
    repository = Path(__file__).resolve().parents[3]
    data_root = source_root or repository / "data" / "veritas-observatory"
    if data_root.is_symlink():
        raise ValueError("Veritas qualification source root cannot be a symlink")
    analysis_events_root = data_root / "analysis-events"
    if analysis_events_root.is_symlink():
        raise ValueError("Veritas finalized analysis event root cannot be a symlink")
    event_dir = data_root / "analysis-events" / "v4"
    if event_dir.is_symlink() or not event_dir.is_dir():
        raise ValueError("Finalized Veritas v4 analysis events are unavailable")
    paths = list(itertools.islice(event_dir.glob("scan-*.json"), MAX_EVENT_CATALOG_FILES + 1))
    if len(paths) > MAX_EVENT_CATALOG_FILES:
        raise ValueError("Finalized Veritas event catalog exceeds the file-count bound")
    paths.sort(key=lambda path: path.name)
    selected_paths: list[Path] = []
    for path in paths:
        if path.is_symlink():
            raise ValueError(f"Unsafe Veritas analysis event: {path.name}")
        selected_paths.append(path)
        if path.stem == spec.expected_latest_scan_id:
            break
    if not selected_paths or selected_paths[-1].stem != spec.expected_latest_scan_id:
        raise ValueError("Expected finalized Veritas scan is not indexed by v4 analysis")
    if len(selected_paths) > spec.max_events:
        raise ValueError("Finalized Veritas event count exceeds the Arena job bound")
    source_bytes = 0
    for path in selected_paths:
        size = path.stat().st_size
        if size > MAX_EVENT_BYTES:
            raise ValueError(f"Veritas analysis event exceeds its byte bound: {path.name}")
        source_bytes += size
        if source_bytes > spec.max_source_bytes:
            raise ValueError("Finalized Veritas analysis events exceed the Arena source-byte bound")

    phase = getattr(progress, "phase", None)
    if phase:
        phase("Validating finalized Veritas snapshot events")
    events: list[dict[str, Any]] = []
    for index, path in enumerate(selected_paths, start=1):
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or value.get("scan_id") != path.stem:
            raise ValueError(f"Invalid finalized Veritas event identity: {path.name}")
        events.append(value)
        if progress:
            progress(index, len(selected_paths))

    result = compare_qualification_rules(events, quantity=spec.quantity)
    source_code_sha256 = result["experiment_source_code_sha256"]
    identity_hash = hashlib.sha256(
        f"{result['dataset_sha256']}:{source_code_sha256}".encode()
    ).hexdigest()[:16]
    identity = f"veritas-qualification-v1-{identity_hash}"
    directory = artifact_path(arena_root, "findings", identity)
    manifest_path = directory / "manifest.json"
    if directory.is_symlink() or manifest_path.is_symlink():
        raise ValueError("Arena qualification artifact path cannot be a symlink")
    arena_root.mkdir(parents=True, exist_ok=True)
    findings_root = arena_root / "findings"
    if arena_root.is_symlink() or findings_root.is_symlink():
        raise ValueError("Arena qualification output root cannot be a symlink")
    lock_path = arena_root / "veritas-qualification.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if manifest_path.exists():
            if manifest_path.stat().st_size > 2 * 1024**2:
                raise ValueError("Existing Arena qualification artifact exceeds its byte bound")
            existing = json.loads(manifest_path.read_text())
            existing_result = existing.get("result")
            if not isinstance(existing_result, dict):
                raise ValueError("Existing Arena qualification artifact is malformed")
            existing_payload = dict(existing_result)
            claimed_digest = existing_payload.pop("experiment_sha256", None)
            calculated_digest = hashlib.sha256(
                json.dumps(
                    existing_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            if (
                existing.get("artifact_id") != identity
                or existing.get("experiment_sha256") != result["experiment_sha256"]
                or claimed_digest != calculated_digest
                or calculated_digest != result["experiment_sha256"]
            ):
                raise ValueError("Existing Arena qualification artifact differs for this identity")
            return cast(dict[str, Any], existing)
        manifest = {
            "artifact_id": identity,
            "artifact_type": "veritas_public_opportunity_qualification",
            "artifact_version": "veritas-arena-qualification-v1",
            "analysis_version": SNAPSHOT_ANALYSIS_VERSION,
            "economic_experiment_version": ECONOMIC_EXPERIMENT_VERSION,
            "expected_latest_scan_id": spec.expected_latest_scan_id,
            "source_event_count": len(events),
            "source_bytes": source_bytes,
            "source_root": str(data_root.resolve()),
            "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "orders_submitted": False,
            "authenticated_requests": False,
            "result": result,
            "experiment_sha256": result["experiment_sha256"],
        }
        atomic_json(manifest_path, manifest)
    register = getattr(progress, "register", None)
    if register:
        register("findings", identity)
    return manifest
