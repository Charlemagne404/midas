# Gate C checkpoint 018 — remove duplicate frame JSON decoding

**Captured:** 2026-10-16 11:11 UTC
**Status:** Implemented and locally verified in `project/veritas`; not deployed to the frozen worker.

## Change

The shadow context previously called `Engine.consume(row)`, which decoded each
frame payload to reconstruct books, then decoded the same payload again to
record `last_trade_price` events. `Engine.consume` now returns the already
decoded event list. `Context.consume` reuses it for trade tracking. The
canonical source record and its hash inputs remain unchanged.

This removes one frame-payload JSON decode per frame on this code path. The
change is confined to the Veritas worktree. It does not alter the code copy,
plan, labels, source cursor, or database of the active Reality campaign.

## Verification

- `PYTHONPATH=packages /home/charlie/midas/.venv/bin/pytest -q tests/test_reality_shadow.py tests/test_reality.py` — **26 passed**.
- Ruff on the two source files and the focused test — **passed**.
- Focused Mypy on the two source files — **passed**.
- The new regression test counts frame-payload JSON decodes and confirms that
  last-trade state is retained with one decode.
- The frozen campaign plan hash remained
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
  The frozen `shadow_source.py` copy remains at SHA-256
  `6e0cb3811a8e32a81e9003a79de0ab778eccc28ff9e725f2163d58decf31b327`, matching
  the Veritas `HEAD` version before this change.

## Effect and limits

The deterministic improvement is one fewer JSON decode per source frame in the
shadow context. End-to-end CPU, catch-up throughput, and the active worker's
source lag have not been measured with this change. The running worker uses
its frozen campaign code and remains `WARMING_OR_LAGGED_SOURCE`; its latest
source receipt is still about 18.5 hours old, and no service was restarted.

The source-seal failure that caused its historical restart remains unexplained.
This change may reduce CPU during a future separately versioned reader run;
it does not repair the frozen campaign or establish that parsing is the sole
cause of its lag. Next, profile a bounded sealed-segment replay in an isolated
successor and compare state digests and throughput before proposing deployment.

No orders or authenticated requests were made. No live campaign or service was
modified.
