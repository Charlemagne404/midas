# Binary complete-position mathematics

For two proved complementary instruments, acquire the **same** quantity q. In every eligible modeled outcome vector `(y, n)` with `y + n = B`, payout is `qB`. This also covers fractional binary split resolutions. B defaults to one collateral unit in synthetic contracts; live B is not attested.

At each sorted ask price `p_i`, consume `x_i = min(remaining, floor(level size, 0.01))` until q is acquired. Per-level size is conservatively floored to the synthetic venue's modeled match precision; raw depth is retained for inspection. This matching precision remains unverified for live execution. Each instrument must provide q shares. Aggregate available matching depth is the smaller side's total ask size. Actual acquisition notional is the sum of consumed quantities times their ask prices, conservatively rounded upward to six decimal collateral places per slice.

For a supported taker fee schedule, modeled raw slice fee is `x_i r p_i (1 − p_i)`. The evaluator ceilings each slice fee to 0.00001 and adds a fragmentation reserve of `2 × 100q × 0.00001` for a nonzero rate. The reserve assumes matches at least 0.01 shares in the synthetic exchange model. This assumption is **not verified for live matching**, which remains excluded by the payout gate. A future live fee bound needs actual matching precision/fragmentation evidence. Zero fees have zero reserve.

```
gross cost        = sum(rounded slice notionals)
modeled fees      = sum(ceiled slice fees) + fragmentation reserve
required capital  = gross cost + modeled fees
minimum payout    = q × B
gross profit      = minimum payout − gross cost
net profit        = minimum payout − required capital
gross edge        = gross profit / gross cost
net edge          = net profit / required capital
capital use       = required capital / available virtual capital
slippage          = (gross cost − q × sum(best asks)) / (q × sum(best asks))
```

All classification arithmetic is Decimal. Frontend numbers are formatted with JavaScript only for presentation; that does not determine eligibility.

## Size selection

Requested quantities round down to 0.01 shares; both instrument minimums must be met. Without an explicit requested quantity, evaluate the two books' cumulative depth breakpoints, the minimum quantity and the capital boundary. A binary search on integer hundredths locates the largest affordable quantity. Among these feasible candidates choose the highest modeled net profit, breaking ties toward smaller size.

This is breakpoint selection under a conservative rounding model, **not a proof of global optimization across every rounded subquantity**. It can intentionally select a smaller position than total available depth. Available depth and selected modeled quantity are separate fields. A future exact optimizer can enumerate rounding discontinuities if that yields measurable value.

## Verification gates

Unsupported protocol or negative-risk structure; inactive/closed market; non-distinct pair; missing book; wrong provenance or condition; invalid book; unknown tick; stale/missing/future timestamps; unestablished complementary payout; unknown fee schedule; insufficient depth; insufficient capital; and nonpositive edge all produce structured rejection reasons.

`VERIFIED_MATHEMATICAL` requires positive minimum modeled profit, a configured edge threshold, and all preceding model gates. `CANDIDATE` is positive modeled profit below that threshold. Neither label guarantees fills, atomic acquisition, redemption timing, fiat value or operational safety.

Risk decisions are separate. Simulated settlement proceeds and realized P&L are journal-derived and may differ substantially from the theoretical model, including losses from unmatched execution. Rewards, rebates, external hedges, financing costs, conversion/gas costs and real redemption are excluded. No actual arbitrage profitability is established by synthetic demonstrations.

## Milestone 2 live proof rules

Live top-level CTF pairs require deployed helper evidence rather than the former boolean
payout gate. Ideal fractional payouts sum to q, but independently floored base-unit
redemptions can lose one 0.000001 collateral quantum per complete pair; live minimum
payout is q−0.000001. First/second full-outcome payout remains q. Rational settlement
uses integer arithmetic, avoiding repeated-decimal division for credits.

Live fee bounds use twice raw fees per depth slice; nearest quantum rounding satisfies
rounded(x)≤2x, so arbitrary unknown fragmentation is bounded without asserting a live
minimum match size. Legacy synthetic fragmentation rules are retained. Live minima are
conservatively treated as notional; 0.01 quantity precision remains explicitly modeled.
Every evaluation includes a proof trace, evidence, costs, payout matrix, invalidation
conditions and unresolved assumptions. Gas/financing/conversion costs are unmodeled;
positive verification is conditional on their absence and collateral/pUSD parity,
not proof of realized or unconditional exchange profit.
