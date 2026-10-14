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

## Active: Project Reality

Build continuous observation of real public markets, durable recordings,
chronological datasets, execution calibration, and forward validation. Research
should measure what the system observed and what a conservative paper execution
model could have done. Keep observations, estimated fills, and synthetic results
distinct, and preserve chronological ordering and source provenance throughout
dataset creation and evaluation.

Mission 1 recording is complete. Mission 2 is executing Gates A–G in order;
Gate A is accepted with eight-market observation, bounded storage, verified daily
archival, versioned reconstruction, timing evidence and controlled deployment.
Gate B is accepted with reproducible public-observation datasets, measured/censored
labels, chronological embargoes, family grouping and independent raw audits.
Gate C adds observational calibration, explicit execution-uncertainty scenarios
and preserved-simulator comparisons. Gate D adds genuine observation-target
training, consumed frozen tests and explicit insufficient-evidence eligibility.
Gate E is accepted with a live frozen prospective campaign, independently audited
canary and durable integrity monitoring. Gate F's native Reality interface is next. See the
[Calibration Laboratory progress and operations](REALITY_CALIBRATION_LABORATORY.md).

## Deferred: Project Atlas

Build secure distributed research computing across multiple machines, with
easy-install Windows workers and centralized orchestration. Atlas should give
operators clear worker enrollment, bounded task execution, durable job states,
and verifiable result transfer.

Atlas remains deferred while Reality Mission 2 is implemented. The future
systems should remain architecturally compatible. Reality should produce immutable, checksummed dataset manifests
and bounded replay or evaluation tasks that Atlas can dispatch. Atlas should
return portable artifacts and provenance that Reality can validate without
sharing a mutable database or research directory between machines.

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
- Develop Reality and Atlas in separate branches or worktrees rooted at the
  Prometheus baseline. Do not begin either program as part of repository
  maintenance.
