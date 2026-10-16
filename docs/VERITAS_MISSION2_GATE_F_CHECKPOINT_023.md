# Gate F checkpoint 023 — durable Director recovery

**Captured:** 2026-10-15 23:34 UTC  
**Mission status:** active; scheduled collection and analysis continue.

## Scan-pinned qualification state

The Arena child for scan 39 completed all 39 events with exit status 0 and
reported `no_positive_gross_candidate_observed`. Its finding contains 1,375
quality-valid pairs across 732 selected markets and zero positive counts at
all five economic gates. The child completed at 23:16:27 UTC. The Director
manifest still showed `current_job_state=QUEUED` and scan 38 as the latest
qualified scan at the 23:34 UTC read-only check; the next scheduled cycle is
23:45 UTC. This is a delayed projection, not a failed Arena job. Scan 40 was
published at 23:32:05 UTC and awaits qualification.

## Recovery improvement

The Director previously stopped with `UNVERIFIED` when its persisted child
job ID could not be inspected, even if the Arena store still contained the
same scan-pinned admission under its durable idempotency key. It now searches
the bounded job catalog using the canonical admission key and adopts a child
only after validating its scan and configuration. If no matching durable
child exists, it remains `UNVERIFIED` and does not submit a replacement.

Two isolated fixtures cover recovery of a stale pointer and the no-retry
behavior when both pointer and admission evidence are missing. This change is
a defensive recovery improvement; the current scan-39 job record was present
and completed, so a live stale-pointer incident has not been established.
The scheduled Director was not run manually and no research job or campaign
was altered for this change.

## Verification

`tests/test_veritas_research_director.py`: 10 passed. Ruff, Ruff format,
strict Mypy for the Director module, and `git diff --check` passed. The tests
use temporary repository and Arena roots. No full regression suite was run.

The new result is recorded as [artifact
001](VERITAS_MISSION2_DIRECTOR_RECOVERY_001.json), [research ledger
H083](VERITAS_RESEARCH_LEDGER.json), and [inventory
045](VERITAS_MISSION2_RESEARCH_INVENTORY_045.json). Gate F remains in progress.
