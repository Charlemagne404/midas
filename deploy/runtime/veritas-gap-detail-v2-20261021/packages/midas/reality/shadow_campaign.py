"""Immutable prospective period, source rules, models and analysis plan."""

from __future__ import annotations

import importlib.metadata
import json
import time
from pathlib import Path
from typing import Any

from .execution_research import families
from .model_registry import load
from .research_schema import FEATURE_VERSION, LABEL_VERSION, LIMITATIONS, digest
from .storage import atomic_json, file_hash

VERSION = "reality-forward-campaign-v1"
FILES = (
    "shadow_campaign.py",
    "shadow_source.py",
    "shadow_store.py",
    "shadow_policy.py",
    "shadow_worker.py",
    "execution_research.py",
    "research_measurements.py",
    "research_schema.py",
    "reconstruction.py",
    "storage.py",
    "model_features.py",
    "model_registry.py",
    "model_fitting.py",
    "model_metrics.py",
    "foundry.py",
)


def source_files() -> dict[str, Path]:
    result = {"reality/" + n: Path(__file__).with_name(n) for n in FILES}
    base = Path(__file__).parents[1]
    for directory in ("arbitrage", "core", "economics", "risk"):
        result.update(
            {
                directory + "/" + p.name: p
                for p in (base / directory).glob("*.py")
                if p.name != "__init__.py"
            }
        )
    return result


def verify(plan: dict[str, Any], *, check_code: bool = True) -> None:
    if digest(plan["identity"]) != plan["campaign_id"]:
        raise ValueError("Campaign identity corruption")
    i = plan["identity"]
    if (
        i["frozen_ns"] >= i["start_ns"]
        or i["start_ns"] >= i["end_ns"]
        or i["end_ns"] - i["start_ns"] > 30 * 86400 * 10**9
    ):
        raise ValueError("Campaign was not frozen before a bounded future period")
    if i["feature_version"] != FEATURE_VERSION or i["label_version"] != LABEL_VERSION:
        raise ValueError("Campaign measurement version incompatible")
    if check_code and {n: file_hash(p) for n, p in source_files().items()} != i["code"]:
        raise ValueError("Use frozen campaign code; no mid-period implementation retuning")


def freeze(
    root: Path,
    raw: Path,
    training: Path,
    run_id: str,
    producer_hash: str,
    selection: dict[str, Any],
    *,
    fixture: bool = False,
    start_ns: int | None = None,
    days: int = 14,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    if (root / "campaign.json").exists():
        plan = json.loads((root / "campaign.json").read_text())
        verify(plan)
        return dict(plan)
    now = time.time_ns()
    start = start_ns or now + 2 * 10**9
    report_path = training / "runs" / run_id / "report.json"
    report = json.loads(report_path.read_text())
    models = {}
    eligible = {}
    for target, data in report["targets"].items():
        if not data.get("selected_by_validation"):
            continue
        model = load(training, data["selected_by_validation"])
        models[target] = dict(
            model_id=model["info"]["model_id"],
            weights_sha256=model["info"]["weights_sha256"],
            metadata_sha256=model["info"]["identity"]["metadata_sha256"],
        )
        eligible[target] = data.get("eligibility", {}).get("policy_eligible", False)
    identity = dict(
        version=VERSION,
        source_kind="labeled_fixture" if fixture else "genuine_public_recording",
        frozen_ns=now,
        start_ns=start,
        end_ns=start + (duration_seconds if duration_seconds is not None else days * 86400) * 10**9,
        raw_root=str(raw.resolve()),
        training_root=str(training.resolve()),
        training_run_id=run_id,
        training_report_sha256=file_hash(report_path),
        models=models,
        eligibility_at_freeze=eligible,
        allowed_producer_hashes=[producer_hash],
        allowed_reconstruction_versions=[4],
        market_selection=selection,
        feature_version=FEATURE_VERSION,
        label_version=LABEL_VERSION,
        scenarios=[a.manifest() for a in families()],
        horizons_ms=[100, 300, 1000, 5000],
        future_tolerance_ms=500,
        followup_availability_grace_ms=2000,
        max_freshness_ms=5000,
        max_skew_ms=250,
        max_decision_input_lag_ms=250,
        baseline_stride_ms=30000,
        opportunity_stride_ms=5000,
        observatory_stride_ms=5000,
        quantity="5",
        capital="100",
        settlement_lock_days=7,
        max_decisions=400000,
        max_observations=4000000,
        evidence_budget_bytes=4 * 1024**3,
        reserve_bytes=20 * 1024**3,
        risk=dict(
            max_positions=5,
            max_opportunity_capital="25",
            max_market_exposure="25",
            max_family_exposure="50",
            max_total_exposure="50",
            persistence_threshold=0.9,
            disruption_threshold=0.1,
        ),
        risk_objective="Avoid unsupported hypothetical risk; reserve worst-case acquisition capital for declared seven-day lock; no inferred settlement proceeds",
        controls=[
            "no_trade",
            "mathematical_filter",
            "prometheus_control",
            "conservative_risk",
            "prediction_gate",
            "recovery_guard",
        ],
        analysis=dict(
            version="reality-prospective-analysis-v1",
            promotion=False,
            threshold_retuning=False,
            paired_on="Same recorded source/decision across controls and scenarios",
            grouping="Connected event/condition/negative-risk families and UTC time blocks; shared feed remains correlated",
            reported="Decision behavior, censoring, public persistence/depth/price changes and per-trial hypothetical bounds; no summed realized P&L",
            recovery="Declared quoted-bid unwind only where later observed depth supports quantity/minimum; otherwise retain unmatched bounds",
            eligibility="Experimental probes do not authorize a policy; no champion manufactured",
        ),
        code={n: file_hash(p) for n, p in source_files().items()},
        toolchain={n: importlib.metadata.version(n) for n in ("numpy", "scikit-learn")},
    )
    plan = dict(campaign_id=digest(identity), identity=identity, limitations=LIMITATIONS)
    verify(plan)
    for path in root.parent.glob("*/campaign.json"):
        old = json.loads(path.read_text())["identity"]
        if old["source_kind"] == identity["source_kind"] and max(old["start_ns"], start) <= min(
            old["end_ns"], identity["end_ns"]
        ):
            raise ValueError("Forward period overlaps an existing frozen campaign")
    for name, path in source_files().items():
        target = root / "code" / "midas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    for package in ("", "reality", "arbitrage", "core", "economics", "risk"):
        folder = root / "code" / "midas" / package
        (folder / "__init__.py").write_text(
            "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
        )
    atomic_json(root / "campaign.json", plan)
    return plan
