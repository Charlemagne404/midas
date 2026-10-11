"""Arena metadata stays available without loading ML libraries into API startup."""

import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict


def router(root: Path) -> APIRouter:
    api = APIRouter(prefix="/api/arena", tags=["Arena"])

    async def call(fn: Any, *args: Any) -> Any:
        try:
            return await asyncio.to_thread(fn, *args)
        except FileNotFoundError as error:
            raise HTTPException(404, "Research artifact not found") from error
        except (ValueError, KeyError) as error:
            raise HTTPException(409, str(error)) from error
        except ImportError as error:
            raise HTTPException(
                503, "Install requirements-arena.txt with CPU PyTorch to run research"
            ) from error

    def path(kind: str, identity: str) -> Path:
        from midas.arena.artifacts import artifact_path

        return artifact_path(root, kind, identity)

    def catalog(kind: str) -> list[dict[str, Any]]:
        values = []
        for manifest in sorted(
            (root / kind).glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:100]:
            record = json.loads(manifest.read_text())
            # Curves live on detail pages, not every overview poll.
            values.append({k: v for k, v in record.items() if k != "curves"})
        return values

    def overview_data() -> dict[str, Any]:
        dependencies = {
            name: importlib.util.find_spec(name) is not None
            for name in ("numpy", "sklearn", "torch", "gymnasium", "stable_baselines3")
        }
        jobs = []
        files = sorted(
            (root / "jobs").glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:100]
        for file in files:
            if all(dependencies.values()):
                from midas.arena.jobs import inspect

                jobs.append(inspect(root, file.parent.name))
            else:
                jobs.append(json.loads(file.read_text()))
        memory = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:", "SwapFree:")):
                name, value, *_ = line.split()
                memory[name.rstrip(":")] = int(value) // 1024
        return {
            "datasets": catalog("datasets"),
            "models": catalog("models"),
            "tournaments": catalog("tournaments"),
            "jobs": jobs,
            "findings": catalog("findings"),
            "dependencies": dependencies,
            "health": {"memory_mb": memory, "worker_cpu_cores": 1, "worker_memory_mb": 4096},
            "registered_strategies": ["arbitrage", "conservative", "no_trade", "random"],
            "provenance": "SYNTHETIC / HYPOTHETICAL / ECONOMICALLY UNVERIFIED",
            "root": str(root),
        }

    @api.get("")
    async def overview() -> Any:
        return await call(overview_data)

    @api.get("/datasets/{identity}")
    async def dataset(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("datasets", identity) / "manifest.json").read_text())
        )

    @api.get("/models/{identity}")
    async def model(identity: str) -> Any:
        def read() -> Any:
            directory = path("models", identity)
            if (directory / "manifest.json").exists():
                return json.loads((directory / "manifest.json").read_text())
            record = json.loads((directory / "training.json").read_text())
            if (directory / "checkpoint.json").exists():
                checkpoint = json.loads((directory / "checkpoint.json").read_text())
                record["curves"] = checkpoint["curves"]
                record["checkpoints"] = ["checkpoint.json"]
            elif (directory / "curves.json").exists():
                record["curves"] = json.loads((directory / "curves.json").read_text())
                record["checkpoints"] = (
                    ["checkpoint.zip"] if (directory / "checkpoint.zip").exists() else []
                )
            record["training_duration_seconds"] = max(
                0, __import__("time").time() - record["created_at"]
            )
            return record

        return await call(read)

    @api.get("/models/{identity}/artifacts/{name}")
    async def model_artifact(identity: str, name: str) -> Any:
        from fastapi.responses import FileResponse

        if name not in {
            "parameters.json",
            "checkpoint.json",
            "checkpoint.zip",
            "policy.zip",
            "progress.csv",
            "curves.json",
        }:
            raise HTTPException(404, "Unknown model artifact")
        artifact = await call(lambda: path("models", identity) / name)
        if not artifact.is_file():
            raise HTTPException(404, "Artifact not found")
        return FileResponse(artifact, filename=name)

    @api.get("/tournaments/{identity}")
    async def tournament(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("tournaments", identity) / "manifest.json").read_text())
        )

    @api.get("/tournaments/{identity}/rows")
    async def tournament_rows(
        identity: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        family: str | None = None,
        execution_model: str | None = None,
    ) -> Any:
        def read() -> Any:
            rows = json.loads((path("tournaments", identity) / "rows.json").read_text())
            selected = [
                r
                for r in rows
                if (family is None or r["family"] == family)
                and (execution_model is None or r["execution_model"] == execution_model)
            ]
            return {"total": len(selected), "rows": selected[offset : offset + limit]}

        return await call(read)

    @api.get("/tournaments/{identity}/replay/{row_id}")
    async def replay(identity: str, row_id: str) -> Any:
        import re

        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,150}", row_id):
            raise HTTPException(422, "Invalid replay identity")
        from midas.arena.artifacts import read_replay

        return await call(
            lambda: read_replay(path("tournaments", identity) / "replays" / f"{row_id}.json")
        )

    class JobBody(BaseModel):
        model_config = ConfigDict(extra="forbid")
        configuration: dict[str, Any]

    @api.post("/jobs/validate")
    async def validate_job(body: JobBody) -> Any:
        def validate() -> Any:
            from midas.arena.jobs import JobSpec

            return JobSpec.model_validate(body.configuration).model_dump(mode="json")

        return await call(validate)

    @api.post("/jobs", status_code=201)
    async def create_job(body: JobBody) -> Any:
        def create() -> Any:
            from midas.arena.jobs import JobSpec, create

            return create(root, JobSpec.model_validate(body.configuration))

        return await call(create)

    @api.get("/jobs/{identity}")
    async def job(identity: str) -> Any:
        def inspect() -> Any:
            from midas.arena.jobs import inspect

            return inspect(root, identity)

        return await call(inspect)

    @api.post("/jobs/{identity}/cancel")
    async def cancel_job(identity: str) -> Any:
        def cancel() -> Any:
            from midas.arena.jobs import cancel

            return cancel(root, identity)

        return await call(cancel)

    @api.get("/jobs/{identity}/logs")
    async def job_logs(identity: str) -> Any:
        def read() -> Any:
            import subprocess

            record = json.loads((path("jobs", identity) / "job.json").read_text())
            result = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    record["unit"],
                    "-n",
                    "100",
                    "--no-pager",
                    "-o",
                    "short-iso",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return {
                "job_id": identity,
                "unit": record["unit"],
                "logs": result.stdout,
                "error": result.stderr if result.returncode else None,
            }

        return await call(read)

    return api
