from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from midas.veritas.observatory import (
    DEFAULT_SEED,
    MAX_LATEST_SUMMARY_BYTES,
    VERSION,
    PublicReadClient,
    _atomic_json,
    _collect_pair_books,
    _query_plan,
    _validate_book_batch,
    run_scan,
)


def test_latest_summary_publication_is_bounded_and_preserves_prior_file(tmp_path):
    path = tmp_path / "latest-summary.json"
    previous = b'{"scan_id":"prior"}'
    path.write_bytes(previous)

    with pytest.raises(ValueError, match="publication exceeds"):
        _atomic_json(
            path,
            {"detail": "x" * MAX_LATEST_SUMMARY_BYTES},
            maximum=MAX_LATEST_SUMMARY_BYTES,
        )

    assert path.read_bytes() == previous
    assert not list(tmp_path.glob(".latest-summary.json.*.tmp"))


def _market(index: int) -> dict[str, Any]:
    number = index + 1
    condition = "0x" + f"{number:064x}"
    return {
        "id": str(100_000 + number),
        "conditionId": condition,
        "version": "v1",
        "question": f"Fixture event {number}?",
        "slug": f"fixture-event-{number}",
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": json.dumps([str(1_000 + 2 * number), str(1_001 + 2 * number)]),
        "positionIds": [],
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
        "liquidityNum": 100 + number * 1_000,
        "volume24hr": number * 100,
        "endDate": "2026-10-19T00:00:00Z" if number <= 10 else "2027-03-01T00:00:00Z",
        "spread": "0.01" if number % 2 else "0.06",
        "bestBid": "0.39",
        "bestAsk": "0.40",
        "category": ["Politics", "Sports", "Crypto", "Economics"][number % 4],
        "events": [{"id": str(50_000 + number), "category": "Fixture"}],
    }


