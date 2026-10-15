from __future__ import annotations

import gzip
import json
import time
from pathlib import Path
from typing import Any

import httpx
from midas.veritas.observatory import DEFAULT_SEED, VERSION, run_scan


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
    second = __import__("asyncio").run(_scan(tmp_path, transport))
    second_controls = json.loads((tmp_path / "control-cohort.json").read_text())["market_ids"]

    assert first["analysis_version"] == VERSION
    assert first["selection"]["plan"]["phase"] == "liquidity"
    assert second["selection"]["plan"]["phase"] == "expiry"
    assert first_controls == second_controls
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
    assert all(row["selection_probability"] == str(4 / 45) for row in stable_rows)
    assert all(0 < float(row["selection_probability"]) <= 1 for row in rotating_rows)
    assert first["discovery"]["query_count"] == 6
    assert first["discovery"]["eligible_pair_markets"] == 45
    assert first["counts"]["valid_quality_pairs"] == 30
    assert all(row["liquidity_band"] != "unknown" for row in first["selection"]["selected_markets"])
    assert all(row["expiry_band"] != "unknown" for row in first["selection"]["selected_markets"])
    assert all(row["spread_band"] != "unknown" for row in first["selection"]["selected_markets"])
    assert first["counts"]["positive_full_depth_gross_by_quantity"]["20"] == 30
    assert first["counts"]["positive_minimum_notional_by_quantity"]["20"] == 30
    assert first["counts"]["positive_fragmentation_safe_fee_sensitivity_by_quantity"]["20"] == 30
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
    assert len(stored["source_requests"]["gamma_pages"]) == 6
    assert all(page["response_payload"] for page in stored["source_requests"]["gamma_pages"])
    assert stored["source_requests"]["clob_books"]["response_payload"]
    latest = json.loads((tmp_path / "latest-summary.json").read_text())
    assert latest["scan_id"] == second["scan_id"]
    assert latest["coverage_kind"] == "intermittent_public_snapshots"
    assert "unknown" not in latest["selection"]["selected_by_liquidity"]


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
