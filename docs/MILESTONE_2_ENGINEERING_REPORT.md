# Milestone 2 engineering report

Date: 2026-10-11. Midas 0.2.0 extends the existing research platform with conditional,
protocol-aware CTF economics and a durable autonomous paper account. The original
scanner, risk engine, virtual venue, accounting auditor, scenarios and dashboard are
retained. All orders, fills and settlements are internal simulations. No wallet,
private key, authenticated exchange mutation client or real deployment control exists.

The core economically verifiable scanner and persistent broker are working. Some
requested peripheral UI/analytics features are reduced in scope, and live V2 and
local PostgreSQL runtime remain unverified. This report does not represent those
items as complete.

## Completed functionality

### Economic verification

`midas.economics` supplies a structured `MarketEconomicAttestation`, exact fee
calculations and a conservative fragmented-fee bound. `CTFVerifier` calls only
public Polygon reads at a finalized block. It verifies chain, official CTF contract,
binary condition, unresolved state, zero parent collection, USDC.e collateral and
the actual singleton position IDs for index sets 1 and 2. Every attestation retains
machine evidence, source URLs, metadata/rule hashes, method version, expiry and
unresolved assumptions. Market prose is descriptive evidence, never a mathematical
proof of the natural-language resolution rules.

One genuinely supported live structure exists: **top-level non-negative-risk binary
CTF complementary positions**. Any admissible nonnegative binary payout vector
summing to its positive denominator conserves an equal complete set's ideal payout.
Per-component collateral rounding lowers the arbitrary fractional-split bound by
at most one six-decimal base unit. Settlement uses integer numerator/denominator
arithmetic rather than an approximate recurring Decimal fraction.

The original depth scanner now requires fresh structural and fee evidence for live
markets. It computes both legs through actual ask depth, modeled quantity precision,
conservative minimum notional, market-specific fees, required capital and all supported
terminal outcomes. Each evaluation, including rejection, exposes a structured proof.
The virtual venue independently checks fees and evidence again at execution.
Unknown fees cannot default to verified zero; maker rebates cannot become income.

`VERIFIED_STRUCTURE` means the supported position relationship is established under
the stated chain/contract assumptions. `VERIFIED_MATHEMATICAL` means positive minimum
modeled complete-position profit meeting the configured edge threshold under explicit
acquisition, collateral/parity and operational-cost assumptions. Neither label proves
execution, natural-language interpretation, fiat value or unconditional profit.
Gas, financing and collateral conversion costs remain unresolved, explicitly visible
in the calculation rather than invented. Full definition and official research links:
[Economic attestation](ECONOMIC_ATTESTATION.md).

### Persistent broker, independent risk and accounting

The lifecycle service evaluates observations automatically and logs accepted and
rejected decisions. Synthetic, historical and live-shadow modes preserve distinct
provenance. Historical replay advances by receipt time, presents no future book,
and retains actions beyond dataset end without inventing fills.

Approved positions reserve a shared cash envelope before either leg submits. The
existing `BinaryStrategy`, independent `risk.assess`, `Exchange` and `reconcile` are
reused, avoiding a second execution or risk engine. Each position retains strategy,
execution configuration, decision, journal, independent order actions and hypothetical
fill status. Three presets plus configurable seeded fixed/uniform latency, liquidity,
acknowledgment delay and adverse ticks expose execution dependence. Repeated snapshots
cannot replenish already consumed modeled liquidity.

The default account has **100 virtual USD/pUSD**, with no asserted SEK conversion.
Paper allocation limits default to 20 per trade, 80 total, 20 per market and 40 per
event. Hard limits cover capital, exposure, unmatched legs, daily/cumulative loss,
drawdown, freshness, edge, slippage and concurrent positions. Actual account state
feeds the risk engine; strategy output cannot override it.

Accounting derives available cash, reserved envelopes, locked basis, open orders,
partial inventory, gross/unmatched exposure, fees, proceeds, realized/unrealized P&L,
equity, utilization and drawdown from financial events. Fresh observed bids provide
explicitly hypothetical marks. Pause, future execution-model selection and emergency
stop are functional; stop survives restart. Finalized CTF payout ingestion can credit
modeled settlement internally, but its resolved path has fixture coverage only.
No exchange redemption is performed.

