import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from midas.laboratory.campaigns import archive_bytes


def test_vanished_sqlite_sidecar_does_not_fail_archive_scan():
    database = Mock()
    database.stat.return_value = SimpleNamespace(st_mode=stat.S_IFREG, st_size=123)
    sidecar = Mock()
    sidecar.stat.side_effect = FileNotFoundError("SQLite removed its SHM file")
    directory = Mock()
    directory.stat.return_value = SimpleNamespace(st_mode=stat.S_IFDIR, st_size=4096)
    root = Mock()
    root.rglob.return_value = [database, sidecar, directory]
    assert archive_bytes(root) == 123
    assert database.stat.call_count == sidecar.stat.call_count == 1


def test_archive_scan_does_not_hide_permission_failures():
    payload = Mock()
    payload.stat.side_effect = PermissionError("Unreadable retained evidence")
    root = Mock()
    root.rglob.return_value = [payload]
    with pytest.raises(PermissionError):
        archive_bytes(root)
