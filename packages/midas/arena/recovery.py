"""Bounded missing-leg research through the unchanged broker and exchange ledger."""

import copy
import json
import random
import time
import uuid
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from midas.arbitrage.engine import BinaryStrategy
from midas.arena.datasets import DatasetSpec
from midas.core.models import Book, Market, Model, Source
from midas.economics.attestation import fingerprint
from midas.laboratory.runtime import Environment, NoTrade
from midas.laboratory.spec import Scenario
from midas.paper.broker import ExecutionModel, transition
from midas.risk.engine import Limits
from midas.simulation.exchange import Exchange

D = Decimal
VERSION = "bounded-missing-leg-1"


class RecoverySpec(Model):
    policy: Literal["hold", "complete_missing"] = "hold"
    max_additional_capital: Decimal = Field(default=D("5"), gt=0, le=20, allow_inf_nan=False)
    max_price: Decimal = Field(default=D("0.75"), gt=0, lt=1, allow_inf_nan=False)


class RecoveryStudySpec(Model):
    episodes: int = Field(default=60, ge=30, le=300)
    seed: int = Field(default=213071, ge=0, le=2**32 - 20000)
    recovery: RecoverySpec = RecoverySpec(policy="complete_missing")

    @model_validator(mode="after")
    def fixed_policy(self) -> "RecoveryStudySpec":
        if self.recovery.policy != "complete_missing":
            raise ValueError("Study requires the missing-leg policy and its separate hold control")
        return self


def assess(
    exchange: Exchange,
    market: Market,
    books: dict[str, Book],
    portfolio: dict[str, Any],
    scenario: Scenario,
    spec: RecoverySpec,
    now_ms: int,
) -> dict[str, Any]:
    """Uses observed books and known own inventory; grants no new capital."""
    reasons = []
    limits = Limits.model_validate(portfolio["risk_limits"])
    assets = [i.asset_id for i in exchange.market.instruments]
    quantities = [exchange.portfolio.positions.get(a, D(0)) for a in assets]
    if len(assets) != 2:
        raise ValueError("Recovery requires an existing binary position")
    residual = abs(quantities[0] - quantities[1])
    asset = assets[0 if quantities[0] < quantities[1] else 1]
    if exchange.settled or exchange.emergency_stop or limits.emergency_stop:
        reasons.append("Position settled or stopped")
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
    if not market.fee.verified or not market.payout_verified or market.fee.exponent != 1:
        reasons.append("Unverified payout or fee evidence")
    for field, limit in (
        ("max_drawdown", limits.max_drawdown),
        ("daily_loss", limits.max_daily_loss),
        ("cumulative_loss", limits.max_cumulative_loss),
    ):
        value = D(str(portfolio[field]))
        if value > 0 and value >= limit:
            reasons.append(f"Existing {field} cutoff")
    book = books.get(asset)
    if residual <= 0:
        reasons.append("No residual inventory")
    if (
        not book
        or not book.valid
        or book.source != market.source
        or book.condition_id != market.condition_id
        or book.received_ts_ms > now_ms
        or book.exchange_ts_ms is None
        or book.exchange_ts_ms > now_ms
        or now_ms - book.received_ts_ms > limits.max_age_ms
        or now_ms - book.exchange_ts_ms > limits.max_age_ms
    ):
        reasons.append("Missing, invalid or stale observed recovery book")
    budget = min(spec.max_additional_capital, limits.max_capital, exchange.portfolio.available)
    quantity, price, reserve = D(0), D(0), D(0)
    if book:
        levels = sorted((x for x in book.asks if x.price <= spec.max_price), key=lambda x: x.price)
        depth = D(0)
        # Bound reservation using the same fee curve and fragmentation reserve as
        # Exchange.submit. The exchange independently charges actual fills.
        for level in levels:
            depth += level.size
            limit = level.price
            if limit > levels[0].price * (1 + limits.max_slippage):
                continue
            fee_price = min(limit, D("0.5"))
            per_share = (
                limit
                + market.fee.rate * fee_price * (1 - fee_price)
                + (D("0.001") if market.fee.rate else D(0))
            )
            q = min(residual, depth, budget / per_share).quantize(D("0.01"), rounding=ROUND_FLOOR)
            required = (q * per_share).quantize(D("0.000001"), rounding=ROUND_CEILING)
            minimum_ok = (
                q * limit >= book.min_order_size
                if book.minimum_unit == "notional"
                else q >= book.min_order_size
            )
            # Each additional filled missing share costs at most its complete-set
            # payout. This bounds worst-settlement exposure, not realized profit.
            if (
                q > quantity
                and minimum_ok
                and required <= budget
                and required <= q * market.payout_per_set * scenario.costs.collateral_value_factor
            ):
                quantity, price, reserve = q, limit, required
    if quantity <= 0:
        reasons.append("Residual, observed depth or remaining allocated budget is insufficient")
    for value, threshold, reason in (
        (
            D(str(portfolio["gross_exposure"])) + reserve,
            limits.max_exposure,
            "Overall exposure limit",
        ),
        (
            exchange.portfolio.locked + exchange.portfolio.reserved + reserve,
            limits.max_market_exposure,
            "Market exposure limit",
        ),
        (
            exchange.portfolio.locked + exchange.portfolio.reserved + reserve,
            limits.max_event_exposure,
            "Event exposure limit",
        ),
        (
            exchange.portfolio.locked + reserve,
            limits.max_unmatched_exposure,
            "Potential unmatched-leg capital limit",
        ),
    ):
        if value > threshold:
            reasons.append(reason)
    return {
        "allowed": not reasons,
        "reasons": reasons or ["Bounded residual-reducing order within existing allocation"],
        "asset_id": asset,
        "quantity": str(quantity),
        "limit": str(price),
        "reserved_bound": str(reserve),
        "residual_before": str(residual),
        "additional_external_capital": "0",
        "decision_time_ms": now_ms,
    }


