# Guarded Execution Receipts

`scripts/midas_resource_preflight.py run` writes a lifecycle receipt before it
requests a transient systemd unit. The default directory is
`$XDG_STATE_HOME/midas/guarded-executions`, or
`~/.local/state/midas/guarded-executions` when `XDG_STATE_HOME` is unset. The
directory is user-owned mode `0700`; receipt and inner-status files are mode
`0600` and updated atomically with file and directory synchronization.

Each receipt starts as `indeterminate`. It records the invocation UUID, source
and release identities when supplied, an argument-shape hash that excludes
argument values, admission evidence, requested and observed unit limits, unit
and invocation IDs, worker start confirmation, cgroup metrics, bounded
runner-output byte counts and diagnostic categories, watchdog actions, a final
classification, and journal references.
Raw command arguments, environment contents, worker stdout, and worker stderr
are not copied into receipts. Veritas transient services direct stdout and
stderr to the journal; use the recorded unit or invocation ID to inspect them.

An atomic inner-status file tracks the gate and worker lifecycle while the unit
runs. It is captured into the final receipt and kept beside it as supplementary
evidence. This lets an interrupted parent leave a durable `indeterminate`
receipt and the last inner lifecycle state without treating an absent result as
success. The inner Veritas supervisor retains its runtime PSI watchdog and
execution timeout if the outer caller disappears; the transient unit also has
`RuntimeMaxSec` and `KillMode=control-group`.

Completed receipts and their sidecars are retained together, up to the newest
128. Incomplete or indeterminate receipts are never pruned automatically. At
256 retained receipts, new work fails closed until an operator reviews the
incomplete records. The runner does not retry work. Only after a final receipt
is durable may an inactive Veritas transient unit be reset from systemd's
failed-unit list.

Important classifications include `admission_denied`,
`admission_check_failed`, `unit_creation_failed`, `unit_created_not_started`,
`inner_admission_failed`, `execution_setup_failed`, `worker_startup_failed`,
`worker_failed`, `worker_terminated_by_signal`, `worker_killed_oom_or_oomd`,
`psi_watchdog_cancelled`, `timed_out`, `cancelled_by_parent_signal`, and
`result_missing_indeterminate`. Only `worker_succeeded` is a successful result.
An indeterminate result requires diagnosis; it must never be promoted to
success based on a zero exit code alone.
