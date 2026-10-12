# Independent virtual risk gate

`risk.assess` accepts a proposed evaluation, a portfolio risk state, configured limits and observation time. It returns an allowed flag and explicit reasons. It runs independently from the strategy's financial calculations and must be invoked by any strategy runner before admitting a virtual position.

| Default constraint | Limit |
| --- | --- |
| Capital per opportunity | 100 virtual USD |
| Overall virtual exposure | 500 virtual USD |
| Per-market exposure | 150 virtual USD |
| Overlapping event exposure | 200 virtual USD |
| Simultaneous positions | 10 |
| Maximum book age, both clocks | 15,000 ms |
| Minimum theoretical net edge | 0.001 (0.1%) |
| Maximum depth slippage | 0.05 (5%) |
| Maximum simulated drawdown | 0.10 (10%) |
| Existing unmatched inventory | Reject new risk until reconciled |
| Missing payout/fees/integrity | Reject |
| Emergency stop | Reject new proposals |

The venue independently prevents overspending, invalid quantity/tick orders, unverified fees/payout and execution while stopped or settled. Submission reserves collateral and fill settlement cannot exceed it. This provides a separate monetary constraint even after a strategy proposal has been authorized.

All milestone experiments are isolated portfolios. Existing correlated exposures are scenario input fixtures rather than an actual shared, continuously traded account. Risk assessment occurs for the complete proposed position; two preauthorized leg submissions then execute independently under venue checks. The current low-level Exchange class is an internal simulator primitive; future plugins must use a controlled runner/gateway, not call it directly. Enforcing that gateway against untrusted strategy code and managing a persistent multi-market paper portfolio are next-milestone work.

The dashboard emergency stop blocks new scenario runs and marks risk decisions rejected. It is process-local and resets on restart. Scenarios separately inject a stop during virtual execution. No real orders exist to cancel.

## Milestone 2 shared-account risk

The persistent paper broker supplies actual cash, reserved envelopes, locked basis,
market/event exposure, unmatched inventory, daily/cumulative simulated loss and drawdown
rather than an empty default state. It allocates an envelope before either leg submits
and uses a conservative limit/fee budget. No second signal can reuse that cash.

New independent limits: potential unmatched-leg capital, existing unmatched quantity,
daily loss and cumulative loss. The default paper preset is 100 virtual USD/pUSD:
20 per trade, 80 total, 20 market, 40 event, 10 positions, 15 s data age, 0.1% edge,
5% depth slippage, 10% drawdown, 5 daily loss and 10 cumulative loss. Existing unmatched
inventory freezes new positions by default. The potential leg capital cap defaults to
100 in the reusable risk contract; it is configurable and additional to allocation limits.
Both loss limits use negative net realized P&L in the relevant window; unrealized losses
also affect drawdown. Execution rechecks configured data age and attestation/fee expiry.

Emergency stop is durable, cancels pending virtual actions and releases unspent
reservations. Pause blocks new decisions while approved actions can finish. The low-level
matcher remains a simulation primitive, not an untrusted-plugin boundary. No strategy or
confidence score can override the independent gate. Paper accounts keep initial config;
new-account limits accept `MIDAS_PAPER_LIMITS` JSON.

## Arena enforcement semantics

Arena policies request actions through the production broker's independent
admission gate. A learned score cannot override it. The limits control admission
and allocation; a drawdown or daily-loss stop blocks subsequent risk after the
threshold is observed. It does not guarantee that an already admitted pair of
independent legs cannot lose more when one leg fails or prices move.

Reserved envelopes and the venue's ledger prevent virtual cash overspending.
They do not guarantee a profitable exit, completion of the missing leg, or an
upper bound on all analytical financing/redemption estimates. Those estimates
remain separate from spendable paper-broker balances. Arena currently supports
abstention and initial sizing; it has no hedge or unwind action.

The local paper ledger exposes fills when the simulator commits a match.
Order acknowledgment can be delayed independently. Delayed private fill reports
are not separately modeled, so portfolio visibility is an explicit hypothetical
assumption rather than an empirically calibrated account feed.