def _transport(
    markets: list[dict[str, Any]], seen_requests: list[tuple[str, str, str]]
) -> httpx.MockTransport:
    by_asset: dict[str, dict[str, Any]] = {}
    for market in markets:
        yes, no = json.loads(market["clobTokenIds"])
        by_asset[yes] = {"market": market["conditionId"], "side": "yes"}
        by_asset[no] = {"market": market["conditionId"], "side": "no"}

    def handle(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8") if request.content else ""
        seen_requests.append((request.method, request.url.host, request.url.path))
        if request.method == "GET" and request.url.host == "gamma-api.polymarket.com":
            query = dict(request.url.params)
            if query.get("tag_id"):
                page = markets[::3][:20]
            elif query.get("end_date_min"):
                page = markets[:20]
            elif query.get("liquidity_num_min") == "10000":
                page = markets[8:28]
            elif query.get("liquidity_num_min") == "1000":
                page = markets[18:38]
            elif query.get("liquidity_num_min") == "1":
                page = markets[28:48]
            else:
                page = markets[5:45]
            return httpx.Response(200, json=page)
        if (
            request.method == "POST"
            and request.url.host == "clob.polymarket.com"
            and request.url.path == "/books"
        ):
            assets = json.loads(body)
            response = []
            for item in assets:
                asset_id = item["token_id"]
                identity = by_asset[asset_id]
                stamp = time.time_ns() // 1_000_000
                price = ".40" if identity["side"] == "yes" else ".50"
                response.append(
                    {
                        "market": identity["market"],
                        "asset_id": asset_id,
                        "timestamp": str(stamp),
                        "hash": f"hash-{asset_id}",
                        "bids": [{"price": ".39", "size": "100"}],
                        "asks": [{"price": price, "size": "100"}],
                        "min_order_size": "5",
                        "tick_size": "0.01",
                        "neg_risk": False,
                    }
                )
            return httpx.Response(200, json=response)
        return httpx.Response(404, json={"error": "unexpected endpoint"})

    return httpx.MockTransport(handle)


async def _scan(root: Path, transport: httpx.MockTransport) -> dict[str, Any]:
    return await run_scan(
        root,
        target_markets=30,
        control_count=4,
        seed=DEFAULT_SEED,
        quantity_grid=("5", "10", "20"),
        transport=transport,
        request_interval_seconds=0.2,
    )


def test_stratified_observatory_is_bounded_reproducible_and_keeps_controls(tmp_path):
    markets = [_market(index) for index in range(45)]
    seen: list[tuple[str, str, str]] = []
    transport = _transport(markets, seen)

    first = __import__("asyncio").run(_scan(tmp_path, transport))
    first_controls = json.loads((tmp_path / "control-cohort.json").read_text())["market_ids"]
    control_record = json.loads((tmp_path / "control-cohort.json").read_text())
    assert control_record["version"] == "veritas-control-cohort-v1"
    control_record["version"] = "veritas-public-observatory-v1"
    (tmp_path / "control-cohort.json").write_text(json.dumps(control_record))
    second = __import__("asyncio").run(_scan(tmp_path, transport))
    second_controls = json.loads((tmp_path / "control-cohort.json").read_text())["market_ids"]

    assert first["analysis_version"] == VERSION
    assert first["measurement_pilot"]["study_id"] == "VERITAS-M2-COVERAGE-PILOT-001"
    assert first["measurement_pilot"]["status"] == "not_advanced_analysis_protocol_changed"
    assert first["measurement_pilot_v2"]["study_id"] == "VERITAS-M2-COVERAGE-PILOT-002"
    assert first["measurement_pilot_v2"]["status"] == "not_advanced_analysis_protocol_changed"
    assert first["discovery_frame_protocol"] == "stratified-gamma-page-rotation-v3-reference-sample"
    assert first["selection"]["plan"]["phase"] == "liquidity"
    assert second["selection"]["plan"]["phase"] == "expiry"
    assert first_controls == second_controls
    assert json.loads((tmp_path / "control-cohort.json").read_text())["version"] == (
        "veritas-public-observatory-v1"
    )
    assert len(first_controls) == 4
    assert len(first["selection"]["selected_markets"]) == 30
    assert len(second["selection"]["selected_markets"]) == 30
    stable_rows = [
        row
        for row in first["selection"]["selected_markets"]
        if row["cohort_role"] == "stable_random_control"
    ]
    rotating_rows = [
        row
        for row in first["selection"]["selected_markets"]
        if row["cohort_role"] == "rotating_stratified"
    ]
    reference_rows = [
        row
        for row in first["selection"]["selected_markets"]
        if row["cohort_role"] == "reference_random"
    ]
    assert all(row["selection_probability"] == str(4 / 45) for row in stable_rows)
    assert all(0 < float(row["selection_probability"]) <= 1 for row in rotating_rows)
    assert len(reference_rows) == 8
    assert all(row["selection_probability"] == str(8 / 41) for row in reference_rows)
    assert first["discovery"]["query_count"] == 6
    assert first["discovery"]["eligible_pair_markets"] == 45
    assert first["counts"]["valid_quality_pairs"] == 30
    assert all(row["liquidity_band"] != "unknown" for row in first["selection"]["selected_markets"])
    assert all(row["expiry_band"] != "unknown" for row in first["selection"]["selected_markets"])
    assert all(row["spread_band"] != "unknown" for row in first["selection"]["selected_markets"])
    assert first["counts"]["positive_full_depth_gross_by_quantity"]["20"] == 30
    assert first["counts"]["positive_minimum_notional_by_quantity"]["20"] == 0
    assert first["counts"]["positive_minimum_shares_by_quantity"]["20"] == 30
    assert first["counts"]["positive_reported_constraints_by_quantity"]["20"] == 0
    assert first["counts"]["positive_fragmentation_safe_fee_sensitivity_by_quantity"]["20"] == 0
    assert first["orders_submitted"] is False
    assert first["authenticated_requests"] is False
    assert all(host in {"gamma-api.polymarket.com", "clob.polymarket.com"} for _, host, _ in seen)
    assert all(
        (method == "GET" and host == "gamma-api.polymarket.com" and path == "/markets")
        or (method == "POST" and host == "clob.polymarket.com" and path == "/books")
        for method, host, path in seen
    )
    assert len(seen) == 14

    snapshot_path = tmp_path / first["snapshot_file"]
    stored = json.loads(gzip.decompress(snapshot_path.read_bytes()))
    assert stored["snapshot_evidence_sha256"] == first["snapshot_evidence_sha256"]
    assert all(
        row["audit"]["constraint_support"]["minimum_order_notional_unit_status"] == "unverified"
        and all(
            quantity["minimum_order_notional_satisfied"] is None
            and quantity["minimum_order_constraints_satisfied"] is None
            for quantity in row["audit"]["quantity_results"]
        )
        for row in stored["market_observations"]
    )
    assert len(stored["source_requests"]["gamma_pages"]) == 6
    assert all(page["response_payload"] for page in stored["source_requests"]["gamma_pages"])
    assert stored["source_requests"]["clob_books"]["response_payload"]
    latest = json.loads((tmp_path / "latest-summary.json").read_text())
    assert latest["scan_id"] == second["scan_id"]
    assert latest["measurement_pilot"]["status"] == "not_advanced_analysis_protocol_changed"
    assert latest["measurement_pilot_v2"]["status"] == "not_advanced_analysis_protocol_changed"
    assert latest["coverage_kind"] == "intermittent_public_snapshots"
    assert (
        latest["discovery"]["frame_protocol"]
        == "stratified-gamma-page-rotation-v3-reference-sample"
    )
    assert latest["discovery"]["offset_bucket_seconds"] == 30 * 60
    assert latest["collection_bounds"]["target_markets"] == 30
    assert latest["collection_bounds"]["maximum_public_read_calls_per_scan"] == 8
    assert latest["collection_bounds"]["maximum_public_http_attempts_per_scan"] == 16
    assert latest["collection_bounds"]["maximum_retries_per_public_read"] == 1
    assert latest["collection_bounds"]["maximum_response_bytes"] == 48 * 1024**2
    assert latest["source_http_attempts"] == 7
    assert len(latest["selection"]["sampled_markets"]) == 30
    assert all("selection_probability" in row for row in latest["selection"]["sampled_markets"])
    assert all("primary_category_source" in row for row in latest["selection"]["sampled_markets"])
    assert (
        sum(
            row["cohort_role"] == "reference_random"
            for row in latest["selection"]["sampled_markets"]
        )
        == 8
    )
    assert "unknown" not in latest["selection"]["selected_by_liquidity"]
    assert (
        latest["continuous_analysis"]["analysis_version"]
        == "veritas-finalized-snapshot-analysis-v6"
    )
    assert "observed_market_ids" not in latest["continuous_analysis"].get("cumulative", {})
    from midas.veritas.scan_catalog import summary as catalog_summary

    assert catalog_summary(tmp_path)["scan_count"] == 2
    status_files = list((tmp_path / "pipeline-status").glob("*.json"))
    assert len(status_files) == 2
    assert all(json.loads(path.read_text())["snapshot_file_sha256"] for path in status_files)


def test_snapshot_change_stratum_requires_repeated_snapshot_evidence():
    from midas.veritas.observatory import _snapshot_change_bucket

    assert _snapshot_change_bucket("m1", {}) == "unclassified"
    history = {
        "m1": [
            {"captured_ns": 1_000_000_000, "state_hash": "a"},
            {"captured_ns": 1_801_000_000_000, "state_hash": "b"},
            {"captured_ns": 3_601_000_000_000, "state_hash": "c"},
        ]
    }
    assert _snapshot_change_bucket("m1", history) == "higher_snapshot_change"


def test_discovery_offsets_rotate_across_liquidity_and_id_frames():
    from datetime import UTC, datetime

    from midas.veritas.observatory import DISCOVERY_OFFSET_BUCKET_NS

    start_ns = int(datetime(2026, 10, 15, 9, 0, tzinfo=UTC).timestamp() * 1_000_000_000)
    first = dict(_query_plan(start_ns, DEFAULT_SEED))
    repeated = dict(_query_plan(start_ns + 10_000_000_000, DEFAULT_SEED))
    following = dict(_query_plan(start_ns + DISCOVERY_OFFSET_BUCKET_NS, DEFAULT_SEED))
    rotating_ids = (
        "high_liquidity",
        "medium_liquidity",
        "low_liquidity",
        "rotating_id_control_frame",
    )

    first_offsets = {query_id: first[query_id]["offset"] for query_id in rotating_ids}
    repeated_offsets = {query_id: repeated[query_id]["offset"] for query_id in rotating_ids}
    next_offsets = {query_id: following[query_id]["offset"] for query_id in rotating_ids}
    assert len(set(first_offsets.values())) == len(rotating_ids)
    assert all(0 <= offset < 1_000 for offset in first_offsets.values())
    assert repeated_offsets == first_offsets
    assert all(first_offsets[key] != next_offsets[key] for key in rotating_ids)
    assert "offset" not in first["near_expiry"]
    assert "offset" not in first["tagged_near_expiry"]


def test_market_category_prefers_market_category_to_alphabetical_tags():
    from midas.veritas.observatory import _category_metadata

    raw = {
        "category": ["Economics", "Macro"],
        "events": [
            {
                "category": "Geopolitics",
                "tags": [{"label": "Elections"}, {"label": "Politics"}],
            }
        ],
        "tags": [{"label": "Crypto"}],
    }

    categories, primary, source = _category_metadata(raw)
    assert categories == ["Crypto", "Economics", "Elections", "Geopolitics", "Macro", "Politics"]
    assert primary == "Economics"
    assert source == "market.category"


def test_market_category_falls_back_to_event_then_tags():
    from midas.veritas.observatory import _category_metadata

    categories, primary, source = _category_metadata(
        {"events": [{"category": "Sports", "tags": [{"label": "Baseball"}]}]}
    )
    assert categories == ["Baseball", "Sports"]
    assert (primary, source) == ("Sports", "event.category")

    categories, primary, source = _category_metadata({"tags": [{"label": "Crypto"}]})
    assert categories == ["Crypto"]
    assert (primary, source) == ("Crypto", "tag.label")


def test_public_read_receipt_counts_retry_attempts_and_includes_retry_delay():
    import asyncio

    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[])

    async def exercise() -> tuple[dict[str, Any], int]:
        client = PublicReadClient(transport=httpx.MockTransport(respond), min_interval_seconds=0.2)
        try:
            _, receipt = await client.discover({"limit": 50})
            return receipt, client.request_attempts
        finally:
            await client.close()

    receipt, request_attempts = asyncio.run(exercise())
    assert attempts == 2
    assert request_attempts == 2
    assert receipt["request_attempts"] == 2
    assert receipt["received_at_ns"] >= receipt["requested_at_ns"]


