"""Start only the immutable campaign implementation; no recorder dependency."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--campaign", type=Path, required=True)
args = parser.parse_args()
plan = json.loads(args.campaign.read_text())
encoded = json.dumps(
    plan["identity"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
).encode()
if hashlib.sha256(encoded).hexdigest() != plan["campaign_id"]:
    raise ValueError("Campaign identity corruption")
root = args.campaign.parent.resolve()
for name, expected in plan["identity"]["code"].items():
    path = root / "code" / "midas" / name
    if (
        path.is_symlink()
        or not path.resolve().is_relative_to(root / "code")
        or hashlib.sha256(path.read_bytes()).hexdigest() != expected
    ):
        raise ValueError("Frozen campaign implementation corruption")
workspace = Path(__file__).resolve().parents[1]
os.environ["PYTHONPATH"] = str(root / "code") + os.pathsep + str(workspace / "packages")
os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "midas.reality.shadow_worker",
        "--campaign",
        str(args.campaign.resolve()),
    ],
)
