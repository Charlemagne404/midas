# Gate E checkpoint 001 — end-to-end economic qualification comparison

**Captured:** 2026-10-16T04:12:21Z
**Mission status:** active; the qualification experiment is complete, while strategy-P&L research remains unready.

## Experiment

Run VERITAS-M2-ECO-QUAL-001-V4-RUN-788bf01df465 compares the unchanged top-ask gross-sign baseline with the implemented depth-, minimum-, fee-, and source-replay-aware qualification path. Arena processed all 48 finalized snapshot events for scan 48. The experiment uses actual retained public observations; it does not use synthetic profitability.

| Measure | Result |
| --- | ---: |
| Saved snapshots / selected pair observations | 48 / 1,920 |
| Quality-valid / invalid pairs | 1,660 / 260 |
| Distinct selected market IDs | 849 |
| Baseline positive top-ask gross states | 0 |
| Improved full-depth gross states | 0 |
| Full-depth plus both minimums | 0 |
| Single-match fee sensitivity positives | 0 |
| Fragmentation-safe fee sensitivity positives | 0 |
| Candidate rows / replayed rows | 0 complete / 0 complete |

The top-pair edge range was -0.996 to -0.001 per share; the median was -0.02. The unchanged baseline and the improved qualification path therefore produced the same zero-candidate decision on this sample. The implementation improves the evidence path and separates depth, Gamma USDC minimum notional, CLOB minimum share quantity, and fee gates; it did not improve candidate count or demonstrate strategy P&L.

## Verification and lineage

- Arena job: job-5bccafe9aff34826bb5efec2, completed 48/48 with exit status 0.
- Finding: veritas-qualification-v1-20478e2374e46a85.
- Dataset digest: 788bf01df46539325680926fd6074c00dd2c08b63e48ff94217a842eac495491.
- Experiment digest: 0a3229b5285e0cceeb722eddcbdc5c185b3844a11164b995ac644e2fb16e1d67.
- Job JSON SHA-256: 66f15b34a9016a2e9831dabf1992343135d47b20abe68ad8173df47db201d585.
- Arena source manifest SHA-256: e50f42ab0fa5944d49c7587347f7982d879173b32854da81329a27a48c59269a.
- Finding manifest SHA-256: 48fb2721987b6292a64f1193faf4e97675a149901145d4fc9cea1af99bd1731e.
- Candidate evidence is complete and empty; independent candidate replay is complete with zero rows.
- No authenticated request or order was used.

This is an end-to-end economic qualification experiment against an unchanged baseline. It meets the mission's economic-comparison evidence criterion at the discovery/qualification layer. It is not a policy tournament, fill simulation, strategy-return comparison, or profitability result. Repeated snapshots are dependent and selected. Only same-condition V1 pairs are supported; sequence freshness, persistence, order arrival, and fills remain unverified. The Research Director correctly reports that no model or execution-policy comparison is justified without a qualified gross candidate.

The authoritative Arena record is [Gate F checkpoint 030](VERITAS_MISSION2_GATE_F_CHECKPOINT_030.md); the implementation is packages/midas/veritas/economic_experiment.py. Mission 2 remains active.
