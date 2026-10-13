# PPO checkpoint continuation

PPO jobs accept an optional `rl.resume_from` parent model ID. The requested
`timesteps` is a cumulative upper bound across parent and child; only complete
additional rollouts that fit inside that bound are admitted. There must be room
for at least one rollout. Other optimizer, architecture, seed and environment
configuration must match. A new artifact preserves the parent evidence.

Example configuration (use an actual compatible parent):

```json
{
  "kind": "rl",
  "rl": {
    "dataset_id": "dataset-ID",
    "resume_from": "model-PARENT",
    "seed": 7,
    "timesteps": 4096,
    "rollout_steps": 128,
    "hidden_size": 32,
    "learning_rate": 0.0003,
    "max_wall_seconds": 1800
  }
}
```

Native jobs retain their existing CPU/memory/wall/storage guards. Dataset/source
and checkpoint hashes are checked before loading locally trusted PPO archives.
Source changes deliberately block continuation; this is not a schema migration
or permission to silently resume an older simulator. Parent checkpoint payloads
and manifests remain unchanged.

## Supported semantics

Saved policy weights, Adam optimizer state/counters, cumulative transition
counters, and Python/NumPy/Torch global RNG are restored. The environment and
rollout buffer reset. New collection proceeds through the same training-only
episode identities. This is `optimizer-preserving-environment-reset`, not exact
trajectory equivalence with an uninterrupted run.

Version-2 checkpoints record completed optimizer-update boundaries and retain
the exact curves available there. Legacy checkpoints did not save global RNG or
rollout state: where source/configuration compatibility is established, their
reset/discard semantics are explicitly recorded. Legacy inference is unchanged.

Checkpoint archives are named by their byte checksum. File and directory are
fsynced before atomic metadata publication. Failed publication leaves the
previous reference intact; an unreferenced payload can remain for later inspection.
There is no automatic checkpoint deletion. Final policy archives remain available
under `policy.zip` for existing inference consumers.

## Evidence and interface

Training records expose parent identity/checkpoint hash, prior transitions,
initial/new optimizer updates, new transitions and effective total budget.
Model details show lineage and link to parent evidence. Checkpoint payloads and
metadata can be downloaded through the existing artifact endpoint with confined
filenames. Scientific exports traverse parent lineage, verify parent checkpoints,
and preserve finished or interrupted parent records and native source evidence.

Implementation tests compare actual loaded optimizer tensors before continuing,
prove further real optimization, preserve parent file hashes, restore global RNG,
reject drift/corruption/exhausted budgets, recover from interrupted training, and
check API/download/export paths. Production training and fresh policy evaluation
remain a separate gate; successful continuation alone is not strategy improvement.
