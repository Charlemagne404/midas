import pytest
from midas.arena.artifacts import atomic_json, sha256

from scripts.reproduce_archived_policy import captured_source


def test_captured_source_checks_payloads_and_ignores_unfinished_jobs(tmp_path):
    atomic_json(tmp_path / "tournaments/tournament-test/manifest.json", {"source_hash": "fixed"})
    atomic_json(tmp_path / "jobs/job-unfinished/job.json", {"result": None})
    directory = tmp_path / "jobs/job-finished"
    atomic_json(
        directory / "job.json",
        {"result": {"tournament_id": "tournament-test"}, "submitted_source_hash": "fixed"},
    )
    payload = directory / "source/packages/midas/example.py"
    payload.parent.mkdir(parents=True)
    payload.write_text("original")
    atomic_json(
        directory / "source-manifest.json",
        {"source_hash": "fixed", "files": {"packages/midas/example.py": sha256(payload)}},
    )
    assert captured_source(tmp_path, "tournament-test") == (directory / "source/packages", "fixed")
    payload.write_text("changed")
    with pytest.raises(ValueError, match="payload"):
        captured_source(tmp_path, "tournament-test")


def test_missing_captured_source_refused(tmp_path):
    atomic_json(tmp_path / "tournaments/tournament-test/manifest.json", {"source_hash": "fixed"})
    with pytest.raises(ValueError, match="No exact"):
        captured_source(tmp_path, "tournament-test")
