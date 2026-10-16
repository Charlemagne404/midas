# Gate A checkpoint 013 — rotating discovery scan 16

**Captured:** 2026-10-15 11:31:31 UTC  
**Branch:** `project/veritas`  
**Checkpoint base:** `6cc4061`

## Bounded discovery and selection

The 11:31:26 scheduled scan, `scan-20261015T113126Z-bf24f3a0706b`, used the
six-frame rotating Gamma protocol and seven public HTTP attempts. The bounded
response union contained 300 unique IDs: 164 supported same-condition V1
binary pairs and 136 explicit exclusions (76 augmented NegRisk records and 60
unsupported outcome relationships). The 40-market sample contained 37 rotating
markets and three available frozen controls. It represented 14 high-, 4
medium-, and 22 low-liquidity markets. The selected panel is conditional on
the bounded response union; it is not a venue-wide sample.

Thirty-five of 40 pairs passed the common request/receipt quality gate; seven
also passed the prior reported-age gate. The CLOB batch returned the complete
unique asset set in 102 ms. Atomicity, venue sequence, and upstream queue age
remain unverified.

## Economic result

Continuous v4 analysis now contains 16 finalized snapshots, 640 selected
observations, 578 quality-valid pairs, and 62 invalid pairs across 256 market
IDs. The prior reported-age/skew gate accepts 140/640. The paired recovery is
438 states, or 68.44 percentage points. No top-ask, full-depth, minimum-size,
single-match fee, or fragmentation-safe fee gate has a positive state. Among
the 578 valid states, top-pair edge ranges from -$0.984 to -$0.001 per share.
The qualifying Arena result for this scan is recorded in [Gate F checkpoint
004](VERITAS_MISSION2_GATE_F_CHECKPOINT_004.md).

The scan and its v4 event are pinned by snapshot evidence SHA256
`bf24f3a0706b8f37d80cf62a964c4158399668eacd5106b72374ec519258c209` and
analysis event SHA256
`cc8bb26396118d238274581a1ce37fbe1eaf67c179dff076a887936a696bdee4`.
There were no authenticated requests or orders.

The previous event-level NegRisk study remains limited to one complete group
and one stale capture. Its next step is to verify additional complete groups
and their event-specific settlement bounds before comparing basket economics.
See [research inventory 016](VERITAS_MISSION2_RESEARCH_INVENTORY_016.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and the
[research backlog](VERITAS_RESEARCH_BACKLOG.md). Mission 2 remains active.
