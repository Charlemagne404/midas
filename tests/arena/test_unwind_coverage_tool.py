import pytest
from midas.economics.attestation import digest

from scripts.analyze_unwind_coverage import summarize


def entry(group, allowed, filled):
    proposal = {"allowed": allowed, "residual_before": "5", "reasons": ["stale", "stale"]}
    proposal["evidence_sha256"] = digest(proposal)
    return (
        {
            "policy": "sell_residual",
            "execution_model": "standard",
            "base_episode_id": group,
            "intervention_requests": int(allowed),
            "intervention_filled_shares": filled,
        },
        [proposal],
    )


def test_coverage_reports_all_groups_and_overlapping_reasons():
    report = summarize([entry("a", False, "0"), entry("b", True, "0"), entry("c", True, "2")])
    assert report["sell_residual/standard"] == {
        "source_groups": 3,
        "groups_with_proposals": 3,
        "groups_with_residual_at_proposal": 3,
        "groups_with_allowed_request": 2,
        "groups_with_intervention_fill": 1,
        "blocked_reason_counts": {"stale": 1},
    }


def test_reject_changed_evidence_or_request_count():
    row, proposals = entry("a", True, "1")
    row["intervention_requests"] = 0
    with pytest.raises(ValueError, match="count"):
        summarize([(row, proposals)])
    row["intervention_requests"] = 1
    proposals[0]["residual_before"] = "8"
    with pytest.raises(ValueError, match="checksum"):
        summarize([(row, proposals)])
