import gzip
import io
import json
import tarfile

import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, sha256
from midas.economics.attestation import digest

from scripts.archive_replays import archive
from scripts.pack_replays import pack, prune
from scripts.verify_cold_retention import verify


def setup(tmp_path):
    root = tmp_path / "arena"
    root.mkdir()
    study = root / "tournaments/tournament-fixture"
    core = {"passed": True, "complete": True, "metrics": {"fixture": 1}}
    journal = [{"kind": "fixture", "amount": "1.00"}]
    result = {
        **core,
        "result_hash": digest(core),
        "journal_hash": digest(journal),
        "journal": journal,
    }
    row = {"id": "row", "result_hash": result["result_hash"]}
    atomic_replay(study / "replays/row.json", {"row": row, "result": result})
    atomic_json(study / "rows.json", [row])
    atomic_json(
        study / "manifest.json", {"state": "COMPLETED", "rows_sha256": sha256(study / "rows.json")}
    )
    backup = tmp_path / "original.tar.gz"
    with tarfile.open(backup, "w:gz") as bundle:
        for path in study.rglob("*"):
            if path.is_file():
                bundle.add(path, arcname=str(path.relative_to(root)), recursive=False)
    pack(root, "tournaments", study.name)
    prune(root, "tournaments", study.name)
    archive(root, "tournaments", study.name)
    return root, study, backup


def test_independent_verifier_checks_prepared_and_pruned_bytes(tmp_path):
    root, study, backup = setup(tmp_path)
    first = verify(root, "tournaments", study.name, backup, sha256(backup))
    assert first["hot_copy_present"] and first["original_byte_replays_verified"] == 1
    archive(root, "tournaments", study.name, prune=True)
    second = verify(root, "tournaments", study.name, backup, sha256(backup))
    assert not second["hot_copy_present"] and second["original_byte_replays_verified"] == 1


def test_verifier_rejects_changed_backup_and_rows(tmp_path):
    root, study, backup = setup(tmp_path)
    with pytest.raises(ValueError, match="backup checksum"):
        verify(root, "tournaments", study.name, backup, "0" * 64)
    (study / "rows.json").write_text("[]")
    with pytest.raises(ValueError, match="rows checksum"):
        verify(root, "tournaments", study.name, backup, sha256(backup))


def test_verifier_rejects_changed_cold_database_even_with_hot_copy(tmp_path):
    root, study, backup = setup(tmp_path)
    marker = json.loads((study / "replays/cold.json").read_text())
    database = tmp_path / "arena-cold" / marker["database_sha256"] / "replays.sqlite"
    database.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="database checksum"):
        verify(root, "tournaments", study.name, backup, sha256(backup))


def test_verifier_compares_exact_original_compressed_bytes(tmp_path):
    root, study, backup = setup(tmp_path)
    changed = tmp_path / "recompressed.tar.gz"
    with tarfile.open(backup, "r:gz") as old, tarfile.open(changed, "w:gz") as new:
        for member in old:
            payload = old.extractfile(member).read()
            if member.name.endswith(".json.gz"):
                payload = gzip.compress(gzip.decompress(payload), mtime=123)
            entry = tarfile.TarInfo(member.name)
            entry.size = len(payload)
            new.addfile(entry, io.BytesIO(payload))
    with pytest.raises(ValueError, match="original backup"):
        verify(root, "tournaments", study.name, changed, sha256(changed))
