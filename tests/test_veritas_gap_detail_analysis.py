from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from midas.reality.storage import Store, file_hash
from midas.veritas import gap_detail_analysis as analysis

START = 1_792_000_000_000_000_000


def _market(index: int = 1) -> dict[str, Any]:
    return {
        "id": f"market-{index}",
        "condition": f"condition-{index}",
        "tokens": {f"asset-yes-{index}": "Yes", f"asset-no-{index}": "No"},
    }


def _fixture(tmp_path: Path, market_count: int = 1) -> tuple[Path, Path, str]:
    raw = tmp_path / "raw"
    raw.mkdir()
    store = Store(raw, reserve=1, segment_bytes=32 * 1024**2)
    store.rotate()
    store.append(
        "gap",
        {"reason": "process_start"},
        received_ns=START - 1_000_000_000,
        monotonic_ns=0,
    )
    markets = [_market(index) for index in range(1, market_count + 1)]
    store.append("discovery", "fixture universe", received_ns=START, cohort=markets)
    store.rotate()
    store.append(
        "gap",
        {
            "reason": "book_resynchronization",
            "affected_assets": {
                **{
                    f"asset-yes-{index}": "timestamp_regression"
                    for index in range(1, market_count + 1)
                },
                "asset-missing": "malformed_frame",
            },
        },
        received_ns=START + 10_000_001,
        monotonic_ns=1,
    )
    store.rotate()
    store.append(
        "gap",
        {"reason": "connection_failure"},
        received_ns=START + 20_000_002,
        monotonic_ns=2,
    )
    store.append(
        "gap",
        {"reason": "scheduled_refresh"},
        received_ns=START + 150_000_000,
        monotonic_ns=3,
    )
    store.close()

    campaign_path = tmp_path / "campaign.json"
    campaign_path.write_text(
        json.dumps(
            {
                "campaign_id": "fixture-campaign",
                "identity": {
                    "raw_root": str(raw.resolve()),
                    "start_ns": START,
                    "end_ns": START + 100_000_000,
                },
            }
        )
    )
    return campaign_path, raw, file_hash(campaign_path)


def _run(
    root: Path,
    campaign_path: Path,
    raw: Path,
    campaign_sha256: str,
    monkeypatch: pytest.MonkeyPatch,
    **kwargs: Any,
) -> dict[str, Any]:
    monkeypatch.setattr(analysis, "verify_campaign", lambda plan: None)
    return analysis.update_finalized_gap_detail_analysis(
        root,
        campaign_path=campaign_path,
        expected_campaign_sha256=campaign_sha256,
        expected_campaign_id="fixture-campaign",
        expected_source_root=raw,
        **kwargs,
    )


def test_gap_detail_analysis_is_bounded_resumable_and_maps_reported_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    campaign_path, raw, campaign_sha256 = _fixture(tmp_path)
    output = tmp_path / "observatory"
    (raw / f"{'9' * 20}-{'b' * 32}.open").write_bytes(b"must remain unopened")

    first = _run(output, campaign_path, raw, campaign_sha256, monkeypatch, max_segments=1)
    assert first["batch_processed_segment_count"] == 1
    assert first["processed_segment_count"] == 1
    assert first["pending_segment_count"] == 2
    assert first["campaign_window_gap_event_count"] == 0
    assert first["active_segment_read"] is False

    second = _run(output, campaign_path, raw, campaign_sha256, monkeypatch, max_segments=1)
    assert second["batch_processed_segment_count"] == 1
    assert second["campaign_window_gap_counts_by_reason"] == {"book_resynchronization": 1}
    assert second["campaign_window_affected_market_counts"] == {"market-1": 1}
    assert second["campaign_window_unmapped_affected_asset_count"] == 1

    complete = _run(output, campaign_path, raw, campaign_sha256, monkeypatch, max_segments=1)
    assert complete["processed_segment_count"] == complete["replayable_catalog_segment_count"] == 3
    assert complete["empty_finalized_segment_count"] == 1
    assert complete["pending_segment_count"] == 0
    assert complete["campaign_window_gap_event_count"] == 2
    assert complete["campaign_window_gap_counts_by_reason"] == {
        "book_resynchronization": 1,
        "connection_failure": 1,
    }
    assert complete["campaign_window_gap_events_without_reported_assets"] == 1
    assert complete["all_period_gap_counts_by_reason"] == {
        "book_resynchronization": 1,
        "connection_failure": 1,
        "process_start": 1,
        "scheduled_refresh": 1,
    }

    event_dir = output / "gap-detail-events" / "v1"
    assert len(list(event_dir.glob("*.json"))) == 3
    final_event = json.loads((event_dir / f"{3:020d}.json").read_text())
    assert [item["reason"] for item in final_event["gap_events"]] == [
        "connection_failure",
        "scheduled_refresh",
    ]
    assert final_event["gap_events"][0]["in_campaign_window"] is True
    assert final_event["gap_events"][1]["in_campaign_window"] is False
    assert final_event["gap_events"][0]["affected_market_ids"] == []
    assert "asset-yes" not in json.dumps(final_event)

    repeated = _run(output, campaign_path, raw, campaign_sha256, monkeypatch)
    assert repeated["batch_processed_segment_count"] == 0
    assert repeated["campaign_window_gap_event_count"] == 2
    assert len(list(event_dir.glob("*.json"))) == 3
    assert analysis.read_finalized_gap_detail_summary(output) == repeated


def test_gap_detail_analysis_rejects_changed_processed_catalog_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    campaign_path, raw, campaign_sha256 = _fixture(tmp_path)
    output = tmp_path / "observatory"
    _run(output, campaign_path, raw, campaign_sha256, monkeypatch, max_segments=1)

    first_sidecar = next(
        path for path in sorted(raw.glob("*.json")) if json.loads(path.read_text())["count"] > 0
    )
    catalog = json.loads(first_sidecar.read_text())
    catalog["sha256"] = "f" * 64
    first_sidecar.write_text(json.dumps(catalog))

    with pytest.raises(ValueError, match="catalog prefix changed"):
        _run(output, campaign_path, raw, campaign_sha256, monkeypatch)


def test_gap_detail_analysis_bounds_markets_separately_from_gap_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    campaign_path, raw, campaign_sha256 = _fixture(tmp_path, market_count=129)

    result = _run(
        tmp_path / "observatory",
        campaign_path,
        raw,
        campaign_sha256,
        monkeypatch,
        max_segments=2,
    )

    assert result["campaign_window_gap_counts_by_reason"] == {"book_resynchronization": 1}
    assert len(result["campaign_window_affected_market_counts"]) == 129
    assert set(result["campaign_window_affected_market_counts"].values()) == {1}


def test_gap_detail_analysis_rejects_tampered_event_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    campaign_path, raw, campaign_sha256 = _fixture(tmp_path)
    output = tmp_path / "observatory"
    _run(output, campaign_path, raw, campaign_sha256, monkeypatch)

    event_path = output / "gap-detail-events" / "v1" / f"{1:020d}.json"
    event = json.loads(event_path.read_text())
    event["gap_event_count"] = 999
    event_path.write_text(json.dumps(event))

    with pytest.raises(ValueError, match="digest mismatch"):
        _run(output, campaign_path, raw, campaign_sha256, monkeypatch)
