import hashlib
import json

from midas.reality.storage import canonical

from scripts.reconcile_reality_source_quality import reconcile_divergence


def test_reconciles_response_hash_with_persisted_body_and_frame_lineage():
    body = {
        "asset_id": "asset-1",
        "market": "condition-1",
        "timestamp": "123",
        "hash": "native-hash",
        "bids": [{"price": "0.50", "size": "2.0"}],
        "asks": [{"price": "0.60", "size": "3"}],
    }
    depth = {"bids": {"0.5": "2"}, "asks": {"0.6": "3"}}
    body_hash = hashlib.sha256(canonical(depth)).hexdigest()
    audit_case = {
        "record_ordinal": 20,
        "raw_ordinal": 19,
        "after_lineage": [17, 0],
        "replay_lineage_at_durable_record": [17, 0],
        "local_depth_sha256": "a" * 64,
        "replay_state_advanced_after_response": False,
        "local_level_counts": {"bids": 1, "asks": 1},
    }
    comparison = {
        "ordinal": 20,
        "kind": "book_comparison",
        "payload": {
            "assessment": "stable_local_lineage_divergence",
            "asset_id": "asset-1",
            "condition": "condition-1",
            "raw_ordinal": 19,
            "before_lineage": [17, 0],
            "after_lineage": [17, 0],
            "local_depth_sha256": "f" * 64,
            "independent_depth_sha256": body_hash,
            "response_ns": 200,
            "source_timestamp_ms": 123,
            "source_native_hash": "native-hash",
        },
    }
    independent = {
        "ordinal": 19,
        "kind": "independent_book",
        "asset": "asset-1",
        "received_ns": 200,
        "payload": json.dumps(body),
    }
    frame = {
        "ordinal": 17,
        "kind": "frame",
        "received_ns": 150,
        "payload": json.dumps(
            {
                "event_type": "book",
                "asset_id": "asset-1",
                "market": "condition-1",
                "timestamp": "122",
                "bids": [],
                "asks": [],
            }
        ),
    }

    result = reconcile_divergence(audit_case, comparison, independent, frame)

    assert result["independent_body_verified"] is True
    assert result["independent_body_matches_recorded_depth_hash"] is True
    assert result["response_local_frame_verified"] is True
    assert result["response_to_local_frame_age_ns"] == 50
    assert result["classification"] == "STABLE_RESPONSE_TIME_DEPTH_MISMATCH_DIRECTION_UNKNOWN"
    assert result["independent_level_counts"] == {"bids": 1, "asks": 1}
    assert result["response_local_level_counts"] == {"bids": 1, "asks": 1}
    assert result["source_timestamp_comparison"]["websocket_minus_rest_ms"] == -1


def test_reports_unlinked_independent_body_without_claiming_verification():
    body = {
        "asset_id": "asset-2",
        "market": "condition-1",
        "timestamp": "123",
        "hash": "native-hash",
        "bids": [],
        "asks": [],
    }
    body_hash = hashlib.sha256(canonical({"bids": {}, "asks": {}})).hexdigest()
    audit_case = {"record_ordinal": 20, "raw_ordinal": 19, "after_lineage": [17, 0]}
    comparison = {
        "ordinal": 20,
        "kind": "book_comparison",
        "payload": {
            "assessment": "stable_local_lineage_divergence",
            "asset_id": "asset-1",
            "condition": "condition-1",
            "raw_ordinal": 19,
            "before_lineage": [17, 0],
            "after_lineage": [17, 0],
            "local_depth_sha256": "f" * 64,
            "independent_depth_sha256": body_hash,
            "response_ns": 200,
            "source_timestamp_ms": 123,
            "source_native_hash": "native-hash",
        },
    }
    independent = {
        "ordinal": 19,
        "kind": "independent_book",
        "asset": "asset-2",
        "received_ns": 200,
        "payload": json.dumps(body),
    }
    frame = {
        "ordinal": 17,
        "kind": "frame",
        "received_ns": 150,
        "payload": json.dumps({"event_type": "book", "asset_id": "asset-1"}),
    }

    result = reconcile_divergence(audit_case, comparison, independent, frame)

    assert result["independent_body_verified"] is False
    assert result["independent_body_matches_recorded_depth_hash"] is True


