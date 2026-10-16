# Gate A checkpoint 039 — isolated discovery successor implementation

Captured 2026-10-16 00:32:33 UTC. This is a code and operations checkpoint;
the successor has not collected live data and has not been activated.

## Implementation

Commit `52342dc` adds `discovery-successor-001` as a separate scanner. A
complete scan makes eight logical public reads: the existing six Gamma
discovery frames, one explicit-ID Gamma lookup for the frozen control cohort,
and one batched CLOB books request. All six frames remain in place. The
successor has its own artifact root and rejects overlap with the active v1
observer root.

The direct control response is classified independently. A control enters the
stable group only if it has exactly one direct result, passes current v1
eligibility, and has an identity consistent with any matching frame record.
Missing, duplicate, ineligible, conflicting, or unexpected controls fail
closed. The rotation denominator stays the eligible population from the six
discovery frames after frozen control IDs are removed; direct controls do not
silently alter that denominator.

The implementation retains the public-read allowlist, timeouts, retries,
pacing, response-size bounds, immutable compressed scan artifacts, and bounded
state/history. It does not call the v1 scan, pilot recorder, or finalized
analysis updater. The CLI checks the pilot's fixed stop time before running.
No unit or timer was added or enabled.

## Verification

Focused verification after the final code edits:

- `tests/test_veritas_discovery_successor.py`,
  `tests/test_veritas_observatory.py`, and
  `tests/test_veritas_control_retrieval.py`: 18 passed in 8.91 seconds.
- Ruff lint, Ruff format, strict Mypy for the new module and CLI, and
  `git diff --check`: passed.
- Tests use mocked public-response transports and temporary roots. No market
  HTTP request or new experiment was run for this implementation.

Source commit hashes:

| File | SHA-256 |
| --- | --- |
| `packages/midas/veritas/discovery_successor.py` | `7908387c1d4ec03a77010b6ad9899934d0797cf289aa113ee5864b954b9f2f62` |
| `scripts/veritas_discovery_successor.py` | `d9b6dd5a7b9e6d2baa3e91a2b53aa954ec2116dcba6f91297bad62264dd00e66` |
| `tests/test_veritas_discovery_successor.py` | `2d62d1477d995f8f5c6bdb829347de8e7cc6345dc91c08bb21643565157f5f66` |

## Current v1 evidence

The scheduled v1 observer completed scan
`scan-20261016T003208Z-f65962fb4420` at 00:32:08 UTC. The scan selected 40
market pairs; 29 passed current quality checks. Its six-frame response union
contained 300 unique IDs, of which 116 met the current same-condition
eligibility rule. It had zero positive top-gross pairs and zero positive
full-depth, per-leg-minimum, single-match-fee, or fragmentation-safe-fee
states.

The 42-snapshot replay has 1,467/1,680 quality-valid selected pairs and zero
positive states at those economic gates. The fixed pilot has 12/48 scans,
397/480 quality-valid selected slots, 299 distinct selected IDs, and no
skipped scan sequences. It remains nonrandomized and descriptive, with a
fixed stop at 2026-10-16 19:00:55 UTC. These observations are intermittent and
do not establish venue-wide coverage, executable fills, or profitability.

The saved source replay summary generated at 00:14 UTC covers 4,242/4,733
finalized segments and 268,179 quality-valid campaign-window states across 67
markets. It reports zero positive top-gross or deeper economic states and 491
segments / 121,839,194 bytes pending. The saved gap-detail summary generated
at 00:21 UTC covers 908/4,753 catalog segments, with 3,843 / 1,070,710,043
bytes pending. Its processed prefix has not reached the campaign window, so
its zero campaign-window gap count is incomplete.

## Operations and next work

At 00:32:33 UTC the observer timer was active and waiting after a successful
run. The observer service, source analyzer, gap-detail analyzer, and Director
one-shot were inactive. Reality recorder, shadow, Midas API, Reality API, and
web services reported active. Available memory was 10,349,871,104 bytes,
swap use was 3,749,310,464 bytes, and the filesystem was 56% used with
212,458,233,856 bytes available. No HTTP health probe was performed.

No service or campaign was manually restarted or modified, and no pilot file
changed. The v1 observer wrote its normal scheduled scan 42; I read the
completed artifact after the service exited. The successor has produced no
scan, has no economic evidence, and remains gated through the fixed pilot
stop.

After the pilot reaches its stop, review its fixed comparison and then decide
whether to run the successor as the sole scheduled collector. Any activation
must avoid concurrent collectors and retain the versioned protocol and
separate artifact root. Gate A is not complete: live successor behavior,
control availability over time, operating bounds, and a post-pilot evaluation
remain unverified.
