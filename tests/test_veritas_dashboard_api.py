import gzip
import hashlib
import json
import shutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.veritas import MAX_ARTIFACT_BYTES, coverage_design_audit_overview, router


def write_artifact(root: Path, name: str, value: dict) -> None:
    path = root / "docs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def write_market_universe_coverage_fixture(root: Path) -> Path:
    artifact = {
        "schema_version": 1,
        "analysis_version": "veritas-market-universe-coverage-v1",
        "captured_at_utc": "2026-10-15T23:56:00Z",
        "orders_submitted": False,
        "authenticated_requests": False,
        "source": {
            "snapshot_count": 2,
            "gamma_response_count": 12,
            "first_scan_id": "scan-20261015T190055Z-7799523b9d87",
            "last_scan_id": "scan-20261015T193055Z-7799523b9d87",
            "gamma_response_hashes_verified": True,
            "clob_response_hashes_verified": True,
            "snapshot_evidence_hashes_verified": True,
            "read_only_evidence": True,
        },
        "collection_protocol": {
            "coverage_kind": "intermittent_public_snapshots",
            "total_attempted_market_pairs": 3,
            "total_quality_valid_market_pairs": 2,
            "positive_top_gross_pairs": 0,
            "candidate_events": 0,
            "mean_unique_market_ids_per_bounded_union": 3.5,
            "mean_v1_eligible_market_ids_per_bounded_union": 2.5,
            "capture_vs_current_replay_valid_pair_delta": 1,
            "scans_with_capture_vs_replay_count_mismatch": 1,
            "capture_vs_replay_count_mismatches": [
                {"scan_id": "scan-20261015T190055Z-7799523b9d87"}
            ],
        },
        "identity_coverage": {
            "distinct_gamma_market_ids_over_window": 4,
            "distinct_market_ids_eligible_at_least_once": 3,
            "distinct_condition_ids_over_window": 4,
            "distinct_outcome_asset_ids_over_window": 8,
            "selected_market_ids_over_window": 2,
            "selected_condition_ids_over_window": 2,
            "selected_outcome_asset_ids_over_window": 4,
            "latest_scan": {
                "scan_id": "scan-20261015T193055Z-7799523b9d87",
                "gamma_market_ids": 4,
                "eligible_market_ids": 2,
                "excluded_market_ids": 2,
                "selected_market_ids": 1,
                "distinct_selected_condition_ids": 1,
                "distinct_selected_outcome_asset_ids": 2,
                "distinct_payoff_verified_outcome_asset_ids": 2,
            },
        },
        "metadata_coverage": {
            "latest_scan_v1_eligible_population": {
                "liquidity_band_counts": {"high": 1, "low": 1},
                "expiry_band_counts": {"near_7d": 1, "long": 1},
                "spread_band_counts": {"tight_le_0.01": 1, "wide_gt_0.05": 1},
            }
        },
        "sampling": {
            "selection_probabilities": {
                "count_numeric_conditional_probabilities": 2,
                "min": 0.5,
                "median": 0.75,
                "max": 1.0,
                "scope": "conditional on bounded union and controls",
            },
            "selected_slots_by_cohort_role": {"rotating_stratified": 2},
        },
        "limitations": ["The observed query union is not a venue-wide denominator."],
    }
    path = root / "docs" / "VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_004.json"
    write_artifact(root, path.name, artifact)
    update_market_universe_coverage_receipt(root, path)
    return path


def update_market_universe_coverage_receipt(root: Path, artifact_path: Path) -> None:
    ledger_path = root / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    hypotheses = ledger.get("hypotheses")
    if not isinstance(hypotheses, list):
        hypotheses = []
        ledger["hypotheses"] = hypotheses
    entries = [
        item
        for item in hypotheses
        if isinstance(item, dict) and item.get("hypothesis_id") == "VERITAS-H110"
    ]
    receipt = entries[0] if len(entries) == 1 else {}
    if not entries:
        hypotheses.append(receipt)
    receipt.update(
        {
            "hypothesis_id": "VERITAS-H110",
            "title": "Fixture coverage audit",
            "status": "continue",
            "decision": "Keep the bounded sample caveat.",
            "result": {
                "artifact_path": "docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_004.json",
                "artifact_file_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                "analysis_version": "veritas-market-universe-coverage-v1",
            },
        }
    )
    ledger_path.write_text(json.dumps(ledger))


