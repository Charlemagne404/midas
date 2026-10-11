# Crash recovery and accounting

Alembic migration 002 adds `paper_accounts` and `paper_events`. Account ID/revision
and event ID are unique; `(account_id, revision)` has a unique index. Each transition
updates the account through compare-and-swap and inserts its immutable journal event
in one transaction. Journal events retain input command, decision, new financial entries,
state checksum and preceding checksum. The latest account holds a complete checkpoint.
The hot decision cache is bounded to 200; all decisions remain in the financial journal.
Financial journal tables are excluded from observation retention/pruning.

State is computed on a private copy, then published after commit. A crash before commit
leaves both journal and account unchanged; a crash after commit recovers both. The
same event ID and command is idempotent; an ID with different content is an error.
No replay recreates a fill blindly. Pending actions contain the original leg/order IDs.
A stale or unavailable current book makes the restarted action expire. The journal
alone can reconstruct every financial state transition with the recorded inputs.

Startup replays every command from initial configuration, checks contiguous revisions,
checksums and derived event facts, audits each exchange, then compares the recovered
state to the account snapshot. Bucket/inventory/fill/settlement/order reservations and
asset cost basis reconcile independently. Inconsistent snapshots, corrupt journals or
CAS conflicts halt admission. No automatic repair fabricates money. Restore a verified
backup or diagnose the exact discrepancy; never reset an account to conceal it.

SQLite uses WAL, explicit FULL synchronous writes and a five-second busy timeout.
This is a local single-service laboratory. CAS also protects concurrent managers from
lost writes, but conflicts halt that manager rather than providing a distributed broker
or transparent leader election. PostgreSQL uses SQL transactions and the same schema;
actual local PostgreSQL execution remains unavailable because Docker socket permission
is denied and no local server binary is present. No privilege escalation was attempted.
The CI PostgreSQL job now executes the broker recovery test in addition to migrations.

SQLite startup now uses Alembic too. A legacy records-only bootstrap with the expected
column names is adopted at revision 001, then upgraded; unexpected schemas fail closed.
Back up the database before upgrading an existing laboratory. Runtime migrations assume
one process owns startup; cross-process migration coordination is not implemented.

Physical termination reproduction (use a fresh explicit demonstration database):

```bash
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase prepare
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase partial_exit
# Expected exit status 92: one committed leg, no graceful shutdown.
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase inspect
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase finish
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase inspect
```

`before_commit` and `after_commit` instead exit 91 at the SQL boundary. Automated tests
exercise all three exits and repeated restart. `MILESTONE_2_RECOVERY_EVIDENCE.json` records
one fill/4.20 locked/5.30 reserved after partial termination, then exactly two fills,
100.50 available and 0.50 synthetic realized P&L after completion; reconciliation is empty
at every inspection. No real orders or settlement occur.

Independent PostgreSQL reproduction on a Docker-enabled workstation:

```bash
docker compose up -d postgres
MIDAS_DATABASE_URL=postgresql+asyncpg://midas:midas_local@localhost:54329/midas .venv/bin/alembic upgrade head
MIDAS_TEST_POSTGRES_URL=postgresql+asyncpg://midas:midas_local@localhost:54329/midas .venv/bin/pytest tests/integration/test_postgres_paper.py -q
```

Recovery cost grows with journal length; checkpoints/compaction preserving verifiable
financial history and replay across future strategy versions need further work. Raw
market JSONL remains a separate recording system without fsync; it is not the durable
financial ledger. Recording degradation blocks new paper decisions and action processing.
