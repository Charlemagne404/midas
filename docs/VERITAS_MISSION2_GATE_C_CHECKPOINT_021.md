# Gate C checkpoint 021 — independent full-consume replay and snapshot preflight

**Captured:** 2026-10-16T13:42:04Z
**Status:** The second non-overlapping finalized-source window matched the pinned reader's state and research rows. The optimization remains undeployed to the frozen campaign.

## Independent replay window

Benchmark 003 consumes ordinals 521245–525719 from 16 hash-verified finalized
segments: 4,475 records and 3,899 frames. It does not overlap benchmark 002,
which ended at ordinal 521244. Both the pinned implementation and the Veritas
branch produced the same engine and context digests and all 768 normalized
research rows (128 decisions, 128 committed decisions, 512 follow-ups).

Under matching 25% CPU, 512 MiB memory and low-priority limits, the pinned
reader used 63.83 CPU seconds and 255.31 wall seconds. The Veritas reader used
13.43 CPU seconds and 53.67 wall seconds: 78.96% less CPU and 78.98% less wall
time in this single comparison per implementation. This extends the first
full-consume result; it is not a long-run service throughput measurement.

The replay-derived rows had 45 quality-valid decision states and zero
positive gross, quantity-supported, or post-fee candidates. All temporary
policy actions abstained. Of 512 replay-window follow-ups, 2 were public
measurements and 510 were censored at the bounded replay horizon or for data
quality. These are not prospective campaign yield or independent trials.

## Runtime-snapshot preflight

The benchmark runner's new `--runtime-snapshot-output` option was checked with
two sequential one-segment replays. The producer consumed ordinals 521576–522003
(428 records, 419 frames) and wrote a snapshot. The consumer loaded that exact
snapshot and consumed the next segment, ordinals 522004–522245 (242 records,
185 frames). Both runs verified one finalized segment and the same frozen
campaign identity. Temporary outputs and runtime snapshots were kept under
`/tmp`; the live worker database was not opened for writing.

The focused shadow suite passed (**16 passed**). Ruff lint/format and strict
Mypy passed after removing obsolete type-ignore comments. `git diff --check`
and JSON parsing passed for the checkpoint artifacts. No full regression was
run.

## Limits and next step

This confirms semantic equivalence and a large CPU reduction on a second
bounded range; it does not establish live catch-up, better freshness, reduced
campaign censoring, or economic improvement. The original campaign and worker
were not modified or restarted. Next, use a separate journal and versioned
identity for a resource-bounded reader canary, and compare its progress with
newly finalized source before considering any deployment.

See [benchmark 003](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_003.json),
[benchmark 002](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_002.json), and ledger
H140–H141.
