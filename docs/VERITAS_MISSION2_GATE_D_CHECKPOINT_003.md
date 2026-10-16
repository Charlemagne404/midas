# Gate D checkpoint 003 — isolate finalized replay from mutable campaign code

**Captured:** 2026-10-16 11:29 UTC
**Status:** Bounded source and gap-detail replays resumed successfully; scheduled recurrence still to be verified.

## Failure

The finalized-source analyzer failed at 11:11 UTC, and the gap-detail analyzer
failed at 11:20 UTC. Both loaded `midas.reality.shadow_campaign` and related
modules from the editable `project/veritas` checkout. The Mission 2 campaign
guard correctly rejected those modules because `reconstruction.py` and
`shadow_source.py` had changed in that checkout. The frozen plan and its own
20-file code snapshot were unchanged.

## Recovery

A persistent import overlay was created at
`/home/charlie/.local/share/midas-veritas/frozen-runtime-overlay`. It maps
Reality packages to the immutable campaign snapshot under
`/home/charlie/midas-reality/data/research/reality/forward/mission2/code/midas`
and maps Veritas analysis packages and CLI scripts to the active branch. Both
user-level one-shot services now prepend the overlay through
`20-frozen-campaign-import.conf` drop-ins. Their campaign verification and
resume-state identity checks remain enabled.

## Verification

- Preflight found all 20 campaign code hashes equal to the frozen plan.
- Preflight found the source analyzer's `_code_identity()` equal to its
  persisted analysis state.
- The gap-detail analyzer's `_code_identity()` also equaled its persisted
  analysis state.
- Source replay resumed its saved cursor and completed 85 new segments at
  6,055/6,055. It processed 21,776,308 new bytes, reached 1,552,487,702
  processed bytes, and reports 416,513 quality-valid states across 102
  markets. Positive top-ask and full-depth counts remain zero. No bytes are
  pending. The run used 8.524 CPU seconds and peaked at 122.7 MiB.
- Gap detail processed 128 new segments and advanced to 5,885/6,064, leaving
  177 segments / 44,891,642 bytes pending. It indexes 2,142 campaign-window
  gap events: 2,138 book resynchronizations and 4 connection failures. The run
  used 4.386 CPU seconds, peaked at 112 MiB, and did not read the active
  segment.
- Both one-shot jobs exited successfully with zero systemd restarts. The
  campaign SHA remains
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`; the
  separate Reality checkout remains clean.

## Limits and next step

The import overlay is a host-level configuration outside Git, recorded in the
Mission 2 operations document. The 11:35 UTC gap-detail and 11:40 UTC source
analysis timer runs must verify recurrence. The overlay recovers frozen
historical replay; it does not modify the frozen worker, fix its source lag, or
measure the un-deployed decode-reuse change. No orders or authenticated
requests were made.
