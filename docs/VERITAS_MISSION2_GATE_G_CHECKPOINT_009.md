# Gate G checkpoint 009 — qualified edge distribution

**Captured:** 2026-10-15 22:37 UTC  
**Mission status:** active; the API and dashboard projection is read-only.

## Implemented

The bounded Arena research-activity response now includes the newest
completed, successful v3 Veritas qualification's top-pair edge distribution.
The API accepts it only when the job's requested scan and result metadata
match the digest-verified finding, the finding is read-only, its sample count
matches the quality-valid count, its last source snapshot matches the job's
scan, and its positive count reconciles with the unchanged top-ask gross gate.
If the newest completed qualification does not pass those checks, no edge
distribution is projected.

The Gate G opportunity panel shows the minimum, nearest-rank median, maximum,
and positive gross count alongside its source scan and snapshot count. It links
to the sealed finding and states that the qualification may trail the newest
observer scan. Repeated states remain labeled as correlated measurements,
not independent opportunities or fills.

## Evidence shown

The latest live observer artifact is scan 38,
`scan-20261015T223101Z-62913d43b3c1`: 1,520 selected market observations,
1,341 quality-valid pairs, and a maximum top-pair edge of -$0.001 per share.
It records no positive states at any gross, depth, minimum-notional, or fee
gate.

The newest completed sealed qualification is still scan 37,
`scan-20261015T220039Z-1bcb8753082e`: 1,480 attempted pairs, 1,307
quality-valid pairs, and 689 unique market IDs across 37 snapshots. Its
quality-valid edge distribution has a -$0.996 minimum, -$0.020 nearest-rank
median, -$0.001 maximum, and zero positive gross states. The API projection
was read directly from the current persisted Arena job and digest-verified
finding. It remains explicitly bounded through scan 37; it does not include
scan 38.

## Verification

- `tests/arena/test_arena_api.py`: **18 passed**, including digest, job-state,
  scan-identity, and edge-count reconciliation. One existing Starlette/httpx
  deprecation warning was emitted.
- `apps/web/src/Veritas.test.tsx`: **1 passed**, including the distribution
  and sealed-finding link.
- TypeScript typecheck, ESLint on changed TSX files, Prettier check, Ruff
  check/format, and `git diff --check`: passed.
- The Python test command used the Veritas worktree's `packages/` path because
  the shared environment also contains the sibling `midas` checkout.
- No browser E2E, production build, full regression, service restart, new
  research job, or experiment was run for this increment.

The coverage pilot's pinned analyzer and protocol, collectors, frozen
campaigns, and running services were left untouched. Gate G and Mission 2
remain in progress.
