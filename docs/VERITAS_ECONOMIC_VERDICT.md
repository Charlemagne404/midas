# Project Veritas — economic verdict

**As of:** 2026-10-15

**Model correction (2026-10-16):** The synthetic v2 P&L numbers below used an
outcome-share fee deduction. Current public fee guidance specifies fees in
USDC, and current CTF Exchange V2 settlement code charges buy fees from
collateral. Model v3 charges both purchased legs at entry; the v2 synthetic
figures below are retained as historical output and are superseded for current
economics by [Gate B checkpoint 012](VERITAS_MISSION2_GATE_B_CHECKPOINT_012.md)
and [break-even artifact 002](VERITAS_GATE_B_EXECUTION_BREAK_EVEN_002.json).
No observed gross-candidate conclusion changed.

**Verdict:** No observed opportunity qualifies for strategy promotion or a new prospective campaign. Keep the no-trade control.

## Observed opportunity funnel

The latest replay analyzed 2,040 finalized source segments (483,718,250 bytes)
through ordinal 251,887 over approximately 4 hours 16 minutes. It covered 16
selected market IDs and 56,912 market-frame records. Of 46,298 touched paired
states, 44,981 passed quality checks and 1,317 did not.

All 44,981 valid states had the requested five-share depth and fee metadata.
The positive-candidate counts were:

| Test | Positive states |
| --- | ---: |
| Best-ask pair edge | 0 |
| Quantity-specific top edge | 0 |
| Full-depth pre-fee edge | 0 |
| Full-depth edge satisfying both per-leg USDC minimums | 0 |

Maximum top-pair edge was -0.001 per share; median was -0.01. The panel is
selected, brief, and correlated. The result means that no candidate appeared
in this observed snapshot; it does not establish that opportunities never
occur or estimate venue-wide prevalence. Source detail is in [raw funnel
004](VERITAS_GATE_A_RAW_FUNNEL_004.json) and [checkpoint
012](VERITAS_GATE_A_CHECKPOINT_012.md).

## Synthetic execution sensitivity

The following values use a hand-authored synthetic V1 book and declared fee,
rounding, settlement, capital, and carry assumptions. They are not derived
from observed campaign quotes.

| 100 shares per leg, full displayed depth | Worst-resolution result |
| --- | ---: |
| Completed pair, single-match fee rounding | +1.4178 USDC |
| Completed pair, fragmentation-safe fee upper bound | -0.7822 USDC |
| One adverse unmatched leg, assumed unrecovered | -50.1959 USDC |

In the single-match case, the algebraic sensitivity requires 35.4039 matched
completions per unmatched event to break even. An illustrative 1% unmatched
event rate would require a 35.40% matched-completion rate; a 5% unmatched rate
would require an infeasible 177.02%. These are selected sensitivity inputs,
not observed rates. The fragmentation-safe completed-pair case is already
negative before adding an incomplete-position loss. At half displayed depth,
the 100-share completed-pair case is negative under both fee assumptions.

The synthetic input book, break-even formula, and full size grid are in [Gate
B checkpoint 001](VERITAS_GATE_B_CHECKPOINT_001.md) and
[its machine-readable artifact](VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json).
No fill probability or recovery value is estimated from public quotes.

## Campaign decision

Do not create or start a separate prospective campaign on this evidence. The
existing frozen Mission 2 campaign reports insufficient forward evidence in
the captured Reality checkpoint; its observed follow-ups and hypothetical
scenario reports do not establish actual money or strategy performance. The
Veritas follow-up proposal is a measurement-yield design, not a trading test,
and it remains blocked on evidence readiness: two days of verifiable
per-market coverage, at least nine eligible markets under the draft rules,
multi-day dependence estimates or bounds, exact assignment simulation, and
independent review. See [design draft 002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md)
and the [Mission 2 acceptance audit](REALITY_MISSION2_ACCEPTANCE.md).

Reconsider only if a longer finalized panel contains a quality-valid positive
gross candidate that survives independent payoff mapping, per-leg minimums,
quantity-specific full-depth costs, and fee checks. That would justify further
hypothetical analysis; it still would not establish fills or profitability.