def write_coverage_design_audit_fixture(root: Path) -> Path:
    result = {
        "schema_version": 1,
        "experiment_id": "VERITAS-M2-COVERAGE-DESIGN-AUDIT-002",
        "analysis_version": "veritas-coverage-design-audit-v2",
        "analysis_code_sha256": "a" * 64,
        "created_at_utc": "2026-10-16T07:36:23Z",
        "study_status_at_audit": "running",
        "source": {
            "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
            "protocol_version": "veritas-coverage-pilot-v1",
            "summary_sha256": "b" * 64,
            "summary_file_sha256": "c" * 64,
            "event_count": 2,
            "compressed_snapshot_bytes": 4096,
        },
        "analysis": {
            "scan_count": 2,
            "role_totals": {
                "rotating_stratified": {"selected": 30, "valid": 24, "yield": 0.8},
                "stable_random_control": {"selected": 4, "valid": 2, "yield": 0.5},
            },
            "fully_supported_scan_count": 1,
            "partially_supported_scan_count": 1,
            "unsupported_scan_count": 0,
            "mean_rotating_population_support_fraction": 0.95,
            "fully_supported_scan_weighted_yield_mean": 0.82,
            "supported_population_scan_yield_range": {"minimum": 0.77, "maximum": 0.87},
            "skipped_selection_sequences": 1,
        },
        "interpretation": {
            "no_venue_wide_inference": True,
            "no_continuous_coverage_claim": True,
            "no_economic_candidate_or_profit_claim": True,
            "markets_and_scans_are_dependent": True,
        },
        "safety": {
            "live_requests": 0,
            "authenticated_requests": False,
            "orders_submitted": False,
            "campaign_modified": False,
        },
    }
    artifact = {**result, "result_sha256": hashlib.sha256(canonical_json(result)).hexdigest()}
    artifact["artifact_sha256"] = hashlib.sha256(canonical_json(artifact)).hexdigest()
    artifact_path = root / "docs" / "VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(canonical_json(artifact))

    ledger_path = root / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    ledger["hypotheses"].append(
        {
            "hypothesis_id": "VERITAS-H125",
            "experiment_id": "VERITAS-M2-COVERAGE-DESIGN-AUDIT-002",
            "title": "Fixture inclusion-support audit",
            "result": {
                "artifact_path": "docs/VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json",
                "artifact_file_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                "artifact_sha256": artifact["artifact_sha256"],
                "result_sha256": artifact["result_sha256"],
                "analysis_version": "veritas-coverage-design-audit-v2",
            },
        }
    )
    ledger_path.write_text(json.dumps(ledger))
    return artifact_path


def update_censor_gap_attribution_receipt(root: Path, artifact_path: Path) -> None:
    ledger_path = root / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    hypotheses = ledger.get("hypotheses")
    if not isinstance(hypotheses, list):
        hypotheses = []
        ledger["hypotheses"] = hypotheses
    entries = [
        item
        for item in hypotheses
        if isinstance(item, dict) and item.get("hypothesis_id") == "VERITAS-H109"
    ]
    receipt = entries[0] if len(entries) == 1 else {}
    if not entries:
        hypotheses.append(receipt)
    artifact = json.loads(artifact_path.read_text())
    receipt.update(
        {
            "hypothesis_id": "VERITAS-H109",
            "title": "Fixture gap-censor attribution refresh",
            "status": "continue",
            "decision": "Keep the partial-prefix and temporal-link caveats.",
            "result": {
                "artifact_path": "docs/VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_002.json",
                "artifact_file_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                "result_sha256": artifact["result_sha256"],
                "analysis_version": "veritas-censor-gap-attribution-v1",
            },
        }
    )
    ledger_path.write_text(json.dumps(ledger))


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


def write_label_feasibility_artifact(root: Path, *, campaign_id: str = "campaign-fixture") -> None:
    source = (
        Path(__file__).resolve().parents[1] / "docs/VERITAS_MISSION2_LABEL_FEASIBILITY_001.json"
    )
    artifact = json.loads(source.read_text())
    artifact["campaign"]["campaign_id"] = campaign_id
    write_artifact(root, "VERITAS_MISSION2_LABEL_FEASIBILITY_001.json", artifact)


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def write_censor_gap_audit_fixture(root: Path, *, campaign_id: str = "campaign-fixture") -> Path:
    artifact = {
        "schema_version": 1,
        "artifact_id": "VERITAS-M2-CENSOR-GAP-AUDIT-001",
        "analysis_version": "veritas-censor-gap-reference-audit-v1",
        "status": "verified",
        "captured_at_utc": "2026-10-15T21:52:08Z",
        "campaign": {"campaign_id": campaign_id, "campaign_plan_sha256": "a" * 64},
        "gap_censors": {
            "outcome_rows": 5,
            "explicit_recorded_gap_outcomes": 3,
            "book_issue_gap_outcomes": 2,
            "unique_explicit_gap_records_by_reason": {"book_resynchronization": 2},
            "unique_explicit_gap_records_verified": 2,
            "unique_termination_records": 4,
            "unique_book_issue_termination_records_by_source_kind": {"discovery_page": 2},
            "unique_termination_record_kinds": {"gap": 2, "discovery_page": 2},
            "book_issue_direct_gap_causality_verified": False,
        },
        "source_verification": {
            "unique_source_records_verified": 4,
            "unique_finalized_segments_verified": 3,
            "record_offsets_and_hashes_verified": True,
            "active_open_segments_read": False,
        },
        "journal_snapshot": {"read_only": True, "hash_chain_reverified": False},
        "query": {"truncated": False},
        "limitations": ["The SQLite event hash chain was not reverified."],
    }
    artifact["artifact_sha256"] = hashlib.sha256(canonical_json(artifact)).hexdigest()
    write_artifact(root, "VERITAS_MISSION2_CENSOR_GAP_AUDIT_001.json", artifact)
    return root / "docs" / "VERITAS_MISSION2_CENSOR_GAP_AUDIT_001.json"


