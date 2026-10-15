# Project Veritas handoff

Reality Mission 2 is complete at `714f824` and merged into `main`. Project
Veritas is now active on the separate `project/veritas` branch, based on the
release checkout. Its current work covers read-only source replay, decision
freshness, market opportunity, and hypothetical economics. It has not changed
the Reality campaign and does not include orders, wallets, credentials, or
live execution. Use the research backlog, ledger, and Gate A checkpoints as
the current state of the work.

## Current architecture

- `packages/midas/` contains domain, observation, simulation, research, and
  artifact logic. Reality is implemented under `packages/midas/reality/`.
- `apps/api/` exposes the application API. Reality's evidence routes live in
  `apps/api/reality.py` and provide bounded collection, history, artifact,
  operations, and forward-research interfaces.
- `apps/web/` is the API-backed dashboard. Reality's native view is
  `apps/web/src/Reality.tsx`, with styles and history helpers beside it.
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
   procedures](VERITAS_OPERATIONS.md), and latest
   [Gate A checkpoint 010](VERITAS_GATE_A_CHECKPOINT_010.md).
2. Review the protected campaign's immutable identity and service health
   through read-only checks; do not launch a second worker against its store.
3. Continue research changes in the `project/veritas` worktree. Keep Reality
   operations untouched and do not merge into `main` without a separate
   integration request.
