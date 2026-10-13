"""Reproduce a migrated replay using its exact captured package source and weights."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from midas.arena.artifacts import artifact_path, read_replay, sha256

CHILD = """
import json,sys
from pathlib import Path
from scripts.reproduce_policy_inference import reproduce
report=reproduce(Path(sys.argv[1]),sys.argv[2],sys.argv[3])
Path(sys.argv[4]).write_text(json.dumps(report))
"""


def captured_source(root: Path, identity: str) -> tuple[Path, str]:
    manifest = json.loads(
        (artifact_path(root, "tournaments", identity) / "manifest.json").read_text()
    )
    for path in root.glob("jobs/*/job.json"):
        job = json.loads(path.read_text())
        if (job.get("result") or {}).get("tournament_id") != identity:
            continue
        record = json.loads((path.parent / "source-manifest.json").read_text())
        if (
            record["source_hash"] != manifest["source_hash"]
            or job["submitted_source_hash"] != manifest["source_hash"]
        ):
            raise ValueError("Captured study source identity differs")
        for relative, expected in record["files"].items():
            name = Path(relative)
            if (
                name.is_absolute()
                or ".." in name.parts
                or sha256(path.parent / "source" / name) != expected
            ):
                raise ValueError("Captured study source payload changed")
        return path.parent / "source/packages", manifest["source_hash"]
    raise ValueError("No exact captured source found for study")


def reproduce(root: Path, identity: str, row_id: str) -> dict:
    packages, source_hash = captured_source(root, identity)
    study = artifact_path(root, "tournaments", identity)
    rows = json.loads((study / "rows.json").read_text())
    if len([r for r in rows if r["id"] == row_id]) != 1 or Path(row_id).name != row_id:
        raise ValueError("Missing, duplicate or invalid row identity")
    if (
        sha256(study / "rows.json")
        != json.loads((study / "manifest.json").read_text())["rows_sha256"]
    ):
        raise ValueError("Frozen study rows changed")
    with tempfile.TemporaryDirectory(prefix="midas-captured-policy-") as temporary:
        working = Path(temporary)
        target = working / "tournaments" / identity
        target.mkdir(parents=True)
        for name in ("manifest.json", "rows.json"):
            shutil.copyfile(study / name, target / name)
        replay_path = study / "replays" / (row_id + ".json")
        # Verify through the current reader, then restore one exact stored payload.
        read_replay(replay_path)
        replay_directory = target / "replays"
        replay_directory.mkdir()
        if replay_path.exists():
            shutil.copyfile(replay_path, replay_directory / replay_path.name)
        elif replay_path.with_suffix(".json.gz").exists():
            shutil.copyfile(
                replay_path.with_suffix(".json.gz"), replay_directory / (row_id + ".json.gz")
            )
        else:
            import gzip
            import hashlib
            import sqlite3
            from contextlib import closing

            packing = json.loads((study / "replays/packing.json").read_text())
            original_name, entry = next(
                (name, value)
                for name, value in packing["files"].items()
                if value["logical_name"] == row_id + ".json"
            )
            with closing(
                sqlite3.connect(
                    (study / "replays/replays.sqlite").resolve().as_uri() + "?mode=ro", uri=True
                )
            ) as connection:
                payload = connection.execute(
                    "select payload from replays where name=?", (row_id + ".json",)
                ).fetchone()[0]
            original = payload if entry["original_format"] == "gzip" else gzip.decompress(payload)
            if (
                hashlib.sha256(original).hexdigest() != entry["sha256"]
                or Path(original_name).name != original_name
            ):
                raise ValueError("Original restoration checksum or filename differs")
            (replay_directory / original_name).write_bytes(original)
        for kind in ("models", "datasets"):
            (working / kind).symlink_to((root / kind).resolve(), target_is_directory=True)
        output = working / "proof.json"
        environment = {
            **os.environ,
            "PYTHONPATH": str(packages.resolve())
            + os.pathsep
            + str(Path(__file__).resolve().parents[1]),
            "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "CUDA_VISIBLE_DEVICES": "",
        }
        subprocess.run(
            [sys.executable, "-B", "-c", CHILD, str(working), identity, row_id, str(output)],
            check=True,
            timeout=120,
            env=environment,
            capture_output=True,
            text=True,
        )
        report = json.loads(output.read_text())
        if report["source_hash"] != source_hash or not report["verified"]:
            raise ValueError("Captured-source policy did not reproduce")
        return {
            **report,
            "captured_source_used": True,
            "restored_bytes_workspace": "Temporary isolated directory removed after reexecution",
            "orchestrator_sha256": sha256(Path(__file__)),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("row_id")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = reproduce(args.root, args.identity, args.row_id)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
