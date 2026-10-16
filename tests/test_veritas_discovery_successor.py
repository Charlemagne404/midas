from __future__ import annotations

import asyncio
import gzip
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from midas.veritas.discovery_successor import (
    ACTIVE_OBSERVATORY_ROOT,
    CONTROL_COHORT_VERSION,
    MAX_CUMULATIVE_RESPONSE_BYTES,
    DiscoverySuccessorClient,
    require_fixed_pilot_stop,
    run_discovery_successor,
)


def _market(index: int, *, condition_index: int | None = None) -> dict[str, Any]:
    condition = condition_index if condition_index is not None else index + 1
    return {
        "id": str(100_000 + index),
        "conditionId": "0x" + f"{condition:064x}",
        "version": "v1",
        "question": f"Fixture market {index}?",
        "slug": f"fixture-market-{index}",
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": json.dumps([str(200_000 + index * 2), str(200_001 + index * 2)]),
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "negRisk": False,
        "negRiskAugmented": False,
        "restricted": False,
        "orderPriceMinTickSize": "0.01",
        "orderMinSize": 5,
        "feesEnabled": False,
        "feeSchedule": None,
        "liquidityNum": 10_000 + index * 100,
        "volume24hr": 5_000 + index * 10,
        "endDate": "2027-03-01T00:00:00Z",
        "spread": "0.02",
        "bestBid": "0.49",
        "bestAsk": "0.51",
        "category": ["Politics", "Sports", "Crypto", "Economics"][index % 4],
    }


def _write_controls(path: Path, market_ids: list[str]) -> bytes:
    payload = json.dumps(
        {
            "version": CONTROL_COHORT_VERSION,
            "created_at_ns": 1,
            "market_ids": market_ids,
        },
        sort_keys=True,
    ).encode()
    path.write_bytes(payload)
    return payload


def _transport(
    markets: list[dict[str, Any]],
    seen: list[tuple[str, str, str]],
    *,
    missing_controls: set[str] | None = None,
    duplicate_control: str | None = None,
    conflict_control: str | None = None,
) -> httpx.MockTransport:
    by_id = {row["id"]: row for row in markets}
    by_asset: dict[str, dict[str, Any]] = {}
    for row in markets:
        yes, no = json.loads(row["clobTokenIds"])
        by_asset[yes] = {"condition": row["conditionId"], "side": "yes"}
        by_asset[no] = {"condition": row["conditionId"], "side": "no"}

    def handle(request: httpx.Request) -> httpx.Response:
        body = request.read().decode() if request.content else ""
        seen.append((request.method, request.url.host, request.url.path))
        if request.method == "GET" and request.url.host == "gamma-api.polymarket.com":
            if request.url.params.get("id") is not None:
                ids = request.url.params.get_list("id")
                rows = [
                    by_id[market_id]
                    for market_id in ids
                    if market_id in by_id and market_id not in (missing_controls or set())
                ]
                if duplicate_control and duplicate_control in by_id:
                    rows.append(by_id[duplicate_control])
                if conflict_control and conflict_control in by_id:
                    changed = dict(by_id[conflict_control])
                    changed["conditionId"] = "0x" + f"{999_999:064x}"
                    rows = [row for row in rows if row["id"] != conflict_control]
                    rows.append(changed)
                return httpx.Response(200, json=rows)
            return httpx.Response(200, json=markets[:45])
        if (
            request.method == "POST"
            and request.url.host == "clob.polymarket.com"
            and request.url.path == "/books"
        ):
            response = []
            for item in json.loads(body):
                asset_id = item["token_id"]
                identity = by_asset[asset_id]
                stamp = time.time_ns() // 1_000_000
                ask = "0.51" if identity["side"] == "yes" else "0.52"
                bid = "0.49" if identity["side"] == "yes" else "0.50"
                response.append(
                    {
                        "market": identity["condition"],
                        "asset_id": asset_id,
                        "timestamp": str(stamp),
                        "hash": f"book-{asset_id}",
                        "bids": [{"price": bid, "size": "100"}],
                        "asks": [{"price": ask, "size": "100"}],
                        "min_order_size": "5",
                        "tick_size": "0.01",
                        "neg_risk": False,
                    }
                )
            return httpx.Response(200, json=response)
        return httpx.Response(404, json={"error": "unexpected endpoint"})

    return httpx.MockTransport(handle)


