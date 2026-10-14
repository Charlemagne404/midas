# Veritas Gate A checkpoint 001 — initial forensics and economic engine

Captured 15 October 2026 local time. The machine-readable release, service, and
campaign snapshot is [VERITAS_GATE_A_BASELINE.json](VERITAS_GATE_A_BASELINE.json).
This checkpoint records the start of Veritas; it does not accept Gate A or any
later development gate.

## Safe start and release evidence

- `origin/main` and the peeled `reality-final-2026-10-14` tag both resolved to
  `f968095feb9c591de38fe12d7493224425f62f3a`.
- The main worktree was clean at the release. The separate Reality worktree was
  clean at `714f824f74d710f946169834787daa8b5e3a47ea`.
- `project/veritas` was created at the release commit in
  `/home/charlie/midas-veritas`. Main and Reality were not edited.
- Read-only health endpoints reported the main API and Reality API ready. The
  Reality collector, frozen shadow worker, capacity timer, archive timer,
  research timer, and shadow-integrity timer were active. Both long-running
  Reality units had zero automatic restarts at the service snapshot.
- The collector reported eight markets, 16/16 fresh books, zero timing-uncertain
  books, zero current failures, and sequence verification unavailable. Its
  raw root was about 393 MB, with the capacity forecast around 728 MB/day from a
  recent finalized-segment sample that includes gaps and metadata. The forecast
  is not a promise of uninterrupted future collection.
- The shadow worker remained paper-only, with zero submitted orders. The original
  campaign plan hash and identity are recorded in the machine snapshot.

No operational service or Reality data was changed to create this checkpoint.

## Frozen campaign funnel at the journal snapshot

The read-only forensic query used the frozen campaign
`adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`, verified
the plan identity, checked SQLite integrity, and observed journal event sequence
`16852`. It did not reverify the full event hash chain or raw-source replay.

- 1,408 decisions covered ten accumulated markets, six connected families, and
  one UTC day in this consistent database snapshot.
- 381 initial decisions had quality-valid features and a baseline. The other
  1,027 were invalid at decision time: 898 `stale_book`, 72 `empty_ask_side`,
  22 `book_issue:stale`, 21 `source_timing_uncertainty`, 11
  `book_issue:advertised_top_pending`, and three
  `independent_book_divergence`.
- The 381 valid initial decisions had a pre-fee top-of-book edge distribution
  from `-0.51` to `-0.001` collateral units per share, with a nearest-rank median
  of `-0.03`. None was positive.
- All six frozen policies abstained. The mathematical filter cited
  `no_initial_supported_discrepancy` for every valid initial state. The
  Prometheus control cited stale data or unsupported structure. Conservative
  policies cited their frozen liquidity, timing, fee, or recovery gate. The
  available evidence does not justify loosening those gates.
- Across the four frozen horizons, the journal had 5,632 follow-ups: 5,570
  censored and 62 observed public measurements. The 4,108 `invalid_at_decision`
  outcomes are the four follow-ups for each of the 1,027 initially invalid
  decisions; they should not be conflated with missing future outcomes after a
  valid initial state.
- For 1,524 follow-ups attached to valid initial states, 62 were measured and
  1,462 were censored. Of those valid-state censors, 1,183 arose because no
  qualifying synchronized future observation was available before the frozen
  deadline or availability grace. The other 279 reflect later stale books,
  resynchronization gaps, or pending advertised-top quality states.

The service status file was sampled separately from the SQLite transaction and
was two outcomes behind it at capture. The SQL summary is the consistent journal
snapshot; the status counters are operational telemetry, not a transactionally
aligned copy. Missing future observations remain scientifically censored under
the frozen campaign. Whether alternative predeclared horizons or event-time
sampling would materially improve future coverage remains open.

## Diagnosis and next questions

Universal abstention is currently consistent with the measured funnel: most
decisions failed initial quality checks, and every quality-valid initial state
had negative pre-fee top-of-book edge. This is a bounded sample, not proof that
no opportunities exist elsewhere or later. ML thresholds cannot turn a negative
observed gross discrepancy into a supported arbitrage. The next priority is to
reconstruct the full raw opportunity funnel and determine whether the large
stale-book count is inherent to this panel/cadence or can be reduced in a new
prospective design without weakening frozen quality requirements.

The largest open public-observation limitation is paired future coverage. The
recording emits many source events, but a valid later label requires both
complementary books to be usable, within the declared age/skew bounds, and
observed inside the frozen horizon window. This does not identify private fills.

## Implemented Veritas work

- Added `midas.veritas.economics` as a new versioned hypothetical model. It
  walks actual displayed ask levels, reports quantity-specific costs, accepts
  per-leg fee/minimum metadata, models single-match and equal-fragment fee
  sensitivities, and calculates a conservative upper fee bound for unknown
  fragmentation. It returns no fill probability and marks actual fills unknown.
- Added partial-position payout bounds for verified same-condition V1 binary
  CTF semantics. It reports both binary terminal outcomes rather than assuming
  an unmatched position is hedged or recoverable.
- Added `midas.veritas.forensics` and
  `scripts/veritas_forward_audit.py`. They read a frozen journal through
  SQLite `mode=ro`, validate campaign identity and indexed event consistency,
  bound the query at 50,000 decisions, separate invalid-initial and later
  censors, and exclude raw payload archives from output.
- The official fee documentation says the formula depends on market-specific
  parameters, applies to takers at match time, and rounds to five decimal
  places. The legacy Reality scenario helper adds one fee quantum per leg;
  MIDAS's shared economics package already has a more conservative
  fragmentation bound. For controlled inputs `q=100`, `p=0.5`, `rate=0.04`,
  the legacy reserve is `1.00001` while the fragmentation-safe bound is
  `2.00000`. This is an assumption sensitivity, not an observed trade or fee
  invoice. See [official fee rules](https://docs.polymarket.com/trading/fees).
- The observed source distinction between CTF token IDs and V2 position IDs is
  preserved; this first engine rejects V2 and unverified payout relationships.
  See [official outcome book documentation](https://docs.polymarket.com/market-data/prices-order-books).

The existing Reality helper, the frozen campaign, and its records were not
rewritten. The new engine is exploratory and has not been promoted into a
campaign or production policy.

## Verification and limits

- Focused Veritas tests: 20 passed.
- Ruff: passed for Veritas source and focused tests.
- Strict mypy: passed for `packages/midas/veritas`.
- No full backend/frontend/browser suite was run in this checkpoint.
- No training job was started. Current public labels and decision coverage do
  not justify more model compute before the observation funnel is understood.
- Reality service memory snapshots were about 380 MB for the recorder and 179
  MB for the shadow worker. No Veritas background job was started.

Current economic classification: **insufficient independent evidence**. The
monitored, quality-valid sample contained no positive pre-fee top-of-book
discrepancy. Actual fillability, private matching, broader-market prevalence,
and real profitability remain unknown.

## Next work

1. Build a streaming, source-provenanced full opportunity funnel over finalized
   Reality segments without taking writer ownership or loading the raw archive
   wholesale.
2. Stratify stale books, synchronized-book age, cross-outcome skew, market
   activity, and decisions by connected family and time block.
3. Independently check fee arithmetic, tick/minimum handling, capital sizing,
   and the binary payoff calculations against captured public market metadata.
4. Use observed update activity to preregister a separate set of future public
   measurement horizons and cadence; keep Reality's original campaign intact.
5. Add the resulting evidence to the durable [research ledger](VERITAS_RESEARCH_LEDGER.json)
   and update the ranked [backlog](VERITAS_RESEARCH_BACKLOG.md).
