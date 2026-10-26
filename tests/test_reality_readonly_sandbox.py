from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_landlock_denies_source_mutation_and_allows_independent_staging(tmp_path):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    source = tmp_path / "immutable"
    output = tmp_path / "staging"
    source.mkdir()
    output.mkdir()
    original = source / "segment.seg"
    original.write_bytes(b"source evidence")
    (output / "segment.seg").symlink_to(original)
    probe = output / "probe.py"
    probe.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "from reality_readonly_sandbox import apply_readonly_source_policy, verify_source_write_denied\n"
        f"source = Path({str(source)!r})\n"
        f"output = Path({str(output)!r})\n"
        "policy = apply_readonly_source_policy(source, output)\n"
        "verify_source_write_denied(output / 'segment.seg')\n"
        "try:\n"
        "    os.unlink(source / 'segment.seg')\n"
        "except PermissionError:\n"
        "    pass\n"
        "else:\n"
        "    raise AssertionError('source unlink was allowed')\n"
        "(output / 'checkpoint.json').write_text('staging state')\n"
        "assert 'Landlock' in policy['mechanism']\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(scripts) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run([sys.executable, str(probe)], env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert original.read_bytes() == b"source evidence"
    assert (output / "checkpoint.json").read_text() == "staging state"
