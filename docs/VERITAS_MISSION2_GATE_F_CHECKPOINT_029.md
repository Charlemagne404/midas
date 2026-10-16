# Gate F checkpoint 029 — scheduled scan 47 qualification

**Captured:** 2026-10-16 03:19 UTC

**Mission status:** active; the Director's current manifest projection awaits
its next scheduled reconciliation.

## Scheduled admission and Arena result

The 03:15:03 UTC Research Director cycle reconciled scan 46 and admitted one
bounded Arena qualification for scan 47,
`scan-20261016T030203Z-8baf1b769e20`. The child job
`job-d5fda223640d4a94893cdf35` completed all 47/47 source events at 03:15:46
UTC with exit status 0 in 3.02 seconds. Its job record and source manifest pin
the submitted source revision. The persisted finding is
`veritas-qualification-v1-2c8fea9bc2f8c8a9`.

The finding covers 47 snapshots, 1,880 selected pair observations, 1,628
quality-valid states, and 835 selected market IDs. The unchanged top-ask
gross gate, full-depth gross, full-depth plus per-leg minimums,
single-match-fee sensitivity, and fragmentation-safe-fee sensitivity each
have zero positive states. Candidate evidence is complete with zero rows,
and the source replay is complete with zero candidates. The finding keeps the
no-trade recommendation; it is qualification evidence, not strategy P&L or
independent venue confirmation.

| Evidence | SHA-256 / value |
| --- | --- |
| Job record | `81ae5bcc349740dbd0c7ec689b266ac7af8a312a13516a9a3f98de56036c243c` |
| Source manifest file | `e50f42ab0fa5944d49c7587347f7982d879173b32854da81329a27a48c59269a` |
| Finding manifest file | `7b23d70025557aa1ef7ad30b658aeecbdaa05facfd532c978c9ea37c180c5724` |
| Experiment | `VERITAS-M2-ECO-QUAL-001-V4-RUN-8eb3c4effd22` |
| Experiment digest | `16d87730dc9744ead219a698cf32015b6d1e8f17f8bae4674cddc8c9271f19e9` |
| Dataset digest | `8eb3c4effd22b83323f726db0c9a3f7012ee4cfafde68ad0febf861de39c8b8e` |
| Source revision | `2fdf687710705a717e480d127a162ab9a4fabccb92dd5bb02c2caab25e1b6743` |
| Scan-46 reconciliation event file | `aa1b35575f65f5a944e71b3f88b47a920bfea35d959dcd1024293c34323e2942` |
| Scan-47 admission event file | `bf7cf80fe7404622928678abfb8625fd9a7e7b39dc63cb09dc3b489d1ce208ca` |
| Director manifest file | `116295d5ad503679fbeaa1acd3fb4b56181fa1e0a77ecdff53e45c01c1e9fefc` |

The finding's experiment digest recomputes from its result payload, and its
artifact ID matches the dataset/source-code identity. The result agrees with
the independent 47-snapshot source replay in Gate B checkpoint 002.

## Projection and source readiness

At 03:15:28 UTC the Director manifest still showed `RUNNING`, projected the
current child as `QUEUED`, and retained scan 46 as its last qualified scan.
The child completed 18 seconds later. The user timer listing at 03:18:52 UTC
showed the next Director start at 03:45:19 UTC; allow that scheduled cycle to
reconcile the completed scan-47 child. No manual job API poll, retry, or
re-admission was made.

The source summary pinned by the Director was generated at 03:14:52 UTC and
was marked `catching_up_finalized_source`: 4,997/5,089 segments and
1,292,353,290 processed bytes, with 92 segments / 23,048,067 bytes pending.
It reports 331,241 quality-valid states and zero positive top-ask or
full-depth states. Independent confirmation remains not ready because there
are fewer than 48 hours of observation and no independent venue sequence.

Persisted job and finding files are under
`data/arena/jobs/job-d5fda223640d4a94893cdf35/` and
`data/arena/findings/veritas-qualification-v1-2c8fea9bc2f8c8a9/`. The prior
scan-46 cycle is recorded in [Gate F checkpoint 028](VERITAS_MISSION2_GATE_F_CHECKPOINT_028.md).
Services, timers, the collector, and the frozen campaign were not restarted
or modified for this checkpoint.
