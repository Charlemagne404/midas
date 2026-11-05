# MIDAS backup and recovery

This runbook covers active SQLite databases and the Reality recording store.
The principal data-tree inventory was measured on 2026-11-05 around 15:30
Europe/Stockholm; the active database file sizes below were refreshed at
18:42–18:43. Recording and ignored-research sizes remain from the earlier
inventory. Recheck mounts, service ownership, data sizes, and the resource gate
before each operation.

## Current protection status

There is no verified independent backup of the current MIDAS databases,
recordings, or research stores. The existing `continental-infrastructure`
backup covers other applications and Status databases; the Status timer backs
up only Status. Neither includes MIDAS. The `data/backups/` ignore rule only
keeps local backup files out of Git; it does not provide backup storage.

`/mnt/continental-cloud` is currently a separate ext4 partition on `/dev/sda4`
with about 592 GiB free. The root filesystem is on a different NVMe device.
This is a useful second disk on the same host, not an off-host copy. Confirm
that the mount is present and still uses a separate physical device before
writing; an absent mount must never be replaced by a same-named directory on
the root disk. The existing `data/midas-reality-staging` tree is historical
staging material, not a verified copy of the current Reality store.

Current measured sources include:

| Source | Current owner and state | Measured size |
|---|---|---:|
| `/home/charlie/midas/data/midas.db` | `midas-api.service`, actively written in WAL mode | 16,528,715,776 bytes; WAL 4,482,592 bytes at 18:42 |
| `/home/charlie/midas-reality/data/research/reality/interface/preview.db` | `midas-reality-api.service`, actively written in WAL mode | 12,615,774,208 bytes; WAL 4,317,792 bytes at 18:43 |
| `/home/charlie/midas-reality/data/recordings/reality` | `midas-reality.service`; writer lock held and one `.open` segment active | 58,367 finalized segments and sidecars; segment bytes 19,739,677,482 |

Additional ignored research data exists in Reality, Veritas, Arena, and
historical worktrees. These stores have different writers and evidence
contracts; they are not covered by the procedures below until individually
classified and added to the inventory. Source branches and Git history do not
back up ignored data.

A read-only check of the active Reality recorder configuration at 16:45 on
2026-11-05 found `retention_days=90`; its storage policy defines a 120-day
retention stop threshold. These runtime values are not backup retention
settings and do not prove that automated evidence pruning is enabled or
functioning. No backup retention schedule or policy is configured; confirm the
intended evidence and backup retention with the owner before enabling pruning.

## Off-host destination requirements

There is no MIDAS backup repository or verified off-host copy. `restic` is
installed, but no repository URL, credentials, schedule, retention rule, or
failure alert is configured. Do not use `/mnt/continental-cloud` as proof of
off-host protection: it is another internal disk in the same computer.

The measured principal data roots total about 64.2 GB, and a Reality staging
root adds about 4.1 GB. That gives a **known minimum payload of about 68.3 GB**;
the ignored research data across 37 worktrees has not been completely inventoried,
so the actual total is larger or equal and remains unknown. Size the off-host
destination only after classifying all protected roots. It must hold one full
verified baseline, at least 30 days of incremental change, verification and
restore workspace, and safety reserve. Do not treat compression or deduplication
as guaranteed capacity savings.

To enable it, MIDAS needs an approved destination in a separate host or cloud
failure domain, network access from the backup runner, and a least-privilege
repository credential stored outside Git (for example, a user-owned secret
store or systemd credential). The credential must permit writing and listing
snapshots; pruning access should be isolated to the retention job. A remote
provider and transfer of private research data require the owner's choice and
approval. Keep the repository encrypted, test a fresh-host restore, and alert
outside the source host when a scheduled backup or integrity check fails.

### Destination sizing and proposed operating schedule

The latest read-only mount check found `/mnt/continental-cloud` on ext4
`/dev/sda4`, UUID `2be0060d-8620-4c13-ad02-6e2bada0fb9b`, with about 592 GiB
free; `/` is on NVMe `/dev/nvme0n1p2`. This is useful local disk-failure
separation, but both devices are in the same host and failure domain. It cannot
protect against loss of the machine, theft, fire, host compromise, or a
host-level deletion.

