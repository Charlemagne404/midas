"""Laboratory API: durable campaigns, datasets, incidents and persisted replay states."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from midas.laboratory.analytics import compare
from midas.laboratory.campaigns import PRESETS, Campaigns, CampaignSpec
from midas.laboratory.datasets import load_dataset, validate
from midas.laboratory.spec import FAMILIES, STRATEGIES
from pydantic import BaseModel, ConfigDict


def router(get_lab: Any) -> APIRouter:
    api = APIRouter(prefix="/api/laboratory", tags=["Laboratory"])

    async def call(fn: Any, *args: Any) -> Any:
        try:
            return await asyncio.to_thread(fn, *args)
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except (ValueError, FileNotFoundError) as error:
            raise HTTPException(409, str(error)) from error

    @api.get("/catalog")
    async def catalog() -> dict[str, Any]:
        lab: Campaigns = get_lab()
        datasets: list[dict[str, Any]] = []
        for p in sorted(lab.datasets.glob("*.manifest.json")):
            id = p.name.removesuffix(".manifest.json")
            try:
                path, manifest = load_dataset(lab.datasets, id)
                quality = validate(path, manifest)
                datasets.append(
                    {"id": id, "manifest": manifest.model_dump(mode="json"), "validation": quality}
                )
            except ValueError as error:
                datasets.append({"id": id, "quarantined": True, "reason": str(error)})
        return {
            "families": FAMILIES,
            "strategies": STRATEGIES,
            "presets": PRESETS,
            "models": ["optimistic", "standard", "conservative"],
            "datasets": datasets,
            "default_config": CampaignSpec().model_dump(mode="json"),
        }

    @api.get("/campaigns")
    async def campaigns() -> Any:
        return await call(get_lab().all)

    @api.post("/campaigns", status_code=201)
    async def create(body: CampaignSpec) -> Any:
        return await call(get_lab().create, body)

    @api.get("/campaigns/{id}")
    async def campaign(id: str) -> Any:
        return await call(get_lab().get, id)

    class Control(BaseModel):
        model_config = ConfigDict(extra="forbid")
        action: str

    @api.patch("/campaigns/{id}")
    async def control(id: str, body: Control) -> Any:
        return await call(get_lab().control, id, body.action)

    @api.get("/campaigns/{id}/runs")
    async def runs(id: str, offset: int = 0, limit: int = 50) -> Any:
        await call(get_lab().get, id)
        return await call(get_lab().runs, id, offset, limit)

    @api.get("/campaigns/{id}/comparison")
    async def comparison(id: str) -> Any:
        lab = get_lab()
        campaign = await call(lab.get, id)
        # Bound dashboard analysis. Prefix sampling is explicit, not an inferential claim.
        rows = []
        for offset in range(0, min(campaign["completed"], 2000), 200):
            rows.extend(await call(lab.runs, id, offset, 200))
        result = await asyncio.to_thread(compare, rows)
        return {
            **result,
            "settings": campaign["spec"],
            "analyzed_runs": len(rows),
            "total_runs": campaign["completed"],
            "sampling": "First 2000 runs in canonical episode/variant order",
        }

    @api.get("/campaigns/{id}/export")
    async def export(id: str) -> Any:
        campaign = await call(get_lab().get, id)
        return JSONResponse(
            campaign, headers={"Content-Disposition": f'attachment; filename="campaign-{id}.json"'}
        )

    @api.get("/runs/{id}")
    async def artifact(id: str) -> Any:
        return await call(get_lab().artifact, id)

    @api.get("/runs/{id}/export")
    async def export_run(id: str) -> Any:
        result = await call(get_lab().artifact, id)
        return JSONResponse(
            result, headers={"Content-Disposition": f'attachment; filename="run-{id}.json"'}
        )

    @api.post("/runs/{id}/reproduce")
    async def reproduce(id: str) -> Any:
        from midas.laboratory.runtime import execute
        from midas.laboratory.spec import Scenario

        archived = await call(get_lab().artifact, id)
        actual = await call(execute, Scenario.model_validate(archived["result"]["scenario"]))
        if actual["result_hash"] != archived["result"]["result_hash"]:
            raise HTTPException(409, "Current simulator did not reproduce the archived result")
        return {
            "run_id": id,
            "matches": actual["result_hash"] == archived["result"]["result_hash"],
            "expected_hash": archived["result"]["result_hash"],
            "actual_hash": actual["result_hash"],
            "passed": actual["passed"],
            "classification": actual["classification"],
        }

    @api.get("/incidents")
    async def incidents() -> Any:
        return await call(get_lab().incidents)

    return api
