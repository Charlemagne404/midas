"""Read-only final verification of every retained recovery and unwind study."""

import json
import time
from pathlib import Path

from midas.arena.artifacts import atomic_json, sha256

from scripts.verify_recovery import verify as recovery
from scripts.verify_unwind import verify as unwind


def verify(root: Path) -> dict:
    reports = []
    for kind, check in (("recoveries", recovery), ("unwinds", unwind)):
        for path in sorted((root / kind).glob("*/manifest.json")):
            result = check(root, path.parent.name)
            reports.append({"kind": kind, **result, "manifest_sha256": sha256(path)})
            print(
                json.dumps(
                    {"study": path.parent.name, "verified_replays": result["verified_replays"]}
                ),
                flush=True,
            )
    return {
        "checked_at": time.time(),
        "reports": reports,
        "verified_replays": sum(r["verified_replays"] for r in reports),
        "producer_hashes": {
            name: sha256(Path(__file__).parent / name)
            for name in ("verify_final_recovery.py", "verify_recovery.py", "verify_unwind.py")
        },
        "limitations": "Retained synthetic evidence reverified; not a new cohort, broker training run or observed execution result. Separate verifier scopes are recorded per study.",
    }


if __name__ == "__main__":
    result = verify(Path("data/arena"))
    atomic_json(Path("docs/PROMETHEUS_FINAL_RECOVERY_AUDIT.json"), result)
    print(json.dumps({"verified_replays": result["verified_replays"]}), flush=True)
