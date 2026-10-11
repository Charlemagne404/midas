"""Versioned fault laboratory and differential execution using production state machine."""

from typing import Any

from midas.arbitrage.engine import BinaryStrategy
from midas.core.models import Book, Market, MarketEvent
from midas.economics.attestation import VERSION as ECONOMIC_VERSION
from midas.economics.attestation import digest
from midas.paper.broker import (
    AccountConfig,
    ExecutionModel,
    audit,
    initial,
    serial,
    summary,
    transition,
)
from midas.simulation.exchange import Exchange
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

FAULTS = (
    "none",
    "withdraw",
    "pause",
    "lost_ack",
    "delayed_ack",
    "out_of_order",
    "fee_change",
    "invalidate",
    "restart",
    "duplicate",
    "metadata_conflict",
    "settlement_delay",
    "ledger_fault",
    "malformed",
    "stale",
)
VERSION = "paper-fault-lab-2"


def run_experiment(
    seed: int = 7, execution: ExecutionModel | None = None, fault: str = "none"
) -> dict[str, Any]:
    if fault not in FAULTS:
        raise ValueError("Unknown fault")
    model = execution or ExecutionModel()
    model = model.model_copy(update={"seed": seed})
    config = AccountConfig(execution=model)
    state = initial(config)
    market, books = binary_fixture(ts=DEMO_EPOCH)
    ts = DEMO_EPOCH
    command: dict[str, Any] = {
        "id": "signal",
        "kind": "observe",
        "ts": ts,
        "market": market.model_dump(mode="json"),
        "books": {a: b.model_dump(mode="json") for a, b in books.items()},
    }
    state = transition(state, command)
    timeline: list[dict[str, Any]] = [{"command": command, "portfolio": summary(state, ts)}]
    inputs = [command]
    actions = sorted(state["pending"], key=lambda p: (p["due"], p["id"]))
    if fault == "out_of_order":
        # Late acknowledgment delivered before other venue messages; no blind resubmission.
        actions = sorted(actions, key=lambda p: (p["kind"] != "ack", p["due"], p["id"]))
    errors = []
    injected = False
    for a in actions:
        ts = max(ts, a["due"])
        cmd: dict[str, Any] = {"id": a["id"], "kind": "action", "ts": ts, "action_id": a["id"]}
        if not injected and a["kind"] == (
            "ack" if fault in {"lost_ack", "delayed_ack"} else "match"
        ):
            injected = True
            if fault in {"withdraw", "lost_ack"}:
                cmd["fault"] = fault
            elif fault == "pause":
                cmd["market"] = market.model_copy(update={"accepting_orders": False}).model_dump(
                    mode="json"
                )
            elif fault == "fee_change":
                from decimal import Decimal

                cmd["market"] = market.model_copy(
                    update={"fee": market.fee.model_copy(update={"rate": Decimal(".07")})}
                ).model_dump(mode="json")
            elif fault == "invalidate":
                cmd["market"] = market.model_copy(update={"payout_verified": False}).model_dump(
                    mode="json"
                )
            elif fault == "delayed_ack":
                ts += 5000
                cmd["ts"] = ts
            elif fault == "metadata_conflict":
                cmd["market"] = market.model_copy(
                    update={"description": "Rules changed"}
                ).model_dump(mode="json")
            elif fault == "stale":
                ts += 16000
                cmd["ts"] = ts
            elif fault == "malformed":
                bad = dict(command["books"])
                bad[next(iter(bad))] = {"asset_id": "broken"}
                cmd["books"] = bad
            elif fault == "restart":
                state = serial(state)
                cmd["fault"] = "none"
            elif fault == "ledger_fault":
                broken = serial(state)
                position = broken["positions"]["signal"]["exchange"]
                if position["ledger"]:
                    position["ledger"][0]["reserved_delta"] = "0"
                try:
                    detected = audit(broken)
                except ValueError:
                    detected = ["Invalid ledger prefix"]
                if not detected:
                    errors.append("Ledger fault was not detected")
        try:
            state = transition(state, cmd)
        except ValueError as error:
            if fault != "malformed":
                raise
            timeline.append(
                {
                    "command": serial(cmd),
                    "rejected_fault": str(error),
                    "portfolio": summary(state, ts),
                }
            )
            # Input rejected atomically; valid event retry proceeds.
            cmd.pop("books", None)
            state = transition(state, cmd)
        inputs.append(cmd)
        if fault == "duplicate":
            after = digest(state)
            state = transition(state, cmd)
            if digest(state) != after:
                errors.append("Duplicate action changed state")
        timeline.append({"command": cmd, "portfolio": summary(state, ts)})
    ts += 86_400_000 if fault == "settlement_delay" else 1000
    payout = {i.asset_id: "1" if index == 0 else "0" for index, i in enumerate(market.instruments)}
    settlement = {
        "id": "settle",
        "kind": "settle",
        "ts": ts,
        "position": "signal",
        "payout": payout,
    }
    state = transition(state, settlement)
    inputs.append(settlement)
    timeline.append({"command": settlement, "portfolio": summary(state, ts)})
    errors.extend(audit(state))
    result = {
        "experiment_version": VERSION,
        "strategy_version": BinaryStrategy.version,
        "venue_version": Exchange.version,
        "simulator_version": "paper-broker-2",
        "dataset_version": "binary-fixture-1",
        "dataset_hash": digest(command),
        "economic_verification_config": {
            "version": ECONOMIC_VERSION,
            "attestation_ttl_ms": 300_000,
            "fee_rule_version": "polymarket-fees-2026-10-11",
        },
        "data_source": "SYNTHETIC",
        "seed": seed,
        "fault": fault,
        "execution_model": model.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
        "start_ts_ms": DEMO_EPOCH,
        "end_ts_ms": ts,
        "inputs": inputs,
        "timeline": timeline,
        "expected_invariant": "Exact balance conservation, hard risk constraints, idempotency, deterministic replay",
        "actual_result": summary(state, ts),
        "errors": errors,
        "passed": not errors,
        "reproduction": f".venv/bin/python scripts/paper_lab.py --seed {seed} --fault {fault} --model {model.name}",
    }
    result["artifact_hash"] = digest(result)
    return result


