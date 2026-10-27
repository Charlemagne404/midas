from pathlib import Path


def test_python_tests_do_not_reference_held_live_probe_capture() -> None:
    tests_root = Path(__file__).resolve().parents[1]
    forbidden = "/".join(("data", "frontier", "live-" + "probes"))

    references = [
        str(path.relative_to(tests_root.parent))
        for path in sorted(tests_root.rglob("*.py"))
        if forbidden in path.read_text(encoding="utf-8")
    ]

    assert not references, f"Test sources reference held live-probe capture: {references}"
