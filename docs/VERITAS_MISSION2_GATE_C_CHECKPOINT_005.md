# Gate C checkpoint 005 — shadow source-lag and capacity diagnosis

**Captured:** 2026-10-15 23:05 UTC
**Mission status:** active; the Reality recorder, frozen shadow worker, and
24-hour measurement pilot remain unchanged.

## New observer and measurement-pilot evidence

The scheduled observer completed scan
`scan-20261015T230055Z-ff1f8c3dbcd8` at 23:00:55 UTC. Six bounded queries
returned 300 unique market IDs; 174 met the supported same-condition pair
rule and 126 were excluded. The observer selected 40 pairs, of which 34
passed request/receipt quality and six failed because an ask side was empty.
The raw snapshot reports zero positive top-gross, full-depth, per-leg-minimum,
single-match-fee, and fragmentation-safe-fee states for all five quantities.
The v3 scan-pinned Arena qualification remains pending its scheduled Director
cycle; the raw scan counts are not presented as that qualification.

The fixed coverage pilot has completed nine scans: 305/360 pair slots passed
quality checks (84.72%) across 257 distinct selected markets, with zero missed
scan sequences. Rotating selections are 294/331 valid; frozen controls are
11/29. In scan 39, three of eight controls were selected and five were absent
from the six-query union. The read-only dashboard API verified this against
the hash-linked snapshot and pilot event chain. The pilot remains descriptive;
bounded-query absence does not establish market closure or venue absence.

## Source-lag evidence

A paired read-only sample over 23.1 seconds showed:

- Recorder ordinal advanced by 84, including 31 frame records (3.64
  ordinals/second).
- Shadow cursor advanced by 21 records (0.91 records/second), and all 21
  newly processed frames were counted as too lagged for new decisions.
- The shadow source-receipt timestamp advanced only 4.57 seconds during the
  sample. Its cursor throughput was about 25% of the recorder's ordinal rate.
- The worker's cgroup received 2.006 CPU seconds under its 100 ms/s quota.
  All 201 observed CFS periods were throttled; throttled time increased by
  18.04 seconds. The service used about 258 MB of its 512 MiB memory cap.

The current campaign plan pins a 250 ms maximum decision-input lag. The
worker's `Tail` reader advances through strictly sequential, checksummed
records and the SQLite runtime checkpoint digest verified. The worker still
processes lagged records for reconstruction and follow-up handling, then
skips new decision evaluation for stale frames. At 23:05 UTC its cursor was
166,022 ordinals behind the recorder. A metadata-only estimate counted 993
later source segments plus 21,955 bytes remaining in the cursor segment, for
about 299.4 MB pending. The estimate uses file sizes and the digest-verified
cursor; no active `.open` segment content was read.

This evidence identifies a binding CPU quota as the proximate throughput
constraint during the sample. It does not prove a long-run service rate or
independent recorder continuity. At the latest recorder status captured at
23:03 UTC, the state was `RECORDING_UNSEQUENCED`; the status still carried one
temporary DNS resolution error and 3,578 gap markers. Its observation
timestamp was current, all 16 books were flagged fresh, and sequence
continuity remained unverified. The shadow had 10,253 decisions, zero orders,
and its last decision remained at 08:58 UTC.

## Decision and next work

The active worker is advancing and its cursor digest verifies. The measured
lag is consistent with its frozen 10% CPU quota and 250 ms decision-input
bound. The current campaign and service settings were not changed or
restarted. Do not treat this lagged campaign as continuous evidence.

For a successor worker, create a separately versioned plan and benchmark
record processing with throughput margin over observed recorder input while
preserving resource limits and the decision-lag rule. Do not apply that
change to the running frozen campaign. Continue the bounded source and
gap-detail analyzers; their latest captured prefixes were 3,953/4,554 and
530/4,574 segments respectively.

Evidence: [source-lag diagnostic 001](VERITAS_MISSION2_SHADOW_LAG_DIAGNOSTIC_001.json),
[inventory 042](VERITAS_MISSION2_RESEARCH_INVENTORY_042.json), and the current
[operations checkpoint](VERITAS_MISSION2_OPERATIONS.md). Gate C remains in
progress.
