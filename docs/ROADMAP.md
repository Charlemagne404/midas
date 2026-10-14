# Project roadmap

## Completed

- **Foundation:** the read-only market-data path, deterministic evaluation,
  independent risk checks, virtual exchange, paper ledger, API, and dashboard.
- **Laboratory:** reproducible synthetic campaigns, recording and replay,
  adversarial tests, paper-account recovery, and accounting verification.
- **Prometheus:** the bounded model research system, Arena, evidence registry,
  replay and recovery workflows, and verified handoff. The
  [final report](PROMETHEUS_FINAL_REPORT.md) records results, exceptions, and
  known limitations.
- **Reality:** public observation, bounded recording, chronological research,
  calibrated execution assumptions, the frozen shadow campaign, and its native
  dashboard. Mission 2 is accepted for engineering handoff. Scientific model
  eligibility and multi-week conclusions remain open evidence questions; see the
  [acceptance record](REALITY_MISSION2_ACCEPTANCE.md).

## Next: Project Veritas

Project Veritas is the next project; its requirements and implementation scope
have not been set. Start with the [handoff](VERITAS_HANDOFF.md) to review the
current architecture, evidence limits, active campaign, and preservation rules.
Reality's collector and frozen fourteen-day campaign continue in their isolated
operational worktree while Veritas is scoped.

## Deferred: Project Atlas

Build secure distributed research computing across multiple machines, with
easy-install Windows workers and centralized orchestration. Atlas should give
operators clear worker enrollment, bounded task execution, durable job states,
and verifiable result transfer.

Atlas remains deferred. If resumed later, its workers should receive bounded,
reviewable jobs and return portable artifacts with provenance. They should not
share mutable databases or research directories across machines.

## Shared constraints

- Keep MIDAS paper-only. Do not add wallet handling, private trading keys, or an
  exchange order-submission path.
- Preserve the existing module boundary: domain and simulation logic belongs in
  `packages/midas`; API lifecycle and persistence belong in `apps/api`; the
  dashboard remains an API client.
- Keep observations, synthetic data, estimated execution, and research findings
  separately labeled. Do not present model scores or historical paper results
  as evidence of real profitability.
- Treat source revisions and input datasets as explicit artifact provenance.
  Workers should receive bounded, reviewable jobs and return verifiable results;
  concurrent worktrees and machines must not depend on a shared mutable local
  database or artifact directory.
- Keep the operational Reality worktree in place while its frozen campaign runs.
  Scope Veritas separately before implementing it; do not alter Reality evidence
  or runtime data during project setup.
