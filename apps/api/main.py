from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from midas.simulation.scenarios import SCENARIOS, catalog
from pydantic import BaseModel, ConfigDict, Field

from apps.api.config import Settings
from apps.api.service import Service

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer(),
    ]
)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    service = Service(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            await service.start()
            yield
        finally:
            await service.stop()

    app = FastAPI(
        title="Midas Research API",
        version="0.1.0",
        lifespan=lifespan,
        description="Read-only public market data and internal virtual simulation. No trading credentials or live orders.",
    )
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception) -> Any:
        from fastapi.responses import JSONResponse

        await service.report("ERROR", f"API failure {request.url.path}: {type(error).__name__}")
        return JSONResponse(
            status_code=503,
            content={"detail": "Operation failed; inspect Incidents and server logs"},
        )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": service.status, "mode": config.mode, "live_execution": False}

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        return await service.state()

    @app.get("/api/markets")
    async def markets() -> list[dict[str, Any]]:
        return [m.model_dump(mode="json") for m in service.markets.values()]

    @app.get("/api/opportunities")
    async def opportunities() -> list[dict[str, Any]]:
        return [
            {**e.model_dump(mode="json"), "risk": service.risk(e)}
            for e in service.current_evaluations()
        ]

    @app.get("/api/opportunities/{market_id}")
    async def opportunity(market_id: str) -> dict[str, Any]:
        match = next((e for e in service.current_evaluations() if e.market_id == market_id), None)
        if match is None:
            raise HTTPException(404, "Market observation not found")
        return {**match.model_dump(mode="json"), "risk": service.risk(match)}

    @app.get("/api/scenarios")
    async def scenarios() -> list[dict[str, str]]:
        return catalog()

    class RunInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        seed: int = Field(default=7, ge=0, le=2**32 - 1)

    @app.post("/api/scenarios/{scenario_id}/run")
    async def run(scenario_id: str, body: RunInput) -> dict[str, Any]:
        if scenario_id not in SCENARIOS:
            raise HTTPException(404, "Scenario not found")
        try:
            return await service.simulate(scenario_id, body.seed)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/api/simulations")
    async def simulations() -> list[dict[str, Any]]:
        return await service.store.recent("simulation", 200)

    @app.get("/api/incidents")
    async def incidents() -> list[dict[str, Any]]:
        return await service.store.recent("event", 200)

    @app.get("/api/analytics")
    async def analytics() -> dict[str, Any]:
        source = "SYNTHETIC" if config.mode == "demo" else "LIVE"
        observations = await service.store.recent("observation", 1000, source)
        runs = await service.store.recent("simulation", 200, "SYNTHETIC")
        counts: dict[str, int] = {}
        buckets: dict[int, dict[str, int]] = {}
        for record in observations:
            status = record["payload"]["status"]
            counts[status] = counts.get(status, 0) + 1
            minute = record["received_ts_ms"] // 60000 * 60000
            bucket = buckets.setdefault(minute, {"observations": 0, "verified": 0})
            bucket["observations"] += 1
            bucket["verified"] += status == "VERIFIED_MATHEMATICAL"
        return {
            "source": source,
            "observation_window": len(observations),
            "status_distribution": counts,
            "activity": [{"timestamp_ms": ts, **v} for ts, v in sorted(buckets.items())],
            "simulations": [
                {
                    "id": r["key"],
                    "timestamp_ms": r["received_ts_ms"],
                    "scenario_id": r["payload"]["scenario_id"],
                    "seed": r["payload"]["seed"],
                    "passed": r["payload"]["passed"],
                    "pnl": r["payload"]["portfolio"]["realized_pnl"],
                    "source": "SYNTHETIC",
                }
                for r in reversed(runs)
            ],
            "simulation_unit": "virtual USD",
            "note": "Each simulation starts a separate portfolio. P&L is not a cumulative strategy return.",
        }

    @app.get("/api/strategies")
    async def strategies() -> dict[str, Any]:
        return {
            "version": service.strategy.version,
            "name": "Complementary binary baseline",
            "capabilities": [
                "Decimal arithmetic",
                "Depth walking",
                "Independent risk gate",
                "Deterministic replay",
            ],
        }

    @app.get("/api/settings")
    async def settings_view() -> dict[str, Any]:
        return {
            "mode": config.mode,
            "market_limit": config.market_limit,
            "refresh_seconds": config.refresh_seconds,
            "risk_limits": service.limits.model_dump(mode="json"),
            "execution": "SIMULATION_ONLY",
        }

    class StopInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        emergency_stop: bool

    @app.patch("/api/settings")
    async def change_settings(body: StopInput) -> dict[str, Any]:
        service.limits = service.limits.model_copy(update={"emergency_stop": body.emergency_stop})
        await service.report(
            "WARNING" if body.emergency_stop else "INFO",
            f"Emergency stop {'enabled' if body.emergency_stop else 'released'}",
        )
        return await settings_view()

    return app


app = create_app()
