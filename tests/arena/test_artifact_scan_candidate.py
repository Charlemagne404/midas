import os
import shutil

import pytest
from midas.arena.jobs import artifact_usage

from scripts.profile_artifact_scan import find_usage


@pytest.mark.skipif(shutil.which("find") is None, reason="GNU find not installed")
def test_candidate_matches_logical_bytes_and_symlink_semantics(tmp_path):
    root = tmp_path / "arena"
    root.mkdir()
    payload = root / "original"
    payload.write_bytes(b"12345")
    os.link(payload, root / "hard-link")
    (root / "newline\nname").write_bytes(b"123")
    nested = root / "nested"
    nested.mkdir()
    (nested / "file").write_bytes(b"12")
    (root / "file-link").symlink_to(payload)
    (root / "directory-link").symlink_to(nested)
    (root / "broken-link").symlink_to(root / "absent")
    assert find_usage(root) == artifact_usage(root) == (20, 5)
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(root)
    assert find_usage(linked_root) == artifact_usage(linked_root)
    assert find_usage(tmp_path / "missing") == artifact_usage(tmp_path / "missing") == (0, 0)