class RecoveryEnvironment(Environment):
    """One ordinary risk-admitted position, then hold or one repair attempt."""

    def __init__(self, scenario: Scenario, spec: RecoverySpec, retain: bool = True):
        if scenario.provenance != "GENERATED" or scenario.market.source != Source.SYNTHETIC:
            raise ValueError("Recovery research requires generated synthetic scenarios")
        if scenario.strategy != "arbitrage":
            raise ValueError("Recovery runner requires one initial arbitrage policy")
        self.recovery_spec = spec
        self.recovery_decided = False
        self.recovery_decisions: list[dict[str, Any]] = []
        super().__init__(scenario, retain)

    def reset(self) -> dict[str, Any]:
        self.recovery_decided = False
        self.recovery_decisions = []
        return super().reset()

    def _apply(self, command: dict[str, Any]) -> None:
        strategy = (
            NoTrade()
            if command["kind"] == "observe" and self.state["positions"]
            else BinaryStrategy(
                self.scenario.account.limits.max_age_ms, self.scenario.account.limits.min_edge
            )
        )
        # Capacity accounting uses unadjusted venue prices. Legacy broker maps
        # adverse fills by adjusted prices; normalize inside this research runner
        # so a subsequent recovery cannot reuse already consumed depth.
        action = next(
            (a for a in self.state["pending"] if a["id"] == command.get("action_id")), None
        )
        before = None
        ledger_size = 0
        if action and action["kind"] == "match" and action.get("side", "BUY") == "BUY":
            before = copy.deepcopy(self.state["used_liquidity"].get(action["asset"], {}))
            ledger_size = len(self.state["positions"][action["position"]]["exchange"]["ledger"])
        self.state = transition(self.state, command, strategy)
        if before is not None:
            model = ExecutionModel.model_validate(
                self.state["positions"][action["position"]]["execution_model"]
            )
            tick = Book.model_validate(command["books"][action["asset"]]).tick_size
            for fill in self.state["positions"][action["position"]]["exchange"]["ledger"][
                ledger_size:
            ]:
                if fill["kind"] == "fill":
                    venue_price = D(fill["price"]) - model.adverse_ticks * tick
                    key = str(venue_price)
                    before[key] = str(D(before.get(key, "0")) + D(fill["quantity"]))
            self.state["used_liquidity"][action["asset"]] = before
        for pending in self.state["pending"]:
            self.clock.schedule(
                pending["due"], pending["id"], "action", {"action_id": pending["id"]}, 20
            )

    def _process(self, event: Any) -> dict[str, Any] | None:
        if event.kind == "checkpoint" and event.payload.get("recovery_order"):
            proposal = event.payload["recovery_order"]
            position = proposal["position"]
            order = f"{position}:recovery:1"
            if any(a["order"] == order for a in self.state["pending"]):
                raise ValueError("Duplicate recovery scheduling")
            model = self.scenario.account.execution
            assets = [i.asset_id for i in self.scenario.market.instruments]
            index = assets.index(proposal["asset_id"])
            rng = random.Random(model.seed)
            jitters = [
                rng.randint(0, model.jitter_ms) if model.distribution == "uniform" else 0
                for _ in assets
            ]
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
                        "position": position,
                        "order": order,
                        "asset": proposal["asset_id"],
                        "quantity": proposal["quantity"],
                        "limit": proposal["limit"],
                    }
                )
                self.clock.schedule(timestamp, identity, "action", {"action_id": identity}, 20)
            return {"kind": "recovery_request", "ts": event.time, "id": event.id, **proposal}
        command = super()._process(event)
        if (
            event.kind == "decision"
            and self.recovery_spec.policy == "complete_missing"
            and not self.recovery_decided
            and self.state["positions"]
        ):
            position = next(iter(self.state["positions"]))
            if any(a["position"] == position for a in self.state["pending"]):
                return command
            self.recovery_decided = True
            exchange = Exchange.restore(self.state["positions"][position]["exchange"])
            observation = self.observe()
            proposal = assess(
                exchange,
                Market.model_validate(observation["market"]),
                {a: Book.model_validate(b) for a, b in observation["books"].items()},
                observation["portfolio"],
                self.scenario,
                self.recovery_spec,
                event.time,
            )
            proposal["position"] = position
            self.recovery_decisions.append(proposal)
            if proposal["allowed"]:
                self.clock.schedule(
                    event.time,
                    f"{position}:recovery-request",
                    "checkpoint",
                    {"recovery_order": proposal},
                    11,
                )
        return command


