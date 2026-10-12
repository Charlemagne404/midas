"""Describe admission cutoffs separately from realized exposure and loss bounds."""

import argparse
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest

FIELDS = {
    "max_drawdown": ("max_drawdown", "Drawdown limit"),
    "daily_loss": ("max_daily_loss", "Daily simulated loss limit"),
    "cumulative_loss": ("max_cumulative_loss", "Cumulative simulated loss limit"),
    "net_exposure_shares": (
        "max_unmatched_quantity",
        "Existing partial position requires reconciliation",
    ),
}


def number(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Risk counters must be finite and nonnegative")
    return result


def measure(result: dict[str, Any]) -> dict[str, Any]:
    journal = result["journal"]
    if not journal:
        raise ValueError("Retained risk journal required")
    limits = journal[0]["before"]["risk_limits"]
    peaks = {field: max(number(j["after"][field]) for j in journal) for field in FIELDS}
    above = {field: peaks[field] > number(limits[limit]) for field, (limit, _) in FIELDS.items()}
    admitted = checked = 0
    violations = []
    rejections: Counter[str] = Counter()
    for event in journal:
        if event["kind"] != "decision":
            continue
        decision = event["after"]["decisions"][-1]
        risk = decision["risk"]
        checked += 1
        admitted += bool(risk["allowed"])
        for field, (limit, reason) in FIELDS.items():
            value = number(event["before"][field])
            threshold = number(risk["limits"][limit])
            triggered = (
                value > threshold
                if field == "net_exposure_shares"
                else value > 0 and value >= threshold
            )
            if triggered and risk["allowed"]:
                violations.append(
                    {
                        "decision_id": decision["id"],
                        "field": field,
                        "before": str(value),
                        "threshold": str(threshold),
                    }
                )
            if not risk["allowed"] and reason in risk["reasons"]:
                rejections[reason] += 1
    return {
        "decisions_checked": checked,
        "admitted_decisions": admitted,
        "admissions_after_observed_cutoff": violations,
        "peak_observed": {field: str(value) for field, value in peaks.items()},
        "observed_above_admission_trigger": above,
        "cutoff_rejection_reasons": dict(rejections),
        "interpretation": "Post-fill exposure or loss above an admission trigger is not automatically an invariant violation. These gates reject new proposals; they do not execute a hedge, unwind inventory, cancel every prior action or guarantee maximum realized loss.",
    }


def audit(root: Path, tournament_id: str, policy: str) -> dict[str, Any]:
    directory = artifact_path(root, "tournaments", tournament_id)
    manifest = json.loads((directory / "manifest.json").read_text())
    if sha256(directory / "rows.json") != manifest["rows_sha256"]:
        raise ValueError("Frozen rows changed")
    rows = json.loads((directory / "rows.json").read_text())
    selected = [r for r in rows if r["policy"] == policy]
    expected = {
        (r["base_episode_id"], r["execution_model"]) for r in rows if r["policy"] == "no_trade"
    }
    if (
        len(rows) != manifest["variants"]
        or not expected
        or len(selected) != len(expected)
        or {(r["base_episode_id"], r["execution_model"]) for r in selected} != expected
    ):
        raise ValueError("Incomplete matched policy coverage")
    observations = []
    for row in selected:
        replay = read_replay(directory / "replays" / (row["id"] + ".json"))
        result = replay["result"]
        core = {
            k: v
            for k, v in result.items()
            if k not in {"result_hash", "journal_hash", "journal", "runtime"}
        }
        if (
            not row["passed"]
            or replay["row"] != row
            or digest(core) != row["result_hash"]
            or digest(result["journal"]) != result["journal_hash"]
        ):
            raise ValueError("Saved financial/journal integrity failed")
        observations.append(
            {
                "row_id": row["id"],
                "base_episode_id": row["base_episode_id"],
                "execution_model": row["execution_model"],
                **measure(result),
            }
        )
    return {
        "analysis_version": "admission-versus-loss-bounds-1",
        "tournament_id": tournament_id,
        "policy": policy,
        "producer_sha256": sha256(Path(__file__)),
        "rows_sha256": manifest["rows_sha256"],
        "source_groups": len({r["base_episode_id"] for r in selected}),
        "correlated_variants": len(selected),
        "decisions_checked": sum(r["decisions_checked"] for r in observations),
        "admissions_after_observed_cutoff": sum(
            len(r["admissions_after_observed_cutoff"]) for r in observations
        ),
        "variants_observed_above_trigger": {
            field: sum(r["observed_above_admission_trigger"][field] for r in observations)
            for field in FIELDS
        },
        "observations": observations,
        "scope": "Checks four recorded pre-decision counters and their admission cutoffs. It does not reimplement all capital, timestamp, market-overlap or potential unmatched-leg admission rules. Counts are descriptive correlated variants, not independent risk probabilities.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--tournament", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.root, args.tournament, args.policy)
    from scripts.capture_public_series import publish_exclusive

    publish_exclusive(
        args.output, json.dumps(report, indent=2, sort_keys=True, allow_nan=False).encode()
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "source_groups",
                    "correlated_variants",
                    "decisions_checked",
                    "admissions_after_observed_cutoff",
                    "variants_observed_above_trigger",
                )
            }
        )
    )
