"""Versioned exports, verified receipt-ordered replay and online checkpoint checks."""

from pathlib import Path
from typing import Any

from .reconstruction import Engine
from .storage import _read_manifest_for_replay


def replay(root: Path, manifest: dict[str, Any], through: int | None = None) -> tuple[Engine, int]:
    engine = Engine()
    checkpoints = 0
    for record in _read_manifest_for_replay(root, manifest):
        if through is not None and record["ordinal"] > through:
            # Consume the immutable tail so each segment's checksum and manifest
            # metadata are still verified after a prefix-only state reconstruction.
            continue
        if record["kind"] == "checkpoint":
            if engine.digest() != record["payload"]["state_sha256"]:
                raise ValueError(f"Online/replay state differs at {record['ordinal']}")
            checkpoints += 1
        engine.consume(record)
    return engine, checkpoints
