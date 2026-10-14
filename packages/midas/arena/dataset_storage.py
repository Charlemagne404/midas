"""Explicit stored feature representations and canonical migration verification."""

import json
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, sha256
from midas.arena.features import FEATURES
from midas.economics.attestation import digest

VERSIONS = {"decision-storage-1": "ordered-features-1", "decision-storage-2": "named-features-1"}


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate stored dataset key")
        result[key] = value
    return result


def decode_rows(payload: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    version = manifest.get("storage_version", "decision-storage-1")
    if (
        version not in VERSIONS
        or manifest.get("row_encoding", "ordered-features-1") != VERSIONS[version]
    ):
        raise ValueError("Unsupported dataset storage schema/encoding")
    rows: list[dict[str, Any]] = json.loads(payload, object_pairs_hook=unique_object)
    if not isinstance(rows, list):
        raise ValueError("Stored dataset rows must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Stored dataset row must be an object")
        features = row.get("features")
        if version == "decision-storage-2":
            if not isinstance(features, dict) or set(features) != set(FEATURES):
                raise ValueError("Named feature schema differs")
            row["features"] = [features[name] for name in FEATURES]
        elif not isinstance(features, list):
            raise ValueError("Ordered feature schema differs")
    if manifest.get("canonical_rows_sha256") and digest(rows) != manifest["canonical_rows_sha256"]:
        raise ValueError("Canonical migrated content checksum differs")
    return rows


def encode_rows(rows: list[dict[str, Any]], version: str) -> list[dict[str, Any]]:
    if version not in VERSIONS:
        raise ValueError("Unsupported migration target storage schema")
    return [
        {
            **row,
            "features": dict(zip(FEATURES, row["features"], strict=True))
            if version == "decision-storage-2"
            else list(row["features"]),
        }
        for row in rows
    ]


def verify_migration(
    root: Path,
    identity: str,
    manifest: dict[str, Any],
    rows: list[dict[str, Any]],
    parent: dict[str, Any],
    parent_rows: list[dict[str, Any]],
) -> None:
    migration = manifest["migration"]
    directory = artifact_path(root, "datasets", identity)
    parent_directory = artifact_path(root, "datasets", migration["source_dataset_id"])
    ignored = {
        "dataset_id",
        "rows_sha256",
        "created_at",
        "storage_version",
        "row_encoding",
        "migration",
        "canonical_rows_sha256",
        "limitations",
    }
    if (
        migration.get("version") != "dataset-storage-migration-1"
        or migration.get("target_storage_version") != manifest.get("storage_version")
        or migration.get("source_rows_sha256") != parent["rows_sha256"]
        or migration.get("source_manifest_sha256") != sha256(parent_directory / "manifest.json")
        or migration.get("producer_sha256") != sha256(directory / "migration-producer.py")
        or migration.get("canonical_rows_sha256") != digest(parent_rows)
        or manifest.get("canonical_rows_sha256") != digest(rows)
        or rows != parent_rows
        or {k: v for k, v in manifest.items() if k not in ignored}
        != {k: v for k, v in parent.items() if k not in ignored}
        or manifest["limitations"][: len(parent["limitations"])] != parent["limitations"]
    ):
        raise ValueError("Dataset storage migration changes canonical data or provenance")
