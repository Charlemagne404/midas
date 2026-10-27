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


def test_runtime_guard_blocks_held_capture_path_under_temporary_directory(tmp_path: Path) -> None:
    held_path = tmp_path / "data" / "frontier" / ("live-" + "probes") / "absent.json"

    with pytest.raises(PermissionError, match="may not access held source captures"):
        held_path.read_text(encoding="utf-8")
    with pytest.raises(PermissionError, match="may not access held source captures"):
        held_path.write_text("{}", encoding="utf-8")

    assert not held_path.exists()
