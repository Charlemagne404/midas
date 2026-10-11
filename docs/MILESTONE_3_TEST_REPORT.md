# Milestone 3 test and demonstration report

Executed 2026-10-11 on Linux/Python 3.12.3. All orders, fills,
positions and payouts were internal simulations. Existing regression coverage remains.

## Automated checks actually executed

| Command | Result |
| --- | --- |
| `.venv/bin/pytest -q` | **228 passed, 1 skipped**, 61.50 seconds |
| `.venv/bin/ruff check packages apps/api tests infra scripts` | Passed |
| `.venv/bin/ruff format --check packages apps/api tests infra scripts` | Passed, 74 files |
| `.venv/bin/mypy packages/midas apps/api` | Passed, 41 source files |
| `corepack pnpm test` | **4 passed** |
| `corepack pnpm test:e2e` | **4 passed**, final rerun 14.0 seconds |
| `corepack pnpm lint`, `typecheck`, `format:check` | Passed |
| `corepack pnpm build` | Passed |
| `.venv/bin/python scripts/laboratory.py reproduce --incident tests/fixtures/milestone3/controlled-ledger.json` | Exact controlled-failure hash reproduced |
| Existing account replay from read-only SQLite backup | Healthy `paper-demo`, recovery revision 1244, two hypothetical fills |

[Local runtime evidence](MILESTONE_3_LOCAL_RUNTIME.json) confirms the upgraded running
service is READY, all four campaign archives are accessible, and the persistent paper
balances/fills are unchanged. [Overview](laboratory-overview.png) was captured from the
existing dashboard on port 5173 after restart.

The skipped PostgreSQL test still requires `MIDAS_TEST_POSTGRES_URL`; PostgreSQL
runtime is not claimed. The suite retains the upstream Starlette/httpx TestClient
deprecation warning. Vite retains its 544.41 kB lazy chart chunk warning. Browser tools
also emit their NO_COLOR/FORCE_COLOR environment warning. None was concealed.

New coverage includes seeded families, heap priorities/identities, stateful ordering,
checkpoint/journal equality, Python hash seeds, FOK atomicity, FAK partials, cancellation
races, market pauses, idempotent/conflicting financial IDs, independent rational
fees/payouts, original reference vectors, explicit lockup/cost sensitivity, recorded
hash/clock/provenance validation, future-book exclusion, late updates, delta invalidation,
worker determinism, active pause/cancel/recovery, single-writer ownership, resource
budgets, archive integrity, paired controls, API contracts and browser research workflows.

## Five implemented demonstrations

Run the four backend demonstrations and preserve their local campaign archive:

```bash
.venv/bin/python scripts/laboratory_demonstrations.py --root data/laboratory-final --runs 1000
corepack pnpm test:e2e
```

Exact final inputs, campaign IDs, selected runs, assumptions and outputs are in
[MILESTONE_3_DEMONSTRATIONS.json](MILESTONE_3_DEMONSTRATIONS.json).
New invocations create new IDs/timestamps while preserving logical scenario/result hashes.
The checked-in manifest points to the executed local archive; it is not a portable copy
of that SQLite database. Exported scenarios can be replayed directly on another checkout.

1. **Historical replay:** `ctf-4024677`, three execution variants, three original public
   events each. All pass invariants; the original complete-book opportunity has negative
   edge and is rejected. Zero hypothetical fills and zero settled virtual P&L. Metadata,
   incomplete-book and complete-book decisions are visible; no profitable opportunity
   or historical hypothetical fill was fabricated. The second retained dataset validates
   independently in tests. These are bounded real snapshots, not sustained feed histories.
2. **Large scenario campaign:** seed 20261011, 1000 separate reset episodes cycling
   calm/volatile/one_sided/unresolved, standard model, two workers. **1000 passes, zero
   invariant failures**, 12336 events, 73.304 seconds, 13.642 runs/second and 168.286
   events/second. Worst settled simulated P&L **−10.40**; mean **0.747728**. Valid losses
   pass. Open inventory and zero-trade episodes remain included; these figures do not
   estimate realized returns or profitability in real markets.
3. **Adversarial discovery:** seed 7, explicitly injected ledger corruption. One controlled
   invariant failure; three declarative events reduced to two, single-deletion minimality
   checked. Original/minimized inputs and full state history retained. The permanent
   fixture reproduces hash `3052bb2b38cc228ee61c63038d33649f81a99e01da7c77f9720c5e8eac495240`.
   Separately, a 100-trial noncontrolled search with seed 20261011 found no invariant
   failures; that is bounded evidence, not a correctness proof.
4. **Execution/strategy comparison:** 12 identical episode inputs × three strategies ×
   three models = **108 runs**, all invariants pass. Mean settled simulated P&L for
   arbitrage: optimistic **1.645**, standard **1.778**, conservative **0.127917**.
   No-trade outcomes are zero. The conservative strategy's threshold does not improve
   this fixed sample. Standard versus optimistic has paired mean difference **0.133**,
   synthetic bootstrap interval **[−1.509163, 2.325283]**, labeled **INCONCLUSIVE**.
   Partial winning-leg inventory can outperform a complete hedge in a small synthetic
   sample; model names are not an ordering guarantee. Neither bootstrap nor the sample
   establishes real-world profitability.
5. **Interactive Laboratory:** Playwright configures and launches an actual paired
   campaign, inspects committed results, compares models, navigates persisted replay
   backward/forward/scrubs, exports history and verifies exact re-execution. A second
   workflow launches controlled corruption, inspects its 3→2 minimization and replays
   the failure. [Replay screenshot](laboratory-replay.png) is generated by that workflow.

## Measured performance

```bash
.venv/bin/python scripts/laboratory_benchmark.py --runs 1000 --workers 2
```

[MILESTONE_3_BENCHMARK.json](MILESTONE_3_BENCHMARK.json) retains platform, source hash,
configuration, profile and actual metrics. 100000 heap events scheduled/popped in
1.197 seconds: **83512 events/second**, excluding strategy/risk/accounting.
100 fully audited calm episodes (634 events) took 3.152 seconds: **201.111 events/second**,
31.721 episodes/second. A separate durable 1000-episode campaign processed 12336 events
in **71.434 seconds**, **13.999 runs/second**, **172.692 events/second**, zero violations.
Its compact archive used **1560576 bytes**; first-200 sampled worker lifetime peak RSS
was **79.203 MiB**, coordinator lifetime peak **80.547 MiB** including scheduler/profile
phases. These scopes differ and are not interchangeable throughput/memory claims.

Profiling before optimization is preserved in
[MILESTONE_3_PROFILE_BEFORE.json](MILESTONE_3_PROFILE_BEFORE.json). Fifty profiled episodes
called portfolio summary 2500 times; the final profile calls it 1750 times by avoiding
unpublished observations/discarded replay construction. Both independent accounting
checks remain. CPU loads varied across runs; do not infer a causal speedup percentage
from the wall-time comparison. Production account recovery still replays full history
and is substantially slower than compact research episodes; compaction is deferred.
