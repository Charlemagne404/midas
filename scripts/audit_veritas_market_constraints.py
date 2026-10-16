#!/usr/bin/env python3
"""Produce a digest-linked Gamma/CLOB market-constraint semantics audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from midas.veritas.market_constraint_audit import audit_market_constraint_semantics


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshots_dir = args.root / "snapshots"
    if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        parser.error("snapshot root is missing or unsafe")
    scan_ids = sorted(
        path.name.removesuffix(".json.gz") for path in snapshots_dir.glob("*.json.gz")
    )
    result = audit_market_constraint_semantics(args.root, scan_ids)
    artifact: dict[str, Any] = {
        "artifact_id": "VERITAS-M2-MARKET-CONSTRAINT-AUDIT-001",
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_root": str(args.root),
        **result,
    }
    artifact["result_sha256"] = hashlib.sha256(_canonical(artifact)).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "artifact_id": artifact["artifact_id"],
                "status": artifact["status"],
                "complete": artifact["complete"],
                "snapshot_count": artifact["snapshot_count"],
                "book_leg_count": artifact["book_leg_count"],
                "result_sha256": artifact["result_sha256"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0 if artifact["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
