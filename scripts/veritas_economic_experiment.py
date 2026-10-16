"""Run the versioned depth-aware economic qualification comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from midas.veritas.economic_experiment import run_finalized_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "veritas-observatory",
    )
    parser.add_argument("--quantity", default="20")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_finalized_experiment(args.root, quantity=args.quantity)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as handle:
            handle.write(encoded)
            handle.write("\n")
    print(encoded)


if __name__ == "__main__":
    main()
