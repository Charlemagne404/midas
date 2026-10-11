from midas.arena.datasets import DatasetSpec, build
from midas.arena.quality import analyze


def test_quality_exposes_constant_features_and_family_settlement_shortcuts(tmp_path):
    dataset = build(tmp_path, DatasetSpec(episodes=60))
    report = analyze(tmp_path, dataset["dataset_id"])
    assert report["base_episodes"] == dataset["eligible_base_episodes"]
    assert report["variants"] == dataset["rows"]
    assert "capital_available" in report["constant_features"]
    assert any("parity" in warning for warning in report["warnings"])
    assert all(value["missing"] == 0 for value in report["feature_distributions"].values())
