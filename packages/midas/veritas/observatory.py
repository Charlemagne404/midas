"""Bounded stratified public market discovery and snapshot observation pilot.

The Gamma query union is an explicit bounded frame, not the full venue. Each
run stores a finalized, hashed snapshot; periodic snapshots are not continuous
coverage. The only CLOB write method is the unauthenticated public `/books`
read endpoint. No credential, order, wallet, or trading endpoint is used.
"""

from __future__ import annotations

import asyncio
import fcntl
import gzip
import hashlib
import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from .continuous_analysis import update_finalized_analysis
from .opportunity_audit_v2 import audit_pair_snapshot, normalize_market
from .scan_catalog import reconcile as reconcile_snapshot_catalog
from .scan_catalog import record_snapshot as record_catalog_snapshot

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
VERSION = "veritas-public-observatory-v2"
DISCOVERY_FRAME_PROTOCOL = "stratified-gamma-page-rotation-v3-reference-sample"
CONTROL_COHORT_VERSION = "veritas-control-cohort-v1"
LEGACY_CONTROL_COHORT_VERSION = "veritas-public-observatory-v1"
DISCOVERY_LIMIT = 50
DISCOVERY_QUERIES = 6
DISCOVERY_OFFSET_RANGE = 1_000
DISCOVERY_OFFSET_BUCKET_SECONDS = 30 * 60
DISCOVERY_OFFSET_BUCKET_NS = DISCOVERY_OFFSET_BUCKET_SECONDS * 1_000_000_000
MAX_RESPONSE_BYTES = 48 * 1024**2
MAX_REQUESTS_PER_SCAN = DISCOVERY_QUERIES + 2
MAX_RETRIES_PER_PUBLIC_READ = 1
MAX_PUBLIC_HTTP_ATTEMPTS_PER_SCAN = MAX_REQUESTS_PER_SCAN * (MAX_RETRIES_PER_PUBLIC_READ + 1)
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_MARKETS = 50
DEFAULT_MARKETS = 40
DEFAULT_CONTROL_MARKETS = 8
DEFAULT_REFERENCE_MARKETS = 8
DEFAULT_QUANTITIES = ("5", "10", "20", "50", "100")
MAX_ROOT_BYTES = 1024**3
MAX_STATE_BYTES = 8 * 1024**2
MAX_ANALYSIS_RESERVE_BYTES = 16 * 1024**2
MAX_LATEST_SUMMARY_BYTES = 512 * 1024
MAX_ACTIVITY_MARKETS = 2_000
DEFAULT_INTERVAL_SECONDS = 30 * 60
REQUEST_INTERVAL_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 5.0
REPORTED_UPDATE_AGE_DIAGNOSTIC_THRESHOLD_MS = 5_000
REPORTED_UPDATE_SKEW_DIAGNOSTIC_THRESHOLD_MS = 250
DEFAULT_SEED = 20261015
PHASES = ("liquidity", "expiry", "category", "spread", "snapshot_change")


