#!/usr/bin/env python3
"""Exercise a candidate API twice against a restored database under a resource scope."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

READ_ONLY_PATHS = (
    "/api/health",
    "/api/state",
    "/api/markets",
    "/api/opportunities",
    "/api/paper",
    "/api/paper/summary",
    "/api/paper/decisions",
    "/api/paper/journal",
    "/api/scenarios",
    "/api/simulations",
    "/api/experiments",
    "/api/incidents",
    "/api/analytics",
    "/api/strategies",
    "/api/settings",
)
PRODUCTION_DATABASE = Path.home() / "midas/data/midas.db"


class SmokeError(RuntimeError):
    pass


def require_resource_scope() -> str:
    declared = os.environ.get("MIDAS_RESOURCE_PREFLIGHT_CGROUP")
    if not declared:
        raise SmokeError("run through scripts/midas_resource_preflight.py run")
    lines = Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines()
    actual = next((line.split(":", 2)[2] for line in lines if line.startswith("0::")), None)
    if actual is None or f"/sys/fs/cgroup{actual}" != declared:
        raise SmokeError("resource-preflight cgroup does not match this process")
    cgroup = Path(declared)
    for name in ("memory.high", "memory.max"):
        value = (cgroup / name).read_text(encoding="ascii").strip()
        if value in {"max", "infinity"}:
            raise SmokeError("candidate smoke requires finite MemoryHigh and MemoryMax")
    return actual


def validate_database_path(isolated_root: Path, database: Path) -> tuple[Path, Path]:
    root = isolated_root.expanduser().resolve(strict=True)
    if isolated_root.is_symlink() or not root.is_dir():
        raise SmokeError("isolated root must be an existing real directory")
    if database.is_symlink():
        raise SmokeError("database path must not be a symlink")
    path = database.expanduser().resolve(strict=True)
    if not path.is_file() or not path.is_relative_to(root):
        raise SmokeError("database must be a regular file inside the isolated root")
    if path == PRODUCTION_DATABASE.resolve(strict=False):
        raise SmokeError("refusing to start a candidate against the production database")
    return root, path


def read_database_summary(path: Path, *, prefix_upper_bound: int | None = None) -> dict[str, Any]:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    try:
        check = [row[0] for row in connection.execute("PRAGMA quick_check")]
        if check != ["ok"]:
            raise SmokeError(f"isolated database quick_check failed: {check[:10]}")
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        records: int | None = None
        records_max_id: int | None = None
        prefix_count = 0
        prefix_sha256: str | None = hashlib.sha256().hexdigest()
        appended_count = 0
        appended_sources: dict[str, int] = {}
        if "records" in tables:
            records = int(connection.execute("SELECT count(*) FROM records").fetchone()[0])
            records_max_id = int(
                connection.execute("SELECT coalesce(max(id), 0) FROM records").fetchone()[0]
            )
            upper_bound = records_max_id if prefix_upper_bound is None else prefix_upper_bound
            digest = hashlib.sha256()
            prefix_count = 0
            for row in connection.execute(
                "SELECT id, kind, key, source, received_ts_ms, payload "
                "FROM records WHERE id <= ? ORDER BY id",
                (upper_bound,),
            ):
                digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode())
                digest.update(b"\n")
                prefix_count += 1
            prefix_sha256 = digest.hexdigest()
            if prefix_upper_bound is not None:
                appended_count = int(
                    connection.execute(
                        "SELECT count(*) FROM records WHERE id > ?", (prefix_upper_bound,)
                    ).fetchone()[0]
                )
                appended_sources = {
                    str(source): int(count)
                    for source, count in connection.execute(
                        "SELECT source, count(*) FROM records WHERE id > ? GROUP BY source",
                        (prefix_upper_bound,),
                    )
                }
        revisions = (
            [str(row[0]) for row in connection.execute("SELECT version_num FROM alembic_version")]
            if "alembic_version" in tables
            else []
        )
        return {
            "records": records,
            "records_max_id": records_max_id,
            "record_prefix_count": prefix_count,
            "record_prefix_sha256": prefix_sha256,
            "appended_record_count": appended_count,
            "appended_record_sources": appended_sources,
            "alembic_revisions": revisions,
            "tables": sorted(tables),
            "quick_check": check,
        }
    finally:
        connection.close()


def allocate_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def get_json(url: str, timeout: float = 2.0) -> tuple[int, dict[str, Any]]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = json.load(response)
            return response.status, body if isinstance(body, dict) else {"value": body}
    except HTTPError as error:
        return error.code, {}
    except (OSError, URLError, json.JSONDecodeError) as error:
        raise SmokeError(str(error)) from error


def candidate_environment(
    candidate_root: Path, isolated_root: Path, database: Path
) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("MIDAS_")}
    manifest_path = candidate_root / "release-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_commit = str(manifest.get("source_commit", "unknown"))
    environment.update(
        {
            "PYTHONPATH": os.pathsep.join((str(candidate_root), str(candidate_root / "packages"))),
            "MIDAS_MODE": "demo",
            "MIDAS_RUNTIME_ROOT": str(isolated_root / "candidate-runtime"),
            "MIDAS_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
            "MIDAS_ARENA_ROOT": str(isolated_root / "candidate-arena"),
            "MIDAS_LABORATORY_ROOT": str(isolated_root / "candidate-laboratory"),
            "MIDAS_RECORDING_ROOT": str(isolated_root / "candidate-recordings"),
            "MIDAS_REALITY_WORKSPACE": str(isolated_root / "candidate-reality"),
            "MIDAS_VERITAS_WORKSPACE": str(isolated_root / "candidate-veritas"),
            "MIDAS_FRONTIER_ROOT": str(isolated_root / "candidate-frontier"),
            "MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED": "false",
            "MIDAS_RELEASE_ID": candidate_root.name,
            "MIDAS_SOURCE_REVISION": source_commit,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "CUDA_VISIBLE_DEVICES": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


def serve_cycle(
    *,
    candidate_root: Path,
    python: Path,
    isolated_root: Path,
    database: Path,
    cycle: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    port = allocate_port()
    base = f"http://127.0.0.1:{port}"
    log_path = isolated_root / f"candidate-api-cycle-{cycle}.log"
    if log_path.exists() or log_path.is_symlink():
        raise SmokeError(f"refusing to replace existing candidate log: {log_path}")
    command = [
        str(python),
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    with log_path.open("x", encoding="utf-8") as log:
        os.chmod(log_path, 0o600)
        process = subprocess.Popen(
            command,
            cwd=candidate_root,
            env=candidate_environment(candidate_root, isolated_root, database),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + timeout_seconds
            health: dict[str, Any] = {}
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    status, health = get_json(f"{base}/api/health")
                    if status == 200 and health.get("startup_status") == "READY":
                        break
                except SmokeError:
                    pass
                time.sleep(0.25)
            else:
                raise SmokeError(f"candidate API failed readiness before timeout: {log_path}")
            if process.poll() is not None:
                raise SmokeError(f"candidate API exited early ({process.returncode}): {log_path}")
            if health.get("startup_status") != "READY" or health.get("live_execution") is not False:
                raise SmokeError(f"candidate health is not safely ready: {health}")
            if health.get("deployment", {}).get("schema_version") != "003":
                raise SmokeError(f"unexpected migrated schema identity: {health.get('deployment')}")

            route_results: list[dict[str, Any]] = []
            for path in READ_ONLY_PATHS:
                status, _ = get_json(f"{base}{path}")
                route_results.append({"path": path, "status": status})
                if status != 200:
                    raise SmokeError(f"read-only route returned HTTP {status}: {path}")
            openapi_status, openapi = get_json(f"{base}/openapi.json")
            if openapi_status != 200:
                raise SmokeError(f"candidate OpenAPI returned HTTP {openapi_status}")
            return {
                "cycle": cycle,
                "health_status": health.get("status"),
                "startup_status": health.get("startup_status"),
                "schema_version": health.get("deployment", {}).get("schema_version"),
                "paper_recovery": health.get("paper_recovery"),
                "read_only_routes": route_results,
                "openapi_path_count": len(openapi.get("paths", {})),
            }
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def run_smoke(
    candidate_root: Path,
    python: Path,
    isolated_root: Path,
    database: Path,
    cycles: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    cgroup = require_resource_scope()
    candidate_root = candidate_root.expanduser().resolve(strict=True)
    # Preserve venv symlink paths: resolving bin/python can escape the venv and
    # discard its site-packages (common on Linux installations).
    python = python.expanduser().absolute()
    if not (candidate_root / "apps/api/main.py").is_file():
        raise SmokeError("candidate root has no API application")
    if not python.is_file() or not os.access(python, os.X_OK):
        raise SmokeError("candidate Python must be an executable file")
    root, database = validate_database_path(isolated_root, database)
    before = read_database_summary(database)
    cycles_result: list[dict[str, Any]] = []
    for cycle in range(1, cycles + 1):
        cycle_result = serve_cycle(
            candidate_root=candidate_root,
            python=python,
            isolated_root=root,
            database=database,
            cycle=cycle,
            timeout_seconds=timeout_seconds,
        )
        cycle_summary = read_database_summary(
            database, prefix_upper_bound=before["records_max_id"] or 0
        )
        if (
            cycle_summary["record_prefix_count"] != before["record_prefix_count"]
            or cycle_summary["record_prefix_sha256"] != before["record_prefix_sha256"]
        ):
            raise SmokeError(
                "candidate changed or removed records that predate the isolated smoke: "
                f"before={before} after={cycle_summary}"
            )
        if set(cycle_summary["appended_record_sources"]) - {"SYNTHETIC"}:
            raise SmokeError(
                "demo-mode candidate appended records that are not explicitly synthetic: "
                f"{cycle_summary['appended_record_sources']}"
            )
        cycle_result["durable_record_summary"] = cycle_summary
        cycles_result.append(cycle_result)
    after = read_database_summary(database, prefix_upper_bound=before["records_max_id"] or 0)
    if after["alembic_revisions"] != ["003"]:
        raise SmokeError(f"candidate did not leave database at migration head 003: {after}")
    if (
        after["record_prefix_count"] != before["record_prefix_count"]
        or after["record_prefix_sha256"] != before["record_prefix_sha256"]
    ):
        raise SmokeError(f"candidate did not preserve the pre-existing record prefix: {after}")
    if set(after["appended_record_sources"]) - {"SYNTHETIC"}:
        raise SmokeError(f"candidate appended non-synthetic demo rows: {after}")
    if before["records"] is not None and not {"records", "paper_accounts", "paper_events"}.issubset(
        after["tables"]
    ):
        raise SmokeError(f"expected API tables are absent after migration: {after['tables']}")
    manifest = candidate_root / "release-manifest.json"
    return {
        "result": "PASS",
        "sampled_at_utc": datetime.now(UTC).isoformat(),
        "candidate_root": str(candidate_root),
        "candidate_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "candidate_source_commit": json.loads(manifest.read_text(encoding="utf-8")).get(
            "source_commit"
        ),
        "isolated_database": str(database),
        "resource_cgroup": cgroup,
        "before": before,
        "after": after,
        "cycles": cycles_result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--candidate-python", type=Path, required=True)
    parser.add_argument("--isolated-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--startup-timeout-seconds", type=float, default=45)
    args = parser.parse_args(argv)
    if args.cycles < 1 or args.cycles > 3:
        parser.error("--cycles must be between 1 and 3")
    try:
        print(
            json.dumps(
                run_smoke(
                    args.candidate_root,
                    args.candidate_python,
                    args.isolated_root,
                    args.database,
                    args.cycles,
                    args.startup_timeout_seconds,
                ),
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    except (
        OSError,
        sqlite3.Error,
        ValueError,
        KeyError,
        json.JSONDecodeError,
        SmokeError,
    ) as error:
        print(json.dumps({"result": "FAILED", "error": str(error)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
