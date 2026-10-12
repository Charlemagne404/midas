import json

import pytest

from scripts import verify_joint_cost_study as study


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    plain = study.CostGateSpec(model_id="model-cost")
    support = study.CostGateSpec(
        model_id="model-cost", completion_model_id="model-completion", completion_threshold=0
    )
    joint = support.model_copy(update={"completion_threshold": 0.9})
    gates = {"plain": plain, "support": support, "joint": joint}
    controls = {
        condition: {role: gate.identity(role) for role in ("forecast", "quoted", "scope")}
        for condition, gate in gates.items()
    }
    fixed = {}
    for key in ("model-cost", "model-completion"):
        directory = tmp_path / "models" / key
        save(directory / "parameters.json", {"weights": [1]})
        fixed[key] = {
            "artifact_sha256": study.sha256(directory / "parameters.json"),
            "dataset_id": "dataset-original",
            "dataset_sha256": "data-hash",
        }
        save(directory / "manifest.json", fixed[key])
    plan = {
        "configuration": {
            "tournament": {"cost_gates": [gate.model_dump(mode="json") for gate in gates.values()]}
        },
        "source_hash": "source-hash",
        "source_groups": 2,
        "correlated_variants": 78,
        "fixed_models": fixed,
        "controls": controls,
        "primary_comparisons": [["joint.scope", "support.scope"], ["joint.forecast", "no_trade"]],
        "limitations": ["synthetic"],
    }
    job = tmp_path / "jobs" / "job-test"
    save(
        job / "job.json",
        {
            "state": "COMPLETED",
            "configuration": plan["configuration"],
            "submitted_source_hash": plan["source_hash"],
            "result": {"tournament_id": "tournament-test"},
        },
    )
    save(job / "source" / "code.py", {"source": "frozen"})
    save(
        job / "source-manifest.json",
        {
            "source_hash": plan["source_hash"],
            "files": {"code.py": study.sha256(job / "source" / "code.py")},
        },
    )
    manifest = {
        "configuration": plan["configuration"]["tournament"],
        "source_hash": plan["source_hash"],
        "base_episodes": 2,
        "variants": 78,
        "research_champion": None,
        "model_artifact_hashes": {key: value["artifact_sha256"] for key, value in fixed.items()},
        "cost_policy_bindings": {
            gate.identity(role): {"specification": gate.model_dump(mode="json"), "kind": role}
            for gate in gates.values()
            for role in ("forecast", "quoted", "scope")
        },
    }
    save(tmp_path / "tournaments" / "tournament-test" / "manifest.json", manifest)
    calls = []
    monkeypatch.setattr(study, "verify", lambda *_: {"replays_verified": 78})

    def comparison(root, identity, control, candidate):
        calls.append((control, candidate))
        return {"control": control, "candidate": candidate}

    monkeypatch.setattr(study, "compare", comparison)
    monkeypatch.setattr(study, "analyze", lambda root, identity, policy: {"policy": policy})
    return tmp_path, plan, calls


def test_verifier_preserves_preregistered_comparison_order(frozen):
    root, plan, calls = frozen
    result = study.analyze_study(root, plan, "job-test")
    assert calls == [
        (plan["controls"]["support"]["scope"], plan["controls"]["joint"]["scope"]),
        ("no_trade", plan["controls"]["joint"]["forecast"]),
    ]
    assert result["preregistration"] == plan
    assert len(result["accounting_attributions"]) == 3
    assert result["research_champion"] is None


@pytest.mark.parametrize("payload", ["source", "weights", "configuration", "binding"])
def test_verifier_rejects_changed_evidence_before_comparison(frozen, payload):
    root, plan, calls = frozen
    if payload == "source":
        (root / "jobs" / "job-test" / "source" / "code.py").write_text("changed")
    elif payload == "weights":
        (root / "models" / "model-cost" / "parameters.json").write_text("changed")
    elif payload == "binding":
        path = root / "tournaments" / "tournament-test" / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["cost_policy_bindings"][plan["controls"]["joint"]["scope"]]["specification"][
            "completion_threshold"
        ] = 0.7
        path.write_text(json.dumps(manifest))
    else:
        plan["configuration"] = {"tournament": {"retuned": True}}
    with pytest.raises(ValueError):
        study.analyze_study(root, plan, "job-test")
    assert calls == []
