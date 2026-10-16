# Gate A checkpoint 035 — direct frozen-control retrieval

**Captured:** 2026-10-15 23:12 UTC  
**Mission status:** active; the 24-hour coverage pilot and protected Reality
campaign remain unchanged.

## Bounded direct lookup

Scan 39 completed at 23:00:55 UTC. Three of the eight frozen controls were
selected; the other five were absent from its six-query Gamma union. At
23:11:44 UTC, a separate probe issued one unauthenticated `GET /markets`
request with the eight explicit market IDs and `closed=any`. Gamma's published
[OpenAPI schema](https://gamma-api.polymarket.com/openapi.json) defines the ID
filter as an array and documents `closed=any` for including open and closed
markets.

The response returned all eight controls. Cross-checking against scan 39 and
the same V1 metadata normalizer found:

- Three controls selected in scan 39 were open and eligible in the direct
  lookup.
- Three controls absent from scan 39's bounded union were also open and
  eligible in the direct lookup.
- The remaining two controls were absent from the bounded union and had
  `closed=true` in the direct response.

The three open controls missed by the six-query frame show that its control
availability diagnostic was measuring query-frame coverage as intended; it
was not evidence that those controls had closed. The lookup followed scan 39
by about 11 minutes, so it does not establish their exact lifecycle metadata
at the scan's capture time. The two `closed=true` values describe the direct
response only.

The probe made one public request and one HTTP attempt. It read no CLOB books,
used no credentials, and submitted no orders. The gzip evidence is stored in
the ignored research-data directory with mode `0600`; the response hash,
cohort hash, file hash, and per-control hashed identifiers are recorded in
[inventory 043](VERITAS_MISSION2_RESEARCH_INVENTORY_043.json). The diagnostic
does not evaluate prices, liquidity, fees, or economic viability.

## Decision and next work

Keep the current v1 pilot and its pinned implementation unchanged through its
fixed stop. This probe verifies that an explicit-ID lookup can resolve the
frozen controls within one bounded request. A successor scan can reserve one
of the existing seven public-call slots for that lookup by using five Gamma
discovery frames, one control-ID lookup, and the existing batched book read.
That tradeoff needs a separately versioned study after the v1 pilot ends; it
reduces rotating discovery frames by one and must be measured against the
current frame before adoption.

The standalone probe and classifier are implemented in
[`control_retrieval.py`](../packages/midas/veritas/control_retrieval.py) and
[`run_veritas_control_retrieval_probe.py`](../scripts/run_veritas_control_retrieval_probe.py).
Three focused tests pass, along with Ruff lint, formatting, and diff checks.
Gate A remains in progress. See [research ledger H081](VERITAS_RESEARCH_LEDGER.json)
and [inventory 043](VERITAS_MISSION2_RESEARCH_INVENTORY_043.json).
