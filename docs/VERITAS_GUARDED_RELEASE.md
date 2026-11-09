# Veritas guarded source-analysis release

This runbook deploys one immutable Veritas source-analysis package through the
existing user systemd manager. The permanent one-shot unit is only the trigger;
`midas_resource_preflight.py` owns admission, the transient worker, the PSI
watchdog, the durable receipt, and the exit status returned to systemd.

## Release identity

- Release: `veritas-guarded-streaming-683346e0-isolated-imports-v4`
- Streaming module SHA-256: `683346e0f14a594528158676343dd1c63e5731fcb2c5beec9739abc96d1898ff`
- Veritas worker wrapper SHA-256: `5c912ed80fba851dc75fc6de19df34de3c8d5d3179b4865ffb79a78998291e59`
- Guarded launcher SHA-256: `1d216b5e40f7a23bf6bd266b4a8f0a1290d27fcd45c9126e0700fa9da8a24eda`
- Previous production module SHA-256: `e6304b6547dc5d285baab4aae3940b0fe7a6828712d995bb677aad582a44f016`
- Research root: `/home/charlie/midas-veritas/data/veritas-observatory`
- Receipt directory: `/home/charlie/.local/state/midas/guarded-executions`
- Worker ceiling: 128 segments, 32 MiB, MemoryHigh 192 MiB, MemoryMax 256 MiB,
  no swap, one CPU, 10 minutes, IOWeight 10, idle I/O priority.

The release carries the Veritas module, the eight checkpoint-provenance helper
modules, and the additional transitive import closure required by
`shadow_worker` and `shadow_campaign` (`foundry`, model feature/fitting/metrics/
registry modules, policy/store modules, arbitrage/core/economics modules).
It also carries the complete 20-file source set that the frozen campaign
provenance verifier hashes, including the risk engine. Every file is copied
from the exact currently resolved production overlay and is independently
pinned in the manifest. The manifest also pins the runtime Python ABI and
locked numerical/model-validation distributions. The worker starts Python with
`-S` and receives only the release package plus the pinned virtualenv
`site-packages` directory. This prevents the virtualenv's editable-install
`.pth` file from adding the main checkout as a fallback import root. The release
does not include the unrelated Reality API, recorder, or capacity reader.

There is exactly one packaged `ExecStart`, and it is the immutable guarded
launcher. The launcher starts the only transient research worker, waits for its
systemd result, checks the sealed v2 checkpoint and bounded summary, and returns
that result to the permanent oneshot. `ExecStartPre`, `ExecStartPost`, and
`ExecStop` alternatives are rejected. `PYTHONPATH` is cleared on the permanent
trigger. The worker uses `-S` with the release package and validated virtualenv
site packages explicitly, so editable-install `.pth` files cannot add the old
frozen overlay or main checkout as fallback import roots.

The isolated systemd integration workflow uses a dedicated CI-only service
alias and a fixed `~/midas-veritas-ci` fixture. Its guarded path redirects the
worker to that fixture only after verifying the actual packaged production
`ExecStart`, and its parent and transient worker units allow only `AF_UNIX`
address families. The test output and write permissions are confined to the
fixture; the live production service, prior immutable release v3, and live
Veritas files are not changed by the workflow.

The workflow validates a synthetic schema-v1 checkpoint through the real
systemd parent-to-transient-worker path. A fresh restore and migration test
against the exact production Restic snapshot remain blocked until the existing
backup admission policy passes the Reality protected-service headroom gate.

## Controlled rollout

1. Verify the release manifest checksum, file hashes, owner, and read-only
   modes. Verify the live module still has the previous-production hash.
2. Confirm both affected timers are disabled and inactive, the one-shot service
   is inactive, no Veritas or other conflicting worker owns the research lock,
   and the APIs and recorder are healthy.
3. Restore-verify a current recovery point. Compare its checkpoint seal,
   schema, cursor, event count, event-chain hash, campaign digest, and provenance
   to the live Veritas state. Stop if the state advanced.
4. Run the Veritas-specific 30-second admission check. Require every configured
   memory, swap, pressure, protected-service, task, and storage gate to pass.
5. Atomically copy the current service unit to a private rollback file and
   install only the packaged `midas-veritas-source-analysis.service` at
   `~/.config/systemd/user/midas-veritas-source-analysis.service`. Run
   `systemctl --user daemon-reload`. Do not install Reality v6 or update the
   production checkout. Confirm the loaded `ExecStart` exactly matches the
   single packaged launcher command, `UnsetEnvironment=PYTHONPATH` is active,
   and sandbox paths and service limits match the package.
6. Start `midas-veritas-source-analysis.service` exactly once. Do not start the
   timer. The launcher rechecks the release and checkpoint, performs outer and
   inner resource admission, and starts one transient worker under the verified
   cgroup and filesystem restrictions.
7. Require the final durable receipt classification `worker_succeeded`, a
   matching systemd result, confirmed transient-unit cleanup, verified effective
   cgroup limits, no OOM/watchdog intervention, and a sealed v2 checkpoint and
   summary whose campaign, provenance, cursor, event-chain digest, and bounded
   progress match. The launcher refuses success if the post-run state check is
   missing, malformed, regressed, or inconsistent.
8. Confirm the Reality timer remains disabled, all unrelated services remain
   healthy, and the Veritas timer remains disabled. Scheduled reactivation is a
   separate approval and must account for `Persistent=yes` catch-up behavior.

The guarded run performs the versioned v1-to-v2 checkpoint migration only
inside the bounded worker. The existing v1 file remains as a preserved rollback
artifact. Existing migration and restart tests use synthetic disposable
fixtures and verify the sealed state, event chain, cursor, and provenance
before and after migration. The exact production snapshot has not yet been
freshly restored for migration testing. The installed launcher additionally
verifies post-execution state before returning success.

## Stop and rollback rules

- Before any v2 checkpoint is committed, a deployment or preflight failure may
  be rolled back by atomically restoring the recorded previous service unit;
  the old module was not replaced by this release design.
- After restoring the old unit before migration, run `systemctl --user daemon-reload`
  and verify its old direct `ExecStart` and previous module hash before any
  future execution. Keep the timer disabled.
- If the v1-to-v2 migration has committed, never run the old v1 implementation
  against live state. Keep both timers disabled, preserve the v2 checkpoint,
  event ledger, receipt, and logs, and use the verified recovery procedure only
  after separate authorization.
- If the receipt is missing, contradictory, or not `worker_succeeded`, treat
  the invocation as failed or indeterminate. Do not retry automatically.
- Do not restore a checkpoint over live data or reactivate scheduling as part of
  rollback.
