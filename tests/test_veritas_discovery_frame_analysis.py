from __future__ import annotations

import hashlib
import json

import pytest
from midas.veritas.discovery_frame_analysis import (
    analyze_control_adjusted_frame_drop,
    analyze_snapshot_frames,
)


def _market(market_id: str) -> dict[str, object]:
    return {
        "id": market_id,
        "conditionId": "0x" + f"{int(market_id):064x}",
        "version": "v1",
        "question": "Fixture?",
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": '["1001", "1002"]',
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "negRisk": False,
        "negRiskAugmented": False,
        "orderPriceMinTickSize": "0.01",
        "orderMinSize": 5,
        "feesEnabled": False,
    }


def _pages() -> list[dict[str, object]]:
    frames = {
        "f0": [_market("1"), _market("3")],
        "f1": [_market("2"), _market("3")],
        "f2": [],
        "f3": [],
        "f4": [],
        "f5": [],
    }
    pages = []
    for query_id, rows in frames.items():
        payload = json.dumps(rows, separators=(",", ":"))
        pages.append(
            {
                "query_id": query_id,
                "candidate_count": len(rows),
                "response_payload": payload,
                "response_bytes": len(payload.encode()),
                "response_sha256": hashlib.sha256(payload.encode()).hexdigest(),
            }
        )
    return pages


def test_leave_one_frame_out_counts_unique_and_eligible_markets():
    result = analyze_snapshot_frames(_pages())
    by_frame = {row["frame"]: row for row in result["marginal_by_frame"]}
    assert result["unique_ids"] == 3
    assert result["eligible_ids"] == 3
    assert by_frame["f0"]["unique_ids_exclusive_to_frame"] == 1
    assert by_frame["f0"]["eligible_ids_exclusive_to_frame"] == 1
    assert by_frame["f1"]["unique_ids_exclusive_to_frame"] == 1
    assert by_frame["f1"]["eligible_ids_exclusive_to_frame"] == 1
    assert by_frame["f2"]["eligible_ids_exclusive_to_frame"] == 0


def test_control_adjusted_sensitivity_adds_only_directly_eligible_rows():
    result = analyze_control_adjusted_frame_drop(
        _pages(), [_market("10"), {**_market("11"), "closed": True}]
    )
    assert result["six_frame_unique_union"] == 3
    assert result["six_frame_eligible_union"] == 3
    assert result["direct_control_count"] == 2
    assert result["direct_eligible_control_count"] == 1
    by_frame = {row["frame_removed"]: row for row in result["sensitivity_by_removed_frame"]}
    assert by_frame["f0"]["combined_unique_union_with_controls"] == 4
    assert by_frame["f0"]["combined_eligible_union"] == 3
    assert by_frame["f2"]["combined_eligible_union"] == 4


def test_frame_analysis_rejects_tampered_response_digest():
    pages = _pages()
    pages[0]["response_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        analyze_snapshot_frames(pages)  # type: ignore[arg-type]
