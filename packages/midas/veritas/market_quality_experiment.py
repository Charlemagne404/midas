"""Evaluate pre-book market metadata for ranking quality-valid public snapshots.

This bounded experiment reads immutable observatory snapshots only. Its target
is book-pair measurement validity, not gross opportunity, execution, or P&L.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ANALYSIS_VERSION = "veritas-market-quality-selection-experiment-v1"
SOURCE_ANALYSIS_VERSION = "veritas-public-observatory-v2"
SOURCE_CODE_SHA256 = "4ab2fa35be8d568a6e65a833f26f3c32e5b20f821bfb6e6c3ddcb9474bd6f060"
DISCOVERY_FRAME_PROTOCOL = "stratified-gamma-page-rotation-v2"
DATA_CUTOFF_SCAN_ID = "scan-20261016T213038Z-498756c46b83"
PREREGISTRATION_PATH = Path("docs/VERITAS_MISSION2_MARKET_QUALITY_EXPERIMENT_001.md")
MAX_COMPRESSED_BYTES = 2 * 1024**2
MAX_UNCOMPRESSED_BYTES = 48 * 1024**2
TRAIN_FRACTION = 0.70
TOP_FRACTION = 0.25
RANDOM_BASELINE_SEED = 20261016
MIN_SCANS = 10
MIN_TRAIN_MARKETS = 100
MIN_TEST_MARKETS = 40
NUMERIC_FEATURES = (
    "log_liquidity_usdc",
    "log_volume_24h_usdc",
    "days_to_expiry",
    "spread_per_share",
)
CATEGORICAL_FEATURES = (
    "primary_category",
    "primary_category_source",
    "liquidity_band",
    "expiry_band",
    "spread_band",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_COMPRESSED_BYTES:
        raise ValueError(f"unsafe or oversized snapshot: {path.name}")
    try:
        with gzip.open(path, "rb") as stream:
            raw = stream.read(MAX_UNCOMPRESSED_BYTES + 1)
        if len(raw) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError(f"snapshot exceeds uncompressed bound: {path.name}")
        value = json.loads(raw)
    except (OSError, EOFError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid compressed snapshot: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"snapshot is not an object: {path.name}")
    return value, _sha256(path.read_bytes())


def _finite_nonnegative(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _scan_rows(snapshot: dict[str, Any], *, scan_index: int) -> list[dict[str, Any]]:
    selection = snapshot.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("snapshot has no selection record")
    selected = selection.get("selected_markets")
    observations = snapshot.get("market_observations")
    if not isinstance(selected, list) or not isinstance(observations, list):
        raise ValueError("snapshot selection or observations are invalid")
    by_market: dict[str, dict[str, Any]] = {}
    for observation in observations:
        if not isinstance(observation, dict) or not isinstance(observation.get("market_id"), str):
            raise ValueError("invalid market observation identity")
        market_id = observation["market_id"]
        if market_id in by_market:
            raise ValueError("duplicate market observation in a scan")
        by_market[market_id] = observation

    captured_ns = snapshot.get("captured_ns")
    if not isinstance(captured_ns, int) or isinstance(captured_ns, bool):
        raise ValueError("snapshot capture time is invalid")
    phase = (
        selection.get("plan", {}).get("phase") if isinstance(selection.get("plan"), dict) else None
    )
    scan_id = snapshot.get("scan_id")
    if not isinstance(scan_id, str):
        raise ValueError("snapshot scan id is invalid")

    rows: list[dict[str, Any]] = []
    for metadata in selected:
        if not isinstance(metadata, dict):
            raise ValueError("invalid selected-market metadata")
        if metadata.get("cohort_role") != "rotating_stratified":
            continue
        market_id = metadata.get("market_id")
        if not isinstance(market_id, str) or market_id not in by_market:
            raise ValueError("selected rotating market has no matching observation")
        observation = by_market[market_id]
        audit = observation.get("audit")
        if not isinstance(audit, dict) or not isinstance(audit.get("valid"), bool):
            raise ValueError("market observation has no boolean quality label")
        probability = _finite_nonnegative(metadata.get("selection_probability"))
        if probability is None or probability <= 0 or probability > 1:
            raise ValueError("invalid market-selection probability")

        liquidity = _finite_nonnegative(metadata.get("liquidity_usdc"))
        volume = _finite_nonnegative(metadata.get("volume_24h_usdc"))
        spread = _finite_nonnegative(metadata.get("spread_per_share"))
        end_ns = metadata.get("end_ns")
        days_to_expiry = (
            max(0.0, (end_ns - captured_ns) / 86_400_000_000_000)
            if isinstance(end_ns, int) and not isinstance(end_ns, bool)
            else None
        )
        rows.append(
            {
                "scan_id": scan_id,
                "scan_index": scan_index,
                "captured_ns": captured_ns,
                "market_id": market_id,
                "phase": str(phase or "unknown"),
                "selection_probability": probability,
                "sample_weight": 1.0 / probability,
                "valid": int(audit["valid"]),
                "positive_gross": bool(audit.get("positive_top_pair_gross", False)),
                "log_liquidity_usdc": math.log1p(liquidity) if liquidity is not None else None,
                "log_volume_24h_usdc": math.log1p(volume) if volume is not None else None,
                "days_to_expiry": days_to_expiry,
                "spread_per_share": spread,
                "primary_category": str(metadata.get("primary_category") or "unknown"),
                "primary_category_source": str(
                    metadata.get("primary_category_source") or "unavailable"
                ),
                "liquidity_band": str(metadata.get("liquidity_band") or "unknown"),
                "expiry_band": str(metadata.get("expiry_band") or "unknown"),
                "spread_band": str(metadata.get("spread_band") or "unknown"),
            }
        )
    return rows


def _load_frozen_dataset(
    root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("observatory root is missing or unsafe")
    cutoff_name = f"{DATA_CUTOFF_SCAN_ID}.json.gz"
    files = sorted(
        path for path in root.glob("snapshots/scan-*.json.gz") if path.name <= cutoff_name
    )
    scans: list[tuple[int, dict[str, Any], str, str]] = []
    for path in files:
        snapshot, file_sha256 = _read_snapshot(path)
        if (
            snapshot.get("analysis_version") != SOURCE_ANALYSIS_VERSION
            or snapshot.get("source_code_sha256") != SOURCE_CODE_SHA256
            or snapshot.get("discovery_frame_protocol") != DISCOVERY_FRAME_PROTOCOL
        ):
            continue
        scan_id = snapshot.get("scan_id")
        captured_ns = snapshot.get("captured_ns")
        if not isinstance(scan_id, str) or not isinstance(captured_ns, int):
            raise ValueError("eligible snapshot has invalid identity or capture time")
        if path.name != f"{scan_id}.json.gz":
            raise ValueError("snapshot filename and embedded scan id disagree")
        scans.append((captured_ns, snapshot, file_sha256, path.relative_to(root).as_posix()))

    scans.sort(key=lambda item: (item[0], str(item[1]["scan_id"])))
    if not scans or scans[-1][1]["scan_id"] != DATA_CUTOFF_SCAN_ID:
        raise ValueError("the preregistered cutoff snapshot is unavailable")
    if len(scans) < MIN_SCANS:
        raise ValueError("not enough same-revision scans for the preregistered split")

    rows: list[dict[str, Any]] = []
    source_manifest: list[dict[str, str]] = []
    scan_ids: list[str] = []
    for index, (_, snapshot, file_sha256, relative_path) in enumerate(scans):
        scan_id = str(snapshot["scan_id"])
        scan_ids.append(scan_id)
        source_manifest.append(
            {"scan_id": scan_id, "path": relative_path, "compressed_file_sha256": file_sha256}
        )
        rows.extend(_scan_rows(snapshot, scan_index=index))
    return rows, source_manifest, scan_ids


def chronological_unseen_market_split(
    rows: list[dict[str, Any]], scan_ids: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Use first market observation in each period and exclude market overlap."""
    train_scan_count = math.floor(len(scan_ids) * TRAIN_FRACTION)
    if train_scan_count < 2 or train_scan_count >= len(scan_ids):
        raise ValueError("chronological split has an empty side")
    train_scan_set = set(scan_ids[:train_scan_count])
    train_by_market: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["scan_id"] in train_scan_set:
            train_by_market.setdefault(row["market_id"], row)
    seen_train = set(train_by_market)

    evaluation_by_market: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["scan_id"] not in train_scan_set and row["market_id"] not in seen_train:
            evaluation_by_market.setdefault(row["market_id"], row)
    train = sorted(train_by_market.values(), key=lambda row: (row["scan_index"], row["market_id"]))
    evaluation = sorted(
        evaluation_by_market.values(), key=lambda row: (row["scan_index"], row["market_id"])
    )
    if len(train) < MIN_TRAIN_MARKETS or len(evaluation) < MIN_TEST_MARKETS:
        raise ValueError("market-disjoint split is below the preregistered sample floor")
    if {row["market_id"] for row in train} & {row["market_id"] for row in evaluation}:
        raise AssertionError("market identifier leaked across the evaluation split")
    metadata = {
        "training_scan_ids": scan_ids[:train_scan_count],
        "evaluation_scan_ids": scan_ids[train_scan_count:],
        "training_scan_count": train_scan_count,
        "evaluation_scan_count": len(scan_ids) - train_scan_count,
        "training_market_count": len(train),
        "evaluation_unseen_market_count": len(evaluation),
        "overlapping_market_ids_excluded_from_evaluation": len(seen_train),
    }
    return train, evaluation, metadata


