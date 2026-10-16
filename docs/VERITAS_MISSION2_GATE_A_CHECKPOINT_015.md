# Gate A checkpoint 015 — independent NegRisk group and scan 18

**Captured:** 2026-10-15 12:31 UTC (scan); basket books captured 12:27 UTC
**Branch:** `project/veritas`
**Checkpoint base:** `a01b507`

## A second complete outcome group

The bounded structure study examined the OpenAI IPO market-cap group
`0xd2c21cbb9d2cb407ab3dcf619d93f6d65b7967154cd6ee930f7758baa2b4bf00`.
Direct Gamma reads identified markets 608362–608368. Their question IDs share
the group prefix and carry consecutive final-byte indices 0–6. A public Polygon
`eth_call` to the adapter's `getQuestionCount(bytes32)` at block 95,574,561
returned seven. This gives two independent membership checks: a complete
sequential index set and the adapter's count. The Gamma group-filter query
returned 20 unrelated records and no matching group members, so the study uses
the direct market responses and the on-chain count instead of that filter.

The shared rules describe six exhaustive market-cap ranges: below $500B,
$500B–$750B, $750B–$1T, $1T–$1.25T, $1.25T–$1.5T, and $1.5T or higher. Exact
bracket boundaries resolve to the higher bracket. A seventh outcome covers no
IPO by December 31, 2026. The first six intervals are contiguous, with no gap
or overlap. The primary references are Polymarket's [Gamma API
documentation](https://gamma-api.polymarket.com/docs), the NegRisk adapter's
[MarketDataManager documentation](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/docs/MarketDataManager.md),
[MarketDataManager source](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/src/modules/MarketDataManager.sol),
[NegRiskAdapter documentation](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/docs/NegRiskAdapter.md),
and [deployed address list](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/addresses.json).
The source exposes `getQuestionCount(bytes32)` and derives each question index
from the final byte. The adapter documentation says at most one question can
resolve true, while all-false remains possible; that supports a six-share
minimum No-basket payout for seven outcomes.

The seven Gamma market bodies, failed group-filter response, adapter address
source, and Polygon RPC reads are preserved in the membership evidence. The
membership probe SHA256 is
`ee6d5ea4360d7d44c2918a639ff1cd3c445ce279684f0a65e86545eef40ff765`; its raw
source archive SHA256 is
`40089f009f74df2e301d2cdd383e378fd81863e6ebebfda50937b1a4a7de8e13`.

## Complete-book economics and quality

One unauthenticated CLOB `/books` request returned all 14 Yes/No token books in
100 ms (33,042 response bytes). Every outcome had displayed depth for 5, 20,
and 100 shares, and all legs met the five-share minimum. The books did not pass
the freshness gate: the oldest source timestamp was 33,546 ms old and the
cross-book timestamp skew was 20,962 ms, against limits of 5,000 ms and 250 ms.
Every result below is therefore descriptive and cannot qualify a candidate.

The Yes basket pays one share only if exactly one outcome resolves Yes. The
protocol alone permits at most one Yes and does not guarantee one. The No
basket has a protocol minimum of six payout shares per set if at most one of
the seven outcomes resolves Yes. No order or authenticated request was made;
actual fills remain unknown.

| Basket | Best-ask cost per set | Assumed minimum payout | Top-of-book gross edge |
| --- | ---: | ---: | ---: |
| Yes | $1.000 | $1.000, conditional on exactly one Yes | $0.000 |
| No | $6.035 | $6.000 under the at-most-one-Yes rule | -$0.035 |

| Shares per outcome | Yes gross | Yes fee-safe net | No gross | No fee-safe net |
| ---: | ---: | ---: | ---: | ---: |
| 5 | $0.00000 | -$0.03356 | -$0.17500 | -$0.20301 |
| 20 | -$0.01344 | -$0.14861 | -$0.70000 | -$0.81201 |
| 100 | -$0.30500 | -$0.99938 | -$3.50000 | -$4.05988 |

The fee-safe net uses the existing fragmentation-safe upper fee envelope and
the captured taker fee schedule. The unchanged no-position baseline is $0
exposure and $0 P&L; neither basket beats it on the displayed arithmetic, even
before applying the stale-source disqualification. There are zero qualified
positive basket candidates.

The sealed study artifact is
`data/veritas-observatory/structure-studies/1792067234767876259-openai-ipo-basket-study.json`
(276,056 bytes; file SHA256
`1d8f30c59d28e20c46f35acc8a1004e6ebbef5ac63592d150972530928828506`). Its
embedded artifact SHA256 is
`ac25dce74644181f6c39c99f6a091c8ff219b5bd7a92fc0b154beb0a097157fd`; the
replayed result SHA256 is
`f62224d516665762a8ef9b04872d70612a32beacd7a6fa9d65a9a82fd3c8de44`. The
source book response SHA256 is
`f73e6f7c033f383f72cbf0a1d33b5065c278de18ae2bdae1e5c4522bb1066a15`.
Replay it with:

```sh
PYTHONPATH=packages python3 scripts/veritas_openai_ipo_basket_study.py \
  --replay data/veritas-observatory/structure-studies/1792067234767876259-openai-ipo-basket-study.json
```

The runner validates the embedded source hashes, sequential question indices,
on-chain count, range partition, complete token set, source timestamps, depth,
and fee envelope before confirming the stored result digest. A later bounded
capture can use `--fetch-public`; it makes one public CLOB request against this
same pinned member set.

## Prospective discovery continued

The 12:31:14 UTC scheduled scan,
`scan-20261015T123114Z-ded26b5ea023`, added the 18th finalized snapshot. Its
300 bounded query rows contained 293 unique market IDs, 84 eligible
same-condition V1 binary pairs, and 209 explicit exclusions (146 augmented
NegRisk records and 63 unsupported outcome relationships). The 40-market
sample contained 37 rotating markets and three available frozen controls. The
selection was stratified across liquidity (8 high, 2 medium, 30 low), expiry
(24 near, 10 medium, 6 long), and spread (10 tight, 12 medium, 18 wide).
Thirty-two pairs passed the current quality gate; eight had an empty ask side.
All five economic qualification counts remain zero-positive.

Cumulative v4 analysis covers 18 snapshots, 720 selected observations, 645
quality-valid pairs, 75 invalid pairs, and 304 distinct markets. The prior
reported-age/skew rule accepts 153/720; the paired difference is 492 pairs
(68.33 percentage points). The top-pair edge range remains -$0.984 to -$0.001
per share. These are selected intermittent observations; request-to-receipt
timing still does not establish source sequence, batch atomicity, or queue age.

Snapshot evidence SHA256 is
`ded26b5ea0238e39fe6648dd7b830702835f5191cbef96e28010ca7f75d8a337`; compressed
file SHA256 is
`92426ac19ef2b1a586c45d4e4b55be0cb0dd384cbe0c8b467e0449ef7e9753c1` and the
v4 analysis event SHA256 is
`e8135eea4dbe3122f122f1087a328db7fee8ef3715c0f72310277c3a396dcce0`. The
12:45 Director cycle has not yet qualified this scan. Current operations and
inventory details are in [research inventory
018](VERITAS_MISSION2_RESEARCH_INVENTORY_018.json) and
[operations](VERITAS_MISSION2_OPERATIONS.md). Mission 2 remains active.
