# veritas-gap-detail-v2-frontier-cpu-pressure-20261021

This immutable overlay replaces the v2 bounded-batch admission wrapper while
continuing to import the analyzer and control package tree from
`veritas-gap-detail-v2-20261021`. The base package tree is pinned by
`runtime/runtime-manifest.json`, including its file count and index digest.

The old host-wide CPU PSI rejection misclassified CPU quota wait imposed on
background replay as host saturation. This wrapper uses normalized one-minute
host load and live CPU PSI for Reality, the primary API, and the Reality API.
It keeps the existing memory and memory-PSI, I/O PSI, disk reserve, active
Arena worker, and global admission lease protections. Missing or malformed CPU
telemetry fails closed.

Only finalized Reality segments are analyzed. The wrapper changes no analyzer
semantics, persisted v1/v2 state, historical evidence, or source data.

Runtime script SHA-256: `e0b9fc8e8066934db3a1dea7c77418e2d11d7919c6fb4d3c408bec340c4f7c3f`.
Base package index SHA-256: `d0b64a7012d8e7d3561738126443065226d983c0283cd43a213a63da84a52e77`.
