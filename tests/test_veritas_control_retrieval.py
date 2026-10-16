from __future__ import annotations

import asyncio

import httpx
import pytest
from midas.veritas.control_retrieval import (
    CONTROL_RETRIEVAL_VERSION,
    retrieve_control_metadata,
    summarize_control_rows,
)
from midas.veritas.observatory import PublicReadClient


def _eligible_market(market_id: str) -> dict[str, object]:
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


def test_direct_control_lookup_is_one_bounded_public_request():
    market = _eligible_market("123")
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[market])

    async def run() -> dict[str, object]:
        client = PublicReadClient(
            transport=httpx.MockTransport(handle),
            min_interval_seconds=0.2,
            max_requests=1,
        )
        try:
            return await retrieve_control_metadata(client, ["123", "456"])
        finally:
            await client.close()

    result = asyncio.run(run())
    assert len(seen) == 1
    assert seen[0].method == "GET"
    assert seen[0].url.host == "gamma-api.polymarket.com"
    assert seen[0].url.path == "/markets"
    assert seen[0].url.params.get_list("id") == ["123", "456"]
    assert seen[0].url.params["closed"] == "any"
    assert result["version"] == CONTROL_RETRIEVAL_VERSION
    response = result["response"]
    assert isinstance(response, dict)
    outcomes = response["outcomes"]
    assert isinstance(outcomes, list)
    assert outcomes[0]["classification"] == "eligible_current_market_metadata"
    assert outcomes[1]["classification"] == "not_returned_by_direct_id_query"
    assert "response_payload" not in outcomes[0]


def test_returned_closed_control_has_explicit_ineligibility_reason():
    closed = _eligible_market("321")
    closed["closed"] = True
    outcomes = summarize_control_rows(["321"], [closed])
    assert outcomes[0]["classification"] == "returned_but_ineligible"
    assert outcomes[0]["ineligibility_reason"] == "closed_or_unknown_lifecycle"


def test_control_lookup_rejects_oversized_or_duplicate_cohort():
    with pytest.raises(ValueError, match="1..8"):
        summarize_control_rows([str(index) for index in range(9)], [])
    with pytest.raises(ValueError, match="1..8"):
        summarize_control_rows(["123", "123"], [])