### Durability

Alembic revision 002 adds financial accounts and immutable events. SQLite now follows
versioned migrations, adopts only the recognized legacy records schema, uses WAL,
FULL synchronous writes and bounded lock waits. Financial history is excluded from
observation retention. The account checkpoint and its journal event commit atomically
through revision compare-and-swap and unique event constraints. State is published
after commit; identical events are idempotent, conflicting reuse fails closed.

Startup independently replays commands, checks contiguous revisions and chained
checksums, verifies journal facts, reconciles portfolios and compares the checkpoint.
Pending leg/order identities survive termination. Duplicate financial checkpoint
entries are rejected rather than silently discarded. Inconsistent snapshots, journal
corruption and concurrent-writer conflicts halt admission. Physical exit tests verify
before/after SQL commit and recovery with a partial active position.

### Laboratory, analytics and dashboard

The **43 original scenarios** remain; the new lab has **15 fault choices**, seeded
production-state-machine execution, persistent experiment history, full inputs/event
timeline, portfolio evolution, version/config/dataset hashes, reproducibility artifacts
and three-model differential comparisons. Tests include malformed/conflicting metadata,
stale evidence, fee changes, pauses, withdrawal, lost/delayed/out-of-order acknowledgments,
restart, duplicate events, settlement delay and reconciliation faults. Physical process
termination is separately exercised through integration tests.

The dashboard preserves its visual identity and adds Paper Trading as a ninth view.
Mission Control and Paper Trading use the actual persistent account; scanner inspection
shows structural evidence, fees and full proof; protocol/rejection filters work.
Users can inspect orders, financial events and complete decisions, including paginated
older decisions, control the paper lifecycle and download experiment artifacts.
Simulation Lab adds parameter editing and model comparison. Analytics separates
observation samples, supported structures, depth capacity, hypothetical fills, completed
virtual positions and modeled settlement. Opportunity lifetime is a polling lower bound;
open episodes are censored. Zero-trade periods remain visible. Real profit is absent.
Telemetry exposes actual feed/data/queue/database/recovery/processing statistics and
process CPU/peak RSS. Invalid streaming books now produce DEGRADED health even when
the socket remains connected.

## Verified public integrations and explicit support matrix

The controlled direct probe used two currently active markets at capture time. A
separate service probe ran real startup, public streaming and persistent decisions.
Retained evidence covers **four distinct CTF conditions**: main probe 4024677/4024680,
final service probe 4024681/4024677, and earlier raw fixture 4061337. That is **one
verified market structure**, not four protocols. Captures expire and are replayed at
their original clock in tests.

| Capability | CTF v1 | Protocol V2 |
| --- | --- | --- |
| Gamma discovery | Genuine public responses | Controlled query returned none; unverified |
| Outcome identifiers | Finalized deployed helpers match Gamma IDs | Fixture routing only |
| CLOB books | Genuine instrument-specific public reads | Fixture routing only |
| Fee metadata | Gamma schedule cross-checked with compact CLOB details | Not live verified |
| Public streaming | Actual CTF snapshot and PONG; short service connection | Not live verified |
| Economic attestation | Supported complete binary singleton pair | Explicitly unsupported |
| Simulator compatibility | Production venue and recorded-fixture journey tested | Synthetic routing fixtures only |
| Resolved payouts | Implemented finalized reads; resolved path fixture-tested | Unsupported |

Official current API/SDK documentation and OpenAPI were reviewed. Unified SDK public
capabilities and `polymarket-client>=0.12.0` support were researched; Midas retains its
narrow GET transport instead of importing trading capabilities. Instrument routing,
compact CLOB metadata and documented Gamma `secondsDelay`/CLOB `itode` are used where
established. The V2 empty result is a limitation of this bounded probe, not a claim
that no V2 markets exist. Negative and augmented negative risk remain unsupported.

## Demonstrated outcomes and test evidence

The final suite reports **162 Python tests passed, one PostgreSQL test skipped; two
frontend tests and two browser tests passed**. Ruff, formatting, strict mypy, TypeScript,
frontend lint/build, replay and Compose configuration checks passed. No existing test
or scenario was removed. CI coverage was extended; configuring CI is not a claim
that hosted jobs have already passed. Exact commands, warnings, references and all
three required demonstrations are in [Test report](MILESTONE_2_TEST_REPORT.md).

