# Gate G checkpoint 006 — frozen-campaign label-feasibility visibility

**Captured:** 2026-10-15 20:28 UTC  
**Mission status:** active; the report is exposed read-only, while the coverage pilot and finalized-source replay continue on their schedules.

## Implemented

The Veritas overview now returns a separate `label_feasibility` projection
from `VERITAS_MISSION2_LABEL_FEASIBILITY_001.json`. The existing v1.3
follow-up/censoring projection remains tied to its own report schema. The new
projection is available at `/api/veritas/overview`, and the underlying
allowlisted artifact is available at
`/api/veritas/artifacts/label-feasibility`.

Before exposing the summary, the API checks the artifact ID and schema,
`veritas-forward-forensics-v1.4` version, genuine-public-recording marker,
campaign identity against the current raw-funnel artifact, decision and
horizon totals, markout counts, censor totals, and five-second target and
execution categories. The endpoint returns the exact file digest and does
not expose source paths or raw observations.

The UI shows frozen-campaign decisions and market coverage, observed yield at
each horizon, the number of five-second observations without an initial
discrepancy, and the number whose execution ground truth is
`unknown_counterfactual`. It states that no orders were submitted and
realized money is absent, and links to the hash-verified source artifact.
This panel is kept separate from the pinned v1.3 censoring summary and the
synthetic execution-sensitivity panel.

## Evidence shown

The genuine public recording report contains 10,253 decisions across 43
markets and 37 connected families. Of the 3,503 valid initial states, 473
have a five-second public markout (13.50%). All 473 have
`opportunity_target_status=no_initial_discrepancy`,
`opportunity_persistence=null`, and
`execution_ground_truth=unknown_counterfactual`. Across the four horizons,
937 public markouts are observed from 41,012 scheduled follow-up slots;
40,075 are censored. The initial pre-fee edge has zero positive states. This
does not establish execution, realized P&L, or a strategy target suitable for
training.

## Verification

- `tests/test_veritas_dashboard_api.py`: **15 passed**. Coverage includes a matching report, artifact digest, campaign mismatch, and unreconciled horizon rejection.
- `apps/web/src/Veritas.test.tsx`: **1 passed**, including markout-only and execution-unknown text.
- Ruff check and Ruff format check passed.
- Strict Mypy for `apps/api/veritas.py` passed.
- Prettier check and TypeScript typecheck passed.
- The API test runner reported one Starlette/httpx deprecation warning.
- No full regression suite or production build was run for this focused change.

No services, campaigns, collectors, or research jobs were restarted or altered.
