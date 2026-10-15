"""Capture or replay a bounded, read-only OpenAI IPO NegRisk basket study."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_json
from midas.veritas.neg_risk_set_audit import audit_books

REPOSITORY = Path(__file__).resolve().parents[1]
STUDY_ROOT = REPOSITORY / "data" / "veritas-observatory" / "structure-studies"
MEMBERSHIP_PATH = STUDY_ROOT / "neg-risk-membership-openai-ipo-1792067167.json"
SOURCE_ARCHIVE_PATH = STUDY_ROOT / "neg-risk-membership-openai-ipo-1792067167-raw.json"
GROUP_ID = "0xd2c21cbb9d2cb407ab3dcf619d93f6d65b7967154cd6ee930f7758baa2b4bf00"
MARKET_IDS = tuple(str(value) for value in range(608_362, 608_369))
ADAPTER_ADDRESS = "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296"
RPC_URL = "https://polygon-bor-rpc.publicnode.com"
BOOKS_URL = "https://clob.polymarket.com/books"
MAX_RESPONSE_BYTES = 2_000_000
MAX_GROUP_MARKETS = 16
MAX_BOOK_AGE_MS = 5_000
MAX_BOOK_SKEW_MS = 250
MAX_BATCH_DURATION_MS = 5_000
USER_AGENT = "MIDAS-Veritas-readonly-structure-study/1.0"
ANALYSIS_VERSION = "veritas-openai-ipo-complete-outcome-basket-study-v1"
ZERO = Decimal(0)
ONE = Decimal(1)
_MONEY = r"\$(\d+(?:\.\d+)?)([bt])"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Any,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _time_text(timestamp_ns: int) -> str:
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, UTC).isoformat(
        timespec="microseconds"
    )


def _read_public_books(body: bytes) -> tuple[list[dict[str, Any]], bytes, dict[str, Any]]:
    if len(body) > 16_000:
        raise ValueError("CLOB request body exceeds the bounded token-list size")
    request = urllib.request.Request(
        BOOKS_URL,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    started_ns = time.time_ns()
    with opener.open(request, timeout=20) as response:
        response_body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise ValueError("CLOB response exceeded the 2,000,000-byte bound")
        status = response.status
        http_date = response.headers.get("Date")
    received_ns = time.time_ns()
    if status != 200:
        raise ValueError(f"CLOB endpoint returned HTTP {status}")
    value = json.loads(response_body)
    if (
        not isinstance(value, list)
        or len(value) > MAX_GROUP_MARKETS * 2
        or any(not isinstance(book, dict) for book in value)
    ):
        raise ValueError("CLOB response is not a bounded book list")
    metadata = {
        "url": BOOKS_URL,
        "method": "POST",
        "started_ns": started_ns,
        "received_ns": received_ns,
        "started_at_utc": _time_text(started_ns),
        "received_at_utc": _time_text(received_ns),
        "duration_ms": (received_ns - started_ns) // 1_000_000,
        "http_date": http_date,
        "status_code": status,
        "response_bytes": len(response_body),
        "response_sha256": _sha256(response_body),
    }
    return value, response_body, metadata


def _source_responses(source_archive: dict[str, Any]) -> dict[str, dict[str, Any]]:
    responses = source_archive.get("responses")
    if not isinstance(responses, list):
        raise ValueError("Membership source archive has no response list")
    result: dict[str, dict[str, Any]] = {}
    for response in responses:
        if not isinstance(response, dict) or not isinstance(response.get("name"), str):
            raise ValueError("Membership source archive contains an invalid response entry")
        body = str(response.get("body") or "").encode()
        if (
            response.get("status") != 200
            or response.get("response_bytes") != len(body)
            or response.get("response_sha256") != _sha256(body)
        ):
            raise ValueError(f"Membership response digest mismatch: {response.get('name')}")
        if response["name"] in result:
            raise ValueError("Membership source archive contains a duplicate response name")
        result[response["name"]] = response
    return result


def _rpc_result(responses: dict[str, dict[str, Any]], name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    response = responses.get(name)
    if response is None or not isinstance(response.get("request_body"), dict):
        raise ValueError(f"Missing captured Polygon RPC evidence: {name}")
    result = json.loads(str(response["body"]))
    if not isinstance(result, dict) or result.get("error") is not None:
        raise ValueError(f"Malformed Polygon RPC result: {name}")
    return response["request_body"], result


def _money_billions(number: str, unit: str) -> Decimal:
    value = Decimal(number)
    return value * (Decimal(1_000) if unit.casefold() == "t" else ONE)


def _range_for_question(question: str) -> tuple[Decimal, Decimal | None] | None:
    normalized = question.casefold().replace("’", "'")
    if "not ipo by december 31, 2026" in normalized:
        return None
    less_than = re.search(rf"less than\s+{_MONEY}\b", normalized)
    if less_than:
        return ZERO, _money_billions(less_than.group(1), less_than.group(2))
    between = re.search(rf"between\s+{_MONEY}\s+and\s+{_MONEY}\b", normalized)
    if between:
        lower = _money_billions(between.group(1), between.group(2))
        upper = _money_billions(between.group(3), between.group(4))
        if lower >= upper:
            raise ValueError("Market-cap interval is empty or reversed")
        return lower, upper
    at_least = re.search(rf"{_MONEY}\s+or greater\b", normalized)
    if at_least:
        return _money_billions(at_least.group(1), at_least.group(2)), None
    raise ValueError(f"Unsupported OpenAI IPO outcome: {question[:120]}")


def _verify_membership(
    membership: dict[str, Any], source_archive: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if (
        membership.get("group_id") != GROUP_ID
        or membership.get("orders_submitted") is not False
        or membership.get("authenticated_requests") is not False
    ):
        raise ValueError("Membership probe does not match the pinned group or read-only scope")
    responses = _source_responses(source_archive)
    if membership.get("membership_complete_by_index_and_onchain_count") is not True:
        raise ValueError("Membership probe is not marked complete")

    addresses = responses.get("official_adapter_addresses")
    if (
        addresses is None
        or addresses.get("method") != "GET"
        or addresses.get("url")
        != "https://raw.githubusercontent.com/Polymarket/neg-risk-ctf-adapter/main/addresses.json"
    ):
        raise ValueError("Missing official NegRisk adapter address source")
    address_map = json.loads(str(addresses["body"]))
    if str(address_map.get("137", {}).get("negRiskAdapter", "")).casefold() != ADAPTER_ADDRESS:
        raise ValueError("Captured Polygon adapter address does not match the official address source")
    chain_request, chain_response = _rpc_result(responses, "rpc_eth_chainId")
    block_request, block_response = _rpc_result(responses, "rpc_eth_blockNumber")
    call_request, call_response = _rpc_result(responses, "rpc_eth_call")
    if (
        chain_request.get("jsonrpc") != "2.0"
        or chain_request.get("id") != 10
        or chain_request.get("method") != "eth_chainId"
        or chain_response.get("result") != "0x89"
        or block_request.get("jsonrpc") != "2.0"
        or block_request.get("id") != 11
        or block_request.get("method") != "eth_blockNumber"
        or call_request.get("jsonrpc") != "2.0"
        or call_request.get("id") != 12
        or any(
            responses[name].get("url") != RPC_URL
            for name in ("rpc_eth_chainId", "rpc_eth_blockNumber", "rpc_eth_call")
        )
    ):
        raise ValueError("Captured RPC evidence is not a Polygon chain read")
    block_tag = block_response.get("result")
    call_params = call_request.get("params")
    expected_calldata = "0xb7f75d2c" + GROUP_ID[2:]
    if (
        not isinstance(block_tag, str)
        or not isinstance(call_params, list)
        or len(call_params) != 2
        or not isinstance(call_params[0], dict)
        or str(call_params[0].get("to", "")).casefold() != ADAPTER_ADDRESS
        or call_params[0].get("data") != expected_calldata
        or call_params[1] != block_tag
        or call_request.get("method") != "eth_call"
    ):
        raise ValueError("Captured RPC call does not query this group at the recorded block")
    count_hex = str(call_response.get("result") or "")
    try:
        onchain_count = int(count_hex, 16)
    except ValueError as error:
        raise ValueError("Captured on-chain question count is invalid") from error
    if onchain_count != len(MARKET_IDS):
        raise ValueError("On-chain question count does not match the pinned market set")
    onchain_probe = membership.get("onchain_membership_probe")
    if (
        not isinstance(onchain_probe, dict)
        or onchain_probe.get("adapter_address_source_url")
        != addresses.get("url")
        or str(onchain_probe.get("adapter_address", "")).casefold() != ADAPTER_ADDRESS
        or onchain_probe.get("market_id") != GROUP_ID
        or onchain_probe.get("returned_question_count") != onchain_count
        or onchain_probe.get("block_number") != int(str(block_tag), 16)
        or onchain_probe.get("chain_id_hex") != "0x89"
    ):
        raise ValueError("Membership probe summary does not match the captured on-chain reads")

    raw_markets: list[dict[str, Any]] = []
    for market_id in MARKET_IDS:
        source = responses.get(f"market_{market_id}")
        if (
            source is None
            or source.get("method") != "GET"
            or source.get("url") != f"https://gamma-api.polymarket.com/markets/{market_id}"
        ):
            raise ValueError(f"Missing direct Gamma market response: {market_id}")
        market = json.loads(str(source["body"]))
        if not isinstance(market, dict) or str(market.get("id")) != market_id:
            raise ValueError(f"Direct Gamma response does not identify market {market_id}")
        raw_markets.append(market)

    observed_ids = [str(market.get("id")) for market in raw_markets]
    indices: list[int] = []
    normalized: list[dict[str, Any]] = []
    descriptions: set[str] = set()
    for market in raw_markets:
        question_id = str(market.get("questionID") or "").casefold()
        if len(question_id) != 66 or question_id[:64] != GROUP_ID[:64]:
            raise ValueError("Gamma question IDs do not map to the expected NegRisk group")
        index = int(question_id[-2:], 16)
        indices.append(index)
        if (
            market.get("negRisk") is not True
            or market.get("negRiskAugmented") not in (None, False)
            or market.get("negRiskMarketID") != GROUP_ID
            or market.get("active") is not True
            or market.get("closed") is not False
            or market.get("acceptingOrders") is not True
            or market.get("enableOrderBook") is not True
            or market.get("version") != "v1"
        ):
            raise ValueError(f"Market {market.get('id')} has unsupported NegRisk or lifecycle state")
        outcomes = json.loads(str(market.get("outcomes") or "null"))
        token_ids = json.loads(str(market.get("clobTokenIds") or "null"))
        if (
            not isinstance(outcomes, list)
            or not isinstance(token_ids, list)
            or len(outcomes) != 2
            or len(token_ids) != 2
            or {str(value).casefold() for value in outcomes} != {"yes", "no"}
            or len({str(value) for value in token_ids}) != 2
            or any(not str(value).isdecimal() for value in token_ids)
        ):
            raise ValueError(f"Market {market.get('id')} has invalid outcome tokens")
        tokens = {str(outcome).casefold(): str(token) for outcome, token in zip(outcomes, token_ids, strict=True)}
        schedule = market.get("feeSchedule")
        if (
            market.get("feesEnabled") is not True
            or not isinstance(schedule, dict)
            or schedule.get("takerOnly") is not True
        ):
            raise ValueError(f"Market {market.get('id')} has an unsupported fee regime")
        description = str(market.get("description") or "")
        descriptions.add(description)
        question = str(market.get("question") or "")
        interval = _range_for_question(question)
        condition = str(market.get("conditionId") or "").casefold()
        tick = Decimal(str(market.get("orderPriceMinTickSize")))
        minimum = Decimal(str(market.get("orderMinSize")))
        fee_rate = Decimal(str(schedule.get("rate")))
        fee_exponent = Decimal(str(schedule.get("exponent")))
        if (
            len(condition) != 66
            or not condition.startswith("0x")
            or tick <= ZERO
            or tick > ONE
            or minimum <= ZERO
            or not ZERO <= fee_rate <= ONE
            or fee_exponent <= ZERO
        ):
            raise ValueError(f"Market {market.get('id')} has invalid constraints or identity")
        normalized.append(
            {
                "market_id": str(market["id"]),
                "question_index": index,
                "condition_id": condition,
                "question": question,
                "yes_token_id": tokens["yes"],
                "no_token_id": tokens["no"],
                "tick_size": str(tick),
                "minimum_order_shares": str(minimum),
                "fee_rate": str(fee_rate),
                "fee_exponent": str(fee_exponent),
                "outcome_interval_billions": (
                    {
                        "lower_inclusive": str(interval[0]),
                        "upper_exclusive": str(interval[1]) if interval[1] is not None else None,
                    }
                    if interval is not None
                    else None
                ),
            }
        )

    if (
        observed_ids != list(MARKET_IDS)
        or indices != list(range(len(MARKET_IDS)))
        or onchain_count != len(raw_markets)
    ):
        raise ValueError("Direct Gamma market IDs and sequential indices do not match on-chain count")
    normalized.sort(key=lambda row: row["question_index"])
    descriptions_folded = {description.casefold() for description in descriptions}
    if (
        len(descriptions_folded) != 1
        or "no ipo occurs by december 31, 2026" not in next(iter(descriptions_folded))
        or "exactly between two brackets" not in next(iter(descriptions_folded))
        or "higher range bracket" not in next(iter(descriptions_folded))
    ):
        raise ValueError("Shared event description does not establish deadline and boundary handling")
    ranges = sorted(
        (Decimal(row["outcome_interval_billions"]["lower_inclusive"]),
         Decimal(row["outcome_interval_billions"]["upper_exclusive"])
         if row["outcome_interval_billions"]["upper_exclusive"] is not None else None)
        for row in normalized
        if row["outcome_interval_billions"] is not None
    )
    if (
        sum(row["outcome_interval_billions"] is None for row in normalized) != 1
        or not ranges
        or ranges[0][0] != ZERO
        or ranges[-1][1] is not None
        or any(left[1] != right[0] for left, right in zip(ranges, ranges[1:], strict=False))
    ):
        raise ValueError("Market-cap outcomes have a gap or overlap, or the No-IPO outcome is missing")

    probe_markets = membership.get("markets")
    if not isinstance(probe_markets, list) or len(probe_markets) != len(raw_markets):
        raise ValueError("Membership probe market rows do not match direct source responses")
    probe_by_id = {str(row.get("market_id")): row for row in probe_markets if isinstance(row, dict)}
    for raw, row in zip(raw_markets, normalized, strict=True):
        probe = probe_by_id.get(row["market_id"])
        if (
            probe is None
            or probe.get("question_index") != row["question_index"]
            or probe.get("condition_id") != row["condition_id"]
            or probe.get("neg_risk_market_id") != GROUP_ID
            or json.loads(str(probe.get("token_ids")))
            != [row["yes_token_id"], row["no_token_id"]]
            or str(raw.get("question")) != row["question"]
        ):
            raise ValueError("Membership summary does not match its direct Gamma market source")

    filter_probe = membership.get("gamma_membership_probe")
    filter_response = responses.get("neg_risk_group_filter")
    if (
        not isinstance(filter_probe, dict)
        or filter_response is None
        or filter_response.get("method") != "GET"
        or filter_response.get("url") != filter_probe.get("filter_request_url")
    ):
        raise ValueError("Missing Gamma group-filter comparison evidence")
    filtered = json.loads(str(filter_response["body"]))
    if not isinstance(filtered, list):
        raise ValueError("Captured Gamma group-filter result is malformed")
    filter_matches = [row for row in filtered if isinstance(row, dict) and row.get("negRiskMarketID") == GROUP_ID]
    if len(filtered) != 20 or filter_matches:
        raise ValueError("Captured Gamma group-filter result no longer reproduces the mismatch")
    if (
        filter_probe.get("direct_market_count") != len(raw_markets)
        or filter_probe.get("direct_market_ids") != observed_ids
        or filter_probe.get("direct_group_id_matches") != len(raw_markets)
        or filter_probe.get("direct_market_question_indices") != indices
        or filter_probe.get("unique_indices") != len(set(indices))
        or filter_probe.get("all_direct_markets_same_group") is not True
        or filter_probe.get("filter_response_count") != len(filtered)
        or filter_probe.get("filter_matching_market_ids") != []
        or filter_probe.get("filter_matches_group") != len(filter_matches)
    ):
        raise ValueError("Gamma membership probe summary does not match captured source responses")

    return normalized, {
        "group_id": GROUP_ID,
        "market_count": len(normalized),
        "question_indices": indices,
        "onchain_question_count": onchain_count,
        "onchain_block_number": int(str(block_tag), 16),
        "gamma_filter_returned_records": len(filtered),
        "gamma_filter_group_matches": len(filter_matches),
        "exact_boundary_goes_to_higher_bracket": True,
        "numeric_ranges_billions": [row["outcome_interval_billions"] for row in normalized],
        "no_ipo_outcome_count": sum(
            row["outcome_interval_billions"] is None for row in normalized
        ),
    }


def _analyze_baskets(
    markets: list[dict[str, Any]],
    books: list[dict[str, Any]],
    *,
    captured_ns: int,
    batch_started_ns: int,
) -> dict[str, Any]:
    expected_tokens = {
        token
        for market in markets
        for token in (market["yes_token_id"], market["no_token_id"])
    }
    observed = [str(book.get("asset_id")) for book in books]
    complete = len(observed) == len(expected_tokens) and set(observed) == expected_tokens
    by_asset: dict[str, list[dict[str, Any]]] = {}
    for book in books:
        by_asset.setdefault(str(book.get("asset_id")), []).append(book)
    result: dict[str, Any] = {
        "complete_14_token_response": complete,
        "yes_basket": None,
        "no_basket": None,
        "protocol_payout_assumptions": {
            "yes_basket": "one payout share per complete set, conditional on exactly one Yes outcome",
            "no_basket": "at least six payout shares per complete set if at most one of seven outcomes resolves Yes",
        },
        "actual_fills": "unknown_counterfactual",
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    for side in ("yes", "no"):
        token_field = f"{side}_token_id"
        selected = [
            book
            for market in markets
            for book in by_asset.get(market[token_field], [])
        ]
        payout = ONE if side == "yes" else Decimal(len(markets) - 1)
        audited = audit_books(
            markets,
            selected,
            captured_ns=captured_ns,
            batch_started_ns=batch_started_ns,
            include_stale_quotes_for_descriptive_math=True,
            side=side,
            payout_shares_per_set=payout,
            payoff_description=result["protocol_payout_assumptions"][f"{side}_basket"],
        )
        if not complete:
            issues = set(audited["quality"]["issues"])
            issues.add("combined_book_asset_set_does_not_match_complete_group")
            audited["quality"]["issues"] = sorted(issues)
            audited["quality"]["valid"] = False
            for scenario in audited["quantity_scenarios"]:
                scenario["quality_valid"] = False
                scenario["positive_full_depth_gross"] = False
                scenario["positive_fragmentation_safe_after_fee"] = False
            audited["top_of_book"]["positive_gross"] = False
        result[f"{side}_basket"] = audited
    return result


def _make_artifact(
    membership_bytes: bytes,
    archive_bytes: bytes,
    capture: dict[str, Any],
    books_body: bytes,
    books: list[dict[str, Any]],
) -> dict[str, Any]:
    membership = json.loads(membership_bytes)
    source_archive = json.loads(archive_bytes)
    if not isinstance(membership, dict) or not isinstance(source_archive, dict):
        raise ValueError("Membership evidence payload is not an object")
    markets, structure = _verify_membership(membership, source_archive)
    token_ids = [
        token
        for market in markets
        for token in (market["yes_token_id"], market["no_token_id"])
    ]
    request_body = _canonical([{"token_id": token} for token in token_ids])
    if capture.get("request_asset_ids") != token_ids or capture.get("request_sha256") != _sha256(
        request_body
    ):
        raise ValueError("CLOB capture request does not match the complete verified token set")
    if (
        capture.get("url") != BOOKS_URL
        or capture.get("method") != "POST"
        or capture.get("status_code") != 200
        or capture.get("request_bytes") != len(request_body)
        or capture.get("response_bytes") != len(books_body)
        or capture.get("response_sha256") != _sha256(books_body)
    ):
        raise ValueError("CLOB capture metadata does not match its response payload")
    if json.loads(books_body) != books:
        raise ValueError("CLOB response payload does not match parsed books")
    result = _analyze_baskets(
        markets,
        books,
        captured_ns=int(capture["received_ns"]),
        batch_started_ns=int(capture["started_ns"]),
    )
    evidence = {
        "membership_probe_path": MEMBERSHIP_PATH.relative_to(REPOSITORY).as_posix(),
        "membership_probe_sha256": _sha256(membership_bytes),
        "membership_probe_payload": membership_bytes.decode("utf-8"),
        "source_archive_path": SOURCE_ARCHIVE_PATH.relative_to(REPOSITORY).as_posix(),
        "source_archive_sha256": _sha256(archive_bytes),
        "source_archive_payload": archive_bytes.decode("utf-8"),
    }
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "study_id": f"VERITAS-M2-OPENAI-IPO-BASKET-{capture['received_at_utc']}",
        "created_at_utc": capture["received_at_utc"],
        "scope": {
            "event": "OpenAI market cap at close on IPO day, with a No-IPO outcome through 2026-12-31",
            "group_id": GROUP_ID,
            "market_count": len(markets),
            "book_request_asset_count": len(token_ids),
            "maximum_response_bytes": MAX_RESPONSE_BYTES,
            "request_asset_ids": token_ids,
            "orders_submitted": False,
            "authenticated_requests": False,
        },
        "membership_evidence": evidence,
        "verified_structure": structure,
        "normalized_markets": markets,
        "books_request": {
            **capture,
            "request_bytes": len(request_body),
            "request_sha256": _sha256(request_body),
            "request_body": request_body.decode("utf-8"),
        },
        "books_response_payload": books_body.decode("utf-8"),
        "result": result,
    }
    artifact["result_sha256"] = _sha256(_canonical(result))
    artifact["artifact_sha256"] = _sha256(_canonical(artifact))
    return artifact


def _load_capture_metadata(path: Path) -> tuple[dict[str, Any], bytes, list[dict[str, Any]]]:
    if path.is_symlink():
        raise ValueError("Capture metadata must not be a symbolic link")
    metadata = json.loads(path.read_text())
    if not isinstance(metadata, dict):
        raise ValueError("Capture metadata is not an object")
    response_path = Path(str(metadata.get("response_path") or ""))
    if not response_path.is_absolute():
        response_path = REPOSITORY / response_path
    response_path = response_path.resolve()
    if not response_path.is_relative_to(STUDY_ROOT.resolve()) or not response_path.is_file():
        raise ValueError("Captured CLOB body must be a regular file under the study root")
    body = response_path.read_bytes()
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Captured CLOB response exceeds its 2,000,000-byte bound")
    books = json.loads(body)
    if not isinstance(books, list) or any(not isinstance(row, dict) for row in books):
        raise ValueError("Captured CLOB payload is not a list of books")
    capture = {key: value for key, value in metadata.items() if key != "response_path"}
    return capture, body, books


def _capture_public(markets: list[dict[str, Any]]) -> tuple[dict[str, Any], bytes, list[dict[str, Any]]]:
    token_ids = [
        token
        for market in markets
        for token in (market["yes_token_id"], market["no_token_id"])
    ]
    request_body = _canonical([{"token_id": token} for token in token_ids])
    books, response_body, metadata = _read_public_books(request_body)
    capture = {
        **metadata,
        "request_asset_ids": token_ids,
        "request_bytes": len(request_body),
        "request_sha256": _sha256(request_body),
    }
    return capture, response_body, books


def fetch_study() -> dict[str, Any]:
    membership_bytes = MEMBERSHIP_PATH.read_bytes()
    archive_bytes = SOURCE_ARCHIVE_PATH.read_bytes()
    membership = json.loads(membership_bytes)
    markets, _ = _verify_membership(membership, json.loads(archive_bytes))
    capture, books_body, books = _capture_public(markets)
    artifact = _make_artifact(membership_bytes, archive_bytes, capture, books_body, books)
    STUDY_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = STUDY_ROOT / f"{capture['received_ns']}-openai-ipo-basket-study.json"
    if path.exists():
        raise FileExistsError("Refusing to replace an existing OpenAI IPO basket study")
    atomic_json(path, artifact)
    return _summary(path, artifact)


def build_from_capture(metadata_path: Path) -> dict[str, Any]:
    membership_bytes = MEMBERSHIP_PATH.read_bytes()
    archive_bytes = SOURCE_ARCHIVE_PATH.read_bytes()
    capture, books_body, books = _load_capture_metadata(metadata_path.expanduser())
    artifact = _make_artifact(membership_bytes, archive_bytes, capture, books_body, books)
    STUDY_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = STUDY_ROOT / f"{capture['received_ns']}-openai-ipo-basket-study.json"
    if path.exists():
        raise FileExistsError("Refusing to replace an existing OpenAI IPO basket study")
    atomic_json(path, artifact)
    return _summary(path, artifact)


def _summary(path: Path, artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_path": path.relative_to(REPOSITORY).as_posix(),
        "artifact_sha256": artifact["artifact_sha256"],
        "result_sha256": artifact["result_sha256"],
        "verified_structure": artifact["verified_structure"],
        "result": artifact["result"],
    }


def replay_study(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("Replay artifact must not be a symbolic link")
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(STUDY_ROOT.resolve()) or not resolved.is_file():
        raise ValueError("Replay artifact must be a regular file under the study root")
    if resolved.stat().st_size > MAX_RESPONSE_BYTES:
        raise ValueError("Stored study exceeds its 2,000,000-byte evidence bound")
    artifact = json.loads(resolved.read_text())
    if not isinstance(artifact, dict) or artifact.get("analysis_version") != ANALYSIS_VERSION:
        raise ValueError("Unsupported OpenAI IPO basket study artifact")
    sealed = dict(artifact)
    claimed_artifact_sha = sealed.pop("artifact_sha256", None)
    if claimed_artifact_sha != _sha256(_canonical(sealed)):
        raise ValueError("Stored study artifact digest does not match")
    evidence = artifact.get("membership_evidence")
    request = artifact.get("books_request")
    if not isinstance(evidence, dict) or not isinstance(request, dict):
        raise ValueError("Stored study evidence is incomplete")
    membership_bytes = str(evidence.get("membership_probe_payload") or "").encode()
    archive_bytes = str(evidence.get("source_archive_payload") or "").encode()
    if (
        _sha256(membership_bytes) != evidence.get("membership_probe_sha256")
        or _sha256(archive_bytes) != evidence.get("source_archive_sha256")
    ):
        raise ValueError("Stored membership source evidence digest does not match")
    membership = json.loads(membership_bytes)
    source_archive = json.loads(archive_bytes)
    markets, structure = _verify_membership(membership, source_archive)
    if structure != artifact.get("verified_structure") or markets != artifact.get("normalized_markets"):
        raise ValueError("Replayed group structure differs from the stored study")
    books_body = str(artifact.get("books_response_payload") or "").encode()
    if (
        len(books_body) > MAX_RESPONSE_BYTES
        or _sha256(books_body) != request.get("response_sha256")
        or len(books_body) != request.get("response_bytes")
    ):
        raise ValueError("Stored CLOB response digest or bound does not match")
    books = json.loads(books_body)
    if not isinstance(books, list) or any(not isinstance(row, dict) for row in books):
        raise ValueError("Stored CLOB response is malformed")
    expected_request = _canonical(
        [{"token_id": token} for token in artifact["scope"]["request_asset_ids"]]
    )
    expected_tokens = [
        token
        for market in markets
        for token in (market["yes_token_id"], market["no_token_id"])
    ]
    if (
        request.get("url") != BOOKS_URL
        or request.get("method") != "POST"
        or request.get("status_code") != 200
        or artifact["scope"].get("request_asset_ids") != expected_tokens
        or request.get("request_asset_ids") != expected_tokens
        or request.get("request_body") != expected_request.decode()
        or request.get("request_sha256") != _sha256(expected_request)
        or request.get("request_bytes") != len(expected_request)
    ):
        raise ValueError("Stored CLOB request metadata does not match the verified token set")
    result = _analyze_baskets(
        markets,
        books,
        captured_ns=int(request["received_ns"]),
        batch_started_ns=int(request["started_ns"]),
    )
    result_sha = _sha256(_canonical(result))
    if result_sha != artifact.get("result_sha256") or result != artifact.get("result"):
        raise ValueError("Replayed basket calculations differ from the stored study")
    return {
        "artifact_path": resolved.relative_to(REPOSITORY).as_posix(),
        "artifact_sha256": claimed_artifact_sha,
        "result_sha256": result_sha,
        "verified_structure": structure,
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--fetch-public", action="store_true", help="Fetch one bounded CLOB books response"
    )
    source.add_argument(
        "--capture-metadata",
        type=Path,
        help="Build a sealed study from a previously captured response and metadata",
    )
    source.add_argument("--replay", type=Path, help="Replay a sealed study artifact")
    args = parser.parse_args()
    if args.fetch_public:
        result = fetch_study()
    elif args.capture_metadata:
        result = build_from_capture(args.capture_metadata)
    else:
        result = replay_study(args.replay)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
