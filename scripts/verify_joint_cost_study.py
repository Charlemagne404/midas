"""Verify a completed preregistered joint-cost study and its fixed comparisons."""

import argparse
import json
from pathlib import Path

from midas.arena.artifacts import artifact_path, sha256
from midas.arena.cost_policy import CostGateSpec

from scripts.attribute_arena_losses import analyze
from scripts.compare_policies import compare
from scripts.verify_cost_policy import verify


def analyze_study(root: Path, plan: dict, job_id: str) -> dict:
    job_directory = artifact_path(root, "jobs", job_id)
    job = json.loads((job_directory / "job.json").read_text())
    if (
        job["state"] != "COMPLETED"
        or job["configuration"] != plan["configuration"]
        or job["submitted_source_hash"] != plan["source_hash"]
    ):
        raise ValueError("Completed worker differs from preregistration")
    source_manifest = json.loads((job_directory / "source-manifest.json").read_text())
    if source_manifest["source_hash"] != plan["source_hash"] or not source_manifest["files"]:
        raise ValueError("Captured source identity differs from preregistration")
    for relative, expected in source_manifest["files"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid captured source path")
        if sha256(job_directory / "source" / path) != expected:
            raise ValueError("Captured source payload changed")
    identity = job["result"]["tournament_id"]
    directory = artifact_path(root, "tournaments", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest["configuration"] != plan["configuration"]["tournament"]
        or manifest["source_hash"] != plan["source_hash"]
        or manifest["base_episodes"] != plan["source_groups"]
        or manifest["variants"] != plan["correlated_variants"]
        or manifest["research_champion"] is not None
    ):
        raise ValueError("Tournament differs from the fixed nonpromotion design")
    expected_weights = {
        key: value["artifact_sha256"] for key, value in plan["fixed_models"].items()
    }
    if manifest["model_artifact_hashes"] != expected_weights:
        raise ValueError("Tournament weights differ from preregistration")
    for key, frozen in plan["fixed_models"].items():
        model_directory = artifact_path(root, "models", key)
        model = json.loads((model_directory / "manifest.json").read_text())
        if any(model[field] != frozen[field] for field in frozen):
            raise ValueError("Current model provenance changed")
        if sha256(model_directory / "parameters.json") != frozen["artifact_sha256"]:
            raise ValueError("Current model weights changed")
    expected_bindings = {
        policy for condition in plan["controls"].values() for policy in condition.values()
    }
    if set(manifest["cost_policy_bindings"]) != expected_bindings:
        raise ValueError("Policy binding coverage differs from the plan")
    declared = {}
    for configuration in plan["configuration"]["tournament"]["cost_gates"]:
        gate = CostGateSpec.model_validate(configuration)
        for role in ("forecast", "quoted", "scope"):
            declared[gate.identity(role)] = {
                "specification": gate.model_dump(mode="json"),
                "kind": role,
            }
    if manifest["cost_policy_bindings"] != declared:
        raise ValueError("Actual policy parameters differ from preregistration")
    verification = verify(root, identity)

    def resolve(reference: str) -> str:
        if reference == "no_trade":
            return reference
        condition, role = reference.split(".")
        return plan["controls"][condition][role]

    comparisons = []
    for candidate, control in plan["primary_comparisons"]:
        comparisons.append(
            {
                "candidate_reference": candidate,
                "control_reference": control,
                "result": compare(root, identity, resolve(control), resolve(candidate)),
            }
        )
    attributions = {
        condition: {role: analyze(root, identity, policy) for role, policy in roles.items()}
        for condition, roles in plan["controls"].items()
    }
    return {
        "analysis_version": "preregistered-joint-cost-1",
        "producer_sha256": sha256(Path(__file__)),
        "job_id": job_id,
        "tournament_id": identity,
        "preregistration": plan,
        "verification": verification,
        "primary_comparisons": comparisons,
        "accounting_attributions": attributions,
        "research_champion": None,
        "limitations": plan["limitations"]
        + [
            "Paired intervals describe mean P&L; sample tail metrics lack confidence intervals here.",
            "Four preregistered comparisons; no multiplicity correction or promotion decision.",
            "Saved inference verification reuses its implementation and is not an independent broker rerun.",
            "Accounting decomposition is descriptive and does not identify causal effects.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze_study(args.root, json.loads(args.plan.read_text()), args.job_id)
    from scripts.capture_public_series import publish_exclusive

    publish_exclusive(args.output, json.dumps(report, indent=2, allow_nan=False).encode())
    print(
        json.dumps(
            {
                "tournament_id": report["tournament_id"],
                "verification": report["verification"],
                "comparisons": [
                    {
                        "candidate": c["candidate_reference"],
                        "control": c["control_reference"],
                        "mean_change": c["result"]["mean_candidate_minus_control"],
                        "interval": c["result"]["group_bootstrap_mean_interval"],
                    }
                    for c in report["primary_comparisons"]
                ],
            },
            indent=2,
        )
    )