def test_public_read_enforces_response_byte_bound_while_streaming(monkeypatch):
    import asyncio

    import midas.veritas.observatory as observatory
    import pytest

    monkeypatch.setattr(observatory, "MAX_RESPONSE_BYTES", 4)
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, content=b"12345")

    async def exercise() -> None:
        client = PublicReadClient(transport=httpx.MockTransport(respond))
        try:
            await client.discover({"limit": 50})
        finally:
            await client.close()

    with pytest.raises(ValueError, match="response exceeds its byte bound"):
        asyncio.run(exercise())
    assert attempts == 1


def _book(asset_id: str, condition: str) -> dict[str, Any]:
    return {
        "market": condition,
        "asset_id": asset_id,
        "timestamp": "1792044000000",
        "hash": f"book-{asset_id}",
        "bids": [{"price": "0.39", "size": "100"}],
        "asks": [{"price": "0.40", "size": "100"}],
        "min_order_size": "5",
        "tick_size": "0.01",
        "neg_risk": False,
    }


def test_book_batch_classifies_missing_duplicate_unexpected_and_malformed_assets():
    valid_d = _book("d", "condition-d")
    payload = [
        _book("a", "condition-a"),
        _book("a", "condition-a"),
        {**_book("b", "condition-b"), "asks": None},
        _book("unexpected", "condition-x"),
        "not-a-book-object",
        valid_d,
    ]

    usable, integrity = _validate_book_batch(payload, ["a", "b", "c", "d"])

    assert integrity["status"] == "partial"
    assert integrity["missing_asset_ids"] == ["c"]
    assert integrity["duplicate_asset_ids"] == ["a"]
    assert integrity["unexpected_asset_ids"] == ["unexpected"]
    assert integrity["malformed_assets"] == {"b": ["asks_not_array"]}
    assert integrity["malformed_rows"] == [{"row_index": 4, "reason": "row_not_object"}]
    assert set(usable) == {"d"}
    isolated_usable, isolated_integrity = _validate_book_batch(
        [_book("a", "condition-a"), _book("unexpected", "condition-x")], ["a"]
    )
    assert isolated_integrity["status"] == "partial"
    assert isolated_integrity["unexpected_asset_ids"] == ["unexpected"]
    assert set(isolated_usable) == {"a"}


