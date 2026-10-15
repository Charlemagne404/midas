import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.veritas import MAX_ARTIFACT_BYTES, router


def write_artifact(root: Path, name: str, value: dict) -> None:
    path = root / "docs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture_client(tmp_path: Path) -> TestClient:
    write_artifact(
        tmp_path,
        "VERITAS_GATE_A_BASELINE.json",
        {
            "frozen_campaign_forensics": {
                "coverage": {
                    "decisions": 10,
                    "valid_initial_decisions": 4,
                    "connected_families": 2,
                    "utc_days": ["2026-10-15"],
                },
                "outcomes": {
                    "by_horizon": {
                        "1000": {
                            "counts_by_status": {
                                "observed_public_measurement": 1,
                                "censored": 9,
                            },
                            "pending": 0,
                            "censor_reasons": {
                                "future_observation_unavailable": 3,
                                "invalid_at_decision": 6,
                            },
                        }
                    }
                },
                "policy_actions": {"no_trade": {"abstain": 10}},
            }
        },
    )
    write_artifact(
        tmp_path,
        "VERITAS_GATE_A_RAW_FUNNEL_003.json",
        {
            "captured_at_utc": "2026-10-15T00:00:00+00:00",
            "campaign_id": "campaign-fixture",
            "markets": [{"selection_role": "fixture"}],
            "source_segments": 3,
            "source_bytes": 80,
            "period_frame_records": 20,
            "touched_market_frame_states": 12,
            "quality_valid_states": 10,
            "positive_top_ask_pair_states": 0,
            "positive_top_with_quantity_depth_states": 0,
            "quantity_depth_complete_states": 10,
            "positive_full_depth_pre_fee_states": 0,
            "positive_full_depth_minimum_notional_satisfied_states": 0,
            "quantity_requested": "5",
            "pre_fee_top_edge_distribution": {
                "count": 10,
                "maximum": "-0.001",
                "median_nearest_rank": "-0.01",
                "positive_count": 0,
            },
        },
    )
    sensitivity = {
        "quantity_shares_per_leg": "100",
        "complete_pair_pnl_scenarios_usdc": {
            "single_match_rounding_worst_resolution": "1.4",
            "fragmentation_safe_fee_worst_resolution": "-0.8",
        },
        "unmatched_leg_loss": {"conservative_unmatched_leg_loss_usdc": "50.2"},
        "break_even": {
            "single_match_rounding_scenario": {
                "minimum_matched_completions_per_unmatched_event": "35.4",
                "required_matched_rate_by_unmatched_event_rate": [
                    {
                        "unmatched_event_rate_assumption": "0.01",
                        "required_matched_completion_rate": "0.354",
                        "probability_mass_feasible": True,
                    },
                    {
                        "unmatched_event_rate_assumption": "0.05",
                        "required_matched_completion_rate": "1.77",
                        "probability_mass_feasible": False,
                    },
                ],
            }
        },
    }
    write_artifact(
        tmp_path,
        "VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json",
        {
            "execution_break_even_scenarios": {
                scenario: {"quantity_scenarios": [sensitivity]}
                for scenario in ("full_displayed_depth", "half_displayed_depth")
            }
        },
    )
    write_artifact(tmp_path, "VERITAS_GATE_B_CAPACITY_001.json", {"fixture": True})
    write_artifact(
        tmp_path,
        "VERITAS_RESEARCH_LEDGER.json",
        {
            "hypotheses": [
                {
                    "hypothesis_id": "VERITAS-H001",
                    "title": "Fixture finding",
                    "status": "continue",
                    "result": {"status": "completed"},
                    "decision": "Keep observing.",
                }
            ]
        },
    )
    write_artifact(
        tmp_path,
        "VERITAS_RESEARCH_INVENTORY.json",
        {"experiments": [{}], "models": [], "candidates": []},
    )
    app = FastAPI()
    app.include_router(router(tmp_path))
    return TestClient(app)


def test_overview_uses_bounded_versioned_evidence_without_raw_paths(tmp_path):
    client = fixture_client(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_independent_evidence"
    assert data["coverage"]["markets"] == 1
    assert data["opportunity_funnel"]["positive_top_ask_pair_states"] == 0
    assert data["followup_yield"]["by_horizon"][0]["observed"] == 1
    assert data["followup_yield"]["by_horizon"][0]["censored"] == 3
    assert data["followup_yield"]["by_horizon"][0]["invalid_initial"] == 6
    assert data["baseline_policies"]["all_abstained"] is True
    assert data["execution_sensitivity"]["actual_fills"] == "unknown_counterfactual"
    assert data["execution_sensitivity"]["break_even_at_5pct_unmatched_feasible"] is False
    assert "source_root" not in response.text


def test_artifact_allowlist_hash_and_size_bound(tmp_path):
    client = fixture_client(tmp_path)

    response = client.get("/api/veritas/artifacts/raw-funnel")
    assert response.status_code == 200
    digest = hashlib.sha256(
        (tmp_path / "docs/VERITAS_GATE_A_RAW_FUNNEL_003.json").read_bytes()
    ).hexdigest()
    assert response.json()["file_sha256"] == digest
    assert client.get("/api/veritas/artifacts/../../secret").status_code == 404
    assert client.get("/api/veritas/artifacts/unknown").status_code == 404

    oversized = tmp_path / "docs/VERITAS_GATE_A_RAW_FUNNEL_003.json"
    oversized.write_text(" " * (MAX_ARTIFACT_BYTES + 1))
    assert client.get("/api/veritas/artifacts/raw-funnel").status_code == 413

    oversized.unlink()
    target = tmp_path / "outside-docs.json"
    target.write_text("{}")
    oversized.symlink_to(target)
    assert client.get("/api/veritas/artifacts/raw-funnel").status_code == 404


def test_overview_rejects_followup_counts_that_do_not_reconcile(tmp_path):
    client = fixture_client(tmp_path)
    baseline = tmp_path / "docs/VERITAS_GATE_A_BASELINE.json"
    data = json.loads(baseline.read_text())
    data["frozen_campaign_forensics"]["outcomes"]["by_horizon"]["1000"]["counts_by_status"][
        "censored"
    ] = 8
    baseline.write_text(json.dumps(data))

    assert client.get("/api/veritas/overview").status_code == 503
