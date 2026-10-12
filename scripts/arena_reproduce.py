"""Read-only verification of an Arena episode; no Laboratory writer is opened."""

import argparse
import json
from pathlib import Path

from midas.arena.reproduce import reproduce

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path("data/arena"))
parser.add_argument("--tournament", required=True)
parser.add_argument("--row", required=True)
args = parser.parse_args()
print(json.dumps(reproduce(args.root, args.tournament, args.row), indent=2))
