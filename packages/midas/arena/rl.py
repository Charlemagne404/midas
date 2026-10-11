"""Bounded genuine PPO training with atomic checkpoints and persisted diagnostics."""

import os
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import Field

from midas.arena.artifacts import artifact_path, atomic_json, sha256
from midas.arena.datasets import DatasetSpec, load, partition, research_hash
from midas.arena.environment import ArenaEnv
from midas.core.models import Model
from midas.laboratory.campaigns import revision


class RLSpec(Model):
    dataset_id: str
    seed: int = Field(default=7, ge=0, le=2**32 - 1)
    timesteps: int = Field(default=4096, ge=512, le=100000)
    learning_rate: float = Field(default=0.0003, gt=0, le=0.01, allow_inf_nan=False)
    rollout_steps: int = Field(default=128, ge=64, le=1024, multiple_of=64)
    hidden_size: int = Field(default=32, ge=8, le=128)
    max_wall_seconds: int = Field(default=1800, ge=10, le=7200)


def indices(spec: DatasetSpec, name: str) -> list[int]:
    return [
        i
        for i in range(spec.episodes)
        if partition(f"{spec.families[i % len(spec.families)]}:{spec.seed + i}", spec.split_seed)
        == name
    ]


def save_policy(model: Any, path: Path) -> None:
    temporary = path.with_name(path.stem + ".pending.zip")
    model.save(temporary)
    with temporary.open("rb") as f:
        os.fsync(f.fileno())
    os.replace(temporary, path)


def train_rl(root: Path, spec: RLSpec, progress: Any = None) -> dict[str, Any]:
    import numpy as np
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor

    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    manifest, _ = load(root, spec.dataset_id)
    dataset_spec = DatasetSpec.model_validate(manifest["spec"])
    training_indices = indices(dataset_spec, "train")
    environment: Any = Monitor(
        ArenaEnv(dataset_spec, training_indices, dataset_spec.execution_models)
    )
    identity = "model-" + uuid.uuid4().hex[:24]
    directory = artifact_path(root, "models", identity)
    directory.mkdir(parents=True)
    began = time.monotonic()
    execution_revision = revision()
    source_hash = research_hash()
    atomic_json(
        directory / "training.json",
        {
            "model_id": identity,
            "family": "ppo",
            "state": "TRAINING",
            "dataset_id": spec.dataset_id,
            "configuration": spec.model_dump(mode="json"),
            "created_at": time.time(),
            "validation": None,
            "test": None,
            "artifact_sha256": None,
            "training_duration_seconds": 0,
            "limitations": manifest["limitations"],
            "checkpoints": [],
        },
    )
    register = getattr(progress, "register", None)
    if register:
        register("models", identity)
    curves: list[dict[str, Any]] = []

    class Callback(BaseCallback):
        def _on_step(self) -> bool:
            for info in self.locals["infos"]:
                if "episode" in info:
                    curves.append(
                        {
                            "timesteps": self.num_timesteps,
                            "episode_return": float(info["episode"]["r"]),
                            "episode_length": int(info["episode"]["l"]),
                            "net_simulated_pnl": float(info["net_simulated_pnl"]),
                            "action_counts": info["action_counts"],
                            "reward_penalty": info["reward_penalty"],
                        }
                    )
            if self.num_timesteps % 64 == 0:
                atomic_json(directory / "curves.json", curves)
                if progress:
                    progress(self.num_timesteps, spec.timesteps)
            if self.num_timesteps % 256 == 0:
                save_policy(self.model, directory / "checkpoint.zip")
                atomic_json(
                    directory / "checkpoint-manifest.json",
                    {
                        "timesteps": self.num_timesteps,
                        "artifact_sha256": sha256(directory / "checkpoint.zip"),
                        "configuration": spec.model_dump(mode="json"),
                        "dataset_sha256": manifest["rows_sha256"],
                        "source_hash": source_hash,
                        "resume_note": "PPO optimizer is saved; episode and rollout state reset on resume. Exact mid-rollout continuation is not supported.",
                    },
                )
            return time.monotonic() - began < spec.max_wall_seconds

    model = PPO(
        "MlpPolicy",
        environment,
        seed=spec.seed,
        device="cpu",
        learning_rate=spec.learning_rate,
        n_steps=spec.rollout_steps,
        batch_size=64,
        n_epochs=10,
        policy_kwargs={"net_arch": dict(pi=[spec.hidden_size] * 2, vf=[spec.hidden_size] * 2)},
        verbose=0,
    )
    model.set_logger(configure(str(directory), ["csv"]))
    model.learn(total_timesteps=spec.timesteps, callback=Callback())
    save_policy(model, directory / "policy.zip")
    atomic_json(directory / "curves.json", curves)
    # Reload verification uses the same held-out-free state and deterministic prediction.
    observation, _ = environment.reset(seed=spec.seed)
    restored = PPO.load(directory / "policy.zip", device="cpu")
    original_action, _ = model.predict(observation, deterministic=True)
    restored_action, _ = restored.predict(observation, deterministic=True)
    if not np.array_equal(original_action, restored_action):
        raise ValueError("PPO reload changed deterministic action")
    record = {
        "model_id": identity,
        "family": "ppo",
        "state": "TRAINED",
        "created_at": time.time(),
        "dataset_id": spec.dataset_id,
        "dataset_sha256": manifest["rows_sha256"],
        "configuration": spec.model_dump(mode="json"),
        "source_hash": source_hash,
        "code_revision": execution_revision,
        "artifact_sha256": sha256(directory / "policy.zip"),
        "training_duration_seconds": time.monotonic() - began,
        "timesteps": model.num_timesteps,
        "training_episodes": len(curves),
        "training_episode_mean_return": float(np.mean([c["episode_return"] for c in curves]))
        if curves
        else None,
        "curves": curves,
        "validation": None,
        "test": None,
        "checkpoints": ["checkpoint.zip"],
        "architecture": {
            "algorithm": "Stable-Baselines3 PPO",
            "policy": [spec.hidden_size] * 2,
            "value": [spec.hidden_size] * 2,
            "device": "cpu",
        },
        "reward_definition": "Change in cost-adjusted realized Laboratory P&L minus 0.02*maximum unmatched shares, maximum drawdown ratio, and 0.1 per invalid action",
        "limitations": manifest["limitations"]
        + [
            "Training return is not independent evaluation",
            "Action-dependent execution paths limit common random number pairing",
            "No hedge or unwind actions yet",
        ],
    }
    atomic_json(directory / "manifest.json", record)
    environment.close()
    return record
