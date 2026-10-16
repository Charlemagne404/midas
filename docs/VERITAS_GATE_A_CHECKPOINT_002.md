# Veritas Gate A checkpoint 002 — finalized-source decision replay

Captured at `2026-10-14T22:59:40.573453Z`. The machine-readable result is
[VERITAS_GATE_A_SOURCE_REPLAY_001.json](VERITAS_GATE_A_SOURCE_REPLAY_001.json).
This checkpoint adds a source-replay result to the initial forensic record in
[checkpoint 001](VERITAS_GATE_A_CHECKPOINT_001.md); it does not accept Gate A or
any later development gate.

## Protected-state check

- The frozen Reality campaign identity remains
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46` and its
  plan SHA256 remains
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The main worktree remains clean on `main`; the protected Reality worktree
  remains clean on `project/reality`.
- The Reality recorder and shadow worker are active, each with zero service
  restarts at this checkpoint. No campaign, raw recording, or service state was
  changed by this audit.

## Method and result

`scripts/veritas_reconcile_sources.py` captured a bounded read-only decision
sample from the campaign journal, closed the SQL snapshot, then replayed the
numbered catalog entries and their finalized `.seg` files. It did not enumerate
or open the active `.open` segment. The source manifest hash, every segment
hash, segment metadata, contiguous ordinal sequence, and online reconstruction
checkpoints were verified. The campaign identity and pinned Reality code were
also checked before replay.

At the source snapshot, 1,696 decisions were selected (the 5,000-row bound did
not truncate the sample) at database event sequence 20,152. Of those, 1,688
source ordinals were inside the finalized prefix through ordinal 210,322. All
1,688 reproduced without mismatch for source record, reconstruction state,
producer identity, quality reason, features, baseline, and core lineage. All
9,838 distinct source references cited by those decisions resolved to actual
records in the verified prefix. No decision row inside the finalized prefix was
missing. Eight newer decisions referenced source ordinals beyond that prefix
and were left uncovered because their source segment was active.

The verified prefix contained 1,752 finalized segments and 404,829,765 bytes.
The replay checked 1,748 online engine checkpoints. Its source manifest hash is
`2b28b87c7edb3fcabd199142e605d915f11ca0c31d71550e0f85f8f7747558a8`.

The worker's stored rolling `feature_sources.history` lists differed from a
continuous replay for 1,254 decisions. The worker prunes this rolling history
when its runtime snapshot is saved, and the exact save timing is not reproduced
by the offline scan. This variance did not extend to stored features or core
lineage in the finalized-prefix sample; every cited source reference resolved
and pointed to an ordinal no later than its decision. Exact history-window
membership is therefore a recorded runtime detail, not an exact replay match.

## Interpretation and limits

This is evidence that the sampled decisions are reproducible from the
immutable finalized source prefix. It does not prove the worker emitted every
eligible decision, recover data from the active segment, reproduce future
outcomes, or establish fillability or profitability. It also does not replace
the next raw-source opportunity-funnel analysis: event quality, synchronized
pair cadence, market activity, full displayed depth, and cost bounds still need
to be stratified and tested prospectively.

## Verification

- Veritas focused suite: 23 passed.
- Ruff: passed for Veritas modules, focused tests, and both audit commands.
- Strict mypy: passed for `packages/midas/veritas`.
- The synthetic replay test included a malformed `.open` file beside a valid
  finalized segment and confirmed the scanner ignored it.

## Next work

1. Build a bounded raw opportunity funnel by market, family, activity, and
   quality state, using the finalized source reader and explicit fee/depth
   assumptions.
2. Measure pair-update and valid-observation cadence before preregistering any
   new cadence or horizons; leave Reality's frozen plan untouched.
3. Validate economic edge under full displayed depth, per-leg fees, minimums,
   settlement, capital, and adverse unmatched-position outcomes.
4. Preserve the evolving campaign with later source snapshots, keeping each
   capture's journal sequence and source manifest hash separate.
