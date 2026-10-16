"""Run or replay a bounded read-only study of a verified NegRisk outcome set."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from midas.arena.artifacts import atomic_json
from midas.veritas.neg_risk_set_audit import EVENT_ID, audit_books, verify_event

REPOSITORY = Path(__file__).resolve().parents[1]
DATA_ROOT = REPOSITORY / "data" / "veritas-observatory"
STUDY_ROOT = DATA_ROOT / "structure-studies"
EVENT_URL = f"https://gamma-api.polymarket.com/events/{EVENT_ID}"
BOOKS_URL = "https://clob.polymarket.com/books"
MAX_RESPONSE_BYTES = 2_000_000
MAX_GROUP_MARKETS = 16
REQUEST_SPACING_SECONDS = 1.0
USER_AGENT = "MIDAS-Veritas-readonly-structure-study/1.0"
LEGACY_ANALYSIS_VERSION_V1 = "veritas-neg-risk-complete-yes-set-study-v1"
LEGACY_ANALYSIS_VERSION_V2 = "veritas-neg-risk-complete-yes-set-study-v2"
ANALYSIS_VERSION = "veritas-neg-risk-complete-outcome-basket-study-v3"


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


def _read_public_json(
    url: str, *, method: str, body: bytes | None = None
) -> tuple[Any, bytes, dict[str, Any]]:
    if url not in {EVENT_URL, BOOKS_URL} or method not in {"GET", "POST"}:
        raise ValueError("Public study request is outside its fixed endpoint allowlist")
    if (url == EVENT_URL and (method != "GET" or body is not None)) or (
        url == BOOKS_URL and (method != "POST" or body is None)
    ):
        raise ValueError("Public study method or request body is invalid")
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    started_ns = time.time_ns()
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(_NoRedirectHandler())
    with opener.open(request, timeout=15) as response:
        response_body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise ValueError("Public study response exceeded its 2,000,000-byte bound")
        status_code = response.status
        server_date = response.headers.get("Date")
    received_ns = time.time_ns()
    if status_code != 200:
        raise ValueError(f"Public study endpoint returned HTTP {status_code}")
    value = json.loads(response_body)
    return (
        value,
        response_body,
        {
            "url": url,
            "method": method,
            "started_at_utc": _time_text(started_ns),
            "received_at_utc": _time_text(received_ns),
            "started_ns": started_ns,
            "received_ns": received_ns,
            "duration_ms": (received_ns - started_ns) // 1_000_000,
            "http_date": server_date,
            "status_code": status_code,
            "response_bytes": len(response_body),
            "response_sha256": _sha256(response_body),
        },
    )


def _analyze_event_books(
    markets: list[dict[str, Any]],
    books: list[dict[str, Any]],
    *,
    captured_ns: int,
    batch_started_ns: int,
) -> dict[str, Any]:
    expected_assets = {
        token_id
        for market in markets
        for token_id in (market["yes_token_id"], market["no_token_id"])
    }
    if len(expected_assets) != len(markets) * 2:
        raise ValueError("Verified event has duplicate outcome token IDs")
    books_by_asset: dict[str, list[dict[str, Any]]] = {}
    for book in books:
        books_by_asset.setdefault(str(book.get("asset_id")), []).append(book)
    yes_books = [
        book for market in markets for book in books_by_asset.get(market["yes_token_id"], [])
    ]
    no_books = [
        book for market in markets for book in books_by_asset.get(market["no_token_id"], [])
    ]
    yes = audit_books(
        markets,
        yes_books,
        captured_ns=captured_ns,
        batch_started_ns=batch_started_ns,
        include_stale_quotes_for_descriptive_math=True,
    )
    minimum_no_payout = Decimal(len(markets) - 1)
    no = audit_books(
        markets,
        no_books,
        captured_ns=captured_ns,
        batch_started_ns=batch_started_ns,
        include_stale_quotes_for_descriptive_math=True,
        side="no",
        payout_shares_per_set=minimum_no_payout,
        payoff_description=(
            f"At least {minimum_no_payout} payout shares per complete No basket under "
            "the protocol rule that at most one outcome can resolve Yes"
        ),
    )
    expected_asset_set_valid = (
        len(books) == len(expected_assets)
        and {str(book.get("asset_id")) for book in books} == expected_assets
    )
    if not expected_asset_set_valid:
        for result in (yes, no):
            issues = set(result["quality"]["issues"])
            issues.add("combined_book_asset_set_does_not_match_complete_event")
            result["quality"]["issues"] = sorted(issues)
            result["quality"]["valid"] = False
            for scenario in result["quantity_scenarios"]:
                scenario["quality_valid"] = False
                scenario["positive_full_depth_gross"] = False
                scenario["positive_fragmentation_safe_after_fee"] = False
            result["top_of_book"]["positive_gross"] = False
    return {
        "event_structure_verified": True,
        "protocol_enforces_at_most_one_yes_but_not_all_no_exclusion": True,
        "yes_basket": yes,
        "no_basket": no,
        "actual_fills": "unknown_counterfactual",
        "orders_submitted": False,
        "authenticated_requests": False,
    }


def fetch_study() -> dict[str, Any]:
    event, event_body, event_request = _read_public_json(EVENT_URL, method="GET")
    if not isinstance(event, dict):
        raise ValueError("Gamma event response is not an object")
    markets = verify_event(event)
    if len(markets) > MAX_GROUP_MARKETS:
        raise ValueError("Verified outcome set exceeds the book-request bound")
    token_ids = [
        token_id
        for market in markets
        for token_id in (market["yes_token_id"], market["no_token_id"])
    ]
    if len(set(token_ids)) != len(token_ids):
        raise ValueError("Verified outcome set has duplicate Yes token IDs")
    time.sleep(REQUEST_SPACING_SECONDS)
    request_body = _canonical([{"token_id": token_id} for token_id in token_ids])
    books, books_body, books_request = _read_public_json(
        BOOKS_URL, method="POST", body=request_body
    )
    if not isinstance(books, list) or len(books) > len(token_ids):
        raise ValueError("CLOB book response is not a bounded list")
    if any(not isinstance(book, dict) for book in books):
        raise ValueError("CLOB book response contains a non-object")
    result = _analyze_event_books(
        markets,
        books,
        captured_ns=books_request["received_ns"],
        batch_started_ns=books_request["started_ns"],
    )
    artifact: dict[str, Any] = {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "study_id": f"VERITAS-M2-NEG-RISK-SET-{event_request['received_at_utc']}",
        "created_at_utc": books_request["received_at_utc"],
        "scope": {
            "event_id": EVENT_ID,
            "event_slug": event["slug"],
            "market_count": len(markets),
            "book_request_asset_count": len(token_ids),
            "book_request_outcome_sides": ["yes", "no"],
            "request_spacing_seconds": REQUEST_SPACING_SECONDS,
            "maximum_response_bytes": MAX_RESPONSE_BYTES,
            "orders_submitted": False,
            "authenticated_requests": False,
        },
        "event_request": event_request,
        "event_response_payload": event_body.decode("utf-8"),
        "books_request": {
            **books_request,
            "request_asset_ids": token_ids,
            "request_sha256": _sha256(request_body),
            "request_bytes": len(request_body),
        },
        "books_response_payload": books_body.decode("utf-8"),
        "result": result,
    }
    artifact["result_sha256"] = _sha256(_canonical(result))
    artifact["artifact_sha256"] = _sha256(_canonical(artifact))
    STUDY_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    filename_stamp = str(books_request["received_ns"])
    artifact_path = STUDY_ROOT / f"{filename_stamp}-event-{EVENT_ID}.json"
    if artifact_path.exists():
        raise FileExistsError("Refusing to replace an existing NegRisk study artifact")
    atomic_json(artifact_path, artifact)
    return {"artifact_path": artifact_path.relative_to(REPOSITORY).as_posix(), **result}


def replay_study(path: Path) -> dict[str, Any]:
    path = path.expanduser()
    study_root = STUDY_ROOT.resolve()
    if path.is_symlink():
        raise ValueError("Replay artifact must not be a symbolic link")
    path = path.resolve()
    if not path.is_relative_to(study_root) or not path.is_file():
        raise ValueError("Replay artifact must be a regular file under the Veritas study root")
    if path.stat().st_size > 2 * MAX_RESPONSE_BYTES + 256 * 1024:
        raise ValueError("Replay artifact exceeds its stored evidence bound")
    artifact = json.loads(path.read_text())
    supported_versions = {
        ANALYSIS_VERSION,
        LEGACY_ANALYSIS_VERSION_V1,
        LEGACY_ANALYSIS_VERSION_V2,
    }
    if not isinstance(artifact, dict) or artifact.get("analysis_version") not in supported_versions:
        raise ValueError("Unsupported NegRisk study artifact")
    claimed_artifact_sha = artifact.get("artifact_sha256")
    sealed = dict(artifact)
    sealed.pop("artifact_sha256", None)
    if claimed_artifact_sha != _sha256(_canonical(sealed)):
        raise ValueError("Stored NegRisk study artifact digest does not match")
    event_body = str(artifact.get("event_response_payload") or "").encode()
    books_body = str(artifact.get("books_response_payload") or "").encode()
    if _sha256(event_body) != artifact.get("event_request", {}).get("response_sha256"):
        raise ValueError("Stored event response digest does not match")
    if _sha256(books_body) != artifact.get("books_request", {}).get("response_sha256"):
        raise ValueError("Stored CLOB response digest does not match")
    event = json.loads(event_body)
    books = json.loads(books_body)
    if not isinstance(event, dict) or not isinstance(books, list):
        raise ValueError("Stored source responses are malformed")
    markets = verify_event(event)
    captured_ns = int(artifact["books_request"]["received_ns"])
    batch_started_ns = int(artifact["books_request"]["started_ns"])
    version = artifact["analysis_version"]
    if version in {LEGACY_ANALYSIS_VERSION_V1, LEGACY_ANALYSIS_VERSION_V2}:
        result = audit_books(
            markets,
            books,
            captured_ns=captured_ns,
            batch_started_ns=batch_started_ns,
            include_stale_quotes_for_descriptive_math=version == LEGACY_ANALYSIS_VERSION_V2,
        )
    else:
        result = _analyze_event_books(
            markets,
            books,
            captured_ns=captured_ns,
            batch_started_ns=batch_started_ns,
        )
    result_sha = _sha256(_canonical(result))
    if result_sha != artifact.get("result_sha256") or result != artifact.get("result"):
        raise ValueError("Replayed outcome-set result differs from the stored study")
    return {
        "artifact_path": path.relative_to(REPOSITORY).as_posix(),
        "result_sha256": result_sha,
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--fetch-public", action="store_true", help="Read one Gamma event and one CLOB books batch"
    )
    source.add_argument(
        "--replay", type=Path, help="Recompute an existing study from stored responses"
    )
    args = parser.parse_args()
    result = fetch_study() if args.fetch_public else replay_study(args.replay)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
