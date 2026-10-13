# Verified replay packing

Completed Arena studies may store their exact gzip replay payloads in a versioned
SQLite file. JSON/gzip lookup remains preferred; absent loose files use the
read-only store with per-payload checksums. Connections are closed explicitly.

`python -m scripts.pack_replays --kind tournaments --identity <id>` prepares and
checks the store without removing loose files. Maintenance holds both admission
and worker leases and refuses queued/active jobs. Temporary storage headroom is
checked against the unchanged1GiB cap.

After deployed-reader, backup and full-gate verification, `--prune` checks every
original/restored byte before removing loose files. Partial pruning can be rerun;
readers fall back to the store even when a loose file disappears during lookup.

Restore byte-identical loose files into a new directory with `--restore
<study>/replays --destination <new-directory>`. Existing files are never
overwritten. Restoration is required when using older captured source readers
that predate packed-store support. Bundles include the store and packing manifest.

This reduces file/watch pressure; SQLite page overhead can increase stored bytes.
It does not reclaim economic evidence or increase storage/kernel quotas.
Protected Laboratory archives are never packed through this tool.