def execute(scenario: Scenario, spec: RecoverySpec) -> dict[str, Any]:
    env = RecoveryEnvironment(scenario, spec)
    result = env.run()
    if not result["passed"] or not result["complete"]:
        raise ValueError(f"Invalid recovery accounting: {result['errors']}")
    return {
        "runner_version": VERSION,
        "specification": spec.model_dump(mode="json"),
        "recovery_decisions": env.recovery_decisions,
        "result": result,
    }


def run_study(root: Any, spec: RecoveryStudySpec, progress: Any = None) -> dict[str, Any]:
    import math
    from collections import defaultdict
    from pathlib import Path

    import numpy as np

    from midas.arena.artifacts import artifact_path, atomic_json, atomic_replay, sha256
    from midas.arena.datasets import research_hash
    from midas.laboratory.spec import generate

    root = Path(root)
    for file in (root / "datasets").glob("*/manifest.json"):
        existing = json.loads(file.read_text())["spec"]
        if (
            spec.seed < existing["seed"] + existing["episodes"]
            and existing["seed"] < spec.seed + spec.episodes
        ):
            raise ValueError("Recovery study seeds overlap existing dataset")
    for kind in ("tournaments", "recoveries"):
        for file in (root / kind).glob("*/manifest.json"):
            existing = json.loads(file.read_text())
            configuration = existing["configuration"]
            source = configuration if kind == "recoveries" else configuration.get("challenge")
            if (
                source
                and spec.seed < source["seed"] + source["episodes"]
                and source["seed"] < spec.seed + spec.episodes
            ):
                raise ValueError("Recovery study seeds overlap opened research")
    identity = "recovery-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "recoveries", identity)
    if progress and getattr(progress, "register", None):
        progress.register("recoveries", identity)
    families = ("thin", "deep", "calm", "liquidity_shock", "volatile", "one_sided", "disappearing")
    # Validate the same generator contract used elsewhere, without constructing
    # labels or selecting cases based on any future settlement outcome.
    DatasetSpec(episodes=spec.episodes, seed=spec.seed, families=families)
    atomic_json(
        directory / "preparing.json",
        {"configuration": spec.model_dump(mode="json"), "source_hash": research_hash()},
    )
    rows = []
    grouped: dict[str, list[float]] = defaultdict(list)
    policies = {"hold": RecoverySpec(), "complete_missing": spec.recovery}
    for index in range(spec.episodes):
        for execution_name in ("optimistic", "standard", "conservative"):
            scenario = generate(
                families[index % len(families)],
                spec.seed + index,
                ExecutionModel.preset(execution_name).model_copy(
                    update={"seed": spec.seed + index}
                ),
            )
            values = {}
            for policy in ("no_trade", "hold", "complete_missing"):
                started = time.monotonic()
                if policy == "no_trade":
                    result = Environment(
                        scenario.model_copy(update={"strategy": "no_trade"}), retain=True
                    ).run()
                    report = {"runner_version": VERSION, "recovery_decisions": [], "result": result}
                else:
                    report = execute(scenario, policies[policy])
                    result = report["result"]
                if not result["passed"] or not result["complete"]:
                    raise ValueError("Invalid recovery comparison accounting")
                attempts = [r for r in report["recovery_decisions"] if r["allowed"]]
                initial = result["final_portfolio"]["positions"]
                recovery_orders = [
                    o for p in initial for o in p["orders"] if ":recovery:" in o["id"]
                ]
                row = {
                    "id": f"{index}-{execution_name}-{policy}",
                    "base_episode_id": f"{families[index % len(families)]}:{spec.seed + index}",
                    "family": families[index % len(families)],
                    "seed": spec.seed + index,
                    "execution_model": execution_name,
                    "policy": policy,
                    "metrics": result["metrics"],
                    "recovery_requests": len(attempts),
                    "recovery_orders": len(recovery_orders),
                    "recovery_filled_shares": str(
                        sum((D(o["quantity"]) - D(o["remaining"]) for o in recovery_orders), D(0))
                    ),
                    "result_hash": result["result_hash"],
                    "journal_hash": result["journal_hash"],
                    "runtime_seconds": time.monotonic() - started,
                }
                rows.append(row)
                values[policy] = float(result["metrics"]["net_simulated_pnl"])
                atomic_replay(directory / "replays" / (row["id"] + ".json"), {"row": row, **report})
                if progress:
                    progress(len(rows), spec.episodes * 9)
            grouped[f"{families[index % len(families)]}:{spec.seed + index}"].append(
                values["complete_missing"] - values["hold"]
            )
    means = np.array([np.mean(grouped[g]) for g in sorted(grouped)])
    rng = np.random.default_rng(991)
    interval = np.quantile(
        [rng.choice(means, len(means), replace=True).mean() for _ in range(2000)], [0.025, 0.975]
    ).tolist()
    leaderboard = []
    for policy in ("no_trade", "hold", "complete_missing"):
        selected = [r for r in rows if r["policy"] == policy]
        values = [float(r["metrics"]["net_simulated_pnl"]) for r in selected]
        tail = max(0, -float(np.mean(sorted(values)[: max(1, math.ceil(len(values) * 0.05))])))
        leaderboard.append(
            {
                "policy": policy,
                "mean_pnl": float(np.mean(values)),
                "cvar_05_loss": tail,
                "score": float(np.mean(values)) - tail,
                "worst_pnl": min(values),
                "recovery_requests": sum(r["recovery_requests"] for r in selected),
                "recovery_filled_shares": str(
                    sum((D(r["recovery_filled_shares"]) for r in selected), D(0))
                ),
            }
        )
    atomic_json(directory / "rows.json", rows)
    manifest = {
        "recovery_id": identity,
        "state": "COMPLETED",
        "created_at": time.time(),
        "configuration": spec.model_dump(mode="json"),
        "runner_version": VERSION,
        "source_hash": research_hash(),
        "rows_sha256": sha256(directory / "rows.json"),
        "source_groups": spec.episodes,
        "correlated_variants": len(rows),
        "leaderboard": leaderboard,
        "paired_recovery_minus_hold_mean": float(means.mean()),
        "group_bootstrap_95": interval,
        "limitations": [
            "One initial risk-admitted position; no subsequent new-position strategy",
            "One observed missing-leg recovery decision at most; no selling or external capital",
            "Unknown acknowledgments, stale books, loss/exposure cutoffs can force holding",
            "Recovery orders experience the same latency, liquidity fraction, adverse ticks, fee formula and settlement constraints as initial orders",
            "Recovery can lower realized profit when held inventory would have won; no realized loss guarantee",
            "Observed quote depth does not guarantee future execution",
            "Research runner normalizes adverse-fill consumption to unadjusted venue prices; legacy broker and archive bytes remain unchanged",
            "Synthetic hypothetical results; execution variants remain correlated within source groups",
        ],
    }
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(
        artifact_path(root, "findings", identity) / "manifest.json",
        {
            "finding_id": identity,
            "title": "Bounded missing-leg recovery comparison completed",
            "created_at": time.time(),
            "recovery_id": identity,
            "interpretation": f"Mean recovery-minus-hold P&L {means.mean():.3f}, grouped 95% interval {interval}. The same initial admission policy was used for both; execution remained uncertain.",
            "outcome": manifest,
            "caveats": manifest["limitations"],
            "next_experiment": "Investigate actual rejected/partial recovery traces before widening recovery budgets or implementing a sell-ledger unwind.",
        },
    )
    return manifest
