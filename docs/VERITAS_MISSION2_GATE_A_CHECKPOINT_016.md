# Gate A checkpoint 016 — stream cross-check and scan 18 qualification

**Captured:** 2026-10-15 12:48 UTC
**Branch:** `project/veritas`
**Checkpoint base:** `cadf1a8`

## Second REST capture and public stream cross-check

A second bounded CLOB `/books` request at 12:38:15.890 UTC returned all 14
Yes/No books in 57 ms. Its books still failed the source-age and cross-book
skew limits: 95,353 ms maximum age and 90,247 ms skew against 5,000 ms and
250 ms bounds. The displayed basket arithmetic matched the first capture:
the Yes top ask costs $1.000 against its conditional $1 payout, while the No
top ask costs $6.035 against a six-share protocol payout floor. No tested
quantity from 5 to 100 shares per outcome had positive gross or fee-safe net
edge. The replayable REST artifact is
`data/veritas-observatory/structure-studies/1792067895890897143-openai-ipo-basket-study.json`;
its file SHA256 is
`f712a9b2914ca22fc0b71ace4f78f40c7cf947de9e946d8d05e1d236bbffc5ab` and its
embedded artifact SHA256 is
`053b11c30356b29cb022f7b018a15915f2a4dea85043b8cb9ed4dc5d26da740f`.

The official public market WebSocket stream at
`wss://ws-subscriptions-clob.polymarket.com/ws/market` delivered all 14 books
in one 33,630-byte frame over 84 ms. All 14 WebSocket book timestamps are
newer than their REST-refresh counterparts, but the stream capture still fails
the same freshness gate:
17,781 ms maximum source age and 11,977 ms cross-book skew. The official
[market data documentation](https://docs.polymarket.com/market-data/realtime-data)
describes book timestamps and content but provides no per-book sequence field
for this stream. The capture itself contains no sequence field. This is a
cross-channel check of book content, not proof of gap-free sequence or source
freshness.

Across the 14 matched token IDs, REST and WebSocket best bids, best asks, and
last-trade prices match exactly. Full displayed bid depth matches for 6/14
tokens and ask depth for 6/14; the remaining levels changed between the
captures, which were about six minutes apart. The captured top-of-book
economics remain unchanged: Yes gross is $0.000 at 5 shares, -$0.01344 at 20,
and -$0.305 at 100; No gross is -$0.175, -$0.700, and -$3.500. Fee-safe net
remains negative at every tested size. No candidate qualifies, and no order or
authenticated request was made.

The WebSocket artifact is
`data/veritas-observatory/structure-studies/1792068256146934167-openai-ipo-market-stream.json`
(file SHA256
`dc56f342f43b4b04b64156c8d57e49890dabff48747d90f2b526108fa65206e4`; embedded
artifact SHA256
`e48110ef0be269aae364fd34589f8fe792e0924c2cf0e8bd6a8a1625c8757ad7`). Its
analysis SHA256 is
`a7f121e6f88fb004e2741273469fa342c9e9c797d6968878186ed9122b78d9d6`. Replay
validates the capture digest, the referenced REST artifact and complete token
set, then re-computes every quality and economic field:

```sh
PYTHONPATH=packages python3 scripts/veritas_openai_ipo_basket_study.py \
  --replay-market-stream data/veritas-observatory/structure-studies/1792068256146934167-openai-ipo-market-stream.json
```

The runner binds NegRisk and minimum-size constraints omitted by the stream
book event to the digest-verified Gamma metadata in the referenced REST study.
It uses the stream's own market, asset, timestamp, tick, bid, and ask fields for
the book audit. Replay completed with 14/14 books and reproduced the stored
basket arithmetic and quality failures.

## Prospective scan and Director qualification

Scan 18 remains the 12:31:14 UTC finalized snapshot
`scan-20261015T123114Z-ded26b5ea023`. The bounded panel has 18 snapshots, 720
selected observations, 645 quality-valid pairs, 75 invalid pairs, and 304
distinct markets. The five economic gates remain zero-positive. Its
12:45:13 UTC Director cycle admitted job
`job-3c739889ee5846dd80f284b8`; the Arena job completed at 12:45:53 UTC after
validating all 18 events. Finding
`veritas-qualification-v1-c6d40523cb31a232` reports zero positive states at
every gate across 645 valid pairs and keeps the no-trade recommendation. The
job took 0.929 seconds and used the pinned source revision
`e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd`.

At checkpoint capture, the Arena job JSON and finding are complete, while the
Director manifest still shows the admitted job as queued and scan 17 as its
last qualified scan. The next scheduled Director cycle is 13:15 UTC; no
manual poll or retry was started. Keep this projection lag visible until that
scheduled cycle reconciles it. Detailed lineage is in [Gate F checkpoint
006](VERITAS_MISSION2_GATE_F_CHECKPOINT_006.md).

## Finalized-source replay and continuation

The 12:40 UTC bounded source replay published its summary at 12:43:27 UTC. It
processed 1,548 of 3,373 cataloged finalized segments (351,662,824 bytes),
leaving 1,825 segments / 487,084,989 bytes pending through ordinal 183,006.
The processed prefix contains 4,078 campaign-window frame records, including
2,779 touched market-frame states and 2,739 quality-valid states; positive
top-ask and full-depth states remain zero. The campaign window is incomplete
because finalized segments remain pending; readiness is
`catching_up_finalized_source`.
Summary SHA256 is
`15fb5a0364063e02b14c0bb435cb9538077557bb2125204b144c98cfa63f74d8`; file
SHA256 is
`71ad639e9241e98721c82ab30ba4dbd9633dbba74f988e43342aab221bfa9e5d`.

The observer, source-analysis, and Director timers remain active. Their next
scheduled UTC runs are 13:00:57, 13:10:42, and 13:15:27, respectively. Mission
2 remains active. Continue the bounded sample and the source-prefix replay;
retain the stale-source findings, the independent-sequence gap, and the
unchanged zero-exposure baseline.

Current tracked state and runtime hashes are summarized in [research
inventory 019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [engineering](VERITAS_MISSION2_ENGINEERING.md).