Use these conservative minima until a complete ignored-data inventory and
30-day change sample exist:

- The first off-host baseline must store at least the known 68.3 GB of
  uncompressed source data. The total is incomplete; do not provision exactly
  that amount.
- Add the measured 30-day changed-data volume, repository metadata, and at
  least 20% free reserve. Neither the change volume nor deduplication ratio is
  currently known.
- A separate restore target needs at least the full current source payload
  (currently at least 68.3 GB) plus 20% working headroom. This is a minimum of
  about 82 GB before the incomplete inventory is added. For a new-host recovery,
  the destination host also needs room for restored data alongside its
  operating system and tools.
- The two SQLite snapshot outputs alone need roughly 29.2 GB of local
  destination space while created. The Reality recording snapshot needs about
  19.8 GB for finalized segments and sidecars, before other research roots,
  receipts, or reserve. Snapshots must be serialized and pass fresh admission.

`restic 0.16.4` is installed locally, but no MIDAS repository, URI, credentials,
timer, or external alert exists. The only active backup timers found were for
the unrelated continental infrastructure and Status database; neither covers
MIDAS. Do not add a service or timer until the owner selects an off-host
failure domain and supplies a secret through a host-owned credential store.
The eventual operator-owned environment should provide `RESTIC_REPOSITORY` and
`RESTIC_PASSWORD_FILE`; keep both out of Git and use a separate restricted
credential for retention pruning.

Suggested policy after approval, not enabled:

- Seed and fully verify an off-host baseline after the full data inventory and
  heavy resource preflight pass. Take the SQLite snapshots one at a time using
  the online backup API, then transfer immutable snapshots with restic.
- Run daily incremental repository snapshots for data sources with reviewed
  consistency semantics. The current Reality recording tool deliberately
  refuses an active writer and `.open` segment; it therefore needs either a
  separately approved clean-stop window or a separately reviewed
  writer-coordinated incremental snapshot design before automated daily
  recording protection can be claimed. Never copy the active SQLite main file
  directly or include an open recording segment as finalized evidence.
- After the repository is known-good, keep 35 daily and 12 monthly recovery
  points as an initial retention proposal. Review it against research/evidence
  retention requirements before enabling deletion. Run `restic check` weekly,
  verify a random data subset monthly, and perform a restored SQLite plus
  recording replay drill quarterly. Perform a full off-host recovery exercise
  at least annually. Send failures and last-success age to monitoring outside
  the source host.

The source-side snapshot commands already create timestamped receipts, hashes,
integrity results, and non-replacing destinations. An off-host schedule still
needs to link each receipt to its restic snapshot ID and publish a distinct
failure receipt; there is no such integration yet. Retention expiration must
be visibly reported and must not silently prune the only verified recovery
point.

## Resource admission

Large backup and verification work must run through
`scripts/midas_resource_preflight.py run`. It checks free storage, memory and
swap reserves, pressure, protected service headroom, active workers, and a
bounded systemd scope. The SQLite snapshot command also rejects large work
unless the scope reports the `heavy` profile. The Reality recording snapshot
always requires that profile. These checks must pass at run time; do not lower
their thresholds or bypass them.

The 2026-11-05 heavy admission probe returned `DENY` for
`swap_reserve_below_profile_floor` and `swap_activity_above_profile_limit`.
The 18:40 read-only refresh showed all 4 GiB of swap occupied with 52 KiB free;
the first `vmstat` sample had 49 pages swapped in and 53 out, with none in the
next two samples. I/O PSI was elevated and the two later samples had 7% I/O
wait. `/mnt/continental-cloud` has capacity, but no live data backup or heavy
preflight was attempted during this refresh. Wait for the machine to satisfy
admission and rerun the gate. This is not a fresh pass. Capture each gate
result in a private receipt log so denials and failures remain reviewable.

## SQLite snapshot

