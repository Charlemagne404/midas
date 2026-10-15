# Shadow-canary failure forensics 001

## Finding

The one-shot service failure for canary campaign
`eaa761d7d4e7fa1f4561a5f61e350ce5c3f4a98420b414821a0ca9eb70b9cc14` was
caused by a frozen source-reader snapshot that rejected an empty finalized
segment after a populated segment.

The canary froze at 2026-10-14 20:48:58 CEST. Its captured
`shadow_source.py` hash was
`eed00214749e77f0fe96df6746412a806c0784b81b18317d8d1b14eb7763010e`. The
service failed at 20:49:15 CEST after reading 847 source records; the campaign
status records `source_ordinal=847`, `records=847`, zero decisions, and zero
actual orders.

The source reader sorted segment filenames by name. The recording catalog has
two finalized segments with ordinal prefix 776:

- `00000000000000000776-028583b9455246b88e0d4339a265c3e4.seg`: 72 records,
  ordinals 776–847.
- `00000000000000000776-0ea71c438ac74394a00a3faf1b1891ce.seg`: zero records,
  `last=0`, and an 8-byte framing header. Its SHA256 and size match its
  catalog, so the failing clause was the nonzero-cursor comparison.

After consuming the populated segment, the frozen reader advanced its global
cursor to 847. It then compared the empty segment's `last=0` with that global
cursor and raised `Final source segment integrity/continuity mismatch`. Empty
segments have no final ordinal to compare, so that equality check was too
strict.

## Resolution in the release baseline

Commit `8775bdaa9f6a6116ba89ac5c436a133998582ceb` changed the check to require
`info["count"] > 0` before comparing `last` with the global cursor. The same
commit added regression
`tests/test_reality_shadow.py::test_verified_empty_rotated_segments_do_not_reset_global_ordinal`.
The fix commit is an ancestor of the Veritas release baseline. That focused
test passed in the Veritas checkout in 1.25 seconds.

The failed canary's code is frozen. Its campaign and journal were not edited or
restarted to apply the fix; the original protected Mission 2 campaign was not
changed. The failure is historical and fixed in released code, not evidence of
a current shadow-worker defect.

## Scope and limits

This classification read the failed service journal, canary plan/status,
captured source code, and segment catalog JSON. It did not read any `.open`
file or replay source frames. To rule out the checksum and size branches of the
reported condition, it hashed only the empty segment's 8-byte framing header;
it did not read the populated segment's record data. No campaign was modified
or service restarted. No orders were submitted.

The exact triggering catalog and cursor state are supported by the error
ordinal and matching segment metadata. The failed campaign itself was not
restarted or replayed, preserving its frozen evidence and failed status.
