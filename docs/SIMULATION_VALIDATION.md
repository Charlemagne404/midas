# Simulation validation

Validation uses the production broker/risk/venue and an independently implemented
Fraction/integer reference layer. Rational charges do not import production fee or
payout helpers. They reconstruct acquisition costs, fees, cash/reservation/basis buckets,
quantity conservation, asset basis and terminal payouts from journal facts. Existing
Decimal reconciliation additionally checks restored portfolio/order state. Both run
throughout every Laboratory episode, including expensive campaigns.

| Property | Applicable assumptions and evidence |
| --- | --- |
| Replay equality | Identical complete inputs, implementation, supported Python/Decimal settings and seed; result and full checkpoint journals compared |
| No future observations | Receipt time grants access, decisions freeze inputs, delayed second instrument/processing cannot expose future books |
| Increasing fees cannot improve fixed-trade profit | Fixed quantity/prices/rounding rule; rational fee monotonicity, separately supplied official 100-share vectors |
| Reduced liquidity cannot increase fixed-order fills | Fixed approved order limits/quantity and unchanged model; tested by execution liquidity fraction |
| Duplicate notifications do not double-credit | Identical action/financial identity; conflicts reject rather than being treated as duplicates |
| Complete binary pair conserves modeled payout | Eligible nonnegative terminal numerators sum to positive denominator; integer six-decimal floor may lose at most one unit across complementary components |
| Rejected/cancelled order releases unused funds | No fills pending confirmation are inferred; venue reservations and broker envelopes reconciled |
| Presentation/log retention is irrelevant | Same scenario with full versus compact logging yields identical semantic result hash |
| Parallel execution is irrelevant | Same canonical seeds/configs with one and two spawned workers yield identical run hashes |
| Loss is not a software failure | Unresolved financing/partial-leg exposure can lose money while conservation and risk still pass |

Stateful Hypothesis tests compare scheduler ordering against an independent tuple-list
model across scheduling, popping and checkpoint reconstruction. Property tests vary
scenario seeds, checkpoint boundaries, fee boundaries and payout vectors. Known wrong
charges and duplicate/conflicting events are controlled mutations whose detection is
asserted; the suite itself still passes when those checks work.

Campaign tests exercise atomic committed episodes, crash-equivalent abandoned status,
active pause, cancellation, resumption, source changes, single-writer ownership,
read-only readers, memory/resource configuration, pre-exhausted disk/wall budgets,
archive tampering and permanent failure artifacts. Existing physical broker crash,
ledger/CAS/database checks are retained. A database process crash is not automatically
a simulated exchange loss.

Backend contracts and React controls are tested. Playwright actually launches a paired
experiment, compares results, opens persisted history, navigates backward/forward/scrubs,
downloads data, re-executes a run and inspects a minimized controlled incident. Empty
states use no fabricated metrics. Existing browser workflows remain in the same suite.

Limitations: Linux/Python 3.12 is the exercised environment. Local PostgreSQL remains
skipped, no current live V2 attestation/settlement was established, and short captured
REST books cannot calibrate fill probabilities or market reliability. New search is
bounded and root-cause triage remains manual. API financial summaries use SQL floating
aggregates while exact per-run values remain decimal strings; these summaries are
estimates. Statistical paired bootstrap describes synthetic episode variation; repeated
recorded datasets and correlated generator assumptions do not supply independent
real-world confidence. No claim of profitability follows from passing invariants.