def test_eighty_requested_seventy_eight_returned_recovers_only_the_affected_pair():
    import asyncio
    import hashlib

    rows = [
        {
            "market_id": f"market-{index}",
            "condition": f"condition-{index}",
            "outcomes": {"yes": f"yes-{index}", "no": f"no-{index}"},
        }
        for index in range(40)
    ]
    initial_missing = {"yes-17", "no-17"}

    class FixtureClient:
        def __init__(self):
            self.calls: list[list[str]] = []

        async def books(self, assets: list[str]):
            self.calls.append(list(assets))
            is_retry = len(self.calls) > 1
            returned = [
                _book(asset, f"condition-{asset.split('-')[-1]}")
                for asset in assets
                if is_retry or asset not in initial_missing
            ]
            wire = json.dumps(returned, separators=(",", ":"))
            receipt = {
                "requested_at_ns": 1_792_044_000_000_000_000,
                "received_at_ns": 1_792_044_000_010_000_000,
                "request_duration_ms": 10.0,
                "request_asset_ids": list(assets),
                "response_book_count": len(returned),
                "response_sha256": hashlib.sha256(wire.encode()).hexdigest(),
                "response_payload": wire,
            }
            return returned, receipt

    client = FixtureClient()
    result = asyncio.run(_collect_pair_books(client, rows))

    assert [len(call) for call in client.calls] == [80, 2]
    assert result["batch_receipts"][0]["response_book_count"] == 78
    assert result["initial_integrity"]["returned_row_count"] == 78
    assert result["retry_pair_count"] == 1
    assert result["pair_timing"]["market-17"]["status"] == "recovered_by_pair_retry"
    assert sum(item["status"] == "complete" for item in result["pair_timing"].values()) == 39
    assert all(len(result["pair_books"][f"market-{index}"]) == 2 for index in range(40))


