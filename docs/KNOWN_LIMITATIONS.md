# Current limitations — Milestone 2

- One live structure is supported: top-level non-negative-risk binary CTF singleton
  pairs backed by USDC.e. V2 identifiers/book routing remain fixture-tested; the controlled
  V2 discovery query returned no markets. Negative risk, augmented negative risk,
  combinatorial positions and nonzero parent collections are unsupported.
- Structural proof trusts a public Polygon RPC, finalized block identity and the official
  deployed CTF implementation. Exact oracle adapter identity is unresolved in the active
  sample. Human rule interpretation, disputes, clarifications and resolution timing are
  not mathematically proven. These limits are explicit in every attestation.
- pUSD/USDC.e parity, collateral value and absence of additional operational costs are
  modeling assumptions. Gas, financing, conversion and holding rewards are not estimated
  or booked. Mathematical labels are conditional, never unconditional real profit.
- Book snapshots are neither atomic across legs nor proofs of executable liquidity.
  Quantity precision, partial fills, latency, fees and liquidity withdrawal remain paper
  assumptions. No queue model, passive maker matching, sell/unwind strategy, competing
  traders, empirical latency calibration or endogenous market impact exists.
- Consumed depth is conservatively retained instead of inferring replenishment. This
  prevents repeated virtual use of unchanged liquidity but can materially undertrade.
  No automatic unmatched-leg rescue exists; hard risk blocks further proposals.
- Discovery is a bounded liquidity-sorted sample with supported structures prioritized,
  not exhaustive market coverage. Streaming deltas/reconnect logic is deterministically
  tested; public runtime coverage is a snapshot/PONG and short service lifecycle, not
  a sustained reconnect/load campaign. Snapshot hashes are not independently reproduced.
- Finalized CTF settlement ingestion is implemented and fixture-tested; the active public
  sample did not resolve during testing. There is no real redemption, merging or exchange
  execution. Historical replay requires recorded attested metadata to qualify; it cannot
  create missing historical proofs or liquidity beyond dataset end.
- Local SQLite atomic/recovery behavior is exercised, including physical subprocess exit.
  PostgreSQL runtime is **not locally verified**: Docker socket permission denied; no
  server binary. CI has a dedicated broker integration check; configured CI is not a pass
  claim. Docker Compose configuration validates, but containers were not launched.
- Runtime migrations assume one startup owner. Concurrent financial writes are protected
  by CAS/unique constraints; conflicts halt admission rather than providing leader election
  or automatic retries. Deploy as a single laboratory service.
- Journal recovery replays all financial commands. Replay cost grows with history; scalable
  compaction and cross-version financial replay/migration are deferred. Decisions in the
  hot account cache are bounded; immutable SQL decision history is paginated. Observation
  retention never removes financial journal entries. Account configuration persists and
  environment changes do not reset existing balances or risk limits.
- JSONL recordings flush without fsync and may have a truncated tail requiring explicit
  repair. This is separate from the FULL-synchronous SQL financial ledger. Recording
  degradation blocks new decisions and action processing; no external alerting service.
- The UI adds real broker state, controls, decisions, fee/proof detail, model comparison,
  telemetry and artifacts. It does not implement every requested specialized chart or an
  interactive portfolio cursor for the new lab: full lab timelines are inspectable JSON,
  while the legacy lab retains its interactive timeline. No latency sweep, distribution
  statistics, rule-review workflow or multi-dataset experiment selector is implemented.
- Experiments currently use the binary synthetic fixture and 15 configurable fault modes;
  43 legacy scenarios remain intact. Physical process crashes are separate integration
  tests, not falsely described as a simulated production-process outage.
- HTTP access is intended for a trusted local user. Authentication, multi-user isolation,
  public hosting and untrusted strategy-code sandboxing are outside scope. The chart
  library still produces a large lazily loaded chunk. No ML, wallets, credentials, real
  orders, cancellation, onchain settlement or real-money deployment controls exist.
