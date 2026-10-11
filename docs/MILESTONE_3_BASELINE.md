# Milestone 3 baseline and economic reconciliation

Audited on 2026-10-11 against Milestone 2 reports and revision
`1afb4e9a41c6a03ae47f6d8fdfe6fd5905398497`. The initial independent rerun produced
162 Python passes, one PostgreSQL skip (21.65 seconds), two frontend passes and
two browser passes (7.6 seconds). No existing tests or the 43 original scenarios
were removed. PostgreSQL runtime and live V2 remain unverified.

The existing venue uses Decimal money, an insertion-ordered heap, reservation/fill/
release/settlement journal entries, and independently arriving legs. The broker uses
copy-on-write transitions, an independent risk gate, a shared capital envelope,
SQL journal/checkpoint commits, checksums and revision compare-and-swap. Existing
fault experiments and receipt-time replay are valuable foundations, but there was
no general campaign scheduler, validated dataset manifest, scenario shrinker or full
research workstation. Milestone 3 extends these implementations rather than replacing them.

A read-only integrity backup of the existing local SQLite account was replayed
with the new implementation in a temporary database: `paper-demo`, revision 1244
including the new recovery entry, healthy, exactly two hypothetical fills. The
original database was not changed by this compatibility check. New default execution
fields are omitted from serialization, preserving the old journal representation.

## Facts, assumptions and unresolved evidence

Current official documentation was reviewed on 2026-10-11. Documentary descriptions
are not new onchain verification of the retained captures.

| Topic | Established fact or implementation | Laboratory treatment |
| --- | --- | --- |
| Reservation | Midas transfers virtual available cash to reserved envelopes before independent legs | No second use of reserved funds; rejection/cancellation releases unused reservations |
| Complete set | Official docs describe equal binary outcomes converting through a separate merge operation and confirmation | Acquisition locks basis; no automatic merge or instant recycling of capital |
| Resolution/redemption | Resolution makes positions redeemable; redemption is a subsequent operation | A `settle` event means confirmed spendable simulated proceeds; omitting it leaves positions locked |
| Payout | Verified supported top-level CTF binary algebra; arbitrary eligible splits conserve a complete set subject to base-unit rounding | Existing integer terminal arithmetic plus independently implemented rational oracle |
| Collateral | Docs now describe pUSD backed by USDC, with six decimals and adapter/router-specific routes | Retained structural evidence checks USDC.e-derived CTF position IDs; adapter routing and collateral value are not thereby proven |
| Fees | Market-specific formula and five-decimal precision are documented | Retain original fee evidence/version; HALF_UP ties and modeled fragmentation are explicit simulator choices |
| Operating costs | Gas/relayer eligibility, infrastructure, conversion and financing costs are route-dependent | Configurable per-fill/redemption estimates, annual financing and collateral-value sensitivity; unknown does not become verified zero |
| Partial legs | Separate legs can execute differently | Keep unmatched inventory, loss outcomes and admission limits; no invented rescue or liquidation |

[Position management](https://docs.polymarket.com/trading/positions/manage) describes
merge and redemption as transactions whose confirmation precedes use of balances.
[Collateral documentation](https://docs.polymarket.com/concepts/pusd) establishes the
published pUSD design, not unconditional fiat parity or availability of a particular
adapter. [Resolution documentation](https://docs.polymarket.com/concepts/resolution)
describes dispute-dependent timing; the short synthetic settlement schedules are
explicit fixtures, not calibrated estimates of those timelines.
[Fee documentation](https://docs.polymarket.com/trading/fees) supplies reference vectors
and precision; [order lifecycle](https://docs.polymarket.com/concepts/order-lifecycle)
supplies public order semantics, not internal matching priority or hypothetical fill probability.

Every new Laboratory output has `economically_verified: false` and
`execution_certainty: HYPOTHETICAL_UNCALIBRATED`. The existing
`VERIFIED_MATHEMATICAL` scanner label retains its documented conditional algebraic
meaning for compatibility; it is not a claim of economically verified strategy returns.
Cost-adjusted research results are an analytical overlay, not a mutation of the
production virtual ledger or spendable account balances. Those costs do not yet
feed ongoing admission risk. This limitation is explicit in every run.
