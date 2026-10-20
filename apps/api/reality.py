"""Read-only, bounded Reality evidence API. No collector or research writer ownership."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import subprocess
import time
import zlib
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from midas.reality.shadow_report import report
from midas.reality.storage import MAGIC

CALIBRATION = "8e29bed2af533d3e2ee1640c5c9e876d3323480d8b2d579b454b6c9768aa2500"
TRAINING = "9f593b0e68c61c5a8eabf3b01b7ad38c9e1df27436bd041a55a505c995a0a9f9"


def classify_collector_health(status: dict[str, Any], now_ns: int) -> tuple[str, list[str]]:
    """Classify current capture health without treating lifetime failures as active faults."""
    if not status:
        return "unavailable", ["status_unavailable"]
    if status.get("state") == "STOPPED":
        return "paused", []

    reasons: list[str] = []
    updated_ns = status.get("updated_ns")
    if not isinstance(updated_ns, int) or now_ns - updated_ns > 30 * 1_000_000_000:
        reasons.append("status_stale")

    state = status.get("state")
    if state != "RECORDING_UNSEQUENCED":
        reasons.append("collector_state")

    config = status.get("config")
    stale_seconds = config.get("stale_seconds", 60) if isinstance(config, dict) else 60
    if not isinstance(stale_seconds, (int, float)) or stale_seconds <= 0:
        stale_seconds = 60
    last_observation_ns = status.get("last_observation_ns")
    if not isinstance(last_observation_ns, int):
        reasons.append("observations_missing")
    elif now_ns - last_observation_ns >= stale_seconds * 1_000_000_000:
        reasons.append("observations_stale")

    if status.get("backpressure_active"):
        reasons.append("backpressured")
    return ("degraded" if reasons else "recording"), reasons


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    if path.stat().st_size > 8_000_000:
        raise ValueError("Evidence file exceeds interface bound")
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def router(workspace: Path) -> APIRouter:
    routes = APIRouter(prefix="/api/reality", tags=["Reality public observation research"])
    raw = workspace / "data/recordings/reality"
    research = workspace / "data/research/reality"
    forward = research / "forward/mission2"
    cache: dict[str, tuple[float, Any]] = {}

    def database() -> sqlite3.Connection:
        path = forward / "shadow.sqlite"
        if not path.exists():
            raise HTTPException(404, "No prospective journal available yet")
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=1)
        db.execute("pragma query_only=on")
        deadline = time.monotonic() + 2
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        return db

    def artifact_paths() -> dict[str, Path]:
        return {
            "dataset": research
            / "datasets/23201960592577e4cb280c5f3dc1fb64d75e3b12bacb45d347cc2ae32472242c/manifest.json",
            "calibration": research / f"calibration/{CALIBRATION}.json",
            "training": research / f"training/runs/{TRAINING}/report.json",
            "campaign": forward / "campaign.json",
            "integrity": forward / "integrity.json",
            "capacity": workspace / "data/recordings/capacity.json",
            "schedule": research / "scheduled/status.json",
            "configuration": workspace / "deploy/reality.json",
        }

    @routes.get("/overview")
    def overview() -> dict[str, Any]:
        status = read_json(raw / "status.json")
        status.pop("selection_audit", None)
        now = time.time_ns()
        updated_ns = status.get("updated_ns")
        age = (now - updated_ns) / 1e9 if isinstance(updated_ns, int) else None
        health, health_reasons = classify_collector_health(status, now)
        return dict(
            now_ns=now,
            collector=status,
            collector_status_age_seconds=age,
            health=health,
            health_reasons=health_reasons,
            forward=read_json(forward / "status.json"),
            capacity=read_json(artifact_paths()["capacity"]),
            schedule=read_json(artifact_paths()["schedule"]),
            integrity=read_json(artifact_paths()["integrity"]),
            execution_ground_truth="unknown_counterfactual",
            orders_submitted=0,
        )

    @routes.get("/artifacts/{kind}")
    def artifact(kind: str) -> dict[str, Any]:
        path = artifact_paths().get(kind)
        if path is None:
            raise HTTPException(404, "Unknown evidence artifact")
        data = read_json(path)
        if not data:
            raise HTTPException(404, "Evidence has not been generated")
        # The empirical joint kernel contains thousands of individual rows, not UI data.
        if kind == "calibration":
            data.pop("empirical_joint_kernel", None)
        return dict(
            artifact=kind,
            relative_path=str(path.relative_to(workspace)),
            file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            data=data,
        )

    @routes.get("/forward")
    def forward_report(limit: int = Query(500, ge=1, le=5000)) -> dict[str, Any]:
        key = f"forward:{limit}"
        cached = cache.get(key)
        if cached and time.monotonic() - cached[0] < 15:
            return cached[1]  # type: ignore[no-any-return]
        if not (forward / "shadow.sqlite").exists():
            raise HTTPException(404, "No prospective journal available yet")
        result = report(forward, limit=limit)
        cache[key] = (time.monotonic(), result)
        return result

    @routes.get("/history")
    def history(
        condition: str = Query(min_length=1, max_length=100),
        start_ns: int = Query(ge=0),
        end_ns: int = Query(ge=0),
        limit: int = Query(720, ge=1, le=1500),
    ) -> dict[str, Any]:
        if end_ns < start_ns or end_ns - start_ns > 86_400_000_000_000:
            raise HTTPException(422, "Choose an ordered interval of at most 24 hours")
        with closing(database()) as db:
            records = db.execute(
                "select e.seq,e.body from observations o join events e on e.seq=o.event_seq "
                "where o.condition=? and o.ns>=? and o.ns<=? order by o.ns limit ?",
                (condition, start_ns, end_ns, limit + 1),
            ).fetchall()
        return dict(
            rows=[
                dict(event_seq=seq, **json.loads(zlib.decompress(body)))
                for seq, body in records[:limit]
            ],
            truncated=len(records) > limit,
            start_ns=start_ns,
            end_ns=end_ns,
            limit=limit,
            resolution="Frozen campaign observation sampling, nominal 5 seconds; no interpolation across missing observations",
        )

    @routes.get("/decisions")
    def decisions(
        before_ns: int = Query(2**63 - 1, ge=0),
        limit: int = Query(40, ge=1, le=100),
        condition: str = Query("", max_length=100),
    ) -> dict[str, Any]:
        where = "d.ns<?" + (" and d.condition=?" if condition else "")
        params: tuple[Any, ...] = (
            (before_ns, condition, limit + 1) if condition else (before_ns, limit + 1)
        )
        with closing(database()) as db:
            selected = db.execute(
                "select d.id,d.commit_ns,e.body from decisions d join events e on e.seq=d.event_seq "
                f"where {where} order by d.ns desc limit ?",
                params,
            ).fetchall()
        rows = []
        for uid, commit, body in selected[:limit]:
            row = json.loads(zlib.decompress(body))
            rows.append(
                {
                    k: row.get(k)
                    for k in (
                        "decision_ns",
                        "market_id",
                        "condition",
                        "title",
                        "quality_reason",
                        "policies",
                        "decision_latency_ns",
                        "decision_ordinal",
                        "market_title",
                    )
                }
                | dict(
                    id=uid,
                    commit_ns=commit,
                    baseline=None
                    if row["baseline"] is None
                    else {k: v for k, v in row["baseline"].items() if k != "views"},
                )
            )
        return dict(rows=rows, has_more=len(selected) > limit)

    @routes.get("/decisions/{uid}")
    def decision(uid: str) -> dict[str, Any]:
        if len(uid) != 64 or any(c not in "0123456789abcdef" for c in uid):
            raise HTTPException(422, "Expected a decision content identity")
        with closing(database()) as db:
            row = db.execute(
                "select e.body,d.commit_ns from decisions d join events e on e.seq=d.event_seq where d.id=?",
                (uid,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Unknown prospective decision")
            outcomes = [
                json.loads(zlib.decompress(body))
                for (body,) in db.execute(
                    "select e.body from outcomes o join events e on e.seq=o.event_seq where o.decision_id=? order by o.horizon",
                    (uid,),
                )
            ]
        return dict(
            decision=json.loads(zlib.decompress(row[0])),
            commit_ns=row[1],
            outcomes=outcomes,
            replay="Frozen decision evidence; later labels are separate from decision-time inputs",
        )

    @routes.get("/records/{ordinal}")
    def record(
        ordinal: int,
        segment: str = Query(pattern=r"^[0-9]{20}-[a-f0-9]{32}\.(seg|open)$"),
        offset: int = Query(ge=8, le=16_777_216),
    ) -> dict[str, Any]:
        requested = raw / segment
        handle = None
        for path in (
            requested,
            requested.with_suffix(".open" if requested.suffix == ".seg" else ".seg"),
        ):
            if path.is_symlink():
                raise HTTPException(404, "Source segment unavailable")
            try:
                handle = path.open("rb")
                break
            except FileNotFoundError:
                continue
        if handle is None:
            raise HTTPException(404, "Source segment unavailable")
        with handle:
            if handle.read(len(MAGIC)) != MAGIC:
                raise HTTPException(409, "Source framing mismatch")
            handle.seek(offset)
            header = handle.read(36)
            if len(header) != 36:
                raise HTTPException(404, "Source offset unavailable")
            size = struct.unpack(">I", header[:4])[0]
            if not 1 <= size <= 8_000_000:
                raise HTTPException(422, "Record exceeds inspection bound")
            compressed = handle.read(size)
        if hashlib.sha256(compressed).digest() != header[4:]:
            raise HTTPException(409, "Source record checksum mismatch")
        inflater = zlib.decompressobj()
        try:
            body = inflater.decompress(compressed, 8_000_001)
        except zlib.error as error:
            raise HTTPException(409, "Invalid source compression") from error
        if len(body) > 8_000_000 or not inflater.eof:
            raise HTTPException(422, "Expanded record exceeds inspection bound")
        try:
            data = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise HTTPException(409, "Invalid source JSON") from error
        if not isinstance(data, dict) or data.get("ordinal") != ordinal:
            raise HTTPException(409, "Ordinal does not match source offset")
        # Large discovery payloads remain on disk. Their exact hash is still available.
        truncated = len(body) > 100_000
        if truncated:
            data["payload"] = {
                "inspection": "Payload exceeds 100 KB browser limit; retained in raw source"
            }
        return dict(
            record=data,
            payload_truncated=truncated,
            segment=path.name,
            offset=offset,
            canonical_record_sha256=hashlib.sha256(body).hexdigest(),
            compressed_record_sha256=hashlib.sha256(compressed).hexdigest(),
        )

    units = (
        "midas-reality.service",
        "midas-reality-shadow.service",
        "midas-reality-capacity.timer",
        "midas-reality-archive.timer",
        "midas-reality-research.timer",
        "midas-reality-shadow-integrity.timer",
    )

    @routes.get("/operations")
    def operations() -> dict[str, Any]:
        cached = cache.get("operations")
        if cached and time.monotonic() - cached[0] < 10:
            return cached[1]  # type: ignore[no-any-return]
        services = []
        for unit in units:
            result = subprocess.run(
                [
                    "systemctl",
                    "--user",
                    "show",
                    unit,
                    "--property=ActiveState,SubState,MainPID,NRestarts,MemoryCurrent,CPUUsageNSec",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            services.append(
                dict(
                    unit=unit,
                    available=result.returncode == 0,
                    properties=dict(
                        line.split("=", 1) for line in result.stdout.splitlines() if "=" in line
                    ),
                )
            )
        value = dict(
            services=services,
            configuration=read_json(artifact_paths()["configuration"]),
            storage_policy=read_json(workspace / "deploy/reality-storage-policy.json"),
            controls=["check-capacity", "check-integrity", "pause-schedule", "resume-schedule"],
            collector_deployment="Collector replacement requires scripts/reality_deployment.py gates; dashboard does not restart it.",
        )
        cache["operations"] = (time.monotonic(), value)
        return value

    @routes.post("/operations/{action}")
    def operation(action: str, request: Request) -> dict[str, Any]:
        # Same-origin browser requests only. Fixed argv; never accepts unit names or shell text.
        origin = request.headers.get("origin")
        if origin is None or origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "Operations require a same-origin browser request")
        commands = {
            "check-capacity": ["start", "--no-block", "midas-reality-capacity.service"],
            "check-integrity": ["start", "--no-block", "midas-reality-shadow-integrity.service"],
            "pause-schedule": ["stop", "midas-reality-research.timer"],
            "resume-schedule": ["start", "midas-reality-research.timer"],
        }
        if action not in commands:
            raise HTTPException(422, "Unknown safe operation")
        result = subprocess.run(
            ["systemctl", "--user", *commands[action]],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        audit = workspace / "data/research/reality/interface"
        audit.mkdir(parents=True, exist_ok=True)
        event = dict(
            action=action,
            requested_ns=time.time_ns(),
            accepted=result.returncode == 0,
            detail=result.stderr[:1000],
        )
        with (audit / "operations.jsonl").open("a") as handle:
            handle.write(json.dumps(event) + "\n")
        cache.pop("operations", None)
        if result.returncode:
            raise HTTPException(409, event)
        return event

    return routes
