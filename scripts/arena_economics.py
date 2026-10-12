"""Fixed-action economic sensitivity from verified simulation accounting paths."""

import argparse
import json
import math
import os
import time
import uuid
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, read_replay, sha256
from midas.economics.attestation import digest
from midas.laboratory.spec import Costs

YEAR_MS = Decimal(365 * 86_400_000)


def reprice(result: dict[str, Any], costs: Costs) -> Decimal:
    """Apply the Laboratory terminal cost formula to unchanged fills/capital paths."""
    metrics, final = result["metrics"], result["final_portfolio"]
    return (
        Decimal(metrics["gross_settled_virtual_pnl"])
        - Decimal(metrics["capital_time_integral_ms"])
        * Decimal(str(costs.annual_financing_rate))
        / YEAR_MS
        - Decimal(metrics["fill_count"]) * Decimal(str(costs.operating_per_fill))
        - Decimal(final.get("settled_positions", 0)) * Decimal(str(costs.redemption_cost))
        - Decimal(final.get("settlement_proceeds", "0"))
        * (1 - Decimal(str(costs.collateral_value_factor)))
    )


def summarize(rows: list[dict[str, Any]], values: list[float], seed: int = 991) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row, value in zip(rows, values, strict=True):
        groups[row["base_episode_id"]].append(value)
    if not groups:
        raise ValueError("Economic summary needs observations")
    grouped = np.asarray([np.mean(groups[g]) for g in sorted(groups)])
    rng = np.random.default_rng(seed)
    boot = rng.choice(grouped, (500, len(grouped)), replace=True).mean(axis=1)
    pnl = np.asarray(values)
    tail_loss = max(0.0, -float(np.sort(pnl)[: max(1, math.ceil(0.05 * len(pnl)))].mean()))
    return {
        "base_episodes": len(groups),
        "variants": len(rows),
        "mean_pnl": float(pnl.mean()),
        "worst_pnl": float(pnl.min()),
        "cvar_05_loss": tail_loss,
        "mean_pnl_episode_bootstrap_95": np.quantile(boot, [0.025, 0.975]).tolist(),
    }


