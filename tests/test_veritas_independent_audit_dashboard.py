from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from apps.api.veritas import (
    independent_opportunity_audit_overview,
    router,
)

EXPERIMENT_ID = "VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-002"
ANALYSIS_VERSION = "veritas-independent-source-opportunity-audit-v2"


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _artifact(scan_count: int, result_digest: str, manifest_digest: str) -> dict:
    return {
        "version": ANALYSIS_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "complete": True,
        "status": "NO_POSITIVE_GROSS_CANDIDATE_OBSERVED",
        "captured_at_utc": "2026-10-16T21:53:13.124373+00:00",
        "authenticated_requests": False,
        "orders_submitted": False,
        "snapshot_count": scan_count,
        "selected_market_observation_count": scan_count * 40,
        "v4_stored_quality_valid_count": 2845,
        "independent_v3_valid_count": 2845,
        "v4_v3_validity_mismatch_count": 0,
        "v4_v3_top_edge_mismatch_count": 0,
        "independent_fee_checked_quantity_count": 3768,
        "independent_fee_disagreement_count": 0,
        "strict_freshness_valid_count": 622,
        "reported_age_exceedance_pair_count": 2222,
        "pair_skew_exceedance_count": 1,
        "positive_top_pair_gross_count": 0,
        "positive_full_depth_gross_by_quantity": {"5": 0, "10": 0, "20": 0, "50": 0, "100": 0},
        "positive_full_depth_and_both_minimums_by_quantity": {
            "5": 0,
            "10": 0,
            "20": 0,
            "50": 0,
            "100": 0,
        },
        "positive_both_fee_sensitivities_by_quantity": {
            "5": 0,
            "10": 0,
            "20": 0,
            "50": 0,
            "100": 0,
        },
        "source_manifest_sha256": manifest_digest,
        "result_sha256": result_digest,
        "limitations": ["selected intermittent correlated snapshots"],
    }


def _write_receipted_audit(root: Path, scans: list[int]) -> list[tuple[str, Path, str]]:
    hypotheses = []
    written = []
    for number in scans:
        relative_path = f"docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_{number:03}.json"
        result_digest = f"{number:064x}"[-64:]
        manifest_digest = hashlib.sha256(f"manifest-{number}".encode()).hexdigest()
        artifact = _artifact(number, result_digest, manifest_digest)
        path = root / relative_path
        _write_json(path, artifact)
        file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hypotheses.append(
            {
                "hypothesis_id": f"VERITAS-H{number}",
                "experiment_id": EXPERIMENT_ID,
                "result": {
                    "artifact_path": relative_path,
                    "artifact_sha256": file_digest,
                    "result_sha256": result_digest,
                    "source_manifest_sha256": manifest_digest,
                },
            }
        )
        written.append((relative_path, path, file_digest))
    ledger = {"hypotheses": hypotheses}
    _write_json(root / "docs/VERITAS_RESEARCH_LEDGER.json", ledger)
    return written


def test_independent_audit_overview_uses_newest_hash_receipted_scan_panel(tmp_path):
    written = _write_receipted_audit(tmp_path, [19, 20])
    ledger = json.loads((tmp_path / "docs/VERITAS_RESEARCH_LEDGER.json").read_text())

    result = independent_opportunity_audit_overview(tmp_path, ledger)

    assert result is not None
    assert result["snapshot_count"] == 20
    assert result["selected_market_observation_count"] == 800
    assert result["validity_mismatches"] == 0
    assert result["fee_calculations_checked"] == 3768
    assert result["positive_top_gross_count"] == 0
    assert result["artifact"]["file_sha256"] == written[-1][2]
    assert result["artifact"]["url"] == "/api/veritas/artifacts/independent-opportunity-audit"


def test_independent_audit_endpoint_returns_receipted_artifact(tmp_path):
    _, path, file_digest = _write_receipted_audit(tmp_path, [20])[0]
    app = FastAPI()
    app.include_router(router(tmp_path))

    response = TestClient(app).get("/api/veritas/artifacts/independent-opportunity-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact"] == "independent-opportunity-audit"
    assert body["file_sha256"] == file_digest
    assert body["data"]["snapshot_count"] == 20
    assert path.is_file()


def test_independent_audit_overview_rejects_tampered_artifact(tmp_path):
    _, path, _ = _write_receipted_audit(tmp_path, [20])[0]
    ledger = json.loads((tmp_path / "docs/VERITAS_RESEARCH_LEDGER.json").read_text())
    path.write_text(path.read_text() + " ")

    with pytest.raises(HTTPException, match="failed its receipt checks"):
        independent_opportunity_audit_overview(tmp_path, ledger)
