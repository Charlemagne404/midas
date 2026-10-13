import os
import shutil

import pytest
from midas.arena.artifacts import atomic_bytes
from midas.arena.jobs import artifact_usage
from midas.arena.usage import UsageIndex


def exact(index, root):
    assert index.usage() == artifact_usage(root)


def test_index_tracks_file_lifecycle_and_nested_tree(tmp_path):
    index = UsageIndex(tmp_path, artifact_usage)
    try:
        if index.fd < 0:
            pytest.skip(index.last_error)
        for i in range(20):
            path = tmp_path / "deep" / str(i) / "value"
            atomic_bytes(path, b"a" * (i + 1))
            exact(index, tmp_path)
            path.write_bytes(b"b" * (i + 10))
            exact(index, tmp_path)
            moved = path.with_name("renamed")
            path.rename(moved)
            exact(index, tmp_path)
        shutil.rmtree(tmp_path / "deep")
        exact(index, tmp_path)
        atomic_bytes(tmp_path / "new" / "again", b"123")
        exact(index, tmp_path)
    finally:
        index.close()
    assert index.fd == -1


def test_hard_links_and_external_alias_writes(tmp_path):
    root = tmp_path / "arena"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"123")
    os.link(outside, root / "one")
    os.link(outside, root / "two")
    index = UsageIndex(root, artifact_usage)
    try:
        exact(index, root)
        outside.write_bytes(b"123456789")
        exact(index, root)
        (root / "one").unlink()
        exact(index, root)
        outside.write_bytes(b"z")
        exact(index, root)
    finally:
        index.close()


def test_external_hard_link_added_after_initial_index(tmp_path):
    root = tmp_path / "arena"
    root.mkdir()
    original = root / "file"
    original.write_bytes(b"1")
    index = UsageIndex(root, artifact_usage)
    try:
        outside = tmp_path / "later-link"
        os.link(original, outside)
        outside.write_bytes(b"1234567")
        exact(index, root)
        for i in range(20):
            atomic_bytes(original, b"a" * (i + 1))
            exact(index, root)
        assert index.reconciliations == 1
    finally:
        index.close()


def test_external_symlink_targets_replacement_and_type_changes(tmp_path):
    root = tmp_path / "arena"
    root.mkdir()
    target = tmp_path / "target"
    target.write_bytes(b"123")
    (root / "link").symlink_to(target)
    (root / "broken").symlink_to(tmp_path / "absent")
    directory = tmp_path / "directory"
    directory.mkdir()
    (root / "dir-link").symlink_to(directory)
    index = UsageIndex(root, artifact_usage)
    try:
        exact(index, root)
        atomic_bytes(target, b"12345678")
        exact(index, root)
        target.write_bytes(b"4")
        exact(index, root)
        target.unlink()
        exact(index, root)
        target.write_bytes(b"567")
        exact(index, root)
        directory.rmdir()
        directory.write_bytes(b"abc")
        exact(index, root)
        assert index.usage() == (6, 2)
    finally:
        index.close()


def test_overflow_and_watch_failure_reconcile(tmp_path, monkeypatch):
    atomic_bytes(tmp_path / "file", b"123")
    index = UsageIndex(tmp_path, artifact_usage)
    try:
        before = index.reconciliations
        monkeypatch.setattr(index, "_events", lambda: None)
        (tmp_path / "file").write_bytes(b"123456")
        exact(index, tmp_path)
        assert index.reconciliations > before and index.fallbacks > 0

        def broken(path):
            raise OSError("Watch limit exhausted")

        monkeypatch.setattr(index, "_watch", broken)
        index._rebuild()
        assert index.fd == -1
        atomic_bytes(tmp_path / "another", b"123")
        exact(index, tmp_path)
    finally:
        index.close()


def test_missing_root_and_deleted_root_remain_exact(tmp_path):
    root = tmp_path / "arena"
    index = UsageIndex(root, artifact_usage)
    try:
        exact(index, root)
        atomic_bytes(root / "file", b"1234")
        exact(index, root)
        index._rebuild()
        exact(index, root)
        shutil.rmtree(root)
        exact(index, root)
        atomic_bytes(root / "new", b"12345")
        exact(index, root)
    finally:
        index.close()


def test_root_symlink_retargeting(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "file").write_bytes(b"1")
    (b / "file").write_bytes(b"123456")
    root = tmp_path / "root"
    root.symlink_to(a)
    index = UsageIndex(root, artifact_usage)
    try:
        exact(index, root)
        root.unlink()
        root.symlink_to(b)
        exact(index, root)
    finally:
        index.close()


def test_replacement_during_watch_registration_falls_back(tmp_path, monkeypatch):
    file = tmp_path / "file"
    file.write_bytes(b"1")
    index = UsageIndex(tmp_path, artifact_usage)
    try:
        if index.fd < 0:
            pytest.skip(index.last_error)
        fresh = tmp_path / "fresh"
        fresh.write_bytes(b"12")
        watch = index._watch
        changed = False

        def replace(path, inode=None):
            nonlocal changed
            watch(path, inode)
            if inode is not None and not changed:
                changed = True
                atomic_bytes(fresh, b"1234567")

        monkeypatch.setattr(index, "_watch", replace)
        exact(index, tmp_path)
        assert changed and index.fd == -1 and index.fallbacks > 0
    finally:
        index.close()
