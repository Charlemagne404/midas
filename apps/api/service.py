import asyncio
import hashlib
import time
from collections import deque
from decimal import Decimal, DecimalException
from pathlib import Path
from typing import Any

import structlog
from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Book, Evaluation, Market, MarketEvent, Source, Status
from midas.market_data.ctf import CTFVerifier
from midas.market_data.polymarket import PublicClient, normalize_market, now_ms
from midas.market_data.recording import Recorder
from midas.market_data.stream import BookState, MarketStream
from midas.paper.broker import AccountConfig, ExecutionModel, risk_state, summary
from midas.risk.engine import Limits, RiskState, assess
from midas.simulation.scenarios import run_scenario

from apps.api.config import Settings
from apps.api.paper import PaperBroker
from apps.api.storage import Store

log = structlog.get_logger()


class Service:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = Store(settings.database_url)
        self.recorder = Recorder(Path("data/recordings"), settings.recording_max_bytes)
        self.broker = PaperBroker(
            self.store,
            f"paper-{settings.mode}",
            AccountConfig(
                capital=settings.paper_capital,
                mode="synthetic" if settings.mode == "demo" else "live_shadow",
                execution=ExecutionModel.preset(settings.paper_execution_model),
                limits=settings.paper_limits,
            ),
        )
        self.verifier: CTFVerifier | None = None
        self.books = BookState()
        self.markets: dict[str, Market] = {}
        self.evaluations: dict[str, Evaluation] = {}
        self.events: deque[dict[str, Any]] = deque(maxlen=300)
        self.client: PublicClient | None = None
        self.stream = MarketStream(self.books, self.record, self.report)
        self.strategy = BinaryStrategy(max_age_ms=settings.max_data_age_ms)
        self.limits = Limits(max_age_ms=settings.max_data_age_ms)
        self.tasks: list[asyncio.Task[None]] = []
        self.simulation_slots = asyncio.Semaphore(2)
        self.pending_simulations = 0
        self.status = "STARTING"
        self.processing_latency_ms = 0.0
        self.last_refresh_ms: int | None = None
        self.recording_healthy = True
        self.retention_last_ms = 0
        self.started_ms = now_ms()
        self.last_settlement_poll_ms = 0

    async def report(self, severity: str, message: str, source: Source | None = None) -> None:
        event: dict[str, Any] = {
            "severity": severity,
            "message": message,
            "timestamp_ms": now_ms(),
            "source": (
                source or (Source.SYNTHETIC if self.settings.mode == "demo" else Source.LIVE)
            ).value,
        }
        self.events.appendleft(event)
        log.info("system_event", **event)
        try:
            await self.store.append(
                "event", severity, event["source"], event["timestamp_ms"], event
            )
        except Exception as error:
            self.status = "DEGRADED"
            log.error("event_persistence_failed", error=str(error))

    async def record(self, event: MarketEvent) -> None:
        try:
            await self.recorder.append(event)
            self.recording_healthy = True
        except OSError as error:
            self.recording_healthy = False
            self.status = "DEGRADED"
            await self.report("ERROR", f"Market recording halted: {error}")

    async def start(self) -> None:
        Path("data").mkdir(exist_ok=True)
        await self.store.initialize()
        await self.broker.start(now_ms())
        self.limits = self.limits.model_copy(
            update={"emergency_stop": self.broker.state["emergency_stop"]}
        )
        # Recover bounded incident history across restarts.
        rows = await self.store.recent("event", 100)
        self.events.extend(r["payload"] for r in rows)
        await self.report(
            "INFO", f"Midas started in {self.settings.mode.upper()} mode. Virtual orders only."
        )
        if self.settings.mode == "demo":
            await self.refresh_demo()
            self.tasks = [asyncio.create_task(self.loop())]
        else:
            self.client = PublicClient()
            self.verifier = CTFVerifier(self.settings.polygon_rpc_url)
            self.tasks = [asyncio.create_task(self.loop()), asyncio.create_task(self.stream.run())]

        self.tasks.append(asyncio.create_task(self.broker_loop()))

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.client:
            await self.client.close()
        if self.verifier:
            await self.verifier.close()
        await self.store.close()

    async def refresh_demo(self) -> None:
        ts = now_ms()
        for scenario_id in (
            "profitable",
            "unprofitable",
            "break_even",
            "fee_erased",
            "insufficient_liquidity",
            "missing_payout",
        ):
            fixture = await asyncio.to_thread(run_scenario, scenario_id, 7)
            market = Market.model_validate(fixture["initial_conditions"]["market"])
            self.markets[market.id] = market
            await self.store.append(
                "market", market.id, market.source.value, ts, market.model_dump(mode="json")
            )
            for raw in fixture["initial_conditions"]["books"].values():
                book = Book.model_validate(raw).model_copy(
                    update={"exchange_ts_ms": ts, "received_ts_ms": ts}
                )
                self.books.snapshot(book)
                await self.record(
                    MarketEvent(
                        event_id=f"demo:{ts}:{book.asset_id}",
                        kind="snapshot",
                        source=Source.SYNTHETIC,
                        received_ts_ms=ts,
                        exchange_ts_ms=ts,
                        asset_id=book.asset_id,
                        book=book,
                        raw=raw,
                    )
                )
        await self.scan()
        self.last_refresh_ms = ts
        self.status = "READY" if self.recording_healthy and self.store.healthy else "DEGRADED"

    async def refresh_live(self, metadata: bool) -> None:
        assert self.client is not None
        if metadata:
            raw_markets, wire = await self.client.discover_wire(
                max(self.settings.market_limit, self.settings.discovery_limit)
            )
            ts = now_ms()
            await self.record(
                MarketEvent(
                    event_id=f"gamma_batch:{ts}",
                    kind="metadata_bundle",
                    source=Source.LIVE,
                    received_ts_ms=ts,
                    raw={"markets": raw_markets},
                    raw_wire_json=wire,
                )
            )
            discovered: dict[str, Market] = {}
            selected = sorted(
                raw_markets,
                key=lambda r: not (r.get("version") == "v1" and r.get("negRisk") is False),
            )[: self.settings.market_limit]
            for raw in selected:
                try:
                    market = normalize_market(raw)
                    if market.protocol == "v1" and not market.negative_risk:
                        market, _ = await self.client.enrich(market)
                    assert self.verifier is not None
                    attestation = await self.verifier.verify(market)
                    market = market.model_copy(
                        update={
                            "attestation": attestation.model_dump(mode="json"),
                            "payout_verified": attestation.status == "VERIFIED_STRUCTURE",
                            "complementary_verified": attestation.status == "VERIFIED_STRUCTURE",
                            "payout_evidence": attestation.relationship,
                        }
                    )
                    await self.record(
                        MarketEvent(
                            event_id=f"attestation:{now_ms()}:{market.id}",
                            kind="attested_metadata",
                            source=Source.LIVE,
                            received_ts_ms=now_ms(),
                            raw={"market": market.model_dump(mode="json")},
                        )
                    )
                    discovered[market.id] = market
                    await self.store.append(
                        "market", market.id, "LIVE", now_ms(), market.model_dump(mode="json")
                    )
                    await self.record(
                        MarketEvent(
                            event_id=f"gamma:{now_ms()}:{market.id}",
                            kind="metadata",
                            source=Source.LIVE,
                            received_ts_ms=now_ms(),
                            raw=raw,
                        )
                    )
                except (ValueError, KeyError, TypeError, DecimalException) as error:
                    await self.report("WARNING", f"Rejected Gamma metadata: {error}")
            self.markets = discovered
            assets = {i.asset_id for m in discovered.values() for i in m.instruments}
            self.books.books = {a: b for a, b in self.books.books.items() if a in assets}
            self.evaluations = {k: e for k, e in self.evaluations.items() if k in discovered}
            await self.stream.subscribe(assets)
        failures = 0
        for market in self.markets.values():
            for instrument in market.instruments:
                try:
                    book, raw, wire = await self.client.book(
                        instrument.asset_id, market.condition_id
                    )
                    # REST responses arriving during deltas cannot prove continuity;
                    # each resulting book is a snapshot observation only.
                    self.books.snapshot(book)
                    await self.record(
                        MarketEvent(
                            event_id=f"rest:{book.received_ts_ms}:{book.asset_id}",
                            raw_wire_json=wire,
                            kind="snapshot",
                            source=Source.LIVE,
                            received_ts_ms=book.received_ts_ms,
                            exchange_ts_ms=book.exchange_ts_ms,
                            asset_id=book.asset_id,
                            book=book,
                            raw=raw,
                        )
                    )
                except Exception as error:
                    failures += 1
                    self.books.invalidate(instrument.asset_id, "REST refresh failed")
                    await self.report(
                        "WARNING", f"Snapshot refresh failed {instrument.asset_id}: {error}"
                    )
        await self.scan()
        self.last_refresh_ms = now_ms()
        self.status = (
            "READY"
            if not failures and self.recording_healthy and self.store.healthy
            else "DEGRADED"
        )

    async def scan(self) -> None:
        started = time.perf_counter()
        ts = now_ms()
        self.evaluations = await asyncio.to_thread(
            lambda: {
                m.id: self.strategy.evaluate(
                    m, dict(self.books.books), ts, self.settings.paper_capital
                )
                for m in self.markets.values()
            }
        )
        for e in self.evaluations.values():
            await self.store.append(
                "observation", e.market_id, e.source.value, ts, e.model_dump(mode="json")
            )
        if self.broker.healthy and self.recording_healthy and self.store.healthy:
            for m in self.markets.values():
                await self.broker.apply(
                    {
                        "id": f"observation:{ts}:{m.id}",
                        "kind": "observe",
                        "ts": ts,
                        "market": m.model_dump(mode="json"),
                        "books": {
                            a: b.model_dump(mode="json")
                            for a, b in self.books.books.items()
                            if a in {i.asset_id for i in m.instruments}
                        },
                    }
                )
        self.processing_latency_ms = (time.perf_counter() - started) * 1000

    async def broker_loop(self) -> None:
        while True:
            try:
                if self.broker.healthy and self.store.healthy and self.recording_healthy:
                    await self.broker.tick(now_ms(), self.books.books, self.markets)
                    if self.verifier and now_ms() - self.last_settlement_poll_ms > 60_000:
                        self.last_settlement_poll_ms = now_ms()
                        for position_id, item in list(self.broker.state["positions"].items()):
                            if item["exchange"]["settled"]:
                                continue
                            original = Market.model_validate(item["exchange"]["market"])
                            evidence = await self.verifier.resolution(original)
                            if evidence:
                                await self.record(
                                    MarketEvent(
                                        event_id=f"resolution:{position_id}",
                                        kind="verified_resolution",
                                        source=Source.LIVE,
                                        received_ts_ms=now_ms(),
                                        raw={
                                            "market_id": original.id,
                                            "resolution_evidence": evidence,
                                        },
                                    )
                                )
                                await self.broker.apply(
                                    {
                                        "id": f"settlement:{position_id}",
                                        "kind": "settle",
                                        "ts": now_ms(),
                                        "position": position_id,
                                        "resolution_evidence": evidence,
                                    }
                                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.status = "DEGRADED"
                await self.report("ERROR", f"Paper broker halted: {type(error).__name__}: {error}")
            await asyncio.sleep(0.1 if self.broker.state["pending"] else 1)

    async def loop(self) -> None:
        last_metadata = 0
        while True:
            try:
                ts = now_ms()
                if self.settings.mode == "demo":
                    await self.refresh_demo()
                else:
                    metadata = ts - last_metadata > self.settings.metadata_refresh_seconds * 1000
                    await self.refresh_live(metadata)
                    if metadata:
                        last_metadata = ts
                if ts - self.retention_last_ms > 3_600_000:
                    count = await self.store.prune(ts - self.settings.retention_days * 86_400_000)
                    self.retention_last_ms = ts
                    if count:
                        await self.report(
                            "INFO", f"Retention removed {count} expired database records"
                        )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.status = "DEGRADED"
                for asset in self.books.books:
                    self.books.invalidate(asset, "Refresh cycle failure")
                await self.report("ERROR", f"Refresh failed: {type(error).__name__}: {error}")
            await asyncio.sleep(self.settings.refresh_seconds)

    def current_evaluations(self) -> list[Evaluation]:
        # Re-evaluate at read time: a stalled worker cannot keep old VERIFIED labels.
        ts = now_ms()
        return [
            self.strategy.evaluate(m, self.books.books, ts, self.settings.paper_capital)
            for m in self.markets.values()
        ]

    def health_status(self, ts: int | None = None) -> str:
        ts = now_ms() if ts is None else ts
        if not self.store.healthy or not self.broker.healthy or not self.recording_healthy:
            return "DEGRADED"
        if any(
            not b.valid
            or max(ts - b.received_ts_ms, ts - (b.exchange_ts_ms or b.received_ts_ms))
            > self.settings.max_data_age_ms
            for b in self.books.books.values()
        ):
            return "DEGRADED"
        if self.settings.mode == "live" and self.stream.status != "CONNECTED":
            return "DEGRADED"
        return self.status

    async def state(self) -> dict[str, Any]:
        ts = now_ms()
        evaluations = self.current_evaluations()
        verified = [e for e in evaluations if e.status == Status.VERIFIED]
        ages = [
            max(ts - b.received_ts_ms, ts - b.exchange_ts_ms)
            if b.exchange_ts_ms is not None
            else ts - b.received_ts_ms
            for b in self.books.books.values()
        ]
        health = self.health_status(ts)
        runs = await self.store.recent("simulation", 20)
        # Runs are independent experiments, never a combined portfolio return.
        latest = runs[0]["payload"] if runs else None
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "mode": self.settings.mode,
            "source": "SYNTHETIC" if self.settings.mode == "demo" else "LIVE",
            "status": health,
            "connection": "OFFLINE_DEMO" if self.settings.mode == "demo" else self.stream.status,
            "timestamp_ms": ts,
            "markets": len(self.markets),
            "instruments": sum(len(m.instruments) for m in self.markets.values()),
            "books": len(self.books.books),
            "invalid_books": sum(not b.valid for b in self.books.books.values()),
            "oldest_book_age_ms": max(ages) if ages else None,
            "verified_opportunities": len(verified),
            "rejected_opportunities": len(evaluations) - len(verified),
            "potential_gross_profit": str(sum((e.gross_profit for e in verified), Decimal(0))),
            "potential_net_profit": str(sum((e.net_profit for e in verified), Decimal(0))),
            "virtual_starting_capital": str(self.settings.paper_capital),
            "paper_broker": {**summary(self.broker.state, ts), "healthy": self.broker.healthy},
            "latest_simulated_pnl": latest["portfolio"]["realized_pnl"] if latest else None,
            "latest_simulation": latest["scenario_id"] if latest else None,
            "unit": "virtual USD" if self.settings.mode == "demo" else "modeled pUSD",
            "warnings": sum(e["severity"] == "WARNING" for e in self.events),
            "errors": sum(e["severity"] == "ERROR" for e in self.events),
            "events": list(self.events)[:50],
            "telemetry": {
                "cpu_seconds": round(usage.ru_utime + usage.ru_stime, 3),
                "peak_memory_kib": usage.ru_maxrss,
                "broker_healthy": self.broker.healthy,
                "broker_pending_actions": len(self.broker.state["pending"]),
                "broker_processing_delay_ms": max(
                    (max(0, ts - p["due"]) for p in self.broker.state["pending"]), default=0
                ),
                "broker_recoveries": self.broker.state["recovery_count"],
                "scanner_markets_per_second": len(self.markets)
                / (self.processing_latency_ms / 1000)
                if self.processing_latency_ms
                else None,
                "uptime_seconds": (ts - self.started_ms) // 1000,
                "processing_latency_ms": round(self.processing_latency_ms, 3),
                "queue_depth": self.stream.queue.qsize(),
                "queue_capacity": self.stream.queue.maxsize,
                "reconnects": self.stream.reconnects,
                "pending_simulations": self.pending_simulations,
                "last_stream_message_ms": self.stream.last_message_ms,
                "database_healthy": self.store.healthy,
                "recording_healthy": self.recording_healthy,
                "last_refresh_ms": self.last_refresh_ms,
            },
            "safety": {
                "live_execution": False,
                "credentials_required": False,
                "emergency_stop": self.limits.emergency_stop,
            },
        }

    async def simulate(self, scenario_id: str, seed: int) -> dict[str, Any]:
        if self.limits.emergency_stop:
            raise ValueError("Emergency stop active; new simulation runs are blocked")
        if not self.store.healthy or not self.recording_healthy:
            raise ValueError("Persistence degraded; restore auditability before new runs")
        if self.pending_simulations >= 8:
            raise ValueError("Experiment queue full; retry after an existing run completes")
        self.pending_simulations += 1
        try:
            async with self.simulation_slots:
                if (
                    self.limits.emergency_stop
                    or not self.store.healthy
                    or not self.recording_healthy
                ):
                    raise ValueError("Virtual admission halted while experiment was queued")
                result = await asyncio.to_thread(run_scenario, scenario_id, seed)
                key = hashlib.sha256(f"{scenario_id}:{seed}:{now_ms()}".encode()).hexdigest()[:16]
                await self.store.append("simulation", key, "SYNTHETIC", now_ms(), result)
                if not result["passed"]:
                    root = Path("data/failures")
                    await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
                    import json

                    await asyncio.to_thread(
                        (root / f"{key}.json").write_text, json.dumps(result, indent=2)
                    )
                    await self.report(
                        "ERROR",
                        f"Scenario failed invariants: {scenario_id}; artifact {key}",
                        Source.SYNTHETIC,
                    )
                else:
                    await self.report(
                        "INFO", f"Scenario {scenario_id} passed; seed {seed}", Source.SYNTHETIC
                    )
                return result

        finally:
            self.pending_simulations -= 1

    def risk(self, evaluation: Evaluation) -> dict[str, Any]:
        state = (
            risk_state(self.broker.state, evaluation.market, now_ms())
            if evaluation.market and self.broker.state
            else RiskState()
        )
        limits = self.broker.config.limits.model_copy(
            update={
                "emergency_stop": self.limits.emergency_stop
                or self.broker.state.get("paused", False)
            }
        )
        return assess(evaluation, state, limits, now_ms()).model_dump(mode="json")
