# Persistent autonomous paper broker

`apps/api/paper.py` owns durability; `midas.paper.broker` owns a deterministic state
machine. Neither paper strategy nor virtual matcher can access a public exchange
mutation client. The existing `BinaryStrategy`, independent `risk.assess`, `Exchange`
and `reconcile` are reused.

Startup migrates the database, replays the financial journal, reconciles snapshots,
restores cash/inventory/orders/pending actions and stop state, then starts the broker.
Each feed refresh records observations, evaluates markets against shared account cash,
logs the full decision and independently approves or rejects it. Approved positions
receive a cash envelope immediately, before either leg submits. Pending submit/match/ack
operations are durable and processed by a separate lifecycle task. No approvals can
spend the same reserved envelope. Risk uses actual holdings and event exposures.

Default account: **100 virtual USD/pUSD**, intended as a small research bankroll.
This is not an asserted SEK conversion. No SEK display or exchange-rate claim exists.
`MIDAS_PAPER_CAPITAL` controls new-account capital; existing capital cannot be reset by
changing an environment variable. `MIDAS_PAPER_LIMITS` accepts a JSON Limits object.
Paper defaults allocate at most 20 per trade, 80 total, 20 per market and 40 per event.
Loss, unmatched leg, freshness, edge, slippage, drawdown and position constraints are
independent hard gates. Starting capital and financial units are in every artifact.

Modes:

| Mode | Source and execution |
| --- | --- |
| synthetic | Default demo, controlled fixture observations; virtual fills; explicit modeled outcome injection |
| historical | `scripts/paper_replay.py`, genuine recorded LIVE provenance, receipt clock, no future book access |
| live_shadow | `MIDAS_MODE=live`, public Gamma/CLOB/market stream and Polygon structural reads; all orders internal |

Separate `paper-demo` and `paper-live` accounts prevent contamination. Historical
accounts use a separate name/database. Gamma discovery reads up to 100 liquid markets,
prioritizes eligible non-negative-risk CTF markets and monitors the configured bounded
subset. Unknown economics stay unsupported. Legacy recordings without an attestation
cannot receive a new retrospective proof; they produce rejected observations.

Recorded replay applies arrivals before due actions at the same receipt clock. It
retains pending actions beyond dataset end rather than creating future liquidity or
settlement. Use an actual recorded file from live operation:

```bash
.venv/bin/python scripts/paper_replay.py data/recordings/live-2026-10-11.jsonl \
  --db sqlite+aiosqlite:///data/historical-paper.db --capital 100 --model conservative
```

The matcher checks freshness again, treats legs independently and consumes observed
liquidity. A conservative consumed-depth budget persists across observations; repeated
snapshots do not replenish virtual inventory. This can understate true replenishment.
Open market positions block reuse. Marks use fresh observed bids; they are hypothetical
liquidation values. Cash, reserved envelopes, locked cost basis, fees, realized/unrealized
P&L, equity, exposure, drawdown, utilization and order status are journal-derived.

Finalized CTF payout reads can credit modeled live/historical settlement through the
internal ledger; nothing is redeemed onchain. This path is fixture-tested; the active
live sample did not settle during verification. Synthetic outcomes must be explicit.

API: `GET /api/paper`, `/api/paper/journal`, `/api/paper/decisions`; `PATCH /api/paper`
with `paused` or `execution_model`. Journal and decisions support `before_revision`
pagination. Pause blocks new decisions while already approved legs finish. Emergency
stop cancels pending actions/releases virtual reservations and survives restart.
`POST /api/paper/positions/{position_id}/settle` accepts a complete payout map only for
synthetic accounts. Live accounts reject manual outcome injection.

The dashboard's Paper Trading view exposes balances, orders, ledger timeline, assumptions,
full decisions, older decisions and controls. Hypothetical fill certainty is always
`HYPOTHETICAL_UNVERIFIED`; a displayed paper fill is not proof of a real transaction.
