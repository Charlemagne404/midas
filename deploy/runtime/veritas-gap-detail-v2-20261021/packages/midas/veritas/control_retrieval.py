"""One-request direct lookup for a frozen Veritas control cohort.

This diagnostic is separate from the scheduled v1 pilot. It asks Gamma for a
small, fixed list of market IDs including closed markets, then reports which
rows were returned and whether their current metadata passes the existing V1
market admission checks. A missing row is not evidence that a market is
closed or absent from the venue.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .observatory import PublicReadClient
from .opportunity_audit import normalize_market

CONTROL_RETRIEVAL_VERSION = "veritas-control-retrieval-probe-v1"
MAX_CONTROL_IDS = 8


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _id_hash(market_id: str) -> str:
    return _sha256(market_id.encode("utf-8"))


def _validate_control_ids(control_ids: list[str]) -> list[str]:
    ids = [str(value) for value in control_ids]
    if (
        not ids
        or len(ids) > MAX_CONTROL_IDS
        or len(ids) != len(set(ids))
        or any(not value.isdecimal() for value in ids)
    ):
        raise ValueError("Control retrieval accepts 1..8 unique decimal market IDs")
    return ids


def summarize_control_rows(
    control_ids: list[str], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Classify returned control metadata without copying identifiers onward."""
    ids = _validate_control_ids(control_ids)
    returned: dict[str, list[dict[str, Any]]] = {market_id: [] for market_id in ids}
    unexpected: set[str] = set()
    for row in rows:
        raw_id = row.get("id")
        if raw_id is None:
            continue
        market_id = str(raw_id)
        if market_id in returned:
            returned[market_id].append(row)
        else:
            unexpected.add(market_id)

    outcomes: list[dict[str, Any]] = []
    for market_id in ids:
        matches = returned[market_id]
        outcome: dict[str, Any] = {
            "market_id_sha256": _id_hash(market_id),
            "response_rows": len(matches),
        }
        if not matches:
            outcome["classification"] = "not_returned_by_direct_id_query"
        elif len(matches) > 1:
            outcome["classification"] = "duplicate_id_in_response"
            outcome["returned_metadata_sha256"] = [_sha256(_canonical(row)) for row in matches]
        else:
            row = matches[0]
            normalized, reason = normalize_market(row)
            outcome["returned_metadata_sha256"] = _sha256(_canonical(row))
            if normalized is not None:
                outcome["classification"] = "eligible_current_market_metadata"
            else:
                outcome["classification"] = "returned_but_ineligible"
                outcome["ineligibility_reason"] = reason or "unknown_exclusion"
        outcomes.append(outcome)

    # Unexpected rows are summarized by count and digest, never copied into
    # per-control results. The retained source payload remains the audit trail.
    if unexpected:
        outcomes.append(
            {
                "classification": "unexpected_market_ids_returned",
                "count": len(unexpected),
                "market_ids_set_sha256": _sha256(_canonical(sorted(unexpected))),
            }
        )
    return outcomes


async def retrieve_control_metadata(
    client: PublicReadClient, control_ids: list[str]
) -> dict[str, Any]:
    """Use exactly one bounded Gamma read to retrieve a frozen control cohort."""
    ids = _validate_control_ids(control_ids)
    rows, receipt = await client.discover({"id": ids, "closed": "any"})
    return {
        "version": CONTROL_RETRIEVAL_VERSION,
        "query": {
            "closed": "any",
            "requested_market_count": len(ids),
            "requested_market_ids_set_sha256": _sha256(_canonical(sorted(ids))),
        },
        "response": {
            "returned_market_count": len(rows),
            "outcomes": summarize_control_rows(ids, rows),
            "request_receipt": receipt,
        },
        "orders_submitted": False,
        "authenticated_requests": False,
    }