def _weighted_metrics(
    labels: NDArray[Any], scores: NDArray[Any], weights: NDArray[Any]
) -> dict[str, Any]:
    scores = np.clip(scores.astype(float), 1e-9, 1.0 - 1e-9)
    total_weight = float(weights.sum())
    prevalence = float(np.average(labels, weights=weights))
    result: dict[str, Any] = {
        "row_count": int(len(labels)),
        "observed_quality_valid_count": int(labels.sum()),
        "observed_quality_valid_fraction": float(labels.mean()),
        "sum_inverse_probability_weights": total_weight,
        "kish_effective_sample_size_before_dependence_adjustment": float(
            total_weight**2 / float(np.square(weights).sum())
        ),
        "observed_inverse_probability_weighted_quality_valid_yield": prevalence,
        "weighted_brier_score": float(np.average((labels - scores) ** 2, weights=weights)),
        "weighted_log_loss": float(
            np.average(
                -(labels * np.log(scores) + (1 - labels) * np.log(1 - scores)),
                weights=weights,
            )
        ),
    }
    if len(np.unique(labels)) == 2:
        result["weighted_roc_auc"] = float(roc_auc_score(labels, scores, sample_weight=weights))
        result["weighted_average_precision"] = float(
            average_precision_score(labels, scores, sample_weight=weights)
        )
    else:
        result["weighted_roc_auc"] = None
        result["weighted_average_precision"] = None
    return result


