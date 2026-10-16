"""Run one bounded Veritas public discovery and snapshot-observation cycle."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from midas.veritas.observatory import (
    DEFAULT_CONTROL_MARKETS,
    DEFAULT_MARKETS,
    DEFAULT_QUANTITIES,
    DEFAULT_SEED,
    REQUEST_INTERVAL_SECONDS,
    _summary,
    run_scan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "veritas-observatory",
    )
    parser.add_argument("--markets", type=int, default=DEFAULT_MARKETS)
    parser.add_argument("--controls", type=int, default=DEFAULT_CONTROL_MARKETS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--quantities", default=",".join(DEFAULT_QUANTITIES))
    parser.add_argument("--request-interval", type=float, default=REQUEST_INTERVAL_SECONDS)
    args = parser.parse_args()
    quantities = tuple(part.strip() for part in args.quantities.split(",") if part.strip())
    report = asyncio.run(
        run_scan(
            args.root,
            target_markets=args.markets,
            control_count=args.controls,
            seed=args.seed,
            quantity_grid=quantities,
            request_interval_seconds=args.request_interval,
        )
    )
    summary = _summary(report)
    # Full per-market detail is preserved in latest-summary.json and the
    # immutable compressed snapshot; keep scheduled service logs compact.
    summary.pop("market_observations", None)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
