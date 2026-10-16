# Gate A checkpoint 054 — bounded universe replay through scan 78

**Captured:** 2026-10-16T18:55:16Z

## Verified discovery coverage

The local A1 replay verified all 78 saved snapshots, all snapshot evidence
hashes, all 468 Gamma response hashes, and all retained CLOB response hashes.
It used 50,119,641 compressed bytes and made no network requests or orders.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs / condition IDs observed | 7,801 / 7,801 |
| Distinct markets eligible at least once under current V1 metadata | 2,552 |
| Distinct outcome asset IDs observed | 15,602 |
| Selected unique market IDs / condition IDs / asset IDs | 1,307 / 1,307 / 2,614 |
| Market IDs with multiple conditions / source identity conflicts | 0 / 0 |
| Mean unique IDs per six-frame query union | 298.82 |
| Mean V1-eligible IDs per bounded union (range 70–249) | 155.51 |
| Latest scan union: IDs / eligible / excluded | 300 / 156 / 144 |
| Attempted / quality-valid pair observations | 3,120 / 2,628 (84.23%) |
| Positive top-gross pairs | 0 |

Eligibility and selection remain conditional on the bounded six-query unions.
The 7,801 observed market IDs are not a venue-wide denominator, and the
repeated observations are dependent. Multi-outcome payoff relationships that
do not meet the same-condition binary definition remain excluded or
unverified.

## Freshness and sampled activity

Among markets with repeated comparable snapshots, 706/1,385 sampled top-of-book
comparisons changed (50.97%). This is a sparse snapshot-change proxy,
not a market update rate or quote lifetime. Reported update age exceeded five
seconds on 2,058 YES legs and 2,058 NO legs. One pair exceeded 250 ms reported
cross-outcome timestamp skew. The separate independent v3 audit admits 569
strict reported-age pairs; neither measure proves venue sequence freshness,
atomicity, quote persistence, or fills.

The current replay classifier matched the stored eligible count in 78/78
scans. One older scan still has a capture-versus-replay validity-count
mismatch: scan `scan-20261015T055928Z-c9777c1cc300` recorded 5 quality-valid
pairs at capture but replays to 32, a 27-pair difference. Snapshot and source
hashes verify; this is a stored counter discrepancy that remains open for
provenance review, not evidence of a positive opportunity.

## Resource outcome

The first attempt with a 384 MiB memory cap was OOM-killed before writing an
artifact. The one-shot local retry completed at a 5% CPU quota, no swap, and a
2 GiB memory ceiling. It used 14.93 CPU seconds over 4 minutes 57 seconds and
peaked at 952.2 MiB. No production services, campaign files, or research
records were touched. The need to retain the full verified panel makes
memory-bounded streaming a useful future improvement to this analyzer.

## Evidence

- Artifact: [market-universe coverage 013](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_013.json)
- Artifact file SHA-256: `19fb72f6b9a87b1b90110a3380503cdcbe021cf03bdd80f72c1097f151fb7673`
- Snapshot manifest SHA-256: `6120d5431fc89ca48718d75e608c55274c63db31a7fbd4c4d7afe1fc1fe03468`
- Gamma response manifest SHA-256: `9a58ccfef5f8829ee1ececaf125f7a56d052ffa232760bfef31417cd91a6345f`
- Current independent economic replay: [Gate B checkpoint 015](VERITAS_MISSION2_GATE_B_CHECKPOINT_015.md)

The bounded panel contains no positive gross candidate. Keep no-trade and
maintain the explicit coverage and freshness limitations.