def test_failed_pair_retry_does_not_invalidate_other_complete_pairs():
    import asyncio
    import hashlib

    rows = [
        {
            "market_id": f"market-{index}",
            "condition": f"condition-{index}",
            "outcomes": {"yes": f"yes-{index}", "no": f"no-{index}"},
        }
        for index in range(4)
    ]

    class FixtureClient:
        def __init__(self):
            self.calls = 0

        async def books(self, assets: list[str]):
            self.calls += 1
            returned = [
                _book(asset, f"condition-{asset.split('-')[-1]}")
                for asset in assets
                if asset != "yes-1"
            ]
            wire = json.dumps(returned, separators=(",", ":"))
            return returned, {
                "requested_at_ns": 1_792_044_000_000_000_000,
                "received_at_ns": 1_792_044_000_010_000_000,
                "request_duration_ms": 10.0,
                "request_asset_ids": list(assets),
                "response_book_count": len(returned),
                "response_sha256": hashlib.sha256(wire.encode()).hexdigest(),
                "response_payload": wire,
            }

    client = FixtureClient()
    result = asyncio.run(_collect_pair_books(client, rows))

    assert client.calls == 2
    assert result["pair_timing"]["market-1"]["status"] == "incomplete_after_retry"
    assert result["pair_books"]["market-1"] == {}
    for index in (0, 2, 3):
        assert result["pair_timing"][f"market-{index}"]["status"] == "complete"
        assert len(result["pair_books"][f"market-{index}"]) == 2
