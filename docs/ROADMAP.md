# Next engineering milestones

## Directive 002: audited live observations and persistent paper execution

Highest priority: implement and independently test market-specific payout attestations for eligible v1/v2 binary conditions; verify protocol-specific fee rounding/fragmentation and resolution behavior against current contracts. Capture longer real public websocket campaigns, exercise reconnects/lifecycle updates, and measure reliable snapshot/delta reconciliation.

Build a persistent multi-market virtual broker that accepts strategy intents only through the independent risk gateway, derives actual event/market exposure from one portfolio, journals scheduler state and safely resumes after a process crash. Add full end-to-end recorded-event ingestion with honest estimated fills, input dataset manifests/hashes and migration management for both SQLite and PostgreSQL.

## Subsequent directions

- Better fill models: explicit queue assumptions, stochastic latency, competing liquidity, sell/exit orders and impact sensitivity. Compare them on fixed recorded datasets.
- Campaign runner: bounded Monte Carlo jobs, strategy/dataset registries, invariant failure minimization, differential accounting, mutation and chaos testing.
- Advanced mathematical sets: complete multi-outcome and neg-risk models only after verified outcome closure/conversion/payout mechanics; capital lockup analysis and portfolio optimization.
- Learning laboratory: execution-risk predictors first, then versioned Gymnasium environments and agent interfaces, PyTorch training, held-out evaluation, model registry and head-to-head arena.
- Operational work: authentication, metrics export, incident drilldowns, monitored disk pressure, partitioned storage, load testing and deployment hardening.

Real execution remains a separate explicit future directive and independent audit. Its implementation is not implied by any milestone above.
