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
from midas.frontier.models import BookSnapshot, FrontierMarket, StatePayout
from test_relationships_economics_replay import (
    T0,
    _multi_outcome_books,
    _multi_outcome_market,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-candidates", type=int, default=32)
    parser.add_argument(
        "--case",
        choices=("all", "single-basket", "eleven-baskets", "no-basket", "dense-ceiling"),
        default="all",
    )
    args = parser.parse_args()
    if not 1 <= args.repeats <= 50:
        parser.error("--repeats must be between 1 and 50")
    if not 1 <= args.max_candidates <= 32:
        parser.error("--max-candidates must be between 1 and 32")

    vectors_by_case = {
        "single-basket": (
            ((1, 1, 0), (0, 1, 1), (1, 0, 1)),
            1,
        ),
        "eleven-baskets": (
            tuple((1,) + (0,) * 15 for _ in range(11)) + ((0,) + (1,) * 15,),
            11,
        ),
        "no-basket": (
            tuple((1,) + (0,) * 15 for _ in range(12)),
            0,
        ),
        "dense-ceiling": (
            tuple((1,) * 16 for _ in range(12)),
            4095,
        ),
    }
    selected_cases = tuple(vectors_by_case) if args.case == "all" else (args.case,)
    for case_name in selected_cases:
        vectors, expected_qualifying_subsets = vectors_by_case[case_name]
        market, books = _build_synthetic_case(case_name, vectors)
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

        expected_candidates = min(args.max_candidates, expected_qualifying_subsets)
        if len(warmup) != expected_candidates or counts != [expected_candidates] * args.repeats:
            raise RuntimeError(
                f"{case_name}: expected {expected_candidates} candidates, got warmup="
                f"{len(warmup)} repeated={counts}"
            )

        instrument_count = len(vectors)
        state_count = len(vectors[0])
        enumerated_subsets = (1 << instrument_count) - 1
        print(
            f"case={case_name} instruments={instrument_count} states={state_count} "
            f"enumerated_subsets={enumerated_subsets} "
            f"qualifying_subsets={expected_qualifying_subsets} "
            f"returned_candidates={expected_candidates}"
        )
        print("seconds=" + ",".join(f"{value:.6f}" for value in samples))
        print(f"median_seconds={statistics.median(samples):.6f} max_seconds={max(samples):.6f}")
    print("input=synthetic fixtures only; no network or store access")


def _build_synthetic_case(
    case_name: str, vectors: tuple[tuple[int, ...], ...]
) -> tuple[FrontierMarket, dict[str, BookSnapshot]]:
    state_ids = tuple(
        ("red", "green", "blue", *(f"state-{index}" for index in range(3, len(vectors[0]))))
    )
    base = _multi_outcome_market(state_count=len(state_ids))
    instruments = tuple(
        instrument.model_copy(
            update={
                "label": f"Synthetic {case_name} claim {index + 1}",
                "outcome_id": f"synthetic-{case_name}-{index + 1}",
                "payouts": tuple(
                    StatePayout(state_id=state, amount=Decimal(value))
                    for state, value in zip(state_ids, vector, strict=True)
                ),
            }
        )
        for index, (instrument, vector) in enumerate(
            zip(base.instruments[: len(vectors)], vectors, strict=True)
        )
    )
    market_data = base.model_dump(mode="python")
    market_data.update(
        title=f"Synthetic {case_name} payoff-search fixture",
        instruments=instruments,
        payoff=base.payoff.model_dump(mode="python")
        | {"verification_basis": f"synthetic {case_name} benchmark"},
    )
    market = FrontierMarket.model_validate(market_data)
    books = _multi_outcome_books(market, asks=("0.10",) * len(instruments))
    return market, books


if __name__ == "__main__":
    main()
