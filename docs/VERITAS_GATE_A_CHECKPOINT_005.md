# Veritas Gate A checkpoint 005 — source update cadence

Captured at `2026-10-14T23:27:08.178011Z`. The machine-readable result is
[VERITAS_GATE_A_SOURCE_CADENCE_001.json](VERITAS_GATE_A_SOURCE_CADENCE_001.json).
This checkpoint joins market update activity to the decision timing measured in
[checkpoint 004](VERITAS_GATE_A_CHECKPOINT_004.md). It does not accept Gate A or
any later development gate.

## Protected-state check

- The frozen Reality campaign remains
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`; its plan
  SHA256 remains
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The Reality recorder and shadow worker were active before and after the scan,
  each with zero service restarts.
- The campaign plan, journal, raw recordings, and service state were not
  changed. No orders were submitted.

## Same-snapshot source and decision coverage

The bounded read-only query selected 2,120 decision rows under its 5,000-row
limit at journal event sequence 24,919. Every selected decision reproduced from
the finalized prefix without mismatch. The replay verified 1,806 finalized
segments (420,222,882 bytes), 217,712 source records, 1,802 reconstruction
checkpoints, and all 12,387 cited source references. No sampled row was beyond
the finalized prefix. The manifest SHA256 is
`1c9ead2717035a8b9fa22ac12fa4f8ec2c10728cb8fcf2cea9df72453562f319`.

The analysis counted 22,780 campaign-window market book-update frames across ten
markets. In 22,738 frames both outcomes updated in the same raw record; 42 frames
updated only one outcome. It recorded 138 `book_resynchronization` gaps. Pair
update intervals that crossed a source gap, unsupported producer or
reconstruction frame, or receiver clock regression were censored rather than
counted as continuous-market silence.

## Scheduled-decision alignment

Decision time minus the cited raw frame receiver timestamp had a 41.970 ms
median, 219.469 ms p95, and 248.866 ms maximum, all within the frozen 250 ms
limit. However:

- 1,761 of 2,120 scheduled rows (83.1%) cited a source frame that updated
  neither outcome of the target market. The other 359 rows updated both
  outcomes in that frame; none updated exactly one.
- 1,334 `stale_book` decisions had no target-market outcome update in their
  cited frame. The same-frame count only describes that exact raw record; it
  does not mean the market had no update during the preceding five seconds.
- 1,380 decisions (65.1%) had a reconstructed outcome book older than the
  frozen 5 s freshness limit. The source input frame was recent, while the
  target market's latest book could be much older.

The table pairs per-market update intervals with scheduled freshness in this
snapshot. Interval percentiles are fixed-width buckets, and gap-spanning
intervals are excluded.

| Market | Book-update frames | Pair interval p50 / p95 | Intervals censored | Decisions over 5 s |
| --- | ---: | --- | ---: | ---: |
| 559687 | 274 | 10–30 s / 30–60 s | 137 | 212/265 (80.0%) |
| 561251 | 279 | 5–10 s / 30–60 s | 137 | 204/265 (77.0%) |
| 562828 | 7,450 | 0–250 ms / 2–5 s | 78 | 6/151 (4.0%) |
| 5674900 | 355 | 0–250 ms / 30–60 s | 137 | 210/265 (79.2%) |
| 5674902 | 104 | 0–250 ms / 30–60 s | 23 | 33/45 (73.3%) |
| 5674915 | 648 | 0–250 ms / 10–30 s | 137 | 209/265 (78.9%) |
| 5675021 | 11,637 | 0–250 ms / 1–2 s | 138 | 118/265 (44.5%) |
| 665205 | 177 | 10–30 s / 30–60 s | 137 | 217/265 (81.9%) |
| 679026 | 1,113 | 2–5 s / 10–30 s | 137 | 149/265 (56.2%) |
| 679055 | 743 | 1–2 s / 5–10 s | 35 | 22/69 (31.9%) |

## Interpretation and limits

The 30 s scheduled decisions often land on a recent global source frame that
does not update the market being evaluated. The market's activity is uneven:
562828 had frequent pair updates and a 4.0% freshness-violation rate, while
559687 had sparse pair updates and an 80.0% rate. This supports an
activity-and-schedule alignment explanation for much of the stale-book pattern.

Pooled intervals still hide bursts and quiet blocks. Market 5675021 had a fast
median and p95 pair-update interval but a 44.5% scheduled freshness-violation
rate, showing why total update volume alone is insufficient. The 138
`book_resynchronization` gaps also censor many intervals; their affected issue
types have not yet been broken down. No recorder or campaign defect is proven,
and no cadence change is justified by this aggregate snapshot.

These are correlated measurements of one selected cohort. Frame-receiver
timestamps do not identify upstream exchange timing. Neither source updates nor
displayed depth establish fills, queue position, market impact, or profitability.

## Verification

- Veritas focused suite: 27 passed.
- Ruff check and formatting check passed for the changed source and replay test.
- Strict mypy passed for `packages/midas/veritas`.
- Source replay v3 passed with no mismatches and no uncovered sampled rows.

## Next work

1. Align source updates, gaps, and decision freshness by five-minute market
   family blocks to reveal burst and quiet periods.
2. Summarize the affected issue labels in `book_resynchronization` gaps without
   exporting asset or event payloads.
3. Only propose a separate frozen sampling-cadence experiment after those
   results identify an economically useful, measurable target population.
