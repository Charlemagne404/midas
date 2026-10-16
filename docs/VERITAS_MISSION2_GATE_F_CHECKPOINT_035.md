# Gate F checkpoint 035 — source-analysis code-pin recovery

**Captured:** 2026-10-16T09:23:41Z

**Mission status:** active; bounded source analysis recovered, no economic
candidate observed.

## Failure and cause

The 09:10:33 UTC scheduled `midas-veritas-source-analysis.service` run exited
with status 1 at 09:11:13 UTC. It rejected its persisted state with
`Source-analysis state is pinned to different campaign or code`. A read-only
comparison showed that the only changed entry was `economics.py`: the v3 fee
correction had replaced the file whose hash is part of the resumable source
analysis identity. The pinned campaign hash and all other code-file hashes
matched. The stored cursor was intact at 5,734 segments through ordinal 786,013.

No state reset, campaign edit, or raw-record repair was made. The v3 economic
engine was moved to
[`economic_feasibility_v3.py`](../packages/midas/veritas/economic_feasibility_v3.py),
and the original `economics.py` was restored byte-for-byte to its pinned source
identity. Opportunity audits, the observer, and the synthetic scenario now
import the v3 module. The finalized-source analysis and raw-funnel replay keep
using the pinned depth walker. A regression test checks that the v3 and pinned
depth walkers agree on the tested quantities.

## Recovery evidence

After confirming that the campaign and complete code fingerprint exactly
matched the saved source-analysis state, the failed bounded oneshot was started
once at 09:21:21 UTC. It completed successfully at 09:23:41 UTC with exit
status 0. It used 7.024 seconds of CPU time, peaked at 121.5 MB reported
service memory, and left the timer active with zero systemd restarts.

| Measure | Result after recovery |
| --- | ---: |
| Cataloged / processed finalized segments | 5,815 / 5,815 |
| Batch processed in recovery run | 81 segments / 18,820,608 bytes |
| Cumulative processed source bytes | 1,491,299,688 |
| Pending segments / pending bytes | 0 / 0 |
| Last processed ordinal | 794,343 |
| Quality-valid states / markets | 394,313 / 102 |
| Positive top-ask / full-depth / minimum-notional states | 0 / 0 / 0 |
| Readiness | `collecting_frozen_campaign_window` |
| Summary SHA-256 | `8233bf2cc94d52ec6fa789cf5846c8ce837f33457cca378a6d2e0b5d3646f9f4` |
| Pinned campaign SHA-256 | `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5` |
| Pinned source-analysis code SHA-256 | `9f9e2249b49dd1cb10c11713aa2683567aa9cf0914c3ed2b08cf8e3fea25ebf8` |

The recovered process read finalized segments only. It did not access the
active `.open` recording, alter campaign inputs, or change the original frozen
campaign. The 09:10 UTC failure remains recorded as an operational failure;
the later successful run is not represented as if the failure never occurred.

## Verification and next checks

- Focused Veritas backend suite: 120 passed; one upstream Starlette/httpx
  deprecation warning.
- Ruff check and formatting passed for the touched Python modules.
- The saved state campaign hash, per-file code map, and aggregate code digest
  match the restored analyzer inputs exactly.
- The independent opportunity audit output default now advances to audit 012,
  preserving hash-receipted audit 011.
- The next scheduled checks are the observer at 09:30 UTC, source analysis at
  09:40 UTC, and Research Director at 09:45 UTC. Their completion remains
  unverified at this checkpoint.
- The hosted API still runs from `/home/charlie/midas`, not this branch. Its
  health endpoint and the web root respond, but it has no Veritas API routes;
  the branch dashboard changes remain undeployed.

Keep the no-trade decision. Continue passive capture and scheduled source
analysis. Monitor the next source-analysis and Director cycles for regressions
before considering this recovery durable across recurrence.
