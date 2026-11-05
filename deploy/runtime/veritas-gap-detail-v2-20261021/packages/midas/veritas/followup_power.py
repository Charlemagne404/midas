"""Planning-only power sensitivity for a future public follow-up study."""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any

VERSION = "veritas-followup-power-v1"
DEFAULT_DESIGN_EFFECTS = (1.0, 1.5, 2.0, 3.0)


def _probability(value: float, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a probability") from error
    if not math.isfinite(result) or not 0 < result < 1:
        raise ValueError(f"{name} must be strictly between 0 and 1")
    return result


def required_independent_n_per_arm(
    control_probability: float,
    treatment_probability: float,
    *,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """Return a normal-approximation sample size for a two-sided proportion test."""
    control = _probability(control_probability, "Control probability")
    treatment = _probability(treatment_probability, "Treatment probability")
    significance = _probability(alpha, "Alpha")
    target_power = _probability(power, "Power")
    if treatment <= control:
        raise ValueError("Treatment probability must exceed the control probability")

    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - significance / 2)
    z_power = normal.inv_cdf(target_power)
    pooled = (control + treatment) / 2
    numerator = z_alpha * math.sqrt(2 * pooled * (1 - pooled)) + z_power * math.sqrt(
        control * (1 - control) + treatment * (1 - treatment)
    )
    return math.ceil(numerator**2 / (treatment - control) ** 2)


def build_followup_power_report(
    *,
    baseline_decisions: int,
    valid_initial_decisions: int,
    baseline_successes: int,
    expected_decisions_per_day: int,
    relative_minimum_detectable_lift: float = 0.5,
    alpha: float = 0.05,
    power: float = 0.8,
    maximum_days: int = 14,
    design_effects: tuple[float, ...] = DEFAULT_DESIGN_EFFECTS,
) -> dict[str, Any]:
    """Build an explicitly unclustered planning baseline and DE sensitivity grid."""
    if baseline_decisions <= 0 or expected_decisions_per_day <= 0 or maximum_days <= 0:
        raise ValueError("Decision counts and the study window must be positive")
    if not 0 < baseline_successes < baseline_decisions:
        raise ValueError("Successes must be within the baseline decision count")
    if not 0 <= valid_initial_decisions <= baseline_decisions:
        raise ValueError("Valid initial decisions must be within the baseline count")
    if baseline_successes > valid_initial_decisions:
        raise ValueError("Successes cannot exceed valid initial decisions")
    lift = float(relative_minimum_detectable_lift)
    if not math.isfinite(lift) or lift <= 0:
        raise ValueError("Relative minimum detectable lift must be positive")
    effects = tuple(float(effect) for effect in design_effects)
    if not effects or any(not math.isfinite(effect) or effect < 1 for effect in effects):
        raise ValueError("Design effects must be finite and at least 1")

    control = baseline_successes / baseline_decisions
    treatment = control * (1 + lift)
    if treatment >= 1:
        raise ValueError("Target probability must be below 1")
    independent_n = required_independent_n_per_arm(
        control,
        treatment,
        alpha=alpha,
        power=power,
    )
    expected_slots = expected_decisions_per_day * maximum_days
    sensitivity = []
    for effect in effects:
        per_arm = math.ceil(independent_n * effect)
        total = 2 * per_arm
        sensitivity.append(
            {
                "planning_design_effect": effect,
                "required_slots_per_arm": per_arm,
                "required_total_slots": total,
                "expected_days_at_baseline_volume": total / expected_decisions_per_day,
                "fits_maximum_window_capacity": total <= expected_slots,
            }
        )

    return {
        "experiment_id": "VERITAS-GATE-A-FOLLOWUP-POWER-20261015-001",
        "analysis_version": VERSION,
        "evidence_class": "derived_planning_sensitivity_only",
        "source_evidence": "docs/VERITAS_GATE_A_BASELINE.json",
        "baseline": {
            "decisions": baseline_decisions,
            "valid_initial_decisions": valid_initial_decisions,
            "invalid_initial_decisions": baseline_decisions - valid_initial_decisions,
            "one_second_public_measurements": baseline_successes,
            "one_second_yield_per_scheduled_decision": control,
            "one_second_yield_per_valid_initial_decision": (
                baseline_successes / valid_initial_decisions if valid_initial_decisions else None
            ),
            "selected_cohort_only": True,
        },
        "planning_assumptions": {
            "relative_minimum_detectable_lift": lift,
            "target_treatment_probability": treatment,
            "two_sided_alpha": alpha,
            "power": power,
            "independent_bernoulli_sample_size_per_arm": independent_n,
            "sample_size_method": "normal approximation for two independent proportions",
            "cluster_design_effects_are_empirical_estimates": False,
        },
        "cluster_sensitivity": sensitivity,
        "capacity": {
            "expected_scheduled_decisions_per_day": expected_decisions_per_day,
            "maximum_days": maximum_days,
            "expected_total_slots_at_baseline_volume": expected_slots,
            "maximum_design_effect_supported_by_slot_count": expected_slots / (2 * independent_n),
        },
        "limitations": [
            "The baseline is one selected cohort and its rate is not assumed stationary.",
            "No market, time-block, family, or repeated-measure correlation was estimated.",
            "A single design effect is only a sensitivity illustration; crossed market and time dependence needs a design-specific power analysis.",
            "This calculation does not establish campaign feasibility, fills, or profitability.",
        ],
        "campaign_created_or_started": False,
        "orders_submitted": False,
        "promotion": "planning sensitivity only; no campaign or strategy promotion",
    }
