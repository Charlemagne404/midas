# Known limitations

- Live market-specific payout attestation is not implemented; live observations cannot be labeled mathematically verified. The supported v1/v2 selection and public observation paths are separate from this payout gate.
- Real live V2 discovery/books and sustained streaming deltas/reconnect campaigns were not empirically validated in this environment. V2 identification and synthetic economics are fixture-tested.
- Only a configured liquidity-sorted active-market subset is discovered. Pagination and exhaustive event discovery are deferred; Gamma embedded associated events supply event identity.
- No atomic cross-instrument snapshots, trustworthy websocket sequence recovery or validated book-hash reproduction. Stream deltas conservatively invalidate books until polling confirms snapshots.
- Fee ceiling/fragmentation reserve assumes the synthetic venue's 0.01-share matching model. Real aggregate books do not establish that assumption. Unsupported exponent schedules are rejected.
- Size optimization evaluates depth breakpoints and capital constraints; it does not prove an optimum over every financial rounding discontinuity.
- The venue models internal BUY limits/IOC/GTC explicitly matched against asks. It lacks queue position, probabilistic fills, passive matching, sell orders, market impact, competing participants and empirical latency distributions.
- Virtual portfolios are per experiment. There is no continuous shared paper account or persistent scheduler checkpoint recovery; exchange checkpoint scenarios serialize state within a process. Event/market existing exposures are scenario inputs.
- The low-level simulator is not an isolation boundary for untrusted plugins. Future agents need an enforced risk-controlled broker gateway.
- Raw writes flush but do not fsync; a truncated tail requires explicit repair. Metadata replay requires the external market contracts; raw-only book updates cannot recreate trustworthy execution.
- Live recording/persistence degradation blocks new simulations, but there is no external alerting service or full service-level chaos campaign. Raw budget and record retention are configurable; older files require explicit pruning.
- SQLite auto-bootstrap and PostgreSQL Alembic migration paths both exist. Migration upgrades for existing SQLite auto-created databases need a unified follow-up implementation.
- All HTTP operations are intended for a trusted local user. No authentication/authorization, internet deployment controls or arbitrary strategy-code sandbox exists.
- Emergency stop is process-local and resets on restart; scenario-level stop events are separate reproducibility inputs.
- Docker socket access was denied locally. Container build/start and PostgreSQL execution must be verified in CI or on a Docker-enabled workstation; local tests use SQLite. CI includes a PostgreSQL migration and insert/read job.
- The graphing library creates a substantial lazily loaded browser chunk. Bundle measurements and remaining warnings are reported in the engineering report.
- No multi-outcome/neg-risk arbitrage, ML training, funded account, shadow/live execution, wallet authentication, signatures or real order management is implemented.
