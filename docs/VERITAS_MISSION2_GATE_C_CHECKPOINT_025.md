# Gate C checkpoint 025 — four-segment durable replay

Captured 2026-10-16 17:47 UTC. A paired replay processed the same four
sequential finalized segments from the same runtime snapshot, first with the
frozen campaign implementation and then with committed branch
`40d1207`. Both runs used 10% CPU, 384 MiB memory, zero swap, a 360-second
wall limit, and separate isolated journals.

Both processed ordinals 529093–529998: 906 records, 777 frames, and four
verified sealed segments. They produced 32 decisions, 168 observations, 188
research events, and 361 journal events. Engine, context, research semantics,
and journal tail hashes were identical; both journal verifiers succeeded.
The replay contains one observed public-measurement follow-up and 123
censored follow-ups. It adds no new market collection or execution evidence.

The frozen implementation used 17.293 CPU seconds / 172.99 wall seconds; the
branch used 3.230 CPU seconds / 32.30 wall seconds: reductions of 81.32% and
81.33%. This validates exact semantics over four sequential segments and
meaningful CPU savings on this window. It remains one paired pass and does
not establish long-run live catch-up. The branch implementation hashes were
not compared with the frozen campaign's code hashes; the frozen side was
pinned and verified.

The Reality collector and shadow remained active, with restart counts 0 and
1. Campaign SHA-256 remained
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. See
[benchmark 006](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_006.json) and isolated
results under `data/veritas-canaries/shadow-multisegment-001/`.
