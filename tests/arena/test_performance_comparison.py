import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, sha256
from midas.economics.attestation import digest

from scripts.compare_performance_replay import compare


def test_comparison_requires_identical_accounting_and_excludes_active_jobs(tmp_path):
    result = {"metrics": {"net_simulated_pnl": "0"}, "passed": True}
    result_hash = digest(result)
    result.update(result_hash=result_hash, journal=[], journal_hash=digest([]))
    row = {
        "id": "one",
        "result_hash": result_hash,
        "scenario_hash": "same",
        "policy_version": "same",
        "metrics": result["metrics"],
        "passed": True,
    }
    for identity, duration in [("original", 4), ("replay", 2)]:
        directory = tmp_path / "tournaments" / identity
        atomic_json(directory / "rows.json", [row])
        atomic_json(
            directory / "manifest.json",
            {
                "duration_seconds": duration,
                "variants": 1,
                "rows_sha256": sha256(directory / "rows.json"),
            },
        )
        atomic_replay(directory / "replays" / "one.json", {"row": row, "result": result})
        atomic_json(
            tmp_path / "jobs" / identity / "job.json",
            {
                "state": "COMPLETED",
                "result": {"tournament_id": identity},
                "configuration": {
                    "tournament": {
                        "purpose": "research" if identity == "original" else "performance_replay"
                    }
                },
            },
        )
    report = compare(tmp_path, "original", "replay")
    assert report["observed_speed_ratio"] == 2
    assert report["matched_variants"] == 1
    atomic_json(tmp_path / "jobs" / "replay" / "job.json", {"state": "RUNNING"})
    with pytest.raises(ValueError, match="completed"):
        compare(tmp_path, "original", "replay")
