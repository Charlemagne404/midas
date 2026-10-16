#!/usr/bin/env python3
"""Emit planning-only power sensitivity from the committed Gate A baseline."""

from __future__ import annotations

import json
from pathlib import Path

from midas.veritas.followup_power import build_followup_power_report

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "docs" / "VERITAS_GATE_A_BASELINE.json"


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text())
    forensics = baseline["frozen_campaign_forensics"]
    coverage = forensics["coverage"]
    one_second = forensics["outcomes"]["by_horizon"]["1000"]["counts_by_status"]
    report = build_followup_power_report(
        baseline_decisions=coverage["decisions"],
        valid_initial_decisions=coverage["valid_initial_decisions"],
        baseline_successes=one_second["observed_public_measurement"],
        expected_decisions_per_day=coverage["decisions"],
        maximum_days=14,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
