"""Bounded local campaign orchestration with durable per-episode checkpoints."""

from __future__ import annotations

import concurrent.futures
import fcntl
import inspect
import json
import multiprocessing
import resource
import sqlite3
import stat
import subprocess
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.core.models import Model, Nonnegative
from midas.economics.attestation import digest
from midas.laboratory import VERSION
from midas.laboratory.adversarial import minimize, mutate_sequence
from midas.laboratory.datasets import load_dataset, replay_scenario, validate
from midas.laboratory.runtime import execute
from midas.laboratory.spec import FAMILIES, Costs, Scenario, generate
from midas.paper.broker import AccountConfig, ExecutionModel
from midas.risk.engine import Limits

PRESETS = {"Quick": 32, "Standard": 1000, "Deep": 10_000, "Extreme": 1_000_000}


def archive_bytes(root: Path) -> int:
    """Count present files, allowing SQLite sidecars to vanish during a scan."""
    total = 0
    for path in root.rglob("*"):
        try:
            metadata = path.stat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(metadata.st_mode):
            total += metadata.st_size
    return total


class CampaignSpec(Model):
    preset: Literal["Quick", "Standard", "Deep", "Extreme"] = "Quick"
    runs: int = Field(default=32, ge=1, le=1_000_000)
    seed: int = Field(default=7, ge=0, le=2**32 - 1)
    families: tuple[str, ...] = ("calm", "volatile", "one_sided", "unresolved")
    strategies: tuple[Literal["arbitrage", "conservative", "no_trade"], ...] = ("arbitrage",)
    models: tuple[Literal["optimistic", "standard", "conservative"], ...] = ("standard",)
    dataset_id: str | None = None
    dataset_hash: str | None = None
    dataset_manifest_hash: str | None = None
    workers: int = Field(default=1, ge=1, le=4)
    memory_mb: int = Field(default=512, ge=256, le=2048)
    max_wall_seconds: int = Field(default=300, ge=1, le=86_400)
    max_disk_mb: int = Field(default=128, ge=8, le=2048)
    retain_successes: int = Field(default=3, ge=0, le=100)
    observation_latency_ms: int = Field(default=0, ge=0, le=60_000)
    submission_latency_ms: int | None = Field(default=None, ge=0, le=60_000)
    liquidity_fraction: Nonnegative | None = Field(default=None, le=1)
    fee_rate: Nonnegative | None = Field(default=None, le=1)
    capital: Nonnegative = Field(default=Decimal("100"), gt=0)
    limits: Limits = AccountConfig().limits
    costs: Costs = Costs()
    adversarial: bool = False

    @model_validator(mode="after")
    def supported(self) -> CampaignSpec:
        if not self.families or set(self.families) - set(FAMILIES):
            raise ValueError("Select known scenario families")
        if (
            not self.models
            or not self.strategies
            or len(set(self.models)) != len(self.models)
            or len(set(self.strategies)) != len(self.strategies)
        ):
            raise ValueError("Strategies and models must be nonempty and unique")
        if self.runs > 10_000 and self.preset != "Extreme":
            raise ValueError("Large campaigns require the explicit Extreme preset")
        if self.dataset_id and self.fee_rate is not None:
            raise ValueError("Recorded fee evidence cannot be overridden")
        return self


def revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def code_hash() -> str:
    root = Path(__file__).resolve().parents[3]
    paths = sorted((root / "packages/midas").rglob("*.py"))
    # Arena training modules cannot affect Laboratory execution. Keep research-only
    # additions out of old campaign identities so their reproduction remains valid.
    paths = [
        p
        for p in paths
        if p.resolve() != Path(__file__).resolve()
        and "arena" not in p.relative_to(root / "packages/midas").parts
    ]
    campaign_logic = [
        (name, digest(inspect.getsource(value)))
        for name, value in (
            ("CampaignSpec", CampaignSpec),
            ("plan", plan),
            ("run_group", run_group),
        )
    ]
    return digest(
        {
            "version": "midas-laboratory-execution-v1",
            "runtime_modules": [
                (str(path.relative_to(root)), digest(path.read_text())) for path in paths
            ],
            "campaign_logic": campaign_logic,
        }
    )