def _scan(
    root: Path,
    control_file: Path,
    transport: httpx.MockTransport,
    *,
    target: int = 30,
) -> dict[str, Any]:
    return asyncio.run(
        run_discovery_successor(
            root,
            control_file=control_file,
            target_markets=target,
            quantity_grid=("5", "10"),
            transport=transport,
            request_interval_seconds=0.2,
        )
    )


def test_eight_read_successor_keeps_frames_and_adds_direct_only_control(tmp_path):
    markets = [_market(index) for index in range(60)]
    controls = [markets[0]["id"], markets[59]["id"]]
    control_file = tmp_path / "control-cohort.json"
    original_controls = _write_controls(control_file, controls)
    root = tmp_path / "successor-root"
    seen: list[tuple[str, str, str]] = []

    report = _scan(root, control_file, _transport(markets, seen))

    assert len(seen) == 8
    assert seen[:7] == [("GET", "gamma-api.polymarket.com", "/markets")] * 7
    assert seen[7] == ("POST", "clob.polymarket.com", "/books")
    assert report["analysis_version"] == "veritas-public-observatory-discovery-successor-v1"
    assert report["collection_bounds"]["maximum_public_read_calls_per_scan"] == 8
    assert report["source_requests"]["public_read_calls"] == 8
    assert report["source_requests"]["public_http_attempts"] == 8
    assert len(report["source_requests"]["gamma_pages"]) == 6
    request_starts = [row["requested_at_ns"] for row in report["source_requests"]["gamma_pages"]]
    request_starts.extend(
        [
            report["source_requests"]["direct_control_lookup"]["requested_at_ns"],
            report["source_requests"]["clob_books"]["requested_at_ns"],
        ]
    )
    assert all(
        later - earlier >= 150_000_000
        for earlier, later in zip(request_starts[:-1], request_starts[1:], strict=True)
    )
    assert report["direct_control_lookup"]["eligible_control_count"] == 2
    assert report["direct_control_lookup"]["direct_only_eligible_control_count"] == 1
    assert report["discovery"]["unique_market_ids"] == 45
    assert report["selection"]["frame_eligible_population"] == 45
    selected = report["selection"]["selected_markets"]
    assert len(selected) == 30
    stable = [row for row in selected if row["cohort_role"] == "stable_random_control"]
    rotating = [row for row in selected if row["cohort_role"] == "rotating_stratified"]
    assert {row["market_id"] for row in stable} == set(controls)
    assert all(
        row["selection_probability"] == "1 conditional on frozen control cohort" for row in stable
    )
    assert all(0 < float(row["selection_probability"]) <= 1 for row in rotating)
    assert all(row["selection_stratum"] for row in rotating)
    assert report["selection"]["plan"]["rotation_population_after_controls"] == 44
    assert "six-frame eligible union" in report["selection"]["plan"]["probability_scope"]
    assert report["counts"]["valid_quality_pairs"] == 30
    assert report["counts"]["positive_top_gross_pairs"] == 0
    assert report["orders_submitted"] is False
    assert report["authenticated_requests"] is False
    assert "measurement_pilot" not in json.loads((root / "latest-summary.json").read_text())
    assert control_file.read_bytes() == original_controls
    assert len(list((root / "snapshots").glob("*.json.gz"))) == 1
    stored = json.loads(gzip.decompress(next((root / "snapshots").glob("*.json.gz")).read_bytes()))
    assert stored["snapshot_evidence_sha256"] == report["snapshot_evidence_sha256"]
    assert stored["source_requests"]["public_read_calls"] == 8
    assert not (ACTIVE_OBSERVATORY_ROOT / "successor-root").exists()


