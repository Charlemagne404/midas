# Milestone 2 test and demonstration evidence

Executed on 2026-10-11 in `/home/charlie/midas`, Python 3.12.3. Public responses
are timestamped captures, not current quotes. No test removed an existing scenario
or submitted a real order. See [baseline](MILESTONE_2_BASELINE.md) for the independent
initial rerun: 103 Python tests, two frontend tests and one browser test.

## Final checks

| Command from repository root | Actual result |
| --- | --- |
| `.venv/bin/pytest -q` | **162 passed, 1 skipped**, 22.03 seconds |
| `.venv/bin/ruff check packages apps/api tests infra scripts` | Passed |
| `.venv/bin/ruff format --check packages apps/api tests infra scripts` | Passed, 56 files |
| `.venv/bin/mypy packages/midas apps/api` | Passed, 31 source modules |
| `corepack pnpm format:check` | Passed |
| `corepack pnpm lint` | Passed |
| `corepack pnpm typecheck` | Passed; production build also executes `tsc -b` |
| `corepack pnpm test` | **2 passed** |
| `corepack pnpm build` | Passed |
| `corepack pnpm test:e2e` | **2 passed**, 7.6 seconds; isolated API/frontend/database |
| `.venv/bin/python scripts/replay.py` | Passed; missing second books rejected before complete observations |
| `.venv/bin/uv build` | Built 0.2.0 wheel and source distribution |
| `docker compose config -q` | Passed |
| `docker info` | Failed: Docker API socket permission denied |

The skipped test is `tests/integration/test_postgres_paper.py`; no PostgreSQL server
was available and `MIDAS_TEST_POSTGRES_URL` was unset. PostgreSQL runtime is not
claimed. CI now includes the actual broker persistence/recovery check with PostgreSQL.
The Python suite emits one upstream Starlette/httpx TestClient deprecation warning.
The frontend build retains the large lazy chart chunk warning, 544.41 kB minified.
Neither warning was hidden. Browser tests use ports 18000/15173 and a fresh temporary
database, avoiding reuse of an old API instance.

## Coverage and independent checks

The **43 legacy scenarios remain intact**. The new lab supplies **15 fault choices**
(including the no-fault control), parameterized execution and seed selection. These
are configuration choices, not a claim of 58 separately cataloged legacy scenarios.
The final Python suite has 59 more passing cases than the baseline.

- Structural evidence: incorrect chain/contract/collateral/condition/position/parent,
  unsupported structures, expired or changed metadata and malformed attestations
  fail closed. Captured real responses replay through the production RPC verifier.
- Fees: official 100-share reference vectors independently verify helper and virtual
  venue results. Integer reference arithmetic checks rounding and fragmented fee
  bounds; unknown fees cannot become zero. Maker rebates are never credited.
- Payouts: generated terminal vectors and separate integer base-unit arithmetic
  verify fractional redemption rounding. They do not call the production financial
  calculation as their reference oracle.
- Safety and liveness: shared envelopes prevent overlapping capital reuse; mode,
  asset and book identity checks reject contamination; hard unmatched-leg limits
  remain independent; acceptable synthetic positions progress to fills and settlement.
- Recovery: real subprocess exits before commit, after commit and after one committed
  leg; repeated replay; duplicate fills; conflicting IDs; corrupt journal/checkpoint;
  duplicate restored financial entries; persistent stop; concurrent-manager CAS.
- Journey: genuine recorded metadata/books, receipt-ordered historical decisions,
  no future second book, durable restart, actual API balances/decisions/experiments,
  browser controls and downloaded comparison artifact.
- Transport boundary: exchange mutation paths are rejected before transport; all
  public HTTP requests are GET; signing and transaction RPC methods are rejected.
  Economic RPC uses only chain/block/contract reads. The virtual venue has no network
  execution adapter.
- Health: invalidated books produce DEGRADED status; a confirmed valid snapshot
  restores readiness. Streaming connection alone does not grant scanner verification.

## Demonstration A — genuine observation

