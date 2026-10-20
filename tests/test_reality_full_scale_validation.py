"""Disposable fixture verification of the deferred full-store procedure."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from midas.reality import recovery
from midas.reality.storage import Store

from scripts import reality_full_scale_validation as validation


def fixture(tmp_path):
    source = tmp_path / "source"
    store = Store(source, reserve=1)
    store.append("gap", {"reason": "synthetic_one"})
    store.append("gap", {"reason": "synthetic_two"})
    store.close()
    return source


def test_inventory_pins_finalized_only_without_claiming_hash_verification(tmp_path):
    source = fixture(tmp_path)
    (source / "00000000000000000003-active.open").write_bytes(b"active")
    catalog, identities, summary = validation.inventory(source)
    assert len(catalog["segments"]) == len(identities) == 1
    assert summary["last_ordinal"] == 2
    assert summary["kinds"]["gap"] == 2
    assert summary["excluded_open"][0]["observed_bytes"] == 6
    assert "NOT yet verified" in summary["scope"]


def test_inventory_rejects_missing_sidecar_inside_boundary(tmp_path):
    source = fixture(tmp_path)
    (source / "00000000000000000001-orphan.seg").write_bytes(b"bad")
    with pytest.raises(ValueError, match="without sidecar"):
        validation.inventory(source)


def test_failed_admission_does_not_create_snapshot(tmp_path, monkeypatch):
    source = fixture(tmp_path)
    output = tmp_path / "never-created"

    def reject():
        raise ValueError("resource gate")

    monkeypatch.setattr(validation, "admission", reject)
    with pytest.raises(ValueError, match="resource gate"):
        validation.run(source, output)
    assert not output.exists()


def test_recovery_matrix_and_real_interruption_preserve_source(tmp_path):
    source = fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    catalog, _, _ = validation.inventory(source)
    view = tmp_path / "view"
    view.mkdir()
    validation.write(tmp_path / "catalog.json", catalog)
    for info in catalog["segments"]:
        (view / info["file"]).symlink_to(source / info["file"])
    expected = None
    environment = dict(os.environ)
    candidate_packages = str(Path(recovery.__file__).resolve().parents[2])
    environment["PYTHONPATH"] = candidate_packages + os.pathsep + environment.get("PYTHONPATH", "")
    for phase in ("cold", "fast", "restart", "corrupt", "stale", "interrupt",
                  "after_interrupt", "interrupt_save", "after_interrupt_save"):
        process = subprocess.run([sys.executable, str(Path(validation.__file__).resolve()),
                                  "worker", "--source", str(view), "--phase", phase],
                                 capture_output=True, text=True, env=environment, timeout=20)
        if phase in ("interrupt", "interrupt_save"):
            assert process.returncode == -9, process.stderr
            continue
        assert process.returncode == 0, process.stderr
        result = json.loads((tmp_path / f"{phase}.json").read_text())
        if expected is None:
            expected = result["internal_sha256"]
            (tmp_path / "valid.checkpoint").write_bytes((view / recovery.CHECKPOINT_NAME).read_bytes())
        assert result["internal_sha256"] == expected
        assert result["ordinal"] == result["gaps"] == 2
        if phase in ("fast", "restart", "after_interrupt_save"):
            assert result["recovery"]["segments_reconstructed"] == 0
        if phase in ("corrupt", "stale", "after_interrupt"):
            assert result["recovery"]["mode"] == "full_replay"
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}