def _top_quartile_yield(
    rows: list[dict[str, Any]], scores: NDArray[Any], *, tie_seed: str
) -> dict[str, Any]:
    count = max(1, math.ceil(len(rows) * TOP_FRACTION))
    ordering = sorted(
        range(len(rows)),
        key=lambda index: (
            -float(scores[index]),
            hashlib.sha256(f"{tie_seed}:{rows[index]['market_id']}".encode()).hexdigest(),
        ),
    )
    selected = [rows[index] for index in ordering[:count]]
    weights = np.asarray([row["sample_weight"] for row in selected], dtype=float)
    labels = np.asarray([row["valid"] for row in selected], dtype=float)
    return {
        "selected_markets": count,
        "selected_fraction": TOP_FRACTION,
        "weighted_quality_valid_yield": float(np.average(labels, weights=weights)),
        "valid_markets": int(labels.sum()),
    }


def _heuristic_score(row: dict[str, Any]) -> tuple[float, float]:
    liquidity = _finite_nonnegative(row.get("log_liquidity_usdc"))
    spread = _finite_nonnegative(row.get("spread_per_share"))
    return (liquidity if liquidity is not None else -1.0, -(spread if spread is not None else 1e9))


def run_market_quality_experiment(root: Path, preregistration: Path) -> dict[str, Any]:
    rows, source_manifest, scan_ids = _load_frozen_dataset(root)
    training, evaluation, split = chronological_unseen_market_split(rows, scan_ids)
    feature_order = (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)

    def feature_matrix(source_rows: list[dict[str, Any]]) -> NDArray[Any]:
        return np.asarray(
            [
                [
                    *[np.nan if row[name] is None else row[name] for name in NUMERIC_FEATURES],
                    *[row[name] or "unknown" for name in CATEGORICAL_FEATURES],
                ]
                for row in source_rows
            ],
            dtype=object,
        )

    train_frame = feature_matrix(training)
    eval_frame = feature_matrix(evaluation)
    train_labels = np.asarray([row["valid"] for row in training], dtype=int)
    eval_labels = np.asarray([row["valid"] for row in evaluation], dtype=int)
    train_weights = np.asarray([row["sample_weight"] for row in training], dtype=float)
    eval_weights = np.asarray([row["sample_weight"] for row in evaluation], dtype=float)
    if len(np.unique(train_labels)) < 2 or len(np.unique(eval_labels)) < 2:
        raise ValueError("both train and held-out data must contain valid and invalid markets")

    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
            ("encode", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
        ]
    )
    preprocessor = ColumnTransformer(
        [
            ("numeric", numeric, list(range(len(NUMERIC_FEATURES)))),
            (
                "categorical",
                categorical,
                list(range(len(NUMERIC_FEATURES), len(feature_order))),
            ),
        ],
        verbose_feature_names_out=True,
    )
    model = Pipeline(
        [
            ("features", preprocessor),
            (
                "logistic",
                LogisticRegression(C=1.0, solver="lbfgs", max_iter=2_000, random_state=20261016),
            ),
        ]
    )
    model.fit(train_frame, train_labels, logistic__sample_weight=train_weights)
    model_scores = model.predict_proba(eval_frame)[:, 1]
    prevalence = float(np.average(train_labels, weights=train_weights))
    constant_scores = np.full(len(evaluation), prevalence, dtype=float)
    model_metrics = _weighted_metrics(eval_labels, model_scores, eval_weights)
    constant_metrics = _weighted_metrics(eval_labels, constant_scores, eval_weights)

    rng = np.random.default_rng(RANDOM_BASELINE_SEED)
    random_scores = rng.random(len(evaluation))
    random_top = _top_quartile_yield(
        evaluation, random_scores, tie_seed=f"random-{RANDOM_BASELINE_SEED}"
    )
    model_top = _top_quartile_yield(evaluation, model_scores, tie_seed=ANALYSIS_VERSION)
    heuristic_order = sorted(
        evaluation,
        key=lambda row: (
            -_heuristic_score(row)[0],
            -_heuristic_score(row)[1],
            hashlib.sha256(f"heuristic:{row['market_id']}".encode()).hexdigest(),
        ),
    )
    heuristic_ids = {
        row["market_id"]
        for row in heuristic_order[: max(1, math.ceil(len(evaluation) * TOP_FRACTION))]
    }
    heuristic_rows = [row for row in evaluation if row["market_id"] in heuristic_ids]
    heuristic_weights = np.asarray([row["sample_weight"] for row in heuristic_rows], dtype=float)
    heuristic_labels = np.asarray([row["valid"] for row in heuristic_rows], dtype=float)
    heuristic_top = {
        "selected_markets": len(heuristic_rows),
        "selected_fraction": TOP_FRACTION,
        "weighted_quality_valid_yield": float(
            np.average(heuristic_labels, weights=heuristic_weights)
        ),
        "valid_markets": int(heuristic_labels.sum()),
        "ranking": "highest log1p liquidity, then narrowest spread; deterministic market-id hash tie break",
    }

    fitted_features = model.named_steps["features"]
    numeric_names = fitted_features.named_transformers_["numeric"].get_feature_names_out(
        NUMERIC_FEATURES
    )
    categorical_names = fitted_features.named_transformers_["categorical"].get_feature_names_out(
        CATEGORICAL_FEATURES
    )
    feature_names = [str(name) for name in (*numeric_names, *categorical_names)]
    coefficients = model.named_steps["logistic"].coef_[0]
    ranked_coefficients = sorted(
        ((float(coefficients[index]), feature_names[index]) for index in range(len(feature_names))),
        key=lambda item: (-abs(item[0]), item[1]),
    )[:20]
    top_coefficients = [
        {"feature": feature_name, "coefficient": coefficient}
        for coefficient, feature_name in ranked_coefficients
    ]
    phase_metrics: dict[str, Any] = {}
    for phase in sorted({row["phase"] for row in evaluation}):
        indices = [index for index, row in enumerate(evaluation) if row["phase"] == phase]
        phase_weights = eval_weights[indices]
        phase_labels = eval_labels[indices]
        phase_metrics[phase] = {
            "market_count": len(indices),
            "quality_valid_count": int(phase_labels.sum()),
            "inverse_probability_weighted_quality_valid_yield": float(
                np.average(phase_labels, weights=phase_weights)
            ),
        }

    preregistration_raw = preregistration.read_bytes()
    module_path = Path(__file__).resolve()
    artifact = {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "experiment_id": "VERITAS-M2-MARKET-QUALITY-PREDICTION-001",
        "study_id": "VERITAS-M2-COVERAGE-PILOT-002-EXPLORATORY-QUALITY-PREDICTION",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "question": "Can pre-book Gamma metadata rank rotating-stratified markets by same-snapshot quality validity?",
        "target": "existing audit.valid boolean; not opportunity, fill, P&L, or profitability",
        "authenticated_requests": False,
        "orders_submitted": False,
        "live_selection_changed": False,
        "frozen_campaign_changed": False,
        "source": {
            "root": "data/veritas-observatory/snapshots",
            "analysis_version": SOURCE_ANALYSIS_VERSION,
            "source_code_sha256": SOURCE_CODE_SHA256,
            "discovery_frame_protocol": DISCOVERY_FRAME_PROTOCOL,
            "data_cutoff_scan_id": DATA_CUTOFF_SCAN_ID,
            "snapshot_count": len(scan_ids),
            "first_scan_id": scan_ids[0],
            "last_scan_id": scan_ids[-1],
            "source_manifest": source_manifest,
        },
        "preregistration": {
            "path": PREREGISTRATION_PATH.as_posix(),
            "sha256": _sha256(preregistration_raw),
        },
        "analysis_code": {
            "path": module_path.relative_to(module_path.parents[3]).as_posix(),
            "sha256": _sha256(module_path.read_bytes()),
        },
        "split": split,
        "features": {
            "numeric": list(NUMERIC_FEATURES),
            "categorical": list(CATEGORICAL_FEATURES),
            "excluded": ["market_id", "book prices", "economic edges", "future observations"],
        },
        "sampling": {
            "primary_cohort": "rotating_stratified",
            "inverse_inclusion_probability_weighted": True,
            "probability_scope": "within saved bounded Gamma query-response frame only",
            "evaluation_market_ids_disjoint_from_training": True,
        },
        "model": {
            "type": "scikit-learn LogisticRegression",
            "C": 1.0,
            "solver": "lbfgs",
            "max_iter": 2_000,
            "random_state": 20261016,
            "converged": bool(model.named_steps["logistic"].n_iter_[0] < 2_000),
            "training_weighted_prevalence": prevalence,
            "top_coefficients": top_coefficients,
            "not_deployed": True,
        },
        "evaluation": {
            "held_out_first_observation_of_unseen_markets": model_metrics,
            "constant_training_prevalence_baseline": constant_metrics,
            "model_top_quartile": model_top,
            "random_top_quartile": random_top,
            "fixed_liquidity_spread_heuristic_top_quartile": heuristic_top,
            "by_selection_phase": phase_metrics,
            "positive_gross_candidates_in_held_out_markets": sum(
                row["positive_gross"] for row in evaluation
            ),
            "orders_submitted": False,
        },
        "limitations": [
            "The target is one snapshot's measurement-quality gate, not economic opportunity or future market behavior.",
            "The sample is selected from a bounded, changing Gamma query-response union and is not venue-representative.",
            "The seven-scan chronological holdout is short and supports only exploratory internal validation.",
            "A market-disjoint split limits ID leakage but does not make markets or categories independent; the Kish effective size does not adjust for temporal or category dependence.",
            "Reported update ages, batch receipt, and quality validity do not establish venue sequence freshness or atomicity.",
            "No fitted model was deployed and no selection rule, campaign, or service was changed.",
        ],
    }
    return artifact


def write_artifact(artifact: dict[str, Any], output: Path) -> str:
    if output.is_symlink():
        raise ValueError("refusing to write through a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_bytes(raw)
    temporary.replace(output)
    return _sha256(raw)
