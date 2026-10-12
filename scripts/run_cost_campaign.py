"""Bounded durable coordinator: await a fixed dataset and fit three registered regressors."""

import argparse
import fcntl
import json
import time
from pathlib import Path

from midas.arena.artifacts import atomic_json, sha256
from midas.arena.costs import CostSpec
from midas.arena.datasets import research_hash
from midas.arena.jobs import JobSpec, create, inspect


def run(root: Path, plan_file: Path) -> None:
    with plan_file.with_suffix(".lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = json.loads(plan_file.read_text())
        if plan["state"] == "COMPLETED":
            return
        if (
            research_hash() != plan["source_hash"]
            or sha256(Path(__file__)) != plan["producer_sha256"]
        ):
            raise ValueError("Frozen campaign producer or research source changed")
        deadline = time.monotonic() + 7000
        plan["state"] = "RUNNING"
        atomic_json(plan_file, plan)
        try:
            dataset = inspect(root, plan["dataset_job_id"])
            while dataset["state"] in {"RUNNING", "QUEUED"}:
                if time.monotonic() > deadline:
                    raise TimeoutError("Campaign wall limit")
                plan["dataset_progress"] = dataset.get("progress")
                plan["updated_at"] = time.time()
                atomic_json(plan_file, plan)
                time.sleep(3)
                dataset = inspect(root, plan["dataset_job_id"])
            if dataset["state"] != "COMPLETED":
                raise ValueError(f"Dataset job ended {dataset['state']}: {dataset.get('error')}")
            if dataset["submitted_source_hash"] != plan["source_hash"]:
                raise ValueError("Dataset job source differs from frozen campaign")
            dataset_id = dataset["result"]["dataset_id"]
            dataset_manifest = json.loads(
                (root / "datasets" / dataset_id / "manifest.json").read_text()
            )
            if (
                dataset_manifest["source_hash"] != plan["source_hash"]
                or dataset_manifest["spec"] != dataset["configuration"]["dataset"]
            ):
                raise ValueError("Dataset output differs from its admitted job")
            plan["dataset_id"] = dataset_id
            for index, candidate in enumerate(plan["models"]):
                configuration = JobSpec(
                    kind="cost",
                    cost=CostSpec(
                        dataset_id=dataset_id, **plan["training_configuration"], **candidate
                    ),
                    max_wall_seconds=1800,
                ).model_dump(mode="json")
                stage = plan["stages"][index]
                if not stage.get("job_id"):
                    # Persist an intent before job admission; on recovery adopt one
                    # matching owned-time/source/config record or stop if ambiguous.
                    if not stage.get("intent_created"):
                        stage.update(
                            intent_created=time.time(),
                            configuration=configuration,
                            state="SUBMITTING",
                        )
                        atomic_json(plan_file, plan)
                    if stage["configuration"] != configuration:
                        raise ValueError("Stage configuration changed")
                    matches = []
                    for file in (root / "jobs").glob("*/job.json"):
                        existing = json.loads(file.read_text())
                        if (
                            existing["created_at"] >= stage["intent_created"]
                            and existing["submitted_source_hash"] == plan["source_hash"]
                            and existing["configuration"] == configuration
                        ):
                            matches.append(existing)
                    if len(matches) > 1:
                        raise ValueError("Ambiguous admission; no duplicate job created")
                    job = (
                        matches[0]
                        if matches
                        else create(root, JobSpec.model_validate(configuration))
                    )
                    stage.update(job_id=job["job_id"], state=job["state"])
                    atomic_json(plan_file, plan)
                job = inspect(root, stage["job_id"])
                while job["state"] in {"QUEUED", "RUNNING"}:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Campaign wall limit")
                    stage.update(state=job["state"], progress=job.get("progress"))
                    plan["updated_at"] = time.time()
                    atomic_json(plan_file, plan)
                    time.sleep(3)
                    job = inspect(root, stage["job_id"])
                if job["state"] != "COMPLETED":
                    raise ValueError(f"Training ended {job['state']}: {job.get('error')}")
                model_id = job["result"]["model_id"]
                model = json.loads((root / "models" / model_id / "manifest.json").read_text())
                if (
                    model["source_hash"] != plan["source_hash"]
                    or model["test"] is not None
                    or model["configuration"] != configuration["cost"]
                    or sha256(root / "models" / model_id / "parameters.json")
                    != model["artifact_sha256"]
                ):
                    raise ValueError("Model provenance or test status differs")
                stage.update(
                    state="COMPLETED",
                    model_id=model_id,
                    validation=model["validation"],
                    artifact_sha256=model["artifact_sha256"],
                )
                atomic_json(plan_file, plan)
            ridge = plan["stages"][0]
            neural = plan["stages"][1:]
            neural_rmse = sum(s["validation"]["episode_rmse"] for s in neural) / len(neural)
            chosen = (
                ridge
                if ridge["validation"]["episode_rmse"] <= neural_rmse + 0.005
                else min(neural, key=lambda s: s["validation"]["episode_rmse"])
            )
            plan.update(
                state="COMPLETED",
                completed_at=time.time(),
                selection={
                    "model_id": chosen["model_id"],
                    "ridge_validation_rmse": ridge["validation"]["episode_rmse"],
                    "mean_neural_validation_rmse": neural_rmse,
                    "partition": "validation",
                    "criterion": plan["selection_rule"],
                    "test_evaluated": False,
                },
            )
            atomic_json(plan_file, plan)
            print(
                json.dumps(
                    {
                        "state": plan["state"],
                        "dataset_id": dataset_id,
                        "selection": plan["selection"],
                    }
                ),
                flush=True,
            )
        except Exception as error:
            plan.update(
                state="INTERRUPTED" if isinstance(error, TimeoutError) else "FAILED",
                error=str(error),
                updated_at=time.time(),
            )
            atomic_json(plan_file, plan)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.plan.resolve())