`scripts/midas_sqlite_snapshot.py` uses SQLite's online backup API. It reads a
consistent transaction including WAL contents without copying, checkpointing,
or replacing the live database. It writes a standalone DELETE-journal database,
checks SQLite integrity and schema identity, calculates a SHA-256 digest, and
publishes a timestamped directory without replacing an existing recovery
point. Its optional `--receipt` records success or a caught failure. Restore
always targets a new file.

First verify that the intended mount is present and is still the separate
destination disk. The current mount was `/mnt/continental-cloud`, ext4 UUID
`2be0060d-8620-4c13-ad02-6e2bada0fb9b`; confirm the device and UUID again at
run time. `mountpoint` must succeed, and the destination source must differ
from the root filesystem source. If either check fails, stop without creating
the backup directory:

```bash
set -euo pipefail
mount=/mnt/continental-cloud
mountpoint -q "$mount"
findmnt --mountpoint "$mount" --output TARGET,SOURCE,FSTYPE,UUID
findmnt --target / --output TARGET,SOURCE,FSTYPE,UUID
test "$(findmnt --noheadings --output UUID --mountpoint "$mount" | xargs)" = \
  "2be0060d-8620-4c13-ad02-6e2bada0fb9b"
test "$(findmnt --noheadings --output SOURCE --mountpoint "$mount" | xargs)" != \
  "$(findmnt --noheadings --output SOURCE --target / | xargs)"
```

After verifying the mount, create private destination and receipt directories.
Each command below performs a fresh heavy admission before it starts the
operation; it must pass. Choose a fresh UTC timestamp for each run:

```bash
set -euo pipefail
umask 077
backup_root=/mnt/continental-cloud/data/midas-backups
receipt_root="$HOME/.local/state/midas/backup-receipts"
install -d -m 700 "$backup_root/sqlite" "$backup_root/recordings" "$receipt_root"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
```

For each active database, run one bounded backup at a time. The example below
is for the main API database; repeat it with a distinct receipt and destination
for `preview.db`.

```bash
set -euo pipefail
umask 077
log_path="$receipt_root/$stamp-main-db.log"
( set -o noclobber; : > "$log_path" )
.venv/bin/python scripts/midas_resource_preflight.py run \
  --profile heavy --memory-budget-mib 512 \
  --storage-path "$backup_root/sqlite" \
  --storage-required-mib 20000 --storage-reserve-mib 5120 \
  --memory-high-mib 1024 --memory-max-mib 1536 \
  --cpu-quota-percent 20 --timeout-seconds 21600 --label midas-sqlite \
  -- .venv/bin/python scripts/midas_sqlite_snapshot.py backup \
     --source /home/charlie/midas/data/midas.db \
     --destination "$backup_root/sqlite/midas-$stamp" \
     --allow-large --receipt "$receipt_root/$stamp-main-db.json" \
  2>&1 | tee -a "$log_path"
```

The 20,000 MiB storage estimate leaves room for either measured database plus
the separate 5,120 MiB reserve. The command still checks the actual logical
database size and current free space before copying. Use a separate admission
run for `preview.db`; do not run both copies concurrently. Verify the complete
copy before treating it as a recovery point:

```bash
set -euo pipefail
umask 077
.venv/bin/python scripts/midas_resource_preflight.py run \
  --profile heavy --memory-budget-mib 512 \
  --storage-path "$backup_root/sqlite" \
  --storage-required-mib 1024 --storage-reserve-mib 5120 \
  --memory-high-mib 1024 --memory-max-mib 1536 \
  --cpu-quota-percent 20 --timeout-seconds 21600 --label midas-sqlite-verify \
  -- .venv/bin/python scripts/midas_sqlite_snapshot.py verify \
     --snapshot "$backup_root/sqlite/midas-$stamp" \
     --integrity full --receipt "$receipt_root/$stamp-main-verify.json"
```

To perform a full-size restore drill, use a fresh path on the verified backup
disk. It creates another database-sized file and must pass fresh admission:

