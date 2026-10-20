import json

import pytest
from midas.arena import director
from midas.arena.director import DirectorSpec


class Cancelled(Exception):
    pass


class Progress:
    job_id = "job-0123456789abcdef01234567"

    def __call__(self, done: int, total: int) -> None:
        pass

    def phase(self, name: str) -> None:
        pass

    def register(self, kind: str, artifact_id: str) -> None:
        pass


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (Cancelled("operator requested stop"), "CANCELLED"),
        (InterruptedError("worker stopped"), "INTERRUPTED"),
        (RuntimeError("stage failed"), "FAILED"),
    ],
)
def test_director_publishes_terminal_state_when_owned_job_stops(
    tmp_path, monkeypatch, error, expected_state
):
    monkeypatch.setattr(
        director,
        "load",
        lambda root, identity: (
            {
                "rows_sha256": "a" * 64,
                "label_target": "completion",
                "spec": {"observation_latency_ms": 100},
            },
            None,
        ),
    )
    monkeypatch.setattr(director, "research_hash", lambda: "b" * 64)
    monkeypatch.setattr(director, "revision", lambda: "c" * 40)

    def fail_sweep(*args, **kwargs):
        raise error

    monkeypatch.setattr(director, "run_sweep", fail_sweep)
    spec = DirectorSpec(dataset_id="dataset-fixture")

    with pytest.raises(type(error)):
        director.run_director(tmp_path, spec, Progress())

    manifests = list((tmp_path / "directors").glob("*/manifest.json"))
    assert len(manifests) == 1
    record = json.loads(manifests[0].read_text())
    assert record["state"] == expected_state
    assert record["owner_job_id"] == Progress.job_id
    assert record["last_error"] == f"{type(error).__name__}: {error}"
    assert record["steps"][0]["state"] == expected_state
    assert record["steps"][0].get("progress") is None


def test_director_retry_resumes_cancelled_step_and_publishes_completed_state(tmp_path, monkeypatch):
    monkeypatch.setattr(
        director,
        "load",
        lambda root, identity: (
            {
                "rows_sha256": "a" * 64,
                "label_target": "completion",
                "spec": {"observation_latency_ms": 100},
            },
            None,
        ),
    )
    monkeypatch.setattr(director, "research_hash", lambda: "b" * 64)
    monkeypatch.setattr(director, "revision", lambda: "c" * 40)
    spec = DirectorSpec(dataset_id="dataset-fixture")
    monkeypatch.setattr(
        director,
        "run_sweep",
        lambda *args, **kwargs: {
            "sweep_id": "sweep-fixture",
            "selection": {"selected_model_id": "model-fixture"},
        },
    )
    monkeypatch.setattr(
        director,
        "run_tournament",
        lambda *args, **kwargs: {
            "tournament_id": "tournament-fixture",
            "conclusion": "Synthetic fixture complete.",
        },
    )
    identity_hash = director.digest([spec.model_dump(mode="json"), "a" * 64, "b" * 64])[:24]
    record_path = tmp_path / "directors" / f"director-{identity_hash}" / "manifest.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        json.dumps(
            {
                "director_id": f"director-{identity_hash}",
                "state": "CANCELLED",
                "created_at": 1,
                "code_revision": "c" * 40,
                "source_hash": "b" * 64,
                "dataset_sha256": "a" * 64,
                "label_target": "completion",
                "configuration": spec.model_dump(mode="json"),
                "research_question": "Test cancelled director resume.",
                "hypothesis": "A stopped stage resumes without changing completed evidence.",
                "steps": [
                    {
                        "name": name,
                        "state": "CANCELLED" if index == 0 else "PENDING",
                        "artifact": None,
                    }
                    for index, name in enumerate(
                        (
                            "validation-only multi-seed selection",
                            "fresh challenge with support warnings",
                            "matched challenge with support abstention",
                        )
                    )
                ],
                "current_stage": "validation-only multi-seed selection",
                "last_error": "Cancelled: previous attempt stopped",
                "stopped_at": 2,
            }
        )
    )

    record = director.run_director(tmp_path, spec, Progress())

    assert record["state"] == "COMPLETED"
    assert record["owner_job_id"] == Progress.job_id
    assert record["resumed_from_state"] == "CANCELLED"
    assert record["current_stage"] is None
    assert all(step["state"] == "COMPLETED" for step in record["steps"])
    assert not record.get("last_error")
