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
