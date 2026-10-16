# Gate C checkpoint 011 — campaign gap-censor attribution

**Captured:** 2026-10-16 03:12 UTC
**Mission status:** active; the finalized gap index remains scheduled and incomplete.

## Scheduled gap-detail progress

The 03:05 UTC gap-detail batch exited successfully at 03:06:14 UTC. It read
128 finalized segments / 32,886,676 source bytes and advanced the verified
prefix to 1,919/5,079 segments, or 449,729,433 processed bytes. There are
3,158 segments / 862,240,407 bytes pending. The sealed index now contains
194 campaign-window `book_resynchronization` events across ten reported
markets. It did not read an active `.open` segment. The prefix remains partial.

## New source-grounded censor join

The new read-only attribution audit scanned all 40,075 censored horizon rows
from the frozen campaign journal without truncation. It reverified the sealed
gap-detail summary, state, source-code pins, all 1,919 gap-detail event-file
digests, prefix catalog chain, event chain, and the frozen campaign window.
It separately verified 157 exact campaign termination records in 133
finalized Reality segments (58,443,329 segment bytes) under the existing
128 MiB source cap. No active source file was opened and the SQLite event hash
chain was not reverified.

Of the 339 gap-labeled censors, 179 are explicit
`recorded_gap:book_resynchronization` outcomes. Their raw source references
were verified; 38 outcome rows (27 distinct gap records) are represented in
the current detail prefix, while 141 exact gap records lie beyond it.

The other 160 rows are `book_issue:gap:book_resynchronization` labels whose
termination references point to preceding market/discovery records rather
than to the gap itself. Among those rows, the partial detail prefix found:

- 45 outcomes with a preceding same-market, same-reason gap candidate,
  spanning six distinct indexed gap records;
- 29 outcomes whose termination references are within the indexed prefix but
  have no matching preceding same-market gap there;
- 86 outcomes whose termination references are beyond the indexed prefix.

The 45 candidate links are weak temporal evidence. Only eight are within five
minutes of the referenced gap; 30 are more than one hour later. The median
gap-to-termination receiver-time interval is about 2.26 hours, and the maximum
is about 9.08 hours. These are recorder receiver times, not exchange quote
times. A gap record can also precede later recovery; this audit cannot show
that a book stayed impaired or that a particular gap caused a censor.

The complete row-level attribution and source pointers are in
[CENSOR_GAP_ATTRIBUTION_001](VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_001.json).
Its file SHA-256 is
`332258b51f72c058cf945742ff29f0d26abcb1da0d5865ebcfd5419fb94e45a5`; its
sealed result digest is
`2c81d4ad8852b2feaae7a7b5f7bf6948a5f85c514ac9d6bfd0f3bff3935dcab2`.

## Implementation and next work

The new `censor_gap_attribution` reader keeps the previous exact-reference
audit intact. It validates a stable sealed gap-index snapshot, verifies its
code and prefix pins, matches only earlier same-market gaps with the same
reason, distinguishes an incomplete prefix from a completed no-match, and
labels indirect joins as candidate links rather than causal findings.
Three isolated tests passed, covering exact references, candidate links,
partial-prefix handling, and tamper rejection. Strict Mypy passed for the two
production/script files; Ruff and formatting passed. No full regression was
run.

Keep the 15-minute finalized-source gap schedule active. Re-run this attribution
audit after the index reaches later campaign outcomes; preserve the current
partial result as a baseline and do not promote the indirect matches to causal
labels.
