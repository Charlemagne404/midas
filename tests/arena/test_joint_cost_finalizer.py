import hashlib
import io
import json
import tarfile

import pytest

from scripts import finalize_joint_cost_study as finisher
from scripts.finalize_joint_cost_study import finalize, verify_bundle


@pytest.mark.parametrize("corruption", [None, "changed", "missing", "duplicate"])
def test_finalizer_bundle_verification(tmp_path, corruption):
    payload = b"scientific evidence"
    manifest = {"files": {"evidence.json": hashlib.sha256(payload).hexdigest()}}
    path = tmp_path / "bundle.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        entries = [("BUNDLE_MANIFEST.json", json.dumps(manifest).encode())]
        if corruption != "missing":
            entries.append(("evidence.json", b"changed" if corruption == "changed" else payload))
        if corruption == "duplicate":
            entries.append(("evidence.json", payload))
        for name, content in entries:
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))
    if corruption is None:
        assert verify_bundle(path) == 1
    else:
        with pytest.raises(ValueError):
            verify_bundle(path)


def test_finalizer_preserves_failure_and_refuses_blind_retry(tmp_path):
    job = tmp_path / "jobs" / "job-test"
    job.mkdir(parents=True)
    (job / "job.json").write_text(json.dumps({"state": "FAILED"}))
    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    with pytest.raises(ValueError, match="did not complete"):
        finalize(tmp_path, plan, "job-test", tmp_path / "never-exported.tar.gz", 60)
    state = json.loads((job / "post-study-state.json").read_text())
    assert state["phase"] == "FAILED"
    assert state["tool_hashes"]
    with pytest.raises(ValueError, match="inspection"):
        finalize(tmp_path, plan, "job-test", tmp_path / "never-exported.tar.gz", 60)
    assert not (tmp_path / "never-exported.tar.gz").exists()


def test_finalizer_publishes_finding_and_verified_bundle(tmp_path, monkeypatch):
    job = tmp_path / "jobs" / "job-test"
    job.mkdir(parents=True)
    (job / "job.json").write_text(json.dumps({"state": "COMPLETED"}))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"hypothesis": "Fixed comparison", "source_groups": 2}))
    report = {
        "tournament_id": "tournament-test",
        "primary_comparisons": [],
        "verification": {"replays_verified": 78},
        "limitations": ["synthetic"],
    }
    monkeypatch.setattr(finisher, "analyze_study", lambda *_: report)
    monkeypatch.setattr(finisher, "artifact_usage", lambda *_: (0, 0))

    def export(root, identity, output):
        paths = [
            root / "tournaments" / identity / "analyses" / "joint-cost-study.json",
            *root.glob("findings/*/manifest.json"),
        ]
        files = {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths
        }
        with tarfile.open(output, "w:gz") as archive:
            for path in paths:
                archive.add(path, arcname=str(path.relative_to(root)))
            metadata = json.dumps({"files": files}).encode()
            entry = tarfile.TarInfo("BUNDLE_MANIFEST.json")
            entry.size = len(metadata)
            archive.addfile(entry, io.BytesIO(metadata))
        return {"path": str(output)}

    monkeypatch.setattr(finisher, "export_tournament", export)
    state = finalize(tmp_path, plan, "job-test", tmp_path / "evidence.tar.gz", 60)
    assert state["phase"] == "VERIFIED" and state["payloads_verified"] == 2
    finding = json.loads(next(tmp_path.glob("findings/*/manifest.json")).read_text())
    assert "2 fresh synthetic" in finding["interpretation"]
    assert finding["outcome"]["verification"] == report["verification"]