def test_uses_full_replay_hash_only_when_response_lineage_is_unchanged():
    body = {
        "asset_id": "asset-1",
        "market": "condition-1",
        "timestamp": "123",
        "hash": "native-hash",
        "bids": [{"price": "0.50", "size": "2"}],
        "asks": [],
    }
    body_hash = hashlib.sha256(canonical({"bids": {"0.5": "2"}, "asks": {}})).hexdigest()
    audit_case = {
        "record_ordinal": 20,
        "raw_ordinal": 19,
        "after_lineage": [17, 0],
        "local_lineage": [17, 0],
        "local_lineage_agrees_with_after": True,
        "local_depth_sha256": body_hash,
    }
    comparison = {
        "ordinal": 20,
        "kind": "book_comparison",
        "payload": {
            "assessment": "stable_local_lineage_divergence",
            "asset_id": "asset-1",
            "condition": "condition-1",
            "raw_ordinal": 19,
            "before_lineage": [17, 0],
            "after_lineage": [17, 0],
            "independent_depth_sha256": body_hash,
            "response_ns": 200,
            "source_timestamp_ms": 123,
            "source_native_hash": "native-hash",
        },
    }
    independent = {
        "ordinal": 19,
        "kind": "independent_book",
        "asset": "asset-1",
        "received_ns": 200,
        "payload": json.dumps(body),
    }
    frame = {
        "ordinal": 17,
        "kind": "frame",
        "received_ns": 150,
        "payload": json.dumps({"event_type": "book", "asset_id": "asset-1"}),
    }

    result = reconcile_divergence(audit_case, comparison, independent, frame)

    assert result["response_local_depth_hash_source"] == "full_replay_unchanged_response_lineage"
    assert result["response_local_hash_matches_body"] is True
    assert result["classification"] == "RECORDED_DIVERGENCE_NOT_REPRODUCED_AT_RESPONSE"


def test_does_not_use_full_replay_hash_after_response_lineage_advanced():
    body = {
        "asset_id": "asset-1",
        "market": "condition-1",
        "timestamp": "123",
        "hash": "native-hash",
        "bids": [],
        "asks": [],
    }
    body_hash = hashlib.sha256(canonical({"bids": {}, "asks": {}})).hexdigest()
    audit_case = {
        "record_ordinal": 20,
        "raw_ordinal": 19,
        "after_lineage": [17, 0],
        "replay_lineage_at_durable_record": [18, 0],
        "replay_state_advanced_after_response": True,
        "local_depth_sha256": "f" * 64,
    }
    comparison = {
        "ordinal": 20,
        "kind": "book_comparison",
        "payload": {
            "assessment": "stable_local_lineage_divergence",
            "asset_id": "asset-1",
            "condition": "condition-1",
            "raw_ordinal": 19,
            "before_lineage": [17, 0],
            "after_lineage": [17, 0],
            "independent_depth_sha256": body_hash,
            "response_ns": 200,
            "source_timestamp_ms": 123,
            "source_native_hash": "native-hash",
        },
    }
    independent = {
        "ordinal": 19,
        "kind": "independent_book",
        "asset": "asset-1",
        "received_ns": 200,
        "payload": json.dumps(body),
    }
    frame = {
        "ordinal": 17,
        "kind": "frame",
        "received_ns": 150,
        "payload": json.dumps({"event_type": "book", "asset_id": "asset-1"}),
    }

    result = reconcile_divergence(audit_case, comparison, independent, frame)

    assert result["response_local_depth_hash_source"] is None
    assert result["response_local_hash_matches_body"] is False
    assert result["classification"] == "RESPONSE_TIME_DEPTH_HASH_UNAVAILABLE"
