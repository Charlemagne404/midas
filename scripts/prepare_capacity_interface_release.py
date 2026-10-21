"""Build a pinned API-only efficiency release; never changes a service or recording."""

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import TypedDict

BASE = "c83320000a085bf30490b4b76b425527fe8574f7"
OVERRIDES = (
    "apps/api/reality.py",
    "apps/api/storage.py",
    "apps/api/paper.py",
    "apps/api/state_codec.py",
    "packages/midas/paper/broker.py",
    "packages/midas/arena/admission.py",
    "packages/midas/laboratory/campaigns.py",
    "scripts/paper_state_storage.py",
    "scripts/verify_paper_journal.py",
)


class ReleaseReceipt(TypedDict):
    base: str
    overrides: list[str]
    patched: str
    files: dict[str, str]


def prepare(destination: Path) -> ReleaseReceipt:
    repository = Path(__file__).resolve().parents[1]
    destination.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(
        [
            "git",
            "archive",
            BASE,
            "apps/__init__.py",
            "apps/api",
            "packages",
            "infra",
            "alembic.ini",
            "scripts",
        ],
        cwd=repository,
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(destination, filter="data")
    for name in OVERRIDES:
        shutil.copyfile(repository / name, destination / name)
    # The legacy interface launcher has a fixed 4 GiB cap. Apply admission
    # inside its existing idempotency/owner lock, before any new job artifacts.
    jobs = destination / "packages/midas/arena/jobs.py"
    source = jobs.read_text()
    before = "        return _create(root, spec, launch, admission_key)"
    assert source.count(before) == 1, "Pinned interface launcher changed"
    source = source.replace(
        before,
        """        if launch:
            from midas.arena.admission import admission_slot

            with admission_slot(root, requested_memory_bytes=4 * 1024**3):
                return _create(root, spec, launch, admission_key)
        return _create(root, spec, launch, admission_key)""",
    )
    source = source.replace(
        '"minimum_available_memory_mb": 2048,', '"minimum_available_memory_mb": 6144,'
    )
    source = source.replace(
        '"--property=MemoryMax=4G",',
        '"--property=MemoryMax=4G",\n            "--property=MemorySwapMax=0",',
    )
    source = source.replace(
        '"--property=CPUQuota=100%",',
        '"--property=CPUQuota=100%",\n            "--property=CPUWeight=10",',
    )
    # Transient units don't inherit the caller's import path. Keep spawned
    # workers on this pinned release rather than the recorder's editable tree.
    source = source.replace(
        "    if launch:\n        command = [",
        """    if launch:
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = Path(sys.executable).parent.parent / "lib" / version / "site-packages"
        command = [""",
    )
    source = source.replace(
        '            "systemd-run",',
        """            "systemd-run",
            f"--setenv=PYTHONPATH={repository / 'packages'}:{repository}:{site_packages}",""",
    )
    source = source.replace(
        '            sys.executable,\n            "-m",',
        '            sys.executable,\n            "-S",\n            "-m",',
    )
    jobs.write_text(source)
    (destination / "data").symlink_to(Path.home() / "midas-reality/data", target_is_directory=True)
    files = {
        str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in destination.rglob("*")
        if p.is_file() and not p.is_symlink()
    }
    receipt: ReleaseReceipt = {
        "base": BASE,
        "overrides": list(OVERRIDES),
        "patched": str(jobs.relative_to(destination)),
        "files": files,
    }
    (destination / "capacity-release.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = prepare(args.destination)
    print(json.dumps({"destination": str(args.destination), "files": len(result["files"])}))
