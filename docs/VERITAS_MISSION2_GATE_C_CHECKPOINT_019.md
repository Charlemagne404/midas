# Gate C checkpoint 019 — remove repeated source-directory scans

**Captured:** 2026-10-16 12:06 UTC
**Status:** Two local reader optimizations passed focused verification and a bounded state-equivalence replay. They are not deployed to the frozen Reality worker.

## Diagnosis

The shadow lag diagnostic showed a CPU quota of 100 ms per second. A direct
measurement of `Tail.refresh()` found that a forced full listing and symlink
check over roughly 6,134 segment paths costs 68–91 ms CPU. The reader invokes
that refresh at most every 0.5 seconds, so the directory walk alone can demand
136–182 ms CPU per second before consuming records. This is sufficient to
explain substantial throttling under the configured quota.

## Changes

- `Tail.refresh()` now checks the source directory device, inode, modification
  time and change time before rebuilding the sorted segment list. It rescans
  and validates symlinks when directory entries change. If entries change
  during enumeration, the earlier marker is retained so the next refresh
  retries.
- `Engine.consume()` returns its decoded frame events; `Context.consume()`
  reuses them for last-trade tracking instead of decoding the frame payload a
  second time.
- Focused tests cover cache reuse, segment discovery after a directory change,
  symlink rejection, and preservation of last-trade state.

## Verification and measured effect

- `PYTHONPATH=packages /home/charlie/midas/.venv/bin/pytest -q tests/test_reality_shadow.py tests/test_reality.py` — **28 passed**.
- Ruff on the modified source and test files — **passed**.
- Strict Mypy on the two modified source files — **passed**.
- A 100-call unchanged-directory check measured a 0.004 ms median CPU cost per
  cached refresh, versus a 67.79 ms median forced full scan over a similar
  directory. Temporary-directory tests verify that new segment entries still
  trigger a scan and that symlinks are rejected.
- Three alternating replays of finalized ordinals 516051–519036 consumed 2,970
  non-checkpoint records and 2,461 frames across 16 hash-verified sealed
  segments. Median `Tail` plus `Context` CPU fell from 5.6814 s with the frozen
  reader to 4.7632 s with the Veritas reader (**16.16% lower**). Context state
  SHA-256 matched exactly. The context-only comparison cut frame-payload
  parses from 4,922 to 2,461 and CPU by 7.45%.

The full benchmark record is in
[shadow reader benchmark 001](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_001.json).

## Limits and next step

The replay did not exercise `Shadow.consume()` policy inference, journal
transactions, pending follow-ups, or five-second status saves. Its bounded
range begins mid-campaign, so checkpoint assertion rows were omitted while
all source records needed by the reader path were retained. It does not prove
the active worker will catch up or produce fresh decisions. The frozen
campaign and its worker were not changed or restarted.

Next, profile the complete consume path in an isolated successor with a
temporary journal and explicit resource bounds. Keep the original campaign
untouched; do not promote or deploy this change without that comparison.

No orders or authenticated requests were made.
