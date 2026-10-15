# Veritas Mission 2 Gate C Checkpoint 001 — Source-Grounded Censoring Audit

- **Captured:** 2026-10-15 08:44 UTC
- **Analysis:** `veritas-forward-forensics-v1.3`
- **Campaign:** `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`
- **Status:** current read-only censoring breakdown implemented; the prospective campaign continues unchanged.

## Implementation and source boundary

`forensics.py` now derives censor counts by market, decision UTC hour, frozen horizon, initial observation-quality regime, and censoring mechanism. Missing outcome rows are represented as pending, separately from censored outcomes. The report is an immutable Veritas derivative; it reads the Reality campaign database through SQLite `mode=ro` plus `PRAGMA query_only=on`, begins one read transaction, and copies no raw observation bodies to the output.

The run selected all 10,165 indexed decisions under its 50,000-decision bound. The captured tail was event 111,571, SHA256 `cb5f6962e9c23ea5166da11f9f22fc1231747a240fa334e32e70a1c596c72661`. Campaign ID and plan SHA matched the pinned frozen identity. The artifact also records hashes for the pinned `shadow_worker.py`, `research_measurements.py`, `shadow_source.py`, `reconstruction.py`, and `foundry.py` copies. The active Reality writer was not stopped or changed.

## Results at this read snapshot

- 10,165 decisions across 42 markets and 36 connected families over two UTC dates; decision times span 2026-10-14 21:07:59–2026-10-15 08:40:09 UTC.
- 3,481 decisions had valid initial states; 6,684 failed initial quality. Across four frozen horizons (100, 300, 1,000, and 5,000 ms), 40,660 follow-up slots contain 930 public measurements, 39,730 censors, and zero pending rows in this SQLite snapshot.
- Invalid starts contribute 26,736 `invalid_at_decision` horizon censors. They are not later follow-up failures. The remaining 12,994 censors belong to valid initial states.
- Valid-initial follow-up yields are 29/3,481 (0.83%) at 100 ms, 94/3,481 (2.70%) at 300 ms, 337/3,481 (9.68%) at 1,000 ms, and 470/3,481 (13.50%) at 5,000 ms.
- Among valid-start censors: 10,184 are `future_observation_unavailable`; 1,448 `stale_book`; 954 source availability timeouts; 336 logged source/reconstruction gaps; 67 advertised-top-pending issues; four event-order/timestamp-regression labels; and one independent-book divergence.
- The artifact contains 168 market-by-horizon groups, 48 UTC-hour-by-horizon groups, and 32 initial-quality-by-horizon groups. At 5 seconds, 22 markets had at least one valid start; their observed measurement yield ranged from 0% to 27.9%, with a nearest-rank median of 0%. Twelve UTC-hour buckets are present.
- Initial invalid-quality reasons are separately counted: 5,994 stale books, 494 empty ask sides, 80 `book_issue:stale`, 75 source timing uncertainty, 15 advertised-top-pending issues, 13 independent-book divergences, and 13 reported expiries.

## Censor interpretation from the frozen worker

The pinned worker checks initial validity first and emits `invalid_at_decision` for every horizon when there is no valid baseline. For valid starts it computes a target time as decision time plus the horizon and a deadline from the frozen tolerance. If a source record arrives after the deadline before a qualifying future book was found, it emits `future_observation_unavailable`. If the worker remains pending beyond the deadline plus the two-second availability grace, it emits `source_followup_availability_timeout`. The former is not proof that the venue had no quote: it can reflect quiet activity, query/cohort selection, or feed coverage.

Follow-up `stale_book` means a book was present but failed the frozen freshness rule. `recorded_gap:*` is an explicit source gap barrier; `book_issue:gap:*` is a reconstruction/book gap. `book_issue:advertised_top_pending` denotes an unreconciled advertised top. `future_preceded_durable_decision` and `book_issue:timestamp_regression` are event-order evidence problems, not confirmed code defects. `independent_book_divergence` records outcome-book disagreement. The source's possible cross-outcome-skew, unsupported-semantics, lifecycle, and tick-regime reasons have zero observed censor labels in this snapshot. The source does not identify legitimately unknowable outcomes separately.

No frozen campaign rule or historical outcome was edited. An overrestrictive reported-age gate was repaired only in the separate Veritas public-snapshot analyzer; its paired v4 comparison remains a measurement-yield study and did not relabel Reality history.

## API and dashboard

The read-only API validates the campaign identity and count reconciliation before using this report for current follow-up yield. The dashboard displays yield by horizon and expands to a longest-horizon table by market and UTC hour plus censoring-mechanism counts. A bounded artifact link exposes the full per-market/time/horizon/quality report. The 08:44 snapshot is interim and correlated; it does not establish strategy performance or campaign completion.

The earlier 08:38 UTC v1.2 capture remains preserved as [`VERITAS_GATE_A_CENSORING_002.json`](VERITAS_GATE_A_CENSORING_002.json), SHA256 `90187991a7e676e1f6106e303aefd30f1947dd880800916fe5319ed388ea8eb5`; the 08:44 UTC v1.3 artifact below supersedes its grouping schema while retaining the earlier evidence.

Artifact: [`VERITAS_GATE_A_CENSORING_003.json`](VERITAS_GATE_A_CENSORING_003.json), file SHA256 `4e7d8d2bde0cda1afdc5876de2fbc31c3a54219b95d9baba0bfbfeed454b9b72` (348,795 bytes). The bounded 50,000-row analyzer call completed in about 4.2 seconds wall time; CPU and peak memory were not measured. The report is below the API's 512 KiB artifact limit.

## Verification and remaining work

- Full Veritas tests: 88 passed; one existing Starlette/httpx deprecation warning.
- Ruff and strict Mypy across the Veritas package and API: passed.
- Frontend tests: 29 passed; typecheck, lint, Prettier check, and production build passed. The Vite large-chunk advisory remains.
- Veritas browser workflow: one end-to-end test passed, including the new censoring artifact and dashboard view.
- The 14-day campaign remains active. The read snapshot does not reverify the full SQLite event hash chain or run a full database integrity scan. Future-observation-unavailable remains an unresolved mixture until independent feed coverage/sequence evidence exists.
