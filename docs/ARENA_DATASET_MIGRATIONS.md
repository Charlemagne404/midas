# Versioned dataset storage migrations

Dataset semantic version remains `synthetic-decision-1`. New generation accepts
only that supported semantic version; unknown values fail validation. Legacy
manifests/specifications without an explicit version retain the documented
version-1 interpretation. Storage representation has a separate version:

| Storage version | Stored features | Canonical training input |
|---|---|---|
| decision-storage-1 | Ordered numeric list | Same ordered numeric list |
| decision-storage-2 | Object keyed by declared feature names | Declared feature order reconstructed exactly |

The loader rejects unknown encodings, missing/extra/duplicate names, semantic
version mismatches, corrupted hashes, cyclic migration ancestry and changed
canonical content. Existing model transforms and policy features are unchanged.

## Migration jobs

Submit through native job validation/admission or the Training console:

```json
{
  "configuration": {
    "kind": "migration",
    "migration": {
      "source_dataset_id": "dataset-SOURCE",
      "target_storage_version": "decision-storage-2"
    },
    "max_wall_seconds": 300
  }
}
```

Version 2→1 is also supported. Requesting the already-used representation is
rejected. Each conversion creates a new content/source-bound identity, preserving
the original files. Repeating the same completed conversion verifies and reuses
the existing identity; publication is serialized. Incomplete drafts are not
catalogued as complete and changed draft bytes are not silently overwritten.

Inputs are bounded to 64 MiB / 60,000 rows, with the unchanged native resource
limits and Arena storage-headroom guard. The producer file and encoded rows are
written first. Parent hashes and every decoded row are checked before completion
manifest publication. Canonical content hashes, original manifest/rows hashes,
implementation source hash, producer hash and immediate parent identity are
retained. No simulation, target relabelling, normalization fitting or model
training is performed.

## Scientific identity

All episode IDs, partition assignments, labels/targets, decision scopes, observed
times, economic assumptions and generator provenance are identical. A migrated
artifact is **the same observations in a new representation**, not an additional
independent dataset. Observation lineage traverses storage migrations and existing
target derivations to the original collection.

Target derivation after migration uses the declared encoding and records its own
transformation ancestry; it does not inherit a misleading storage-only claim.
Exports include the migrated rows, producer and full required parent lineage.
Existing saved predictor parameters receive canonically identical vectors.

The overview labels storage versions and reused source identity. Paged API rows
at `/api/arena/datasets/ID/rows` expose canonical feature vectors and their schema;
offset is nonnegative and page size is 1–200. This inspection does not evaluate
held-out models or make migrated observations independent.

## Deployment evidence still required

Focused native/round-trip/corruption/export and frontend gates precede full backend
regression. The first production pilot must independently compare every source
and target row, parent bytes, original predictor outputs and actual browser/API
evidence. Until that pilot passes, report migration as implemented, not deployed
and empirically verified. Original scientific collections and protected Laboratory
archives must remain unchanged.
