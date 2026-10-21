"""Conditional observable-target metrics, matched controls and grouped uncertainty."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np


def coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    rows = [r for r in rows if r.get("target_applicable", True)]
    known = [r for r in rows if r["y"] is not None]
    return dict(
        candidate_decisions=total,
        not_applicable_decisions=total - len(rows),
        eligible_decisions=len(rows),
        measured_targets=len(known),
        unknown_targets=len(rows) - len(known),
        markets=len({r["market_id"] for r in known}),
        families=len({r["family_id"] for r in known}),
        family_time_blocks=len({r["dependence_group"] for r in known}),
        days=sorted({r["day_utc"] for r in known}),
        class_counts={
            str(v): sum(r["y"] == v for r in known) for v in sorted({r["y"] for r in known})
        }
        if known and set(r["y"] for r in known) <= {0.0, 1.0}
        else None,
    )


def grouped_interval(rows: list[dict[str, Any]], losses: Any) -> list[float] | None:
    families: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row, loss in zip(rows, np.asarray(losses, dtype=float), strict=True):
        families[row["family_id"]][row["dependence_group"]].append(float(loss))
    if len(families) < 3 or sum(len(v) for v in families.values()) < 10:
        return None
    rng = np.random.default_rng(719)
    names = sorted(families)
    estimates = []
    for _ in range(150):
        values = []
        for name in rng.choice(names, len(names), replace=True):
            blocks = sorted(families[name])
            for block in rng.choice(blocks, len(blocks), replace=True):
                values.extend(families[name][block])
        estimates.append(float(np.mean(values)))
    return [float(v) for v in np.quantile(estimates, [0.025, 0.975])]


def score(kind: str, y: Any, p: Any) -> float:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2 if kind == "classification" else np.abs(p - y)))


def evaluate(
    rows: list[dict[str, Any]],
    predictions: Any,
    kind: str,
    baseline: Any = None,
    supported: Any = None,
) -> dict[str, Any]:
    if any(r["y"] is None for r in rows):
        raise ValueError("Unknown targets must not enter prediction metrics")
    p = np.asarray(predictions, dtype=float).reshape(-1)
    y = np.array([r["y"] for r in rows], dtype=float)
    if len(p) != len(rows) or not np.isfinite(p).all():
        raise ValueError("Prediction coverage or finiteness failure")
    if kind not in {"classification", "regression"}:
        raise ValueError("Unknown metric kind")
    if kind == "classification" and (np.any((p < 0) | (p > 1)) or np.any((y != 0) & (y != 1))):
        raise ValueError("Invalid classification target/probability")
    if not rows:
        return dict(state="no_measured_targets", rows=0, metrics=None)
    losses = (p - y) ** 2 if kind == "classification" else np.abs(p - y)
    out: dict[str, Any] = dict(
        state="descriptive_conditional_metrics",
        coverage=coverage(rows),
        score=score(kind, y, p),
        score_kind="brier" if kind == "classification" else "mae",
        exploratory_grouped_score_95=grouped_interval(rows, losses),
        uncertainty_notice="Family/time-block resampling; conditional on known targets. Informative censoring and single-day evidence prevent population or economic validation.",
    )
    if kind == "classification":
        clipped = np.clip(p, 1e-7, 1 - 1e-7)
        tp = int(np.sum((p >= 0.5) & (y == 1)))
        positive = int(np.sum(p >= 0.5))
        actual = int(np.sum(y == 1))
        both = len(set(y)) == 2
        out.update(
            brier=float(np.mean(losses)),
            log_loss=float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1 - clipped))),
            observed_positive_rate=float(y.mean()),
            both_classes_present=both,
            precision=tp / positive if both and positive else None,
            recall=tp / actual if both and actual else None,
            threshold=0.5,
            threshold_selected_on_test=False,
            calibration=[],
        )
        for i in range(10):
            mask = np.minimum((p * 10).astype(int), 9) == i
            out["calibration"].append(
                dict(
                    lower=i / 10,
                    upper=(i + 1) / 10,
                    count=int(mask.sum()),
                    predicted=float(p[mask].mean()) if mask.any() else None,
                    observed=float(y[mask].mean()) if mask.any() else None,
                )
            )
        out["ece"] = sum(
            b["count"] * abs(b["predicted"] - b["observed"])
            for b in out["calibration"]
            if b["count"]
        ) / len(rows)
    else:
        residual = p - y
        out.update(
            mae=float(np.mean(np.abs(residual))),
            rmse=float(np.sqrt(np.mean(residual**2))),
            residual_quantiles={
                str(q): float(np.quantile(residual, q)) for q in (0.01, 0.05, 0.5, 0.95, 0.99)
            },
            absolute_error_p95=float(np.quantile(np.abs(residual), 0.95)),
            max_absolute_error=float(np.max(np.abs(residual))),
            prediction_intervals=None,
            prediction_interval_notice="Insufficient multi-day residual coverage; no calibrated interval claimed.",
        )
    if baseline is not None:
        base = np.asarray(baseline, dtype=float).reshape(-1)
        if base.shape != p.shape or not np.isfinite(base).all():
            raise ValueError("Unmatched baseline coverage")
        base_losses = (base - y) ** 2 if kind == "classification" else np.abs(base - y)
        base_score = float(base_losses.mean())
        out.update(
            control_score=base_score,
            baseline_relative_skill=1 - float(losses.mean()) / base_score if base_score else None,
            paired_score_delta=float((losses - base_losses).mean()),
            exploratory_paired_delta_95=grouped_interval(rows, losses - base_losses),
        )
    supported = (
        np.ones(len(rows), dtype=bool) if supported is None else np.asarray(supported, dtype=bool)
    )
    if len(supported) != len(rows):
        raise ValueError("Unmatched support coverage")
    out["within_training_support"] = dict(
        rows=int(supported.sum()),
        outside_rows=int((~supported).sum()),
        score=score(kind, y[supported], p[supported]) if supported.any() else None,
    )
    slices: dict[str, Any] = {}
    for key in ("selection_role", "family_id", "market_id", "day_utc", "horizon_ms"):
        slices[key] = {}
        for value in sorted({str(r[key]) for r in rows}):
            mask = np.array([str(r[key]) == value for r in rows])
            slices[key][value] = dict(
                rows=int(mask.sum()),
                score=score(kind, y[mask], p[mask]),
                positive_rate=float(y[mask].mean()) if kind == "classification" else None,
            )
    slices["categories"] = {}
    for category in sorted({c for r in rows for c in r["categories"]}):
        mask = np.array([category in r["categories"] for r in rows])
        slices["categories"][category] = dict(
            rows=int(mask.sum()), score=score(kind, y[mask], p[mask])
        )
    out["slices"] = slices
    initial = np.array(
        [r["initial_theoretical_edge"] > 0 and r["initial_quantity_supported"] for r in rows]
    )
    out["decision_usefulness"] = dict(
        matched_decisions=len(rows),
        initial_discrepancies=int(initial.sum()),
        state="not_established",
        economic_validation=False,
        explanation="Prediction accuracy does not establish decision usefulness; no actual fills or realized returns are observed.",
    )
    return out
