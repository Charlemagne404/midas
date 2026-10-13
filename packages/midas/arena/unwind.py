"""Observable residual-only interventions through the actual local broker ledger."""

import random
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arena.recovery import RecoveryEnvironment, RecoverySpec
from midas.arena.recovery import assess as assess_repair
from midas.core.models import Book, Market, Model, Source
from midas.economics.attestation import digest, fingerprint
from midas.laboratory.spec import Scenario
from midas.paper.broker import serial
from midas.risk.engine import Limits
from midas.simulation.exchange import Exchange, SellOrder

D = Decimal
VERSION = "bounded-inventory-unwind-1"


class UnwindSpec(Model):
    policy: Literal["hold", "complete_missing", "sell_residual"] = "hold"
    min_bid: Decimal = Field(default=D(".05"), gt=0, lt=1, allow_inf_nan=False)
    max_shares: Decimal = Field(default=D("20"), gt=0, le=1000, allow_inf_nan=False)
    repair: RecoverySpec = RecoverySpec(policy="complete_missing")

    @model_validator(mode="after")
    def repair_control(self) -> "UnwindSpec":
        if self.repair.policy != "complete_missing":
            raise ValueError("Repair control must complete the missing leg")
        return self


class UnwindStudySpec(Model):
    version: Literal["bounded-inventory-unwind-1"] = "bounded-inventory-unwind-1"
    episodes: int = Field(default=60, ge=30, le=300)
    seed: int = Field(default=393071, ge=0, le=2**32 - 20000)
    unwind: UnwindSpec = UnwindSpec(policy="sell_residual")

    @model_validator(mode="after")
    def sell_candidate(self) -> "UnwindStudySpec":
        if self.unwind.policy != "sell_residual":
            raise ValueError("Study requires a residual sell candidate and separate controls")
        return self


def risk_reasons(exchange: Exchange, portfolio: dict[str, Any]) -> list[str]:
    limits = Limits.model_validate(portfolio["risk_limits"])
    reasons = []
    if exchange.settled or exchange.emergency_stop or limits.emergency_stop:
        reasons.append("Position settled or stopped")
    for field, limit in (
        ("max_drawdown", limits.max_drawdown),
        ("daily_loss", limits.max_daily_loss),
        ("cumulative_loss", limits.max_cumulative_loss),
    ):
        value = D(str(portfolio[field]))
        if value > 0 and value >= limit:
            reasons.append(f"Existing {field} cutoff")
    for value, limit, name in (
        (D(str(portfolio["gross_exposure"])), limits.max_exposure, "overall"),
        (
            exchange.portfolio.locked + exchange.portfolio.reserved,
            limits.max_market_exposure,
            "market",
        ),
        (
            exchange.portfolio.locked + exchange.portfolio.reserved,
            limits.max_event_exposure,
            "event",
        ),
        (exchange.portfolio.locked, limits.max_unmatched_exposure, "unmatched capital"),
    ):
        if value > limit:
            reasons.append(f"Existing {name} exposure cutoff")
    return reasons


