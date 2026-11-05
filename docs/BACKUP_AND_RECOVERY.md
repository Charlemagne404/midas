# MIDAS backup and recovery

This runbook covers active SQLite databases and the Reality recording store.
The machine-specific measurements below were refreshed on 2026-11-05 around
15:30 Europe/Stockholm. Recheck mounts, service ownership, database sizes, and
the resource gate before each operation.

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
| `/home/charlie/midas/data/midas.db` | `midas-api.service`, open in WAL mode | 16,422,002,688 bytes; WAL 4,482,592 bytes |
| `/home/charlie/midas-reality/data/research/reality/interface/preview.db` | `midas-reality-api.service`, open in WAL mode | 12,513,951,744 bytes; WAL 4,317,792 bytes |
| `/home/charlie/midas-reality/data/recordings/reality` | `midas-reality.service`; writer lock held and one `.open` segment active | 58,367 finalized segments and sidecars; segment bytes 19,739,677,482 |

Additional ignored research data exists in Reality, Veritas, Arena, and
historical worktrees. These stores have different writers and evidence
contracts; they are not covered by the procedures below until individually
classified and added to the inventory. Source branches and Git history do not
back up ignored data.

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

## Resource admission

Large backup and verification work must run through
`scripts/midas_resource_preflight.py run`. It checks free storage, memory and
swap reserves, pressure, protected service headroom, active workers, and a
bounded systemd scope. The SQLite snapshot command also rejects large work
unless the scope reports the `heavy` profile. The Reality recording snapshot
always requires that profile. These checks must pass at run time; do not lower
their thresholds or bypass them.

The 2026-11-05 probe had 24 KiB free swap, an observed swap-in page, and
adequate separate-disk capacity. Heavy admission returned `DENY` for
`swap_reserve_below_profile_floor` and `swap_activity_above_profile_limit`.
No live data backup was attempted. Wait for the machine to satisfy admission
and rerun the gate. A later 15:30 host sample still showed all 4 GiB of swap in
use with only 16 KiB free. Capture each gate result in a private receipt log so
denials and failures remain reviewable.

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
