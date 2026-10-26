"""Read-only full replay audit for a persisted paper account journal."""

import argparse
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from midas.economics.attestation import digest
from midas.paper.broker import audit, summary

from apps.api.paper import advance_journal_hash, journal_entry, replay_journal
from apps.api.state_codec import decode_state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/midas.db"))
    parser.add_argument("--account", default="paper-demo")
    args = parser.parse_args()
    database = args.database.expanduser().resolve()
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("BEGIN")
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_accounts)")}
        head_column = "journal_hash" if "journal_hash" in columns else "NULL"
        account = connection.execute(
            f"SELECT revision,payload,checksum,{head_column} AS journal_hash "
            "FROM paper_accounts WHERE id=?",
            (args.account,),
        ).fetchone()
        if account is None:
            raise ValueError(f"Paper account not found: {args.account}")
        rows = connection.execute(
            "SELECT revision,event_id,command,payload,checksum,previous_checksum "
            "FROM paper_events WHERE account_id=? ORDER BY revision",
            (args.account,),
        )
        rolling_hash = ""
        event_count = 0

        def events() -> Iterator[dict[str, Any]]:
            nonlocal rolling_hash, event_count
            for row in rows:
                event: dict[str, Any] = {
                    "revision": row["revision"],
                    "event_id": row["event_id"],
                    "command": json.loads(row["command"]),
                    "payload": json.loads(row["payload"]),
                    "checksum": row["checksum"],
                    "previous_checksum": row["previous_checksum"],
                }
                rolling_hash = advance_journal_hash(
                    rolling_hash,
                    journal_entry(
                        args.account,
                        event["event_id"],
                        event["revision"],
                        event["command"],
                        event["payload"],
                        event["checksum"],
                        event["previous_checksum"],
                    ),
                )
                event_count += 1
                yield event

        state = replay_journal(events())
        snapshot_matches = (
            digest(decode_state(json.loads(account["payload"]))) == account["checksum"]
        )
        errors = audit(state)
        valid = (
            account["revision"] == event_count - 1
            and digest(state) == account["checksum"]
            and snapshot_matches
            and not errors
            and (account["journal_hash"] is None or account["journal_hash"] == rolling_hash)
        )
        report = {
            "valid": valid,
            "account": args.account,
            "events": event_count,
            "revision": account["revision"],
            "state_checksum_matches": digest(state) == account["checksum"],
            "snapshot_checksum_matches": snapshot_matches,
            "journal_hash_matches": account["journal_hash"] is None
            or account["journal_hash"] == rolling_hash,
            "reconciliation_errors": errors,
            "accounting": summary(state),
        }
        print(json.dumps(report, indent=2))
        if not valid:
            raise SystemExit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