def differential(seed: int = 7, fault: str = "none") -> dict[str, Any]:
    runs = [
        run_experiment(seed, ExecutionModel.preset(name), fault)
        for name in ("optimistic", "standard", "conservative")
    ]
    return {
        "source": "SYNTHETIC",
        "seed": seed,
        "fault": fault,
        "runs": runs,
        "comparison": [
            {
                "model": r["execution_model"]["name"],
                "theoretical_profit": r["timeline"][0]["portfolio"]["decisions"][0]["evaluation"][
                    "net_profit"
                ],
                "realized_pnl": r["actual_result"]["realized_pnl"],
                "fill_count": r["actual_result"]["hypothetical_fills"],
                "fees": r["actual_result"]["fees"],
                "max_drawdown": r["actual_result"]["max_drawdown"],
                "lockup_ms": r["end_ts_ms"] - r["start_ts_ms"],
            }
            for r in runs
        ],
    }


async def replay_events(broker: Any, events: list[MarketEvent]) -> None:
    """Chronological recorded LIVE observations; no future snapshots/settlements exposed."""
    books: dict[str, Book] = {}
    markets: dict[str, Market] = {}
    last = -1
    seen: set[str] = set()
    for event in events:
        if event.event_id in seen:
            continue
        if event.received_ts_ms < last:
            raise ValueError("Historical receipt clock regresses")
        seen.add(event.event_id)
        last = event.received_ts_ms
        if event.kind == "metadata":
            from midas.market_data.polymarket import normalize_market

            m = normalize_market(event.raw)
            markets[m.id] = m
        if event.kind == "attested_metadata":
            m = Market.model_validate(event.raw["market"])
            markets[m.id] = m
        if event.book:
            books[event.book.asset_id] = event.book
        elif event.asset_id in books:
            books[event.asset_id] = books[event.asset_id].model_copy(update={"valid": False})
        elif event.kind == "price_change":
            for delta in event.raw.get("price_changes", []):
                if delta.get("asset_id") in books:
                    books[delta["asset_id"]] = books[delta["asset_id"]].model_copy(
                        update={"valid": False}
                    )
        if event.kind == "verified_resolution":
            for position_id, item in list(broker.state["positions"].items()):
                if (
                    item["exchange"]["market"]["id"] == event.raw["market_id"]
                    and not item["exchange"]["settled"]
                ):
                    await broker.apply(
                        {
                            "id": f"settlement:{position_id}",
                            "kind": "settle",
                            "ts": last,
                            "position": position_id,
                            "resolution_evidence": event.raw["resolution_evidence"],
                        }
                    )
        # Arrival updates are applied before pending orders, never before their timestamp.
        await broker.tick(last, books, markets)
        if event.book:
            for m in markets.values():
                if event.book.asset_id in {i.asset_id for i in m.instruments}:
                    await broker.apply(
                        {
                            "id": f"replay:{event.event_id}:{m.id}",
                            "kind": "observe",
                            "ts": last,
                            "market": m.model_dump(mode="json"),
                            "books": {
                                a: b.model_dump(mode="json")
                                for a, b in books.items()
                                if a in {i.asset_id for i in m.instruments}
                            },
                        }
                    )
