# MIDAS documentation

Start with the root [README](../README.md) for the product boundary, installation,
and application walkthrough. This index points to the current architecture,
development workflow, operations guidance, and preserved research record.

## Build and operate MIDAS

- [Development and verification](DEVELOPMENT.md): locked setup, local services,
  test commands, and isolated worktrees.
- [Architecture](ARCHITECTURE.md): package boundaries, data flow, and storage.
- [Reliability and service operations](RELIABILITY_OPERATIONS.md): service
  startup, campaign recovery, shutdown, and recording capacity.
- [Crash recovery and reconciliation](RECOVERY_AND_RECONCILIATION.md): paper
  journal recovery and accounting checks.
- [Data provenance](DATA_PROVENANCE.md) and
  [experiment reproducibility](EXPERIMENT_REPRODUCIBILITY.md): recording,
  retention, replay, and artifact handling.
- [Known limitations](KNOWN_LIMITATIONS.md): current model, market, and
  operational limits.

## Research workflows

- [Laboratory architecture](LABORATORY_ARCHITECTURE.md) and
  [adversarial testing](ADVERSARIAL_TESTING.md): synthetic experiment design,
  campaigns, replay, and failure analysis.
- [Arena reproducibility](ARENA_REPRODUCIBILITY.md): registry checks, portable
  artifacts, and evaluation procedures.
- [Arena research topics](ARENA_ADAPTIVE_RESEARCH.md): adaptive studies,
  scheduling, dataset migration, costs, recovery, and related bounded work.
- [Project Prometheus final report](PROMETHEUS_FINAL_REPORT.md): the completed
  program, findings, verification results, exceptions, and limitations.

## Historical evidence

Prometheus generated a large, intentionally retained record under `PROMETHEUS_*`
and `ARENA_*` filenames. The final report is the navigation point and synthesis;
its referenced JSON manifests, logs, screenshots, intermediate checkpoints, and
failed or cancelled run records retain their original meaning. Treat those files
as historical evidence. Do not replace an old result with a rerun or describe a
failed gate as passing. Mutable databases, model stores, recordings, and export
archives belong under local `data/` storage and are not general source files.

## Project roadmap

See [ROADMAP.md](ROADMAP.md) for the completed Foundation, Laboratory, and
Prometheus work and the planned Reality and Atlas programs.