```bash
set -euo pipefail
umask 077
restore_stamp=$(date -u +%Y%m%dT%H%M%SZ)
.venv/bin/python scripts/midas_resource_preflight.py run \
  --profile heavy --memory-budget-mib 512 \
  --storage-path "$backup_root/sqlite" \
  --storage-required-mib 20000 --storage-reserve-mib 5120 \
  --memory-high-mib 1024 --memory-max-mib 1536 \
  --cpu-quota-percent 20 --timeout-seconds 21600 --label midas-sqlite-restore \
  -- .venv/bin/python scripts/midas_sqlite_snapshot.py restore \
     --snapshot "$backup_root/sqlite/midas-$stamp" \
     --destination "$backup_root/sqlite/restored-$restore_stamp.sqlite" \
     --integrity full --receipt "$receipt_root/$restore_stamp-main-restore.json"
```

The full verification checks the manifest checksum,
database digest, SQLite integrity, and schema fingerprint. Keep both the
snapshot directory and its receipt. The snapshot manifest includes the source,
destination, timestamp, byte count, journal mode, schema identity, checksum,
admission evidence, and integrity result.

## Reality recording snapshot

`scripts/midas_recording_snapshot.py` copies only finalized `.seg` files and
their original `.json` sidecars. It acquires `writer.lock` nonblocking and
refuses to run if a writer owns it or any `.open` segment exists. The source
recorder must be stopped cleanly during an approved maintenance window so its
current segment is finalized. The snapshot then validates every copied segment
against its sidecar and replays every record before publishing. It does not
copy `writer.lock`, open segments, mutable status, or unrelated files.

Do not stop the protected recorder for a backup without an approved downtime
window. In a fresh shell, re-run the mount checks above and create/verify the
backup and receipt directories. In that window, the following guarded shell
block stops only the recorder, refuses to proceed if it did not stop cleanly,
and attempts to start it again on every exit path. Confirm that the protected
unit name and owning user still match the live host before running it:

```bash
set -Eeuo pipefail
umask 077
mount=/mnt/continental-cloud
mountpoint -q "$mount"
test "$(findmnt --noheadings --output UUID --mountpoint "$mount" | xargs)" = \
  "2be0060d-8620-4c13-ad02-6e2bada0fb9b"
test "$(findmnt --noheadings --output SOURCE --mountpoint "$mount" | xargs)" != \
  "$(findmnt --noheadings --output SOURCE --target / | xargs)"
backup_root="$mount/data/midas-backups"
receipt_root="$HOME/.local/state/midas/backup-receipts"
install -d -m 700 "$backup_root/sqlite" "$backup_root/recordings" "$receipt_root"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
log_path="$receipt_root/$stamp-reality-recordings.log"
( set -o noclobber; : > "$log_path" )
unit=midas-reality.service
recording_root=/home/charlie/midas-reality/data/recordings/reality
restart_recorder=0
restore_recorder() {
  if (( restart_recorder )); then
    systemctl --user start "$unit"
    systemctl --user is-active --quiet "$unit"
  fi
}
trap restore_recorder EXIT
systemctl --user is-active --quiet "$unit"
restart_recorder=1
systemctl --user stop "$unit"
if systemctl --user is-active --quiet "$unit"; then
  echo "Recorder remains active; aborting backup" >&2
  exit 1
fi
open_segment=$(find "$recording_root" -maxdepth 1 -type f -name '*.open' -print -quit)
if [[ -n "$open_segment" ]]; then
  echo "Recorder left an open segment: $open_segment" >&2
  exit 1
fi
set -o pipefail
.venv/bin/python scripts/midas_resource_preflight.py run \
  --profile heavy --memory-budget-mib 512 \
  --storage-path "$backup_root/recordings" \
  --storage-required-mib 30000 --storage-reserve-mib 5120 \
  --memory-high-mib 1024 --memory-max-mib 1536 \
  --cpu-quota-percent 20 --timeout-seconds 43200 --label midas-recordings \
  -- .venv/bin/python scripts/midas_recording_snapshot.py backup \
     --source-root /home/charlie/midas-reality/data/recordings/reality \
     --destination "$backup_root/recordings/reality-$stamp" \
     --receipt "$receipt_root/$stamp-reality-recordings.json" \
  2>&1 | tee -a "$log_path"
systemctl --user start "$unit"
systemctl --user is-active --quiet "$unit"
restart_recorder=0
trap - EXIT
```

