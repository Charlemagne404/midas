"""Export completed directors or policy searches with checksummed evidence."""

import argparse
import hashlib
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

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def export(root: Path, director_id: str, output: Path) -> dict[str, Any]:
    return export_experiment(root, "directors", director_id, output)


def export_search(root: Path, search_id: str, output: Path) -> dict[str, Any]:
    from scripts.verify_policy_search import verify_search

    verify_search(root, search_id, full_replays=True)
    return export_experiment(root, "searches", search_id, output)


def export_tournament(root: Path, identity: str, output: Path) -> dict[str, Any]:
    directory = artifact_path(root, "tournaments", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Tournament rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    if len(rows) != manifest["variants"]:
        raise ValueError("Tournament is incomplete")
    for row in rows:
        replay = read_replay(directory / "replays" / f"{row['id']}.json")
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if (
            replay["row"] != row
            or digest(core) != row["result_hash"]
            or digest(result["journal"]) != result["journal_hash"]
        ):
            raise ValueError("Tournament replay integrity failed")
    return export_experiment(root, "tournaments", identity, output)


def export_experiment(root: Path, kind: str, identity: str, output: Path) -> dict[str, Any]:
    root = root.resolve()
    directory = artifact_path(root, kind, identity)
    director = json.loads((directory / "manifest.json").read_text())
    if director.get("state", "COMPLETED" if kind == "tournaments" else None) != "COMPLETED":
        raise ValueError("Only completed plans can be exported as complete experiment bundles")
    paths = set(directory.rglob("*"))
    if kind == "directors":
        model_ids = set(director["configuration"]["incumbent_model_ids"])
        steps = director["steps"]
        reference_key = "director_id"
    elif kind == "searches":
        model_ids = {director["configuration"]["model_id"]}
        steps = [
            {"state": "COMPLETED", "artifact": {"kind": "tournaments", "identity": director[key]}}
            for key in ("validation_tournament", "test_tournament")
        ]
        reference_key = "search_id"
    else:
        model_ids = set(director["model_artifact_hashes"])
        steps = [{"state": "COMPLETED", "artifact": {"kind": "tournaments", "identity": identity}}]
        reference_key = "tournament_id"
    for step in steps:
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
        if (job.get("result") or {}).get(reference_key) == identity:
            source_manifest = json.loads((job_file.parent / "source-manifest.json").read_text())
            for relative, expected in source_manifest["files"].items():
                relative_path = Path(relative)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError("Invalid captured source path")
                if sha256(job_file.parent / "source" / relative_path) != expected:
                    raise ValueError("Captured source hash mismatch")
            paths.update(job_file.parent.rglob("*"))
    tournament_ids = {
        step["artifact"]["identity"] for step in steps if step["artifact"]["kind"] == "tournaments"
    }
    for finding in root.glob("findings/*/manifest.json"):
        finding_record = json.loads(finding.read_text())
        if (
            finding_record.get(reference_key) == identity
            or finding_record.get("tournament_id") in tournament_ids
        ):
            paths.update(finding.parent.rglob("*"))
    files = sorted(p for p in paths if p.is_file() and not p.is_symlink())
    extras = {
        "ENVIRONMENT/requirements-arena.txt": Path(__file__).resolve().parents[1]
        / "requirements-arena.txt",
        "ENVIRONMENT/pyproject.toml": Path(__file__).resolve().parents[1] / "pyproject.toml",
        "TOOLS/verify_arena.py": Path(__file__).resolve().parent / "verify_arena.py",
        "TOOLS/compare_arena.py": Path(__file__).resolve().parent / "compare_arena.py",
        "TOOLS/verify_policy_search.py": Path(__file__).resolve().parent
        / "verify_policy_search.py",
        "ARENA_REPRODUCIBILITY.md": Path(__file__).resolve().parents[1]
        / "docs/ARENA_REPRODUCIBILITY.md",
    }
    record: dict[str, Any] = {
        "bundle_version": "arena-experiment-3",
        reference_key: identity,
        "created_at": time.time(),
        "files": {},
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
    if output.exists():
        raise ValueError("Refuse to overwrite an existing scientific bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".bundle-", suffix=".tar.gz", dir=output.parent)
    os.close(fd)
    try:
        with tarfile.open(temporary, "w:gz") as archive:
            # Hash and archive the same bytes even if later annotations replace a
            # model manifest concurrently. Only one file payload is held in RAM.
            for name, path in [(str(p.relative_to(root)), p) for p in files] + list(extras.items()):
                payload = path.read_bytes()
                record["files"][name] = hashlib.sha256(payload).hexdigest()
                entry = tarfile.TarInfo(name)
                entry.size = len(payload)
                archive.addfile(entry, io.BytesIO(payload))
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
        reference_key: identity,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    experiment = parser.add_mutually_exclusive_group(required=True)
    experiment.add_argument("--director")
    experiment.add_argument("--search")
    experiment.add_argument("--tournament")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (
        export(args.root, args.director, args.output)
        if args.director
        else export_search(args.root, args.search, args.output)
        if args.search
        else export_tournament(args.root, args.tournament, args.output)
    )
    print(json.dumps(result, indent=2))
