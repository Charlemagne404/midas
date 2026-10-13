import json

import pytest

from scripts.finalize_ppo_resumption_study import finalize


def test_prior_finalization_refuses_duplicate_export(tmp_path):
    state = tmp_path / "ppo-resumption-studies/study-573071/post-study-state.json"
    state.parent.mkdir(parents=True)
    state.write_text("{}")
    with pytest.raises(ValueError, match="duplicate export"):
        finalize(tmp_path, tmp_path / "missing-plan.json", tmp_path / "output.json")


def test_running_study_cannot_be_finalized(tmp_path):
    state = tmp_path / "ppo-resumption-studies/study-573071/state.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"phase": "RESEARCHING", "jobs": []}))
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    with pytest.raises(ValueError, match="terminal"):
        finalize(tmp_path, plan, tmp_path / "output.json")
    assert not (state.parent / "post-study-state.json").exists()
