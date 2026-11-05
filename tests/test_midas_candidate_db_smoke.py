from __future__ import annotations

import sqlite3

import pytest

from scripts.midas_candidate_db_smoke import (
    SmokeError,
    read_database_summary,
    validate_database_path,
)


def test_database_summary_reads_schema_and_records(tmp_path) -> None:
    database = tmp_path / "restored.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        "CREATE TABLE records (id INTEGER PRIMARY KEY, kind TEXT, key TEXT, source TEXT, "
        "received_ts_ms INTEGER, payload TEXT);"
        "INSERT INTO records VALUES (1, 'market', 'legacy', 'SYNTHETIC', 1, '{}');"
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"
        "INSERT INTO alembic_version VALUES ('003');"
    )
    connection.close()

    summary = read_database_summary(database)
    assert summary["quick_check"] == ["ok"]
    assert summary["records"] == 1
    assert summary["alembic_revisions"] == ["003"]


def test_database_must_be_inside_real_isolated_root(tmp_path) -> None:
    root = tmp_path / "isolated"
    root.mkdir()
    outside = tmp_path / "outside.db"
    outside.touch()
    with pytest.raises(SmokeError, match="inside the isolated root"):
        validate_database_path(root, outside)


def test_database_symlink_is_rejected(tmp_path) -> None:
    root = tmp_path / "isolated"
    root.mkdir()
    actual = root / "actual.db"
    actual.touch()
    link = root / "restored.db"
    link.symlink_to(actual)
    with pytest.raises(SmokeError, match="must not be a symlink"):
        validate_database_path(root, link)
