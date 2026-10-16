# Gate D checkpoint 001 — bounded gross-candidate provenance

**Captured:** 2026-10-15 17:35 UTC  
**Branch:** `project/veritas`  
**Status:** v2 candidate provenance is implemented and tested; no live gross candidate has exercised the path.

## Change

`economic_experiment.py` now emits one `gross_candidate_evidence` row for every
quality-valid positive top-ask row in the finalized snapshot events. The row
points to the exact relative snapshot file and its evidence digest, analysis
event digest, capture timestamp, market ID, sampled book-state fingerprint,
selection context, and prior freshness classification. The experiment checks
that the number of positive rows agrees with the event's positive top-ask
counter, rejects malformed/non-finite edges and missing candidate identity or
snapshot digest, and requires the exact `snapshots/<scan_id>.json.gz` path.

Evidence rows are bounded at 1,024. The qualification fails closed if that
bound is exceeded; it never silently truncates candidate lineage. The
experiment version and run ID are now explicitly v2 so these outputs cannot
be confused with the prior summary-only result. A candidate is marked
`NOT_YET_INDEPENDENTLY_REPLAYED`; its next step calls for independent snapshot
replay and payoff, freshness, depth, per-leg minimum, and fee checks.

This change preserves a reproducible source pointer. It does not itself
re-open a positive snapshot or independently recompute the candidate's
arithmetic, so it cannot promote a candidate or establish executable economics.

## Verification

- Four relevant test modules passed: **21 passed** across the economic
  experiment, Arena qualification, Research Director, and dashboard API.
- Ruff lint and formatting checks passed.
- Strict Mypy passed for the changed economic experiment module.
- A read-only v2 comparison of the current finalized event set processed 28
  snapshots / 1,120 selected pairs / 996 quality-valid pairs across 513
  market IDs. It found zero positive top-ask rows and emitted zero candidate
  evidence rows with `gross_candidate_evidence_complete=true`. This run was
  not written as a research finding; the next scheduled Director qualification
  will persist the updated experiment output.
- The synthetic positive-row fixture verified the complete pointer shape and
  the unverified status. A digest-valid event whose positive counter disagreed
  with its market rows was rejected.

The panel remains intermittent and selected. The positive-candidate path has
only synthetic fixture coverage until a real quality-valid positive state is
observed. No orders or authenticated requests were made; the Reality campaign
and its source records were not changed.

See [research inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json),
[Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md), and the
[Research Director implementation](../packages/midas/veritas/research_director.py).
