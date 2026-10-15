import gzip
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


def write_censoring_artifact(root: Path, *, campaign_id: str = "campaign-fixture") -> None:
    write_artifact(
        root,
        "VERITAS_GATE_A_CENSORING_003.json",
        {
            "artifact_id": "VERITAS-GATE-A-CENSORING-TEST",
            "captured_at_utc": "2026-10-15T08:00:00Z",
            "analysis": {
                "analysis_version": "veritas-forward-forensics-v1.3",
                "campaign_id": campaign_id,
                "query": {"truncated": False},
                "coverage": {
                    "decisions": 10,
                    "markets": 2,
                    "connected_families": 2,
                    "valid_initial_decisions": 4,
                    "invalid_initial_decisions": 6,
                    "utc_days": ["2026-10-15"],
                },
                "outcomes": {
                    "by_horizon": {
                        "1000": {
                            "counts_by_status": {
                                "observed_public_measurement": 1,
                                "censored": 9,
                            },
                            "censor_reasons": {
                                "future_observation_unavailable": 3,
                                "invalid_at_decision": 6,
                            },
                            "pending": 0,
                        }
                    },
                    "censoring_detail": {
                        "by_initial_quality_regime_horizon": {
                            "items": [
                                {
                                    "initial_quality_regime": "valid_initial_observation",
                                    "horizon_ms": 1000,
                                    "scheduled_followups": 4,
                                    "resolved_followups": 4,
                                    "counts_by_status": {
                                        "observed_public_measurement": 1,
                                        "censored": 3,
                                    },
                                    "pending_followups": 0,
                                },
                                {
                                    "initial_quality_regime": "invalid_initial:stale_book",
                                    "horizon_ms": 1000,
                                    "scheduled_followups": 6,
                                    "resolved_followups": 6,
                                    "counts_by_status": {"censored": 6},
                                    "pending_followups": 0,
                                },
                            ]
                        },
                        "by_market_horizon": {
                            "items": [
                                {
                                    "market_id": "market-a",
                                    "horizon_ms": 1000,
                                    "scheduled_followups": 4,
                                    "resolved_followups": 4,
                                    "pending_followups": 0,
                                    "counts_by_status": {
                                        "observed_public_measurement": 1,
                                        "censored": 3,
                                    },
                                    "censor_reasons": {"future_observation_unavailable": 3},
                                    "initial_quality_regimes": {"valid_initial_observation": 4},
                                }
                            ]
                        },
                        "by_utc_hour_horizon": {
                            "items": [
                                {
                                    "utc_hour": "2026-10-15T08:00:00Z",
                                    "horizon_ms": 1000,
                                    "scheduled_followups": 10,
                                    "resolved_followups": 10,
                                    "pending_followups": 0,
                                    "counts_by_status": {
                                        "observed_public_measurement": 1,
                                        "censored": 9,
                                    },
                                    "censor_reasons": {
                                        "future_observation_unavailable": 3,
                                        "invalid_at_decision": 6,
                                    },
                                    "initial_quality_regimes": {
                                        "valid_initial_observation": 4,
                                        "invalid_initial:stale_book": 6,
                                    },
                                }
                            ]
                        },
                        "by_censoring_regime_horizon": {"1000": {"items": []}},
                    },
                },
            },
        },
    )


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
        "VERITAS_GATE_A_RAW_FUNNEL_004.json",
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
    assert data["opportunity_observatory"]["status"] == "not_started"
    assert data["finalized_reality_source"]["status"] == "not_started"
    assert "source_root" not in response.text


def test_artifact_allowlist_hash_and_size_bound(tmp_path):
    client = fixture_client(tmp_path)

    response = client.get("/api/veritas/artifacts/raw-funnel")
    assert response.status_code == 200
    digest = hashlib.sha256(
        (tmp_path / "docs/VERITAS_GATE_A_RAW_FUNNEL_004.json").read_bytes()
    ).hexdigest()
    assert response.json()["file_sha256"] == digest
    assert client.get("/api/veritas/artifacts/../../secret").status_code == 404
    assert client.get("/api/veritas/artifacts/unknown").status_code == 404

    oversized = tmp_path / "docs/VERITAS_GATE_A_RAW_FUNNEL_004.json"
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


