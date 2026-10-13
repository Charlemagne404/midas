"""Bounded immutable dataset storage migrations; no generation or model fitting."""

import fcntl
import json
import time
from pathlib import Path
from typing import Literal

from pydantic import Field

from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.dataset_storage import VERSIONS, decode_rows, encode_rows, verify_migration
from midas.arena.datasets import load, research_hash
from midas.core.models import Model
from midas.economics.attestation import digest


class MigrationSpec(Model):
    source_dataset_id: str = Field(pattern=r"^dataset-[a-zA-Z0-9_-]{1,80}$")
    target_storage_version: Literal["decision-storage-1", "decision-storage-2"] = (
        "decision-storage-2"
    )


def migrate(root: Path, spec: MigrationSpec, progress=None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    with (root / "migration.lock").open("a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        return _migrate(root, spec, progress)


def _migrate(root: Path, spec: MigrationSpec, progress=None) -> dict:
    from midas.arena.jobs import artifact_usage

    parent_directory = artifact_path(root, "datasets", spec.source_dataset_id)
    if (parent_directory / "rows.json").stat().st_size > 64 * 1024**2:
        raise ValueError("Migration source exceeds bounded 64MiB input limit")
    parent, rows = load(root, spec.source_dataset_id)
    if len(rows) > 60000:
        raise ValueError("Migration source exceeds bounded row limit")
    if parent.get("storage_version", "decision-storage-1") == spec.target_storage_version:
        raise ValueError("Dataset already uses requested storage schema")
    producer = Path(__file__).read_bytes()
    producer_hash = sha256(Path(__file__))
    parent_manifest_hash = sha256(parent_directory / "manifest.json")
    implementation_hash = research_hash()
    identity = (
        "dataset-"
        + digest(
            [
                "dataset-storage-migration-1",
                spec.model_dump(mode="json"),
                parent_manifest_hash,
                parent["rows_sha256"],
                producer_hash,
                implementation_hash,
            ]
        )[:24]
    )
    directory = artifact_path(root, "datasets", identity)
    if (directory / "manifest.json").exists():
        return load(root, identity)[0]
    encoded = encode_rows(rows, spec.target_storage_version)
    payload = json.dumps(encoded, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    if artifact_usage(root)[0] + len(payload) + len(producer) + 1024**2 >= 1024**3 - 16 * 1024**2:
        raise ValueError("Insufficient Arena headroom for immutable migration")
    register = getattr(progress, "register", None)
    if register:
        register("datasets", identity)
    if (directory / "rows.json").exists() and (directory / "rows.json").read_bytes() != payload:
        raise ValueError("Existing incomplete migration rows differ")
    if (directory / "migration-producer.py").exists() and (
        directory / "migration-producer.py"
    ).read_bytes() != producer:
        raise ValueError("Existing incomplete migration producer differs")
    atomic_bytes(directory / "rows.json", payload)
    atomic_bytes(directory / "migration-producer.py", producer)
    manifest = {
        **parent,
        "dataset_id": identity,
        "created_at": time.time(),
        "storage_version": spec.target_storage_version,
        "row_encoding": VERSIONS[spec.target_storage_version],
        "rows_sha256": sha256(directory / "rows.json"),
        "canonical_rows_sha256": digest(rows),
        "migration": {
            "version": "dataset-storage-migration-1",
            "source_dataset_id": spec.source_dataset_id,
            "source_rows_sha256": parent["rows_sha256"],
            "source_manifest_sha256": parent_manifest_hash,
            "target_storage_version": spec.target_storage_version,
            "producer_sha256": producer_hash,
            "implementation_source_hash": implementation_hash,
            "canonical_rows_sha256": digest(rows),
        },
        "limitations": [
            *parent["limitations"],
            "Storage migration reuses the exact source observations/labels/partitions; not additional independent data.",
        ],
    }
    if (
        sha256(parent_directory / "manifest.json") != parent_manifest_hash
        or sha256(parent_directory / "rows.json") != parent["rows_sha256"]
    ):
        raise ValueError("Source dataset changed during migration")
    canonical = decode_rows(payload.decode(), manifest)
    verify_migration(root, identity, manifest, canonical, parent, rows)
    # Completion is published last. Interrupted drafts are not catalogued as complete.
    atomic_json(directory / "manifest.json", manifest)
    result = load(root, identity)[0]
    if progress:
        progress(len(rows), len(rows))
    return result
