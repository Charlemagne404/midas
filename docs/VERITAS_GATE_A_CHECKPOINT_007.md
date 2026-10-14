# Veritas Gate A checkpoint 007 — resynchronization issues by market

Captured at 2026-10-14T23:41:53.195266Z. The machine-readable result is
[VERITAS_GATE_A_GAP_MARKET_001.json](VERITAS_GATE_A_GAP_MARKET_001.json). This
checkpoint maps normalized issue entries in recorded book-resynchronization gaps
to campaign market IDs and five-minute blocks. It is diagnostic only and does
not accept Gate A or a later development gate.

## Protected-state check

- The Reality campaign plan SHA256 remained
  aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5.
- The recorder and shadow worker were active before and after the replay, each
  with zero restarts.
- Replay input was limited to cataloged finalized source segments. The active
  .open segment, Reality journal, and campaign plan were not changed; no orders
  were submitted.

## Replay coverage and freshness

The bounded journal query selected 2,344 decisions at event sequence 27,362.
Every decision reproduced from the finalized source prefix with no mismatches,
and all 13,321 cited source references resolved. The replay verified 1,835
finalized segments (426,781,064 bytes), through ordinal 220,633, and 1,831
reconstruction checkpoints. The source manifest SHA256 was
d8a8522b09a71584bd8bc0c8661a9939dbb1deb1d823c7a5d579ab8c87e1e958.

Decision-to-frame input lag had a 41.991 ms median, 219.469 ms p95, and
248.866 ms maximum, within the frozen 250 ms bound. Maximum paired-book age had
a 10.054 s median, 51.785 s p95, and 62.407 s maximum. A total of 1,503 of
2,344 decisions (64.1%) exceeded the frozen five-second paired-book freshness
limit.

The replay observed 24,744 campaign-window paired-book update frames across 12
market IDs. There were 185 family-by-five-minute activity groups and 31
five-minute blocks containing a total of 152 book_resynchronization gaps.

## Gap issue entries by market

The 152 gap records contained 908 affected issue entries: 868 stale, 33
top_divergence, six advertised_top_pending, and one timestamp_regression. Every
entry mapped to a campaign market ID; none was unmatched. The same gap record
can list multiple markets, so the market-level gap counts below overlap. Across
all markets, they sum to 458 market-gap appearances, not 458 distinct gap
records.

| Market | Decisions | Over 5 s | Update frames | Gaps listing market issues | Issue entries |
| --- | ---: | ---: | ---: | ---: | --- |
| 4853873 | 10 | 5 (50.0%) | 30 | 0 | none |
| 4869262 | 9 | 5 (55.6%) | 37 | 0 | none |
| 559687 | 293 | 230 (78.5%) | 316 | 69 | stale 138 |
| 561251 | 293 | 223 (76.1%) | 309 | 69 | stale 138 |
| 562828 | 179 | 10 (5.6%) | 8,765 | 1 | timestamp_regression 1 |
| 5674900 | 293 | 230 (78.5%) | 380 | 90 | stale 174; top_divergence 4; advertised_top_pending 1 |
| 5674902 | 45 | 33 (73.3%) | 104 | 15 | stale 28; top_divergence 2 |
| 5674915 | 274 | 215 (78.5%) | 660 | 81 | stale 152; top_divergence 9 |
| 5675021 | 293 | 134 (45.7%) | 11,973 | 23 | stale 18; top_divergence 18; advertised_top_pending 5 |
| 665205 | 293 | 238 (81.2%) | 199 | 110 | stale 220 |
| 679026 | 293 | 158 (53.9%) | 1,228 | 0 | none |
| 679055 | 69 | 22 (31.9%) | 743 | 0 | none |

Five markets—559687, 561251, 665205, 5674900, and 5674915—account for
822 of 868 stale entries (94.7%). Their scheduled freshness violation rates
were between 76.1% and 81.2% in this snapshot. The highest stale-entry count
was 220 for market 665205; no single market accounts for most of the total.

The relationship is not complete. Market 679026 had a 53.9% scheduled
freshness violation rate but no issue entries in the captured gap maps. Market
5675021 had 11,973 update frames and a 45.7% violation rate, with stale and
top-divergence entries both present. Market 562828 had only one mapped
timestamp-regression entry and a 5.6% violation rate. These contrasts argue
against attributing all stale decisions to resynchronization issue labels.

## Collector context and limits

Read-only inspection of the active service command and deployment configuration
showed that the recorder currently loads deploy/reality.json, with stale_seconds
60, resync_seconds 300, and refresh_seconds 600. The collector code includes
stale and top_divergence among issue types that can break the current WebSocket
path. Campaign decision freshness is a separate, stricter five-second limit.
These current settings are context; this aggregate does not prove which
configuration applied to every historical source gap.

Each affected_assets map lists all books carrying an issue at that gap. It does
not identify which market or issue satisfied the reconnect trigger. A stale
label may reflect quiet market activity, a missing update on one outcome, or a
recording condition. The report maps entries to markets but does not resolve
these alternatives. Source receipt timestamps do not reveal venue timing, and
public depth does not establish fills or profitability.

## Decision and next work

Do not change the Reality collector, campaign, or decision cadence from this
result. Next, inspect the per-outcome issue pattern and the configuration stored
in finalized process-start records to distinguish pair-wide inactivity from
one-sided source behavior. Any sampling or collector experiment must use a new
campaign identity and predeclared rules.

The replay and aggregate cross-sums reconcile: 2,344 decisions, 1,503 freshness
violations, 24,744 update frames, 152 gaps, and 908 issue entries in the
overall, by-market, and by-block groupings. No test suite was run for this
incremental analysis change.
