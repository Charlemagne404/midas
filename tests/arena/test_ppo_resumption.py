import json
import random

import numpy as np
import pytest
import torch
from midas.arena.artifacts import sha256
from midas.arena.datasets import DatasetSpec, build, research_hash
from midas.arena.rl import RLSpec, train_rl
from midas.arena.rl_checkpoints import parent_checkpoint, publish, restore_rng
from stable_baselines3 import PPO


@pytest.fixture(scope="module")
def parent(tmp_path_factory):
    root = tmp_path_factory.mktemp("ppo-resume")
    dataset = build(root, DatasetSpec(episodes=30, seed=73171))
    spec = RLSpec(
        dataset_id=dataset["dataset_id"], timesteps=512, rollout_steps=64, max_wall_seconds=120
    )
    result = train_rl(root, spec)
    return root, dataset, spec, result


def test_real_resume_preserves_optimizer_and_parent_then_trains(parent, monkeypatch):
    root, _, spec, original = parent
    directory = root / "models" / original["model_id"]
    before = {p.name: sha256(p) for p in directory.iterdir() if p.is_file()}
    metadata = json.loads((directory / "checkpoint-manifest.json").read_text())
    saved = PPO.load(directory / metadata["filename"], device="cpu")
    optimizer = saved.policy.optimizer.state_dict()
    learn = PPO.learn
    observed = []

    def inspect(self, *args, **kwargs):
        current = self.policy.optimizer.state_dict()
        assert self.num_timesteps == 512 and self._n_updates == saved._n_updates
        assert current["param_groups"] == optimizer["param_groups"]
        for key, values in optimizer["state"].items():
            for name, value in values.items():
                assert torch.equal(current["state"][key][name], value)
        observed.append(True)
        return learn(self, *args, **kwargs)

    monkeypatch.setattr(PPO, "learn", inspect)
    child = train_rl(
        root, spec.model_copy(update={"resume_from": original["model_id"], "timesteps": 1024})
    )
    assert observed and child["new_timesteps"] == 512 and child["timesteps"] == 1024
    assert child["new_optimizer_updates"] == 80 and child["optimizer_updates"] == 160
    assert child["lineage"]["parent_model_id"] == original["model_id"]
    assert child["lineage"]["global_rng_restored"]
    assert child["artifact_sha256"] != original["artifact_sha256"]
    assert child["curves"][: len(original["curves"])] == original["curves"]
    assert before == {p.name: sha256(p) for p in directory.iterdir() if p.is_file()}


@pytest.mark.parametrize(
    "change,error",
    [
        ({"seed": 9}, "configuration"),
        ({"timesteps": 512}, "exhausted"),
        ({"rollout_steps": 128}, "configuration"),
    ],
)
def test_resume_rejects_changed_configuration_and_exhausted_budget(parent, change, error):
    root, _, spec, original = parent
    with pytest.raises(ValueError, match=error):
        train_rl(
            root,
            spec.model_copy(
                update={"resume_from": original["model_id"], "timesteps": 1024, **change}
            ),
        )


def test_parent_source_data_and_payload_checks(parent):
    root, dataset, spec, original = parent
    configuration = spec.model_copy(update={"timesteps": 1024}).model_dump(mode="json")
    with pytest.raises(ValueError, match="source or frozen dataset"):
        parent_checkpoint(root, original["model_id"], configuration, "different", research_hash())
    with pytest.raises(ValueError, match="source or frozen dataset"):
        parent_checkpoint(
            root, original["model_id"], configuration, dataset["rows_sha256"], "different"
        )
    directory = root / "models" / original["model_id"]
    metadata = json.loads((directory / "checkpoint-manifest.json").read_text())
    payload = directory / metadata["filename"]
    original_bytes = payload.read_bytes()
    try:
        payload.write_bytes(b"corrupt")
        with pytest.raises(ValueError, match="checksum"):
            parent_checkpoint(
                root, original["model_id"], configuration, dataset["rows_sha256"], research_hash()
            )
    finally:
        payload.write_bytes(original_bytes)


def test_global_rng_checkpoint_roundtrip(parent):
    root, _, _, original = parent
    saved = json.loads(
        (root / "models" / original["model_id"] / "checkpoint-manifest.json").read_text()
    )
    restore_rng(saved)
    first = (random.random(), np.random.random(), torch.rand(3))
    restore_rng(saved)
    second = (random.random(), np.random.random(), torch.rand(3))
    assert first[:2] == second[:2] and torch.equal(first[2], second[2])


def test_failed_checkpoint_publication_preserves_previous_reference(parent, tmp_path, monkeypatch):
    from midas.arena import rl_checkpoints as tool

    root, _, _, original = parent
    directory = root / "models" / original["model_id"]
    saved = json.loads((directory / "checkpoint-manifest.json").read_text())
    model = PPO.load(directory / saved["filename"], device="cpu")
    publish(model, tmp_path, {"boundary": "fixture"})
    before = (tmp_path / "checkpoint-manifest.json").read_bytes()
    with torch.no_grad():
        next(model.policy.parameters()).add_(1)
    monkeypatch.setattr(
        tool,
        "atomic_json",
        lambda *args: (_ for _ in ()).throw(OSError("fixture publication interruption")),
    )
    with pytest.raises(OSError, match="interruption"):
        publish(model, tmp_path, {"boundary": "fixture"})
    assert (tmp_path / "checkpoint-manifest.json").read_bytes() == before
    previous = json.loads(before)
    assert sha256(tmp_path / previous["filename"]) == previous["artifact_sha256"]


