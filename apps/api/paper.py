"""Transactional manager. Strategy/venue never see database or public transport."""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from midas.economics.attestation import digest
from midas.paper.broker import AccountConfig, audit, initial, summary, transition
from sqlalchemy import select, update

from apps.api.storage import PaperAccount, PaperEvent, Store

_JOURNAL_VERSION = "paper-journal-v1"


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


def journal_entry(
    account_id: str,
    event_id: str,
    revision: int,
    command: dict[str, Any],
    payload: dict[str, Any],
    checksum: str,
    previous_checksum: str,
) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "event_id": event_id,
        "revision": revision,
        "command": command,
        "payload": payload,
        "checksum": checksum,
        "previous_checksum": previous_checksum,
    }


def advance_journal_hash(previous: str, entry: Mapping[str, Any]) -> str:
    return digest({"version": _JOURNAL_VERSION, "previous": previous, "entry": entry})


def replay_journal(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fully replay and verify a paper event journal for explicit offline audits."""
    if not events:
        raise ValueError("Missing initial financial journal")
    first = events[0]
    command = first["command"]
    if command.get("kind") != "initial":
        raise ValueError("Missing initial financial journal")
    reconstructed = initial(AccountConfig.model_validate(command["config"]))
    previous = ""
    for revision, event in enumerate(events):
        command = event["command"]
        prior_state = reconstructed
        if revision:
            reconstructed = transition(reconstructed, command)
        expected_payload = (
            journal_payload(reconstructed, prior_state, command["kind"])
            if revision
            else {"state_checksum": digest(reconstructed), "kind": "initial"}
        )
        if (
            event["revision"] != revision
            or event["previous_checksum"] != previous
            or event["event_id"] != ("initial" if revision == 0 else command.get("id"))
            or digest(event["payload"]) != digest(expected_payload)
            or digest(reconstructed) != event["checksum"]
        ):
            raise ValueError(
                f"Journal corruption or inconsistent event replay at revision {revision}; account halted"
            )
        previous = event["checksum"]
    return reconstructed


class PaperBroker:
    def __init__(self, store: Store, account_id: str, config: AccountConfig) -> None:
        self.store, self.account_id, self.config = store, account_id, config
        self.state: dict[str, Any] = {}
        self.lock = asyncio.Lock()
        self.healthy = False
        self.revision = -1
        self.recovery_status = "NOT_STARTED"
        self.journal_event_count = 0

    async def start(self, ts: int) -> None:
        async with self.lock:
            async with self.store.sessions.begin() as session:
                account = await session.get(PaperAccount, self.account_id)
                if account is None:
                    state = initial(self.config)
                    checksum = digest(state)
                    initial_command = {
                        "kind": "initial",
                        "config": self.config.model_dump(mode="json"),
                    }
                    initial_payload = {"state_checksum": checksum, "kind": "initial"}
                    rolling_hash = advance_journal_hash(
                        "",
                        journal_entry(
                            self.account_id,
                            "initial",
                            0,
                            initial_command,
                            initial_payload,
                            checksum,
                            "",
                        ),
                    )
                    session.add(
                        PaperAccount(
                            id=self.account_id,
                            revision=0,
                            payload=state,
                            checksum=checksum,
                            journal_hash=rolling_hash,
                        )
                    )
                    session.add(
                        PaperEvent(
                            account_id=self.account_id,
                            event_id="initial",
                            revision=0,
                            command=initial_command,
                            payload=initial_payload,
                            checksum=checksum,
                            previous_checksum="",
                        )
                    )
                    event_count = 1
                    self.recovery_status = "INITIALIZED"
                else:
                    if digest(account.payload) != account.checksum:
                        raise ValueError("Inconsistent account snapshot; account halted")
                    if errors := audit(account.payload):
                        raise ValueError(
                            "Inconsistent account snapshot; account halted: " + "; ".join(errors)
                        )
                    if account.payload["config"]["mode"] != self.config.mode:
                        raise ValueError("Account mode cannot be changed on restart")

                    result = await session.stream(
                        select(
                            PaperEvent.revision,
                            PaperEvent.event_id,
                            PaperEvent.command,
                            PaperEvent.payload,
                            PaperEvent.checksum,
                            PaperEvent.previous_checksum,
                        )
                        .where(PaperEvent.account_id == self.account_id)
                        .order_by(PaperEvent.revision)
                    )
                    previous = ""
                    rolling_hash = ""
                    event_count = 0
                    async for row in result:
                        revision, event_id, command, payload, checksum, previous_checksum = row
                        if revision != event_count or previous_checksum != previous:
                            raise ValueError(
                                f"Paper journal revision or checksum chain is inconsistent at {event_count}"
                            )
                        if (
                            not isinstance(command, dict)
                            or not isinstance(payload, dict)
                            or payload.get("kind") != command.get("kind")
                            or payload.get("state_checksum") != checksum
                        ):
                            raise ValueError(
                                f"Paper journal event is malformed at revision {event_count}"
                            )
                        if event_count == 0:
                            if event_id != "initial" or command.get("kind") != "initial":
                                raise ValueError("Missing initial financial journal")
                            initial_state = initial(AccountConfig.model_validate(command["config"]))
                            if digest(initial_state) != checksum:
                                raise ValueError("Initial paper account checksum is inconsistent")
                        elif command.get("id") != event_id:
                            raise ValueError(
                                f"Paper journal command ID is inconsistent at revision {event_count}"
                            )
                        entry = journal_entry(
                            self.account_id,
                            event_id,
                            revision,
                            command,
                            payload,
                            checksum,
                            previous_checksum,
                        )
                        rolling_hash = advance_journal_hash(rolling_hash, entry)
                        previous = checksum
                        event_count += 1
                    await result.close()
                    if (
                        event_count == 0
                        or account.revision != event_count - 1
                        or account.checksum != previous
                    ):
                        raise ValueError(
                            "Paper account head does not match the journal; account halted"
                        )
                    if account.journal_hash is not None and account.journal_hash != rolling_hash:
                        raise ValueError("Paper journal integrity hash mismatch; account halted")
                    if account.journal_hash is None:
                        # Legacy rows have a verified state/checksum chain but no rolling hash yet.
                        # Bind their exact stored contents once, then verify this head on each boot.
                        account.journal_hash = rolling_hash
                        self.recovery_status = "LEGACY_BASELINED"
                    else:
                        self.recovery_status = "CHECKPOINT_VERIFIED"
                    state = account.payload
                self.journal_event_count = event_count
            self.state = state
            self.config = AccountConfig.model_validate(state["config"])
            self.revision = 0 if account is None else account.revision
            self.healthy = True
        # A checked account snapshot and journal head are durable before recovery is appended.
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
                        self.journal_event_count = account.revision + 1
                        return summary(self.state, command["ts"])
                    if digest(account.payload) != account.checksum:
                        raise ValueError("Account checksum mismatch")
                    next_state = transition(account.payload, command)
                    checksum = digest(next_state)
                    payload = journal_payload(next_state, account.payload, command["kind"])
                    if account.journal_hash is None:
                        raise ValueError("Paper journal head is missing; account halted")
                    rolling_hash = advance_journal_hash(
                        account.journal_hash,
                        journal_entry(
                            account.id,
                            command["id"],
                            account.revision + 1,
                            command,
                            payload,
                            checksum,
                            account.checksum,
                        ),
                    )
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
                            journal_hash=rolling_hash,
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
                            payload=payload,
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
                self.journal_event_count = self.revision + 1
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