def assess_sell(
    exchange: Exchange,
    market: Market,
    books: dict[str, Book],
    portfolio: dict[str, Any],
    spec: UnwindSpec,
    now_ms: int,
) -> dict[str, Any]:
    """No future-event/scenario input; protect matched shares and add no capital."""
    assets = [i.asset_id for i in exchange.market.instruments]
    if len(assets) != 2:
        raise ValueError("Unwind requires a binary position")
    quantities = [exchange.portfolio.positions.get(a, D(0)) for a in assets]
    residual = abs(quantities[0] - quantities[1])
    asset = assets[0 if quantities[0] > quantities[1] else 1]
    limits = Limits.model_validate(portfolio["risk_limits"])
    reasons = risk_reasons(exchange, portfolio)
    if not exchange.orders or any(
        not o.acknowledged or o.status not in {"FILLED", "EXPIRED", "CANCELLED", "REJECTED"}
        for o in exchange.orders.values()
    ):
        reasons.append("Initial order outcomes are not confirmed terminal")
    if (
        fingerprint(market) != fingerprint(exchange.market)
        or market.source != Source.SYNTHETIC
        or not market.active
        or market.closed
        or not market.accepting_orders
    ):
        reasons.append("Observed market identity or eligibility changed")
    if not market.fee.verified or market.fee.exponent != 1 or not market.payout_verified:
        reasons.append("Unverified payout or fee evidence")
    book = books.get(asset)
    if (
        book is None
        or not book.valid
        or book.asset_id != asset
        or book.condition_id != market.condition_id
        or book.source != market.source
        or book.received_ts_ms > now_ms
        or book.exchange_ts_ms is None
        or book.exchange_ts_ms > now_ms
        or now_ms - book.received_ts_ms > limits.max_age_ms
        or now_ms - book.exchange_ts_ms > limits.max_age_ms
    ):
        reasons.append("Missing, invalid or stale observed unwind book")
    quantity, price = D(0), D(0)
    reserved = sum(
        (
            o.inventory_reservation
            for o in exchange.orders.values()
            if isinstance(o, SellOrder) and o.asset_id == asset
        ),
        D(0),
    )
    if book and book.bids and residual > 0:
        levels = sorted(book.bids, key=lambda level: level.price, reverse=True)
        floor = max(spec.min_bid, levels[0].price * (1 - limits.max_slippage))
        depth = D(0)
        for level in levels:
            if level.price < floor:
                continue
            depth += level.size
            q = min(max(D(0), residual - reserved), spec.max_shares, depth).quantize(
                D(".01"), rounding=ROUND_FLOOR
            )
            minimum = (
                q * level.price >= book.min_order_size
                if book.minimum_unit == "notional"
                else q >= book.min_order_size
            )
            if q > quantity and minimum:
                quantity, price = q, level.price
    if quantity <= 0:
        reasons.append("Residual inventory or eligible observed bid depth is insufficient")
    return {
        "allowed": not reasons,
        "reasons": reasons or ["Residual-only sale within owned shares"],
        "side": "SELL",
        "asset_id": asset,
        "quantity": str(quantity),
        "limit": str(price),
        "residual_before": str(residual),
        "matched_before": str(min(quantities)),
        "reserved_bound": "0",
        "additional_external_capital": "0",
        "decision_time_ms": now_ms,
        "interpretation": "Requested quantity reduces residual shares if filled; no P&L or fill guarantee.",
    }


class UnwindEnvironment(RecoveryEnvironment):
    def __init__(self, scenario: Scenario, spec: UnwindSpec, retain: bool = True):
        self.unwind_spec = spec
        self.intervention_decided = False
        self.intervention_decisions: list[dict[str, Any]] = []
        super().__init__(scenario, RecoverySpec(policy="hold"), retain)

    def reset(self) -> dict[str, Any]:
        self.intervention_decided = False
        self.intervention_decisions = []
        return super().reset()

    def _apply(self, command: dict[str, Any]) -> None:
        action = next(
            (a for a in self.state["pending"] if a["id"] == command.get("action_id")), None
        )
        if action and ":intervention:" in action["order"] and action["kind"] in {"submit", "match"}:
            exchange = Exchange.restore(self.state["positions"][action["position"]]["exchange"])
            reasons = risk_reasons(exchange, self.portfolio())
            if self.state["paused"] or self.state["emergency_stop"]:
                reasons.append("Paper account paused or stopped")
            if reasons:
                exchange.cancel(action["order"], command["ts"])
                self.state["positions"][action["position"]]["exchange"] = serial(
                    exchange.checkpoint()
                )
                self.state["pending"] = [
                    a for a in self.state["pending"] if a["order"] != action["order"]
                ]
                command["intervention_admission"] = {"allowed": False, "reasons": reasons}
        super()._apply(command)
        for position in self.state["positions"].values():
            exchange = Exchange.restore(position["exchange"])
            if not exchange.sales_enabled:
                exchange.enable_sales()
                position["exchange"] = serial(exchange.checkpoint())

    def _process(self, event: Any) -> dict[str, Any] | None:
        if event.kind == "checkpoint" and event.payload.get("intervention_order"):
            proposal = event.payload["intervention_order"]
            order = proposal["position"] + ":intervention:1"
            if any(a["order"] == order for a in self.state["pending"]):
                raise ValueError("Duplicate intervention scheduling")
            model = self.scenario.account.execution
            assets = [i.asset_id for i in self.scenario.market.instruments]
            rng = random.Random(model.seed)
            jitters = [
                rng.randint(0, model.jitter_ms) if model.distribution == "uniform" else 0
                for _ in assets
            ]
            index = assets.index(proposal["asset_id"])
            due = (
                event.time
                + model.latency_ms
                + model.taker_delay_ms
                + (self.scenario.market.execution_delay_ms or 0)
                + jitters[index]
                + index
            )
            for kind, timestamp in (
                ("submit", due),
                ("match", due + model.processing_ms),
                ("ack", due + model.processing_ms + model.ack_delay_ms + 1),
            ):
                identity = f"{order}:{kind}"
                self.state["pending"].append(
                    {
                        "id": identity,
                        "kind": kind,
                        "due": timestamp,
                        "position": proposal["position"],
                        "order": order,
                        "asset": proposal["asset_id"],
                        "quantity": proposal["quantity"],
                        "limit": proposal["limit"],
                        "side": proposal["side"],
                    }
                )
                self.clock.schedule(timestamp, identity, "action", {"action_id": identity}, 20)
            return {"kind": "intervention_request", "ts": event.time, "id": event.id, **proposal}
        command = super()._process(event)
        if (
            event.kind == "decision"
            and self.unwind_spec.policy != "hold"
            and not self.intervention_decided
            and self.state["positions"]
        ):
            position = next(iter(self.state["positions"]))
            if any(a["position"] == position for a in self.state["pending"]):
                return command
            self.intervention_decided = True
            exchange = Exchange.restore(self.state["positions"][position]["exchange"])
            observation = self.observe()
            market = Market.model_validate(observation["market"])
            books = {a: Book.model_validate(b) for a, b in observation["books"].items()}
            if self.unwind_spec.policy == "sell_residual":
                proposal = assess_sell(
                    exchange, market, books, self.portfolio(), self.unwind_spec, event.time
                )
            else:
                proposal = assess_repair(
                    exchange,
                    market,
                    books,
                    self.portfolio(),
                    self.scenario,
                    self.unwind_spec.repair,
                    event.time,
                )
                proposal["side"] = "BUY"
            if self.state["paused"] or self.state["emergency_stop"]:
                proposal["allowed"] = False
                proposal["reasons"].append("Paper account paused or stopped")
            proposal.update(
                position=position,
                observed_market=market.model_dump(mode="json"),
                observed_books={a: b.model_dump(mode="json") for a, b in books.items()},
                owned_checkpoint=serial(exchange.checkpoint()),
                decision_portfolio=self.portfolio(),
            )
            proposal["evidence_sha256"] = digest(
                {k: v for k, v in proposal.items() if k != "evidence_sha256"}
            )
            self.intervention_decisions.append(proposal)
            if proposal["allowed"]:
                self.clock.schedule(
                    event.time,
                    position + ":intervention-request",
                    "checkpoint",
                    {"intervention_order": proposal},
                    11,
                )
        return command