```bash
.venv/bin/python scripts/verify_economics.py
```

[Captured evidence](MILESTONE_2_LIVE_EVIDENCE.json) records two live CTF markets,
4024677 and 4024680, both `VERIFIED_STRUCTURE`; the depth/fee evaluations were
`NEGATIVE_EDGE`, respectively −0.571561 and −0.483431 modeled collateral units.
Both virtual decisions rejected; no trades. Raw Gamma, CLOB, finalized helper calls,
attestation and complete proof are in `tests/fixtures/milestone2/ctf-*.json`.
The public subscription received an actual book frame and PONG. This verifies a
short subscription, not sustained streaming or reconnect reliability.

The controlled Gamma `version=v2` query returned no markets. That establishes no
live V2 support and does not prove that V2 markets cannot exist elsewhere.

## Demonstration B — autonomous paper decisions and execution

```bash
.venv/bin/python scripts/live_paper_smoke.py
.venv/bin/python scripts/paper_lab.py --seed 7 --compare
```

[Service evidence](MILESTONE_2_SERVICE_EVIDENCE.json) records actual lifecycle,
public discovery, streaming connection and a SQL-backed RUNNING `live_shadow`
broker. The final sample monitored markets 4024681 and 4024677. Both have structural
attestations, but unsequenced streaming books became invalid; the service reports
DEGRADED, logs `INVALID_MARKET` decisions and makes zero trades. This is a correct
fail-closed result and is distinct from the direct REST economics probe above.

[Differential evidence](MILESTONE_2_DIFFERENTIAL.json) uses one explicitly synthetic
ten-share fixture, identical strategy/data/seed, and the production broker state
machine. Settled virtual P&L: optimistic **0.50**, standard **0.40**, conservative
**0**. The conservative price change prevents fills at approved limits. These are
fixture results, not real profit or an estimate of live opportunity frequency.

The existing local API was gracefully restarted after an integrity-checked SQLite
backup. [Runtime evidence](MILESTONE_2_LOCAL_RUNTIME_EVIDENCE.json) confirms migration
002, retained records, durable financial tables and the autonomous default standard
synthetic account: 100 initial, 92.40 available, 7.60 locked, two hypothetical fills,
zero real orders. This open position is separate from the lab's settled experiment.

## Demonstration C — physical partial-fill termination and recovery

Use a new demonstration database; these commands preserve existing accounts:

```bash
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase prepare
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase partial_exit
# Expected exit 92 from os._exit: no graceful shutdown.
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase inspect
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase finish
.venv/bin/python scripts/paper_recovery_demo.py --db sqlite+aiosqlite:///data/new-recovery-demo.db --phase inspect
.venv/bin/pytest tests/integration/test_paper.py -q
```

[Executed phase evidence](MILESTONE_2_RECOVERY_EVIDENCE.json): after the abrupt partial
exit, 90.50 available, 5.30 reserved, 4.20 locked, one fill and ten unmatched shares.
After remaining virtual actions and explicit synthetic settlement: 100.50 available,
zero reserved/locked, exactly two fills, 0.50 realized virtual P&L. Another restart
preserves those figures. Every inspection has an empty reconciliation error list.
`before_commit` and `after_commit` exit 91; the integration suite exercises both.

## Measured local critical path

```bash
.venv/bin/python scripts/paper_benchmark.py
```

[Benchmark artifact](MILESTONE_2_BENCHMARK.json): 30 rejected synthetic observations,
FULL-synchronous SQLite WAL, durable journal/account commits. Median 24.765 ms;
empirical p95 47.679 ms; replay/reconciliation 347.022 ms at recovered revision 32.
These are local measurements under concurrent verification work, not a production
throughput benchmark, exchange latency estimate or profitability claim. Recovery
cost grows with financial history.

For PostgreSQL reproduction and durability assumptions see
[Recovery and reconciliation](RECOVERY_AND_RECONCILIATION.md). For unsupported cases
and scope reductions see [Known limitations](KNOWN_LIMITATIONS.md).