def write_censor_gap_attribution_fixture(
    root: Path, *, campaign_id: str = "campaign-fixture"
) -> Path:
    outcomes = [
        {
            "reason": "book_issue:gap:book_resynchronization",
            "link_status": "candidate_preceding_same_market_gap",
        },
        {
            "reason": "book_issue:gap:book_resynchronization",
            "link_status": "no_prior_same_market_gap_in_indexed_prefix",
        },
        {
            "reason": "book_issue:gap:book_resynchronization",
            "link_status": "termination_after_indexed_prefix",
        },
        {
            "reason": "recorded_gap:book_resynchronization",
            "link_status": "exact_recorded_gap_reference_verified_and_indexed",
        },
        {
            "reason": "recorded_gap:book_resynchronization",
            "link_status": "exact_recorded_gap_reference_verified_not_yet_indexed",
        },
    ]
    artifact = {
        "schema_version": 1,
        "analysis_version": "veritas-censor-gap-attribution-v1",
        "captured_at_utc": "2026-10-16T03:10:11Z",
        "status": "verified_partial_prefix",
        "campaign": {"campaign_id": campaign_id, "campaign_plan_sha256": "c" * 64},
        "gap_detail_index": {
            "analysis_version": "veritas-finalized-reality-gap-detail-v1",
            "analysis_code_files_verified": True,
            "processed_segment_count": 2,
            "catalog_segment_count": 3,
            "pending_segment_count": 1,
            "pending_source_bytes": 512,
            "indexed_campaign_gap_events": 2,
            "active_segment_read": False,
            "complete": False,
        },
        "query": {
            "censored_outcome_limit": 10,
            "censored_outcomes_scanned": 7,
            "gap_censored_outcomes": 5,
            "censored_outcome_event_bytes_read": 100,
            "event_byte_limit": 1000,
            "truncated": False,
        },
        "journal_snapshot": {"read_only": True, "hash_chain_reverified": False},
        "source_verification": {
            "active_open_segments_read": False,
            "finalized_segment_byte_limit": 1024,
            "unique_finalized_segments_verified": 3,
            "finalized_segment_bytes_hashed": 256,
            "unique_source_records_verified": 4,
            "exact_source_references_verified": True,
        },
        "gap_censors": {
            "outcomes_by_reason": {
                "book_issue:gap:book_resynchronization": 3,
                "recorded_gap:book_resynchronization": 2,
            },
            "link_status_counts": {
                "candidate_preceding_same_market_gap": 1,
                "exact_recorded_gap_reference_verified_and_indexed": 1,
                "exact_recorded_gap_reference_verified_not_yet_indexed": 1,
                "no_prior_same_market_gap_in_indexed_prefix": 1,
                "termination_after_indexed_prefix": 1,
            },
            "unique_gap_events_linked": 2,
            "unique_candidate_preceding_gap_events": 1,
            "unique_exact_recorded_gap_events_indexed": 1,
            "candidate_preceding_gap_age_bands_to_termination_receiver_time_ns": {
                "0_to_1s": 0,
                "1_to_60s": 0,
                "60_to_300s": 0,
                "300_to_3600s": 0,
                "over_3600s": 1,
            },
            "same_market_preceding_gap_is_causal_proof": False,
        },
        "outcomes": outcomes,
        "limitations": ["The indexed gap prefix is incomplete."],
    }
    artifact["result_sha256"] = hashlib.sha256(canonical_json(artifact)).hexdigest()
    path = root / "docs" / "VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_002.json"
    write_artifact(root, path.name, artifact)
    update_censor_gap_attribution_receipt(root, path)
    return path


def write_gap_detail_fixture(root: Path, *, campaign_id: str = "campaign-fixture") -> Path:
    summary = {
        "schema_version": 1,
        "analysis_version": "veritas-finalized-reality-gap-detail-v1",
        "status": "catching_up",
        "generated_at_utc": "2026-10-15T21:51:20+00:00",
        "campaign_id": campaign_id,
        "campaign_sha256": "b" * 64,
        "active_segment_read": False,
        "campaign_window_ns": {"start": 100, "end_exclusive": 200},
        "all_period_gap_event_count": 2,
        "all_period_gap_counts_by_reason": {"book_resynchronization": 2},
        "campaign_window_gap_event_count": 0,
        "campaign_window_gap_counts_by_reason": {},
        "campaign_window_gap_events_without_reported_assets": 0,
        "campaign_window_unmapped_affected_asset_count": 0,
        "catalog_segment_count": 3,
        "replayable_catalog_segment_count": 2,
        "empty_finalized_segment_count": 1,
        "processed_segment_count": 1,
        "pending_segment_count": 1,
        "pending_source_bytes": 512,
        "processed_source_bytes": 256,
        "last_processed_ordinal": 30,
        "recent_gap_events": [
            {
                "reason": "book_resynchronization",
                "received_at_utc": "2026-10-14T10:24:24Z",
                "in_campaign_window": False,
                "received_ns": 90,
            }
        ],
        "limitations": ["Only finalized source segments were read."],
    }
    summary["summary_sha256"] = hashlib.sha256(canonical_json(summary)).hexdigest()
    path = root / "data" / "veritas-observatory" / "gap-detail-summary-v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(summary))
    return path


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


