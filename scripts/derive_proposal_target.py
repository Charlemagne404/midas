"""Freeze an alternative binary target from saved proposal outcomes on identical observations."""

import argparse
import copy
import fcntl
import json
import time
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import load
from midas.economics.attestation import digest


def derive(root: Path, source_id: str, target: str) -> dict[str, Any]:
    if target not in {"completion", "unmatched"}:
        raise ValueError("Supported binary outcome target required")
    source, original = load(root, source_id)
    producer = Path(__file__).read_bytes()
    producer_hash = sha256(Path(__file__))
    lineage = {
        "version": "paired-target-1",
        "source_dataset_id": source_id,
        "source_rows_sha256": source["rows_sha256"],
        "target": target,
        "producer_sha256": producer_hash,
    }
    identity = "dataset-" + digest(lineage)[:24]
    directory = artifact_path(root, "datasets", identity)
    rows = copy.deepcopy(original)
    for row in rows:
        outcome = row.get("initial_outcome", {})
        value = outcome.get(target)
        if type(value) is not int or value not in (0, 1):
            raise ValueError("Saved binary initial proposal outcome required")
        row["label"] = value
        row["label_target"] = target
    # Serialize publication; an existing frozen identity is verified, never rewritten.
    with (root / "derivation.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        if (directory / "manifest.json").exists():
            manifest, saved = load(root, identity)
            if (
                manifest.get("derivation") != lineage
                or saved != rows
                or sha256(directory / "derivation-producer.py") != producer_hash
            ):
                raise ValueError("Existing derivation lineage mismatch")
            return manifest
        manifest = copy.deepcopy(source)
        manifest.update(
            dataset_id=identity,
            created_at=time.time(),
            derivation=lineage,
            label_target=target,
            duration_seconds=0,
            source="Derived target from frozen Midas synthetic proposal outcomes",
        )
        manifest["spec"]["label_target"] = target
        manifest["label_definition"] = (
            "Both sampled risk-admitted proposal orders finish FILLED; later proposals do not affect label"
            if target == "completion"
            else "Unequal acquired shares across sampled proposal legs after all its fills, before settlement; zero fills and matched partial fills are negative."
        )
        manifest["label_frequency"] = {
            p: sum(r["label"] for r in rows if r["partition"] == p)
            / sum(r["partition"] == p for r in rows)
            for p in ("train", "validation")
        }
        manifest["limitations"].append(
            "Shares observations, episode identities and frozen partitions with parent; not independent data. Test target frequency intentionally omitted. Generator source_hash/code_revision inherited; derivation source is separately preserved."
        )
        atomic_bytes(directory / "derivation-producer.py", producer)
        atomic_json(directory / "rows.json", rows)
        manifest["rows_sha256"] = sha256(directory / "rows.json")
        atomic_json(directory / "manifest.json", manifest)
        return load(root, identity)[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True, choices=["completion", "unmatched"])
    args = parser.parse_args()
    print(json.dumps(derive(args.root, args.source, args.target), indent=2))
