"""Dataset diagnostics and read-only audits of correlated Laboratory records."""

import hashlib
import json
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from midas.arena.artifacts import atomic_json
from midas.arena.datasets import load
from midas.arena.features import FEATURES
from midas.economics.attestation import digest


def analyze(root: Path, identity: str) -> dict[str, Any]:
    manifest, rows = load(root, identity)
    x = np.array([r["features"] for r in rows], dtype=float)
    constant = [FEATURES[i] for i in range(len(FEATURES)) if np.ptp(x[:, i]) == 0]
    distributions = {
        name: {
            "minimum": float(x[:, i].min()),
            "maximum": float(x[:, i].max()),
            "quantiles": np.quantile(x[:, i], [0.05, 0.25, 0.5, 0.75, 0.95]).tolist(),
            "missing": int(np.sum(~np.isfinite(x[:, i]))),
        }
        for i, name in enumerate(FEATURES)
    }
    balances = {}
    for key in ("family", "execution_model", "partition"):
        balances[key] = {
            name: {
                "variants": sum(r[key] == name for r in rows),
                "base_episodes": len({r["base_episode_id"] for r in rows if r[key] == name}),
                "positive_frequency": float(np.mean([r["label"] for r in rows if r[key] == name])),
            }
            for name in sorted({r[key] for r in rows})
        }
    signatures: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        signatures[digest(row["features"])].append(row)
    duplicates = [group for group in signatures.values() if len(group) > 1]
    cross_partition_duplicates = sum(
        len({r["partition"] for r in group}) > 1 for group in duplicates
    )
    ambiguous = sum(len({r["label"] for r in group}) > 1 for group in signatures.values())
    independent = [i for i, name in enumerate(FEATURES) if name not in constant]
    correlations: list[dict[str, Any]] = []
    if len(independent) > 1:
        matrix = np.corrcoef(x[:, independent], rowvar=False)
        for i, left in enumerate(independent):
            for j, right in enumerate(independent[i + 1 :], i + 1):
                correlations.append(
                    {
                        "left": FEATURES[left],
                        "right": FEATURES[right],
                        "correlation": float(matrix[i, j]),
                    }
                )
    correlations.sort(key=lambda r: -abs(r["correlation"]))
    train = x[[r["partition"] == "train" for r in rows]]
    test = x[[r["partition"] == "test" for r in rows]]
    scale = np.maximum(train.std(axis=0), 1e-9)
    shifts = {
        name: float(abs(train[:, i].mean() - test[:, i].mean()) / scale[i])
        for i, name in enumerate(FEATURES)
    }
    parity = {
        family: sorted({r["seed"] % 2 for r in rows if r["family"] == family})
        for family in balances["family"]
    }
    warnings = []
    if cross_partition_duplicates:
        warnings.append(
            "Identical observable vectors occur across partitions. Independent scenario IDs do not guarantee covariate diversity; inspect repeated synthetic grids."
        )
    if any(len(values) == 1 for values in parity.values()):
        warnings.append(
            "Some scenario families contain one settlement seed parity only. The current generator uses seed parity for settlement; reorder families and shift seeds before making generalization claims."
        )
    warnings.append(
        "Execution outcomes are partly mechanically determined by hypothetical liquidity and adverse-tick settings. High prediction accuracy can reflect simulator assumptions."
    )
    report = {
        "analysis_version": "dataset-quality-1",
        "dataset_id": identity,
        "rows_sha256": manifest["rows_sha256"],
        "created_at": time.time(),
        "variants": len(rows),
        "base_episodes": len({r["base_episode_id"] for r in rows}),
        "balances": balances,
        "constant_features": constant,
        "feature_distributions": distributions,
        "strongest_correlations": correlations[:20],
        "standardized_train_test_mean_shift": shifts,
        "duplicate_vector_groups": len(duplicates),
        "cross_partition_duplicate_vector_groups": cross_partition_duplicates,
        "ambiguous_observable_vectors": ambiguous,
        "family_settlement_seed_parity": parity,
        "warnings": warnings,
        "interpretation": "Diagnostics expose generated-data limitations; correlations and sensitivity do not prove causality.",
    }
    atomic_json(root / "datasets" / identity / "quality.json", report)
    return report


def audit_campaign(
    database: Path, campaign_id: str, expected_groups: int | None = None
) -> dict[str, Any]:
    """Inspect only compact archive records; never acquire a Laboratory writer lease."""
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    h = hashlib.sha256()
    counts: Counter[int] = Counter()
    variants: dict[int, set[str]] = defaultdict(set)
    seeds: dict[int, set[int]] = defaultdict(set)
    seen = set()
    mismatches = 0
    try:
        campaign = connection.execute(
            "SELECT status,spec,code_hash FROM campaigns WHERE id=?", (campaign_id,)
        ).fetchone()
        if campaign is None:
            raise ValueError("Campaign not found")
        spec = json.loads(campaign[1])
        expected = {
            f"{strategy}/{model}" for strategy in spec["strategies"] for model in spec["models"]
        }
        for index, variant, identity, result in connection.execute(
            "SELECT idx,variant,id,result FROM runs WHERE campaign=? ORDER BY idx,variant",
            (campaign_id,),
        ):
            h.update(json.dumps((index, variant, identity, result), separators=(",", ":")).encode())
            record = json.loads(result)
            counts[index] += 1
            variants[index].add(variant)
            seeds[index].add(record["seed"])
            mismatches += identity != digest([campaign_id, index, variant])[:32]
            if identity in seen:
                raise ValueError("Duplicate persisted variant identity")
            seen.add(identity)
            if not record["complete"] or not record["passed"]:
                raise ValueError("Campaign contains incomplete or invalid results")
        required = expected_groups if expected_groups is not None else spec["runs"]
        if set(counts) != set(range(required)) or any(variants[i] != expected for i in counts):
            raise ValueError("Missing campaign episode or variant coverage")
        if (
            any(values != {(spec["seed"] + index) % 2**32} for index, values in seeds.items())
            or mismatches
        ):
            raise ValueError("Campaign identities or variant seeds disagree")
        return {
            "campaign_id": campaign_id,
            "status": campaign[0],
            "groups": len(counts),
            "variants": sum(counts.values()),
            "variants_per_group": len(expected),
            "logical_sha256": h.hexdigest(),
            "source_hash": campaign[2],
            "verified_grouping": True,
            "verified_deterministic_identities": True,
            "limitations": [
                "Compact outcome records lack decision-time feature vectors.",
                "Importing evaluator results as features would leak future information.",
                "Any future dataset import must reconstruct observations under the archived simulator source or use original retained observations.",
                "Variants are correlated; 162000 variants are not 162000 independent market observations.",
            ],
        }
    finally:
        connection.close()
