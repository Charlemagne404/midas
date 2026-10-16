# Gate F checkpoint 031 — scan 49 qualification and Director queue state

**Captured:** 2026-10-16T04:18:16Z
**Mission status:** active; the scan-49 child is complete and scheduled Director reconciliation is pending.

The 04:15:06 UTC Director cycle completed at 04:15:37 UTC. It admitted the scan-49 public snapshot to Arena under the existing 10% CPU, 512 MiB memory, 300-second wall-time bounds. Arena job job-8e19b6e1e2114d3abd8fb92e completed all 49/49 events in 3.51 seconds with exit status 0 and no error.

The resulting finding is veritas-qualification-v1-d07cb164143e4e53. Experiment run VERITAS-M2-ECO-QUAL-001-V4-RUN-a265c74c1856 has dataset digest a265c74c185653c71461a96a314ca7ca5439b3920164936bc5187a37bb92ca6e and experiment digest a6e3a8c634443540a700f56262195fae05d030509979513278294c5735ff673b.

| Evidence | Result |
| --- | ---: |
| Snapshots / selected pair observations | 49 / 1,960 |
| Quality-valid / invalid pairs | 1,691 / 269 |
| Distinct selected market IDs | 866 |
| Unchanged top-ask gross positives | 0 |
| Full-depth gross positives | 0 |
| Full-depth plus both minimums | 0 |
| Single-match fee sensitivity positives | 0 |
| Fragmentation-safe fee sensitivity positives | 0 |
| Candidate evidence / independent candidate replay | Complete, 0 rows / complete, 0 rows |

The edge distribution has maximum -0.001 per share and median -0.02. The job record SHA-256 is 8ddfb1ffbf9c8240aff1a7dc0ecb16926e2e134438d3c87161b632024ca42e74; Arena source-manifest SHA-256 is e50f42ab0fa5944d49c7587347f7982d879173b32854da81329a27a48c59269a; finding-manifest SHA-256 is 2b3f67a8b638e6dda3fe15f079c00d1dd7f085622ea396d380d890577f7aa19e.

The Director manifest is digest-linked at cefef2f0525afc8a068ef10bf657198a57f038918324db892e9bb909f130b224. It has advanced last_qualified_scan_id to scan-48 and identifies scan 49 as the current scan, but still records current_job_state QUEUED even though the Arena job record is complete. The next Director cycle at 04:45:07 UTC is the scheduled reconciliation point. No manual poll, retry, duplicate admission, service restart, or campaign change was made.

The completed child is qualification evidence over a selected intermittent panel. It is not a strategy-P&L, execution, order-arrival, or fill result. No authenticated request or order was used. Model readiness remains NOT_READY_NO_CANDIDATE_RELEVANT_TARGET and strategy readiness remains NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE.