Verify the resulting snapshot with `scripts/midas_recording_snapshot.py verify`
inside a second heavy scope. The tool checks the snapshot and recording
manifests, every sidecar checksum, every segment digest, and the full record
stream. Use a fresh bounded admission and receipt, for example:

```bash
.venv/bin/python scripts/midas_resource_preflight.py run \
  --profile heavy --memory-budget-mib 512 \
  --storage-path "$backup_root/recordings" \
  --storage-required-mib 1024 --storage-reserve-mib 5120 \
  --memory-high-mib 1024 --memory-max-mib 1536 \
  --cpu-quota-percent 20 --timeout-seconds 43200 --label midas-recordings-verify \
  -- .venv/bin/python scripts/midas_recording_snapshot.py verify \
     --snapshot "$backup_root/recordings/reality-$stamp" \
     --receipt "$receipt_root/$stamp-reality-verify.json"
```

For a full-size restore drill, choose another new path on the verified backup
disk. The restore command replays the copied record stream before publishing
the directory and records the segment/record counts in its receipt:

```bash
set -euo pipefail
umask 077
restore_stamp=$(date -u +%Y%m%dT%H%M%SZ)
.venv/bin/python scripts/midas_resource_preflight.py run \
  --profile heavy --memory-budget-mib 512 \
  --storage-path "$backup_root/recordings" \
  --storage-required-mib 30000 --storage-reserve-mib 5120 \
  --memory-high-mib 1024 --memory-max-mib 1536 \
  --cpu-quota-percent 20 --timeout-seconds 43200 --label midas-recordings-restore \
  -- .venv/bin/python scripts/midas_recording_snapshot.py restore \
     --snapshot "$backup_root/recordings/reality-$stamp" \
     --destination "$backup_root/recordings/restored-$restore_stamp" \
     --receipt "$receipt_root/$restore_stamp-reality-restore.json"
```

The guarded block restarts the recorder after the copy; confirm its
service state and that it opened a new `.open` segment. Keep the verified
snapshot; do not prune old evidence as part of this procedure.

## Recovery and restore drills

Both formats restore to new paths and refuse overwrite. Test restores first in
an isolated directory with no service pointed at it. For SQLite, run
`midas_sqlite_snapshot.py verify` and `restore`, compare the restore digest,
check the schema and application compatibility, and leave the production path
unchanged. For recordings, run `midas_recording_snapshot.py verify` and
`restore`, then enumerate the restored manifest and replay its records. The
unit tests create disposable WAL databases and synthetic Reality segments and
exercise successful restore, tamper detection, active-writer rejection, and
no-overwrite behavior.

A production database or recording-root cutover is a separate change. It
requires a coordinated service stop, fresh backup and restore evidence, a
reviewed path/configuration change, and a tested rollback. Never copy a live
SQLite main file while ignoring its WAL, replace a running database, or point a
writer at a restored recording root without validating its ownership and
recovery state.

## Recovery domains and remaining work

- Git branches and preservation refs protect source history only. The
  2026-11-05 unreachable-commit pins are local refs until copied to another
  trusted Git remote or bundle.
- SQLite snapshots protect database transaction state and WAL contents.
- Reality segment snapshots protect finalized raw recording bytes and their
  record manifests. Runtime status and other evidence roots need their own
  classified backup procedure.
- Existing Veritas, Frontier, Arena, Laboratory, and ignored worktree data has
  not been backed up by this runbook. Preserve it until ownership, writers, and
  consistency requirements are established.
- The current second disk is on the same host. Add a verified off-host copy,
  restore drills, monitoring, and a reviewed retention policy before describing
  MIDAS as protected against host loss.