def execute(scenario: Scenario, spec: UnwindSpec) -> dict[str, Any]:
    environment = UnwindEnvironment(scenario, spec)
    result = environment.run()
    if not result["passed"] or not result["complete"]:
        raise ValueError(f"Invalid unwind accounting: {result['errors']}")
    return {
        "runner_version": VERSION,
        "specification": spec.model_dump(mode="json"),
        "intervention_decisions": environment.intervention_decisions,
        "result": result,
    }


def run_study(root: Any, spec: UnwindStudySpec, progress: Any = None) -> dict[str, Any]:
    import json
    import math
    import time
    import uuid
    from pathlib import Path

    import numpy as np

    from midas.arena.artifacts import artifact_path, atomic_json, atomic_replay, sha256
    from midas.arena.datasets import research_hash
    from midas.laboratory.runtime import Environment
    from midas.laboratory.spec import generate
    from midas.paper.broker import ExecutionModel

    root = Path(root)
    for kind in ("datasets", "tournaments", "recoveries", "unwinds"):
        for path in (root / kind).glob("*/manifest.json"):
            record = json.loads(path.read_text())
            source = record["spec"] if kind == "datasets" else record["configuration"]
            if kind == "tournaments":
                source = source.get("challenge")
            if (
                source
                and spec.seed < source["seed"] + source["episodes"]
                and source["seed"] < spec.seed + spec.episodes
            ):
                raise ValueError("Unwind seeds overlap existing research")
    identity = "unwind-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "unwinds", identity)
    if progress and getattr(progress, "register", None):
        progress.register("unwinds", identity)
    source_hash = research_hash()
    atomic_json(
        directory / "preparing.json",
        {"configuration": spec.model_dump(mode="json"), "source_hash": source_hash},
    )
    families = ("thin", "deep", "calm", "liquidity_shock", "volatile", "one_sided", "disappearing")
    policies = ("no_trade", "hold", "complete_missing", "sell_residual")
    rows: list[dict[str, Any]] = []
    report: dict[str, Any]
    for index in range(spec.episodes):
        for execution in ("optimistic", "standard", "conservative"):
            scenario = generate(
                families[index % 7],
                spec.seed + index,
                ExecutionModel.preset(execution).model_copy(update={"seed": spec.seed + index}),
            )
            for policy in policies:
                began = time.monotonic()
                if policy == "no_trade":
                    result = Environment(scenario.model_copy(update={"strategy": "no_trade"})).run()
                    report = {
                        "runner_version": VERSION,
                        "intervention_decisions": [],
                        "result": result,
                    }
                else:
                    report = execute(scenario, spec.unwind.model_copy(update={"policy": policy}))
                    result = report["result"]
                if not result["passed"] or not result["complete"]:
                    raise ValueError("Unwind comparison contains invalid accounting")
                orders = [
                    o
                    for p in result["final_portfolio"]["positions"]
                    for o in p["orders"]
                    if ":intervention:" in o["id"]
                ]
                row = {
                    "id": f"{index}-{execution}-{policy}",
                    "base_episode_id": f"{families[index % 7]}:{spec.seed + index}",
                    "family": families[index % 7],
                    "seed": spec.seed + index,
                    "execution_model": execution,
                    "policy": policy,
                    "passed": result["passed"],
                    "metrics": result["metrics"],
                    "intervention_requests": sum(
                        p["allowed"] for p in report["intervention_decisions"]
                    ),
                    "intervention_orders": len(orders),
                    "intervention_filled_shares": str(
                        sum((D(o["quantity"]) - D(o["remaining"]) for o in orders), D(0))
                    ),
                    "result_hash": result["result_hash"],
                    "journal_hash": result["journal_hash"],
                    "runtime_seconds": time.monotonic() - began,
                }
                rows.append(row)
                atomic_replay(directory / "replays" / (row["id"] + ".json"), {"row": row, **report})
                if progress:
                    progress(len(rows), spec.episodes * 12)
    indexed = {
        policy: {
            (r["base_episode_id"], r["execution_model"]): r for r in rows if r["policy"] == policy
        }
        for policy in policies
    }
    comparisons = []
    for candidate, control in (
        ("sell_residual", "hold"),
        ("sell_residual", "complete_missing"),
        ("sell_residual", "no_trade"),
    ):
        grouped: dict[str, list[float]] = {}
        for key, row in indexed[candidate].items():
            grouped.setdefault(key[0], []).append(
                float(row["metrics"]["net_simulated_pnl"])
                - float(indexed[control][key]["metrics"]["net_simulated_pnl"])
            )
        means = np.array([np.mean(grouped[k]) for k in sorted(grouped)])
        rng = np.random.default_rng(991)
        interval = np.quantile(
            [rng.choice(means, len(means), replace=True).mean() for _ in range(2000)],
            [0.025, 0.975],
        ).tolist()
        comparisons.append(
            {
                "candidate": candidate,
                "control": control,
                "mean_change": float(means.mean()),
                "group_bootstrap_95": interval,
            }
        )
    leaderboard = []
    for policy in policies:
        selected = list(indexed[policy].values())
        values = [float(r["metrics"]["net_simulated_pnl"]) for r in selected]
        tail = max(0, -float(np.mean(sorted(values)[: max(1, math.ceil(len(values) * 0.05))])))
        leaderboard.append(
            {
                "policy": policy,
                "mean_pnl": float(np.mean(values)),
                "cvar_05_loss": tail,
                "score": float(np.mean(values)) - tail,
                "worst_pnl": min(values),
                "intervention_requests": sum(r["intervention_requests"] for r in selected),
                "intervention_filled_shares": str(
                    sum((D(r["intervention_filled_shares"]) for r in selected), D(0))
                ),
            }
        )
    atomic_json(directory / "rows.json", rows)
    manifest = {
        "unwind_id": identity,
        "state": "COMPLETED",
        "created_at": time.time(),
        "configuration": spec.model_dump(mode="json"),
        "runner_version": VERSION,
        "source_hash": source_hash,
        "rows_sha256": sha256(directory / "rows.json"),
        "source_groups": spec.episodes,
        "correlated_variants": len(rows),
        "leaderboard": leaderboard,
        "paired_comparisons": comparisons,
        "promotion": False,
        "limitations": [
            "Synthetic hypothetical execution and estimated costs only; no real-market profitability evidence.",
            "One initial risk-admitted position and at most one confirmed-terminal intervention.",
            "Current stop/loss/exposure limits can require holding; no forced liquidation exception.",
            "Sale quantity preserves matched shares if filled, not a guaranteed P&L or dollar-loss bound.",
            "Hold, repair and sell use the same sale-capable ledger and actual-settlement redemption semantics.",
            "Different actions can consume different random draws; bootstrap source groups, not variants.",
            "Initial-buy cost predictors are not reused as unwind-cost predictions.",
        ],
    }
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(
        artifact_path(root, "findings", identity) / "manifest.json",
        {
            "finding_id": identity,
            "created_at": time.time(),
            "unwind_id": identity,
            "title": "Matched residual sell/hold/repair comparison completed",
            "outcome": {"leaderboard": leaderboard, "paired_comparisons": comparisons},
            "interpretation": "Fixed bounded policies compared on fresh synthetic groups; no policy promotion.",
            "caveats": manifest["limitations"],
            "next_experiment": "Verify proposals, initial buy ledgers and held-out shift robustness before drawing broader conclusions.",
        },
    )
    return manifest