def plan(spec: CampaignSpec, index: int, datasets: Path) -> list[Scenario]:
    seed = (spec.seed + index) % 2**32
    family = spec.families[index % len(spec.families)]
    scenarios = []
    for strategy in spec.strategies:
        for model_name in spec.models:
            execution = ExecutionModel.preset(model_name).model_copy(update={"seed": seed})
            if spec.submission_latency_ms is not None:
                execution = execution.model_copy(update={"latency_ms": spec.submission_latency_ms})
            if spec.liquidity_fraction is not None:
                execution = execution.model_copy(
                    update={"liquidity_fraction": spec.liquidity_fraction}
                )
            account = AccountConfig(capital=spec.capital, execution=execution, limits=spec.limits)
            if spec.dataset_id:
                path, manifest = load_dataset(datasets, spec.dataset_id)
                if (
                    spec.dataset_hash != manifest.content_sha256
                    or spec.dataset_manifest_hash != digest(manifest.model_dump(mode="json"))
                ):
                    raise ValueError("Archived dataset hash no longer matches")
                scenario = replay_scenario(path, manifest, account, spec.observation_latency_ms)
            else:
                generated = generate(family, seed, execution)
                if family == "low_capital":
                    account = account.model_copy(
                        update={"capital": min(account.capital, generated.account.capital)}
                    )
                scenario = generated.model_copy(update={"account": account})
                if spec.fee_rate is not None:
                    market = scenario.market.model_copy(
                        update={
                            "fee": scenario.market.fee.model_copy(update={"rate": spec.fee_rate})
                        }
                    )
                    scenario = scenario.model_copy(update={"market": market})
                if spec.adversarial:
                    scenario = mutate_sequence(scenario, seed)
            scenarios.append(
                scenario.model_copy(
                    update={
                        "strategy": strategy,
                        "observation_latency_ms": spec.observation_latency_ms,
                        "costs": spec.costs,
                    }
                )
            )
    return scenarios


def worker_limit(memory_mb: int) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024**2, memory_mb * 1024**2))


def run_group(spec_data: dict[str, Any], index: int, dataset_root: str) -> list[dict[str, Any]]:
    spec = CampaignSpec.model_validate(spec_data)
    results = []
    for scenario in plan(spec, index, Path(dataset_root)):
        started = time.time()
        result = execute(scenario, retain=index < spec.retain_successes)
        incident = minimize(scenario) if not result["passed"] else None
        if incident:
            # Failure logs are always regenerated in full even when successes are compact.
            result = execute(scenario, retain=True)
        if incident:
            incident["first_observed_at"] = started
        result["runtime"]["started_at"] = started
        result["runtime"]["completed_at"] = time.time()
        result["runtime"]["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        results.append(
            {
                "variant": f"{scenario.strategy}/{scenario.account.execution.name}",
                "result": result,
                "incident": incident,
            }
        )
    return results


