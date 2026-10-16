"""Run one isolated Veritas eight-read discovery-successor scan.

The CLI refuses to run before the fixed v1 coverage pilot reaches its recorded
stop time. The successor writes to its own root and never updates the v1 pilot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from midas.veritas.discovery_successor import (
    DEFAULT_CONTROL_FILE,
    DEFAULT_ROOT,
    require_fixed_pilot_stop,
    run_discovery_successor,
)
from midas.veritas.observatory import (
    DEFAULT_MARKETS,
    DEFAULT_QUANTITIES,
    DEFAULT_SEED,
    REQUEST_INTERVAL_SECONDS,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--control-file", type=Path, default=DEFAULT_CONTROL_FILE)
    parser.add_argument("--markets", type=int, default=DEFAULT_MARKETS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--quantities", default=",".join(DEFAULT_QUANTITIES))
    parser.add_argument("--request-interval", type=float, default=REQUEST_INTERVAL_SECONDS)
    args = parser.parse_args()
    require_fixed_pilot_stop()
    quantities = tuple(part.strip() for part in args.quantities.split(",") if part.strip())
    report = asyncio.run(
        run_discovery_successor(
            args.root,
            control_file=args.control_file,
            target_markets=args.markets,
            seed=args.seed,
            quantity_grid=quantities,
            request_interval_seconds=args.request_interval,
        )
    )
    from midas.veritas.discovery_successor import _successor_summary

    print(json.dumps(_successor_summary(report), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
