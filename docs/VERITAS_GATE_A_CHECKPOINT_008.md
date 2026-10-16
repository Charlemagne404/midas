# Veritas Gate A checkpoint 008 — economic units and opportunity capacity

Captured 2026-10-14 23:56 UTC. This checkpoint records the v2 hypothetical
economics repair, a corrected raw-funnel version, and an initial controlled
Gate B capacity sensitivity. It does not accept Gate A or Gate B.

## Protected-state check

- The Reality campaign remains `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`.
  Its plan SHA256 after the read-only analysis was
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The Reality recorder and shadow worker were active after analysis, each with
  `NRestarts=0`. The main and Reality worktrees were clean.
- The raw funnel read the cataloged finalized `.seg` files only. It did not read
  the active `.open` segment or write to the Reality worktree. No order was
  submitted, and no wallet or trading credential was used.

## Independent economics review and v2 repair

An independent review of the first Veritas engine found three unit and
accounting gaps:

1. It compared the reported minimum order size against share quantity. Current
   Polymarket market details define `minimumOrderSize` as USDC notional per
   order.
2. It fixed the fee curve at exponent one, even though the market fee schedule
   carries a price-component exponent.
3. It treated buy fees as extra cash and retained the gross winning-share
   quantity. Polymarket describes taker fees in USDC, collected in shares on
   buys; v2 translates the rounded USDC fee to a share-equivalent deduction at
   that fill price and applies it to each possible winning outcome.

The v2 engine uses the per-market exponent, accepts per-leg fee and minimum
metadata, checks each walked leg's USDC notional against its minimum, and keeps
buy-fee share deductions separate from cash acquisition costs. It reports
floor and half-up fee precision scenarios. Official documentation states five
decimal places but does not specify the direction, so the report does not
select one as observed behavior. Unknown match fragmentation retains a
conservative fee upper bound for those rounding modes. The v1 engine is not
rewritten; the Veritas implementation is versioned as
`veritas-economic-feasibility-v2`.

Sources: [official fee rules](https://docs.polymarket.com/trading/fees),
[official market detail fields](https://docs.polymarket.com/market-data/market-details),
[official fee collection description](https://help.polymarket.com/en/articles/13364471-maker-rebates-program),
and [Polymarket's v2 Python fee calculation](https://github.com/Polymarket/py-clob-client-v2/blob/main/py_clob_client_v2/fees.py).

## Raw opportunity funnel v2

The reproducible result is
[VERITAS_GATE_A_RAW_FUNNEL_002.json](VERITAS_GATE_A_RAW_FUNNEL_002.json). It
replayed a finalized source snapshot of 1,862 segments (435,886,391 bytes),
through ordinal 225,124, with 1,858 verified reconstruction checkpoints. The
captured source receipt interval covered about 2 hours 46 minutes of the
campaign; this is not a venue-wide or full-campaign sample.

- 35,892 campaign-period frame records touched 26,524 paired market-frame
  states. Of those states, 25,620 passed the recorded paired-book quality
  checks; 904 were invalid, chiefly empty ask sides (698) and independent book
  divergence (145).
- At the frozen five-share size, every quality-valid state had complete
  displayed depth. None had a positive best-ask pair edge or positive
  quantity-specific pre-fee full-depth edge. The maximum pre-fee edge was
  `-0.001` collateral units per share; the median was `-0.03`.
- Fee regime metadata was available for all 25,620 quality-valid states. No
  fee adjustment was needed to reject the observed nonpositive gross states.
- The prior v1 funnel's minimum-eligibility field compared shares to the USDC
  threshold. The new v2 funnel checks each leg's displayed USDC notional. The
  v1 artifact remains preserved and its minimum field is retired; the v2
  fixture proves that five shares can be above a five-share number while both
  orders remain below a `$5` USDC notional minimum.

This refreshed snapshot adds 6,119 quality-valid paired states to the prior
raw-funnel report and does not change the observed opportunity conclusion.
Repeated market-frame states are correlated observations, not independent
opportunities. The conclusion remains limited to this selected monitored panel
and its captured interval.

## Controlled Gate B capacity sensitivity

The deterministic generator is
[`scripts/veritas_economic_scenario_study.py`](../scripts/veritas_economic_scenario_study.py)
and its result is
[VERITAS_GATE_B_CAPACITY_001.json](VERITAS_GATE_B_CAPACITY_001.json). It uses a
synthetic V1 Yes/No order book, a `$5` minimum per leg, a 4% taker schedule,
explicit settlement and operating cost assumptions, a nine-point size grid,
13 hypothetical USDC budgets, and full/half displayed-depth scenarios.

In the synthetic full-depth case, quantity 100 has positive P&L in the
one-match-per-price-level half-up scenario, but the fragmentation-safe lower
bound is negative in both resolutions (`-0.78` USDC worst case). At quantity
200, the single-match outcome is nonpositive; at quantity 700 even the
no-fee upper P&L is negative because the deeper displayed asks cost more than
the binary payout. The discrete displayed-capacity frontier reaches 100 shares
at `$100`, 350 at `$500`, and 700 at `$750` or above. Under the half-depth
sensitivity it tops out at 350 shares. These are controlled accounting checks,
not measured opportunities or expected fills; no synthetic candidate is
promoted.

The exercise uses USDC directly and makes no SEK conversion. It excludes order
arrival, queue priority, impact, FX, and empirically supported operating costs.
Displayed liquidity remains a depth bound, not guaranteed executable
quantity.

## Verification and decision

- Economics, raw-funnel, and scenario-study tests: **24 passed**.
- Ruff check and format: passed.
- Strict mypy for `packages/midas/veritas`: passed.
- The controlled scenario demonstrates that a favorable single-match case can
  disappear under unknown fragmentation. It does not establish that such a
  quote existed in Reality data.
- No training job or prospective campaign was started. The frozen Reality
  policy and source are unchanged.

Current classification remains **insufficient independent evidence**. In the
captured Reality panel, the opportunity bottleneck is negative gross
complementary pricing, before fees, capital lockup, or execution uncertainty.
The synthetic model also shows that larger size can cross into negative gross
capacity. This evidence does not support threshold relaxation or strategy
promotion.

## Next work

1. Continue the per-outcome issue and process-start configuration audit from
   checkpoint 007; keep collector and campaign settings unchanged.
2. Inspect existing Research Director and campaign interfaces before designing
   a separate prospective sampling experiment with predeclared horizons.
3. Extend economic measurements only after the broader future panel produces
   a positive, quality-valid gross candidate; preserve fee, capacity, and
   incomplete-leg sensitivities as separate outputs.
