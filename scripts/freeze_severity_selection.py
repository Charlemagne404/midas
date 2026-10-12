"""Export the verified pre-test severity selection before opening held-out outcomes."""

import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, sha256

from scripts.capture_public_series import publish_exclusive
from scripts.compare_severity_models import compare


def freeze(root: Path, selection_path: Path, plan_path: Path, output: Path) -> dict[str, Any]:
    selection = json.loads(selection_path.read_text())
    plan = json.loads(plan_path.read_text())
    if compare(root, selection["job_ids"], plan) != selection:
        raise ValueError("Saved pre-test selection differs from verified inputs")
    paths: dict[str, Path] = {
        "PLAN.json": plan_path,
        "SELECTION.json": selection_path,
        "TOOLS/compare_severity_models.py": Path(__file__).with_name("compare_severity_models.py"),
        "ENVIRONMENT/requirements-arena.txt": Path("requirements-arena.txt"),
    }
    for model in selection["models"]:
        directory = artifact_path(root, "models", model["model_id"])
        for p in directory.glob("*"):
            if p.is_file():
                paths[str(Path("EVIDENCE") / p.relative_to(root))] = p
    for identity in selection["job_ids"]:
        for p in artifact_path(root, "jobs", identity).rglob("*"):
            if p.is_file() and not p.is_symlink():
                paths[str(Path("EVIDENCE") / p.relative_to(root))] = p
    directory = artifact_path(root, "datasets", plan["dataset_id"])
    for p in directory.glob("*.json"):
        paths[str(Path("EVIDENCE") / p.relative_to(root))] = p
    buffer = io.BytesIO()
    hashes = {}
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, path in sorted(paths.items()):
            data = path.read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(
            {"files": hashes, "scope": "Pre-test severity fit selection, not policy promotion"},
            sort_keys=True,
        ).encode()
        info = tarfile.TarInfo("BUNDLE_MANIFEST.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    publish_exclusive(output, buffer.getvalue())
    return {
        "path": str(output.resolve()),
        "sha256": sha256(output),
        "files": len(paths),
        "selected_model_id": selection["selected_model_id"],
        "all_final_tests_unopened": True,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument(
        "--selection", type=Path, default=Path("docs/PROMETHEUS_SEVERITY_SELECTION.json")
    )
    parser.add_argument(
        "--plan", type=Path, default=Path("docs/PROMETHEUS_SEVERITY_PREREGISTRATION.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.root, args.selection, args.plan, args.output), indent=2))