def analyze(root: Path, tournament: str) -> dict[str, Any]:
    directory = artifact_path(root, "tournaments", tournament)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Frozen comparison rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    if len(rows) != manifest["variants"]:
        raise ValueError("Incomplete comparison")
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    coverage: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        identity = row["base_episode_id"], row["execution_model"]
        if identity in coverage[row["policy"]]:
            raise ValueError("Duplicate comparison observation")
        coverage[row["policy"]].add(identity)
        replay = read_replay(directory / "replays" / f"{row['id']}.json")
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if (
            replay["row"] != row
            or not row["passed"]
            or digest(core) != row["result_hash"]
            or digest(result["journal"]) != result["journal_hash"]
        ):
            raise ValueError("Replay accounting integrity failed")
        # Check the aggregate cost formula against the retained original result.
        original = Costs.model_validate(result["scenario"]["costs"])
        if abs(
            reprice(result, original) - Decimal(result["metrics"]["net_simulated_pnl"])
        ) > Decimal("1e-18"):
            raise ValueError("Saved path does not reproduce original cost accounting")
        # Integrity is checked before discarding the large journal. Subsequent
        # overlays need only these five accounting totals, not retained traces.
        compact = {
            "metrics": {
                key: result["metrics"][key]
                for key in ("gross_settled_virtual_pnl", "capital_time_integral_ms", "fill_count")
            },
            "final_portfolio": {
                key: result["final_portfolio"].get(key, 0)
                for key in ("settled_positions", "settlement_proceeds")
            },
        }
        grouped[row["policy"]].append((row, compact))
    if "no_trade" not in coverage or any(v != coverage["no_trade"] for v in coverage.values()):
        raise ValueError("Unmatched comparison coverage")
    # One-factor-at-a-time, hypothetical absolute costs. This does not vary venue fees.
    grid = (
        [("operating_per_fill", value) for value in ("0", ".01", ".05", ".1", ".25", ".5", "1")]
        + [("redemption_cost", v) for v in ("0", ".01", ".1", ".5", "1")]
        + [("annual_financing_rate", v) for v in ("0", ".05", ".2", "1")]
        + [("collateral_value_factor", v) for v in ("1", ".99", ".95", ".9")]
    )
    records = []
    for policy, observations in sorted(grouped.items()):
        selected = [r for r, _ in observations]
        base_costs = Costs()
        baseline_values = [float(reprice(r, base_costs)) for _, r in observations]
        baseline = summarize(selected, baseline_values)
        points = []
        for parameter, value in grid:
            costs = Costs.model_validate({parameter: value})
            summary = summarize(selected, [float(reprice(r, costs)) for _, r in observations])
            summary.update(
                parameter=parameter,
                value=value,
                score=summary["mean_pnl"]
                - manifest["configuration"].get("tail_loss_weight", 1) * summary["cvar_05_loss"],
            )
            points.append(summary)
        gross_total = sum((reprice(r, base_costs) for _, r in observations), Decimal(0))
        fills = sum(int(r["metrics"]["fill_count"]) for _, r in observations)
        baseline_score = (
            baseline["mean_pnl"]
            - manifest["configuration"].get("tail_loss_weight", 1) * baseline["cvar_05_loss"]
        )
        # The mean zero-crossing is exact under this linear, fixed-path overlay.
        break_even = str(gross_total / fills) if fills and gross_total > 0 else None
        records.append(
            {
                "policy": policy,
                "baseline_zero_extra_costs": baseline,
                "baseline_downside_score": baseline_score,
                "mean_break_even_operating_per_fill": break_even,
                "break_even_status": "POSITIVE_MEAN_FIXED_PATH"
                if break_even
                else "NO_POSITIVE_MEAN_MARGIN"
                if fills
                else "NO_FILLS",
                "points": points,
            }
        )
    record = {
        "version": "fixed-path-economics-1",
        "tournament_id": tournament,
        "created_at": time.time(),
        "rows_sha256": manifest["rows_sha256"],
        "analysis_source_sha256": sha256(Path(__file__)),
        "policies": records,
        "units": {
            "operating_per_fill": "virtual USD per actual simulated fill event",
            "redemption_cost": "virtual USD per settled position",
            "annual_financing_rate": "fraction per 365-day year",
            "collateral_value_factor": "fraction of gross settlement proceeds retained",
        },
        "limitations": [
            "Synthetic hypothetical fixed-action accounting overlay; no model fitting, policy reoptimization or live trading.",
            "Each axis resets other extra costs to zero and collateral value to one; these are hypothetical scenarios, not observed market fee schedules.",
            "Original exchange fees remain embedded in gross P&L. Operating-per-fill cost is an additional charge, not a taker fee estimate.",
            "Fills, decisions and capital paths are held fixed. Cost-aware risk admission, changed order sizes, execution delay and recovery require new simulations.",
            "Financing uses the actual retained reserved-plus-locked capital integral. Short synthetic lockup cannot establish sensitivity to real settlement delays.",
            "Confidence intervals resample base episodes with execution variants grouped. Break-even values apply to synthetic mean P&L, not guaranteed profitability or downside protection.",
        ],
    }
    record["report_digest"] = digest(record)
    return record


def publish(output: Path, report: dict[str, Any]) -> None:
    """Capture producer bytes and publish exclusively, retaining complete evidence."""
    if output.exists():
        raise ValueError("Preserve existing economic report; choose a new output path")
    source = Path(__file__)
    if sha256(source) != report["analysis_source_sha256"]:
        raise ValueError("Economic analysis source changed before publication")
    snapshot = output.with_name(f"{output.stem}-source-{report['analysis_source_sha256']}.py")
    if snapshot.exists() and sha256(snapshot) != report["analysis_source_sha256"]:
        raise ValueError("Economic source snapshot has changed")
    if not snapshot.exists():
        atomic_bytes(snapshot, source.read_bytes())
    temporary = output.with_name(f".economics-{uuid.uuid4().hex}.json")
    try:
        atomic_json(temporary, report)
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
        directory = os.open(output.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--tournament", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (
        args.output or artifact_path(args.root, "tournaments", args.tournament) / "economics.json"
    )
    if output.exists():
        raise ValueError("Preserve existing economic report; choose a new output path")
    result = analyze(args.root, args.tournament)
    publish(output, result)
    print(json.dumps({"path": str(output), "report_digest": result["report_digest"]}))
