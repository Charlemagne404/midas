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
from midas.arena.datasets import load
from midas.economics.attestation import digest


def export(root: Path, director_id: str, output: Path) -> dict[str, Any]:
    return export_experiment(root, "directors", director_id, output)


def export_search(root: Path, search_id: str, output: Path) -> dict[str, Any]:
    from scripts.verify_policy_search import verify_search

    verify_search(root, search_id, full_replays=True)
    return export_experiment(root, "searches", search_id, output)


def export_recovery(root: Path, identity: str, output: Path) -> dict[str, Any]:
    from scripts.verify_recovery import verify

    verify(root, identity)
    return export_experiment(root, "recoveries", identity, output)


def export_unwind(root: Path, identity: str, output: Path) -> dict[str, Any]:
    from scripts.verify_unwind import verify

    verify(root, identity)
    return export_experiment(root, "unwinds", identity, output)


def export_sweep(root: Path, sweep_id: str, output: Path) -> dict[str, Any]:
    manifest = json.loads((artifact_path(root, "sweeps", sweep_id) / "manifest.json").read_text())
    if "ablation" in manifest:
        from scripts.verify_ablations import verify

        verify(root, sweep_id)
    return export_experiment(root, "sweeps", sweep_id, output)


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


def export_cost_study(root: Path, identity: str, output: Path) -> dict[str, Any]:
    from scripts.verify_cost_campaign import study_path, verify

    root = root.resolve()
    verify(root, identity)
    directory = study_path(root, identity)
    plan = json.loads((directory / "plan.json").read_text())
    paths = set(directory.rglob("*"))
    paths.update(dataset_paths(root, plan["dataset_id"]))
    for stage in plan["stages"]:
        paths.update(artifact_path(root, "models", stage["model_id"]).rglob("*"))
    for job_id in [plan["dataset_job_id"]] + [stage["job_id"] for stage in plan["stages"]]:
        paths.update(artifact_path(root, "jobs", job_id).rglob("*"))
    for finding in root.glob("findings/*/manifest.json"):
        if json.loads(finding.read_text()).get("cost_study_id") == identity:
            paths.update(finding.parent.rglob("*"))
    repository = Path(__file__).resolve().parents[1]
    extras = {
        "TOOLS/verify_cost_campaign.py": repository / "scripts/verify_cost_campaign.py",
        "TOOLS/run_cost_campaign.py": repository / "scripts/run_cost_campaign.py",
        "ARENA_EXECUTION_COSTS.md": repository / "docs/ARENA_EXECUTION_COSTS.md",
        "ENVIRONMENT/requirements-arena.txt": repository / "requirements-arena.txt",
        "ENVIRONMENT/pyproject.toml": repository / "pyproject.toml",
    }
    return write_bundle(
        root,
        sorted(p for p in paths if p.is_file() and not p.is_symlink()),
        extras,
        "cost_study_id",
        identity,
        output,
    )


def dataset_paths(root: Path, identity: str) -> set[Path]:
    """Include exact derived observations, parent lineage and stored transform source."""
    paths: set[Path] = set()
    seen: set[str] = set()
    while True:
        if identity in seen:
            raise ValueError("Cyclic dataset derivation")
        seen.add(identity)
        directory = artifact_path(root, "datasets", identity)
        manifest = json.loads((directory / "manifest.json").read_text())
        if sha256(directory / "rows.json") != manifest["rows_sha256"]:
            raise ValueError("Dataset content hash mismatch")
        paths.update(directory.glob("*.json"))
        lineage = manifest.get("derivation")
        if not lineage:
            return paths
        manifest, rows = load(root, identity)
        producer = directory / "derivation-producer.py"
        parent, original = load(root, lineage["source_dataset_id"])
        ignored = {"label", "label_target"}
        if (
            sha256(producer) != lineage["producer_sha256"]
            or parent["rows_sha256"] != lineage["source_rows_sha256"]
            or manifest["label_target"] != lineage["target"]
            or [{k: v for k, v in row.items() if k not in ignored} for row in rows]
            != [{k: v for k, v in row.items() if k not in ignored} for row in original]
        ):
            raise ValueError("Derived dataset lineage changed")
        paths.add(producer)
        identity = lineage["source_dataset_id"]


