"""Inspect logical account heads or atomically restore plain JSON before code rollback.

Inspection is read-only. Materialization requires an explicitly stopped API and
never changes account revisions, checksums, journal heads, or historical events.
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from apps.api.state_codec import MARKER, decode_state

API_UNITS = ("midas-api.service", "midas-reality-api.service")


def require_stopped(service: str) -> None:
    if service not in API_UNITS:
        raise ValueError("Only MIDAS API units are supported; recorder control is forbidden")
    raw = subprocess.check_output(
        ["systemctl", "--user", "show", service, "-p", "MainPID", "-p", "ActiveState"],
        text=True,
        timeout=5,
    )
    fields = dict(line.split("=", 1) for line in raw.splitlines())
    if fields.get("MainPID") != "0" or fields.get("ActiveState") not in {"inactive", "failed"}:
        raise ValueError("Stop the API explicitly before materializing account heads")


def inspect_accounts(
    database: Path, *, materialize: bool = False, service: str | None = None
) -> list[dict[str, Any]]:
    if database.is_symlink() or not database.is_file():
        raise ValueError("Account database must be an existing regular file")
    if materialize:
        if service is None:
            raise ValueError("Materialization requires an explicitly stopped API unit")
        require_stopped(service)
    mode = "rw" if materialize else "ro"
    connection = sqlite3.connect(database.resolve().as_uri() + f"?mode={mode}", uri=True, timeout=5)
    try:
        if materialize:
            assert service is not None
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            require_stopped(service)
        else:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
        reports = []
        for identity, revision, raw, checksum, journal_hash in connection.execute(
            "SELECT id,revision,payload,checksum,journal_hash FROM paper_accounts ORDER BY id"
        ):
            stored = json.loads(raw)
            logical = decode_state(stored)
            if not isinstance(logical, dict):
                raise ValueError("Account state is not an object")
            canonical = json.dumps(logical, sort_keys=True, separators=(",", ":"), default=str)
            if hashlib.sha256(canonical.encode()).hexdigest() != checksum:
                raise ValueError(f"Logical account checksum mismatch: {identity}")
            encoded = MARKER in stored
            if materialize and encoded:
                result = connection.execute(
                    "UPDATE paper_accounts SET payload=? WHERE id=? AND revision=? AND checksum=?",
                    (json.dumps(logical), identity, revision, checksum),
                )
                if result.rowcount != 1:
                    raise ValueError("Account changed during materialization")
            reports.append(
                {
                    "account_id": identity,
                    "revision": revision,
                    "checksum": checksum,
                    "journal_hash": journal_hash,
                    "encoding": stored.get(MARKER, "plain-json"),
                    "stored_bytes": len(raw.encode()),
                    "logical_bytes": len(canonical.encode()),
                    "materialized": materialize and encoded,
                }
            )
        if materialize:
            assert service is not None
            require_stopped(service)
            connection.commit()
        return reports
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--service", choices=API_UNITS)
    args = parser.parse_args()
    print(
        json.dumps(
            inspect_accounts(args.database, materialize=args.materialize, service=args.service),
            indent=2,
        )
    )
