# Gate C checkpoint 003 — frozen-campaign label feasibility

**Captured:** 2026-10-15 19:58:10 UTC
**Mission status:** active; the forensic report is complete, but the fixed coverage pilot and source replay remain in progress.

## Bounded read-only analysis

`veritas-forward-forensics-v1.4` queried the frozen Reality campaign through a
single SQLite read transaction with `limit=50000`, `since_ns=0`, and no full
integrity scan. The query was not truncated. It reports source kind
`genuine_public_recording`; it did not alter the database or campaign. The
analysis adds observed-only categorical support and numeric movement
distributions per horizon. It does not copy raw market observations into the
summary artifact.

The campaign contains 10,253 decisions across 43 markets and 37 connected
families over two UTC days. Of those decisions, 3,503 were valid initially and
6,750 invalid. All 3,503 valid initial pre-fee edges are non-positive: maximum
`-0.001` per unit, median `-0.01`, and zero positive. Each of the six recorded
policies abstained on all 10,253 decisions.

| Horizon | Observed | Censored | Pending | Observed / valid initial decisions |
| ---: | ---: | ---: | ---: | ---: |
| 100 ms | 29 | 10,224 | 0 | 0.83% |
| 300 ms | 94 | 10,159 | 0 | 2.68% |
| 1,000 ms | 341 | 9,912 | 0 | 9.73% |
| 5,000 ms | 473 | 9,780 | 0 | 13.50% |
| **All horizons** | **937** | **40,075** | **0** | — |

At five seconds, all 473 observed rows have `quote_persistence=true`,
`opportunity_target_status=no_initial_discrepancy`, and
`opportunity_persistence=null`. Every row has
`execution_ground_truth=unknown_counterfactual`; displayed quantity support
does not establish a fill. At one second, quote-persistence has one false and
340 true rows, and two quoted-exit-value changes are positive. Those public
markout movements are not observed arbitrage, strategy P&L, or execution
labels. The per-horizon distributions are in the versioned summary artifact.

The largest censor buckets are 27,000 `invalid_at_decision` slots and 10,233
`future_observation_unavailable` slots across the four horizons. The latter
remains a mixture of venue inactivity, cohort selection, and feed/source
coverage; this query does not disambiguate those causes.

## Finding and decision

Public markout measurements exist, so the broad phrase “no public outcome
labels” needs qualification. These data do **not** support a strategy or model
comparison: no valid initial discrepancy occurred, the five-second
opportunity target is unsupported, censoring is high, and fills/P&L remain
unknown. Keep no-trade and do not train on this evidence.

The Research Director’s snapshot-qualification code was corrected in commit
`5795676` to emit `NOT_READY_NO_CANDIDATE_RELEVANT_TARGET`, with a
candidate-relevant target recommendation. The 20:15 UTC Director cycle
persisted this more precise label in its manifest. That readiness remains
scoped to its separate snapshot dataset and has not ingested this
frozen-campaign report; do not treat it as a global claim about all available
public markouts. The scan-33 qualification job has completed, but its manifest
projection remains queued until the next scheduled reconciliation.

The Arena qualification job for scan 32 independently completed all 32 events
at 19:46:25 UTC with exit status 0. Finding
`veritas-qualification-v1-473344bb0e11e07a` reports 1,136 valid pairs across
598 selected IDs and zero positives at each of the five economic gates. The
finding file SHA-256 is
`f324ae0a3680b69105b9636c9bfd1ac9a604cf6eedfebb488fe8193f4f34ce3b`. The
Director manifest still projects `RUNNING` pending its next scheduled
reconciliation; no manual poll or retry was run.

## Evidence and verification

- Summary artifact: [`VERITAS_MISSION2_LABEL_FEASIBILITY_001.json`](VERITAS_MISSION2_LABEL_FEASIBILITY_001.json)
- Summary artifact SHA-256: `0435c2c6b6dd6287caf39906485ac1dec663da344c0f52181cb7e0273299d0ec`
- Bounded report SHA-256: `dd1994104fbe3cdc75b148d630909ca6eab71120d19a1c3346b70c8038ffd788`
- Campaign ID: `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`
- Frozen plan SHA-256: `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`
- Read-only journal tail: sequence `112960`, SHA-256 `470253da4faab9c24797e9d0e48356fb8d3b30e396d3d8b1940f140a6e26f72b`
- Full event hash chain re-verification: not performed.
- SQLite integrity scan: not performed.
- Focused forensic tests: **9 passed**. Ruff, Ruff format check, and strict Mypy passed.

The v1.4 result remains distinct from the dashboard's pinned v1.3 censoring
summary. It is now available through a separately validated read-only API
projection and dashboard panel; see [Gate G checkpoint
006](VERITAS_MISSION2_GATE_G_CHECKPOINT_006.md). The integration preserves the
markout-only and unknown-execution limitations recorded above.
