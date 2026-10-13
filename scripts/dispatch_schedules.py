"""One bounded dispatcher pass; schedules themselves have finite admission limits."""

import argparse
import fcntl
import json
from pathlib import Path

from midas.arena.scheduling import alert, tick


def dispatch(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "scheduler.lock").open("a+") as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "BUSY", "schedules": []}
        results = []
        for path in sorted(root.glob("schedules/*/manifest.json")):
            record = json.loads(path.read_text())
            if record["state"] in {"COMPLETED", "FAILED", "CANCELLED", "EXPIRED", "STALE_SOURCE", "PAUSED"}:
                continue
            if len(results) >= 100:
                break
            try:
                updated = tick(root, path.parent.name)
                results.append({"schedule_id": path.parent.name, "state": updated["state"]})
            except BlockingIOError:
                results.append({"schedule_id": path.parent.name, "state": "BUSY"})
            except (ValueError, OSError, KeyError) as error:
                alert(root, record, f"Dispatcher failure: {type(error).__name__}: {error}")
                results.append({"schedule_id": path.parent.name, "state": "ERROR", "error": str(error)})
        return {"state": "COMPLETE", "schedules": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    args = parser.parse_args()
    print(json.dumps(dispatch(args.root), indent=2))
