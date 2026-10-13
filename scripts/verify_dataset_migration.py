"""Independent raw-storage equivalence and frozen predictor checks; no fitting."""

import json
from pathlib import Path

import numpy as np
from midas.arena.artifacts import artifact_path, sha256
from midas.arena.supervised import Predictor
from midas.economics.attestation import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(path: Path, manifest: dict) -> list[dict]:
    rows = json.loads(path.read_text())
    schema = manifest["feature_schema"]
    require(len(set(schema)) == len(schema), "Duplicate feature schema")
    result = []
    for stored in rows:
        row = dict(stored)
        if manifest.get("storage_version", "decision-storage-1") == "decision-storage-2":
            require(
                isinstance(row["features"], dict) and set(row["features"]) == set(schema),
                "Named feature coverage differs",
            )
            row["features"] = [row["features"][name] for name in schema]
        else:
            require(
                manifest.get("storage_version", "decision-storage-1") == "decision-storage-1"
                and isinstance(row["features"], list),
                "Unknown raw storage version",
            )
        require(
            len(row["features"]) == len(schema) and np.isfinite(row["features"]).all(),
            "Canonical features invalid",
        )
        result.append(row)
    return result


def verify(root: Path, identity: str, plan: dict) -> dict:
    source_id = plan["configuration"]["migration"]["source_dataset_id"]
    source = artifact_path(root, "datasets", source_id)
    target = artifact_path(root, "datasets", identity)
    require(identity != source_id, "Migration reused original identity")
    for name, expected in plan["source_file_hashes"].items():
        require(
            Path(name).name == name and sha256(source / name) == expected,
            "Frozen source bytes changed",
        )
    parent = json.loads((source / "manifest.json").read_text())
    manifest = json.loads((target / "manifest.json").read_text())
    migration = manifest["migration"]
    require(
        migration["source_dataset_id"] == source_id
        and migration["source_rows_sha256"]
        == plan["source_rows_sha256"]
        == sha256(source / "rows.json"),
        "Migration source rows differ",
    )
    require(
        migration["source_manifest_sha256"]
        == plan["source_manifest_sha256"]
        == sha256(source / "manifest.json"),
        "Migration source metadata differs",
    )
    require(
        migration["implementation_source_hash"] == plan["source_hash"]
        and sha256(target / "migration-producer.py") == migration["producer_sha256"],
        "Migration producer differs",
    )
    require(
        manifest["storage_version"] == plan["configuration"]["migration"]["target_storage_version"]
        and sha256(target / "rows.json") == manifest["rows_sha256"],
        "Target encoding/hash differs",
    )
    original = canonical(source / "rows.json", parent)
    migrated = canonical(target / "rows.json", manifest)
    require(
        original == migrated
        and digest(original)
        == manifest["canonical_rows_sha256"]
        == migration["canonical_rows_sha256"],
        "Canonical source/target rows differ",
    )
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
    require(
        {k: v for k, v in parent.items() if k not in ignored}
        == {k: v for k, v in manifest.items() if k not in ignored},
        "Scientific metadata changed",
    )
    require(
        manifest["limitations"][: len(parent["limitations"])] == parent["limitations"],
        "Original limitations changed",
    )
    predictions = []
    for model_id, expected in plan.get("model_parameters", {}).items():
        directory = artifact_path(root, "models", model_id)
        require(
            sha256(directory / "parameters.json") == expected, "Frozen predictor parameters changed"
        )
        predictor = Predictor(json.loads((directory / "parameters.json").read_text()))
        a = predictor.predict([r["features"] for r in original])
        b = predictor.predict([r["features"] for r in migrated])
        require(np.array_equal(a, b), "Migrated predictions differ")
        predictions.append(
            {
                "model_id": model_id,
                "predictions": len(a),
                "prediction_sha256": digest(a.tolist()),
                "identical": True,
            }
        )
    return {
        "source_dataset_id": source_id,
        "dataset_id": identity,
        "canonical_rows_verified": len(original),
        "source_rows_sha256": plan["source_rows_sha256"],
        "target_rows_sha256": manifest["rows_sha256"],
        "canonical_rows_sha256": digest(original),
        "partition_identities_unchanged": True,
        "predictor_equivalence": predictions,
        "scientific_samples_added": 0,
        "models_trained": 0,
        "producer_sha256": sha256(Path(__file__)),
        "scope": "Separate raw JSON decoder, all-field canonical equivalence and existing predictor outputs; no simulation, labels/partitions changed or held-out model metrics opened.",
    }
