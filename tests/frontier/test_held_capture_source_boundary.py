import os
from pathlib import Path

import pytest


def test_python_tests_do_not_reference_held_live_probe_capture() -> None:
    tests_root = Path(__file__).resolve().parents[1]
    forbidden = "/".join(("data", "frontier", "live-" + "probes"))

    references = [
        str(path.relative_to(tests_root.parent))
        for path in sorted(tests_root.rglob("*.py"))
        if forbidden in path.read_text(encoding="utf-8")
    ]

    assert not references, f"Test sources reference held live-probe capture: {references}"


def test_runtime_guard_blocks_held_capture_path_under_temporary_directory(
    tmp_path: Path,
) -> None:
    held_directory = tmp_path / "data" / "frontier" / ("live-" + "probes")
    nested_directory = held_directory / "nested"
    nested_directory.mkdir(parents=True)
    held_path = held_directory / "absent.json"

    with pytest.raises(PermissionError, match="may not access held source captures"):
        held_path.read_text(encoding="utf-8")
    with pytest.raises(PermissionError, match="may not access held source captures"):
        held_path.write_text("{}", encoding="utf-8")
    with pytest.raises(PermissionError, match="may not access held source captures"):
        open(held_path, "rb")
    with pytest.raises(PermissionError, match="may not access held source captures"):
        os.open(held_path, os.O_RDONLY)

    alias = tmp_path / "alias.json"
    alias.symlink_to(held_path)
    with pytest.raises(PermissionError, match="may not access held source captures"):
        alias.read_text(encoding="utf-8")

    directory_alias = tmp_path / "alias-directory"
    directory_alias.symlink_to(nested_directory, target_is_directory=True)
    traversal = directory_alias / ".." / "absent.json"
    with pytest.raises(PermissionError, match="may not access held source captures"):
        traversal.read_text(encoding="utf-8")

    directory_fd = os.open(tmp_path, os.O_RDONLY)
    try:
        relative_path = os.path.relpath(held_path, start=tmp_path)
        with pytest.raises(PermissionError, match="may not access held source captures"):
            os.open(relative_path, os.O_RDONLY, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)

    assert not held_path.exists()