class CumulativeResponseBudgetExceeded(ValueError):
    """A fatal per-scan response budget breach that must stop further reads."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: Any, *, maximum: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    data = _canonical(value)
    if maximum is not None and (maximum < 1 or len(data) > maximum):
        temporary.unlink(missing_ok=True)
        raise ValueError(f"JSON publication exceeds the {maximum}-byte bound")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _safe_json(path: Path, *, max_bytes: int) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError(f"Unsafe or oversized observatory state: {path.name}")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid observatory state: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Invalid observatory object: {path.name}")
    return value


def _number(value: Any) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _timestamp_ns(value: Any) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return int(parsed.timestamp() * 1_000_000_000)


def _category_labels(value: Any) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [item for item in value if isinstance(item, str)]
    elif isinstance(value, dict):
        label = value.get("label")
        candidates = [label] if isinstance(label, str) else []
    else:
        candidates = []
    return list(dict.fromkeys(label.strip()[:100] for label in candidates if label.strip()))


def _category_metadata(raw: dict[str, Any]) -> tuple[list[str], str, str]:
    market_categories = _category_labels(raw.get("category"))
    event_categories: list[str] = []
    tag_categories: list[str] = []
    tags = raw.get("tags", [])
    if isinstance(tags, list):
        tag_categories.extend(
            label
            for item in tags
            if isinstance(item, dict)
            for label in _category_labels(item.get("label"))
        )
    events = raw.get("events", [])
    if isinstance(events, list):
        for item in events:
            if not isinstance(item, dict):
                continue
            event_categories.extend(_category_labels(item.get("category")))
            event_tags = item.get("tags", [])
            if isinstance(event_tags, list):
                tag_categories.extend(
                    label
                    for tag in event_tags
                    if isinstance(tag, dict)
                    for label in _category_labels(tag.get("label"))
                )
    all_categories = sorted(set(market_categories) | set(event_categories) | set(tag_categories))
    if market_categories:
        return all_categories, market_categories[0], "market.category"
    if event_categories:
        return all_categories, event_categories[0], "event.category"
    if tag_categories:
        return all_categories, sorted(set(tag_categories))[0], "tag.label"
    return all_categories, "unknown", "unavailable"


def _categories(raw: dict[str, Any]) -> list[str]:
    return _category_metadata(raw)[0]


def _enrich_candidate(
    raw: dict[str, Any], normalized: dict[str, Any], query_ids: list[str]
) -> dict[str, Any]:
    best_bid = _number(raw.get("bestBid"))
    best_ask = _number(raw.get("bestAsk"))
    spread = _number(raw.get("spread"))
    if spread is None and best_bid is not None and best_ask is not None and best_ask >= best_bid:
        spread = best_ask - best_bid
    categories, primary_category, primary_category_source = _category_metadata(raw)
    liquidity = _number(raw.get("liquidityNum", raw.get("liquidity")))
    volume_24h = _number(raw.get("volume24hr"))
    end_ns = _timestamp_ns(raw.get("endDate"))
    payload_hash = _sha256(_canonical(raw))
    remaining = end_ns - time.time_ns() if end_ns is not None else None
    expiry_band = (
        "unknown"
        if remaining is None
        else "near_7d"
        if remaining <= 7 * 86_400_000_000_000
        else "medium_90d"
        if remaining <= 90 * 86_400_000_000_000
        else "long"
    )
    return {
        **normalized,
        "question": str(raw.get("question") or "")[:500],
        "slug": str(raw.get("slug") or "")[:250],
        "categories": categories,
        "primary_category": primary_category,
        "primary_category_source": primary_category_source,
        "liquidity_usdc": str(liquidity) if liquidity is not None else None,
        "liquidity_band": (
            "unknown"
            if liquidity is None
            else "high"
            if liquidity >= 10_000
            else "medium"
            if liquidity >= 1_000
            else "low"
            if liquidity > 0
            else "zero"
        ),
        "volume_24h_usdc": str(volume_24h) if volume_24h is not None else None,
        "end_ns": end_ns,
        "expiry_band": expiry_band,
        "spread_per_share": str(spread) if spread is not None else None,
        "spread_band": (
            "unknown"
            if spread is None
            else "tight_le_0.01"
            if spread <= 0.01
            else "medium_le_0.05"
            if spread <= 0.05
            else "wide_gt_0.05"
        ),
        "best_bid_metadata": str(best_bid) if best_bid is not None else None,
        "best_ask_metadata": str(best_ask) if best_ask is not None else None,
        "event_ids": sorted(
            {
                str(event["id"])
                for event in raw.get("events", [])
                if isinstance(event, dict) and event.get("id") is not None
            }
        )
        if isinstance(raw.get("events", []), list)
        else [],
        "discovered_by": sorted(set(query_ids)),
        "raw_market_metadata_sha256": payload_hash,
    }


def _query_plan(now_ns: int, seed: int) -> list[tuple[str, dict[str, Any]]]:
    now = datetime.fromtimestamp(now_ns / 1_000_000_000, UTC)
    common: dict[str, Any] = {
        "active": "true",
        "closed": "false",
        "limit": DISCOVERY_LIMIT,
        "include_tag": "true",
    }
    half_hour_bucket = now_ns // DISCOVERY_OFFSET_BUCKET_NS
    base_offset = (seed + half_hour_bucket * 137) % DISCOVERY_OFFSET_RANGE
    offsets = {
        "high_liquidity": base_offset,
        "medium_liquidity": (base_offset + 271) % DISCOVERY_OFFSET_RANGE,
        "low_liquidity": (base_offset + 542) % DISCOVERY_OFFSET_RANGE,
        "rotating_id_control_frame": (base_offset + 813) % DISCOVERY_OFFSET_RANGE,
    }
    return [
        (
            "high_liquidity",
            {
                **common,
                "order": "liquidityNum",
                "ascending": "false",
                "liquidity_num_min": 10_000,
                "offset": offsets["high_liquidity"],
            },
        ),
        (
            "medium_liquidity",
            {
                **common,
                "order": "id",
                "ascending": "true",
                "liquidity_num_min": 1_000,
                "liquidity_num_max": 10_000,
                "offset": offsets["medium_liquidity"],
            },
        ),
        (
            "low_liquidity",
            {
                **common,
                "order": "id",
                "ascending": "true",
                "liquidity_num_min": 1,
                "liquidity_num_max": 1_000,
                "offset": offsets["low_liquidity"],
            },
        ),
        (
            "near_expiry",
            {
                **common,
                "order": "endDate",
                "ascending": "true",
                "end_date_min": now.isoformat(),
                "end_date_max": (now + timedelta(days=7)).isoformat(),
            },
        ),
        (
            "tagged_near_expiry",
            {
                **common,
                "order": "endDate",
                "ascending": "true",
                "tag_id": 2,
                "end_date_min": now.isoformat(),
                "end_date_max": (now + timedelta(days=7)).isoformat(),
            },
        ),
        (
            "rotating_id_control_frame",
            {
                **common,
                "order": "id",
                "ascending": "true",
                "offset": offsets["rotating_id_control_frame"],
            },
        ),
    ]


class PublicReadClient:
    """Strictly allowlisted unauthenticated GET/POST book reads with pacing."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        min_interval_seconds: float = REQUEST_INTERVAL_SECONDS,
        max_requests: int = MAX_REQUESTS_PER_SCAN,
    ) -> None:
        if min_interval_seconds < 0.2 or max_requests > MAX_REQUESTS_PER_SCAN:
            raise ValueError("Public research client exceeds its request bounds")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS),
            headers={"User-Agent": "MIDAS-Veritas-readonly-observatory/1.0"},
            transport=transport,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
        )
        self.min_interval_seconds = min_interval_seconds
        self.max_requests = max_requests
        self.last_request = 0.0
        self.requests = 0
        self.request_attempts = 0
        self.request_log: list[dict[str, Any]] = []
        self.lock = asyncio.Lock()

    async def _send(
        self,
        method: str,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> tuple[Any, bytes, int, int, int, int, int]:
        allowed = (base == GAMMA and path == "/markets" and method == "GET") or (
            base == CLOB and path == "/books" and method == "POST"
        )
        if not allowed:
            raise ValueError("Observatory request is outside the public read allowlist")
        async with self.lock:
            if self.requests >= self.max_requests:
                raise ValueError("Observatory request budget exhausted")
            await asyncio.sleep(
                max(0.0, self.min_interval_seconds - (time.monotonic() - self.last_request))
            )
            self.last_request = time.monotonic()
            self.requests += 1
        last_error: Exception | None = None
        first_started_ns: int | None = None
        first_started_monotonic_ns: int | None = None
        for attempt in range(MAX_RETRIES_PER_PUBLIC_READ + 1):
            started_ns = time.time_ns()
            started_monotonic_ns = time.monotonic_ns()
            if first_started_ns is None:
                first_started_ns = started_ns
                first_started_monotonic_ns = started_monotonic_ns
            self.request_attempts += 1
            attempt_record: dict[str, Any] = {
                "logical_request_number": self.requests,
                "method": method,
                "endpoint": base + path,
                "attempt_number": attempt + 1,
                "requested_at_ns": started_ns,
                "request_started_monotonic_ns": started_monotonic_ns,
            }
            if params is not None:
                attempt_record["query_parameters"] = params
            if json_body is not None:
                attempt_record["request_body_sha256"] = _sha256(_canonical(json_body))
                if isinstance(json_body, list):
                    attempt_record["request_row_count"] = len(json_body)
            try:
                async with self.client.stream(
                    method,
                    base + path,
                    params=params,
                    json=json_body,
                ) as response:
                    attempt_record["response_headers_received_ns"] = time.time_ns()
                    attempt_record["response_headers_received_monotonic_ns"] = time.monotonic_ns()
                    attempt_record["status_code"] = response.status_code
                    if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                        try:
                            delay = float(response.headers.get("Retry-After", "1"))
                        except ValueError:
                            delay = 1.0
                        delay = min(MAX_RETRY_DELAY_SECONDS, max(0.2, delay))
                        attempt_record["retry_after_seconds"] = delay
                        attempt_record["retry_reason"] = f"http_{response.status_code}"
                        attempt_record["response_received_ns"] = time.time_ns()
                        self.request_log.append(attempt_record)
                        await response.aclose()
                        await asyncio.sleep(delay)
                        last_error = RuntimeError(
                            f"Public endpoint returned HTTP {response.status_code}"
                        )
                        continue
                    chunks: list[bytes] = []
                    response_bytes = 0
                    async for chunk in response.aiter_bytes():
                        response_bytes += len(chunk)
                        if response_bytes > MAX_RESPONSE_BYTES:
                            raise ValueError("Public response exceeds its byte bound")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    body_read_completed_ns = time.time_ns()
                    attempt_record["body_read_completed_ns"] = body_read_completed_ns
                    attempt_record["body_read_completed_monotonic_ns"] = time.monotonic_ns()
                    attempt_record["response_received_ns"] = body_read_completed_ns
                    attempt_record["response_bytes"] = len(body)
                    attempt_record["response_sha256"] = _sha256(body)
                    response.raise_for_status()
                    parsed = json.loads(body)
                    received_ns = time.time_ns()
                    received_monotonic_ns = time.monotonic_ns()
                    attempt_record["payload_json_valid"] = True
                    attempt_record["payload_parsed_ns"] = received_ns
                    attempt_record["request_round_trip_ms"] = (
                        received_monotonic_ns - started_monotonic_ns
                    ) / 1_000_000
                    self.request_log.append(attempt_record)
                    return (
                        parsed,
                        body,
                        first_started_ns,
                        received_ns,
                        attempt + 1,
                        first_started_monotonic_ns or started_monotonic_ns,
                        received_monotonic_ns,
                    )
            except (httpx.HTTPError, json.JSONDecodeError) as error:
                last_error = error
                attempt_record["response_received_ns"] = time.time_ns()
                attempt_record["error_type"] = type(error).__name__
                attempt_record["error"] = str(error)[:300]
                if attempt_record not in self.request_log:
                    self.request_log.append(attempt_record)
                if attempt == 0:
                    await asyncio.sleep(0.5)
            except ValueError as error:
                attempt_record["response_received_ns"] = time.time_ns()
                attempt_record["error_type"] = type(error).__name__
                attempt_record["error"] = str(error)[:300]
                self.request_log.append(attempt_record)
                raise
        raise RuntimeError("Public read retry budget exhausted") from last_error

    async def discover(self, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        (
            value,
            body,
            started_ns,
            received_ns,
            attempt_count,
            started_monotonic_ns,
            received_monotonic_ns,
        ) = await self._send("GET", GAMMA, "/markets", params=params)
        if not isinstance(value, list) or len(value) > DISCOVERY_LIMIT:
            raise ValueError("Gamma returned an unexpected or oversized market page")
        malformed_rows = [index for index, item in enumerate(value) if not isinstance(item, dict)]
        rows = [item for item in value if isinstance(item, dict)]
        return rows, {
            "requested_at_ns": started_ns,
            "received_at_ns": received_ns,
            "request_started_monotonic_ns": started_monotonic_ns,
            "received_monotonic_ns": received_monotonic_ns,
            "request_duration_ms": (received_monotonic_ns - started_monotonic_ns) / 1_000_000,
            "request_attempts": attempt_count,
            "returned_item_count": len(value),
            "valid_market_record_count": len(rows),
            "malformed_market_row_indexes": malformed_rows,
            "response_sha256": _sha256(body),
            "response_bytes": len(body),
            "response_payload": body.decode("utf-8"),
        }

    async def books(self, asset_ids: list[str]) -> tuple[Any, dict[str, Any]]:
        if (
            not asset_ids
            or len(asset_ids) > MAX_MARKETS * 2
            or len(set(asset_ids)) != len(asset_ids)
        ):
            raise ValueError("Invalid or oversized paired-book request")
        body = [{"token_id": asset_id} for asset_id in asset_ids]
        (
            value,
            wire,
            started_ns,
            received_ns,
            attempt_count,
            started_monotonic_ns,
            received_monotonic_ns,
        ) = await self._send("POST", CLOB, "/books", json_body=body)
        response_count = len(value) if isinstance(value, list) else None
        return value, {
            "requested_at_ns": started_ns,
            "received_at_ns": received_ns,
            "request_started_monotonic_ns": started_monotonic_ns,
            "received_monotonic_ns": received_monotonic_ns,
            "request_duration_ms": (received_monotonic_ns - started_monotonic_ns) / 1_000_000,
            "request_attempts": attempt_count,
            "request_asset_count": len(asset_ids),
            "request_asset_ids": list(asset_ids),
            "response_book_count": response_count,
            "response_shape": "array" if isinstance(value, list) else type(value).__name__,
            "request_sha256": _sha256(_canonical(body)),
            "response_sha256": _sha256(wire),
            "response_bytes": len(wire),
            "response_payload": wire.decode("utf-8"),
        }

    async def close(self) -> None:
        await self.client.aclose()


def _identity_fields(raw: dict[str, Any]) -> tuple[Any, ...]:
    outcomes = raw.get("outcomes")
    token_ids = raw.get("clobTokenIds")
    try:
        outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        token_ids = json.loads(token_ids) if isinstance(token_ids, str) else token_ids
    except (ValueError, TypeError):
        pass
    return (
        raw.get("conditionId"),
        raw.get("version"),
        json.dumps(outcomes, sort_keys=True),
        json.dumps(token_ids, sort_keys=True),
    )


async def discover_universe(
    client: PublicReadClient, *, now_ns: int, seed: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build a deduplicated universe from six predeclared Gamma query frames."""
    candidates: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()
    query_reports: list[dict[str, Any]] = []
    response_candidate_count = 0
    duplicate_count = 0
    failed_query_count = 0
    for query_id, params in _query_plan(now_ns, seed):
        try:
            page, receipt = await client.discover(params)
        except CumulativeResponseBudgetExceeded:
            raise
        except (OSError, ValueError, RuntimeError, httpx.HTTPError) as error:
            failed_query_count += 1
            query_reports.append(
                {
                    "query_id": query_id,
                    "parameters": params,
                    "status": "failed",
                    "failure_type": type(error).__name__,
                    "failure_reason": str(error)[:300],
                }
            )
            continue
        response_candidate_count += len(page)
        query_reports.append(
            {
                "query_id": query_id,
                "parameters": params,
                "status": "complete" if not receipt["malformed_market_row_indexes"] else "partial",
                "candidate_count": len(page),
                **receipt,
            }
        )
        for raw in page:
            raw_id = raw.get("id")
            if raw_id is None:
                continue
            market_id = str(raw_id)
            existing = candidates.get(market_id)
            if existing is None:
                candidates[market_id] = {"raw": raw, "query_ids": [query_id]}
            else:
                duplicate_count += 1
                existing["query_ids"].append(query_id)
                if _identity_fields(existing["raw"]) != _identity_fields(raw):
                    conflicts.add(market_id)

    eligible: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    universe_rows: list[dict[str, Any]] = []
    for market_id in sorted(
        candidates, key=lambda value: (int(value) if value.isdecimal() else 10**30, value)
    ):
        item = candidates[market_id]
        raw = item["raw"]
        normalized: dict[str, Any] | None
        reason: str | None
        if market_id in conflicts:
            reason = "duplicate_market_identity_conflict"
            normalized = None
        else:
            normalized, reason = normalize_market(raw)
        if normalized is None:
            exclusions[reason or "unknown_exclusion"] += 1
            universe_rows.append(
                {
                    "market_id": market_id,
                    "question": str(raw.get("question") or "")[:500],
                    "discovered_by": sorted(set(item["query_ids"])),
                    "raw_market_metadata_sha256": _sha256(_canonical(raw)),
                    "eligible_for_pair_observation": False,
                    "exclusion_reason": reason or "unknown_exclusion",
                }
            )
            continue
        market = _enrich_candidate(raw, normalized, item["query_ids"])
        eligible.append(market)
        universe_rows.append(
            {**market, "eligible_for_pair_observation": True, "exclusion_reason": None}
        )

    report = {
        "query_count": len(query_reports),
        "successful_query_count": len(query_reports) - failed_query_count,
        "failed_query_count": failed_query_count,
        "malformed_market_row_count": sum(
            len(query.get("malformed_market_row_indexes", []))
            for query in query_reports
            if isinstance(query, dict)
        ),
        "frame_complete": failed_query_count == 0
        and not any(query.get("malformed_market_row_indexes") for query in query_reports),
        "frame_protocol": DISCOVERY_FRAME_PROTOCOL,
        "offset_bucket_seconds": DISCOVERY_OFFSET_BUCKET_SECONDS,
        "query_candidate_records": response_candidate_count,
        "unique_market_ids": len(candidates),
        "duplicate_records_across_queries": duplicate_count,
        "identity_conflicts": len(conflicts),
        "eligible_pair_markets": len(eligible),
        "excluded_market_ids": len(universe_rows) - len(eligible),
        "exclusion_reasons": dict(sorted(exclusions.items())),
        "queries": query_reports,
        "universe": universe_rows,
        "limitations": [
            "The discovered universe is the union of six bounded Gamma response pages, not the venue-wide universe.",
            "The pages overlap and their upstream ranking is not a probability sample of all markets.",
            "Seeded half-hour page offsets broaden the repeated frame but do not provide known inclusion probabilities for the venue universe.",
            "Selection probabilities are conditional on successful, well-formed query responses; failed or malformed pages reduce the observed frame.",
            "Protocol V2, multi-outcome, augmented negative-risk and ambiguous binary relationships are recorded as excluded from pair economics.",
        ],
    }
    return eligible, report


def _snapshot_change_bucket(market_id: str, history: dict[str, Any]) -> str:
    rows = history.get(market_id, [])
    if not isinstance(rows, list) or len(rows) < 3:
        return "unclassified"
    valid = [
        row
        for row in rows[-12:]
        if isinstance(row, dict) and isinstance(row.get("captured_ns"), int)
    ]
    if len(valid) < 3:
        return "unclassified"
    elapsed_hours = (valid[-1]["captured_ns"] - valid[0]["captured_ns"]) / 3_600_000_000_000
    if elapsed_hours <= 0:
        return "unclassified"
    changes = sum(
        valid[index]["state_hash"] != valid[index - 1]["state_hash"]
        for index in range(1, len(valid))
    )
    rate = changes / elapsed_hours
    if rate == 0:
        return "no_observed_snapshot_change"
    return "higher_snapshot_change" if rate >= 1 else "lower_snapshot_change"


def _stratum(market: dict[str, Any], phase: str, history: dict[str, Any]) -> str:
    if phase == "liquidity":
        value = _number(market.get("liquidity_usdc"))
        if value is None:
            return "unknown"
        return (
            "high"
            if value >= 10_000
            else "medium"
            if value >= 1_000
            else "low"
            if value > 0
            else "zero"
        )
    if phase == "expiry":
        end_ns = market.get("end_ns")
        if not isinstance(end_ns, int):
            return "unknown"
        remaining = end_ns - time.time_ns()
        return (
            "near_7d"
            if remaining <= 7 * 86_400_000_000_000
            else "medium_90d"
            if remaining <= 90 * 86_400_000_000_000
            else "long"
        )
    if phase == "category":
        return str(market.get("primary_category") or "unknown")[:100]
    if phase == "spread":
        spread = _number(market.get("spread_per_share"))
        if spread is None:
            return "unknown"
        return (
            "tight_le_0.01"
            if spread <= 0.01
            else "medium_le_0.05"
            if spread <= 0.05
            else "wide_gt_0.05"
        )
    if phase == "snapshot_change":
        return _snapshot_change_bucket(str(market["market_id"]), history)
    raise ValueError("Unknown stratification phase")


def _allocate_quotas(groups: dict[str, list[dict[str, Any]]], size: int) -> dict[str, int]:
    """Use equal initial coverage, then sqrt-size allocation with deterministic ties."""
    quotas = {key: 0 for key in sorted(groups)}
    remaining = min(size, sum(len(group) for group in groups.values()))
    while remaining:
        available = [key for key in sorted(groups) if quotas[key] < len(groups[key])]
        if not available:
            break
        fresh = [key for key in available if quotas[key] == 0]
        targets = fresh or available
        weight_sum = sum(math.sqrt(len(groups[key])) for key in targets)
        proposed = {key: remaining * math.sqrt(len(groups[key])) / weight_sum for key in targets}
        additions = {
            key: min(len(groups[key]) - quotas[key], int(proposed[key])) for key in targets
        }
        allocated = sum(additions.values())
        for key, value in additions.items():
            quotas[key] += value
        remaining -= allocated
        if not remaining:
            break
        ranked = sorted(
            (key for key in targets if quotas[key] < len(groups[key])),
            key=lambda key: (-(proposed[key] - int(proposed[key])), key),
        )
        if ranked:
            key = ranked[0]
            quotas[key] += 1
            remaining -= 1
    return quotas


def _stable_hash(seed: int, label: str, market_id: str) -> str:
    return hashlib.sha256(f"{seed}:{label}:{market_id}".encode()).hexdigest()


def select_cohort(
    eligible: list[dict[str, Any]],
    *,
    target: int,
    control_count: int,
    reference_count: int = DEFAULT_REFERENCE_MARKETS,
    seed: int,
    sequence: int,
    frozen_control_ids: list[str] | None = None,
    history: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    if (
        not 1 <= target <= MAX_MARKETS
        or not 0 <= control_count <= target
        or not 0 <= reference_count <= target - control_count
    ):
        raise ValueError("Invalid observation cohort bounds")
    history = history or {}
    by_id = {str(row["market_id"]): row for row in eligible}
    if len(by_id) != len(eligible):
        raise ValueError("Eligible universe contains duplicate market IDs")
    population = len(eligible)
    if population == 0:
        return (
            [],
            {
                "target_markets": target,
                "selected_markets": 0,
                "phase": PHASES[(sequence - 1) % len(PHASES)],
                "reference_target": reference_count,
                "reference_selected": 0,
            },
            [],
        )

    if frozen_control_ids is None:
        controls = sorted(
            by_id, key=lambda market_id: _stable_hash(seed, "stable-control", market_id)
        )[: min(control_count, population)]
        control_origin_population = population
        control_origin_k = len(controls)
    else:
        controls = list(dict.fromkeys(frozen_control_ids))
        control_origin_population = None
        control_origin_k = None
    active_controls = [market_id for market_id in controls if market_id in by_id]
    unavailable_controls = [market_id for market_id in controls if market_id not in by_id]
    active_control_ids = set(active_controls)
    reference_frame = [row for row in eligible if str(row["market_id"]) not in active_control_ids]
    reference_target = min(reference_count, len(reference_frame))
    reference_seed = seed + sequence * 1_000_003 + 0x5A17
    reference_rows = sorted(
        reference_frame,
        key=lambda row: _stable_hash(reference_seed, "reference-random", str(row["market_id"])),
    )[:reference_target]
    reference_ids = {str(row["market_id"]) for row in reference_rows}
    remaining_rows = [row for row in reference_frame if str(row["market_id"]) not in reference_ids]
    rotation_target = min(
        max(0, target - len(active_controls) - len(reference_rows)), len(remaining_rows)
    )
    phase = PHASES[(sequence - 1) % len(PHASES)]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in remaining_rows:
        groups[_stratum(row, phase, history)].append(row)
    quotas = _allocate_quotas(groups, rotation_target)
    rotation: list[dict[str, Any]] = []
    probabilities: dict[str, dict[str, Any]] = {}
    rotation_seed = seed + sequence * 1_000_003 + 0xA91D
    for stratum in sorted(groups):
        count = quotas[stratum]
        group = groups[stratum]
        selected = sorted(
            group,
            key=lambda row: _stable_hash(
                rotation_seed, f"{phase}:{stratum}", str(row["market_id"])
            ),
        )[:count]
        for row in selected:
            market_id = str(row["market_id"])
            rotation.append(row)
            probabilities[market_id] = {
                "role": "rotating_stratified",
                "phase": phase,
                "stratum": stratum,
                "population_before_rotation": len(group),
                "quota": count,
                "inclusion_probability_conditional_on_frozen_controls": str(count / len(group)),
            }
    cohort: list[dict[str, Any]] = []
    for market_id in active_controls:
        row = by_id[market_id]
        cohort.append(
            {
                **row,
                "cohort_role": "stable_random_control",
                "selection_probability": (
                    str(control_origin_k / control_origin_population)
                    if control_origin_population and control_origin_k is not None
                    else "1 conditional on frozen control cohort"
                ),
                "selection_probability_basis": (
                    "simple_random_sample_without_replacement_from_first_bounded_discovery_union"
                    if control_origin_population
                    else "frozen_control_cohort_retained_without_outcome_replacement"
                ),
                "cohort_roles": ["stable_random_control"],
                "stable_control_member": True,
                "reference_cohort_member": False,
                "reference_selection_probability": None,
            }
        )
    reference_probability = str(reference_target / len(reference_frame)) if reference_frame else "0"
    for row in reference_rows:
        market_id = str(row["market_id"])
        cohort.append(
            {
                **row,
                "cohort_role": "reference_random",
                "cohort_roles": ["reference_random"],
                "stable_control_member": False,
                "reference_cohort_member": True,
                "reference_selection_probability": reference_probability,
                "selection_probability": reference_probability,
                "selection_probability_basis": (
                    "simple_random_sample_without_replacement_from_current_bounded_frame_excluding_available_frozen_controls"
                ),
            }
        )
    for row in rotation:
        market_id = str(row["market_id"])
        probability = probabilities[market_id]
        cohort.append(
            {
                **row,
                "cohort_role": "rotating_stratified",
                "selection_probability": probability[
                    "inclusion_probability_conditional_on_frozen_controls"
                ],
                "selection_probability_basis": (
                    "simple_random_sample_without_replacement_within_disjoint_phase_stratum; "
                    "conditional on available frozen controls and the independent reference sample"
                ),
                "selection_stratum": probability["stratum"],
                "cohort_roles": ["rotating_stratified"],
                "stable_control_member": False,
                "reference_cohort_member": False,
                "reference_selection_probability": None,
            }
        )
    plan = {
        "sequence": sequence,
        "seed": seed,
        "rotation_seed": rotation_seed,
        "phase": phase,
        "phase_cycle": list(PHASES),
        "bounded_eligible_population": population,
        "target_markets": target,
        "stable_control_population_at_freeze": control_origin_population,
        "stable_control_selected_at_freeze": control_origin_k,
        "stable_control_available_this_scan": len(active_controls),
        "stable_control_missing_this_scan": unavailable_controls,
        "rotation_population_after_controls": len(reference_frame),
        "rotation_population_after_reference": len(remaining_rows),
        "rotation_target": rotation_target,
        "reference_seed": reference_seed,
        "reference_population_excluding_available_frozen_controls": len(reference_frame),
        "reference_target": reference_target,
        "reference_selected": len(reference_rows),
        "reference_inclusion_probability": reference_probability,
        "reference_market_ids": sorted(reference_ids),
        "reference_probability_scope": (
            "current bounded Gamma response union excluding available frozen control IDs; "
            "not the venue-wide market universe"
        ),
        "rotation_strata": {
            stratum: {"population": len(groups[stratum]), "quota": quotas[stratum]}
            for stratum in sorted(groups)
        },
        "selected_count": len(cohort),
        "selection_excludes_price_edge": True,
        "probability_scope": "conditional on the successful bounded query-response union and frozen stable control IDs",
    }
    return cohort, plan, controls


def _book_state_hash(books: dict[str, dict[str, Any]], market: dict[str, Any]) -> str | None:
    try:
        state = [str(books[market["outcomes"][side]].get("hash") or "") for side in ("yes", "no")]
    except (KeyError, TypeError):
        return None
    if not all(state):
        return None
    return _sha256("|".join(state).encode())


def _reported_age_band(age_ms: int) -> str:
    if age_ms < 0:
        return "negative_source_clock_delta"
    if age_ms <= 1_000:
        return "0_to_1s"
    if age_ms <= 5_000:
        return "1_to_5s"
    if age_ms <= 60_000:
        return "5_to_60s"
    if age_ms <= 300_000:
        return "1_to_5m"
    return "over_5m"


def _reported_skew_band(skew_ms: int) -> str:
    if skew_ms <= 250:
        return "0_to_250ms"
    if skew_ms <= 1_000:
        return "250ms_to_1s"
    if skew_ms <= 5_000:
        return "1_to_5s"
    return "over_5s"


def _book_envelope_errors(raw: Any) -> list[str]:
    if not isinstance(raw, dict):
        return ["row_not_object"]
    errors: list[str] = []
    asset_id = raw.get("asset_id", raw.get("assetId"))
    if not isinstance(asset_id, str) or not asset_id:
        errors.append("asset_id_missing_or_invalid")
    if not isinstance(raw.get("market"), str) or not raw["market"]:
        errors.append("market_identity_missing_or_invalid")
    timestamp = raw.get("timestamp")
    try:
        if int(str(timestamp)) <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        errors.append("timestamp_missing_or_invalid")
    if not isinstance(raw.get("bids"), list):
        errors.append("bids_not_array")
    if not isinstance(raw.get("asks"), list):
        errors.append("asks_not_array")
    if not isinstance(raw.get("neg_risk"), bool):
        errors.append("negative_risk_flag_missing_or_invalid")
    for field in ("tick_size", "min_order_size"):
        number = _number(raw.get(field))
        if number is None or number <= 0:
            errors.append(f"{field}_missing_or_nonpositive")
    return errors


def _validate_book_batch(
    payload: Any, requested_asset_ids: list[str]
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Classify per-asset integrity; usable unrelated rows remain auditable."""
    requested = set(requested_asset_ids)
    counts: Counter[str] = Counter()
    rows_by_asset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    malformed_rows: list[dict[str, Any]] = []
    response_shape = "array" if isinstance(payload, list) else type(payload).__name__
    if isinstance(payload, list):
        for index, row in enumerate(payload):
            if not isinstance(row, dict):
                malformed_rows.append({"row_index": index, "reason": "row_not_object"})
                continue
            asset_id = row.get("asset_id", row.get("assetId"))
            if not isinstance(asset_id, str) or not asset_id:
                malformed_rows.append({"row_index": index, "reason": "asset_id_missing_or_invalid"})
                continue
            counts[asset_id] += 1
            rows_by_asset[asset_id].append(row)
    missing = sorted(asset_id for asset_id in requested if counts[asset_id] == 0)
    duplicates = sorted(asset_id for asset_id in requested if counts[asset_id] > 1)
    unexpected = sorted(asset_id for asset_id in counts if asset_id not in requested)
    malformed: dict[str, list[str]] = {}
    usable: dict[str, dict[str, Any]] = {}
    for asset_id in sorted(requested):
        rows = rows_by_asset.get(asset_id, [])
        if len(rows) != 1:
            continue
        errors = _book_envelope_errors(rows[0])
        if errors:
            malformed[asset_id] = errors
        else:
            usable[asset_id] = rows[0]
    status = (
        "complete"
        if response_shape == "array"
        and not missing
        and not duplicates
        and not unexpected
        and not malformed
        and not malformed_rows
        else "partial"
    )
    return usable, {
        "status": status,
        "response_shape": response_shape,
        "requested_asset_count": len(requested_asset_ids),
        "returned_row_count": len(payload) if isinstance(payload, list) else None,
        "returned_requested_asset_count": sum(counts[asset_id] for asset_id in requested),
        "missing_asset_ids": missing,
        "duplicate_asset_ids": duplicates,
        "unexpected_asset_ids": unexpected,
        "malformed_assets": malformed,
        "malformed_rows": malformed_rows,
        "usable_requested_asset_count": len(usable),
    }


async def _collect_pair_books(
    client: PublicReadClient, selected: list[dict[str, Any]]
) -> dict[str, Any]:
    """Read one bounded batch, then retry only affected pairs as coordinated pairs."""
    asset_owners: dict[str, list[str]] = defaultdict(list)
    for row in selected:
        for side in ("yes", "no"):
            asset_owners[str(row["outcomes"][side])].append(str(row["market_id"]))
    colliding_assets = {
        asset_id for asset_id, market_ids in asset_owners.items() if len(set(market_ids)) > 1
    }
    colliding_markets = {
        market_id for asset_id in colliding_assets for market_id in asset_owners[asset_id]
    }
    safe_rows = [row for row in selected if str(row["market_id"]) not in colliding_markets]
    requested_assets = [str(row["outcomes"][side]) for row in safe_rows for side in ("yes", "no")]
    batch_receipts: list[dict[str, Any]] = []
    initial_books: dict[str, dict[str, Any]] = {}
    initial_integrity: dict[str, Any] = {
        "status": "not_requested",
        "response_shape": "not_requested",
        "missing_asset_ids": requested_assets,
        "duplicate_asset_ids": [],
        "unexpected_asset_ids": [],
        "malformed_assets": {},
        "malformed_rows": [],
        "usable_requested_asset_count": 0,
    }
    if requested_assets:
        initial_payload, initial_receipt = await client.books(requested_assets)
        initial_books, initial_integrity = _validate_book_batch(initial_payload, requested_assets)
        initial_receipt["integrity"] = initial_integrity
        initial_receipt["batch_role"] = "initial_all_selected_pairs"
        batch_receipts.append(initial_receipt)

    def issue_for(asset_id: str, integrity: dict[str, Any]) -> str | None:
        if asset_id in integrity.get("duplicate_asset_ids", []):
            return "duplicate_asset"
        if asset_id in integrity.get("malformed_assets", {}):
            return "malformed_asset"
        if asset_id in integrity.get("missing_asset_ids", []):
            return "missing_asset"
        return None

    retry_rows = [
        row
        for row in safe_rows
        if any(
            issue_for(str(row["outcomes"][side]), initial_integrity) is not None
            for side in ("yes", "no")
        )
    ]
    retry_books: dict[str, dict[str, Any]] = {}
    retry_integrity: dict[str, Any] | None = None
    retry_receipt: dict[str, Any] | None = None
    retry_failure: dict[str, Any] | None = None
    retry_assets = [str(row["outcomes"][side]) for row in retry_rows for side in ("yes", "no")]
    if retry_assets:
        try:
            retry_payload, retry_receipt = await client.books(retry_assets)
            retry_books, retry_integrity = _validate_book_batch(retry_payload, retry_assets)
            retry_receipt["integrity"] = retry_integrity
            retry_receipt["batch_role"] = "targeted_affected_pairs_retry"
            batch_receipts.append(retry_receipt)
        except (OSError, ValueError, RuntimeError, httpx.HTTPError) as error:
            retry_failure = {
                "failure_type": type(error).__name__,
                "failure_reason": str(error)[:300],
                "requested_pair_count": len(retry_rows),
                "requested_asset_count": len(retry_assets),
            }

    pair_books: dict[str, dict[str, dict[str, Any]]] = {}
    pair_timing: dict[str, dict[str, Any]] = {}
    for row in selected:
        market_id = str(row["market_id"])
        pair_assets = {side: str(row["outcomes"][side]) for side in ("yes", "no")}
        if market_id in colliding_markets:
            pair_books[market_id] = {}
            pair_timing[market_id] = {
                "status": "identity_collision",
                "reason": "selected_asset_id_reused_across_market_identities",
                "colliding_asset_ids": sorted(set(pair_assets.values()) & colliding_assets),
                "initial_batch_sha256": None,
                "retry_batch_sha256": None,
            }
            continue
        affected = any(issue_for(asset, initial_integrity) for asset in pair_assets.values())
        if affected:
            clean_retry_pair = bool(
                retry_integrity is not None
                and all(asset in retry_books for asset in pair_assets.values())
            )
            source = retry_receipt if clean_retry_pair else None
            books = (
                {asset: retry_books[asset] for asset in pair_assets.values()}
                if clean_retry_pair
                else {}
            )
            status = "recovered_by_pair_retry" if clean_retry_pair else "incomplete_after_retry"
            pair_issue = (
                None
                if clean_retry_pair
                else (
                    retry_failure
                    or {
                        "yes": issue_for(pair_assets["yes"], retry_integrity or initial_integrity),
                        "no": issue_for(pair_assets["no"], retry_integrity or initial_integrity),
                    }
                )
            )
        else:
            source = batch_receipts[0] if batch_receipts else None
            books = {asset: initial_books[asset] for asset in pair_assets.values()}
            status = "complete"
            pair_issue = None
        pair_books[market_id] = books
        pair_timing[market_id] = {
            "status": status,
            "reason": pair_issue,
            "requested_asset_ids_by_leg": pair_assets,
            "initial_asset_status_by_leg": {
                side: issue_for(asset, initial_integrity) or "valid"
                for side, asset in pair_assets.items()
            },
            "retry_attempted": affected,
            "retry_status": (
                "complete_pair"
                if status == "recovered_by_pair_retry"
                else "failed"
                if affected
                else "not_needed"
            ),
            "initial_batch_sha256": (
                batch_receipts[0].get("response_sha256") if batch_receipts else None
            ),
            "retry_batch_sha256": retry_receipt.get("response_sha256") if retry_receipt else None,
            "requested_at_ns": source.get("requested_at_ns") if source else None,
            "received_at_ns": source.get("received_at_ns") if source else None,
            "request_duration_ms": (
                source.get("request_duration_ms")
                if source and source.get("request_duration_ms") is not None
                else None
            ),
        }
    return {
        "pair_books": pair_books,
        "pair_timing": pair_timing,
        "batch_receipts": batch_receipts,
        "initial_integrity": initial_integrity,
        "retry_integrity": retry_integrity,
        "retry_failure": retry_failure,
        "retry_pair_count": len(retry_rows),
        "collision_market_ids": sorted(colliding_markets),
        "collision_asset_ids": sorted(colliding_assets),
        "requested_asset_count": len(requested_assets),
    }


def _write_failed_scan(root: Path, failure: dict[str, Any]) -> Path:
    """Persist bounded evidence for a scan that failed before its snapshot commit."""
    record: dict[str, Any] = {
        "schema_version": 1,
        "failure_record_version": "veritas-observatory-failure-v1",
        "recorded_at_ns": time.time_ns(),
        "failure": failure,
        "orders_submitted": False,
        "authenticated_requests": False,
    }
    data = _canonical(record)
    compressed = gzip.compress(data, compresslevel=6, mtime=0)
    if len(compressed) > MAX_RESPONSE_BYTES:
        discovery = record["failure"].get("discovery")
        queries = discovery.get("queries") if isinstance(discovery, dict) else None
        if isinstance(queries, list):
            for query in queries:
                if not isinstance(query, dict):
                    continue
                payload = query.pop("response_payload", None)
                if isinstance(payload, str):
                    query["response_payload_omitted"] = True
                    query["response_payload_sha256"] = query.get("response_sha256")
                    query["response_payload_bytes"] = len(payload.encode("utf-8"))
        record["failure"]["source_payloads_omitted_due_to_bound"] = True
        data = _canonical(record)
        compressed = gzip.compress(data, compresslevel=6, mtime=0)
    record["failure_evidence_sha256"] = _sha256(data)
    compressed = gzip.compress(_canonical(record), compresslevel=6, mtime=0)
    failure_id = f"failure-{record['recorded_at_ns']}-{record['failure_evidence_sha256'][:12]}"
    directory = root / "failed-scans"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / f"{failure_id}.json.gz"
    if len(compressed) > MAX_RESPONSE_BYTES:
        raise ValueError("Failed-scan evidence exceeds its compressed artifact bound")
    with path.open("xb") as handle:
        handle.write(compressed)
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(directory, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return path


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    positive_candidates = [
        {
            "market_id": row["market_id"],
            "question": row["question"],
            "cohort_role": row["cohort_role"],
            "gross_positive_quantities": row["gross_positive_quantities"],
            "snapshot_file": report["snapshot_file"],
            "snapshot_evidence_sha256": report["snapshot_evidence_sha256"],
            "status": "public_snapshot_candidate_requires_independent_replay",
        }
        for row in report["market_observations"]
        if row["gross_positive_quantities"]
    ]
    selected = report["selection"]["selected_markets"]
    return {
        "schema_version": 1,
        "analysis_version": VERSION,
        "scan_id": report["scan_id"],
        "captured_at_utc": report["captured_at_utc"],
        "captured_ns": report["captured_ns"],
        "source_http_attempts": report["source_requests"]["public_http_attempts"],
        "snapshot_file": report["snapshot_file"],
        "snapshot_evidence_sha256": report["snapshot_evidence_sha256"],
        "source_code_sha256": report["source_code_sha256"],
        "discovery": {
            key: report["discovery"][key]
            for key in (
                "frame_protocol",
                "offset_bucket_seconds",
                "query_count",
                "query_candidate_records",
                "unique_market_ids",
                "duplicate_records_across_queries",
                "eligible_pair_markets",
                "excluded_market_ids",
                "exclusion_reasons",
            )
        },
        "selection": {
            "phase": report["selection"]["plan"]["phase"],
            "eligible_population": report["selection"]["plan"]["bounded_eligible_population"],
            "target_markets": report["selection"]["plan"]["target_markets"],
            "selected_markets": len(selected),
            "stable_control_markets": sum(
                row["cohort_role"] == "stable_random_control" for row in selected
            ),
            "reference_random_markets": sum(
                row["cohort_role"] == "reference_random" for row in selected
            ),
            "rotating_markets": sum(
                row["cohort_role"] == "rotating_stratified" for row in selected
            ),
            "cohort_role_counts": dict(
                sorted(Counter(row["cohort_role"] for row in selected).items())
            ),
            "selected_by_liquidity": dict(
                sorted(Counter(row.get("liquidity_band", "unknown") for row in selected).items())
            ),
            "selected_by_expiry": dict(
                sorted(Counter(row.get("expiry_band", "unknown") for row in selected).items())
            ),
            "selected_by_category": dict(
                sorted(Counter(row.get("primary_category", "unknown") for row in selected).items())
            ),
            "selected_by_spread": dict(
                sorted(Counter(row.get("spread_band", "unknown") for row in selected).items())
            ),
            "sampled_markets": [
                {
                    key: row.get(key)
                    for key in (
                        "market_id",
                        "primary_category",
                        "primary_category_source",
                        "cohort_role",
                        "selection_probability",
                        "selection_probability_basis",
                        "selection_stratum",
                        "reference_selection_probability",
                        "stable_control_member",
                        "reference_cohort_member",
                    )
                }
                for row in selected
            ],
        },
        "collection_bounds": {
            "target_markets": report["selection"]["plan"]["target_markets"],
            "maximum_markets": MAX_MARKETS,
            "gamma_queries_per_scan": DISCOVERY_QUERIES,
            "gamma_page_limit": DISCOVERY_LIMIT,
            "maximum_public_read_calls_per_scan": MAX_REQUESTS_PER_SCAN,
            "maximum_public_http_attempts_per_scan": MAX_PUBLIC_HTTP_ATTEMPTS_PER_SCAN,
            "maximum_retries_per_public_read": MAX_RETRIES_PER_PUBLIC_READ,
            "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "maximum_response_bytes": MAX_RESPONSE_BYTES,
            "minimum_request_interval_seconds": report["collection_bounds"][
                "minimum_request_interval_seconds"
            ],
            "maximum_root_bytes": MAX_ROOT_BYTES,
            "quantity_grid": report["quantity_grid"],
        },
        "observation": {
            "attempted_market_pairs": len(report["market_observations"]),
            "valid_quality_pairs": report["counts"]["valid_quality_pairs"],
            "invalid_reasons": report["counts"]["invalid_reasons"],
            "reported_update_age_bands_by_leg": report["counts"][
                "reported_update_age_bands_by_leg"
            ],
            "reported_update_age_above_5s_by_leg": report["counts"][
                "reported_update_age_above_5s_by_leg"
            ],
            "reported_update_timestamp_skew_bands": report["counts"][
                "reported_update_timestamp_skew_bands"
            ],
            "reported_update_timestamp_skew_above_250ms_pairs": report["counts"][
                "reported_update_timestamp_skew_above_250ms_pairs"
            ],
            "positive_top_gross_pairs": report["counts"]["positive_top_gross_pairs"],
            "positive_full_depth_gross_by_quantity": report["counts"][
                "positive_full_depth_gross_by_quantity"
            ],
            "positive_minimum_notional_by_quantity": report["counts"][
                "positive_minimum_notional_by_quantity"
            ],
            "positive_minimum_shares_by_quantity": report["counts"].get(
                "positive_minimum_shares_by_quantity"
            ),
            "positive_reported_constraints_by_quantity": report["counts"].get(
                "positive_reported_constraints_by_quantity"
            ),
            "positive_single_match_fee_sensitivity_by_quantity": report["counts"][
                "positive_single_match_fee_sensitivity_by_quantity"
            ],
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": report["counts"][
                "positive_fragmentation_safe_fee_sensitivity_by_quantity"
            ],
            "fee_unavailable_pairs": report["counts"].get("fee_unavailable_pairs"),
        },
        "market_observations": [
            {
                "market_id": row["market_id"],
                "question": row["question"],
                "cohort_role": row["cohort_role"],
                "selection_probability": row["selection_probability"],
                "selection_stratum": row.get("selection_stratum"),
                "valid": row["audit"]["valid"],
                "reason": row["audit"].get("reason"),
                "book_integrity_status": row.get("book_integrity", {}).get("status"),
                "pair_batch_duration_ms": row.get("book_integrity", {}).get("request_duration_ms"),
                "top_pair_gross_edge_per_share": row["audit"].get("top_pair_gross_edge_per_share"),
                "gross_positive_quantities": row["gross_positive_quantities"],
                "positive_minimum_notional_quantities": row["positive_minimum_notional_quantities"],
                "positive_minimum_shares_quantities": row.get("positive_minimum_shares_quantities"),
                "positive_reported_constraints_quantities": row.get(
                    "positive_reported_constraints_quantities"
                ),
                "positive_single_match_quantities": row["positive_single_match_quantities"],
                "positive_fragmentation_safe_quantities": row[
                    "positive_fragmentation_safe_quantities"
                ],
                "book_source_sha256": row["book_source_sha256"],
            }
            for row in report["market_observations"]
        ],
        "positive_candidates": positive_candidates,
        "measurement_pilot": report.get("measurement_pilot"),
        "measurement_pilot_v2": report.get("measurement_pilot_v2"),
        "coverage_kind": "intermittent_public_snapshots",
        "orders_submitted": False,
        "limitations": report["limitations"],
    }


async def run_scan(
    root: Path,
    *,
    target_markets: int = DEFAULT_MARKETS,
    control_count: int = DEFAULT_CONTROL_MARKETS,
    reference_count: int = DEFAULT_REFERENCE_MARKETS,
    seed: int = DEFAULT_SEED,
    quantity_grid: tuple[str, ...] = DEFAULT_QUANTITIES,
    transport: httpx.AsyncBaseTransport | None = None,
    request_interval_seconds: float = REQUEST_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Run one atomic market-universe and paired-book snapshot cycle."""
    scan_started_ns = time.time_ns()
    if (
        not 30 <= target_markets <= MAX_MARKETS
        or not 0 <= control_count <= target_markets
        or not 0 <= reference_count <= target_markets - control_count
    ):
        raise ValueError("Observation pilot supports 30..50 markets and bounded controls")
    if not 1 <= len(quantity_grid) <= 10:
        raise ValueError("Quantity grid must contain 1..10 values")
    if len(set(quantity_grid)) != len(quantity_grid):
        raise ValueError("Quantity grid contains duplicates")
    root = root.expanduser()
    if root.exists() and root.is_symlink():
        raise ValueError("Observatory root cannot be a symlink")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = root.resolve()
    snapshots = root / "snapshots"
    snapshots.mkdir(exist_ok=True, mode=0o700)
    if snapshots.is_symlink():
        raise ValueError("Snapshot directory cannot be a symlink")
    lock_path = root / "run.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("A Veritas observatory scan already owns the output root") from error
        total_bytes = sum(
            path.stat().st_size
            for path in root.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        if total_bytes >= MAX_ROOT_BYTES:
            raise ValueError("Observatory evidence budget reached; no observations were removed")
        state_path = root / "state.json"
        state = _safe_json(state_path, max_bytes=MAX_STATE_BYTES) if state_path.exists() else {}
        if state is None:
            state = {}
        sequence = int(state.get("next_sequence", 1))
        history = state.get("snapshot_history", {})
        if not isinstance(history, dict):
            raise ValueError("Malformed activity-proxy history")

        control_path = root / "control-cohort.json"
        control_record = (
            _safe_json(control_path, max_bytes=1_000_000) if control_path.exists() else None
        )
        frozen_control_ids: list[str] | None = None
        if control_record:
            if control_record.get("version") not in {
                CONTROL_COHORT_VERSION,
                LEGACY_CONTROL_COHORT_VERSION,
            } or not isinstance(control_record.get("market_ids"), list):
                raise ValueError("Invalid frozen control cohort")
            frozen_control_ids = [str(item) for item in control_record["market_ids"]]

        client = PublicReadClient(
            transport=transport, min_interval_seconds=request_interval_seconds
        )
        try:
            discovery_ns = time.time_ns()
            eligible, discovery = await discover_universe(client, now_ns=discovery_ns, seed=seed)
            if not eligible:
                _write_failed_scan(
                    root,
                    {
                        "failure_type": "NoEligibleMarkets",
                        "failure_reason": "No eligible V1 binary markets were found in the bounded query union",
                        "failed_stage": "market_discovery",
                        "discovery": discovery,
                        "public_http_attempts": client.request_attempts,
                        "request_attempt_log": client.request_log,
                    },
                )
                raise RuntimeError(
                    "No eligible V1 binary markets were found in the bounded query union"
                )
            selected, selection_plan, control_ids = select_cohort(
                eligible,
                target=target_markets,
                control_count=control_count,
                reference_count=reference_count,
                seed=seed,
                sequence=sequence,
                frozen_control_ids=frozen_control_ids,
                history=history,
            )
            if not selected:
                raise RuntimeError("No markets were selected from the eligible bounded universe")
            selection_completed_ns = time.time_ns()
            if control_record is None:
                controls = [
                    row for row in selected if row["cohort_role"] == "stable_random_control"
                ]
                _atomic_json(
                    control_path,
                    {
                        "version": CONTROL_COHORT_VERSION,
                        "created_at_ns": time.time_ns(),
                        "seed": seed,
                        "discovery_population": selection_plan[
                            "stable_control_population_at_freeze"
                        ],
                        "selected_count": selection_plan["stable_control_selected_at_freeze"],
                        "market_ids": [row["market_id"] for row in controls],
                        "selection_probability": (
                            str(len(controls) / len(eligible)) if eligible else "0"
                        ),
                        "selection_basis": "seeded simple random control within first bounded discovery union",
                        "selection_excludes_price_edge": True,
                    },
                )

            try:
                book_collection = await _collect_pair_books(client, selected)
            except (OSError, ValueError, RuntimeError, httpx.HTTPError) as error:
                _write_failed_scan(
                    root,
                    {
                        "failure_type": type(error).__name__,
                        "failure_reason": str(error)[:500],
                        "failed_stage": "initial_clob_read",
                        "discovery": discovery,
                        "selection_plan": selection_plan,
                        "selected_market_ids": [row["market_id"] for row in selected],
                        "public_http_attempts": client.request_attempts,
                        "request_attempt_log": client.request_log,
                    },
                )
                raise
            observations: list[dict[str, Any]] = []
            invalid_reasons: Counter[str] = Counter()
            update_age_bands_by_leg: dict[str, Counter[str]] = {
                "yes": Counter(),
                "no": Counter(),
            }
            update_age_above_threshold_by_leg: Counter[str] = Counter()
            update_skew_bands: Counter[str] = Counter()
            update_skew_above_threshold_pairs = 0
            quantity_counts: dict[str, Counter[str]] = {
                "positive_full_depth_gross": Counter(),
                "positive_minimum_notional": Counter(),
                "positive_minimum_shares": Counter(),
                "positive_reported_constraints": Counter(),
                "positive_single_match": Counter(),
                "positive_fragmentation_safe": Counter(),
            }
            for row in selected:
                market_id = str(row["market_id"])
                two_books = book_collection["pair_books"].get(market_id, {})
                pair_timing = book_collection["pair_timing"][market_id]
                audit: dict[str, Any]
                if pair_timing["status"] in {"identity_collision", "incomplete_after_retry"}:
                    audit = {
                        "valid": False,
                        "reason": (
                            "selected_asset_identity_collision"
                            if pair_timing["status"] == "identity_collision"
                            else "book_batch_incomplete_after_targeted_retry"
                        ),
                        "book_integrity_reason": pair_timing.get("reason"),
                        "quantity_results": [],
                    }
                else:
                    audit = audit_pair_snapshot(
                        row,
                        two_books,
                        captured_ns=pair_timing["received_at_ns"],
                        batch_started_ns=pair_timing["requested_at_ns"],
                        request_duration_ms=pair_timing.get("request_duration_ms"),
                        quantities=quantity_grid,
                        max_batch_duration_ms=5_000,
                        reported_update_age_threshold_ms=(
                            REPORTED_UPDATE_AGE_DIAGNOSTIC_THRESHOLD_MS
                        ),
                        reported_update_skew_diagnostic_threshold_ms=(
                            REPORTED_UPDATE_SKEW_DIAGNOSTIC_THRESHOLD_MS
                        ),
                    )
                if not audit["valid"]:
                    invalid_reasons[str(audit.get("reason") or "invalid_snapshot")] += 1
                else:
                    quality = audit["quality"]
                    for side, age_ms in quality["reported_update_age_ms_by_leg"].items():
                        update_age_bands_by_leg[side][_reported_age_band(age_ms)] += 1
                        if age_ms > REPORTED_UPDATE_AGE_DIAGNOSTIC_THRESHOLD_MS:
                            update_age_above_threshold_by_leg[side] += 1
                    update_skew_bands[
                        _reported_skew_band(quality["reported_update_timestamp_skew_ms"])
                    ] += 1
                    if quality["reported_update_timestamp_skew_above_diagnostic_threshold"]:
                        update_skew_above_threshold_pairs += 1
                    for quantity_row in audit["quantity_results"]:
                        quantity = quantity_row["quantity_shares_per_leg"]
                        if quantity_row["positive_full_depth_gross"]:
                            quantity_counts["positive_full_depth_gross"][quantity] += 1
                        if (
                            quantity_row["positive_full_depth_gross"]
                            and quantity_row["minimum_order_notional_satisfied"]
                        ):
                            quantity_counts["positive_minimum_notional"][quantity] += 1
                        if (
                            quantity_row["positive_full_depth_gross"]
                            and quantity_row["minimum_order_shares_satisfied"]
                        ):
                            quantity_counts["positive_minimum_shares"][quantity] += 1
                        if (
                            quantity_row["positive_full_depth_gross"]
                            and quantity_row["minimum_order_constraints_satisfied"]
                        ):
                            quantity_counts["positive_reported_constraints"][quantity] += 1
                        if quantity_row["positive_single_match_sensitivity"]:
                            quantity_counts["positive_single_match"][quantity] += 1
                        if quantity_row["positive_fragmentation_safe_sensitivity"]:
                            quantity_counts["positive_fragmentation_safe"][quantity] += 1
                gross_positive_quantities = [
                    result["quantity_shares_per_leg"]
                    for result in audit.get("quantity_results", [])
                    if result.get("positive_full_depth_gross")
                ]
                positive_minimum_quantities = [
                    result["quantity_shares_per_leg"]
                    for result in audit.get("quantity_results", [])
                    if result.get("positive_full_depth_gross")
                    and result.get("minimum_order_notional_satisfied")
                ]
                positive_minimum_shares_quantities = [
                    result["quantity_shares_per_leg"]
                    for result in audit.get("quantity_results", [])
                    if result.get("positive_full_depth_gross")
                    and result.get("minimum_order_shares_satisfied")
                ]
                positive_reported_constraints_quantities = [
                    result["quantity_shares_per_leg"]
                    for result in audit.get("quantity_results", [])
                    if result.get("positive_full_depth_gross")
                    and result.get("minimum_order_constraints_satisfied")
                ]
                positive_single_quantities = [
                    result["quantity_shares_per_leg"]
                    for result in audit.get("quantity_results", [])
                    if result.get("positive_single_match_sensitivity")
                ]
                positive_safe_quantities = [
                    result["quantity_shares_per_leg"]
                    for result in audit.get("quantity_results", [])
                    if result.get("positive_fragmentation_safe_sensitivity")
                ]
                market_books = {asset: _sanitize_book(book) for asset, book in two_books.items()}
                pair_source_hash = (
                    pair_timing.get("retry_batch_sha256")
                    if pair_timing["status"] == "recovered_by_pair_retry"
                    else pair_timing.get("initial_batch_sha256")
                )
                observations.append(
                    {
                        "market_id": row["market_id"],
                        "condition": row["condition"],
                        "outcomes": row["outcomes"],
                        "question": row["question"],
                        "categories": row["categories"],
                        "cohort_role": row["cohort_role"],
                        "selection_probability": row["selection_probability"],
                        "selection_probability_basis": row["selection_probability_basis"],
                        "selection_stratum": row.get("selection_stratum"),
                        "cohort_roles": row.get("cohort_roles", [row["cohort_role"]]),
                        "stable_control_member": row.get("stable_control_member") is True,
                        "reference_cohort_member": row.get("reference_cohort_member") is True,
                        "reference_selection_probability": row.get(
                            "reference_selection_probability"
                        ),
                        "raw_market_metadata_sha256": row["raw_market_metadata_sha256"],
                        "audit": audit,
                        "book_integrity": pair_timing,
                        "gross_positive_quantities": gross_positive_quantities,
                        "positive_minimum_notional_quantities": positive_minimum_quantities,
                        "positive_minimum_shares_quantities": positive_minimum_shares_quantities,
                        "positive_reported_constraints_quantities": (
                            positive_reported_constraints_quantities
                        ),
                        "positive_single_match_quantities": positive_single_quantities,
                        "positive_fragmentation_safe_quantities": positive_safe_quantities,
                        "books": market_books,
                        "book_source_sha256": pair_source_hash,
                    }
                )

            batch_receipts = book_collection["batch_receipts"]
            captured_ns = max(
                (receipt["received_at_ns"] for receipt in batch_receipts), default=time.time_ns()
            )
            captured = datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC)
            source_code_hash = _sha256(
                Path(__file__).read_bytes()
                + Path(__file__).with_name("opportunity_audit_v2.py").read_bytes()
                + Path(__file__).with_name("economic_feasibility_v3.py").read_bytes()
                + Path(__file__).with_name("continuous_analysis.py").read_bytes()
                + Path(__file__).with_name("analysis_catalog.py").read_bytes()
                + Path(__file__).with_name("scan_catalog.py").read_bytes()
            )
            counts = {
                "selected_markets": len(selected),
                "valid_quality_pairs": sum(bool(row["audit"]["valid"]) for row in observations),
                "invalid_reasons": dict(sorted(invalid_reasons.items())),
                "reported_update_age_bands_by_leg": {
                    side: dict(sorted(bands.items()))
                    for side, bands in update_age_bands_by_leg.items()
                },
                "reported_update_age_above_5s_by_leg": {
                    side: update_age_above_threshold_by_leg.get(side, 0) for side in ("yes", "no")
                },
                "reported_update_timestamp_skew_bands": dict(sorted(update_skew_bands.items())),
                "reported_update_timestamp_skew_above_250ms_pairs": (
                    update_skew_above_threshold_pairs
                ),
                "positive_top_gross_pairs": sum(
                    bool(row["audit"].get("positive_top_pair_gross")) for row in observations
                ),
                "positive_full_depth_gross_by_quantity": {
                    quantity: quantity_counts["positive_full_depth_gross"].get(quantity, 0)
                    for quantity in quantity_grid
                },
                "positive_minimum_notional_by_quantity": {
                    quantity: quantity_counts["positive_minimum_notional"].get(quantity, 0)
                    for quantity in quantity_grid
                },
                "positive_minimum_shares_by_quantity": {
                    quantity: quantity_counts["positive_minimum_shares"].get(quantity, 0)
                    for quantity in quantity_grid
                },
                "positive_reported_constraints_by_quantity": {
                    quantity: quantity_counts["positive_reported_constraints"].get(quantity, 0)
                    for quantity in quantity_grid
                },
                "positive_single_match_fee_sensitivity_by_quantity": {
                    quantity: quantity_counts["positive_single_match"].get(quantity, 0)
                    for quantity in quantity_grid
                },
                "positive_fragmentation_safe_fee_sensitivity_by_quantity": {
                    quantity: quantity_counts["positive_fragmentation_safe"].get(quantity, 0)
                    for quantity in quantity_grid
                },
                "fee_unavailable_pairs": sum(
                    any(
                        result["fee_status"] not in {"verified_taker_curve", "verified_disabled"}
                        for result in row["audit"].get("quantity_results", [])
                    )
                    for row in observations
                    if row["audit"]["valid"]
                ),
            }
            report: dict[str, Any] = {
                "schema_version": 1,
                "analysis_version": VERSION,
                "discovery_frame_protocol": DISCOVERY_FRAME_PROTOCOL,
                "quantity_grid": list(quantity_grid),
                "captured_at_utc": captured.isoformat(),
                "captured_ns": captured_ns,
                "coverage_kind": "intermittent_public_snapshots",
                "collection_bounds": {
                    "target_markets": target_markets,
                    "maximum_markets": MAX_MARKETS,
                    "gamma_queries_per_scan": DISCOVERY_QUERIES,
                    "gamma_page_limit": DISCOVERY_LIMIT,
                    "maximum_public_read_calls_per_scan": MAX_REQUESTS_PER_SCAN,
                    "maximum_public_http_attempts_per_scan": MAX_PUBLIC_HTTP_ATTEMPTS_PER_SCAN,
                    "maximum_retries_per_public_read": MAX_RETRIES_PER_PUBLIC_READ,
                    "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
                    "maximum_response_bytes": MAX_RESPONSE_BYTES,
                    "minimum_request_interval_seconds": request_interval_seconds,
                    "maximum_root_bytes": MAX_ROOT_BYTES,
                },
                "source_code_sha256": source_code_hash,
                "discovery": discovery,
                "pipeline_timing": {
                    "scan_started_at_ns": scan_started_ns,
                    "discovery_started_at_ns": discovery_ns,
                    "market_selection_completed_at_ns": selection_completed_ns,
                    "public_acquisition_completed_at_ns": captured_ns,
                    "local_request_timing_source": "monotonic clock per HTTP logical request; attempt-level wall and monotonic timestamps are retained",
                    "book_timestamp_clock_offset": "unknown_exchange_side_clock_offset",
                    "timestamp_comparison_basis": "reported CLOB timestamp versus local wall-clock response parse completion",
                },
                "selection": {
                    "plan": selection_plan,
                    "selected_markets": [
                        {
                            key: row.get(key)
                            for key in (
                                "market_id",
                                "condition",
                                "question",
                                "cohort_role",
                                "categories",
                                "liquidity_usdc",
                                "liquidity_band",
                                "volume_24h_usdc",
                                "end_ns",
                                "expiry_band",
                                "spread_per_share",
                                "spread_band",
                                "primary_category",
                                "primary_category_source",
                                "selection_probability",
                                "selection_probability_basis",
                                "selection_stratum",
                                "reference_selection_probability",
                                "stable_control_member",
                                "reference_cohort_member",
                                "raw_market_metadata_sha256",
                            )
                        }
                        for row in selected
                    ],
                },
                "source_requests": {
                    "public_http_attempts": client.request_attempts,
                    "gamma_pages": discovery["queries"],
                    "clob_books": batch_receipts[0] if batch_receipts else None,
                    "clob_book_batches": batch_receipts,
                    "clob_initial_integrity": book_collection["initial_integrity"],
                    "clob_retry_integrity": book_collection["retry_integrity"],
                    "clob_retry_failure": book_collection["retry_failure"],
                    "clob_retry_pair_count": book_collection["retry_pair_count"],
                    "selected_asset_identity_collisions": {
                        "market_ids": book_collection["collision_market_ids"],
                        "asset_ids": book_collection["collision_asset_ids"],
                    },
                    "request_attempt_log": client.request_log,
                },
                "counts": counts,
                "market_observations": observations,
                "limitations": [
                    "These snapshots are intermittent and do not establish quote lifetime or continuous coverage.",
                    "The query-response union is bounded and selected by public API query filters; it is not the full venue universe.",
                    "The per-scan reference_random cohort is a simple random sample from the current eligible bounded query union after available frozen controls are removed; its probability is conditional on that union and does not estimate venue-wide prevalence.",
                    "Rotating stratified probabilities condition on available frozen controls, the independent reference draw, and the current query union; reference and targeted roles remain explicit.",
                    "The snapshot-change activity stratum measures changes between sampled snapshots only; it is not a WebSocket update-rate estimate.",
                    "Reported book timestamps and batch receipt time are retained separately; a batch response does not verify atomicity, venue sequence ordering, or upstream queue age.",
                    "Displayed depth and hypothetical fee sensitivities do not establish order arrival, persistence, fills, recovery, or profitability.",
                    "The opportunity audit supports same-condition V1 binary pairs only; no cross-condition or multi-outcome payoff is inferred.",
                ],
                "orders_submitted": False,
                "authenticated_requests": False,
            }
            # Include a compact content digest as lineage; the final file is compressed and immutable.
            evidence_material = {
                "gamma_response_hashes": [
                    page["response_sha256"]
                    for page in discovery["queries"]
                    if isinstance(page.get("response_sha256"), str)
                ],
                "clob_response_sha256": [receipt["response_sha256"] for receipt in batch_receipts],
                "source_code_sha256": source_code_hash,
                "captured_ns": captured_ns,
                "selection_seed": seed,
                "sequence": sequence,
            }
            report["snapshot_evidence_sha256"] = _sha256(_canonical(evidence_material))
            report["scan_id"] = (
                f"scan-{captured.strftime('%Y%m%dT%H%M%SZ')}-{report['snapshot_evidence_sha256'][:12]}"
            )
            snapshot_rel = f"snapshots/{report['scan_id']}.json.gz"
            report["snapshot_file"] = snapshot_rel
            # Set the finalized source path on every surfaced candidate.
            for observation in report["market_observations"]:
                if observation["gross_positive_quantities"]:
                    observation["candidate_source"] = {
                        "snapshot_file": snapshot_rel,
                        "snapshot_evidence_sha256": report["snapshot_evidence_sha256"],
                        "book_source_sha256": observation["book_source_sha256"],
                        "raw_market_metadata_sha256": observation["raw_market_metadata_sha256"],
                    }
            report["pipeline_timing"]["snapshot_serialization_started_at_ns"] = time.time_ns()
            compressed = gzip.compress(_canonical(report), compresslevel=6, mtime=0)
            if len(compressed) > MAX_RESPONSE_BYTES:
                raise ValueError("Finalized observation snapshot exceeds its artifact bound")
            if total_bytes + len(compressed) + MAX_ANALYSIS_RESERVE_BYTES >= MAX_ROOT_BYTES:
                raise ValueError(
                    "Observatory evidence budget would be exceeded; no scan was committed"
                )
            final_snapshot = root / snapshot_rel
            persistence_started_ns = time.time_ns()
            with final_snapshot.open("xb") as handle:
                handle.write(compressed)
                handle.flush()
                os.fsync(handle.fileno())
            fd = os.open(final_snapshot.parent, os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            persisted_ns = time.time_ns()
            persistence_status = {
                "scan_id": report["scan_id"],
                "snapshot_file": snapshot_rel,
                "snapshot_evidence_sha256": report["snapshot_evidence_sha256"],
                "snapshot_file_sha256": _sha256(compressed),
                "snapshot_persistence_started_at_ns": persistence_started_ns,
                "snapshot_persisted_at_ns": persisted_ns,
                "response_to_persistence_delay_ms": (persisted_ns - captured_ns) / 1_000_000,
                "orders_submitted": False,
                "authenticated_requests": False,
            }
            catalog_status: dict[str, Any]
            try:
                current_index = record_catalog_snapshot(root, report, final_snapshot)
                catalog_reconciliation = reconcile_snapshot_catalog(root, limit=10)
                catalog_status = {
                    "status": "indexed",
                    "current_snapshot": current_index,
                    "reconciliation": catalog_reconciliation,
                }
            except Exception as error:
                catalog_status = {
                    "status": "indexing_error",
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                }
            persistence_status["catalog_index"] = catalog_status
            try:
                continuous_analysis_full = update_finalized_analysis(root, max_pending=10)
                cumulative = continuous_analysis_full.get("cumulative", {})
                compact_fields = (
                    "snapshot_count",
                    "selected_market_observations",
                    "quality_valid_pairs",
                    "legacy_freshness_valid_pairs",
                    "invalid_pairs",
                    "positive_top_gross_pairs",
                    "candidate_event_count",
                    "top_edge_state_count",
                    "minimum_top_edge_per_share",
                    "maximum_top_edge_per_share",
                )
                continuous_analysis = {
                    "status": continuous_analysis_full.get("status"),
                    "analysis_version": continuous_analysis_full.get("analysis_version"),
                    "measurement_status": continuous_analysis_full.get("measurement_status"),
                    "processed_snapshot_count": continuous_analysis_full.get(
                        "processed_snapshot_count"
                    ),
                    "pending_snapshot_count": continuous_analysis_full.get(
                        "pending_snapshot_count"
                    ),
                    "last_processed_snapshot_file": continuous_analysis_full.get(
                        "last_processed_snapshot_file"
                    ),
                    "summary_file": "research-summary.json",
                    "analysis_summary_sha256": continuous_analysis_full.get(
                        "analysis_summary_sha256"
                    ),
                    "cumulative_counts": {field: cumulative.get(field) for field in compact_fields},
                }
                persistence_status["continuous_analysis"] = {
                    "status": continuous_analysis["status"],
                    "measurement_status": continuous_analysis["measurement_status"],
                    "processed_snapshot_count": continuous_analysis["processed_snapshot_count"],
                    "pending_snapshot_count": continuous_analysis["pending_snapshot_count"],
                    "analysis_version": continuous_analysis["analysis_version"],
                }
            except Exception as error:
                continuous_analysis = {
                    "status": "analysis_error",
                    "analysis_version": None,
                    "processed_snapshot_count": None,
                    "pending_snapshot_count": None,
                    "summary_file": "research-summary.json",
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                }
                persistence_status["continuous_analysis"] = {
                    "status": "analysis_error",
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                }
            measurement_pilot = {
                "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
                "protocol_version": "veritas-coverage-pilot-v1",
                "status": "not_advanced_analysis_protocol_changed",
                "reason": "The frozen pilot expects finalized v4 events; the v6 independent economic audit requires a separately versioned pilot protocol.",
                "orders_submitted": False,
                "authenticated_requests": False,
            }
            measurement_pilot_v2 = {
                "study_id": "VERITAS-M2-COVERAGE-PILOT-002",
                "protocol_version": "veritas-coverage-pilot-v2",
                "status": "not_advanced_analysis_protocol_changed",
                "reason": "The frozen pilot expects finalized v4 events; the v6 independent economic audit requires a separately versioned pilot protocol.",
                "orders_submitted": False,
                "authenticated_requests": False,
            }
            report["measurement_pilot_v2"] = measurement_pilot_v2
            report["measurement_pilot"] = measurement_pilot
            try:
                _atomic_json(
                    root / "pipeline-status" / f"{report['scan_id']}.json",
                    persistence_status,
                )
            except OSError as error:
                persistence_status["status_artifact_write_error"] = str(error)[:300]
            latest = _summary(report)
            latest["continuous_analysis"] = continuous_analysis
            latest["catalog_index"] = catalog_status
            latest["measurement_pilot"] = measurement_pilot
            latest["measurement_pilot_v2"] = measurement_pilot_v2
            try:
                _atomic_json(
                    root / "latest-summary.json",
                    latest,
                    maximum=MAX_LATEST_SUMMARY_BYTES,
                )
            except (OSError, ValueError) as error:
                persistence_status["latest_summary_write_error"] = str(error)[:300]
                try:
                    _atomic_json(
                        root / "pipeline-status" / f"{report['scan_id']}.json",
                        persistence_status,
                    )
                except OSError:
                    pass
            for observation in observations:
                books = observation["books"]
                state_hash = _book_state_hash(books, observation)
                if not state_hash:
                    continue
                prior = history.setdefault(observation["market_id"], [])
                prior.append({"captured_ns": captured_ns, "state_hash": state_hash})
                history[observation["market_id"]] = prior[-12:]
            if len(history) > MAX_ACTIVITY_MARKETS:
                keep_ids = sorted(
                    history,
                    key=lambda market_id: max(
                        (
                            row.get("captured_ns", 0)
                            for row in history[market_id]
                            if isinstance(row, dict)
                        ),
                        default=0,
                    ),
                )[-MAX_ACTIVITY_MARKETS:]
                history = {market_id: history[market_id] for market_id in keep_ids}
            _atomic_json(
                state_path,
                {
                    "version": VERSION,
                    "next_sequence": sequence + 1,
                    "last_scan_id": report["scan_id"],
                    "last_captured_ns": captured_ns,
                    "snapshot_history": history,
                },
            )
            return report
        finally:
            await client.close()


def _sanitize_book(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": str(raw.get("market") or "").casefold(),
        "asset_id": str(raw.get("asset_id") or raw.get("assetId") or ""),
        "timestamp": raw.get("timestamp"),
        "hash": str(raw.get("hash") or ""),
        "bids": raw.get("bids") if isinstance(raw.get("bids"), list) else [],
        "asks": raw.get("asks") if isinstance(raw.get("asks"), list) else [],
        "min_order_size": str(raw.get("min_order_size") or ""),
        "tick_size": str(raw.get("tick_size") or ""),
        "neg_risk": raw.get("neg_risk"),
    }