1. **Verified observation:** two direct public CTF evaluations had verified structures
   but negative modeled edges; both were rejected. The final streamed service snapshot
   had unsequenced invalid books and honestly reported DEGRADED, with zero trades.
2. **Paper operation:** actual SQL-backed service admission works; the local default
   standard synthetic account recorded two hypothetical fills and 7.60 locked capital.
   The identical synthetic differential fixture settled at 0.50 optimistic, 0.40
   standard and zero conservative virtual P&L. These figures do not imply live profit.
3. **Failure/recovery:** abrupt partial-fill termination recovered 90.50 available,
   5.30 reserved and 4.20 locked; finishing and explicit synthetic settlement produced
   exactly two fills, 100.50 cash and 0.50 virtual P&L, unchanged after another restart.
   All recorded reconciliation checks were clean.

Local critical-path measurements cover 30 durable rejected-observation transitions:
24.765 ms median, 47.679 ms empirical p95; 347.022 ms journal replay/reconciliation
at revision 32. These measurements are bounded local evidence, not a trading-speed
or capacity claim. The original running SQLite database was integrity-backed up,
migrated to 002 and restarted successfully; its existing observation records remain.

## Unresolved limitations and scope reductions

- Exact oracle adapter identity and natural-language human rule review remain unresolved.
  Structural algebra covers admissible binary payout vectors but does not establish
  collateral parity/value, dispute timing or additional operating costs.
- Live V2, negative/augmented risk and combinatorial structures stay unsupported.
  Public streaming testing is short; sustained reconnect/load coverage is fixture-based.
  Frequent unsequenced updates intentionally invalidate executable status until a REST
  confirmation. Discovery is bounded rather than exhaustive.
- Observed depth cannot establish real fill probability. No empirical queue model,
  sell/unwind strategy, passive-maker execution, automatic unmatched-leg rescue or
  measured latency calibration exists. Conservatively retained consumed depth can
  undertrade. Live settlement was not observed during the active sample.
- Docker daemon access is denied; no local PostgreSQL server exists. SQLite financial
  durability is exercised; PostgreSQL behavior remains a configured integration check
  to run independently. No unsafe permission bypass or privilege escalation occurred.
- Single-process startup/migration ownership is assumed. CAS prevents lost writes,
  but provides no distributed leader election. Full journal replay grows with history;
  compaction and future cross-version replay are deferred. JSONL is separate from the
  durable financial ledger and does not promise fsync.
- Specialized exposure/return/drawdown charts, a new interactive portfolio cursor,
  latency sweeps, distribution summaries, multiple dataset experiment selection and
  human rule-review workflow are deferred. New lab timelines and analytics drill-down
  are inspectable structured output; the legacy interactive timeline remains intact.
  These are explicit reductions made to prioritize proof and accounting correctness.

The 20 core acceptance checks have implementation/test evidence with the stated
protocol/runtime limits. Broader UI and analytics requirements above are only partially
implemented; this milestone is a strengthened working laboratory, not a claim of full
economic feasibility or production deployment readiness. Comprehensive operational
constraints: [Known limitations](KNOWN_LIMITATIONS.md).

## Recommended next improvements

1. Establish collateral adapter/parity and exact oracle provenance, then record long
   public-data periods to measure candidate frequency, lifetime and capital lockup.
2. Run PostgreSQL integration/recovery checks in an accessible environment; extend
   sustained streaming/resynchronization verification before broadening market sampling.
3. Obtain genuine supported V2 samples before enabling their economics. Preserve the
   fail-closed boundary until identity, collateral, fees and payout structure are proven.
4. Calibrate execution models from public observations without asserting fill certainty;
   add a documented unmatched-leg handling strategy and broader recorded datasets.
5. Add verifiable journal compaction/version migration, then specialized UI charts and
   dataset/latency experiment comparisons based solely on recorded results.

Implementation references: [Architecture](ARCHITECTURE.md), [Risk model](RISK_MODEL.md),
[Simulation design](SIMULATION_DESIGN.md), [Paper broker](PAPER_BROKER.md),
[Execution models](EXECUTION_MODELS.md), [Recovery](RECOVERY_AND_RECONCILIATION.md).
