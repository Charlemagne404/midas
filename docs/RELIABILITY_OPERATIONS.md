# Midas recovery and service operations

The API owns the Laboratory archive at `data/laboratory-final` and is the only writer while it is running. The API process, rather than the dashboard or a terminal, runs campaign coordinators. The user-level systemd units in `deploy/systemd/user/` keep the API and Vite dashboard independent of GNOME terminals and SSH sessions. Both services bind to `127.0.0.1`.

## Install and start

Install the units from the repository and enable them for the current user:

```bash
mkdir -p ~/.config/systemd/user
install -m 644 deploy/systemd/user/midas-api.service ~/.config/systemd/user/
install -m 644 deploy/systemd/user/midas-web.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now midas-api.service midas-web.service
```

With user lingering enabled, the user service manager remains available after logout. On another machine, `loginctl show-user "$USER" -p Linger` reports whether that setting is enabled. Enabling it when needed requires an administrator: `sudo loginctl enable-linger "$USER"`.

Check service and startup state with:

```bash
systemctl --user status midas-api.service midas-web.service
curl --fail http://127.0.0.1:8000/api/health
```

The API also serves interactive documentation at `http://127.0.0.1:8000/docs`. Logs are in the user journal:

```bash
journalctl --user -u midas-api.service -f
journalctl --user -u midas-web.service -f
```

The API health response reports service readiness, paper-journal recovery, and any campaign that is being resumed. A failed startup stays health-only and returns HTTP 503 for other API operations. systemd makes at most three restart attempts in two minutes, then stops so a persistent configuration or recovery failure remains visible.

Paper startup restores the last atomic account snapshot, checks its checksum and accounting invariants, then scans the journal for contiguous revisions, linked state checksums, and a rolling hash over the stored commands and payloads. A legacy database gets that rolling hash recorded on its first upgraded startup; the health response reports `LEGACY_BASELINED` for that one startup. Startup no longer reruns every historical simulation transition. For a full command-by-command audit, run the read-only verifier while the database remains available:

```bash
.venv/bin/python scripts/verify_paper_journal.py --database data/midas.db --account paper-demo
```

The full audit intentionally replays every journal event and can use substantial CPU as the history grows. It is an explicit maintenance check, not part of API startup.

## MacBook access

From the MacBook, open this tunnel and leave it running while using Midas:

```bash
ssh -N \
  -L 5173:127.0.0.1:5173 \
  -L 8000:127.0.0.1:8000 \
  user@midas-ubuntu
```

Open `http://localhost:5173` on the MacBook. The tunnel exposes only the two loopback services to the SSH client; the API, Vite server, and SQLite files remain local to the Ubuntu machine.

## Campaign recovery and shutdown

Inspect the recovered campaign in Campaign Monitor or query it directly (replace `CAMPAIGN_ID` with its ID):

```bash
curl --fail http://127.0.0.1:8000/api/laboratory/campaigns/CAMPAIGN_ID
```

Campaign records are committed by deterministic episode and variant IDs. After an API process crash, the next startup marks stale `RUNNING` campaigns interrupted and resumes only those whose prior state indicates an unexpected exit or graceful service shutdown. It skips committed episodes. A campaign that stopped because it exhausted its configured wall-time or disk budget remains interrupted for explicit operator review.

To pause a campaign, use Campaign Monitor. To request a graceful service stop, use:

```bash
systemctl --user stop midas-api.service
```

systemd signals only the API coordinator first. It finishes the current episode, commits the result, marks unfinished work interrupted, closes the Laboratory writer lease, and then exits. Start it again with `systemctl --user start midas-api.service`; eligible interrupted campaigns resume. Vite runs as a separate unit and stays available while the API restarts.

The API holds the exclusive Laboratory writer lease. Do not run a CLI campaign writer against `data/laboratory-final` while the API is active. If using the CLI, stop the API first, specify `--root data/laboratory-final`, and start the API again after the CLI releases its lease. SQLite WAL and shared-memory files are managed by SQLite; never remove them manually.

The pre-repair data snapshot is stored at an operator-managed recovery location. Its manifest records file hashes and successful SQLite integrity checks. The repaired campaign remains in `data/laboratory-final/laboratory.sqlite` under its original ID.

A second SQLite-consistent snapshot was taken after campaign completion and before the reliability changes.

## Recording capacity during Prometheus

Continuous demo recordings exhausted the original 100 MB append budget on
2026-10-12. A user-service drop-in at
`~/.config/systemd/user/midas-api.service.d/recording-budget.conf` now sets
`MIDAS_RECORDING_MAX_BYTES=1000000000` (1 GB). Existing JSONL recordings were
preserved. Disk headroom was 210 GB at the change; API health returned READY
through the original service. This remains a hard cap. Monitor `du -sh
data/recordings` and rotate preserved recordings explicitly before the new cap
is reached; this change does not implement automatic archival or retention.

### Recording isolation

Recording storage defaults to a `recordings` directory beside the configured
SQLite database. The production `data/midas.db` therefore retains its existing
`data/recordings` location. Temporary test/API databases get separate directories.
Set `MIDAS_RECORDING_ROOT` to choose an explicit location; non-SQLite or in-memory
databases retain the `data/recordings` fallback unless overridden. Each directory
has the configured append cap. This is isolation, not automatic rotation.

Laboratory archive disk scans tolerate files that disappear during enumeration
(including transient SQLite WAL/SHM sidecars). Other filesystem errors remain
visible failures; budgets still include all present regular archive files.

## Account-head encoding and reversible rollback (capacity overhaul)

Large paper account heads use a versioned `zlib-json-1` envelope in
`paper_accounts.payload`. ORM consumers see the complete logical state.
`paper_events` commands/payloads and logical checksums remain ordinary JSON and
unchanged. Each command still commits the complete head and journal atomically
with `synchronous=FULL`; no checkpoint or fsync is skipped. Small/plain legacy
heads remain readable; oversized or incompressible logical heads keep plain JSON.
Compressed decoding is bounded at 64 MiB and rejects malformed,
truncated, concatenated or oversized encodings.

Inspect heads without writing or starting an API:

```sh
.venv/bin/python scripts/paper_state_storage.py --database data/midas.db
```

Before rolling an API back to code without the decoder, explicitly stop that API,
then use the **new** helper/source to materialize its current heads as plain JSON:

```sh
.venv/bin/python scripts/paper_state_storage.py --database data/midas.db \
  --materialize --service midas-api.service
```

For the interface use its isolated `preview.db` and `midas-reality-api.service`.
The helper refuses active APIs and recorder units, checks logical SHA256 before
writing, and updates only payload representation in one FULL-sync transaction.
Revisions, logical checksums, journal hashes and historical events remain intact.
Do not restore an old head backup over a newer journal. Only after successful
materialization should the reviewed old API release be selected and started.
The capacity report records deployed identities and the tested rollback release.

The explicit full financial replay CLI now streams journal rows and validates
both the logical snapshot and every replay transition. It remains CPU-expensive
for a large journal; do not run a production full replay merely as a health check.

API synthetic recording allowances are 4 GiB per service following the capacity
overhaul's measured disk reservation. This allocates storage; it does not prune
records or replace the existing explicit retention procedure. Keep the protected
Reality reserve and separate archive/research commitments when reviewing runway.
