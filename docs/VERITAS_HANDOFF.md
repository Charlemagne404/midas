# Project Veritas handoff

Reality Mission 2 is complete at `714f824` and merged into `main`. Project
Veritas is now active on the separate `project/veritas` branch, based on the
release checkout. Its current work covers read-only source replay, decision
freshness, market opportunity, hypothetical economics, and synthetic execution
break-even thresholds. It has not changed the Reality campaign and does not
include orders, wallets, credentials, or live execution. Use the research
backlog, ledger, inventory, and latest Gate A/B checkpoints as the current
state of the work.

## Current architecture

- `packages/midas/` contains domain, observation, simulation, research, and
  artifact logic. Reality is implemented under `packages/midas/reality/`.
- `apps/api/` exposes the application API. Reality's evidence routes live in
  `apps/api/reality.py` and provide bounded collection, history, artifact,
  operations, and forward-research interfaces.
- `apps/web/` is the API-backed dashboard. Reality's native view is
  `apps/web/src/Reality.tsx`, with styles and history helpers beside it.
  Veritas has its own native page at `apps/web/src/Veritas.tsx`; its read-only,
  artifact-backed API is in `apps/api/veritas.py`.
- `deploy/reality*.json` defines collector and research settings.
  `deploy/systemd/user/` contains the recorder, shadow worker, API, web, archive,
  capacity, scheduled-research, and integrity units and timers.
- Reality services run from `/home/charlie/midas-reality`, a separate
  operational worktree. Keep that checkout and its service paths in place while
  collection and the frozen campaign are active.

## Research limits

The collector observes a bounded public-market panel; it is not a representative
sample of the entire venue. Current protocol support is limited to public legacy
V1 markets. V2 and ambiguous markets are excluded. The feed provides no venue
sequencing guarantee, so some lineage remains explicitly unsequenced.

The records support public quote, depth, timing, and follow-up measurements. They
do not establish private matching behavior, queue position, actual fills, market
impact, order acknowledgments, or real execution latency. Shadow decisions are
research observations and submit zero orders. Synthetic controls and modeled
execution assumptions remain labeled separately from public observations.

Current evidence is insufficient to select an eligible policy model or claim
profitability. Cross-day coverage and multi-week conclusions remain open. A
negative or insufficient result is a valid research outcome.

The Gate G backend suite exposed a Veritas test-wrapper timeout mismatch: a
bounded plan job allowed 300 seconds while its test subprocess was cut off at
180 seconds. The test now allows the declared job budget plus 30 seconds, and
the isolated fixture passed 4 tests in 162.80 seconds after the change; the
full suite has not been rerun. The Gate G browser test's
source-record label failure likely came from an active `.open` file not being
found when the reference retained its `.seg` name. Release commit `c96a031`
added lookup across both segment forms and its focused regression plus browser
recheck passed. The original API response was not captured, so that attribution
remains an inference. See the
[Gate G failure forensics](VERITAS_GATE_G_TEST_FAILURE_FORENSICS_001.md).
The separate 2026-10-14 canary failure was caused by its frozen reader treating
an empty finalized source segment as a continuity break. Release commit
`8775bda` added the zero-count guard and regression test; the canary artifact
was left failed and unchanged. See the
[shadow-canary forensics](VERITAS_SHADOW_CANARY_FAILURE_FORENSICS_001.md).

The native Veritas dashboard is implemented and available from the main
navigation. It exposes bounded summaries from versioned Gate A/B artifacts,
the hypothesis ledger, and the research inventory. Its API only returns
allowlisted JSON artifacts with SHA256 digests; it does not expose raw market
records or campaign controls. The overview omits source paths; a full artifact
response retains any provenance path fields present in that versioned JSON. See
[dashboard checkpoint 001](VERITAS_DASHBOARD_CHECKPOINT_001.md) and the
[dashboard API procedures](VERITAS_OPERATIONS.md#read-only-veritas-dashboard).

The activity-aware follow-up proposal now uses all scheduled slots for its
primary one-second yield and includes a reproducible power sensitivity. It is
still design-only: market/time dependence and the proposed coverage gate are
not yet validated, so no separate campaign is frozen or started. See
[follow-up design draft 002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md).

## Active campaigns and services

The frozen Mission 2 prospective campaign is active. Its immutable identity is
`adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`; it has a
fourteen-day window and currently reports insufficient forward evidence. The
worker appends decisions and follow-ups to its campaign store. Do not edit its
plan, pinned code, models, journal, or checkpoints, and do not restart the worker
as routine maintenance.

The public recorder, shadow worker, Reality API, and Reality dashboard are
managed by separate user services. Use read-only status and health checks first.
The daily shadow-integrity timer and scheduled archive, capacity, and research
jobs are part of the operating setup. Keep these services and the campaign
paper-only; the shadow worker has no order-submission path.

## Important data paths

The operational paths below are rooted in `/home/charlie/midas-reality` unless
noted otherwise:

| Path | Contents |
| --- | --- |
| `data/recordings/reality/` | Raw bounded recorder segments, manifests, and live status |
| `data/research/reality/forward/mission2/` | Frozen campaign plan, pinned implementation, journal database, status, and integrity evidence |
| `data/research/reality/scheduled/` | Scheduled research state |
| `data/research/reality/training/` | Research training artifacts |
| `data/research/reality/evaluation-ledger/` | Evaluation period-use ledger |
| `data/research/reality/interface/` | Dashboard evidence cache and isolated interface data |
| `data/datasets/` | Curated datasets and manifests in the repository checkout |
| `/home/charlie/midas/data/laboratory-final/` | Protected historical Laboratory campaigns and replay evidence |
| `/home/charlie/midas/data/arena/` | Protected Arena datasets, models, evaluations, and replay evidence |

Runtime recordings, research stores, model artifacts, credentials, and generated
research exports are excluded by `.gitignore`. Ignoring a path does not make its
contents disposable; preserve the existing operational data in place.

## Preservation requirements

- Do not prune, rewrite, relocate, or replace raw observations, recording
  segments, manifests, or archives.
- Do not change the frozen campaign identity, plan, pinned code, models, journal,
  follow-up state, or evaluation ledger.
- Do not delete or overwrite protected Laboratory/Arena records, datasets,
  models, or historical research.
- Do not restart collection or shadow services for repository integration work.
  Avoid actions that take ownership of their writer locks or modify their stores.
- Keep public observations, modeled execution, synthetic controls, and any later
  Veritas outputs clearly separated and provenance-linked.

## Recommended starting points

1. Read the [research backlog](VERITAS_RESEARCH_BACKLOG.md), [research
   ledger](VERITAS_RESEARCH_LEDGER.json), [operations
   procedures](VERITAS_OPERATIONS.md), [Gate A checkpoint
   011](VERITAS_GATE_A_CHECKPOINT_011.md), [follow-up design draft
   002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md), and [Gate B checkpoint
   001](VERITAS_GATE_B_CHECKPOINT_001.md).
2. Review the protected campaign's immutable identity and service health
   through read-only checks; do not launch a second worker against its store.
3. Continue research changes in the `project/veritas` worktree. Keep Reality
   operations untouched and do not merge into `main` without a separate
   integration request.
