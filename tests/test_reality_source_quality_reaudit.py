import hashlib

from midas.reality.quality import levels
from midas.reality.storage import canonical

from scripts.reality_source_quality_reaudit import (
    gap_observation,
    segment_index_for_ordinal,
    verify_independent_book_record,
)


def test_gap_observation_summarizes_collector_asset_issue_mapping():
    affected = {f"token-{number}": "top_divergence" for number in range(12)}

    result = gap_observation(
        {
            "kind": "gap",
            "ordinal": 42,
            "payload": {"reason": "book_resynchronization", "affected_assets": affected},
        }
    )

    assert result["assets_field"] == "affected_assets"
    assert result["assets_count"] == len(affected)
    assert result["assets_sample"] == list(affected)[:8]
    assert result["assets_issue_sample"] == [
        {"asset_id": asset, "issue": "top_divergence"} for asset in list(affected)[:8]
    ]


def test_gap_observation_keeps_legacy_asset_lists():
    result = gap_observation(
        {"kind": "gap", "ordinal": 43, "payload": {"reason": "legacy", "assets": ["a", "b"]}}
    )

    assert result["assets_field"] == "assets"
    assert result["assets_count"] == 2
    assert result["assets_sample"] == ["a", "b"]


def test_ordinal_lookup_skips_empty_finalized_segments():
    segments = [
        {"first": 1, "last": 20, "count": 20},
        {"first": 0, "last": 0, "count": 0},
        {"first": 21, "last": 40, "count": 20},
    ]

    assert segment_index_for_ordinal(segments, 25) == 2


def test_rest_body_hash_is_verified_against_linked_comparison_payload():
    body = {
        "asset_id": "token-a",
        "market": "condition-a",
        "bids": [{"price": "0.25", "size": "10.0"}],
        "asks": [{"price": "0.75", "size": "4"}],
    }
    normalized = {side: levels(body[side]) for side in ("bids", "asks")}
    depth_hash = hashlib.sha256(canonical(normalized)).hexdigest()
    raw_record = {"ordinal": 11, "kind": "independent_book", "payload": body}
    comparison = {
        "kind": "book_comparison",
        "ordinal": 12,
        "payload": {
            "raw_ordinal": 11,
            "asset_id": "token-a",
            "condition": "condition-a",
            "independent_depth_sha256": depth_hash,
        },
    }
    divergence = {
        "raw_ordinal": 11,
        "record_ordinal": 12,
        "asset_id": "token-a",
        "condition": "condition-a",
        "independent_depth_sha256": depth_hash,
    }

    receipt = verify_independent_book_record(raw_record, [divergence], {12: comparison})

    assert receipt == {
        "raw_ordinal": 11,
        "comparison_ordinals": [12],
        "comparison_count": 1,
        "independent_depth_hash": depth_hash,
        "body_and_comparison_hash_match": True,
    }