class Campaigns:
    def __init__(self, root: Path, datasets: Path, read_only: bool = False) -> None:
        self.root, self.datasets = root, datasets
        self.read_only = read_only
        root.mkdir(parents=True, exist_ok=True)
        self.db = root / "laboratory.sqlite"
        self.threads: dict[str, threading.Thread] = {}
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.lease = None if read_only else (root / "owner.lock").open("a+")
        if self.lease:
            try:
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                self.lease.close()
                raise ValueError("Another laboratory writer owns this directory") from error
        if read_only:
            if not self.db.exists():
                raise ValueError("Laboratory archive not found")
            return
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, status TEXT, spec TEXT, created REAL, updated REAL, revision TEXT, code_hash TEXT, elapsed REAL DEFAULT 0, error TEXT, peak_rss_mb REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS runs(campaign TEXT, idx INTEGER, variant TEXT, id TEXT UNIQUE, passed INTEGER, pnl REAL, result TEXT, artifact TEXT, incident TEXT, events INTEGER, PRIMARY KEY(campaign,idx,variant));
            CREATE INDEX IF NOT EXISTS runs_campaign ON runs(campaign,idx);
            """)
            columns = {r[1] for r in c.execute("PRAGMA table_info(runs)")}
            if "events" not in columns:
                c.execute("ALTER TABLE runs ADD COLUMN events INTEGER")
                c.execute("UPDATE runs SET events=json_extract(result, '$.event_count')")
            c.execute("PRAGMA user_version=1")
            c.execute("UPDATE campaigns SET status='INTERRUPTED' WHERE status='RUNNING'")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        c = (
            sqlite3.connect(f"file:{self.db}?mode=ro", uri=True, timeout=10)
            if self.read_only
            else sqlite3.connect(self.db, timeout=10)
        )
        c.row_factory = sqlite3.Row
        if not self.read_only:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=FULL")
        try:
            with c:
                yield c
        finally:
            c.close()

    def create(self, spec: CampaignSpec, launch: bool = True) -> dict[str, Any]:
        if self.read_only:
            raise ValueError("Archive reader cannot create campaigns")
        if spec.dataset_id:
            path, manifest = load_dataset(self.datasets, spec.dataset_id)
            validate(path, manifest)
            spec = spec.model_copy(
                update={
                    "dataset_hash": manifest.content_sha256,
                    "dataset_manifest_hash": digest(manifest.model_dump(mode="json")),
                }
            )
        with self.connect() as c:
            if (
                c.execute("SELECT count(*) FROM campaigns WHERE status='RUNNING'").fetchone()[0]
                >= 2
            ):
                raise ValueError("Two campaigns are already active")
            id = uuid.uuid4().hex
            now = time.time()
            c.execute(
                "INSERT INTO campaigns(id,status,spec,created,updated,revision,code_hash) VALUES(?,?,?,?,?,?,?)",
                (id, "READY", spec.model_dump_json(), now, now, revision(), code_hash()),
            )
        if launch:
            self.launch(id)
        return self.get(id)

    def launch(self, id: str) -> None:
        if self.read_only:
            raise ValueError("Archive reader cannot launch campaigns")
        with self.lock:
            if id in self.threads and self.threads[id].is_alive():
                raise ValueError("Campaign is already executing; retry after it pauses")
            row = self.get(id)
            if row["status"] == "COMPLETED":
                raise ValueError("Completed campaigns are immutable")
            if row["code_hash"] != code_hash():
                raise ValueError(
                    "Code changed; archived campaign is not resumable under this implementation"
                )
            with self.connect() as c:
                active = c.execute(
                    "SELECT count(*) FROM campaigns WHERE status='RUNNING'"
                ).fetchone()[0]
                if active >= 2:
                    raise ValueError("Active campaign resource limit")
                c.execute(
                    "UPDATE campaigns SET status='RUNNING',updated=?,error=NULL WHERE id=?",
                    (time.time(), id),
                )
            thread = threading.Thread(target=self._drive, args=(id,), daemon=True)
            self.threads[id] = thread
            thread.start()

    def control(self, id: str, action: str) -> dict[str, Any]:
        if self.read_only:
            raise ValueError("Archive reader cannot control campaigns")
        if action == "resume":
            self.launch(id)
        elif action in {"pause", "cancel"}:
            self.get(id)
            with self.connect() as c:
                c.execute(
                    "UPDATE campaigns SET status=?,updated=? WHERE id=? AND status!='COMPLETED'",
                    ("PAUSED" if action == "pause" else "CANCELLED", time.time(), id),
                )
        else:
            raise ValueError("Unknown campaign control")
        return self.get(id)

    def _drive(self, id: str) -> None:
        began = time.perf_counter()
        elapsed = 0.0
        try:
            row = self.get(id)
            spec = CampaignSpec.model_validate(row["spec"])
            elapsed = row["elapsed_seconds"]
            with self.connect() as c:
                completed = {
                    r[0] for r in c.execute("SELECT DISTINCT idx FROM runs WHERE campaign=?", (id,))
                }
            pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=spec.workers,
                mp_context=multiprocessing.get_context("spawn"),
                initializer=worker_limit,
                initargs=(spec.memory_mb,),
            )
            try:
                # Bounded batches: at most workers outstanding episodes, never millions of futures.
                indices = (i for i in range(spec.runs) if i not in completed)
                while not self.stopping.is_set() and self._current_status(id) == "RUNNING":
                    if elapsed + time.perf_counter() - began > spec.max_wall_seconds:
                        self._status(id, "INTERRUPTED", "Wall-clock resource budget reached")
                        break
                    # Include DB, WAL and all detailed artifacts in the explicit disk budget.
                    if archive_bytes(self.root) > spec.max_disk_mb * 1024**2:
                        self._status(id, "INTERRUPTED", "Laboratory disk budget reached")
                        break
                    batch = []
                    for _ in range(spec.workers):
                        i = next(indices, None)
                        if i is not None:
                            batch.append(i)
                    if not batch:
                        self._status(id, "COMPLETED")
                        break
                    jobs = (
                        [
                            (
                                i,
                                pool.submit(
                                    run_group, spec.model_dump(mode="json"), i, str(self.datasets)
                                ),
                            )
                            for i in batch
                        ]
                        if pool
                        else []
                    )
                    for i in batch:
                        results = (
                            next(f for j, f in jobs if j == i).result()
                            if pool
                            else run_group(spec.model_dump(mode="json"), i, str(self.datasets))
                        )
                        self._commit(id, i, results)
                        self._progress(id, elapsed + time.perf_counter() - began)
            finally:
                if pool:
                    pool.shutdown(wait=True, cancel_futures=True)
            if self.stopping.is_set() and self._current_status(id) == "RUNNING":
                self._status(id, "INTERRUPTED", "Service shutdown; committed episodes retained")
        except Exception as error:
            self._status(id, "FAILED", f"{type(error).__name__}: {error}")
        finally:
            self._progress(id, elapsed + time.perf_counter() - began)

    def _current_status(self, id: str) -> str:
        with self.connect() as c:
            return str(c.execute("SELECT status FROM campaigns WHERE id=?", (id,)).fetchone()[0])

    def _progress(self, id: str, elapsed: float) -> None:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        with self.connect() as c:
            c.execute(
                "UPDATE campaigns SET elapsed=?,updated=?,peak_rss_mb=? WHERE id=?",
                (elapsed, time.time(), rss, id),
            )

    def _status(self, id: str, status: str, error: str | None = None) -> None:
        with self.connect() as c:
            c.execute(
                "UPDATE campaigns SET status=?,error=?,updated=? WHERE id=? AND status='RUNNING'",
                (status, error, time.time(), id),
            )

    def _commit(self, campaign: str, index: int, results: list[dict[str, Any]]) -> None:
        with self.connect() as c:
            for item in results:
                full = item["result"]
                id = digest([campaign, index, item["variant"]])[:32]
                artifact = full if full["journal"] else None
                compact = {
                    k: full[k]
                    for k in (
                        "simulator_version",
                        "strategy_version",
                        "scenario_hash",
                        "seed",
                        "dataset_id",
                        "dataset_hash",
                        "data_source",
                        "execution_certainty",
                        "economically_verified",
                        "complete",
                        "event_count",
                        "passed",
                        "classification",
                        "errors",
                        "metrics",
                        "result_hash",
                    )
                }
                compact["journal_hash"] = full["journal_hash"] if artifact else None
                compact["runtime"] = full["runtime"]
                existing = c.execute("SELECT result FROM runs WHERE id=?", (id,)).fetchone()
                if existing and json.loads(existing[0])["result_hash"] != full["result_hash"]:
                    raise ValueError("Conflicting experiment identity; archive remains immutable")
                c.execute(
                    "INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        campaign,
                        index,
                        item["variant"],
                        id,
                        int(full["passed"]),
                        float(full["metrics"]["net_simulated_pnl"]),
                        json.dumps(compact),
                        json.dumps(artifact) if artifact else None,
                        json.dumps(item["incident"]) if item["incident"] else None,
                        full["event_count"],
                    ),
                )

    def get(self, id: str) -> dict[str, Any]:
        with self.connect() as c:
            row = c.execute("SELECT * FROM campaigns WHERE id=?", (id,)).fetchone()
            if row is None:
                raise KeyError("Campaign not found")
            aggregate = c.execute(
                "SELECT count(*),coalesce(sum(passed),0),count(DISTINCT idx),min(CASE WHEN passed THEN pnl END),max(CASE WHEN passed THEN pnl END),avg(CASE WHEN passed THEN pnl END),coalesce(sum(events),0) FROM runs WHERE campaign=?",
                (id,),
            ).fetchone()
            events = aggregate[6]
        spec = json.loads(row["spec"])
        total = spec["runs"] * len(spec["strategies"]) * len(spec["models"])
        return {
            "id": id,
            "status": row["status"],
            "spec": spec,
            "created": row["created"],
            "updated": row["updated"],
            "code_revision": row["revision"],
            "code_hash": row["code_hash"],
            "simulator_version": VERSION,
            "completed": aggregate[0],
            "episodes_completed": aggregate[2],
            "total": total,
            "remaining": total - aggregate[0],
            "passed": aggregate[1],
            "failed": aggregate[0] - aggregate[1],
            "error": row["error"],
            "elapsed_seconds": row["elapsed"],
            "runs_per_second": aggregate[0] / row["elapsed"] if row["elapsed"] else 0,
            "events": events,
            "events_per_second": events / row["elapsed"] if row["elapsed"] else 0,
            "worst_pnl": aggregate[3],
            "best_pnl": aggregate[4],
            "mean_pnl": aggregate[5],
            "process_peak_rss_mb": row["peak_rss_mb"],
            "resource_note": "Coordinator lifetime peak RSS; worker limits apply separately",
            "economically_verified": False,
        }

    def all(self) -> list[dict[str, Any]]:
        with self.connect() as c:
            ids = [
                r[0] for r in c.execute("SELECT id FROM campaigns ORDER BY created DESC LIMIT 100")
            ]
        return [self.get(id) for id in ids]

    def runs(self, id: str, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT id,idx,variant,result,incident FROM runs WHERE campaign=? ORDER BY idx,variant LIMIT ? OFFSET ?",
                (id, min(200, max(1, limit)), max(0, offset)),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "index": r["idx"],
                "variant": r["variant"],
                "result": json.loads(r["result"]),
                "incident": json.loads(r["incident"]) if r["incident"] else None,
            }
            for r in rows
        ]

    def artifact(self, id: str) -> dict[str, Any]:
        with self.connect() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (id,)).fetchone()
        if row is None:
            raise KeyError("Experiment not found")
        campaign = self.get(row["campaign"])
        compact = json.loads(row["result"])
        code_matches = campaign["code_hash"] == code_hash()
        if not code_matches and row["artifact"]:
            full = json.loads(row["artifact"])
        else:
            scenarios = plan(
                CampaignSpec.model_validate(campaign["spec"]), row["idx"], self.datasets
            )
            scenario = next(
                s for s in scenarios if f"{s.strategy}/{s.account.execution.name}" == row["variant"]
            )
            full = json.loads(row["artifact"]) if row["artifact"] else execute(scenario)
            if full["result_hash"] != compact["result_hash"]:
                raise ValueError(
                    "Archived experiment no longer reproduces under the current simulator"
                )
        core = {
            k: v
            for k, v in full.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if digest(core) != full["result_hash"]:
            raise ValueError("Archived result integrity mismatch")
        if digest(full["journal"]) != full.get("journal_hash") or (
            compact.get("journal_hash") and full["journal_hash"] != compact["journal_hash"]
        ):
            raise ValueError("Archived event journal integrity mismatch")
        return {
            "run_id": id,
            "campaign_id": row["campaign"],
            "index": row["idx"],
            "variant": row["variant"],
            "code_revision": campaign["code_revision"],
            "code_hash": campaign["code_hash"],
            "result": full,
            "incident": json.loads(row["incident"]) if row["incident"] else None,
            "reproduction": f".venv/bin/python scripts/laboratory.py reproduce --root {self.root} --run {id}",
        }

    def incidents(self) -> list[dict[str, Any]]:
        with self.connect() as c:
            rows = c.execute(
                "SELECT id,campaign,idx,incident FROM runs WHERE incident IS NOT NULL ORDER BY rowid DESC LIMIT 100"
            ).fetchall()
        keys = (
            "id",
            "severity",
            "component",
            "classification",
            "invariant",
            "status",
            "expected",
            "actual",
            "original_events",
            "minimized_events",
            "single_deletion_minimal",
            "reproduction",
            "regression_reference",
            "financial_consequence",
            "first_observed_at",
        )
        return [
            {
                "run_id": r["id"],
                "campaign_id": r["campaign"],
                "index": r["idx"],
                **{k: v for k, v in json.loads(r["incident"]).items() if k in keys},
            }
            for r in rows
        ]

    def close(self) -> None:
        self.stopping.set()
        for thread in self.threads.values():
            thread.join(timeout=10)
        if self.lease and not any(t.is_alive() for t in self.threads.values()):
            fcntl.flock(self.lease, fcntl.LOCK_UN)
            self.lease.close()
