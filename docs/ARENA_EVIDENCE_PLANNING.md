# Evidence-bound research planning

The Research Director can propose a finite executable plan from stored evidence.
The initial automatic template changes hypothesis from a PPO optimization plateau
to a completion-classifier capacity comparison. This is a transparent rule,
not unrestricted natural-language scientific reasoning.

## Selection rule

Eligible inputs must have:

- A completion dataset with validated grouped partitions and canonical lineage.
- Comparable completed logistic/MLP validation artifacts over the same observations.
- A saved PPO plateau from at least 30 fresh source groups, with changed parameters
  and zero paired outcome differences confirmed against saved rows.
- Existing comparable neural widths restricted to 32. Once other widths have
  been evaluated, automatic mode refuses to repeat this template.

The selected question asks whether width 16/64 changes validation quality and
fresh synthetic downside. Incumbent logistic/MLP controls are chosen using their
existing validation Brier only. No model's opened final-test score determines
which weights, thresholds or architecture enter the new challenge.

Explicit capacity mode is also available through the API and is labelled as a
requested template, without claiming an automatically inferred plateau.

## Frozen plan

`POST /api/arena/plans/propose` accepts dataset ID, mode, challenge seed,
episode count and training epochs. The plan binds input metadata/weight hashes,
dataset/source hashes, exact evidence snapshots, rule, question, configurations,
challenge identities and budgets. `GET /api/arena/plans/ID` exposes that record.

Freshness rejects existing training/evaluation seeds even if scenario families
are reordered, and includes prior declared tournament/director jobs. Validation
and test variants cannot enter different partitions through a storage alias.

The standard production plan has four training trials: widths 16/64 × seeds
11/29. Selection uses mean validation Brier with a preregistered simplicity
tolerance; representative seed selection is recorded. Two matched evaluations
use a single fresh cohort with support warnings and support abstention. Those
studies do not create two independent datasets. Controls include incumbents,
deterministic policies and no-trade. No automatic champion promotion is allowed.

## Execution and reliability

Native job kind `plan` takes a plan ID. A stable admission key prevents duplicate
execution requests from creating duplicate native jobs. Native CPU/memory/wall
and storage guards remain in force. At least 96 MiB active Arena headroom is
required before execution. Training/tournament stages retain their existing
checkpoints, source capture, progress and findings.

The plan rechecks source, dataset, evidence snapshots and fresh identities before
starting. Failed or interrupted plans require explicit recovery; they are never
blindly restarted. Catalog/detail views inspect the owning native worker rather
than trusting a stale RUNNING file. Exported completed plans include the original
selection evidence snapshots, Director/sweep/tournaments, model parameters,
datasets/lineage, native source and all scientific limitations.

## Boundaries and remaining work

This delivers one evidence-selected question family and its finite execution
sequence. Broader question families, failure-driven follow-up selection and
multi-day adaptive planning remain Prometheus objectives. Past findings justify
the priority rule, not causal claims that larger models will work better.

The next production run must independently verify evidence selection, exact
training configurations, validation-only selection, matched fresh scenario
coverage, accounting/uncertainty, source preservation and exported evidence.
Passing implementation tests is not evidence of a better model or strategy.
