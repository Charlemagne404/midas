# Gate F checkpoint 030 — scheduled qualification through scan 48

**Captured:** 2026-10-16 03:58 UTC
**Mission status:** active; the Director's next reconciliation is still pending.

## Scheduled Director and Arena result

The 03:45:20 UTC Research Director cycle admitted one bounded qualification for scan-20261016T033156Z-fda52aa72c22. Arena job job-5bccafe9aff34826bb5efec2 completed all 48/48 source events at 03:46:03 UTC. The child is terminal, with no current worker. The job record reports a 10% CPU quota, 512 MiB memory bound, and 300-second wall limit.

The finding is veritas-qualification-v1-20478e2374e46a85. Experiment run VERITAS-M2-ECO-QUAL-001-V4-RUN-788bf01df465 has experiment digest 0a3229b5285e0cceeb722eddcbdc5c185b3844a11164b995ac644e2fb16e1d67 and dataset digest 788bf01df46539325680926fd6074c00dd2c08b63e48ff94217a842eac495491.

| Evidence | Result |
| --- | ---: |
| Snapshots / selected pair observations | 48 / 1,920 |
| Quality-valid / invalid pairs | 1,660 / 260 |
| Distinct selected market IDs | 849 |
| Top-ask gross positive states | 0 |
| Full-depth gross positive states | 0 |
| Depth plus per-leg minimum positive states | 0 |
| Single-match fee-sensitivity positive states | 0 |
| Fragmentation-safe fee-sensitivity positive states | 0 |
| Candidate evidence rows | 0, complete |
| Independent candidate replay | Complete, zero candidates |

The observed top-pair edge distribution has 1,660 states, maximum -0.001 per share, median -0.02, minimum -0.996, and zero positive states. The decision remains no-trade while bounded observation continues.

The finding is candidate-qualification evidence for this selected, intermittent panel. It is not strategy P&L, execution, order-arrival, or fill evidence. The separate independent raw-source audit still covers 47 snapshots; this scheduled Arena run does not replace that audit. No authenticated requests or orders were used.

## Reconciliation

The Director admitted the scan-48 child and exited successfully. Its persisted projection still needs the next scheduled reconciliation. No manual poll, retry, duplicate admission, service restart, or campaign change was made for this checkpoint.

Job record SHA-256: 66f15b34a9016a2e9831dabf1992343135d47b20abe68ad8173df47db201d585. Finding manifest SHA-256: 48fb2721987b6292a64f1193faf4e97675a149901145d4fc9cea1af99bd1731e.
