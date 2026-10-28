"""Bounded synthetic upper-bound benchmark for event payoff basket search.

Run from the repository root with:

    PYTHONPATH=packages:. /usr/bin/time -v \
      /home/charlie/midas/.venv/bin/python \
      tests/frontier/benchmark_payoff_basket_search.py

The inputs are controlled test fixtures. The benchmark measures bounded
enumeration and candidate evaluation only; it is not a market observation or
an economic performance study.
"""

from __future__ import annotations

import argparse
import statistics
from datetime import timedelta
from decimal import Decimal
from time import perf_counter

from midas.frontier.economics import generate_bounded_payoff_basket_candidates
from midas.frontier.models import FrontierMarket, StatePayout
from test_relationships_economics_replay import (
    T0,
    _multi_outcome_books,
    _multi_outcome_market,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-candidates", type=int, default=32)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 50:
        parser.error("--repeats must be between 1 and 50")
    if not 1 <= args.max_candidates <= 32:
        parser.error("--max-candidates must be between 1 and 32")

    base = _multi_outcome_market(state_count=16)
    state_ids = base.payoff.state_ids
    instruments = tuple(
        instrument.model_copy(
            update={
                "payouts": tuple(
                    StatePayout(state_id=state, amount=Decimal(1)) for state in state_ids
                )
            }
        )
        for instrument in base.instruments[:12]
    )
    market = FrontierMarket.model_validate(
        base.model_dump(mode="python") | {"instruments": instruments}
    )
    books = _multi_outcome_books(market, asks=("0.10",) * len(instruments))
    kwargs = {
        "as_of_utc": T0 + timedelta(milliseconds=100),
        "max_candidates": args.max_candidates,
    }

    warmup = generate_bounded_payoff_basket_candidates(market, books, **kwargs)
    samples: list[float] = []
    counts: list[int] = []
    for _ in range(args.repeats):
        start = perf_counter()
        candidates = generate_bounded_payoff_basket_candidates(market, books, **kwargs)
        samples.append(perf_counter() - start)
        counts.append(len(candidates))
    if counts != [args.max_candidates] * args.repeats:
        raise RuntimeError(f"unexpected candidate counts: {counts}")

    subset_count = (1 << len(instruments)) - 1
    print(
        f"instruments={len(instruments)} states={len(state_ids)} enumerated_subsets={subset_count}"
    )
    print(
        f"qualifying_subsets={subset_count} requested_max_candidates={args.max_candidates} "
        f"warmup_candidates={len(warmup)} repeated_candidate_counts={counts}"
    )
    print("seconds=" + ",".join(f"{value:.6f}" for value in samples))
    print(f"median_seconds={statistics.median(samples):.6f} max_seconds={max(samples):.6f}")
    print(
        "input=synthetic verified-market fixture with every contract paying one "
        "unit in every terminal state; no network or store access"
    )


if __name__ == "__main__":
    main()
