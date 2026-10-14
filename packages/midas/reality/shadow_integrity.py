"""Read-only scheduled integrity check, independent of the live shadow worker."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .model_registry import load
from .research_schema import digest
from .shadow_store import Journal
from .storage import atomic_json, file_hash


def check(root: Path) -> dict[str, Any]:
    plan = json.loads((root / "campaign.json").read_text())
    i = plan["identity"]
    if digest(i) != plan["campaign_id"]:
        raise ValueError("Frozen campaign identity corruption")
    for name, sha in i["code"].items():
        if file_hash(root / "code" / "midas" / name) != sha:
            raise ValueError("Frozen implementation corruption")
    for model in i["models"].values():
        load(Path(i["training_root"]), model["model_id"], model["weights_sha256"])
    journal = Journal.__new__(Journal)
    journal.db = sqlite3.connect(
        "file:" + str((root / "shadow.sqlite").resolve()) + "?mode=ro", uri=True
    )
    journal.db.execute("begin")
    integrity = journal.verify()
    state = journal.runtime()
    journal.db.close()
    if state is None or state["campaign_id"] != plan["campaign_id"]:
        raise ValueError("Campaign checkpoint mismatch")
    return dict(
        campaign_id=plan["campaign_id"],
        checked_ns=time.time_ns(),
        state="INTEGRITY_VERIFIED",
        journal=integrity,
        code_files=len(i["code"]),
        models=len(i["models"]),
        scope="Artifact hashes, SQLite/event chain and runtime identity; full raw/public-label replay is a separate audit",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.root)
    atomic_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
