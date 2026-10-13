# PPO resumption — next engineering contract

Read-only audit during the cold-retention source freeze found that classification
MLP already restores optimizer and NumPy RNG state. Severity MLP restores
optimizer and Torch RNG state, and has a test comparing resumed curves and final
parameter hash against uninterrupted training. Cost MLP uses that same regression
trainer. Earlier broad descriptions of missing optimizer resumption were too
general; the concrete implementation gap is PPO's missing resume entry point.

## Existing PPO evidence

`packages/midas/arena/rl.py` saves a genuine Stable-Baselines3 PPO archive every
256 steps with dataset/source/configuration hashes. The archive includes optimizer
state. Its metadata already warns that episode and rollout state reset on resume.
`RLSpec` currently cannot request resumption and `train_rl` always constructs a
fresh PPO model. This is incomplete recoverability, not absence of checkpoints.

## Required implementation

1. Add a validated optional parent model identity to RLSpec and the training UI.
2. Resolve only local registered model/training artifacts; verify checkpoint
   bytes, frozen source, dataset hash, environment schema and training settings
   before loading trusted PPO archives. Reject architecture, label, execution,
   seed or other incompatible changes. Allow an explicit larger total budget
   and a fresh wall-time budget, without silently changing optimization settings.
3. Create a new derived artifact with parent/checkpoint hashes and preserved
   prior training curves. Never overwrite parent evidence or reuse its identity.
4. Load the saved policy and optimizer, preserve optimizer counters and cumulative
   training steps, and collect new observations through a fresh isolated
   environment. Record the reset explicitly. Existing checkpoints omit environment,
   rollout and global RNG state: do not claim exact interruption equivalence for
   those legacy artifacts or silently treat their counters as completed updates.
5. Publish checkpoints as content-addressed immutable payloads followed by atomic
   metadata, so interrupted publication cannot pair new weights with old metadata.
   New checkpoints should record rollout/update boundary semantics and required
   RNG state for the supported continuation contract. Fsync parent directory.
6. Refuse a target budget already exhausted; maintain native CPU/memory/wall
   limits and cancellation. Keep validation/final-test identities out of training.
7. Preserve legacy inference and source-aware reproduction, add lineage to model
   details and include resumption provenance in exported scientific evidence.

## Validation and real execution

Tests must cover actual PPO optimizer-state restoration, cumulative counters,
parent immutability, missing/corrupt checkpoints, source/data/configuration drift,
serialization/reload and crash-safe publication. Compare deterministic inference
before continuing, then prove that real optimization occurs after resumption.
State exactly which rollout/environment continuity is supported.

After focused/full regression and frontend gates: run a bounded fresh PPO
training/resumption pair, preserving both artifacts, and evaluate the frozen
result against controls on preregistered fresh groups. Training continuation is
an engineering result; claim policy improvement only if independent evidence
supports it. Preserve existing opened challenge groups rather than tuning to them.

Do not edit source until the cold-retention regression and pilot are terminal.
Complete the cold pilot's actual browser and archive checks first. Prometheus's
remaining calibration, robustness, leagues, migrations and autonomous-planning
objectives remain in scope.
