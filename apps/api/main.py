from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from midas.analytics.research import feasibility
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
        import asyncio
        from pathlib import Path

        from midas.laboratory.campaigns import Campaigns

        laboratory: Campaigns | None = None
        startup_failed = False
        app.state.startup_status = "RECOVERING"
        app.state.startup_error = None
        app.state.campaign_recovery_ids = []
        app.state.campaign_recovery_errors = []
        app.state.laboratory = None
        try:
            await service.start()
            database_path = service.store.engine.url.database
            if config.laboratory_root is not None:
                root = config.laboratory_root
            else:
                parent = (
                    Path(database_path).parent
                    if database_path and database_path != ":memory:"
                    else Path("data")
                )
                existing = parent / "laboratory-final"
                root = existing if existing.is_dir() else parent / "laboratory"
            laboratory = Campaigns(root, Path(__file__).resolve().parents[2] / "data/datasets")
            app.state.laboratory = laboratory
            app.state.laboratory_root = str(root.resolve())

            # RUNNING is converted to INTERRUPTED by Campaigns while it owns the writer lease.
            # Resume only crash/shutdown cases. Budget and disk interruptions need review.
            for campaign in laboratory.all():
                if campaign["status"] != "INTERRUPTED" or campaign["error"] not in (
                    None,
                    "Service shutdown; committed episodes retained",
                ):
                    continue
                try:
                    laboratory.control(campaign["id"], "resume")
                    app.state.campaign_recovery_ids.append(campaign["id"])
                except (KeyError, ValueError) as error:
                    app.state.campaign_recovery_errors.append(
                        {"campaign_id": campaign["id"], "error": str(error)}
                    )
            app.state.startup_status = "DEGRADED" if app.state.campaign_recovery_errors else "READY"
        except Exception as error:
            startup_failed = True
            app.state.startup_status = "FAILED"
            app.state.startup_error = f"{type(error).__name__}: {error}"
            structlog.get_logger().error("startup_failed", error=app.state.startup_error)
            if laboratory is not None:
                await asyncio.to_thread(laboratory.close)
            try:
                await service.stop()
            except Exception as cleanup_error:
                structlog.get_logger().error(
                    "startup_cleanup_failed",
                    error=f"{type(cleanup_error).__name__}: {cleanup_error}",
                )

        try:
            yield
        finally:
            if not startup_failed:
                if laboratory is not None:
                    await asyncio.to_thread(laboratory.close)
                await service.stop()

    app = FastAPI(
        title="Midas Research API",
        version="0.2.0",
        lifespan=lifespan,
        description="Read-only public market data and internal virtual simulation. No trading credentials or live orders.",
    )
    app.state.service = service
    app.state.startup_status = "RECOVERING"
    app.state.startup_error = None
    from apps.api.laboratory import router

    app.include_router(router(lambda: app.state.laboratory))
    from apps.api.arena import router as arena_router

    app.include_router(arena_router(config.arena_root))
    from apps.api.reality import router as reality_router

    app.include_router(reality_router(config.reality_workspace.resolve()))

    @app.middleware("http")
    async def gate_failed_startup(request: Request, call_next: Any) -> Any:
        from fastapi.responses import JSONResponse

        if (
            request.url.path.startswith("/api/")
            and request.url.path != "/api/health"
            and app.state.startup_status == "FAILED"
        ):
            return JSONResponse(
                status_code=503,
                content={"status": "FAILED", "detail": "Midas startup or recovery failed"},
            )
        return await call_next(request)

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
        startup = app.state.startup_status
        if startup == "FAILED":
            status = "FAILED"
        elif startup == "DEGRADED":
            status = "DEGRADED"
        else:
            status = service.health_status()
        laboratory = getattr(app.state, "laboratory", None)
        recovery_campaigns = []
        if laboratory is not None:
            for campaign_id in app.state.campaign_recovery_ids:
                try:
                    if laboratory.get(campaign_id)["status"] == "RUNNING":
                        recovery_campaigns.append(campaign_id)
                except KeyError:
                    continue
        recovery_status = (
            "FAILED"
            if startup == "FAILED"
            else "DEGRADED"
            if app.state.campaign_recovery_errors
            else "RECOVERING"
            if recovery_campaigns
            else "READY"
        )
        result = {
            "status": status,
            "startup_status": startup,
            "startup_error": app.state.startup_error,
            "mode": config.mode,
            "live_execution": False,
            "paper_recovery": {
                "status": service.broker.recovery_status,
                "journal_events": service.broker.journal_event_count,
                "revision": service.broker.revision,
            },
            "laboratory": {
                "status": recovery_status,
                "root": getattr(app.state, "laboratory_root", None),
                "recovering_campaigns": recovery_campaigns,
                "recovery_errors": app.state.campaign_recovery_errors,
            },
        }
        if status == "FAILED":
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content=result)  # type: ignore[return-value]
        return result

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

    @app.get("/api/paper")
    async def paper() -> dict[str, Any]:
        from midas.market_data.polymarket import now_ms
        from midas.paper.broker import summary

        return {**summary(service.broker.state, now_ms()), "healthy": service.broker.healthy}

    class PaperControl(BaseModel):
        model_config = ConfigDict(extra="forbid")
        paused: bool | None = None
        execution_model: str | None = None

    @app.patch("/api/paper")
    async def paper_control(body: PaperControl) -> dict[str, Any]:
        from midas.market_data.polymarket import now_ms
        from midas.paper.broker import ExecutionModel

        ts = now_ms()
        command: dict[str, Any] = {"id": f"control:{ts}", "kind": "control", "ts": ts}
        if body.paused is not None:
            command["paused"] = body.paused
        if body.execution_model is not None:
            try:
                command["execution"] = ExecutionModel.preset(body.execution_model).model_dump(
                    mode="json"
                )
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
        await service.broker.apply(command)
        return await paper()

    class SyntheticSettlement(BaseModel):
        model_config = ConfigDict(extra="forbid")
        payout: dict[str, str]

    @app.post("/api/paper/positions/{position_id}/settle")
    async def synthetic_settlement(position_id: str, body: SyntheticSettlement) -> dict[str, Any]:
        from midas.market_data.polymarket import now_ms

        if service.broker.state["config"]["mode"] != "synthetic":
            raise HTTPException(
                409, "Synthetic outcome injection is restricted to the synthetic account"
            )
        if position_id not in service.broker.state["positions"]:
            raise HTTPException(404, "Paper position not found")
        try:
            await service.broker.apply(
                {
                    "id": f"settlement:{position_id}",
                    "kind": "settle",
                    "ts": now_ms(),
                    "position": position_id,
                    "payout": body.payout,
                }
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return await paper()

    @app.get("/api/paper/decisions")
    async def paper_decisions(
        before_revision: int | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from apps.api.storage import PaperEvent

        statement = select(PaperEvent).where(
            PaperEvent.account_id == service.broker.account_id,
            PaperEvent.command["kind"].as_string() == "observe",
        )
        if before_revision is not None:
            statement = statement.where(PaperEvent.revision < before_revision)
        async with service.store.sessions() as session:
            rows = await session.scalars(
                statement.order_by(PaperEvent.revision.desc()).limit(min(max(limit, 1), 200))
            )
            return [
                {"event_id": r.event_id, "revision": r.revision, "decision": r.payload["decision"]}
                for r in rows
                if r.payload.get("decision")
            ]

    @app.get("/api/paper/journal")
    async def paper_journal(before_revision: int | None = None) -> list[dict[str, Any]]:
        from sqlalchemy import select

        from apps.api.storage import PaperEvent

        async with service.store.sessions() as session:
            rows = await session.scalars(
                select(PaperEvent)
                .where(
                    PaperEvent.account_id == service.broker.account_id,
                    PaperEvent.revision
                    < (before_revision if before_revision is not None else 2**63 - 1),
                )
                .order_by(PaperEvent.revision.desc())
                .limit(200)
            )
            return [
                {
                    "event_id": r.event_id,
                    "revision": r.revision,
                    "command": r.command,
                    "checksum": r.checksum,
                }
                for r in rows
            ]

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

    @app.get("/api/experiments")
    async def experiments() -> list[dict[str, Any]]:
        return await service.store.recent("experiment", 200, "SYNTHETIC")

    from midas.paper.broker import ExecutionModel

    class ExperimentInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        seed: int = Field(default=7, ge=0, le=2**32 - 1)
        fault: str = "none"
        execution: ExecutionModel = ExecutionModel()
        compare: bool = False

    @app.post("/api/experiments")
    async def experiment(body: ExperimentInput) -> dict[str, Any]:
        import asyncio
        import uuid

        from midas.market_data.polymarket import now_ms
        from midas.paper.experiments import FAULTS, differential, run_experiment

        if body.fault not in FAULTS:
            raise HTTPException(422, "Unknown fault")
        if service.limits.emergency_stop or not service.store.healthy or not service.broker.healthy:
            raise HTTPException(409, "Experiment admission halted")
        if service.pending_simulations >= 8:
            raise HTTPException(409, "Experiment queue full")
        service.pending_simulations += 1
        try:
            async with service.simulation_slots:
                if service.limits.emergency_stop:
                    raise HTTPException(409, "Emergency stop active")
                result = (
                    await asyncio.to_thread(differential, body.seed, body.fault)
                    if body.compare
                    else await asyncio.to_thread(
                        run_experiment, body.seed, body.execution, body.fault
                    )
                )
                key = uuid.uuid4().hex
                await service.store.append("experiment", key, "SYNTHETIC", now_ms(), result)
                return {"id": key, "result": result}
        finally:
            service.pending_simulations -= 1

    @app.get("/api/experiments/{experiment_id}")
    async def experiment_artifact(experiment_id: str) -> Any:
        from fastapi.responses import JSONResponse

        for row in await service.store.recent("experiment", 200):
            if row["key"] == experiment_id:
                return JSONResponse(
                    row["payload"],
                    headers={
                        "Content-Disposition": f'attachment; filename="experiment-{experiment_id}.json"'
                    },
                )
        raise HTTPException(404, "Experiment artifact not found in retained window")

    @app.get("/api/incidents")
    async def incidents() -> list[dict[str, Any]]:
        rows = await service.store.recent("event", 200)
        import asyncio

        for index, incident in enumerate(await asyncio.to_thread(app.state.laboratory.incidents)):
            observed = int(incident.get("first_observed_at", 0) * 1000)
            rows.append(
                {
                    "id": -(1000 + index),
                    "key": incident["id"],
                    "source": "LABORATORY",
                    "received_ts_ms": observed,
                    "payload": {
                        **incident,
                        "message": f"{incident['classification']}: {incident['invariant']}",
                        "timestamp_ms": observed,
                        "source": "LABORATORY",
                    },
                }
            )
        for index, incident in enumerate(service.broker.state["incidents"][-100:]):
            rows.insert(
                0,
                {
                    "id": -(index + 1),
                    "key": incident["kind"],
                    "source": "PAPER",
                    "received_ts_ms": incident["ts"],
                    "payload": {
                        **incident,
                        "message": incident.get("result", incident["kind"]),
                        "timestamp_ms": incident["ts"],
                        "source": "PAPER",
                    },
                },
            )
        return rows

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
            "paper": await paper(),
            "feasibility": feasibility(observations, await paper()),
            "experiment_comparisons": [
                r["payload"].get("comparison", [])
                for r in await service.store.recent("experiment", 200)
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
            "risk_limits": service.broker.config.limits.model_copy(
                update={"emergency_stop": service.limits.emergency_stop}
            ).model_dump(mode="json"),
            "legacy_simulation_risk_limits": service.limits.model_dump(mode="json"),
            "execution": "SIMULATION_ONLY",
        }

    class StopInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        emergency_stop: bool

    @app.patch("/api/settings")
    async def change_settings(body: StopInput) -> dict[str, Any]:
        from midas.market_data.polymarket import now_ms

        ts = now_ms()
        await service.broker.apply(
            {"id": f"stop:{ts}", "kind": "control", "ts": ts, "emergency_stop": body.emergency_stop}
        )
        service.limits = service.limits.model_copy(update={"emergency_stop": body.emergency_stop})
        await service.report(
            "WARNING" if body.emergency_stop else "INFO",
            f"Emergency stop {'enabled' if body.emergency_stop else 'released'}",
        )
        return await settings_view()

    return app


app = create_app()