def test_overview_uses_versioned_censoring_by_market_hour_and_quality(tmp_path):
    client = fixture_client(tmp_path)
    write_censoring_artifact(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["captured_at_utc"] == "2026-10-15T08:00:00Z"
    assert data["followup_yield"]["valid_initial_decisions"] == 4
    assert data["followup_yield"]["source_analysis_version"] == "veritas-forward-forensics-v1.3"
    assert data["followup_yield"]["by_horizon"] == [
        {
            "horizon_ms": 1000,
            "observed": 1,
            "censored": 3,
            "invalid_initial": 6,
            "pending": 0,
            "censor_reasons": {
                "future_observation_unavailable": 3,
                "invalid_at_decision": 6,
            },
        }
    ]
    assert data["followup_censoring"]["market_group_count"] == 1
    assert data["followup_censoring"]["utc_hour_group_count"] == 1
    assert data["followup_censoring"]["by_market_at_longest_horizon"][0]["market_id"] == "market-a"
    assert (
        data["followup_censoring"]["by_market_at_longest_horizon"][0]["valid_initial_censored"] == 3
    )
    assert (
        data["followup_censoring"]["by_utc_hour_at_longest_horizon"][0]["utc_hour"]
        == "2026-10-15T08:00:00Z"
    )
    assert any(item["id"] == "censoring" for item in data["artifacts"])
    assert client.get("/api/veritas/artifacts/censoring").status_code == 200


def test_overview_rejects_censoring_artifact_from_another_campaign(tmp_path):
    client = fixture_client(tmp_path)
    write_censoring_artifact(tmp_path, campaign_id="different-campaign")

    assert client.get("/api/veritas/overview").status_code == 503


def test_overview_exposes_incremental_public_observatory_summary(tmp_path):
    client = fixture_client(tmp_path)
    data_dir = tmp_path / "data" / "veritas-observatory"
    data_dir.mkdir(parents=True)
    summary = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-snapshot-analysis-v1",
        "updated_at_utc": "2026-10-15T06:00:00+00:00",
        "processed_snapshot_count": 2,
        "pending_snapshot_count": 0,
        "limitations": ["Repeated snapshots are dependent."],
        "cumulative": {
            "snapshot_count": 2,
            "selected_market_observations": 80,
            "quality_valid_pairs": 70,
            "legacy_freshness_valid_pairs": 35,
            "legacy_freshness_invalid_reasons": {"reported_update_age_above_5s": 35},
            "invalid_pairs": 10,
            "current_bounded_eligible_markets": 50,
            "maximum_bounded_eligible_markets_seen": 50,
            "observed_market_ids": {
                "market-1": {
                    "selected_observations": 2,
                    "quality_valid_pairs": 2,
                    "legacy_freshness_valid_pairs": 1,
                    "invalid_reasons": {},
                    "legacy_freshness_invalid_reasons": {"reported_update_age_above_5s": 1},
                    "categories": ["Politics"],
                    "cohort_roles": {"stable_random_control": 2},
                    "first_observed_at_utc": "2026-10-15T05:30:00+00:00",
                    "last_observed_at_utc": "2026-10-15T06:00:00+00:00",
                    "sampled_state_fingerprint_count": 2,
                    "sampled_state_comparisons": 1,
                    "sampled_state_changes": 1,
                }
            },
            "category_observations": {"Politics": 2},
            "invalid_reasons": {"no_empty_ask_side": 10},
            "positive_top_gross_pairs": 0,
            "positive_full_depth_gross_by_quantity": {"20": 0},
            "positive_minimum_notional_by_quantity": {"20": 0},
            "positive_single_match_by_quantity": {"20": 0},
            "positive_fragmentation_safe_by_quantity": {"20": 0},
            "reported_update_age_bands_by_leg": {"yes": {"over_5m": 35}, "no": {"over_5m": 35}},
            "reported_update_age_above_5s_by_leg": {"yes": 35, "no": 35},
            "reported_update_timestamp_skew_bands": {"0_to_250ms": 35},
            "reported_update_timestamp_skew_above_250ms_pairs": 0,
            "candidate_event_count": 0,
            "candidate_market_ids": [],
            "recent_candidates": [],
            "first_captured_at_utc": "2026-10-15T05:30:00+00:00",
            "last_captured_at_utc": "2026-10-15T06:00:00+00:00",
            "observed_utc_days": ["2026-10-15"],
            "top_edge_state_count": 70,
            "minimum_top_edge_per_share": "-0.5",
            "maximum_top_edge_per_share": "-0.001",
        },
    }
    summary["analysis_summary_sha256"] = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    (data_dir / "research-summary.json").write_text(json.dumps(summary))
    (data_dir / "latest-summary.json").write_text(
        json.dumps(
            {
                "source_http_attempts": 7,
                "discovery": {
                    "query_count": 6,
                    "query_candidate_records": 300,
                    "unique_market_ids": 280,
                    "exclusion_reasons": {"unsupported_protocol": 4},
                    "frame_protocol": "stratified-gamma-page-rotation-v2",
                    "offset_bucket_seconds": 1800,
                },
                "selection": {
                    "phase": "expiry",
                    "target_markets": 40,
                    "selected_markets": 40,
                    "stable_control_markets": 8,
                    "rotating_markets": 32,
                    "selected_by_category": {"Politics": 8},
                    "selected_by_liquidity": {"unknown": 40},
                    "selected_by_expiry": {"unknown": 40},
                    "selected_by_spread": {"unknown": 40},
                    "sampled_markets": [
                        {
                            "market_id": "market-1",
                            "primary_category": "Politics",
                            "primary_category_source": "market.category",
                            "cohort_role": "stable_random_control",
                            "selection_probability": "0.16",
                            "selection_probability_basis": "sample from bounded union",
                            "selection_stratum": None,
                        }
                    ],
                },
                "collection_bounds": {
                    "target_markets": 40,
                    "maximum_markets": 50,
                    "gamma_queries_per_scan": 6,
                    "gamma_page_limit": 50,
                    "maximum_public_read_calls_per_scan": 7,
                    "maximum_public_http_attempts_per_scan": 14,
                    "maximum_retries_per_public_read": 1,
                    "request_timeout_seconds": 15,
                    "maximum_response_bytes": 50_331_648,
                    "minimum_request_interval_seconds": 1.0,
                    "maximum_root_bytes": 1_073_741_824,
                    "quantity_grid": ["5", "10", "20", "50", "100"],
                },
                "observation": {"invalid_reasons": {"no_empty_ask_side": 5}},
            }
        )
    )

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    panel = response.json()["opportunity_observatory"]
    assert panel["processed_snapshot_count"] == 2
    assert panel["readiness"] == "collecting_repeated_temporal_coverage"
    assert panel["discovery"]["unique_market_ids_observed"] == 1
    assert panel["discovery"]["latest_phase"] == "expiry"
    assert panel["discovery"]["latest_frame_protocol"] == "stratified-gamma-page-rotation-v2"
    assert panel["discovery"]["latest_offset_bucket_seconds"] == 1800
    assert panel["discovery"]["latest_query_count"] == 6
    assert panel["discovery"]["latest_query_candidate_records"] == 300
    assert panel["discovery"]["latest_unique_market_ids"] == 280
    assert panel["discovery"]["latest_http_attempts"] == 7
    assert panel["discovery"]["latest_target_markets"] == 40
    assert panel["discovery"]["latest_selected_market_rows"][0]["selection_probability"] == "0.16"
    assert panel["discovery"]["latest_selected_market_rows"][0]["primary_category_source"] == (
        "market.category"
    )
    assert panel["discovery"]["collection_bounds"]["maximum_markets"] == 50
    assert panel["discovery"]["collection_bounds"]["maximum_public_http_attempts_per_scan"] == 14
    assert panel["opportunity"]["quality_valid_pairs"] == 70
    assert panel["opportunity"]["positive_full_depth_gross_by_quantity"] == {"20": 0}
    assert panel["data_quality"]["latest_invalid_reasons"] == {"no_empty_ask_side": 5}
    assert panel["measurement_comparison"]["legacy_freshness_valid_pairs"] == 35
    assert panel["measurement_comparison"]["corrected_freshness_valid_pairs"] == 70
    assert panel["measurement_comparison"]["recovered_valid_pairs"] == 35
    assert panel["measurement_comparison"]["recovered_percentage_points"] == 43.8
    assert panel["market_coverage"]["tracked_markets"] == 1
    assert panel["market_coverage"]["coverage_denominator_snapshots"] == 2
    assert panel["market_coverage"]["sampled_state_changes"] == 1
    market = panel["market_coverage"]["least_observed_markets"][0]
    assert market["snapshot_coverage_percent"] == 100.0
    assert market["quality_valid_percent"] == 100.0
    assert market["legacy_quality_valid_percent"] == 50.0
    assert market["sampled_state_change_fraction"] == 1.0
    assert market["sampled_activity_band"] == "unclassified"
    assert any(item["id"] == "continuous-analysis" for item in response.json()["artifacts"])