def test_interrupted_training_resumes_completed_update_checkpoint(tmp_path):
    data = build(tmp_path, DatasetSpec(episodes=30, seed=73471))
    spec = RLSpec(
        dataset_id=data["dataset_id"], timesteps=512, rollout_steps=64, max_wall_seconds=120
    )

    class Interrupt:
        def register(self, kind, identity):
            self.identity = identity

        def __call__(self, done, total):
            if done == 320:
                raise InterruptedError("fixture worker cancellation")

    observer = Interrupt()
    with pytest.raises(InterruptedError):
        train_rl(tmp_path, spec, observer)
    directory = tmp_path / "models" / observer.identity
    metadata = json.loads((directory / "checkpoint-manifest.json").read_text())
    assert metadata["timesteps"] == 256 and metadata["optimizer_updates"] == 40
    child = train_rl(tmp_path, spec.model_copy(update={"resume_from": observer.identity}))
    assert child["new_timesteps"] == 256 and child["new_optimizer_updates"] == 40
    assert child["timesteps"] == 512


def test_timestep_upper_bound_does_not_overshoot_rollout_rounding(tmp_path):
    data = build(tmp_path, DatasetSpec(episodes=30, seed=73771))
    result = train_rl(
        tmp_path,
        RLSpec(
            dataset_id=data["dataset_id"], timesteps=513, rollout_steps=64, max_wall_seconds=120
        ),
    )
    assert result["timesteps"] == result["effective_target_timesteps"] == 512


def test_resumed_models_expose_checkpoints_and_export_parent_evidence(parent, tmp_path):
    import tarfile

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from midas.arena.tournaments import TournamentSpec, run_tournament

    from apps.api.arena import router
    from scripts.arena_bundle import export_tournament
    from scripts.finalize_joint_cost_study import verify_bundle

    root, _, spec, original = parent
    child = train_rl(
        root, spec.model_copy(update={"resume_from": original["model_id"], "timesteps": 768})
    )
    app = FastAPI()
    app.include_router(router(root))
    with TestClient(app) as client:
        for filename in child["checkpoints"]:
            response = client.get(f"/api/arena/models/{child['model_id']}/artifacts/{filename}")
            assert response.status_code == 200
        detail = client.get(f"/api/arena/models/{child['model_id']}").json()
        assert detail["lineage"]["parent_model_id"] == original["model_id"]
    study = run_tournament(
        root,
        TournamentSpec(
            dataset_id=spec.dataset_id,
            model_ids=(child["model_id"], original["model_id"]),
            max_episodes=2,
            execution_models=("standard",),
        ),
    )
    output = tmp_path / "lineage.tar.gz"
    export_tournament(root, study["tournament_id"], output)
    assert verify_bundle(output) > 12
    with tarfile.open(output) as bundle:
        names = set(bundle.getnames())
        assert f"models/{original['model_id']}/checkpoint-manifest.json" in names
        assert f"models/{child['model_id']}/lineage.json" in names


def test_export_retains_interrupted_parent_without_finished_weights(parent, tmp_path):
    from midas.arena.tournaments import TournamentSpec, run_tournament

    from scripts.arena_bundle import export_tournament
    from scripts.finalize_joint_cost_study import verify_bundle

    root, _, spec, original = parent
    child = train_rl(
        root, spec.model_copy(update={"resume_from": original["model_id"], "timesteps": 768})
    )
    study = run_tournament(
        root,
        TournamentSpec(
            dataset_id=spec.dataset_id,
            model_ids=(child["model_id"],),
            max_episodes=2,
            execution_models=("standard",),
        ),
    )
    manifest = root / "models" / original["model_id"] / "manifest.json"
    saved = manifest.read_bytes()
    try:
        manifest.unlink()
        output = tmp_path / "interrupted-lineage.tar.gz"
        export_tournament(root, study["tournament_id"], output)
        assert verify_bundle(output) > 5
    finally:
        manifest.write_bytes(saved)


def test_wall_stop_before_optimization_does_not_publish_trained_model(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace

    from midas.arena import rl as module

    dataset = build(tmp_path, DatasetSpec(episodes=30, seed=73971))
    clock = [0.0]
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0], time=time.time))

    class Stop:
        def register(self, kind, identity):
            self.identity = identity

        def __call__(self, done, total):
            clock[0] = 1000.0

    observer = Stop()
    with pytest.raises(TimeoutError, match="before any new optimizer update"):
        train_rl(
            tmp_path,
            RLSpec(
                dataset_id=dataset["dataset_id"],
                timesteps=512,
                rollout_steps=64,
                max_wall_seconds=10,
            ),
            observer,
        )
    assert not (tmp_path / "models" / observer.identity / "manifest.json").exists()
