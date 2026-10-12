"""Export a completed director's evidence with a checksummed file manifest."""

import argparse
import importlib.metadata
import io
import json
import os
import platform
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, sha256


def export(root: Path, director_id: str, output: Path) -> dict[str, Any]:
    root = root.resolve()
    directory = artifact_path(root, "directors", director_id)
    director = json.loads((directory / "manifest.json").read_text())
    if director["state"] != "COMPLETED":
        raise ValueError("Only completed plans can be exported as complete experiment bundles")
    paths = set(directory.rglob("*"))
    model_ids = set(director["configuration"]["incumbent_model_ids"])
    for step in director["steps"]:
        if step["state"] != "COMPLETED":
            raise ValueError("Director contains an incomplete stage")
        artifact = step["artifact"]
        path = artifact_path(root, artifact["kind"], artifact["identity"])
        stage = json.loads((path / "manifest.json").read_text())
        if stage.get("state", "COMPLETED") != "COMPLETED":
            raise ValueError("Referenced stage is incomplete")
        if artifact["kind"] == "tournaments" and sha256(path / "rows.json") != stage["rows_sha256"]:
            raise ValueError("Referenced tournament rows have changed")
        paths.update(path.rglob("*"))
        if artifact["kind"] == "sweeps":
            sweep = json.loads((path / "manifest.json").read_text())
            model_ids.update(t["model_id"] for t in sweep["trials"] if t["model_id"])
    for model_id in model_ids:
        model_path = artifact_path(root, "models", model_id)
        model = json.loads((model_path / "manifest.json").read_text())
        weights = model_path / ("policy.zip" if model["family"] == "ppo" else "parameters.json")
        if sha256(weights) != model["artifact_sha256"]:
            raise ValueError("Referenced model weights have changed")
        paths.update(model_path.rglob("*"))
    dataset = artifact_path(root, "datasets", director["configuration"]["dataset_id"])
    dataset_manifest = json.loads((dataset / "manifest.json").read_text())
    if sha256(dataset / "rows.json") != dataset_manifest["rows_sha256"]:
        raise ValueError("Referenced dataset rows have changed")
    if (
        director.get("dataset_sha256", dataset_manifest["rows_sha256"])
        != dataset_manifest["rows_sha256"]
    ):
        raise ValueError("Director dataset provenance differs from referenced dataset")
    paths.update(p for p in dataset.glob("*.json"))
    for job_file in root.glob("jobs/*/job.json"):
        job = json.loads(job_file.read_text())
        if (job.get("result") or {}).get("director_id") == director_id:
            source_manifest = json.loads((job_file.parent / "source-manifest.json").read_text())
            for relative, expected in source_manifest["files"].items():
                relative_path = Path(relative)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError("Invalid captured source path")
                if sha256(job_file.parent / "source" / relative_path) != expected:
                    raise ValueError("Captured source hash mismatch")
            paths.update(job_file.parent.rglob("*"))
    files = sorted(p for p in paths if p.is_file() and not p.is_symlink())
    extras = {
        "ENVIRONMENT/requirements-arena.txt": Path(__file__).resolve().parents[1]
        / "requirements-arena.txt",
        "ENVIRONMENT/pyproject.toml": Path(__file__).resolve().parents[1] / "pyproject.toml",
        "TOOLS/verify_arena.py": Path(__file__).resolve().parent / "verify_arena.py",
        "TOOLS/compare_arena.py": Path(__file__).resolve().parent / "compare_arena.py",
        "ARENA_REPRODUCIBILITY.md": Path(__file__).resolve().parents[1]
        / "docs/ARENA_REPRODUCIBILITY.md",
    }
    record: dict[str, Any] = {
        "bundle_version": "arena-experiment-2",
        "director_id": director_id,
        "created_at": time.time(),
        "files": {str(p.relative_to(root)): sha256(p) for p in files},
        "environment": {
            "python": platform.python_version(),
            "libraries": {
                name: importlib.metadata.version(name)
                for name in (
                    "numpy",
                    "scikit-learn",
                    "torch",
                    "gymnasium",
                    "stable-baselines3",
                    "scipy",
                    "pandas",
                )
            },
        },
        "limitations": [
            "Synthetic hypothetical research only.",
            "Legacy incumbent training source snapshots may not exist; their saved weights and provenance are included.",
            "Native PPO archives require trusted loading and compatible pinned dependencies.",
        ],
    }
    record["files"].update({name: sha256(path) for name, path in extras.items()})
    if output.exists():
        raise ValueError("Refuse to overwrite an existing scientific bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".bundle-", suffix=".tar.gz", dir=output.parent)
    os.close(fd)
    try:
        with tarfile.open(temporary, "w:gz") as archive:
            for path in files:
                archive.add(path, arcname=str(path.relative_to(root)), recursive=False)
            for name, path in extras.items():
                archive.add(path, arcname=name, recursive=False)
            metadata = json.dumps(record, sort_keys=True, indent=2).encode()
            entry = tarfile.TarInfo("BUNDLE_MANIFEST.json")
            entry.size = len(metadata)
            archive.addfile(entry, io.BytesIO(metadata))
        with open(temporary, "rb") as saved:
            os.fsync(saved.fileno())
        # Exclusive publication also protects against a concurrent exporter.
        os.link(temporary, output)
        directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "path": str(output.resolve()),
        "sha256": sha256(output),
        "files": len(files),
        "director_id": director_id,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--director", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.director, args.output), indent=2))