def test_overview_exposes_bounded_finalized_reality_source_analysis(tmp_path):
    client = fixture_client(tmp_path)
    data_dir = tmp_path / "data" / "veritas-observatory"
    data_dir.mkdir(parents=True)
    summary = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-source-analysis-v1",
        "campaign_id": "campaign-fixture",
        "campaign_sha256": "a" * 64,
        "analysis_code_sha256": "b" * 64,
        "source_root": "/private/reality/source",
        "active_segment_read": False,
        "catalog_segment_count": 4,
        "empty_finalized_segment_count": 1,
        "processed_segment_count": 3,
        "pending_segment_count": 1,
        "pending_source_bytes": 512,
        "processed_source_bytes": 1536,
        "last_processed_ordinal": 30,
        "last_processed_segment_file": "segment.seg",
        "prefix_catalog_sha256": "c" * 64,
        "batch_processed_segment_count": 1,
        "batch_processed_source_bytes": 512,
        "campaign_window_ns": {"start": 1, "end_exclusive": 2},
        "readiness": "catching_up_finalized_source",
        "status": "catching_up",
        "cumulative": {
            "period_frame_records": 20,
            "touched_market_frame_states": 12,
            "quality_valid_states": 10,
            "quality_invalid_reason_counts": {"stale_book": 2},
            "positive_top_ask_pair_states": 0,
            "positive_full_depth_pre_fee_states": 0,
            "top_edge_distribution": {"count": 10, "minimum": "-0.5"},
            "raw_records_replayed": 30,
        },
        "most_observed_markets": [],
        "limitations": ["Repeated source records are dependent."],
        "generated_at_utc": "2026-10-15T06:00:00+00:00",
    }
    summary["summary_sha256"] = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    summary_path = data_dir / "source-research-summary.json"
    summary_path.write_text(json.dumps(summary))

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    panel = response.json()["finalized_reality_source"]
    assert panel["processed_segment_count"] == 3
    assert panel["pending_segment_count"] == 1
    assert panel["readiness"] == "catching_up_finalized_source"
    assert panel["cumulative"]["quality_valid_states"] == 10
    assert "source_root" not in response.text
    assert any(item["id"] == "finalized-source-analysis" for item in response.json()["artifacts"])

    artifact = client.get("/api/veritas/artifacts/finalized-source-analysis")
    assert artifact.status_code == 200
    assert artifact.json()["data"]["campaign_id"] == "campaign-fixture"
    assert artifact.json()["file_sha256"] == hashlib.sha256(summary_path.read_bytes()).hexdigest()


def test_finalized_snapshot_download_is_bounded_and_identity_checked(tmp_path):
    client = fixture_client(tmp_path)
    scan_id = "scan-20261015T060201Z-517641164ed1"
    snapshot_dir = tmp_path / "data" / "veritas-observatory" / "snapshots"
    snapshot_dir.mkdir(parents=True)
    snapshot = snapshot_dir / f"{scan_id}.json.gz"
    snapshot.write_bytes(
        gzip.compress(json.dumps({"scan_id": scan_id, "orders_submitted": False}).encode())
    )

    response = client.get(f"/api/veritas/observatory/snapshots/{scan_id}")

    assert response.status_code == 200
    assert response.json()["data"]["scan_id"] == scan_id
    assert (
        response.json()["compressed_file_sha256"]
        == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    )
    assert client.get("/api/veritas/observatory/snapshots/../secret").status_code in {404, 405}
