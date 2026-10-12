"""Event-driven adapter around the production paper broker, strategy and risk gate."""

import copy
import platform
from decimal import Decimal, localcontext
from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Evaluation, Status
from midas.economics.attestation import digest
from midas.laboratory import VERSION
from midas.laboratory.clock import Clock, Event
from midas.laboratory.oracles import verify
from midas.laboratory.spec import Scenario
from midas.paper.broker import audit, initial, serial, summary, transition

D = Decimal


class NoTrade(BinaryStrategy):
    version = "no-trade-1"

    def evaluate(self, *args: Any, **kwargs: Any) -> Evaluation:
        result = super().evaluate(*args, **kwargs)
        return result.model_copy(
            update={"status": Status.CANDIDATE, "reasons": ("No-trade benchmark",)}
        )


class Environment:
    """Future agent boundary: reset, observe, available actions, step, reward, termination.

    Strategies receive observed books only. Venue state is private to the runner.
    The optional mutation event is a labeled oracle calibration, not a production bug.
    """

    def __init__(self, scenario: Scenario, retain: bool = True) -> None:
        self.scenario = scenario
        self.retain = retain
        self.reset()

    def reset(self) -> dict[str, Any]:
        self.clock = Clock()
        self.clock.now = self.scenario.epoch_ms
        self.state = initial(self.scenario.account)
        self.market = self.scenario.market.model_dump(mode="json")
        self.books = {a: b.model_dump(mode="json") for a, b in self.scenario.books.items()}
        self.observed_market = copy.deepcopy(self.market)
        self.observed_books: dict[str, Any] = {}
        self.faults: dict[str, str] = {}
        self.journal: list[dict[str, Any]] = []
        self.last_action: dict[str, Any] | None = None
        self.errors: list[str] = []
        self.event_count = 0
        self.financing = D(0)
        self.locked_integral = D(0)
        self.last_ts = self.scenario.epoch_ms
        self.max_locked = D(0)
        self.max_utilization = D(0)
        self.finished = False
        for event in self.scenario.events:
            self.clock.schedule(
                self.scenario.epoch_ms + event.time_ms,
                event.id,
                event.kind,
                event.payload,
                event.priority,
            )
        return self.observe()

    def observe(self) -> dict[str, Any]:
        return self._observation(self.portfolio())

    def _observation(self, portfolio: dict[str, Any]) -> dict[str, Any]:
        return {
            "time_ms": max(self.scenario.epoch_ms, self.clock.now),
            "market": copy.deepcopy(self.observed_market),
            "books": copy.deepcopy(self.observed_books),
            "portfolio": portfolio,
        }

    def available_actions(self) -> tuple[str, ...]:
        return ("advance",) if not self.finished else ()

    def portfolio(self) -> dict[str, Any]:
        try:
            return summary(self.state, max(self.scenario.epoch_ms, self.clock.now))
        except ValueError:
            return {"unavailable": "State failed independent accounting validation"}

    def _apply(self, command: dict[str, Any]) -> None:
        strategy = (
            NoTrade()
            if self.scenario.strategy == "no_trade"
            else BinaryStrategy(
                self.scenario.account.limits.max_age_ms,
                max(self.scenario.account.limits.min_edge, D(".03"))
                if self.scenario.strategy == "conservative"
                else self.scenario.account.limits.min_edge,
            )
        )
        self.state = transition(self.state, command, strategy)
        for action in self.state["pending"]:
            self.clock.schedule(
                action["due"], action["id"], "action", {"action_id": action["id"]}, 20
            )

    def _process(self, event: Event) -> dict[str, Any] | None:
        payload = copy.deepcopy(event.payload)
        ts = event.time
        command: dict[str, Any] = {**payload, "id": event.id, "ts": ts, "kind": event.kind}
        if event.kind == "market":
            self.market = payload.get("market", self.market)
            changed = {}
            for asset, book in payload.get("books", {}).items():
                old = self.books.get(asset)
                if (
                    old
                    and book.get("valid")
                    and (book.get("exchange_ts_ms") or 0) < (old.get("exchange_ts_ms") or 0)
                ):
                    continue
                self.books[asset] = book
                changed[asset] = book
            self.clock.schedule(
                ts + self.scenario.observation_latency_ms,
                f"{event.id}:receipt",
                "receipt",
                {"market": self.market, "books": changed},
                5,
            )
            return None
        if event.kind == "observe":
            self.clock.schedule(
                ts + self.scenario.observation_latency_ms,
                f"{event.id}:receipt",
                "receipt",
                {"market": self.market, "books": self.books},
                5,
            )
            return None
        if event.kind == "receipt":
            self.observed_market = payload["market"]
            for asset, book in payload["books"].items():
                old = self.observed_books.get(asset)
                # A late older exchange snapshot must not replace a newer observed book.
                if (
                    old
                    and book.get("valid")
                    and (book.get("exchange_ts_ms") or 0) < (old.get("exchange_ts_ms") or 0)
                ):
                    continue
                book["received_ts_ms"] = ts
                self.observed_books[asset] = book
            self.clock.schedule(
                ts + self.scenario.strategy_latency_ms,
                f"{event.id}:decision",
                "decision",
                {"market": self.observed_market, "books": self.observed_books},
                10,
            )
            return None
        if event.kind == "decision":
            command["kind"] = "observe"
            self._apply(command)
        elif event.kind == "action":
            action = next(
                (a for a in self.state["pending"] if a["id"] == payload["action_id"]), None
            )
            if action is None:
                return None
            command.update(
                market=self.market, books=self.books, fault=self.faults.get(action["kind"])
            )
            self._apply(command)
            self.last_action = copy.deepcopy(command)
        elif event.kind == "fault":
            self.faults[payload["action_kind"]] = payload["fault"]
        elif event.kind in {"cancel", "expire"}:
            for position_id, position in self.state["positions"].items():
                for order in position["exchange"]["orders"]:
                    id = f"{event.id}:{order['id']}"
                    due = ts + int(payload.get("delay_ms", 0))
                    self.state["pending"].append(
                        {
                            "id": id,
                            "kind": event.kind,
                            "due": due,
                            "position": position_id,
                            "order": order["id"],
                            "asset": order["asset_id"],
                        }
                    )
                    self.clock.schedule(due, id, "action", {"action_id": id}, 20)
        elif event.kind == "settle":
            # This event denotes confirmed usable collateral, not an oracle announcement.
            if self.scenario.account.mode != "synthetic" and "resolution_evidence" not in payload:
                raise ValueError("Recorded settlement requires verified evidence")
            for position_id in sorted(self.state["positions"]):
                self._apply({**command, "id": f"{event.id}:{position_id}", "position": position_id})
        elif event.kind == "control":
            self._apply(command)
        elif event.kind == "duplicate":
            original = self.last_action
            if original:
                previous = digest(self.state)
                repeated = transition(self.state, original)
                if digest(repeated) != previous:
                    self.errors.append("idempotency: repeated action changes state")
        elif event.kind == "mutate":
            # Deliberately corrupt one committed fill to validate the independent oracle.
            for position in self.state["positions"].values():
                entry = next(
                    (e for e in position["exchange"]["ledger"] if e["kind"] == "fill"), None
                )
                if entry:
                    entry["locked_delta"] = str(D(entry["locked_delta"]) + D(".01"))
                    break
        elif event.kind != "checkpoint":
            raise ValueError(f"Unknown event {event.kind}")
        return command

    def step(self) -> dict[str, Any]:
        with localcontext() as ctx:
            ctx.prec = 28
            return self._step()

    def _step(self, publish: bool = True) -> dict[str, Any]:
        event = self.clock.peek()
        end = self.scenario.epoch_ms + self.scenario.horizon_ms
        if self.finished or event is None or event.time > end:
            if not self.finished:
                self._accrue(end)
            self.finished = True
            return (
                {"observation": self.observe(), "reward": "0", "terminated": True}
                if publish
                else {}
            )
        before = self.portfolio()
        event = self.clock.pop()
        self._accrue(event.time, before)
        command = None
        try:
            command = self._process(event)
            self.errors.extend(verify(self.state))
            self.errors.extend(audit(self.state))
        except (ValueError, KeyError) as error:
            self.errors.append(f"transition: {error}")
        after = self.portfolio()
        self.event_count += 1
        self.max_locked = max(self.max_locked, D(after.get("locked", "0")))
        self.max_utilization = max(self.max_utilization, D(after.get("capital_utilization", "0")))
        if self.retain or self.errors:
            record = {
                "index": self.event_count - 1,
                "id": event.id,
                "time_ms": event.time,
                "kind": event.kind,
                "payload": serial(event.payload),
                "command": command,
                "before": before,
                "after": after,
                "observation": self._observation(after),
                "errors": list(self.errors),
            }
            self.journal.append(serial(record))
        if self.errors:
            self.finished = True
        if not publish:
            return {}
        return {
            "observation": self._observation(after),
            "reward": str(D(after.get("realized_pnl", "0")) - D(before.get("realized_pnl", "0"))),
            "terminated": self.finished,
        }

    def _accrue(self, ts: int, portfolio: dict[str, Any] | None = None) -> None:
        held = D((portfolio or self.portfolio()).get("locked", "0")) + D(
            (portfolio or self.portfolio()).get("reserved", "0")
        )
        interval = max(0, ts - self.last_ts)
        self.locked_integral += held * interval
        self.financing += (
            held * interval * self.scenario.costs.annual_financing_rate / D(365 * 86_400_000)
        )
        self.last_ts = ts

    def run(self, max_events: int | None = None) -> dict[str, Any]:
        with localcontext() as ctx:
            ctx.prec = 28
            steps = 0
            while not self.finished and (max_events is None or steps < max_events):
                self._step(publish=False)
                steps += 1
            return self.result()

    def result(self) -> dict[str, Any]:
        final = self.portfolio()
        fills = int(final.get("hypothetical_fills", 0))
        settled = int(final.get("redemption_positions", final.get("settled_positions", 0)))
        operating = (
            fills * self.scenario.costs.operating_per_fill
            + settled * self.scenario.costs.redemption_cost
        )
        haircut = D(final.get("settlement_proceeds", "0")) * (
            1 - self.scenario.costs.collateral_value_factor
        )
        net = D(final.get("realized_pnl", "0")) - self.financing - operating - haircut
        orders = [o for p in final.get("positions", []) for o in p["orders"]]
        submitted = len(orders)
        partial = sum(
            D(o["remaining"]) != 0 and D(o["remaining"]) < D(o["quantity"]) for o in orders
        )
        metrics = {
            "net_simulated_pnl": str(net),
            "net_simulated_return": str(net / self.scenario.account.capital),
            "gross_settled_virtual_pnl": final.get("realized_pnl", "0"),
            "operating_cost_estimate": str(operating),
            "financing_cost_estimate": str(self.financing),
            "collateral_haircut_estimate": str(haircut),
            "max_locked": str(self.max_locked),
            "capital_time_integral_ms": str(self.locked_integral),
            "max_utilization": str(self.max_utilization),
            "max_drawdown": final.get("max_drawdown", "0"),
            "orders": submitted,
            "fill_count": fills,
            "partial_orders": partial,
            "execution_success_rate": str(sum(o["status"] == "FILLED" for o in orders) / submitted)
            if submitted
            else None,
            "rejected_decisions": final.get("rejected", 0),
            "decisions": self.state["decisions_total"],
            "slippage": [
                p["decision"]["evaluation"]["slippage"] for p in final.get("positions", [])
            ],
            "open_positions": final.get("open_positions", 0),
        }
        if "sale_proceeds" in final:
            metrics["gross_realized_virtual_pnl"] = final.get("realized_pnl", "0")
            metrics["sale_proceeds_virtual"] = final["sale_proceeds"]
        classification = (
            "CONTROLLED_MUTATION"
            if self.errors and any(e.kind == "mutate" for e in self.scenario.events)
            else "SOFTWARE_DEFECT"
            if self.errors
            else "LEGITIMATE_LOSS"
            if net < 0
            else "VALID_RUN"
        )
        core = {
            "simulator_version": VERSION,
            "strategy_version": NoTrade.version
            if self.scenario.strategy == "no_trade"
            else BinaryStrategy.version,
            "scenario": self.scenario.model_dump(mode="json"),
            "scenario_hash": digest(self.scenario.model_dump(mode="json")),
            "seed": self.scenario.seed,
            "dataset_id": self.scenario.dataset_id,
            "dataset_hash": self.scenario.dataset_hash,
            "data_source": self.scenario.provenance,
            "execution_certainty": "HYPOTHETICAL_UNCALIBRATED",
            "economically_verified": False,
            "economic_assumptions": self.scenario.costs.model_dump(mode="json"),
            "complete": self.finished,
            "event_count": self.event_count,
            "passed": not self.errors,
            "classification": classification,
            "errors": list(dict.fromkeys(self.errors)),
            "metrics": metrics,
            "final_portfolio": final,
            "pending_events": len(self.clock.heap),
            "warnings": list(self.scenario.warnings)
            + [
                "Unresolved inventory is not settled profit",
                "Cost-adjusted results are analytical estimates, not spendable broker balances",
            ],
        }
        return {
            **core,
            "result_hash": digest(core),
            "journal_hash": digest(self.journal),
            "journal": self.journal,
            "runtime": {"python": platform.python_version(), "decimal_precision": 28},
        }

    def checkpoint(self) -> dict[str, Any]:
        data = {
            "version": VERSION,
            "scenario": self.scenario.model_dump(mode="json"),
            "retain": self.retain,
            "clock": self.clock.checkpoint(),
            "state": self.state,
            "market": self.market,
            "books": self.books,
            "observed_market": self.observed_market,
            "observed_books": self.observed_books,
            "faults": self.faults,
            "last_action": self.last_action,
            "journal": self.journal,
            "errors": self.errors,
            "event_count": self.event_count,
            "financing": str(self.financing),
            "locked_integral": str(self.locked_integral),
            "last_ts": self.last_ts,
            "max_locked": str(self.max_locked),
            "max_utilization": str(self.max_utilization),
            "finished": self.finished,
        }
        data = serial(data)
        return {**data, "checksum": digest(data)}

    @classmethod
    def restore(cls, data: dict[str, Any]) -> "Environment":
        data = copy.deepcopy(data)
        checksum = data.pop("checksum")
        if digest(data) != checksum or data.pop("version") != VERSION:
            raise ValueError("Checkpoint integrity/version mismatch")
        env = cls(Scenario.model_validate(data.pop("scenario")), data.pop("retain"))
        env.clock = Clock.restore(data.pop("clock"))
        for key in ("financing", "locked_integral", "max_locked", "max_utilization"):
            data[key] = D(data[key])
        for key, value in data.items():
            setattr(env, key, value)
        if verify(env.state) or audit(env.state):
            raise ValueError("Checkpoint ledger validation failed")
        return env


def execute(scenario: Scenario, retain: bool = True) -> dict[str, Any]:
    return Environment(scenario, retain).run()