def export_experiment(root: Path, kind: str, identity: str, output: Path) -> dict[str, Any]:
    root = root.resolve()
    directory = artifact_path(root, kind, identity)
    director = json.loads((directory / "manifest.json").read_text())
    if director.get("state", "COMPLETED" if kind == "tournaments" else None) != "COMPLETED":
        raise ValueError("Only completed plans can be exported as complete experiment bundles")
    paths = set(directory.rglob("*"))
    adaptive = kind == "directors" and director.get("director_version") == "adaptive-latency-1"
    if kind == "directors":
        model_ids = (
            set(director["model_artifact_hashes"])
            if adaptive
            else set(director["configuration"]["incumbent_model_ids"])
        )
        configuration = director["baseline_template"] if adaptive else director["configuration"]
        if adaptive:
            frozen = directory / "preregistration.json"
            if sha256(frozen) != director["preregistration_sha256"]:
                raise ValueError("Adaptive preregistration changed")
            original = json.loads(frozen.read_text())
            mutable = {"state", "cycles", "steps", "current_stage"}
            if any(
                director.get(key) != value for key, value in original.items() if key not in mutable
            ):
                raise ValueError("Adaptive configuration differs from preregistration")
            for source, expected in director["producer_hashes"].items():
                if sha256(directory / "source" / Path(source).name) != expected:
                    raise ValueError("Captured adaptive producer source changed")
            input_path = Path(director["input_study"]["path"]).resolve()
            if (
                not input_path.is_relative_to(root)
                or sha256(input_path) != director["input_study"]["sha256"]
            ):
                raise ValueError("Adaptive input study changed or lies outside its artifact root")
            paths.add(input_path)
            input_study = json.loads(input_path.read_text())
            for condition in input_study["conditions"]:
                input_directory = artifact_path(root, "tournaments", condition["tournament_id"])
                input_manifest = json.loads((input_directory / "manifest.json").read_text())
                if (
                    sha256(input_directory / "rows.json") != condition["rows_sha256"]
                    or input_manifest["model_artifact_hashes"] != director["model_artifact_hashes"]
                ):
                    raise ValueError("Adaptive input condition lineage changed")
                paths.update(input_directory.rglob("*"))
            if len(director["steps"]) != 4 or len(director["cycles"]) != 2:
                raise ValueError("Adaptive plan lacks its complete bounded sequence")
            if len({step.get("job_id") for step in director["steps"]}) != 4 or any(
                not step.get("job_id") for step in director["steps"]
            ):
                raise ValueError("Adaptive stages require four distinct owned jobs")
            if [step["name"] for step in director["steps"]] != [
                step["name"] for step in original["steps"]
            ]:
                raise ValueError("Adaptive step sequence changed")
        steps = director["steps"]
        reference_key = "director_id"
    elif kind == "searches":
        configuration = director["configuration"]
        model_ids = {director["configuration"]["model_id"]}
        steps = [
            {"state": "COMPLETED", "artifact": {"kind": "tournaments", "identity": director[key]}}
            for key in ("validation_tournament", "test_tournament")
        ]
        reference_key = "search_id"
    elif kind in {"recoveries", "unwinds"}:
        configuration = director["configuration"]
        model_ids = set()
        steps = []
        reference_key = "recovery_id" if kind == "recoveries" else "unwind_id"
    elif kind == "sweeps":
        configuration = director["configuration"]
        if any(t["state"] != "COMPLETED" or not t.get("model_id") for t in director["trials"]):
            raise ValueError("Sweep has incomplete fitted candidates")
        model_ids = {trial["model_id"] for trial in director["trials"]}
        steps = []
        reference_key = "sweep_id"
    else:
        configuration = director["configuration"]
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
        if adaptive and (
            stage.get("source_hash") != director["source_hash"]
            or stage.get("model_artifact_hashes") != director["model_artifact_hashes"]
        ):
            raise ValueError("Adaptive stage source or weights changed")
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
        model_dataset = artifact_path(root, "datasets", model["dataset_id"])
        model_data_manifest = json.loads((model_dataset / "manifest.json").read_text())
        if (
            model.get("dataset_sha256", model_data_manifest["rows_sha256"])
            != model_data_manifest["rows_sha256"]
        ):
            raise ValueError("Model training dataset provenance changed")
        paths.update(dataset_paths(root, model["dataset_id"]))
    if kind not in {"recoveries", "unwinds"}:
        dataset = artifact_path(root, "datasets", configuration["dataset_id"])
        dataset_manifest = json.loads((dataset / "manifest.json").read_text())
        if sha256(dataset / "rows.json") != dataset_manifest["rows_sha256"]:
            raise ValueError("Referenced dataset rows have changed")
        if (
            director.get("dataset_sha256", dataset_manifest["rows_sha256"])
            != dataset_manifest["rows_sha256"]
        ):
            raise ValueError("Director dataset provenance differs from referenced dataset")
        paths.update(dataset_paths(root, dataset.name))
    owned_jobs = {step.get("job_id") for step in steps} if adaptive else set()
    for job_file in root.glob("jobs/*/job.json"):
        job = json.loads(job_file.read_text())
        if (job.get("result") or {}).get(reference_key) == identity or job.get(
            "job_id"
        ) in owned_jobs:
            if adaptive and job.get("job_id") in owned_jobs:
                step = next(s for s in steps if s["job_id"] == job["job_id"])
                stage = json.loads(
                    (
                        artifact_path(root, "tournaments", step["artifact"]["identity"])
                        / "manifest.json"
                    ).read_text()
                )
                if (
                    job["state"] != "COMPLETED"
                    or job["result"]["tournament_id"] != stage["tournament_id"]
                    or job["configuration"]["tournament"] != stage["configuration"]
                    or job["submitted_source_hash"] != director["source_hash"]
                ):
                    raise ValueError("Adaptive child job differs from completed stage")
            if kind in {"recoveries", "unwinds"} and (
                job["state"] != "COMPLETED"
                or job["configuration"]["recovery" if kind == "recoveries" else "unwind"]
                != director["configuration"]
                or job["submitted_source_hash"] != director["source_hash"]
            ):
                raise ValueError("Recovery worker differs from completed study")
            source_manifest = json.loads((job_file.parent / "source-manifest.json").read_text())
            for relative, expected in source_manifest["files"].items():
                relative_path = Path(relative)
                if relative_path.is_absolute() or ".." in relative_path.parts:
                    raise ValueError("Invalid captured source path")
                if sha256(job_file.parent / "source" / relative_path) != expected:
                    raise ValueError("Captured source hash mismatch")
            paths.update(job_file.parent.rglob("*"))
            owned_jobs.discard(job.get("job_id"))
    if owned_jobs:
        raise ValueError("Adaptive child job evidence is missing")
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
    if kind == "sweeps" and "ablation" in director:
        extras["TOOLS/verify_ablations.py"] = (
            Path(__file__).resolve().parent / "verify_ablations.py"
        )
        extras["ARENA_FEATURE_ABLATIONS.md"] = (
            Path(__file__).resolve().parents[1] / "docs/ARENA_FEATURE_ABLATIONS.md"
        )
    if kind == "recoveries":
        extras["TOOLS/verify_recovery.py"] = Path(__file__).resolve().parent / "verify_recovery.py"
        extras["ARENA_MISSING_LEG_RECOVERY.md"] = (
            Path(__file__).resolve().parents[1] / "docs/ARENA_MISSING_LEG_RECOVERY.md"
        )
    if kind == "unwinds":
        extras["TOOLS/verify_unwind.py"] = Path(__file__).resolve().parent / "verify_unwind.py"
        extras["ARENA_UNWIND_IMPLEMENTATION_PLAN.md"] = (
            Path(__file__).resolve().parents[1] / "docs/ARENA_UNWIND_IMPLEMENTATION_PLAN.md"
        )
    if kind == "tournaments" and director.get("cost_policy_bindings"):
        for tool in (
            "verify_cost_policy.py",
            "analyze_cost_policy_losses.py",
            "attribute_arena_losses.py",
            "capture_public_series.py",
            "compare_policies.py",
            "verify_joint_cost_study.py",
            "finalize_joint_cost_study.py",
        ):
            extras["TOOLS/" + tool] = Path(__file__).resolve().parent / tool
    return write_bundle(root, files, extras, reference_key, identity, output)


def write_bundle(
    root: Path,
    files: list[Path],
    extras: dict[str, Path],
    reference_key: str,
    identity: str,
    output: Path,
) -> dict[str, Any]:
    """Publish one checksummed archive; all experiment-specific checks precede this."""
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
    experiment.add_argument("--sweep")
    experiment.add_argument("--recovery")
    experiment.add_argument("--unwind")
    experiment.add_argument("--cost-study")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (
        export_unwind(args.root, args.unwind, args.output)
        if args.unwind
        else export_cost_study(args.root, args.cost_study, args.output)
        if args.cost_study
        else export(args.root, args.director, args.output)
        if args.director
        else export_search(args.root, args.search, args.output)
        if args.search
        else export_sweep(args.root, args.sweep, args.output)
        if args.sweep
        else export_recovery(args.root, args.recovery, args.output)
        if args.recovery
        else export_tournament(args.root, args.tournament, args.output)
    )
    print(json.dumps(result, indent=2))
