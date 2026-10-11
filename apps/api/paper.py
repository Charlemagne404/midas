"""Transactional manager. Strategy/venue never see database or public transport."""

import asyncio
from collections.abc import Callable
from typing import Any

from midas.economics.attestation import digest
from midas.paper.broker import AccountConfig, audit, initial, summary, transition
from sqlalchemy import select, update

from apps.api.storage import PaperAccount, PaperEvent, Store


def journal_payload(state: dict[str, Any], previous: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "state_checksum": digest(state),
        "kind": kind,
        "decision": state["decisions"][-1] if kind == "observe" else None,
        "ledger_entries": [
            {"position_id": k, **entry}
            for k, v in state["positions"].items()
            for entry in v["exchange"]["ledger"][
                len(
                    previous["positions"].get(k, {"exchange": {"ledger": []}})["exchange"]["ledger"]
                ) :
            ]
        ],
    }


class PaperBroker:
    def __init__(self, store: Store, account_id: str, config: AccountConfig) -> None:
        self.store, self.account_id, self.config = store, account_id, config
        self.state: dict[str, Any] = {}
        self.lock = asyncio.Lock()
        self.healthy = False
        self.revision = -1

    async def start(self, ts: int) -> None:
        async with self.lock:
            async with self.store.sessions.begin() as session:
                account = await session.get(PaperAccount, self.account_id)
                if account is None:
                    state = initial(self.config)
                    checksum = digest(state)
                    session.add(
                        PaperAccount(
                            id=self.account_id, revision=0, payload=state, checksum=checksum
                        )
                    )
                    session.add(
                        PaperEvent(
                            account_id=self.account_id,
                            event_id="initial",
                            revision=0,
                            command={
                                "kind": "initial",
                                "config": self.config.model_dump(mode="json"),
                            },
                            payload={"state_checksum": checksum, "kind": "initial"},
                            checksum=checksum,
                            previous_checksum="",
                        )
                    )
                else:
                    events = list(
                        await session.scalars(
                            select(PaperEvent)
                            .where(PaperEvent.account_id == self.account_id)
                            .order_by(PaperEvent.revision)
                        )
                    )
                    if not events or events[0].revision != 0:
                        raise ValueError("Missing initial financial journal")
                    reconstructed = initial(
                        AccountConfig.model_validate(events[0].command["config"])
                    )
                    previous = ""
                    for revision, e in enumerate(events):
                        prior_state = reconstructed
                        if revision:
                            reconstructed = transition(reconstructed, e.command)
                        expected_payload = (
                            journal_payload(reconstructed, prior_state, e.command["kind"])
                            if revision
                            else {"state_checksum": digest(reconstructed), "kind": "initial"}
                        )
                        if (
                            e.revision != revision
                            or e.previous_checksum != previous
                            or digest(e.payload) != digest(expected_payload)
                            or digest(reconstructed) != e.checksum
                        ):
                            raise ValueError(
                                "Journal corruption or inconsistent event replay; account halted"
                            )
                        previous = e.checksum
                    if (
                        account.revision != len(events) - 1
                        or digest(account.payload) != account.checksum
                        or account.checksum != previous
                        or audit(account.payload)
                    ):
                        raise ValueError(
                            "Inconsistent account snapshot; account halted, no automatic financial repair"
                        )
                    if account.payload["config"]["mode"] != self.config.mode:
                        raise ValueError("Account mode cannot be changed on restart")
                    state = account.payload
            self.state = state
            self.config = AccountConfig.model_validate(state["config"])
            self.revision = 0 if account is None else account.revision
            self.healthy = True
        # Recovery itself is durable; replay/reconcile precedes any resumed action.
        await self.apply(
            {
                "id": f"recovery:{self.revision + 1}",
                "kind": "recovery",
                "ts": max(ts, state["last_processed_ms"] or ts),
            }
        )

    async def apply(
        self,
        command: dict[str, Any],
        crash: str | None = None,
        crash_hook: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        async with self.lock:
            if not self.healthy:
                raise ValueError("Paper broker reconciliation/persistence is unhealthy")
            try:
                async with self.store.sessions.begin() as session:
                    account = await session.get(PaperAccount, self.account_id)
                    if account is None:
                        raise ValueError("Missing durable account")
                    prior = await session.get(PaperEvent, (self.account_id, command["id"]))
                    if prior is not None:
                        if digest(prior.command) != digest(command):
                            raise ValueError("Event ID reused with different command")
                        self.state = account.payload
                        self.revision = account.revision
                        return summary(self.state, command["ts"])
                    if digest(account.payload) != account.checksum:
                        raise ValueError("Account checksum mismatch")
                    next_state = transition(account.payload, command)
                    checksum = digest(next_state)
                    # CAS prevents lost updates between independent managers/processes.
                    result = await session.execute(
                        update(PaperAccount)
                        .where(
                            PaperAccount.id == self.account_id,
                            PaperAccount.revision == account.revision,
                        )
                        .values(
                            payload=next_state,
                            revision=account.revision + 1,
                            checksum=checksum,
                        )
                        .execution_options(synchronize_session=False)
                    )
                    if result.rowcount != 1:  # type: ignore[attr-defined]
                        raise ValueError(
                            "Concurrent paper writer conflict; retry with same event ID after recovery"
                        )
                    session.add(
                        PaperEvent(
                            account_id=self.account_id,
                            event_id=command["id"],
                            revision=account.revision + 1,
                            command=command,
                            payload=journal_payload(next_state, account.payload, command["kind"]),
                            checksum=checksum,
                            previous_checksum=account.checksum,
                        )
                    )
                    await session.flush()
                    if crash_hook:
                        crash_hook("before_commit")
                    if crash == "before_commit":
                        raise RuntimeError("Injected crash before ledger commit")
                if crash_hook:
                    crash_hook("after_commit")
                if crash == "after_commit":
                    raise RuntimeError("Injected crash after ledger commit before publish")
                self.state, self.revision = next_state, account.revision + 1
                return summary(self.state, command["ts"])
            except Exception:
                self.healthy = False
                raise

    async def tick(self, ts: int, books: dict[str, Any], markets: dict[str, Any]) -> None:
        for p in sorted(list(self.state["pending"]), key=lambda x: (x["due"], x["id"])):
            if p["due"] > ts:
                continue
            x = self.state["positions"][p["position"]]["exchange"]
            market = markets.get(x["market"]["id"])
            await self.apply(
                {
                    "id": p["id"],
                    "kind": "action",
                    "ts": ts,
                    "action_id": p["id"],
                    "books": {
                        a: b.model_dump(mode="json") for a, b in books.items() if a in x["books"]
                    },
                    "market": market.model_dump(mode="json") if market else None,
                }
            )