def write_coverage_pilot_fixture(root: Path) -> Path:
    source_root = Path(__file__).resolve().parents[1] / "packages" / "midas" / "veritas"
    module_dir = root / "packages" / "midas" / "veritas"
    module_dir.mkdir(parents=True)
    source_names = (
        "coverage_pilot.py",
        "observatory.py",
        "continuous_analysis.py",
        "opportunity_audit.py",
    )
    implementation = hashlib.sha256()
    for name in source_names:
        shutil.copyfile(source_root / name, module_dir / name)
        implementation.update(name.encode())
        implementation.update((module_dir / name).read_bytes())
    implementation_sha256 = implementation.hexdigest()

    observatory_root = root / "data" / "veritas-observatory"
    pilot_root = observatory_root / "measurement-pilots" / "VERITAS-M2-COVERAGE-PILOT-001"
    events_dir = pilot_root / "events"
    events_dir.mkdir(parents=True)

    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    control = observatory_root / "control-cohort.json"
    control.parent.mkdir(parents=True, exist_ok=True)
    control.write_bytes(
        canonical(
            {
                "market_ids": [
                    "market-control",
                    "market-missing",
                    "market-excluded",
                    "market-eligible-unselected",
                ],
                "selection_basis": "seeded simple random control within bounded discovery union",
            }
        )
    )
    control_sha256 = hashlib.sha256(control.read_bytes()).hexdigest()

    plan = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs/VERITAS_MISSION2_COVERAGE_PILOT_001.json"
        ).read_text()
    )
    plan_sha256 = hashlib.sha256(canonical(plan)).hexdigest()
    (pilot_root / "plan.json").write_bytes(canonical({**plan, "plan_sha256": plan_sha256}))

    scan_id = "scan-20261015T190055Z-7799523b9d87"
    captured_at = "2026-10-15T19:00:55.062293+00:00"
    market_rows = [
        {
            "market_id": "market-rotating",
            "cohort_role": "rotating_stratified",
            "selection_stratum": "high_liquidity",
            "quality_valid": True,
            "invalid_reason": None,
        },
        {
            "market_id": "market-control",
            "cohort_role": "stable_random_control",
            "selection_stratum": "low_liquidity",
            "quality_valid": False,
            "invalid_reason": "no_empty_ask_side",
        },
    ]
    snapshot_file = f"snapshots/{scan_id}.json.gz"
    snapshot_evidence_sha256 = "c" * 64
    snapshot_source_code_sha256 = "d" * 64
    snapshot = {
        "schema_version": 1,
        "scan_id": scan_id,
        "captured_at_utc": captured_at,
        "snapshot_file": snapshot_file,
        "snapshot_evidence_sha256": snapshot_evidence_sha256,
        "source_code_sha256": snapshot_source_code_sha256,
        "orders_submitted": False,
        "authenticated_requests": False,
        "discovery": {
            "unique_market_ids": 4,
            "eligible_pair_markets": 3,
            "excluded_market_ids": 1,
            "universe": [
                {
                    "market_id": "market-control",
                    "eligible_for_pair_observation": True,
                    "exclusion_reason": None,
                },
                {
                    "market_id": "market-rotating",
                    "eligible_for_pair_observation": True,
                    "exclusion_reason": None,
                },
                {
                    "market_id": "market-eligible-unselected",
                    "eligible_for_pair_observation": True,
                    "exclusion_reason": None,
                },
                {
                    "market_id": "market-excluded",
                    "eligible_for_pair_observation": False,
                    "exclusion_reason": "unsupported_outcome_relationship",
                },
            ],
        },
        "selection": {
            "selected_markets": [
                {"market_id": "market-rotating", "cohort_role": "rotating_stratified"},
                {"market_id": "market-control", "cohort_role": "stable_random_control"},
            ]
        },
    }
    snapshot_bytes = gzip.compress(canonical(snapshot), mtime=0)
    snapshot_dir = observatory_root / "snapshots"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / f"{scan_id}.json.gz").write_bytes(snapshot_bytes)
    event = {
        "schema_version": 1,
        "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
        "protocol_version": "veritas-coverage-pilot-v1",
        "plan_sha256": plan_sha256,
        "implementation_sha256": implementation_sha256,
        "scan_id": scan_id,
        "captured_at_utc": captured_at,
        "phase": "snapshot_change",
        "selection_sequence": 30,
        "bounded_eligible_markets": 3,
        "discovered_unique_market_ids": 4,
        "excluded_market_ids": 1,
        "selected_market_pairs": 2,
        "quality_valid_pairs": 1,
        "invalid_reasons": {"no_empty_ask_side": 1},
        "stable_control_available": 1,
        "stable_control_missing": [
            "market-missing",
            "market-excluded",
            "market-eligible-unselected",
        ],
        "positive_top_gross_pairs": 0,
        "orders_submitted": False,
        "authenticated_requests": False,
        "snapshot_file": snapshot_file,
        "snapshot_file_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "snapshot_evidence_sha256": snapshot_evidence_sha256,
        "snapshot_source_code_sha256": snapshot_source_code_sha256,
        "previous_event_sha256": None,
        "market_rows": market_rows,
    }
    event["event_sha256"] = hashlib.sha256(canonical(event)).hexdigest()
    (events_dir / f"{scan_id}.json").write_bytes(canonical(event))

    scan_summary = {
        "scan_id": scan_id,
        "captured_at_utc": captured_at,
        "selection_sequence": 30,
        "phase": "snapshot_change",
        "selected_market_pairs": 2,
        "quality_valid_pairs": 1,
        "stable_control_available": 1,
        "stable_control_missing_count": 3,
        "discovered_unique_market_ids": 4,
        "bounded_eligible_markets": 3,
        "excluded_market_ids": 1,
        "positive_top_gross_pairs": 0,
    }
    summary = {
        "schema_version": 1,
        "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
        "protocol_version": "veritas-coverage-pilot-v1",
        "status": "running",
        "completion_reason": None,
        "started_at_utc": captured_at,
        "ends_at_utc": "2026-10-16T19:00:55.062293+00:00",
        "maximum_elapsed_hours": 24,
        "maximum_completed_scans": 48,
        "completed_scans": 1,
        "selected_market_pair_slots": 2,
        "quality_valid_pairs": 1,
        "invalid_pairs": 1,
        "quality_valid_yield": 0.5,
        "distinct_selected_market_ids": 2,
        "by_cohort_role": {},
        "by_selection_stratum": {},
        "by_phase": {},
        "skipped_scan_sequences": 0,
        "scans": [scan_summary],
        "source_lineage": {
            "first_scan_id": scan_id,
            "last_scan_id": scan_id,
            "plan_sha256": plan_sha256,
            "implementation_sha256": implementation_sha256,
            "control_cohort_sha256": control_sha256,
        },
        "orders_submitted": False,
        "authenticated_requests": False,
        "limitations": ["Same-scan cohort yields are descriptive."],
    }
    summary["summary_sha256"] = hashlib.sha256(canonical(summary)).hexdigest()
    summary_path = pilot_root / "summary.json"
    summary_path.write_bytes(canonical(summary))
    return summary_path


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
    assert data["opportunity_observatory"]["measurement_pilot"]["status"] == "not_started"
    assert data["execution_sensitivity"]["break_even_at_5pct_unmatched_feasible"] is False
    assert data["opportunity_observatory"]["status"] == "not_started"
    assert data["finalized_reality_source"]["status"] == "not_started"
    assert "source_root" not in response.text


