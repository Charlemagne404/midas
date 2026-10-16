# Gate C checkpoint 024 — durable tail refresh avoidance

Captured 2026-10-16 17:39 UTC. This checkpoint compares the branch immediately
before and after the `Tail` refresh change on one identical finalized-source
segment. The frozen campaign file remained at SHA-256
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`; the live
collector and shadow service remained active, with restart counts 0 and 1.

The change avoids rescanning the segment directory and searching cached path
stems for each record while a segment handle is open. It forces a refresh at a
sealed segment boundary so newly rotated segments remain discoverable. The
matched 5% CPU / 384 MiB / no-swap canary processed ordinals 529093–529528
(436 records, 379 frames), producing 8 decisions, 40 observations, 32
censored follow-ups, and 48 research events. Engine, context, research and
90-event journal hashes matched exactly. The journal verifier succeeded.

Against the immediately preceding top-cache-only branch, process CPU fell from
5.977 to 1.406 seconds (76.48%) and wall time from 119.60 to 28.21 seconds
(76.42%). The only implementation module hash that changed was
`shadow_source.py`; the runner and other module hashes matched. This is one
paired segment and one pass, so the measured reduction is preliminary. It does
not show that the frozen worker has caught up or that the optimization will
scale across longer runs.

Focused shadow, resumable replay and Reality panel tests had passed 51 tests
before this canary; Ruff and formatting checks passed. Strict Mypy for the
latest tail change was not confirmed. No full regression was run. The live
campaign, worker, source cursor and production journal were not modified.

See [benchmark 005](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_005.json) and
isolated result files under `data/veritas-canaries/shadow-tail-refresh-001/`.
