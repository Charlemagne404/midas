# Economic attestation and proof

Version: `ctf-complement-2`. One live structure is supported: two top-level singleton
positions on Polygon CTF, index sets 1 and 2, parent collection zero, collateral
USDC.e at `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`, a prepared binary condition,
not negative risk and not already resolved at attestation time. Labels can name teams;
a title or the words Yes/No never establish complementarity.

`CTFVerifier` reads chain ID, finalized block identity, outcome slot count, payout
denominator, collection IDs and position IDs from the official deployed CTF address.
Both derived IDs must exactly match the protocol-selected Gamma instruments.
Attestations retain the actual RPC method/parameters/results, block hash, endpoint,
collateral, condition, instruments, metadata hash, rule hash, timestamps, source URLs,
method version, unresolved assumptions and invalidation conditions. Invalid RPC
responses, wrong IDs, missing rules, unknown versions and unsupported structures fail
closed. Freshness is checked again by scanner and virtual matcher. Metadata includes
resolution source, question ID and resolution status; changes invalidate the proof.

`VERIFIED_STRUCTURE` establishes protocol complementarity conditional on authentic
RPC state and correct CTF/collateral operation. Descriptive market rules and source
URLs remain descriptive evidence. We do not prove the meaning of natural-language
rules, human-review them, identify an exact adapter/oracle from a title, or promise
resolution time. The complete pair's algebra holds independently of which admissible
binary oracle vector is eventually reported. Exact oracle adapter identity remains
unresolved in the active sample. No attestation asserts otherwise.

For outcome numerators a,b with denominator a+b>0 and equal quantity q, the ideal
complete payout is q. CTF redemption floors each component at six collateral decimals;
the complete set's minimum is q−0.000001 collateral units for an arbitrary fractional
split. The payout matrix displays first outcome, second outcome, and fractional split
minimum separately. Settlement uses integer numerator/denominator arithmetic per asset;
Decimal approximations of repeating fractions do not determine financial credits.

`VERIFIED_MATHEMATICAL` is a different property: positive minimum modeled complete-position
profit meeting the edge threshold, after ask-depth acquisition, modeled precision,
minimums, fees and terminal rounding, with valid structural/fee evidence. It is explicitly
conditional on acquiring every proposed share, collateral retaining value, modeled
pUSD/USDC.e parity and zero unmodeled operational costs. It does not verify execution,
fiat value, gas, financing, adapter conversion economics or natural-language rules.
Every rejection also has an `economic_proof` object explaining the failed gate.

Fees use market-specific Gamma parameters, cross-checked against public CLOB `fd`
metadata for monitored eligible live markets. Only documented exponent-one taker
schedules are supported. Missing or stale schedules fail closed; explicit fee-free
Gamma metadata is distinguishable from an unknown rate. Makers pay zero under the
supported documented schedule; rebates are never booked as income. Nearest five-decimal
rounding has quantum 0.00001; sub-threshold fees round to zero. Independent reference
cases include 100 shares at 0.5: 1.75 at rate 0.07, 1.25 at 0.05; 100 shares at 0.1
and 0.9: 0.36 at rate 0.04.

For arbitrary live maker fragmentation, rounded(x) ≤ 2x for x≥0. Summing twice the raw
slice fees gives a conservative bound without asserting a minimum live match size.
Synthetic legacy scenarios preserve their original explicit 0.01-share fragmentation
reserve. Quantity steps of 0.01 are a paper model choice. Minimum notional is enforced
conservatively using the cheapest ask, which also exceeds an equivalent share minimum.
Actual exchange precision and maker amount rounding remain execution assumptions.

Evidence and fees expire after five minutes; book age has a separate default 15-second
limit. Net profit can be negative for a structurally verified market. An unchanged title
cannot preserve an attestation after changed economic metadata.

Research reviewed on 2026-10-11:

- [Market identifiers, fees and constraints](https://docs.polymarket.com/market-data/market-details)
- [Position economics](https://docs.polymarket.com/concepts/positions-tokens)
- [Resolution and exceptional split outcomes](https://docs.polymarket.com/concepts/resolution)
- [Negative risk](https://docs.polymarket.com/concepts/negative-risk)
- [Fee formula and examples](https://docs.polymarket.com/trading/fees)
- [Order lifecycle and taker delays](https://docs.polymarket.com/concepts/order-lifecycle)
- [CTF identifier helpers and V2 encoding](https://docs.polymarket.com/resources/onchain-position-data)
- [Official contracts](https://docs.polymarket.com/resources/contracts)
- [CLOB OpenAPI](https://docs.polymarket.com/api-spec/clob-openapi.yaml)
- [Unified Python SDK](https://docs.polymarket.com/getting-started/python), [V2 SDK migration](https://docs.polymarket.com/migrate/polymarket-v2/sdk-integrations)

The unified SDK exposes `AsyncPublicClient` and protocol-selected outcome identifiers;
V2 migration documents `polymarket-client>=0.12.0`. Its current [market model](https://github.com/Polymarket/py-sdk/blob/main/src/polymarket/models/gamma/market.py)
confirms `secondsDelay`. Midas continues its narrower read transport rather than importing
secure trading capabilities. It reads `/book?token_id=...` for selected instruments and
`/clob-markets/{condition_id}` for fees and documented `itode` delay; Gamma `secondsDelay`
is the supported seconds delay. Protocol V2 is recognized but live economics remain
unsupported because no V2 market was returned in the controlled public probe.
