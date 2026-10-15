# Veritas operations — research procedures

Veritas work runs in `/home/charlie/midas-veritas` on `project/veritas`, based
on release commit `f968095feb9c591de38fe12d7493224425f62f3a`. Reality collection
and its frozen prospective worker continue from the separate
`/home/charlie/midas-reality` worktree.

## Read the Reality baseline without taking writer ownership

The bounded forensic command opens the campaign journal with SQLite read-only
mode and does not write to the campaign directory:

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_forward_audit.py \
  --root /home/charlie/midas-reality/data/research/reality/forward/mission2 \
  --limit 50000
```

The command validates the frozen campaign identity and limits the indexed
decision query to at most 50,000 records. Its output summarizes reasons and
provenance; it never exports raw observations. A live writer may append while
the read transaction is open. Operational status JSON and service health are
separate snapshots and can lag the journal by a few outcomes.

`--check-integrity` adds a full read-only SQLite scan. Use it during a low-load
period because scan time and disk reads grow with the journal archive. The
default forensic query does not scan the full database or event hash chain.

## Reproduce sampled decisions from finalized raw segments

Use the source replay when journal decisions need independent source verification:

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_reconcile_sources.py \
  --campaign-root /home/charlie/midas-reality/data/research/reality/forward/mission2 \
  --limit 5000
```

The command verifies the frozen campaign code, takes a short read-only journal
snapshot, and replays only cataloged finalized `.seg` files. It does not read an
active `.open` segment, write into Reality, or copy raw observations to its
aggregate report. Decisions at source ordinals beyond the captured finalized
prefix are reported as uncovered. The default source bound is 20 GiB; use a
smaller `--max-source-gib` value when limiting disk reads. Full-prefix replay
reads each finalized segment for both integrity and reconstruction, so use it
when needed rather than as a frequent poll. The committed result is
`docs/VERITAS_GATE_A_SOURCE_REPLAY_001.json`.

The current replay also reports decision-to-frame input lag, paired-book age,
cross-outcome receiver-time skew, per-market book-update intervals, recorded
source gaps, and freshness counts by quality reason and market. The v5 report
adds five-minute family activity groups, normalized issue labels mapped to
campaign market IDs, and unmapped-entry counts, without exporting asset
identifiers. Input lag starts at the recorded frame receiver timestamp; zero skew
is not evidence of venue-level simultaneity.
The latest combined snapshot is
[VERITAS_GATE_A_GAP_MARKET_001.json](VERITAS_GATE_A_GAP_MARKET_001.json),
documented in [Gate A checkpoint 007](VERITAS_GATE_A_CHECKPOINT_007.md).
Intervals spanning
source discontinuities are censored. These measurements are diagnostic and do
not modify the frozen campaign or establish fills.

## Count raw market-frame quality and opportunity states

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_raw_funnel.py \
  --campaign-root /home/charlie/midas-reality/data/research/reality/forward/mission2 \
  --max-source-gib 20 \
  > docs/VERITAS_GATE_A_RAW_FUNNEL_002.json
```

This replays the finalized prefix to rebuild books and verify online
reconstruction checkpoints, but aggregates only campaign-period frames that
touch a paired market. It uses recorded receiver time, not shadow-worker
processing time. Counts are repeated correlated observations, distinct from
the scheduled decision denominator. It reports public ask-depth support before
fees and never claims a fill. Version 2 compares each leg's depth-weighted USDC
notional with the reported per-order USDC minimum. Its bounded, raw-free output
is `docs/VERITAS_GATE_A_RAW_FUNNEL_002.json`.

## Reproduce the controlled capacity sensitivity

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_economic_scenario_study.py \
  > docs/VERITAS_GATE_B_CAPACITY_001.json
```

This deterministic exercise uses a hand-authored synthetic V1 order book, a
discrete quantity grid, USDC capital budgets, explicit fee and carry assumptions,
and full/half displayed-depth sensitivities. It makes no observed-opportunity,
fill, or strategy-performance claim. Its implementation is in
`packages/midas/veritas/scenario_study.py` and its assumptions are embedded in
the output artifact.

Read-only service evidence is available from:

```bash
curl --fail --silent http://127.0.0.1:8010/api/health
curl --fail --silent http://127.0.0.1:8010/api/reality/overview
curl --fail --silent http://127.0.0.1:8010/api/reality/operations
curl --fail --silent 'http://127.0.0.1:8010/api/reality/forward?limit=5000'
```

The `overview` and `operations` endpoints include bounded status and resource
summaries. Do not use dashboard requests to modify campaign state.

## Verify Veritas code

Focused economic and forensic checks:

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/pytest -q \
  tests/test_veritas_economics.py tests/test_veritas_forensics.py \
  tests/test_veritas_source_replay.py tests/test_veritas_raw_funnel.py \
  tests/test_veritas_economic_scenario_study.py
/home/charlie/midas/.venv/bin/ruff check \
  packages/midas/veritas scripts/veritas_forward_audit.py \
  scripts/veritas_reconcile_sources.py scripts/veritas_raw_funnel.py \
  scripts/veritas_economic_scenario_study.py \
  tests/test_veritas_economics.py tests/test_veritas_forensics.py \
  tests/test_veritas_source_replay.py tests/test_veritas_raw_funnel.py \
  tests/test_veritas_economic_scenario_study.py
MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy packages/midas/veritas
```

The latest focused economics, funnel, and synthetic scenario set passed 24
tests. Full project verification remains a later Gate H task. No long-running
Veritas job is currently scheduled.

## Preserve service and evidence ownership

- Never edit `campaign.json`, frozen models, pinned source, labels, plan,
  `shadow.sqlite`, collector status, raw recording segments, or integrity files
  in `/home/charlie/midas-reality`.
- Do not restart, stop, pause, or launch a second process against the Reality
  campaign. Inspect user-service status and bounded API evidence first.
- Do not claim a fill from displayed depth or public quote persistence. All
  Veritas economics are hypothetical, all orders remain disabled, and no wallet
  or trading credentials are used.
- Keep experiments bounded and checkpointed. Use no paid services or external
  compute. Preserve raw, model, Laboratory, Arena, Prometheus, and campaign
  artifacts.
- Save new evidence in this worktree and commit coherent checkpoints on
  `project/veritas`; do not merge into `main` without a separate integration
  request.
