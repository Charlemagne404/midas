import os
from pathlib import Path

import pytest


def test_python_tests_do_not_reference_live_source_capture_roots() -> None:
    tests_root = Path(__file__).resolve().parents[1]
    forbidden_roots = (
        "/".join(("data", "frontier", "live-" + "probes")),
        "/".join(("data", "frontier-" + "public", "probes")),
    )

    references = [
        str(path.relative_to(tests_root.parent))
        for path in sorted(tests_root.rglob("*.py"))
        if any(root in path.read_text(encoding="utf-8") for root in forbidden_roots)
    ]

    assert not references, f"Test sources reference live source capture roots: {references}"


@pytest.mark.parametrize(
    "root_parts",
    (
        ("data", "frontier", "live-" + "probes"),
        ("data", "frontier-" + "public", "probes"),
    ),
)
def test_runtime_guard_blocks_live_capture_paths_under_temporary_directory(
    tmp_path: Path, root_parts: tuple[str, ...]
) -> None:
    live_directory = tmp_path.joinpath(*root_parts)
    nested_directory = live_directory / "nested"
    nested_directory.mkdir(parents=True)
    live_path = live_directory / "absent.json"

    with pytest.raises(PermissionError, match="may not access captured live source data"):
        live_path.read_text(encoding="utf-8")
    with pytest.raises(PermissionError, match="may not access captured live source data"):
        live_path.write_text("{}", encoding="utf-8")
    with pytest.raises(PermissionError, match="may not access captured live source data"):
        open(live_path, "rb")
    with pytest.raises(PermissionError, match="may not access captured live source data"):
        os.open(live_path, os.O_RDONLY)

    alias = tmp_path / "alias.json"
    alias.symlink_to(live_path)
    with pytest.raises(PermissionError, match="may not access captured live source data"):
        alias.read_text(encoding="utf-8")

    directory_alias = tmp_path / "alias-directory"
    directory_alias.symlink_to(nested_directory, target_is_directory=True)
    traversal = directory_alias / ".." / "absent.json"
    with pytest.raises(PermissionError, match="may not access captured live source data"):
        traversal.read_text(encoding="utf-8")

    directory_fd = os.open(tmp_path, os.O_RDONLY)
    try:
        relative_path = os.path.relpath(live_path, start=tmp_path)
        with pytest.raises(PermissionError, match="may not access captured live source data"):
            os.open(relative_path, os.O_RDONLY, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)

    assert not live_path.exists()
