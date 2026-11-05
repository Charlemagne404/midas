"""Bounded synthetic upper-bound benchmark for multi-market joint-state search.

Run from the repository root with:

    PYTHONPATH=packages:. /usr/bin/time -v \
      /home/charlie/midas/.venv/bin/python \
      tests/frontier/benchmark_joint_state_search.py

The inputs are explicit synthetic fixtures. This measures the configured
12-instrument, 64-joint-state search bound; it is not market data or evidence
of an economic opportunity.
"""

from __future__ import annotations

import argparse
import statistics
from datetime import timedelta
from decimal import Decimal
from time import perf_counter

from builders import T0, book, market
from midas.frontier.economics import ExecutionScenario, OpportunityFamily
from midas.frontier.joint_economics import generate_joint_state_basket_candidates
from midas.frontier.models import (
    BookSnapshot,
    FrontierMarket,
    JointStateMap,
    MarketInstrument,
    MarketKind,
    QuantityUnit,
    StatePayout,
    Venue,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-candidates", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error("--repeats must be between 1 and 20")
    if not 1 <= args.max_candidates <= 32:
        parser.error("--max-candidates must be between 1 and 32")

    markets, books_by_market, mapping = _build_synthetic_case()
    kwargs = {
        "scenario": ExecutionScenario(),
        "as_of_utc": T0 + timedelta(milliseconds=100),
        "max_candidates": args.max_candidates,
    }
    warmup = generate_joint_state_basket_candidates(markets, mapping, books_by_market, **kwargs)
    samples: list[float] = []
    counts: list[int] = []
    for _ in range(args.repeats):
        start = perf_counter()
        candidates = generate_joint_state_basket_candidates(
            markets, mapping, books_by_market, **kwargs
        )
        samples.append(perf_counter() - start)
        counts.append(len(candidates))

    instrument_count = sum(len(item.instruments) for item in markets)
    enumerated_subsets = (1 << instrument_count) - 1
    qualifying_subsets = (2 ** (instrument_count // 2) - 1) ** 2
    expected_candidates = min(args.max_candidates, qualifying_subsets)
    if len(warmup) != expected_candidates or counts != [expected_candidates] * args.repeats:
        raise RuntimeError(
            f"expected {expected_candidates} candidates, got warmup={len(warmup)} repeated={counts}"
        )
    if any(item.family != OpportunityFamily.MULTI_MARKET_JOINT_STATE_BASKET for item in warmup):
        raise RuntimeError("benchmark returned an unexpected candidate family")

    print(
        f"markets={len(markets)} instruments={instrument_count} "
        f"joint_states={len(mapping.joint_state_ids)} enumerated_subsets={enumerated_subsets} "
        f"qualifying_subsets={qualifying_subsets} returned_candidates={expected_candidates}"
    )
    print("seconds=" + ",".join(f"{value:.6f}" for value in samples))
    print(f"median_seconds={statistics.median(samples):.6f} max_seconds={max(samples):.6f}")
    print("input=synthetic fixtures only; no network or store access")


def _build_synthetic_case() -> tuple[
    tuple[FrontierMarket, ...],
    dict[str, dict[str, BookSnapshot]],
    JointStateMap,
]:
    joint_states = tuple(f"joint-state-{index:02d}" for index in range(64))
    markets: list[FrontierMarket] = []
    for market_index, digest in enumerate(("a", "b")):
        base = market(Venue.POLYMARKET, f"joint-search-benchmark-{market_index}")
        instruments = tuple(
            MarketInstrument(
                native_instrument_id=f"{base.native_market_id}:CLAIM:{instrument_index}",
                label=f"Synthetic claim {instrument_index}",
                outcome_id=f"synthetic-claim-{instrument_index}",
                quantity_unit=QuantityUnit.SHARE,
                price_currency="USD",
                price_currency_identity=base.settlement_asset_identity,
                payouts=tuple(
                    StatePayout(state_id=state, amount=Decimal(1)) for state in joint_states
                ),
            )
            for instrument_index in range(6)
        )
        market_data = base.model_dump(mode="python")
        market_data.update(
            market_kind=MarketKind.MULTI_OUTCOME_EVENT,
            instruments=instruments,
            payoff=base.payoff.model_copy(
                update={
                    "state_ids": joint_states,
                    "verification_basis": "synthetic joint-state search ceiling",
                }
            ),
            provenance=base.provenance.model_copy(update={"observation_id": digest * 64}),
        )
        markets.append(FrontierMarket.model_validate(market_data))

    mapping = JointStateMap.create(
        market_ids=tuple(sorted(item.canonical_id for item in markets)),
        joint_state_ids=joint_states,
        state_by_market={
            item.canonical_id: {state: state for state in joint_states} for item in markets
        },
        external_assertion_id="synthetic-12-instrument-64-state-ceiling",
        evidence_observation_ids=("a" * 64, "b" * 64),
        asserted_at_utc=T0 + timedelta(milliseconds=50),
    )
    books_by_market: dict[str, dict[str, BookSnapshot]] = {}
    for market_value in markets:
        books_by_market[market_value.canonical_id] = {}
        for instrument in market_value.instruments:
            snapshot = book(market_value, instrument.native_instrument_id, "0.01")
            books_by_market[market_value.canonical_id][instrument.native_instrument_id] = (
                snapshot.model_copy(
                    update={
                        "provenance": snapshot.provenance.model_copy(
                            update={"clock_uncertainty_ms": Decimal(0)}
                        )
                    }
                )
            )
    return tuple(markets), books_by_market, mapping


if __name__ == "__main__":
    main()
