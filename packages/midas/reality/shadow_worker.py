"""Prospective public shadow research. Reads raw files; never submits orders."""

from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import json
import signal
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from .execution_research import Assumptions, evaluate, fee_rate, fee_reserve
from .foundry import family_keys
from .model_registry import load
from .research_measurements import (
    book_view,
    censor,
    depth_cost,
    effective_tick,
    features,
    labels,
    pair_quality,
)
from .research_schema import FEATURE_VERSION, LABEL_VERSION, DatasetSpec, digest
from .shadow_campaign import verify
from .shadow_policy import POLICIES, decide
from .shadow_source import Context, Tail
from .shadow_store import Journal
from .storage import atomic_json, file_hash

D = Decimal


def spec_for(plan: dict[str, Any]) -> DatasetSpec:
    i = plan["identity"]
    return DatasetSpec(
        horizons_ms=tuple(i["horizons_ms"]),
        quantity=i["quantity"],
        hypothetical_capital=i["capital"],
        future_tolerance_ms=i["future_tolerance_ms"],
        max_freshness_ms=i["max_freshness_ms"],
        max_skew_ms=i["max_skew_ms"],
    )


def scenario_results(
    row: dict[str, Any],
    label: dict[str, Any],
    horizon: int,
    plan: dict[str, Any],
    future: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if row["features"] is None:
        return result
    for declaration in plan["identity"]["scenarios"]:
        if declaration["delay_ms"] != horizon:
            continue
        values = {
            k: v
            for k, v in declaration.items()
            if k not in {"version", "assumption_id", "fee_formula"}
        }
        a = Assumptions(**values)
        example = {**row, "horizon_ms": horizon, "labels": label}
        economic = evaluate(example, a)
        recovery: dict[str, Any] = dict(
            state="not_applicable",
            evidence_kind="hypothetical_quoted_unwind",
            actual_fills="unknown_counterfactual",
        )
        if (
            future is not None
            and economic.get("unmatched_quantity")
            and D(economic["unmatched_quantity"]) > 0
        ):
            quantities = economic["imposed_quantities"]
            leg = max(quantities, key=lambda k: D(quantities[k]))
            quantity = D(economic["unmatched_quantity"])
            minimum = D(str(row["features"]["market"]["minimum_order_size_reported"]))
            proceeds = depth_cost(future[leg]["bids"], str(quantity))
            rate = fee_rate(row["features"])
            if quantity < minimum:
                recovery["state"] = "below_reported_recovery_minimum"
            elif not proceeds["complete"] or rate is None:
                recovery["state"] = "insufficient_observed_unwind_support"
            else:
                fee = D(0)
                remaining = quantity
                for price, size in future[leg]["bids"]:
                    amount = min(remaining, D(size))
                    fee += fee_reserve(amount, D(price), rate)
                    remaining -= amount
                    if remaining == 0:
                        break
                net = D(proceeds["value"]) - fee
                low = D(economic["hypothetical_pnl_bounds"][0]) + net
                recovery.update(
                    state="declared_snapshot_unwind_assumption",
                    leg=leg,
                    quantity=str(quantity),
                    displayed_proceeds=proceeds["value"],
                    sell_fee_reserve=str(fee),
                    hypothetical_pnl=str(low),
                    note="Displayed bids do not prove a recovery order would fill; matched payout/settlement remain imposed",
                )
        policies = []
        for policy in row["policies"]:
            if policy["action"] == "hypothetical_trade":
                policies.append(
                    dict(policy=policy["policy"], execution=economic, recovery=recovery)
                )
            else:
                policies.append(
                    dict(
                        policy=policy["policy"],
                        execution=dict(
                            status="policy_abstained",
                            hypothetical_pnl_bounds=["0", "0"],
                            actual_fills="unknown_counterfactual",
                        ),
                        recovery=None,
                    )
                )
        result.append(
            dict(
                assumption_id=declaration["assumption_id"],
                scenario=a.name,
                policy_results=policies,
                evidence_kind="hypothetical_scenario_bounds",
                realized_money=None,
            )
        )
    return result


class Shadow:
    def __init__(self, root: Path, plan: dict[str, Any]) -> None:
        verify(plan)
        self.root = root
        self.plan = plan
        self.i = plan["identity"]
        self.spec = spec_for(plan)
        if {n: importlib.metadata.version(n) for n in self.i["toolchain"]} != self.i["toolchain"]:
            raise ValueError("Frozen inference toolchain changed")
        if (
            file_hash(
                Path(self.i["training_root"]) / "runs" / self.i["training_run_id"] / "report.json"
            )
            != self.i["training_report_sha256"]
        ):
            raise ValueError("Frozen training report changed")
        self.models = {
            t: load(Path(self.i["training_root"]), m["model_id"], m["weights_sha256"])
            for t, m in self.i["models"].items()
        }
        self.journal = Journal(
            root, budget=self.i["evidence_budget_bytes"], reserve=self.i["reserve_bytes"]
        )
        stored = self.journal.runtime()
        if stored and stored["campaign_id"] != plan["campaign_id"]:
            raise ValueError("Runtime belongs to a different campaign")
        self.ctx = Context.restore(stored["context"]) if stored else Context()
        self.tail = Tail(Path(self.i["raw_root"]), stored["cursor"] if stored else None)
        self.next_decision = stored["next_decision"] if stored else {}
        self.next_observation = stored["next_observation"] if stored else {}
        self.pending = self.journal.pending(self.i["horizons_ms"])
        self.running = True
        self.last_save = time.monotonic()
        self.last_clock: tuple[int, int] | None = None
        self.counters = (
            stored["counters"]
            if stored
            else dict(records=0, lagged_frames_skipped=0, source_checkpoints=0)
        )
        self.status = "WARMING_SOURCE"
        with self.journal.db:
            self.journal.append(
                "worker_start",
                dict(
                    campaign_id=plan["campaign_id"],
                    resumed=bool(stored),
                    source_ordinal=self.ctx.engine.last_ordinal,
                ),
            )

    def runtime(self) -> dict[str, Any]:
        return dict(
            campaign_id=self.plan["campaign_id"],
            context=self.ctx.snapshot(),
            cursor=dict(self.tail.cursor),
            next_decision=self.next_decision,
            next_observation=self.next_observation,
            counters=self.counters,
        )

    def save(self, *, failure: bool = False) -> None:
        if not failure:
            self.journal.check_capacity()
        with self.journal.db:
            self.journal.save_runtime(self.runtime())
        self.counters["source_checkpoints"] = self.ctx.checkpoints
        state = dict(
            state=self.status,
            campaign_id=self.plan["campaign_id"],
            updated_ns=time.time_ns(),
            source_ordinal=self.ctx.engine.last_ordinal,
            source_last_received_ns=self.ctx.engine.now_ns,
            producer_hash=self.ctx.producer_hash,
            counters=self.counters,
            **self.journal.summary(),
            actual_orders_submitted=0,
            scientific_state="insufficient_forward_evidence",
            evidence_bytes=sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file()),
            budget_bytes=self.i["evidence_budget_bytes"],
            pending_horizons=sum(len(p["horizons"]) for p in self.pending),
        )
        atomic_json(self.root / "status.json", state)
        self.last_save = time.monotonic()

    def finish(
        self,
        item: dict[str, Any],
        horizon: int,
        label: dict[str, Any],
        ref: dict[str, Any] | None,
        future: dict[str, Any] | None = None,
    ) -> None:
        row = item["row"]
        followup = dict(
            decision_id=row["id"],
            campaign_id=self.plan["campaign_id"],
            horizon_ms=horizon,
            labels=label,
            effective_delays_ms={
                k: (v["received_ns"] - row["decision_ns"]) / 10**6 for k, v in future.items()
            }
            if future
            else None,
            observed_future_received_ns={k: v["received_ns"] for k, v in future.items()}
            if future
            else None,
            future_views=future,
            termination_ref=ref,
            future_sources={
                k: {key: self.ctx.refs[v[key][0]] for key in ("snapshot", "last")}
                for k, v in future.items()
            }
            if future
            else None,
            execution=scenario_results(row, label, horizon, self.plan, future),
            taxonomy=dict(
                labels="derived_public_measurements",
                execution="simulator_imposed_assumptions",
                actual_fills="unknown_counterfactual",
            ),
        )
        self.journal.outcome(followup)
        item["horizons"].remove(horizon)

    def follow(self, record: dict[str, Any], ref: dict[str, Any], barrier: str | None) -> None:
        now = self.ctx.engine.now_ns
        for item in self.pending:
            row = item["row"]
            for horizon in list(item["horizons"]):
                target = row["decision_ns"] + horizon * 10**6
                deadline = target + self.spec.tolerance_ms(horizon) * 10**6
                if row["baseline"] is None:
                    self.finish(item, horizon, censor("invalid_at_decision"), ref)
                    continue
                if now > deadline:
                    self.finish(item, horizon, censor("future_observation_unavailable"), ref)
                    continue
                if not item["committed_ns"]:
                    self.finish(item, horizon, censor("missing_durable_decision_commit_proof"), ref)
                    continue
                if record["received_ns"] <= item["committed_ns"]:
                    continue
                if barrier:
                    self.finish(item, horizon, censor(barrier, disrupted=True), ref)
                    continue
                market = self.ctx.cohort.get(row["condition"])
                if market is None:
                    self.finish(item, horizon, censor("market_retired_or_unobserved"), ref)
                    continue
                issue = pair_quality(
                    market, self.ctx.engine.books, now, self.spec, allow_empty_asks=True
                )
                if self.ctx.producer_hash not in self.i["allowed_producer_hashes"]:
                    issue = "source_revision_changed"
                if any(t in self.ctx.bad for t in market["tokens"]):
                    issue = "independent_book_divergence"
                if issue:
                    self.finish(
                        item,
                        horizon,
                        censor(
                            issue, disrupted=None if issue == "reported_expiry_reached" else True
                        ),
                        ref,
                    )
                    continue
                if any(
                    D(str(effective_tick(market, self.ctx.engine.books[t])))
                    != D(str(row["features"]["legs"][name.lower()]["tick_size"]))
                    for t, name in market["tokens"].items()
                ):
                    self.finish(item, horizon, censor("tick_regime_changed", disrupted=True), ref)
                    continue
                books = {
                    name.lower(): book_view(self.ctx.engine.books[t], now)
                    for t, name in market["tokens"].items()
                }
                times = [b["received_ns"] for b in books.values()]
                if (
                    min(times) < target
                    or max(times) > deadline
                    or max(times) - min(times) > self.spec.max_skew_ms * 10**6
                ):
                    continue
                if min(times) <= item["committed_ns"]:
                    self.finish(item, horizon, censor("future_preceded_durable_decision"), ref)
                    continue
                self.finish(item, horizon, labels(row["baseline"], books), ref, books)
        self.pending = [p for p in self.pending if p["horizons"]]

    def observe(self, market: dict[str, Any], now: int, reason: str | None) -> None:
        condition = market["condition"]
        if now < self.next_observation.get(condition, 0):
            return
        self.next_observation[condition] = now + self.i["observatory_stride_ms"] * 10**6
        points = {}
        for token, name in market["tokens"].items():
            b = self.ctx.engine.books.get(token)
            if b is None:
                continue
            v = book_view(b, now)
            points[name.lower()] = {
                k: v[k]
                for k in (
                    "best_bid",
                    "best_ask",
                    "spread",
                    "total_ask_quantity",
                    "total_bid_quantity",
                    "age_ns",
                    "received_ns",
                    "snapshot",
                    "last",
                )
            }
            points[name.lower()]["top_ask_quantity"] = v["asks"][0][1] if v["asks"] else None
        data = dict(
            ns=now,
            condition=condition,
            market_id=market["id"],
            title=market.get("question", market["id"]),
            legs=points,
            quality_reason=reason,
            protocol=market["protocol"],
            source_kind=self.i["source_kind"],
            sequence_verified=False,
        )
        with self.journal.db:
            seq = self.journal.append("observation", data, now)
            self.journal.db.execute(
                "insert or ignore into observations values(?,?,?)", (now, condition, seq)
            )

    def decision(
        self,
        market: dict[str, Any],
        record: dict[str, Any],
        ref: dict[str, Any],
        now: int,
        mono: int,
        reason: str | None,
    ) -> None:
        condition = market["condition"]
        due = self.next_decision.get(condition, 0)
        fast = False
        if reason is None:
            token_best_asks = [
                (token, self.ctx.engine.top_for(token)[1]) for token in market["tokens"]
            ]
            available_asks = [ask for _, ask in token_best_asks if ask is not None]
            quantity = D(self.i["quantity"])
            fast = (
                len(available_asks) == len(token_best_asks)
                and sum(available_asks, D(0)) < 1
                and all(
                    self.ctx.engine.books[token]["asks"][ask] >= quantity
                    for token, ask in token_best_asks
                    if ask is not None
                )
            )
        if now < due and not fast:
            return
        if fast and now < self.next_decision.get(condition + ":opportunity", 0):
            return
        f = baseline = None
        if reason is None:
            f, baseline = features(
                market,
                self.ctx.engine.books,
                decision_ns=now,
                spec=self.spec,
                history={t: list(h) for t, h in self.ctx.history.items()},
                trades=self.ctx.trades,
            )
        opportunity = (
            f is not None
            and D(f["theoretical_edge_per_unit_before_fees"]) > 0
            and f["quantity_supported"]
        )
        if now < due and not opportunity:
            return
        if opportunity and now < self.next_decision.get(condition + ":opportunity", 0):
            return
        self.next_decision[condition] = now + self.i["baseline_stride_ms"] * 10**6
        if opportunity:
            self.next_decision[condition + ":opportunity"] = (
                now + self.i["opportunity_stride_ms"] * 10**6
            )
        aliases = self.ctx.families.identities()
        family = aliases[family_keys(market)[0]]
        row = dict(
            schema_version=1,
            campaign_id=self.plan["campaign_id"],
            id=digest([self.plan["campaign_id"], condition, record["ordinal"]]),
            condition=condition,
            market_id=market["id"],
            market_title=market.get("question", market["id"]),
            tokens=market["tokens"],
            family_id=family,
            family_keys=family_keys(market),
            day_utc=time.strftime("%Y-%m-%d", time.gmtime(now / 10**9)),
            dependence_group=digest([now // (30 * 10**9), family]),
            shared_feed_time_block=now // (30 * 10**9),
            decision_ns=now,
            decision_monotonic_ns=mono,
            decision_ordinal=record["ordinal"],
            source_record_ref=ref,
            source_state_sha256=self.ctx.engine.digest(),
            source_input_lag_ns=now - record["received_ns"],
            producer_implementation_sha256=self.ctx.producer_hash,
            reconstruction_version=self.ctx.engine.reconstruction_version,
            feature_version=FEATURE_VERSION,
            label_version=LABEL_VERSION,
            features=f,
            baseline=baseline,
            feature_sha256=digest(f) if f else None,
            feature_sources=self.ctx.lineage(market),
            quality_reason=reason,
            hypothetical_context=dict(
                quantity=self.i["quantity"],
                capital=self.i["capital"],
                unit="collateral_unit",
                orders_submitted=False,
                capital_is_not_market_fact=True,
            ),
            horizon_ms=1000,
            selection_role=market.get("selection_role"),
            sampling_reason="additional_observed_discrepancy"
            if opportunity and now < due
            else "scheduled_all_market_control",
            settlement_lock_ns=max(
                self.i["settlement_lock_days"] * 86400 * 10**9, self.i["end_ns"] - now
            ),
            capital_rule="Reserved hypothetical risk is not recycled during campaign; no actual settlement proceeds inferred",
        )
        if f is not None:
            held = {p: self.journal.reserves(p, now) for p in POLICIES}
            for rs in held.values():
                for r in rs:
                    r["family_id"] = aliases.get("condition:" + r["condition"], r["family_id"])
            row["policies"], row["predictions"] = decide(
                row, self.models, self.i["eligibility_at_freeze"], held, self.i["risk"]
            )
        else:
            row["policies"] = [
                dict(
                    policy=p,
                    action="abstain",
                    reason=reason,
                    reserved_capital="0",
                    orders_submitted=False,
                )
                for p in POLICIES
            ]
            row["predictions"] = {}
        row["decision_latency_ns"] = time.monotonic_ns() - mono
        row["decision_computed_ns"] = time.time_ns()
        if self.journal.decision(row, self.runtime()):
            commit = self.journal.db.execute(
                "select commit_ns from decisions where id=?", (row["id"],)
            ).fetchone()[0]
            item = dict(row=row, committed_ns=commit, horizons=list(self.i["horizons_ms"]))
            self.pending.append(item)
            if baseline is None:
                for h in list(item["horizons"]):
                    self.finish(item, h, censor("invalid_at_decision"), ref)

    def consume(self, record: dict[str, Any], ref: dict[str, Any]) -> None:
        barrier = self.ctx.consume(record, ref)
        self.counters["records"] += 1
        self.follow(record, ref, barrier)
        now = time.time_ns()
        mono = time.monotonic_ns()
        if (
            self.last_clock
            and abs((now - self.last_clock[0]) - (mono - self.last_clock[1])) > 100 * 10**6
        ):
            for item in self.pending:
                for h in list(item["horizons"]):
                    self.finish(item, h, censor("shadow_clock_uncertainty"), ref)
            self.status = "DEGRADED_CLOCK"
            self.last_clock = (now, mono)
            return
        self.last_clock = (now, mono)
        if now < self.i["start_ns"]:
            self.status = "FROZEN_WAITING_START"
            return
        if now >= self.i["end_ns"]:
            self.status = "COMPLETED_PERIOD"
            self.status = "DRAINING_FINAL_FOLLOWUPS"
            return
        lag = now - record["received_ns"]
        if record["kind"] != "frame" or record["received_ns"] < self.i["start_ns"]:
            return
        if lag < 0 or lag > self.i["max_decision_input_lag_ms"] * 10**6:
            self.counters["lagged_frames_skipped"] += 1
            self.status = "WARMING_OR_LAGGED_SOURCE"
            return
        if (
            self.ctx.producer_hash not in self.i["allowed_producer_hashes"]
            or self.ctx.engine.reconstruction_version
            not in self.i["allowed_reconstruction_versions"]
        ):
            self.status = "PAUSED_UNSUPPORTED_SOURCE_REVISION"
            return
        self.status = "FORWARD_EVALUATING_EXPERIMENTAL"
        for market in self.ctx.cohort.values():
            reason = pair_quality(market, self.ctx.engine.books, now, self.spec)
            if reason is None and any(t in self.ctx.bad for t in market["tokens"]):
                reason = "independent_book_divergence"
            self.observe(market, now, reason)
            self.decision(market, record, ref, now, mono, reason)

    def expire_unavailable(self, now: int) -> None:
        for item in self.pending:
            for h in list(item["horizons"]):
                deadline = item["row"]["decision_ns"] + (h + self.spec.tolerance_ms(h)) * 10**6
                if now > deadline + 2 * 10**9:
                    self.finish(item, h, censor("source_followup_availability_timeout"), None)
        self.pending = [p for p in self.pending if p["horizons"]]

    def loop(self) -> None:
        try:
            while self.running:
                entry = self.tail.next()
                if entry:
                    self.consume(*entry)
                else:
                    self.expire_unavailable(time.time_ns())
                    if time.time_ns() >= self.i["end_ns"] + 8 * 10**9:
                        self.status = "COMPLETED_PERIOD"
                        self.running = False
                    time.sleep(0.05)
                for seal in self.tail.seals:
                    with self.journal.db:
                        self.journal.append("source_segment_sealed", seal)
                self.tail.seals.clear()
                if time.monotonic() - self.last_save >= 5:
                    aliases = self.ctx.families.identities()
                    with self.journal.db:
                        self.journal.db.executemany(
                            "insert or replace into family_map values(?,?)",
                            [
                                (k.removeprefix("condition:"), v)
                                for k, v in aliases.items()
                                if k.startswith("condition:")
                            ],
                        )
                    totals = self.journal.summary()
                    if (
                        totals["decisions"] >= self.i["max_decisions"]
                        or totals["observations"] >= self.i["max_observations"]
                    ):
                        raise ValueError("Frozen campaign evidence-row limit reached")
                    self.save()
            self.save()
        except Exception as error:
            self.status = "FAILED"
            with self.journal.db:
                self.journal.append(
                    "worker_failure", dict(error_type=type(error).__name__, error=str(error))
                )
            self.save(failure=True)
            raise
        finally:
            self.tail.close()
            self.journal.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    args = parser.parse_args()
    root = args.campaign.parent
    with (root / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        worker = Shadow(root, json.loads(args.campaign.read_text()))

        def stop(*_: Any) -> None:
            worker.running = False
            worker.status = "STOPPED_WITH_RECOVERABLE_PENDING"

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        worker.loop()


if __name__ == "__main__":
    main()