def test_overview_exposes_hash_verified_market_universe_coverage(tmp_path):
    client = fixture_client(tmp_path)
    artifact_path = write_market_universe_coverage_fixture(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    coverage = response.json()["opportunity_observatory"]["market_universe_coverage"]
    assert coverage["status"] == "available"
    assert coverage["snapshot_count"] == 2
    assert coverage["distinct_gamma_market_ids"] == 4
    assert coverage["eligible_market_ids_at_least_once"] == 3
    assert coverage["latest_scan"]["distinct_selected_outcome_asset_ids"] == 2
    assert coverage["latest_eligible_metadata_distributions"]["liquidity"] == {
        "high": 1,
        "low": 1,
    }
    assert coverage["positive_top_gross_pairs"] == 0
    assert (
        coverage["artifact"]["file_sha256"]
        == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    )
    assert any(
        artifact["id"] == "market-universe-coverage" for artifact in response.json()["artifacts"]
    )

    artifact_response = client.get("/api/veritas/artifacts/market-universe-coverage")
    assert artifact_response.status_code == 200
    assert artifact_response.json()["data"]["analysis_version"] == (
        "veritas-market-universe-coverage-v1"
    )
    assert (
        artifact_response.json()["file_sha256"]
        == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    )


def test_market_universe_overview_rejects_unreconciled_counts(tmp_path):
    client = fixture_client(tmp_path)
    artifact_path = write_market_universe_coverage_fixture(tmp_path)
    artifact = json.loads(artifact_path.read_text())
    artifact["collection_protocol"]["total_quality_valid_market_pairs"] = 4
    artifact_path.write_text(json.dumps(artifact))
    update_market_universe_coverage_receipt(tmp_path, artifact_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 503


def test_market_universe_overview_rejects_mismatched_ledger_digest(tmp_path):
    client = fixture_client(tmp_path)
    write_market_universe_coverage_fixture(tmp_path)
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    receipt = next(item for item in ledger["hypotheses"] if item["hypothesis_id"] == "VERITAS-H110")
    receipt["result"]["artifact_file_sha256"] = "0" * 64
    ledger_path.write_text(json.dumps(ledger))

    response = client.get("/api/veritas/overview")

    assert response.status_code == 503


def test_market_universe_overview_rejects_stale_artifact_receipt(tmp_path):
    client = fixture_client(tmp_path)
    artifact_path = write_market_universe_coverage_fixture(tmp_path)
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    receipt = next(item for item in ledger["hypotheses"] if item["hypothesis_id"] == "VERITAS-H110")
    receipt["result"]["artifact_path"] = "docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_002.json"
    receipt["result"]["artifact_file_sha256"] = hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest()
    ledger_path.write_text(json.dumps(ledger))

    response = client.get("/api/veritas/overview")

    assert response.status_code == 503


def test_coverage_design_audit_projects_hash_verified_support_and_pilot_freshness(tmp_path):
    client = fixture_client(tmp_path)
    artifact_path = write_coverage_design_audit_fixture(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    audit = response.json()["opportunity_observatory"]["coverage_design_audit"]
    assert audit["status"] == "available"
    assert audit["study_scan_count"] == 2
    assert audit["current_pilot_scan_count"] == 0
    assert audit["source_is_current"] is False
    assert audit["mean_rotating_population_support_fraction"] == 0.95
    assert audit["fully_supported_scan_weighted_yield_mean"] == 0.82
    assert audit["role_totals"]["rotating_stratified"] == {
        "selected": 30,
        "valid": 24,
        "yield": 0.8,
    }
    assert any(item["id"] == "coverage-design-audit" for item in response.json()["artifacts"])

    ledger = json.loads((tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json").read_text())
    source_is_current = coverage_design_audit_overview(
        tmp_path,
        ledger,
        {"completed_scans": 2, "summary_sha256": "b" * 64},
    )
    assert source_is_current is not None
    assert source_is_current["source_is_current"] is True
    source_is_stale = coverage_design_audit_overview(
        tmp_path,
        ledger,
        {"completed_scans": 3, "summary_sha256": "d" * 64},
    )
    assert source_is_stale is not None
    assert source_is_stale["source_is_current"] is False

    artifact_response = client.get("/api/veritas/artifacts/coverage-design-audit")
    assert artifact_response.status_code == 200
    assert artifact_response.json()["data"]["analysis_version"] == (
        "veritas-coverage-design-audit-v2"
    )
    assert (
        artifact_response.json()["file_sha256"]
        == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    )


def test_coverage_design_audit_fails_closed_on_tampered_digest_or_invalid_fraction(tmp_path):
    client = fixture_client(tmp_path)
    artifact_path = write_coverage_design_audit_fixture(tmp_path)
    artifact = json.loads(artifact_path.read_text())
    artifact["analysis"]["mean_rotating_population_support_fraction"] = 1.5
    artifact_path.write_bytes(canonical_json(artifact))

    assert client.get("/api/veritas/overview").status_code == 503


def test_coverage_design_route_selects_newest_receipted_artifact(tmp_path):
    client = fixture_client(tmp_path)
    artifact_path = write_coverage_design_audit_fixture(tmp_path)
    latest_path = artifact_path.with_name("VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_003.json")
    latest_path.write_bytes(artifact_path.read_bytes())
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    base_result = ledger["hypotheses"][-1]["result"]
    ledger["hypotheses"].append(
        {
            "hypothesis_id": "VERITAS-H126",
            "experiment_id": "VERITAS-M2-COVERAGE-DESIGN-AUDIT-002",
            "result": {
                **base_result,
                "artifact_path": "docs/VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_003.json",
                "artifact_file_sha256": hashlib.sha256(latest_path.read_bytes()).hexdigest(),
            },
        }
    )
    ledger_path.write_text(json.dumps(ledger))

    response = client.get("/api/veritas/artifacts/coverage-design-audit")

    assert response.status_code == 200
    assert response.json()["file_sha256"] == hashlib.sha256(latest_path.read_bytes()).hexdigest()


def test_overview_exposes_hash_verified_gap_censor_and_prefix_evidence(tmp_path):
    client = fixture_client(tmp_path)
    audit_path = write_censor_gap_audit_fixture(tmp_path)
    summary_path = write_gap_detail_fixture(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    data = response.json()
    audit = data["gap_censor_audit"]
    assert audit["outcome_rows"] == 5
    assert audit["explicit_recorded_gap_outcomes"] == 3
    assert audit["book_issue_gap_outcomes"] == 2
    assert audit["unique_explicit_gap_records_verified"] == 2
    assert audit["book_issue_direct_gap_causality_verified"] is False
    assert audit["source_verification"]["active_open_segments_read"] is False
    assert audit["artifact"]["file_sha256"] == hashlib.sha256(audit_path.read_bytes()).hexdigest()

    detail = data["finalized_gap_detail"]
    assert detail["processed_segment_count"] == 1
    assert detail["replayable_catalog_segment_count"] == 2
    assert detail["pending_segment_count"] == 1
    assert detail["readiness"] == "catching_up"
    assert detail["all_period_gap_event_count"] == 2
    assert detail["campaign_window_gap_event_count"] == 0
    assert detail["active_segment_read"] is False
    assert (
        detail["summary_artifact"]["file_sha256"]
        == hashlib.sha256(summary_path.read_bytes()).hexdigest()
    )
    assert {item["id"] for item in data["artifacts"]} >= {
        "censor-gap-audit",
        "gap-detail-current",
    }

    audit_artifact = client.get("/api/veritas/artifacts/censor-gap-audit")
    detail_artifact = client.get("/api/veritas/artifacts/gap-detail-current")
    assert audit_artifact.status_code == 200
    assert audit_artifact.json()["data"]["artifact_id"] == "VERITAS-M2-CENSOR-GAP-AUDIT-001"
    assert detail_artifact.status_code == 200
    assert detail_artifact.json()["data"]["summary_sha256"]


def test_overview_exposes_verified_gap_censor_attribution_and_artifact_route(tmp_path):
    client = fixture_client(tmp_path)
    attribution_path = write_censor_gap_attribution_fixture(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    attribution = response.json()["gap_censor_attribution"]
    assert attribution["status"] == "verified_partial_prefix"
    assert attribution["censored_outcomes_scanned"] == 7
    assert attribution["gap_censored_outcomes"] == 5
    assert attribution["link_status_counts"]["candidate_preceding_same_market_gap"] == 1
    assert attribution["same_market_preceding_gap_is_causal_proof"] is False
    assert attribution["gap_detail_index"]["active_segment_read"] is False
    assert (
        attribution["artifact"]["file_sha256"]
        == hashlib.sha256(attribution_path.read_bytes()).hexdigest()
    )
    assert {item["id"] for item in response.json()["artifacts"]} >= {"censor-gap-attribution"}

    artifact_response = client.get("/api/veritas/artifacts/censor-gap-attribution")
    assert artifact_response.status_code == 200
    assert artifact_response.json()["data"]["result_sha256"]
    assert len(artifact_response.json()["data"]["outcomes"]) == 5


def test_gap_censor_attribution_rejects_mismatches_and_unreconciled_claims(tmp_path):
    client = fixture_client(tmp_path)
    attribution_path = write_censor_gap_attribution_fixture(tmp_path)
    artifact = json.loads(attribution_path.read_text())

    artifact["gap_detail_index"]["pending_source_bytes"] += 1
    attribution_path.write_bytes(canonical_json(artifact))
    assert client.get("/api/veritas/overview").status_code == 503


def test_gap_censor_attribution_rejects_stale_ledger_artifact_path(tmp_path):
    client = fixture_client(tmp_path)
    write_censor_gap_attribution_fixture(tmp_path)
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    receipt = next(item for item in ledger["hypotheses"] if item["hypothesis_id"] == "VERITAS-H109")
    receipt["result"]["artifact_path"] = "docs/VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_001.json"
    ledger_path.write_text(json.dumps(ledger))

    assert client.get("/api/veritas/overview").status_code == 503


def test_gap_censor_attribution_rejects_ledger_digest_mismatch(tmp_path):
    client = fixture_client(tmp_path)
    write_censor_gap_attribution_fixture(tmp_path)
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    receipt = next(item for item in ledger["hypotheses"] if item["hypothesis_id"] == "VERITAS-H109")
    receipt["result"]["artifact_file_sha256"] = "0" * 64
    ledger_path.write_text(json.dumps(ledger))

    assert client.get("/api/veritas/overview").status_code == 503

    attribution_path = write_censor_gap_attribution_fixture(tmp_path)
    artifact = json.loads(attribution_path.read_text())
    artifact["campaign"]["campaign_id"] = "other-campaign"
    artifact["result_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in artifact.items() if key != "result_sha256"})
    ).hexdigest()
    attribution_path.write_bytes(canonical_json(artifact))
    assert client.get("/api/veritas/overview").status_code == 503

    artifact["campaign"]["campaign_id"] = "campaign-fixture"
    artifact["gap_censors"]["same_market_preceding_gap_is_causal_proof"] = True
    artifact["result_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in artifact.items() if key != "result_sha256"})
    ).hexdigest()
    attribution_path.write_bytes(canonical_json(artifact))
    assert client.get("/api/veritas/overview").status_code == 503

    artifact["gap_censors"]["same_market_preceding_gap_is_causal_proof"] = False
    artifact["outcomes"][0]["reason"] = "unrelated_reason"
    artifact["result_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in artifact.items() if key != "result_sha256"})
    ).hexdigest()
    attribution_path.write_bytes(canonical_json(artifact))
    assert client.get("/api/veritas/overview").status_code == 503


def test_gap_evidence_rejects_campaign_mismatch_and_digest_tampering(tmp_path):
    client = fixture_client(tmp_path)
    audit_path = write_censor_gap_audit_fixture(tmp_path)
    audit = json.loads(audit_path.read_text())
    audit["campaign"]["campaign_id"] = "other-campaign"
    audit["artifact_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in audit.items() if key != "artifact_sha256"})
    ).hexdigest()
    audit_path.write_bytes(canonical_json(audit))
    assert client.get("/api/veritas/overview").status_code == 503

    audit["campaign"]["campaign_id"] = "campaign-fixture"
    audit_path.write_bytes(canonical_json(audit))
    assert client.get("/api/veritas/overview").status_code == 503

    audit["gap_censors"]["outcome_rows"] = 6
    audit["artifact_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in audit.items() if key != "artifact_sha256"})
    ).hexdigest()
    audit_path.write_bytes(canonical_json(audit))
    assert client.get("/api/veritas/overview").status_code == 503


def test_gap_detail_rejects_bad_digest_campaign_or_active_segment(tmp_path):
    client = fixture_client(tmp_path)
    summary_path = write_gap_detail_fixture(tmp_path)
    summary = json.loads(summary_path.read_text())
    summary["campaign_id"] = "other-campaign"
    summary["summary_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in summary.items() if key != "summary_sha256"})
    ).hexdigest()
    summary_path.write_bytes(canonical_json(summary))
    assert client.get("/api/veritas/overview").status_code == 503

    summary["campaign_id"] = "campaign-fixture"
    summary_path.write_bytes(canonical_json(summary))
    assert client.get("/api/veritas/overview").status_code == 503

    summary["active_segment_read"] = True
    summary["summary_sha256"] = hashlib.sha256(
        canonical_json({key: value for key, value in summary.items() if key != "summary_sha256"})
    ).hexdigest()
    summary_path.write_bytes(canonical_json(summary))
    assert client.get("/api/veritas/overview").status_code == 503


def test_overview_accepts_legacy_hypotheses_without_top_level_status(tmp_path):
    client = fixture_client(tmp_path)
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    ledger["hypotheses"][0].pop("status")
    ledger["hypotheses"][0].pop("decision")
    ledger_path.write_text(json.dumps(ledger))

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    hypothesis = response.json()["research_status"]["recent_hypotheses"][0]
    assert hypothesis["status"] == "completed"
    assert hypothesis["result_status"] == "completed"
    assert hypothesis["decision"] == "No decision recorded."


def test_overview_tolerates_hypotheses_without_any_status_fields(tmp_path):
    client = fixture_client(tmp_path)
    ledger_path = tmp_path / "docs" / "VERITAS_RESEARCH_LEDGER.json"
    ledger = json.loads(ledger_path.read_text())
    hypothesis = ledger["hypotheses"][0]
    hypothesis.pop("status")
    hypothesis.pop("decision")
    hypothesis["result"].pop("status")
    ledger_path.write_text(json.dumps(ledger))

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    hypothesis = response.json()["research_status"]["recent_hypotheses"][0]
    assert hypothesis["status"] == "unknown"
    assert hypothesis["result_status"] == "unknown"
    assert hypothesis["decision"] == "No decision recorded."


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


def test_overview_exposes_frozen_campaign_markout_feasibility_separately(tmp_path):
    client = fixture_client(tmp_path)
    write_label_feasibility_artifact(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    data = response.json()
    feasibility = data["label_feasibility"]
    assert feasibility["analysis_version"] == "veritas-forward-forensics-v1.4"
    assert feasibility["campaign_id"] == "campaign-fixture"
    assert feasibility["decision_count"] == 10253
    assert feasibility["valid_initial_decisions"] == 3503
    assert feasibility["five_second"]["observed"] == 473
    assert feasibility["five_second"]["opportunity_target_status"] == {
        "no_initial_discrepancy": 473
    }
    assert feasibility["five_second"]["opportunity_persistence"] == {"null": 473}
    assert feasibility["five_second"]["execution_ground_truth"] == {"unknown_counterfactual": 473}
    assert feasibility["economic_observations"]["pre_fee_positive_count"] == 0
    assert feasibility["economic_observations"]["actual_orders_submitted"] == 0
    assert feasibility["economic_observations"]["realized_money"] is None
    assert feasibility["suitable_strategy_target_support"] is False
    assert any(item["id"] == "label-feasibility" for item in data["artifacts"])
    artifact_response = client.get("/api/veritas/artifacts/label-feasibility")
    expected_hash = hashlib.sha256(
        (tmp_path / "docs/VERITAS_MISSION2_LABEL_FEASIBILITY_001.json").read_bytes()
    ).hexdigest()
    assert artifact_response.json()["file_sha256"] == expected_hash


def test_overview_rejects_label_feasibility_artifact_from_another_campaign(tmp_path):
    client = fixture_client(tmp_path)
    write_label_feasibility_artifact(tmp_path, campaign_id="different-campaign")

    assert client.get("/api/veritas/overview").status_code == 503


def test_overview_rejects_unreconciled_label_feasibility_horizon(tmp_path):
    client = fixture_client(tmp_path)
    write_label_feasibility_artifact(tmp_path)
    artifact_path = tmp_path / "docs/VERITAS_MISSION2_LABEL_FEASIBILITY_001.json"
    artifact = json.loads(artifact_path.read_text())
    artifact["followup_label_support"]["by_horizon"]["5000"]["observed_public_measurements"] += 1
    artifact_path.write_text(json.dumps(artifact))

    assert client.get("/api/veritas/overview").status_code == 503


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


def test_overview_exposes_hash_verified_coverage_pilot_and_artifact(tmp_path):
    client = fixture_client(tmp_path)
    summary_path = write_coverage_pilot_fixture(tmp_path)

    response = client.get("/api/veritas/overview")

    assert response.status_code == 200
    pilot = response.json()["opportunity_observatory"]["measurement_pilot"]
    assert pilot["study_id"] == "VERITAS-M2-COVERAGE-PILOT-001"
    assert pilot["status"] == "running"
    assert pilot["completed_scans"] == 1
    assert pilot["selected_market_pair_slots"] == 2
    assert pilot["quality_valid_pairs"] == 1
    assert pilot["quality_valid_yield"] == 0.5
    assert pilot["skipped_scan_sequences"] == 0
    assert pilot["by_cohort_role"]["rotating_stratified"]["quality_valid"] == 1
    assert pilot["by_cohort_role"]["stable_random_control"]["invalid_reasons"] == {
        "no_empty_ask_side": 1
    }
    assert pilot["latest_control_availability"] == {
        "status": "verified",
        "source_scan_id": "scan-20261015T190055Z-7799523b9d87",
        "snapshot_url": "/api/veritas/observatory/snapshots/scan-20261015T190055Z-7799523b9d87",
        "frozen_control_count": 4,
        "available_in_selected_cohort": 1,
        "missing_from_selected_cohort": 3,
        "missing_by_bounded_discovery_status": {
            "excluded_unsupported_outcome_relationship": 1,
            "eligible_but_not_selected": 1,
            "not_returned_by_bounded_query_union": 1,
        },
        "bounded_query_union_markets": 4,
        "eligible_markets_in_query_union": 3,
        "selection_basis": "seeded simple random control within bounded discovery union",
        "limitations": [
            "Absence from the six bounded query responses does not establish that a market is closed or absent from the venue.",
            "The cohort comparison remains descriptive; missing controls were not replaced with outcome-selected markets.",
        ],
    }
    assert "_market_rows" not in pilot["latest_scan"]
    assert "_snapshot_file" not in pilot["latest_scan"]
    assert pilot["latest_scan"]["snapshot_url"] == (
        "/api/veritas/observatory/snapshots/scan-20261015T190055Z-7799523b9d87"
    )
    assert any(item["id"] == "coverage-pilot" for item in response.json()["artifacts"])

    artifact = client.get("/api/veritas/artifacts/coverage-pilot")
    assert artifact.status_code == 200
    assert artifact.json()["data"]["summary_sha256"]
    assert artifact.json()["file_sha256"] == hashlib.sha256(summary_path.read_bytes()).hexdigest()

    snapshot = client.get(pilot["latest_scan"]["snapshot_url"])
    assert snapshot.status_code == 200
    assert snapshot.json()["scan_id"] == "scan-20261015T190055Z-7799523b9d87"


def test_coverage_pilot_rejects_tampered_event(tmp_path):
    client = fixture_client(tmp_path)
    summary_path = write_coverage_pilot_fixture(tmp_path)
    scan_id = "scan-20261015T190055Z-7799523b9d87"
    event_path = summary_path.parent / "events" / f"{scan_id}.json"
    event = json.loads(event_path.read_text())
    event["market_rows"][0]["quality_valid"] = False
    event_path.write_text(json.dumps(event))

    response = client.get("/api/veritas/overview")

    assert response.status_code == 503


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
