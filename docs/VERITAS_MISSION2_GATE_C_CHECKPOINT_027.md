# Gate C checkpoint 027 — SIGTERM checkpoint and resume

Captured 2026-10-16 17:58 UTC. A bounded SIGTERM was delivered to a current
branch replay running in a private canary work directory. The wrapper returned
124 because its 45-second stop threshold fired, but the replay worker caught
the signal and emitted a result with `run_termination` set to
`interrupted_checkpointed`. It durably stopped mid-segment at ordinal 529161
after 69 records / 66 frames; the journal chain verified and no decision or
uncommitted decision had been created.

A separate process resumed the same isolated journal and continued from
ordinal 529161 without a gap or overlap. It reached the same four-segment
endpoint as the one-shot reference: ordinal 529998, 906 total records, 777
frames, 32 decisions, 168 observations, 124 outcomes, and 188 research events.
The final runtime snapshot is byte-identical; engine, context, and research
semantics hashes match. SQLite integrity checks and both event-chain
verifications pass. All business tables match, all 32 decision-commit
references resolve, and the normalized business-event sequence is identical.

The final journal has 362 events versus 361 in the one-shot run because resume
appends one additional `worker_start`. Its tail hash is therefore different;
this lifecycle event is expected and retained. Unlike the prior clean split
canary, business-event ordering in this signal-stop run also matches after
normalizing the lifecycle event and generated decision-event sequence pointer.

This validates graceful interruption and continuation for this isolated
source window. The stop occurred before the first decision, so this canary
does not itself exercise the decision-to-commit recovery branch. The existing
focused regression
`tests/test_veritas_resumable_shadow_replay.py::test_missing_decision_commit_marker_is_repaired_before_followup`
injects a failure between the decision and commit transactions, verifies one
recovered uncommitted decision, and matches uninterrupted state and research
semantics; it passed in the focused 51-test suite. That is deterministic
unit-level fault injection, not an OS kill at the same instruction.

The live collector and frozen shadow remained active (restart counts 0 and 1)
and the campaign SHA remained
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. See
[benchmark 008](VERITAS_MISSION2_SHADOW_INTERRUPT_BENCHMARK_008.json) and
isolated results under `data/veritas-canaries/shadow-resume-signal-001/`.