def test_direct_lookup_missing_control_is_not_reused_from_frame(tmp_path):
    markets = [_market(index) for index in range(60)]
    present, missing = markets[0]["id"], markets[1]["id"]
    control_file = tmp_path / "control-cohort.json"
    _write_controls(control_file, [present, missing])
    seen: list[tuple[str, str, str]] = []
    report = _scan(
        tmp_path / "root",
        control_file,
        _transport(markets, seen, missing_controls={missing}),
    )

    outcome_by_hash = {
        row["market_id_sha256"]: row for row in report["direct_control_lookup"]["outcomes"]
    }
    from midas.veritas.control_retrieval import _id_hash

    assert outcome_by_hash[_id_hash(missing)]["classification"] == "not_returned_by_direct_id_query"
    assert missing not in {row["market_id"] for row in report["selection"]["selected_markets"]}
    assert present in {row["market_id"] for row in report["selection"]["selected_markets"]}
    assert report["selection"]["plan"]["stable_control_available_this_scan"] == 1
    assert len(seen) == 8


@pytest.mark.parametrize("mode", ["duplicate", "identity_conflict"])
def test_ambiguous_or_conflicting_direct_control_fails_closed(tmp_path, mode):
    markets = [_market(index) for index in range(60)]
    control = markets[0]["id"]
    control_file = tmp_path / "control-cohort.json"
    _write_controls(control_file, [control])
    seen: list[tuple[str, str, str]] = []
    options = (
        {"duplicate_control": control} if mode == "duplicate" else {"conflict_control": control}
    )
    report = _scan(tmp_path / "root", control_file, _transport(markets, seen, **options))

    classification = report["direct_control_lookup"]["outcomes"][0]["classification"]
    assert classification == (
        "duplicate_id_in_response"
        if mode == "duplicate"
        else "identity_conflict_with_six_frame_record"
    )
    assert control not in {row["market_id"] for row in report["selection"]["selected_markets"]}
    assert report["selection"]["plan"]["stable_control_available_this_scan"] == 0
    assert len(seen) == 8


def test_successor_rejects_root_overlapping_active_observer(tmp_path):
    markets = [_market(index) for index in range(60)]
    control_file = tmp_path / "control-cohort.json"
    _write_controls(control_file, [markets[0]["id"]])
    with pytest.raises(ValueError, match="separate from the active observer root"):
        _scan(ACTIVE_OBSERVATORY_ROOT, control_file, _transport(markets, []))


def test_successor_rejects_dangling_symlink_root_without_creating_target(tmp_path):
    markets = [_market(index) for index in range(60)]
    control_file = tmp_path / "control-cohort.json"
    _write_controls(control_file, [markets[0]["id"]])
    target = tmp_path / "uncreated-target"
    root_link = tmp_path / "dangling-root-link"
    root_link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="cannot be a symlink"):
        _scan(root_link, control_file, _transport(markets, []))

    assert not target.exists()


def test_cumulative_response_budget_stops_after_first_oversized_frame(tmp_path, monkeypatch):
    import midas.veritas.discovery_successor as successor

    markets = [_market(index) for index in range(60)]
    control_file = tmp_path / "control-cohort.json"
    _write_controls(control_file, [markets[0]["id"]])
    seen: list[tuple[str, str, str]] = []
    monkeypatch.setattr(successor, "MAX_CUMULATIVE_RESPONSE_BYTES", 1)

    with pytest.raises(ValueError, match="cumulative response budget"):
        _scan(tmp_path / "root", control_file, _transport(markets, seen))
    assert len(seen) == 1
    assert not list((tmp_path / "root" / "snapshots").glob("*.json.gz"))


def test_successor_client_rejects_control_lookup_before_six_frames():
    client = DiscoverySuccessorClient(min_interval_seconds=0.2)
    try:
        assert client.max_requests == 8
        assert MAX_CUMULATIVE_RESPONSE_BYTES == 64 * 1024**2
        with pytest.raises(ValueError, match="must follow all six"):
            asyncio.run(client.direct_control_lookup(["100000"]))
        assert client.requests == 0
    finally:
        asyncio.run(client.close())


def test_cli_guard_blocks_before_and_allows_after_fixed_pilot_stop(tmp_path):
    root = tmp_path / "pilot"
    root.mkdir()
    latest = root / "latest-summary.json"
    latest.write_text(
        json.dumps(
            {
                "measurement_pilot": {
                    "ends_at_utc": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
                }
            }
        )
    )
    with pytest.raises(RuntimeError, match="held until"):
        require_fixed_pilot_stop(root)

    latest.write_text(
        json.dumps(
            {
                "measurement_pilot": {
                    "ends_at_utc": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
                }
            }
        )
    )
    require_fixed_pilot_stop(root)
