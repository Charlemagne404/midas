# Gate C checkpoint 023 — maintained top-of-book cache

Captured 2026-10-16 16:38 UTC. This checkpoint covers a branch-local shadow
reconstruction optimization and an isolated sequential replay. The frozen
campaign and live services were not modified or restarted.

`Engine` now maintains best bid/ask values alongside engine-owned reconstructed
books. Full book snapshots populate the cache; price deltas update it
incrementally and rescan a side only when its current best level is removed.
Restored contexts rebuild the derived cache. The serialized engine state keeps
using the reference full scan so runtime digests remain comparable. History and
the worker's fast opportunity gate use the cached top.

The two-segment 5% CPU canary produced the same engine, context, research, and
journal hashes as the baseline, with the same decisions, observations, and
censored follow-ups. Aggregate CPU fell from 9.804 to 9.331 seconds (4.82%);
wall time fell from 196.12 to 186.72 seconds (4.80%). The first segment was
effectively unchanged; the second was about 11.8% faster. Peak RSS increased by
about 1.27 MB. This is a modest preliminary result from one paired pass, not a
live catch-up result. The worker remains on its frozen implementation.

The targeted reconstruction/shadow/resumable-replay suite passed **49 tests**.
Ruff, formatting, strict Mypy, and `git diff --check` passed. Full mission
regression was not run. The new tests compare cache values to the reference
scan over snapshots and bid/ask level changes, verify cache rebuild leaves the
digest unchanged, and assert non-best changes avoid a full scan.

See [benchmark 004](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_004.json) and
the isolated result files under `data/veritas-canaries/shadow-resumable-005/`.
The benchmark explicitly used current branch code, so implementation hashes
were not checked against the frozen campaign code. Further representative
profiling is still needed before any successor worker uses this optimization.
