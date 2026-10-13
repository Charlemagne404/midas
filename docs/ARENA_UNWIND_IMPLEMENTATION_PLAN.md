# Bounded sell/unwind implementation plan

Status: exchange/broker foundation, observable residual-only policy, typed jobs,
matched study producer, independent verifier, export and dashboard implemented.
Production study remains gated behind the next full regression. The campaign
will preserve its source while testing and running the fixed preregistration.

## Scope and decision contract

Extend the actual simulated exchange and independent accounting audit with
inventory-backed selling. Then add a research runner comparing hold, existing
missing-leg buying, and at most one residual sell attempt after initial orders
are acknowledged terminal. Use observed bids and known inventory only. No
shorting, external collateral, assumed fills, hindsight pricing or settlement
outcomes in decisions. Preserve matched complete sets: sale quantity cannot
exceed the excess leg's quantity minus the other leg's quantity.

Emergency stop and existing loss cutoffs remain admission gates. A residual
quantity exception must be explicit and prove the requested action reduces
existing exposure; it must not grant admission to a new arbitrage position.
Book identity, source, freshness, minimum quantity/notional, tick size, market
eligibility and fee evidence remain independently validated at submit/match.

## Inventory and ledger arithmetic

For an asset with owned quantity Q and remaining cost basis C, a fill selling
q shares at observed simulated bid p has gross proceeds floor(q*p, 1e-6).
Use the existing declared fee curve and fee rounding as a synthetic assumption;
net proceeds equal gross proceeds minus independently calculated sell fees.
Reject a fill whose net proceeds are negative. Quantity is rounded down to the
existing 0.01-share grid. Selling never creates negative inventory.

Allocate basis b = floor(C*q/Q, 1e-6) for partial liquidation; when q == Q,
release all remaining C so rounding dust cannot survive a full close.
The sell ledger entry carries positive sold quantity and a distinct sell kind:

- available_delta = net proceeds;
- locked_delta = -b;
- reserved_delta = 0;
- inventory_delta = -q;
- realized P&L increment = net proceeds - b.

This releases cost basis, not spendable cash previously counted elsewhere.
Cash conservation is starting cash minus buy spend plus net sell proceeds plus
settlement proceeds. Remaining inventory settles once using its remaining
basis. Sell proceeds must remain distinct from settlement/redemption proceeds.

Reserve shares for outstanding sell orders separately from monetary collateral.
Multiple orders cannot reserve the same shares. Cancel, expiry, rejection and
partial execution release only their unused share reservation. In the bounded
runner, permit one attempt and block additional actions while it is pending.

## Execution and version compatibility

Match against bids from highest to lowest, consuming actual observed capacity.
Apply adverse ticks downward on sells, honor latency/processing/acknowledgment
timing, and preserve IOC/FAK/FOK semantics. FOK checks aggregate eligible bid
depth before any fill. A rejected request, missing book or vanished bid yields
no invented proceeds. Track venue-price consumption separately for bid and ask
sides so adjusted fill prices do not allow reuse of unchanged liquidity.

Use an explicit research opt-in and a versioned checkpoint extension. Original
buy-only orders/checkpoints retain their current serialization and behavior.
Do not add new default fields to every persistent paper account or rewrite the
protected Laboratory archive. Restore old checkpoints, and independently test
buy-only result hashes before and after the extension. New sell-capable results
must identify the new runner/execution contract and source hash.

## Source locations requiring coordinated changes

- `simulation/exchange.py`: order side, share reservations, sell matching,
  per-asset remaining basis, ledger posting, serialization and restore.
- `simulation/accounting.py`: independent sell fee/proceeds/basis checks,
  inventory reconstruction, cash conservation and order quantity conservation.
- `paper/broker.py`: scheduled sell submission/matching, daily realized losses,
  fee/fill counters and summary accounting. Current daily P&L counts settlement
  entries only; ignoring sell losses would create a risk-admission bug.
- `laboratory/runtime.py`: operating costs on sell fills, financing after basis
  release, redemption costs only on actual settlement, and terminal metrics.
- `arena/recovery.py` or a dedicated versioned runner: observable admission,
  matched hold/buy/sell controls, one-attempt scope, saved proposals and replay.
- `attribute_arena_losses.py`: retain meaningful decomposition with sold shares;
  its current audit assumes positive buy fills and terminal settlement only.

Current execution-cost target version two describes the initial buy position.
Do not reuse it as a sell-cost label or present its predictor as calibrated for
unwinds. A future sell-cost dataset needs a separate explicit target contract.

## Acceptance gates before a production study

1. Exact buy-only compatibility, old checkpoint reload and replay checks.
2. Partial/full sell ledger reconciliation, basis dust and rational settlement.
3. No oversell across multiple pending orders; no fabricated cash or shorting.
4. Cancel/expiry/acknowledgment replay and duplicate event idempotency.
5. Empty/stale/future/invalid bids, minimum/tick violations and FOK failure.
6. Stop/loss-limit rejection and residual-only admission with matched sets intact.
7. Sell fees, operating costs, financing and redemption accounting without
   duplicate charges or omitted realized sell losses.
8. Preserved initial-position ledgers across matched hold/buy/sell policies.
9. Preregister fresh seeds, fixed bounds and grouped uncertainty before running.
10. Independently verify saved ledgers, proposals and bundle payloads; report
    coverage and negative outcomes without assuming that selling improves P&L.
