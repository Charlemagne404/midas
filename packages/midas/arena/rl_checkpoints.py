"""Immutable PPO checkpoint payloads and explicit reset-based continuation."""

import json
import os
import random
import re
import tempfile
from pathlib import Path
from typing import Any, cast

from midas.arena.artifacts import artifact_path, atomic_json, sha256

CONTINUATION = "optimizer-preserving-environment-reset"


def publish(model: Any, directory: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import torch

    descriptor, temporary = tempfile.mkstemp(prefix=".ppo-", suffix=".zip", dir=directory)
    os.close(descriptor)
    temporary_path = Path(temporary)
    try:
        model.save(temporary_path)
        with temporary_path.open("rb") as payload:
            os.fsync(payload.fileno())
        checksum = sha256(temporary_path)
        filename = f"checkpoint-{checksum}.zip"
        target = directory / filename
        if target.exists():
            if target.is_symlink() or sha256(target) != checksum:
                raise ValueError("Existing PPO checkpoint differs")
        else:
            os.link(temporary_path, target)
        fd = os.open(directory, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        numpy_state = cast(tuple[Any, ...], np.random.get_state())
        record = {
            **metadata,
            "checkpoint_version": "ppo-checkpoint-2",
            "filename": filename,
            "artifact_sha256": checksum,
            "timesteps": model.num_timesteps,
            "optimizer_updates": model._n_updates,
            "continuation_mode": CONTINUATION,
            "rng": {
                "python": random.getstate(),
                "torch": torch.get_rng_state().tolist(),
                "numpy": [numpy_state[0], numpy_state[1].tolist(), *numpy_state[2:]],
            },
            "resume_note": "Saved policy/optimizer and global RNG resume; environment and rollout reset. No exact trajectory equivalence is claimed.",
        }
        atomic_json(directory / "checkpoint-manifest.json", record)
        return record
    finally:
        temporary_path.unlink(missing_ok=True)


def parent_checkpoint(
    root: Path, identity: str, configuration: dict[str, Any], dataset_hash: str, source_hash: str
) -> tuple[Path, dict[str, Any]]:
    directory = artifact_path(root, "models", identity)
    record_path = directory / "manifest.json"
    if not record_path.exists():
        record_path = directory / "training.json"
    parent = json.loads(record_path.read_text())
    if parent.get("family") != "ppo" or parent.get("model_id") != identity:
        raise ValueError("Parent must be a registered PPO artifact")
    saved = json.loads((directory / "checkpoint-manifest.json").read_text())
    if saved["source_hash"] != source_hash or saved["dataset_sha256"] != dataset_hash:
        raise ValueError("PPO checkpoint source or frozen dataset changed")
    allowed = {"resume_from", "timesteps", "max_wall_seconds"}
    if {k: v for k, v in saved["configuration"].items() if k not in allowed} != {
        k: v for k, v in configuration.items() if k not in allowed
    }:
        raise ValueError("PPO checkpoint training configuration changed")
    version = saved.get("checkpoint_version")
    if version not in {None, "ppo-checkpoint-2"}:
        raise ValueError("Unsupported PPO checkpoint version")
    if version == "ppo-checkpoint-2" and (
        saved.get("boundary") != "completed-optimizer-update"
        or saved.get("continuation_mode") != CONTINUATION
        or not saved.get("rng")
        or saved.get("optimizer_updates", -1) < 0
        or any(
            c.get("timesteps", -1) < 0 or c["timesteps"] > saved["timesteps"]
            for c in saved.get("curves", [])
        )
    ):
        raise ValueError("PPO checkpoint continuation metadata differs")
    filename = saved.get("filename", "checkpoint.zip")
    if not re.fullmatch(r"checkpoint(?:-[a-f0-9]{64})?\.zip", filename):
        raise ValueError("Invalid PPO checkpoint filename")
    path = directory / filename
    if path.is_symlink() or sha256(path) != saved["artifact_sha256"]:
        raise ValueError("PPO checkpoint checksum differs")
    if configuration["timesteps"] <= saved["timesteps"]:
        raise ValueError("PPO total timestep budget is already exhausted")
    return path, saved


def restore_rng(saved: dict[str, Any]) -> None:
    import numpy as np
    import torch

    if "rng" not in saved:
        return

    def tuples(value: Any) -> Any:
        return tuple(tuples(v) for v in value) if isinstance(value, list) else value

    random.setstate(tuples(saved["rng"]["python"]))
    torch.set_rng_state(torch.tensor(saved["rng"]["torch"], dtype=torch.uint8))
    values = saved["rng"]["numpy"]
    np.random.set_state((values[0], np.array(values[1], dtype=np.uint32), *values[2:]))
