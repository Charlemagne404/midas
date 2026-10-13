"""Arena metadata stays available without loading ML libraries into API startup."""

import asyncio
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict


def inspect_director(root: Path, identity: str) -> dict[str, Any]:
    """Observe coordinator liveness without rewriting its owned manifest."""
    from midas.arena.artifacts import artifact_path

    directory = artifact_path(root, "directors", identity)
    record: dict[str, Any] = json.loads((directory / "manifest.json").read_text())
    if record.get("director_version") != "adaptive-latency-1" or record["state"] != "RUNNING":
        return record
    reference = directory / "supervisor-reference.json"
    if not reference.exists():
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": "Coordinator supervisor reference is unavailable; inspect its child jobs.",
        }
    supervisor = json.loads(reference.read_text())
    unit = supervisor["unit"]
    if not isinstance(unit, str) or not re.fullmatch(
        r"midas-prometheus-followup-[a-zA-Z0-9_-]+\.service", unit
    ):
        raise ValueError("Invalid research coordinator unit")
    record["coordinator_unit"] = unit
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "ActiveState",
                "-p",
                "MainPID",
                "-p",
                "Result",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": f"Coordinator status observation failed: {type(error).__name__}",
        }
    properties = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    record["coordinator_supervisor"] = properties
    if result.returncode or not properties.get("ActiveState"):
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": "Coordinator status could not be verified; no restart was requested.",
        }
    if properties["ActiveState"] in {"inactive", "failed"}:
        return {
            **record,
            "state": "INTERRUPTED",
            "observation_error": "Coordinator stopped before publishing completion. Child jobs retain their own supervised state.",
        }
    if (
        properties["ActiveState"] != "active"
        or not properties.get("MainPID", "0").isdigit()
        or int(properties.get("MainPID", "0")) == 0
    ):
        return {
            **record,
            "state": "UNVERIFIED",
            "observation_error": "Coordinator has no verified active process.",
        }
    for index, step in enumerate(record["steps"]):
        if step["state"] != "RUNNING" or not step.get("job_id"):
            continue
        job_path = artifact_path(root, "jobs", step["job_id"]) / "job.json"
        job = json.loads(job_path.read_text())
        if job["state"] == "COMPLETED":
            step["state"] = "VERIFYING"
            step["progress"] = job.get("progress")
            record["current_stage"] = f"Verifying completed cycle {index // 2 + 1} replays"
        break
    return record


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

    def evaluation_counts(record: dict[str, Any]) -> None:
        independent = validation = 0
        for evaluation in record.get("policy_evaluations", []):
            file = path("tournaments", evaluation["tournament_id"]) / "manifest.json"
            if file.exists():
                design = json.loads(file.read_text()).get("evaluation_design")
                validation += int(design == "VALIDATION")
                independent += int(design in {"TEST", "FRESH_GENERATOR_CHALLENGE"})
        record["independent_policy_evaluations"] = independent
        record["validation_policy_comparisons"] = validation

    def catalog(kind: str) -> list[dict[str, Any]]:
        values = []
        for manifest in sorted(
            (root / kind).glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:100]:
            record = json.loads(manifest.read_text())
            if kind == "directors":
                record = inspect_director(root, manifest.parent.name)
            if kind == "models":
                evaluation_counts(record)
            if kind == "searches" and record["state"] == "RUNNING" and record.get("owner_job_id"):
                from midas.arena.jobs import inspect

                owner = inspect(root, record["owner_job_id"])
                if owner["state"] not in {"RUNNING", "QUEUED"}:
                    record["state"] = (
                        owner["state"] if owner["state"] != "COMPLETED" else "INCOMPLETE"
                    )
                    record["error"] = owner.get("error")
            quality_path = manifest.parent / "quality.json"
            if kind == "datasets" and quality_path.exists():
                quality = json.loads(quality_path.read_text())
                record["quality"] = {
                    key: quality[key]
                    for key in (
                        "warnings",
                        "constant_features",
                        "duplicate_vector_groups",
                        "cross_partition_duplicate_vector_groups",
                        "ambiguous_observable_vectors",
                    )
                }
            # Curves live on detail pages, not every overview poll.
            omitted = {"curves"}
            if kind == "directors" and record.get("director_version") == "adaptive-latency-1":
                record["completed_cycle_count"] = len(record.get("cycles", []))
                omitted.update({"cycles", "input_attribution"})
            values.append({k: v for k, v in record.items() if k not in omitted})
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
        recorded_sources = []
        from midas.laboratory.datasets import load_dataset, validate

        for manifest_path in sorted((root.parent / "datasets").glob("*.manifest.json"))[:100]:
            identity = manifest_path.name.removesuffix(".manifest.json")
            try:
                recording, manifest = load_dataset(root.parent / "datasets", identity)
                validation = validate(recording, manifest)
                recorded_sources.append(
                    {
                        "dataset_id": identity,
                        "provenance": "RECORDED_PUBLIC",
                        "content_sha256": manifest.content_sha256,
                        "events": manifest.event_count,
                        "capture_start_ms": manifest.capture_start_ms,
                        "capture_end_ms": manifest.capture_end_ms,
                        "valid": validation["valid"],
                        "eligible_for_execution_training": False,
                        "limitations": list(manifest.completeness_limitations)
                        + ["No empirically observed execution-completion labels."],
                    }
                )
            except (ValueError, FileNotFoundError) as error:
                recorded_sources.append(
                    {"dataset_id": identity, "valid": False, "error": str(error)}
                )
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:", "SwapFree:")):
                name, value, *_ = line.split()
                memory[name.rstrip(":")] = int(value) // 1024
        from midas.arena.artifacts import cold_storage_status

        return {
            "cold_storage": cold_storage_status(root),
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
            "recorded_sources": recorded_sources,
            "sweeps": catalog("sweeps"),
            "directors": catalog("directors"),
            "searches": catalog("searches"),
            "recoveries": catalog("recoveries"),
            "unwinds": catalog("unwinds"),
            "observations": catalog("observations"),
            "schedules": catalog("schedules"),
            "alerts": catalog("alerts"),
        }

    @api.get("")
    async def overview() -> Any:
        return await call(overview_data)

    @api.get("/datasets/{identity}")
    async def dataset(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("datasets", identity) / "manifest.json").read_text())
        )

    @api.get("/sweeps/{identity}")
    async def sweep(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("sweeps", identity) / "manifest.json").read_text())
        )

    @api.get("/observations/{identity}")
    async def observation_dataset(identity: str) -> Any:
        from midas.arena.observations import load

        return await call(lambda: load(root, identity)[0])

    @api.post("/schedules")
    async def create_schedule(payload: dict[str, Any]) -> Any:
        def admit() -> Any:
            from midas.arena.scheduling import ScheduleSpec, create

            return create(root, ScheduleSpec.model_validate(payload))

        return await call(admit)

    @api.get("/schedules/{identity}")
    async def schedule_detail(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("schedules", identity) / "manifest.json").read_text())
        )

    @api.post("/schedules/{identity}/{action}")
    async def schedule_control(identity: str, action: str) -> Any:
        def change() -> Any:
            from midas.arena.scheduling import control

            if action not in {"pause", "resume", "cancel"}:
                raise ValueError("Unknown schedule control")
            return control(root, identity, action)

        return await call(change)

    @api.get("/observations/{identity}/rows")
    async def observation_rows(
        identity: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ) -> Any:
        def read() -> Any:
            from midas.arena.observations import load

            return load(root, identity)[1][offset : offset + limit]

        return await call(read)

    @api.get("/directors/{identity}")
    async def director(identity: str) -> Any:
        return await call(inspect_director, root, identity)

    @api.post("/directors/{identity}/cancel")
    async def cancel_director(identity: str) -> Any:
        def cancel() -> Any:
            file = path("directors", identity) / "manifest.json"
            record = json.loads(file.read_text())
            if record.get("director_version") != "adaptive-latency-1":
                raise ValueError("Use job cancellation for this research plan")
            from scripts.research_followup import stop

            stop(root, identity)
            return json.loads(file.read_text())

        return await call(cancel)

    @api.get("/searches/{identity}")
    async def policy_search(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("searches", identity) / "manifest.json").read_text())
        )

    @api.get("/recoveries/{identity}")
    async def recovery(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("recoveries", identity) / "manifest.json").read_text())
        )

    @api.get("/unwinds/{identity}")
    async def unwind(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("unwinds", identity) / "manifest.json").read_text())
        )

    @api.get("/unwinds/{identity}/rows")
    async def unwind_rows(
        identity: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)
    ) -> Any:
        return await call(
            lambda: json.loads((path("unwinds", identity) / "rows.json").read_text())[
                offset : offset + limit
            ]
        )

    @api.get("/unwinds/{identity}/replay/{row_id}")
    async def unwind_replay(identity: str, row_id: str) -> Any:
        from midas.arena.artifacts import read_replay

        def read() -> Any:
            directory = path("unwinds", identity)
            if not any(
                r["id"] == row_id for r in json.loads((directory / "rows.json").read_text())
            ):
                raise HTTPException(404, "Unwind row not found")
            return read_replay(directory / "replays" / (row_id + ".json"))

        return await call(read)

    @api.get("/models/{identity}")
    async def model(identity: str) -> Any:
        def read() -> Any:
            directory = path("models", identity)
            if (directory / "manifest.json").exists():
                result = json.loads((directory / "manifest.json").read_text())
                evaluation_counts(result)
                if (directory / "diagnostics.json").exists():
                    diagnostics = json.loads((directory / "diagnostics.json").read_text())
                    if diagnostics["model_artifact_sha256"] != result["artifact_sha256"]:
                        raise ValueError("Diagnostic model hash differs from current weights")
                    result["diagnostics"] = diagnostics
                return result
            record = json.loads((directory / "training.json").read_text())
            owner = None
            for job_path in (root / "jobs").glob("*/job.json"):
                job_record = json.loads(job_path.read_text())
                if job_record.get("active_artifact", {}).get("identity") == identity:
                    from midas.arena.jobs import inspect

                    owner = inspect(root, job_path.parent.name)
                    break
            if owner is None or owner["state"] not in {"RUNNING", "QUEUED"}:
                record["state"] = owner["state"] if owner else "INTERRUPTED"
                record["training_duration_seconds"] = (
                    owner.get("elapsed_seconds", 0) if owner else 0
                )
            if (directory / "checkpoint.json").exists():
                checkpoint = json.loads((directory / "checkpoint.json").read_text())
                record["curves"] = checkpoint["curves"]
                record["checkpoints"] = ["checkpoint.json"]
            elif (directory / "curves.json").exists():
                record["curves"] = json.loads((directory / "curves.json").read_text())
                record["checkpoints"] = (
                    ["checkpoint.zip"] if (directory / "checkpoint.zip").exists() else []
                )
            if record["state"] == "TRAINING":
                record["training_duration_seconds"] = max(
                    0, __import__("time").time() - record["created_at"]
                )
            return record

        return await call(read)

    @api.get("/datasets/{identity}/quality")
    async def dataset_quality(identity: str) -> Any:
        return await call(
            lambda: json.loads((path("datasets", identity) / "quality.json").read_text())
        )

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
            "diagnostics.json",
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

    @api.get("/tournaments/{identity}/economics")
    async def tournament_economics(identity: str) -> Any:
        def read() -> Any:
            from midas.arena.artifacts import sha256
            from midas.economics.attestation import digest

            directory = path("tournaments", identity)
            manifest = json.loads((directory / "manifest.json").read_text())
            if not (directory / "economics.json").exists():
                return None
            report = json.loads((directory / "economics.json").read_text())
            if (
                report["rows_sha256"] != manifest["rows_sha256"]
                or sha256(directory / "rows.json") != report["rows_sha256"]
                or digest({k: v for k, v in report.items() if k != "report_digest"})
                != report["report_digest"]
            ):
                raise ValueError("Economic report integrity or input provenance changed")
            return report

        return await call(read)

    @api.get("/tournaments/{identity}/economic-regimes")
    async def economic_regimes(identity: str) -> Any:
        def read() -> Any:
            from midas.arena.artifacts import sha256

            directory = path("tournaments", identity)
            if not (directory / "manifest.json").exists():
                raise FileNotFoundError(identity)
            reference = directory / "economic-study-reference.json"
            if not reference.exists():
                return None
            link = json.loads(reference.read_text())
            report_path = (
                path("tournaments", link["baseline_tournament_id"]) / "economic-regimes.json"
            )
            if sha256(report_path) != link["report_sha256"]:
                raise ValueError("Economic study report hash changed")
            report = json.loads(report_path.read_text())
            if identity not in {c["tournament_id"] for c in report["conditions"]}:
                raise ValueError("Tournament is not part of the referenced economic study")
            for condition in report["conditions"]:
                folder = path("tournaments", condition["tournament_id"])
                manifest = json.loads((folder / "manifest.json").read_text())
                if (
                    manifest["rows_sha256"] != condition["rows_sha256"]
                    or sha256(folder / "rows.json") != condition["rows_sha256"]
                    or manifest["source_hash"] != report["source_hash"]
                ):
                    raise ValueError("Economic study input provenance changed")
            return report

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
