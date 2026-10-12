import json

import pytest

from scripts import analyze_cost_policy_losses as investigation


def test_investigation_classifies_requested_actions_without_selection(tmp_path, monkeypatch):
    directory = tmp_path / "tournaments" / "challenge"
    directory.mkdir(parents=True)
    manifest = {
        "cost_policy_bindings": {role: {"kind": role} for role in ("forecast", "quoted", "scope")},
        "rows_sha256": "frozen",
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    values = {"forecast": (0, 2), "quoted": (5, 2), "scope": (5, -3)}

    def attribution(root, identity, policy):
        return {
            "episodes": [
                {
                    "base_episode_id": f"group-{i}",
                    "execution_model": "standard",
                    "row_id": f"{policy}-{i}",
                    "net_pnl": str(value),
                }
                for i, value in enumerate(values[policy])
            ]
        }

    monkeypatch.setattr(investigation, "analyze", attribution)

    def replay(path):
        role, index = path.stem.split("-")
        action = 0 if role == "forecast" and index == "0" else 1
        time_ms = 20 if role == "scope" and index == "1" else 10
        return {"decisions": [{"action": action, "time_ms": time_ms}]}

    monkeypatch.setattr(investigation, "read_replay", replay)
    result = investigation.investigate(tmp_path, "challenge")
    quoted = result["requested_action_comparisons"]["quoted"]
    assert quoted["forecast_abstained_control_requested"]["sum_net_difference"] == "-5"
    assert quoted["forecast_abstained_control_requested"]["control_positive_variants"] == 1
    assert quoted["identical_requested_actions"]["sum_net_difference"] == "0"
    scope = result["requested_action_comparisons"]["scope"]
    assert scope["different_requested_actions"]["sum_net_difference"] == "5"
    assert manifest == json.loads((directory / "manifest.json").read_text())
    assert "selection" not in result


def test_investigation_rejects_ambiguous_roles(tmp_path):
    directory = tmp_path / "tournaments" / "challenge"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "cost_policy_bindings": {"a": {"kind": "forecast"}, "b": {"kind": "forecast"}},
            }
        )
    )
    with pytest.raises(ValueError, match="Exactly one"):
        investigation.investigate(tmp_path, "challenge")
