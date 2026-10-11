# Experiment reproducibility and storage

Experiments have deterministic per-campaign/episode/variant IDs and a unique campaign
ID. Campaign configuration is frozen in SQLite; resumption cannot alter it. Each run
retains seed, scenario hash, strategy/simulator version, execution model, dataset/event
content hash, risk/cost settings through the archived campaign/scenario, source revision
and implementation hash, audit timestamps, warnings, invariant results and financial
metrics. Dataset campaigns pin both event bytes and the complete manifest hash.
Full exported artifacts contain the complete declarative scenario and initial portfolio.

```bash
.venv/bin/python scripts/laboratory.py campaign --runs 32 --seed 7 --root data/my-lab
.venv/bin/python scripts/laboratory.py reproduce --root data/my-lab --run <run-id>
.venv/bin/python scripts/laboratory.py reproduce --scenario <scenario.json>
.venv/bin/python scripts/laboratory.py reproduce --incident <incident.json>
.venv/bin/python scripts/laboratory.py campaign --root data/my-lab --resume <campaign-id>
```

A result hash covers semantic outputs and all complete scenario inputs. The event
journal has a separate hash so retention/presentation does not alter logical results.
Detailed exports recompute result and journal hashes; compact success reconstruction
compares the result hash. Conflicting reuse of an experiment ID fails rather than
silently overwriting an archived result. Journals/checkpoints reject accidental
corruption; these are integrity checks, not signatures against malicious rewriting
of both content and checksums.

Git revision alone does not identify uncommitted development code. The implementation
hash covers all domain Python, API Python and the reproduction CLI. Changed code
blocks compact reconstruction and campaign resumption with an explicit explanation.
A retained full artifact remains inspectable, but strict dashboard re-execution requires
the archived code hash. Source snapshots/automatic checkout are not yet archived;
if the original dirty tree was lost, restore it externally or mark that experiment
irreproducible. Cross-version archive migration is deferred.

The default Quick workload is 32 episodes, Standard 1000, Deep 10000; Extreme supports
up to one million only through explicit selection. Each strategy/model variant counts
as a separate run. One to four bounded worker processes use Linux address-space caps;
two campaigns may be active per writer. Wall/disk budgets are checked between bounded
batches and may overshoot by in-flight work. The disk budget applies to the whole
Laboratory directory, including DB/WAL/artifacts. A million configurations does not
promise completion under a small disk/time budget.

Startup converts abandoned RUNNING rows to INTERRUPTED. Every completed episode's
variants commit in one FULL-synchronous transaction. Resumption skips those IDs and
reruns uncommitted episodes. Pause/cancel finish in-flight batches, preserving their
results. A writer advisory lock prevents another manager from falsely declaring a
live writer interrupted. Read-only reproduction can coexist with the writer. Separate
Environment checkpoints permit exact mid-episode resumption; automatic campaign
mid-episode persistence is not implemented.

API paths are under `/api/laboratory`: catalog, campaigns, campaign controls, paginated
runs, paired comparison, campaign export, run artifact/export/reproduce, and incidents.
Dashboard analyses use the first 2000 canonical stored runs and say so explicitly.
Campaign financial summaries exclude accounting-invalid runs, retain legitimate losses,
and report violation counts independently. Detailed replay uses retained journals;
unretained successes are exactly regenerated, verified, then inspected. Playback is
navigation through those states and never fabricates interpolation.
