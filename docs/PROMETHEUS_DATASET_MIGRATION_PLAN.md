# Dataset migration — audit and implementation requirements

Read-only inventory validates all six current datasets: all declare
`synthetic-decision-1`, with ordered numeric feature lists and existing feature
schema/version. Row counts are 1,746 / 1,593 / 1,752 / 1,932 / 1,935 / 1,935.
Five are independently constructed source datasets; one is a target derivation.
These counts are correlated rows, not independent samples.

The specification currently accepts arbitrary dataset version strings. The
loader validates feature version, hashes, labels and grouped partitions, but
does not dispatch on the dataset version. This is a concrete schema-governance
gap. No original manifests or rows were changed during the audit.

## Required migration behavior

- Define supported dataset/storage schema versions explicitly and reject unknown
  versions before building or training. Preserve documented legacy defaults.
- Introduce a meaningful storage revision with named feature values and explicit
  schema metadata, while adapting supported stored representations to the same
  canonical training feature order. Reject missing/extra/duplicate feature names,
  nonfinite values and unsupported feature semantics.
- Migrate by creating a new identity and new files; never edit the legacy source
  or relabel its identity. Record original rows/manifest hashes, transformation
  source, target schema and creation-source identity. Publish completion only
  after the destination has passed full verification.
- Preserve every base episode, partition identity, label/label target, decision
  scope, observed time, economic assumption and execution-cost target version.
  Preserve derivation ancestry and distinguish storage migrations from additional
  independent observations. No synthetic regeneration or new test allocation.
- Check canonical content equivalence on every row and a round trip. Migration
  should not open final-test metrics or fit normalization against held-out data.
- Ensure catalog, model/dataset provenance, quality analysis, exports, original
  source reproduction and source-bound checkpoint rules remain compatible.
  Updated code must not silently permit an incompatible old checkpoint to resume.
- Use explicit bounded operations, native resource guards and retained backups;
  interrupted publication/repeat requests must preserve both evidence sets.

## Validation and deployment

Unit and native integration tests must cover actual legacy-to-new migration,
round-trip canonical content, grouped partitions and targets, unknown versions,
hash/corruption rejection, interrupted publication, derivation ancestry, API
catalog/quality rows and portable bundles. Validate predictions against existing
saved model parameters on canonical inputs without changing fitted artifacts.

After focused/full gates, migrate one already preserved source dataset as a
bounded pilot and compare all canonical rows, source hashes, predictions and
dashboard evidence independently. State explicitly that the resulting identity
is the same scientific observations in a different storage schema.

Do not modify package source while the PPO full regression or source-bound study
is live. Finish that study's actual training/evaluation/export/browser checks
before advancing this task. Broader Prometheus scope remains active.
