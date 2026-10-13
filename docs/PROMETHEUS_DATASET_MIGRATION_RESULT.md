# Dataset storage migration verified on actual preserved research

Native job `job-15b63fe257c849aa8b796701` migrated
`dataset-38ec6e9776097d8e36693372` into
`dataset-86acfda4bc54dc0bf99bf987`, using named feature storage.

All **1,593 rows** decode to exactly the original canonical objects. Every source
file remained byte-identical; labels, partition identities, economic assumptions,
decision scopes and generator provenance are unchanged. Semantic version remains
`synthetic-decision-1`; storage version is now `decision-storage-2`.

Three frozen predictors—tree, logistic regression and MLP—produce identical
outputs on all 1,593 vectors. This is 4,779 prediction-equivalence checks, not
model fitting or new held-out performance evaluation. No model was trained and
no independent scientific samples were added.

The source rows/canonical SHA is
`a0dd2d328f724337a7a544470c616d4d2ef887240fa9d647227aea4ddc00dc27`.
The named-storage rows SHA is
`088eba5fe57977848661f90c78e97c4208729e2a1b7a4a66ca40975a527ac313`.

Portable export SHA:
`ed11c39c613a61fa040dcbd75b8630cccae546e5c20d2addb392c61f522afc59`.
All **95 payloads** verify. Isolated extraction verifies all canonical rows,
the same three predictors, the original collection lineage and the normal loader.
The bundle includes migration producer, native captured source, retained original
rows/metadata and frozen predictor parameters.

Actual browser checks show the reused-observation label, migration controls and
25 canonical rows with the declared 19-feature schema; no page errors. API READY,
92,319 paper journal events checkpoint-verified; protected Laboratory campaign
remains 162,000 variants / 18,000 groups, SQLite integrity OK and ownership held.

Native runtime: 3.69 seconds, one CPU / 4 GiB / 300-second bound, event index,
zero fallback scans. Full backend gate: **582 passed, one skipped**, one existing
deprecation warning, 809.78 seconds. Frontend: **21 tests** plus typing/lint/build
passed. Pilot verifier/coordinator: **six tests** passed separately.

The catalog now contains seven stored synthetic dataset identities: five source
collections, one target derivation, and this storage migration. Seven identities
do not imply seven independent datasets. Models remain 45 artifacts / 44 fitted.

Source/tool freeze is released after both supervised units completed with exit 0.
This completes the implemented storage migration contract, not the entire Data
Foundry or Prometheus scope. Broader model quality, model families, leagues,
research planning and real-market calibration remain unfinished.
