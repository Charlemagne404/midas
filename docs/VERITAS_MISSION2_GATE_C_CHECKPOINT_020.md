# Gate C checkpoint 020 — bounded full-consume reader replay

**Captured:** 2026-10-16 13:06 UTC
**Status:** The branch reader completed an isolated full `Shadow.consume()` replay with exact state and normalized research-row equality on the compared finalized range. It remains undeployed to the protected Reality worker.

## Result

The earlier `Tail` plus `Context` benchmark did not include the worker's policy
evaluation, observation and decision journal writes, follow-up processing, or
periodic saves. This checkpoint extends the comparison through the complete
consume path using the same saved runtime cursor and 16 hash-verified sealed
segments for the pinned campaign implementation and the Veritas branch.

Both runs consumed ordinals 518471–521244: 2,774 records and 2,247 frames.
Each produced 128 decisions, 640 observations, and 768 normalized research
events (128 decisions, 128 committed decisions, and 512 follow-ups). Follow-up
status counts were identical: 12 observed public measurements and 500
censored rows.

The exact normalized research rows matched, as did the reconstructed engine
and context state digests. The shared research-row digest is
`7ab2d997ddd760cda823010eae1a928190df04b73f9ffa3e93e0ab43d469b798`.

Under the same 25% CPU quota, 512 MiB memory limit, and low process priority,
the pinned implementation used 49.64 CPU seconds and 198.56 wall seconds. The
final-tree Veritas pass used 10.01 CPU seconds and 40.02 wall seconds: about
79.8% lower CPU and wall time on this one replay. These are single-pass
measurements, not medians or a long-run service profile.

## Code and verification

- `Tail.refresh()` caches the sorted segment path list until the source
  directory device, inode, modification time, or change time changes; it
  rescans and validates symlinks after a directory change.
- `Engine.consume()` returns parsed frame events so `Context.consume()` can
  reuse the decode for last-trade tracking. Unsupported encodings remain
  rejected; parsed-but-malformed event lists preserve the prior diagnostic
  trade-tracking behavior.
- The focused shadow tests pass (**16 passed**); Ruff and strict Mypy pass.
- The benchmark now uses the recorded clock consistently for both monotonic
  APIs, preventing implementation speed from changing simulated save cadence.
  Its Linux peak-RSS reader uses `/proc/self/status`; the earlier `getrusage`
  conversion was excluded from the A/B result because it disagreed with the
  scope memory peak.

The detailed method, hashes, and limits are in
[benchmark 002](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_002.json). The versioned
inventory is [080](VERITAS_MISSION2_RESEARCH_INVENTORY_080.json), and the
experiment is recorded as ledger H139.

## Limits and next work

This demonstrates CPU reduction and exact evidence-row equality only for one
bounded historical range. It does not show that the protected worker would
catch up, make fresher live decisions, change censoring, or find economic
opportunities. No market conclusion or strategy result follows from this
systems benchmark.

The frozen campaign, persisted runtime, and live worker were not modified or
restarted. Keep the change in the branch. Before considering any deployment,
compare a second independent finalized-source window and preserve the same
state and journal-row equality checks. Continue to investigate the live
worker's lag under the existing preservation rules.

No authenticated requests or orders were made.
