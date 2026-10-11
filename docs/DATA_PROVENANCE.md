# Data provenance and retention

Each market, book and observation carries `LIVE`, `SYNTHETIC` or `RECORDED` provenance. Demo and live book states are never combined. Scenario runs always use synthetic input, even in live observation mode. Historical replay retains each input's original source and reports its historical context separately.

Exact HTTP response text and websocket frame text are preserved as `raw_wire_json`; parsed source payloads are preserved in JSONL alongside interpretation version, schema version, source, event identity, local receipt timestamp and exchange timestamp when available. Normalized snapshots accompany their raw messages. HTTP monetary JSON literals decode to Decimal before normalization. SQL payloads serialize money to strings.

Time is UTC epoch milliseconds internally. The command center displays local browser time and labels it LOCAL. Scenario replay offsets are virtual milliseconds relative to its fixed UTC epoch. Demo snapshots are regenerated from unchanged bundled fixtures with current synthetic receipt/source times; original fixture messages remain in their raw provenance. These are observations of a synthetic scenario, not evidence of real market updates.

Captured public v1 Gamma and CLOB fixture responses under `tests/fixtures` were retrieved on 2026-10-11 without credentials. They are consumed only by adapter tests. `data/samples` contains explicitly synthetic contracts and JSONL snapshots for offline replay. CI does not depend on network data availability.

## Format

Daily files named `<source>-YYYY-MM-DD.jsonl` contain one validated `MarketEvent` per line. Source frames and normalized snapshots are sufficient to reconstruct interpretation but not exchange-side orders, queue position or every missing message. Receipt order is the authoritative replay order. Exchange timestamps do not imply sequence integrity. Hashes suppress duplicates; they are not a verified checksum reconstruction or continuity proof.

Writes are serialized within the recorder, use append mode, flush per event and run outside the event loop. They are **not fsync-backed transaction journals** and do not claim survival of abrupt host power loss. A partial final line is rejected by replay and must be explicitly investigated/repaired; no silent skipping occurs.

## Storage controls

Database queries and in-memory caches are bounded. Structured records have a 30-day default retention with hourly pruning. Raw recordings have a 100 MB total default budget; reaching it visibly degrades recording and blocks new simulation admission. `scripts/prune_recordings.py` offers a dry run by default and explicit `--apply` deletion of closed older daily segments. It never removes today's active file. Preserve experiment artifacts or required input datasets before pruning.

Historical snapshots support mathematical observation replay only. There is no claim that unavailable queue/execution information can be reconstructed. Replaying real snapshots into an eventual virtual venue must label all fills as estimates and define a shared liquidity-consumption policy.
