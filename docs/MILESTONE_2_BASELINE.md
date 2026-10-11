# Milestone 2 independent baseline

Audit date: 2026-10-11. Repository initially clean. Read README and the engineering,
architecture, mathematics, simulation, risk and limitations documents, then inspected
models, scanner, public transport/stream, recording, exchange, auditor, storage,
service, HTTP routes, dashboard and existing tests.

Executed baseline: `.venv/bin/pytest -q`: **103 passed**, 2.40 s; `corepack pnpm test`:
**2 passed**; `corepack pnpm test:e2e`: **1 passed**. No tests removed.

Implemented: Decimal depth scanner, independent risk gate, GET allowlist, public
stream invalidation, JSONL replay, 43 deterministic scenarios, independent ledger
audit, SQLite records, frontend with actual experiment outputs. Reported counts
match the code and rerun. Live integration claims remain historical until new probes.

Missing: market-specific structural attestation, continuous shared paper account,
durable pending actions, process recovery, live V2 economics, differential experiments.
Existing checkpoint restore is in-process; records persistence is not a broker ledger.

Foundational gaps: live proof is a boolean; descriptive Yes/No labels set complement
flag without structural evidence; fee metadata has no expiration; minimum order size
is interpreted as shares while current official market-details describes notional;
fee fragmentation reserve depends on synthetic 0.01-share matching, not live evidence;
risk state always defaults to an empty account; stop is process-local; SQLite bootstrap
is outside Alembic; journal retention must never prune financial recovery facts.

Production/simulation divergence: experiments own isolated single-market exchanges;
live observations never enter them. Existing simulator has good reusable checkpoints
and accounting invariants, so extend those rather than building another matcher.
Demo/live separation is explicit and tested; preserve it and keep paper accounts
separate by mode. Existing mission metrics sum simultaneous theoretical edges without
capital scheduling; present these as observation statistics, never portfolio profits.

Coverage gaps: physical process kill, durable duplicate mutation, concurrent writers,
attestation contradictions/expiry, fee provenance, repeated restart, live-to-paper
journey, execution-model sensitivity and portfolio-aware risk. Docker daemon access
still fails with socket permission denied; no escalation attempted. No PostgreSQL
binary found. Preserve SQLite fallback and exercise PostgreSQL in the existing CI job.
