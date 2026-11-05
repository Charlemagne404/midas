# MIDAS architecture

**Authority:** this describes the consolidated source layout on `main`. The
original `codex/midas-unification` history is preserved behind the squash
integration. Dated milestone details from the former architecture guide are in
[history](history/ARCHITECTURE_HISTORY_2026-10-30.md). Use the
[maintainer handoff](MIDAS_MAINTAINER_HANDOFF.md) and
[operations guide](OPERATIONS.md) for dated runtime facts.

## System shape

MIDAS is a Python modular monolith with one FastAPI application and a separately
built React application. Domain logic lives in packages/midas; apps/api owns
application lifecycle, configuration, persistence projections, and HTTP
contracts; apps/web owns Mission Control navigation and workspace views.

    Public observations -> Market Data and Reality -> owned evidence stores
    Synthetic inputs -> Laboratory -> Arena jobs and evaluations
    Reality, Frontier, Arena and Veritas artifacts -> Veritas qualification
    Domain APIs and research projections -> Mission Control

No path submits real orders. Scanner decisions, synthetic simulations, paper
accounting, source observations, and independent audits are separate evidence
classes.

## Subsystem ownership

| Area | Authoritative owner | Responsibility and boundary |
|---|---|---|
| Core | packages/midas/core, arbitrage, economics, risk, paper, simulation | Validated contracts, exact arithmetic, risk constraints, virtual paper accounting, and deterministic simulation. |
| Market Data | packages/midas/market_data and read-only adapters | Public observation, source-specific normalization, transport limits, and source identity. |
| Reality | packages/midas/reality; apps/api/reality.py | Recording, source quality, reconstruction, replay, capacity observations, and recovery receipts. Raw segments and journals remain Reality-owned. |
| Veritas | packages/midas/veritas; apps/api/veritas.py | Versioned scan/analysis catalogs, independent economics, qualification, observatory projections, and research coordination. It does not rewrite source observations. |
| Frontier | packages/midas/frontier; apps/api/frontier.py | Multi-source research evidence, relationship hypotheses and reviews, bounded store, and cross-market replay. Source-use policy gates remain authoritative. |
| Laboratory | packages/midas/laboratory; apps/api/laboratory.py | Deterministic simulation campaigns and adversarial experiments over synthetic inputs. |
| Arena | packages/midas/arena; apps/api/arena.py | Bounded research jobs, datasets, model evaluation, schedule dispatch, and artifact verification. |
| Research Director | packages/midas/veritas/research_director.py | Research planning and coordination. Arena owns admission, scheduled dispatch, workers, and job state. |
| API | apps/api/main.py and domain routers | Shared settings, startup/shutdown, persistence boundary, readiness, and workspace projections. |
| Mission Control | apps/web/src/App.tsx and workspace components | One navigation shell for scanner, paper, Reality, Veritas, Frontier, Laboratory, Arena, Observatory, readiness, analytics, settings, and system operations. |

There is one current readiness workspace, apps/web/src/Readiness.tsx. The
older readiness and Frontier checkpoint implementation notes remain archived;
they do not define current branch or deployment status.

## Data and evidence ownership

The shared application database stores API-owned records. Reality recordings,
Veritas catalogs, Frontier SQLite evidence, Arena datasets/models/jobs, and
Laboratory campaigns keep separate roots where their writers, retention, or
reproducibility contracts differ. The unified API reads them through subsystem
interfaces. Do not merge stores merely to make directory names uniform.

Preserve artifact identity, source hashes, code and configuration versions,
schema versions, and campaign boundaries. Keep source observations immutable.
Unknown, unavailable, synthetic, historical, virtual, and independently
verified states must remain distinct through the API and frontend.

The normal evidence flow is:

- Market Data and Reality preserve source observations with provenance.
- Laboratory and Arena test bounded simulations and research jobs.
- Frontier records its own multi-source hypotheses, evidence, and replay.
- Veritas analyzes versioned inputs and reports qualification separately from
  source collection.
- Mission Control presents those projections and their freshness/limitations.

A captured observation is not proof of complete continuity. A reconstructed
book, simulated outcome, virtual paper result, or conditional economics report
is not realized trading profitability.

## Development and runtime boundaries

The current development baseline is the reviewed `origin/main` source. Create
task branches from that baseline in a suitable clean checkout or isolated
worktree. The legacy `/home/charlie/midas` checkout and the Reality and Veritas
worktrees remain runtime dependencies on this host; do not treat a development
checkout or a source integration as a deployed release.

The API uses demo mode and local SQLite by default. Public Frontier probes are
disabled/held by default; collectors, campaign workers, timers, and long-running
research are not started by ordinary application startup. Read
[DEVELOPMENT.md](DEVELOPMENT.md) before a local run and
[UNIFICATION_DEPLOYMENT_PLAN.md](UNIFICATION_DEPLOYMENT_PLAN.md) before any
service transition.
