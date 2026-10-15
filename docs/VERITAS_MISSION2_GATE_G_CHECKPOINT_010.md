# Gate G checkpoint 010 — bounded control-availability diagnostic

**Captured:** 2026-10-15 22:52 UTC
**Mission status:** active; the dashboard projection remains read-only.

## Implemented

The coverage-pilot API now verifies the latest frozen-control availability against its hash-linked public snapshot. It checks the control-cohort file digest, pilot event chain, compressed snapshot digest, snapshot and scan identity, discovery counts, selected-market roles, and the equality between the frozen cohort and selected-plus-missing controls. It classifies each missing control as absent from the bounded query union, explicitly excluded with a recorded reason, or eligible but not selected.

The API exposes counts, the source scan, a snapshot link, a bounded selection basis, and the limitations. It never includes frozen control market IDs in this diagnostic. The dashboard shows available and missing controls with a plain-language reason breakdown. It states that absence from the bounded responses does not establish venue closure. The pilot's pinned analyzer and protocol were not modified.

## Evidence

The live API projection verifies scan `scan-20261015T223101Z-62913d43b3c1`: three of eight frozen controls were selected, and five were absent from the six-query union. The current scan's query union contains 299 unique IDs, of which 111 are eligible for the supported pair rule. This describes bounded query availability only.

The dashboard does not change the running host's deployed code. The current Midas API service uses the sibling checkout. This diagnostic is present in the `project/veritas` source tree and is not deployed.

## Verification

- `tests/test_veritas_dashboard_api.py`: **18 passed**, including verified classifications for all three missing-control cases and private-field projection checks. The existing Starlette/httpx deprecation warning remains.
- `apps/web/src/Veritas.test.tsx`: **1 passed**, including the availability summary, all three reason labels, and the query-union caveat.
- Ruff lint/format, Prettier, ESLint, TypeScript, and `git diff --check`: passed.
- A direct read-only projection from the current pilot artifacts returned `verified`, 3/8 controls available, and five absent from the bounded query union.

No service, collector, campaign, or pilot process was restarted. No economic candidate, order, or authenticated request was created. Gate G remains in progress.
