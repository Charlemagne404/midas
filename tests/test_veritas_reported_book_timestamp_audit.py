from __future__ import annotations

from midas.veritas.reported_book_timestamp_audit import (
    BookObservation,
    summarize_repeated_book_observations,
)


def _point(
    scan_id: str,
    *,
    asset_id: str = "asset-a",
    received_ns: int,
    timestamp_ms: int,
    content: str,
) -> BookObservation:
    return BookObservation(
        scan_id=scan_id,
        asset_id=asset_id,
        received_ns=received_ns,
        reported_timestamp_ms=timestamp_ms,
        content_sha256=content * 64,
        response_book_sha1=f"hash-{scan_id}",
    )


def test_reported_age_is_diagnostic_and_endpoint_content_is_counted():
    report = summarize_repeated_book_observations(
        [
            _point("scan-1", received_ns=10_000_000_000, timestamp_ms=9_000, content="a"),
            _point("scan-2", received_ns=20_000_000_000, timestamp_ms=14_000, content="a"),
            _point("scan-3", received_ns=700_000_000_000, timestamp_ms=15_000, content="b"),
        ]
    )

    assert report["repeated_asset_transition_count"] == 2
    assert report["transition_classes"] == {
        "content_changed_timestamp_advanced": 1,
        "content_unchanged_timestamp_advanced": 1,
    }
    assert report["later_endpoint_reported_age_bands"] == {
        "over_5m": 1,
        "threshold_to_30s": 1,
    }
    assert report["later_endpoints_over_age_threshold_by_content_relation"] == {
        "changed": 1,
        "unchanged": 1,
    }
    assert "not classified as a stale book" in report["interpretation"]


def test_changed_content_with_unchanged_timestamp_is_reported_not_filtered():
    report = summarize_repeated_book_observations(
        [
            _point("scan-1", received_ns=10_000_000_000, timestamp_ms=9_000, content="a"),
            _point("scan-2", received_ns=11_000_000_000, timestamp_ms=9_000, content="b"),
        ]
    )

    assert report["transition_classes"] == {"content_changed_timestamp_same": 1}


def test_transition_analysis_never_compares_different_assets():
    report = summarize_repeated_book_observations(
        [
            _point(
                "scan-1",
                asset_id="asset-a",
                received_ns=10_000_000_000,
                timestamp_ms=9_000,
                content="a",
            ),
            _point(
                "scan-2",
                asset_id="asset-b",
                received_ns=20_000_000_000,
                timestamp_ms=19_000,
                content="b",
            ),
        ]
    )

    assert report["repeated_asset_count"] == 0
    assert report["repeated_asset_transition_count"] == 0
    assert report["transition_classes"] == {}


def test_unordered_input_is_compared_in_receipt_order():
    report = summarize_repeated_book_observations(
        [
            _point("scan-2", received_ns=20_000_000_000, timestamp_ms=19_000, content="b"),
            _point("scan-1", received_ns=10_000_000_000, timestamp_ms=9_000, content="a"),
        ]
    )

    assert report["repeated_asset_transition_count"] == 1
    assert report["transition_classes"] == {"content_changed_timestamp_advanced": 1}
