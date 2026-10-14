# Veritas Gate A checkpoint 006 — freshness, activity, and source gaps by time block

Captured at 2026-10-14T23:34:37.391618Z. The machine-readable result is
[VERITAS_GATE_A_TIMEBLOCK_001.json](VERITAS_GATE_A_TIMEBLOCK_001.json). This
checkpoint extends the finalized-source replay in
[checkpoint 005](VERITAS_GATE_A_CHECKPOINT_005.md) with five-minute family
activity blocks and aggregate issue labels from source resynchronization gaps.
It is diagnostic only and does not accept Gate A or a later development gate.

## Protected-state check

- The protected Reality campaign remains
  adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46. Its plan
  SHA256 was aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5
  after the replay.
- At the post-scan status check, the Reality recorder and shadow worker were
  active, each with zero restarts.
- The source replay read only cataloged finalized segments. It did not read the
  active .open segment. The campaign files, services, and plans were not changed;
  no orders were submitted.

## Finalized-prefix reconciliation

The bounded query selected 2,232 decision rows under its 5,000-row limit at
journal event sequence 26,165. Of these, 2,224 reproduced from the captured
finalized prefix without mismatch; eight newer decisions fell beyond that
prefix. No selected row inside the prefix was missing, all 12,795 cited source
references resolved, and the mismatch set was empty.

The replay verified 1,820 finalized segments (423,095,903 bytes), 219,065 raw
records through the last finalized ordinal, and 1,816 reconstruction
checkpoints. The source manifest SHA256 was
fb91b43fe1a4c0d017c3e2bfda5f9caf84f0a46026c3e8d73b503c4ac9023156.

Decision-to-source-frame input lag had a 41.568 ms median, 220.232 ms p95, and
248.866 ms maximum, below the frozen 250 ms limit for all 2,224 reproduced
rows. The maximum of the two reconstructed outcome-book ages had a 10.054 s
median, 50.890 s p95, and 62.407 s maximum. In total, 1,429 of 2,224 rows
(64.2%) exceeded the frozen five-second freshness limit. The quality-reason
counts included 1,383 stale_book, 22 book_issue:stale, 23
source_timing_uncertainty, and one book_issue:advertised_top_pending.

There were 11 sampled markets. In 1,845 decision rows the cited global source
frame updated neither outcome of the target market; 379 rows updated both, and
none updated exactly one. All 1,383 stale_book rows cited a frame with no target
market outcome update in that exact raw record. This exact-frame result does
not establish that the market had no update during the preceding five seconds.

## Time-block activity and freshness

The replay counted 23,743 paired-book update frames across 11 markets. The
170 family-by-five-minute groups sum to 2,224 reproduced decisions and 1,429
freshness violations. Aggregated over UTC five-minute blocks, the violation
fraction ranged from 36.1% to 86.3%. Every one of the 30 blocks containing
resynchronization gaps had two to seven such gaps, but the gap count alone did
not track the freshness rate.

| UTC five-minute block | Decisions | Freshness violations | Source update frames | Resynchronizations |
| --- | ---: | ---: | ---: | ---: |
| 21:45 | 73 | 63 (86.3%) | 251 | 6 |
| 22:10 | 80 | 67 (83.8%) | 1,128 | 5 |
| 22:25 | 72 | 26 (36.1%) | 700 | 5 |

Per-market scheduled freshness and update activity are shown below. Update
frames include the campaign-window activity blocks in the captured source prefix,
including blocks without a sampled decision for that market.

| Market | Decisions | Over 5 s | Book-update frames |
| --- | ---: | ---: | ---: |
| 4853873 | 4 | 1 (25.0%) | 12 |
| 559687 | 278 | 220 (79.1%) | 293 |
| 561251 | 278 | 212 (76.3%) | 296 |
| 562828 | 164 | 8 (4.9%) | 8,175 |
| 5674900 | 278 | 218 (78.4%) | 366 |
| 5674902 | 45 | 33 (73.3%) | 104 |
| 5674915 | 274 | 215 (78.5%) | 660 |
| 5675021 | 278 | 123 (44.2%) | 11,734 |
| 665205 | 278 | 225 (80.9%) | 186 |
| 679026 | 278 | 152 (54.7%) | 1,174 |
| 679055 | 69 | 22 (31.9%) | 743 |

The time grouping makes the variation visible: 22:25 had a lower violation
fraction than 21:45 despite a similar number of resynchronizations. Market
562828 had frequent updates and few stale decisions; several lower-activity
markets had much higher violation rates. These remain correlated observations
from one selected campaign panel, not independent market estimates.

## Resynchronization issue labels

The finalized source window contained 144 book_resynchronization gap records.
Their affected_assets maps had 879 issue entries: 840 stale, 33 top_divergence,
and six advertised_top_pending. These are entries across gap records, not
unique assets; the same asset can appear repeatedly. No token identifiers or
raw event payloads are included in the report.

A read-only inspection of the protected collector code shows stale is one of
the issue types that can trigger a book_resynchronization path, after which
the current WebSocket path is broken. The affected_assets map records all
issue-bearing books at that gap, so these counts do not identify which market
or asset caused an individual reconnect. The many stale labels could reflect
quiet markets under the collector's freshness rule, another source condition,
or collector behavior. This aggregate report cannot distinguish those causes
and does not establish a defect.

## Interpretation and limits

Input lag remained within its frozen threshold while paired-book age often did
not. The latest snapshot therefore reinforces the observed freshness constraint.
Activity and decision scheduling vary sharply by market and time block. Gap
labels are mostly stale, but both counts and labels are insufficient to attribute
the resynchronizations to a particular market.

Receiver timestamps measure source receipt, not upstream venue timing. The
zero cross-outcome receiver-time skew does not prove venue simultaneity. Market
updates and displayed depth do not establish fills, queue position, market
impact, or profitability. No cadence, collector, campaign, strategy, or policy
change is promoted.

## Verification

- The v4 source replay reproduced 2,224 finalized-prefix decisions with no
  mismatch; eight decisions were beyond the captured finalized prefix.
- Cross-sums from the report reconcile to 2,224 decisions, 1,429 freshness
  violations, 23,743 update frames, 144 gaps, and 879 affected issue entries.
- Focused tests, Ruff, formatting, and strict mypy had passed after the v4 code
  changes. No Reality source or campaign code was changed for this checkpoint.

## Next work

1. Map affected issue entries to market IDs and five-minute blocks using the
   already-replayed market context; do not export token identifiers.
2. Compare the issue-bearing markets and gaps against market activity, and
   inspect the recorded collector settings and trigger semantics to distinguish
   ordinary inactivity from a source or collector defect.
3. Keep the frozen campaign unchanged. Any eventual cadence experiment must use
   a new campaign identity and a predeclared target population.
