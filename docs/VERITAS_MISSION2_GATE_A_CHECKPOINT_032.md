# Gate A checkpoint 032 — scan 35 and finalized-source advancement

**Updated through:** 2026-10-15T21:22:40Z  
**Mission status:** active; scan 35 is qualified with no positive candidate. The Director manifest awaits its next scheduled reconciliation.

## Scan 35 and cumulative discovery panel

Scan `scan-20261015T210215Z-1f43257737f1` completed at 21:02:15.077509 UTC.
Six bounded discovery queries returned 300 rows / 300 unique market IDs. Of
these, 144 met the supported same-condition V1 binary relationship rule and
156 were excluded (93 augmented NegRisk markets with unverified semantics and
63 unsupported outcome relationships). Forty markets were selected: 36
rotating stratified selections and four stable controls. Thirty-five pairs
passed the request/receipt quality checks; five were invalid for an empty ask
side. No positive top-gross pair appeared.

The 35-snapshot panel contains 1,400 selected pairs / 1,237 quality-valid
pairs / 163 invalid pairs / 648 selected market IDs. The legacy reported-age
rule accepts 280 pairs; request/receipt quality accepts 1,237, a gain of 957
observations or 68.36 percentage points over the 1,400 selected slots. This
does not establish venue timestamp freshness. The maximum top-pair edge is
still -$0.001 per share. Positive counts remain zero at all five gates:
unchanged top-ask gross, full displayed-depth gross, both per-leg minimums,
single-match fee sensitivity, and fragmentation-safe fee sensitivity.

The five-scan coverage pilot has enrolled 200 selected pair slots: 167 valid,
33 invalid, zero skipped sequences, and 152 distinct market IDs. Rotating
selections account for 161/184 valid slots (87.5%); the stable control accounts
for 6/16 (37.5%). Selection is not randomized, so this split is descriptive
only. The pilot remains active until its fixed stop at
2026-10-16T19:00:55.062293Z.

## Finalized Reality source prefix

The scheduled source-analysis run at 21:10:14 UTC completed at 21:14:02. It
processed 125 segments / 33,387,810 bytes, used 11.574 CPU seconds and
134.6 MiB peak memory, used no swap, and had no restart. The sealed summary
covers 3,641 of 4,377 cataloged segments; 736 segments / 237,913,078 bytes
remain pending through ordinal 481,259. The processed prefix contains 234,756
campaign-window frame records, 211,075 touched market-frame states, and
204,052 quality-valid states across 57 markets. Positive top-ask, quantity
depth, full-depth, and minimum-notional states remain zero.

The campaign-window aggregate reports 1,031 `book_resynchronization` records
and one `connection_failure`. These markers do not measure outage duration or
prove complete feed recovery. Summary digest:
`f79547bf514b24e53e42290303e1c81073486c16aa9f117586e761770c052565`; file
SHA-256: `e047067739112120fd78c6f5a989b8447ef64f36e88c772e8b20f9cb6c1686ac`.

## Bounded gap-detail replay

The separately versioned gap-detail extractor completed its second scheduled
batch at 21:21:07 UTC. Its append-only prefix now covers 256 of 4,396
nonempty finalized segments (4,140 pending), 28,731,135 processed bytes, and
ends at ordinal 13,113 / 2026-10-14T10:15:11.052089Z. This is before the
campaign window begins at 2026-10-14T21:07:58.642601Z; its campaign-window gap
count of zero is therefore an expected scope limitation, not a finding about
the campaign.

The prefix contains 466 all-period gap records: 422 book resynchronizations,
five malformed-constraint markers, 11 process starts, nine process stops, and
19 scheduled refreshes. An independent read-only comparison verified both
256-event seals, source/gap catalog identity and prefix digests, all 466 gap
records against their finalized raw records, the source-analysis event prefix,
and the persisted gap-event chain head. The service used 3.307 CPU seconds,
peaked at 131.5 MiB, used no swap, and exited successfully without restart.
The replay remains bounded and catching up; it has not reached campaign-time
segments. See [gap-detail prefix artifact 001](VERITAS_MISSION2_GAP_DETAIL_PREFIX_001.json).

## Scan-pinned qualification

The 21:15:31 UTC Director cycle admitted one bounded Arena job for scan 35.
Arena completed it at 21:16:12 UTC with exit status 0 and no error:

- Job: `job-b8352727baca4803824a6b95`
- Finding: `veritas-qualification-v1-c92a948f88c300e1`
- Run: `VERITAS-M2-ECO-QUAL-001-V3-RUN-c835a985c45f`
- Dataset SHA-256: `c835a985c45fe938589c9a67aecc385d75fb28b469aab46cf0e2d794581c8b2b`
- Experiment SHA-256: `7c34933b8c5f54b0dc3c490bc1b224c1e6277a8aa8b8b8d2ea0ea0304f78f7aa`
- Job-file SHA-256: `b2e49956b0630b18cbd223e63c7e5e44f31e712faa41616c1515ccc463f73839`
- Finding-manifest SHA-256: `3bbc5a71ed9633eea379fd9eb04582cb75d06fb366e3c07627491c154b516151`

All five economic gates returned zero positive states. Candidate evidence is
complete with zero rows, and independent candidate replay is complete with
status `NO_POSITIVE_CANDIDATES_TO_REPLAY`. The finding covers all 35 snapshots,
1,237 quality-valid pairs, and 648 distinct market IDs. No authenticated
request was used and no order was submitted. This is candidate qualification,
not a strategy P&L or execution result.

At this capture the Director manifest still projects the completed job as
`QUEUED` and scan 34 as the latest qualified scan. The authoritative Arena job
and finding are terminal and successful; the next scheduled Director cycle
at 21:45 UTC is the reconciliation point. No manual poll or retry was used.

## Evidence and limitations

- Scan evidence digest: `1f43257737f143c90036e805e9e87cad664262278a1f6555382f2709dfea2660`
- Compressed snapshot SHA-256: `aff341d050607a8dfed70aab500ab4787dfdbfaee33e45f8ecfcbe00161465fa`
- Scan analysis-event digest: `5183c243adeb04f0ef529bbe9eeadd13ce8edca5d368b7b5e4e6b4af59d8b0a4`
- Scan analysis-event file SHA-256: `1fb8302dffd4732dc0e4bc0b71875b6e661bf2668f965d9128a4bdd6a15244e0`
- Cumulative panel digest: `5c4d181185df24113314db958a2b7f2bc70bc8f68bc26c6ebbff6e3c38eb4a45`
- Coverage-pilot digest: `e663b408598503adf70df8b118ada279b9160bcb79910258acba2e398438e19e`

The bounded discovery union is not a venue census. Repeated snapshots are
correlated and do not establish continuous quote lifetime, venue sequence
freshness, execution, fills, or profitability. Keep no-trade and allow the
existing observation, source-analysis, gap-detail, and Director schedules to
continue.
