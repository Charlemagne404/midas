# Artifact budget index

The worker retains its 1 GiB logical artifact threshold and observes storage at
every progress callback. Cancellation, wall time and host-memory checks still
run on those callbacks. The optimization changes how current sizes are obtained.

An index installs Linux filesystem notifications before its initial enumeration.
Regular inodes receive watches, including files that acquire external hard links
later. Files are opened for inode identity during registration, so pathname
replacement cannot quietly attach a watch to the wrong object. Each file path
counts separately; a hard link is not treated as storage deduplication. Symlink
files count target bytes; directory symlinks are not traversed, and all symlinks
are restatted to handle external target replacement and type changes.

Creates, writes, replacements and renames refresh affected paths and inode
aliases. Directory topology changes and event overflow trigger reconciliation.
Missing platform support, exhausted watch quota, read/registration errors or
sustained notification bursts use the original full scanner. The worker exposes
the guard mode and last tracking error. No kernel watch limit is changed.

The descriptor closes on terminal job paths, including final-report write errors.
The index is per worker, initialized after acquiring the heavy-worker lease.
Queued workers continue using the original scanner. It stores no persistent
authoritative size total that could survive an interruption incorrectly.

Like the original scanner, this is an observation of a live filesystem, not an
atomic filesystem transaction. Concurrent publishers may change bytes immediately
after an observation. Watch errors do not justify an assumed cached total.

## Evidence

Eight index lifecycle cases plus five existing job cases pass. Coverage includes
in-place growth, atomic replacement, nested directory changes, missing/deleted
roots, root symlink retargeting, external hard-link writes, late hard links,
symlink target replacement/type changes, overflow, watch failure and replacement
during registration. Existing sparse-file over-budget rejection remains tested.

The bounded publication benchmark checks every indexed total and file count
against the original scanner and checks exact cleanup. Results live in
`PROMETHEUS_USAGE_INDEX_BENCHMARK.json`. Its observation timings are host-specific
warm-cache measurements; they are not a measured whole-job speedup. Whole-job
and complete regression gates follow before broader promotion of the change.
