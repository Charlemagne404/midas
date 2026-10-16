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
from .coverage_pilot import record_coverage_pilot
from .opportunity_audit import audit_pair_snapshot, normalize_market

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
VERSION = "veritas-public-observatory-v2"
DISCOVERY_FRAME_PROTOCOL = "stratified-gamma-page-rotation-v2"
CONTROL_COHORT_VERSION = "veritas-control-cohort-v1"
LEGACY_CONTROL_COHORT_VERSION = "veritas-public-observatory-v1"
DISCOVERY_LIMIT = 50
DISCOVERY_QUERIES = 6
DISCOVERY_OFFSET_RANGE = 1_000
DISCOVERY_OFFSET_BUCKET_SECONDS = 30 * 60
DISCOVERY_OFFSET_BUCKET_NS = DISCOVERY_OFFSET_BUCKET_SECONDS * 1_000_000_000
MAX_RESPONSE_BYTES = 48 * 1024**2
MAX_REQUESTS_PER_SCAN = DISCOVERY_QUERIES + 1
MAX_RETRIES_PER_PUBLIC_READ = 1
MAX_PUBLIC_HTTP_ATTEMPTS_PER_SCAN = MAX_REQUESTS_PER_SCAN * (MAX_RETRIES_PER_PUBLIC_READ + 1)
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_MARKETS = 50
DEFAULT_MARKETS = 40
DEFAULT_CONTROL_MARKETS = 8
DEFAULT_QUANTITIES = ("5", "10", "20", "50", "100")
MAX_ROOT_BYTES = 1024**3
MAX_STATE_BYTES = 8 * 1024**2
MAX_ANALYSIS_RESERVE_BYTES = 16 * 1024**2
MAX_ACTIVITY_MARKETS = 2_000
DEFAULT_INTERVAL_SECONDS = 30 * 60
REQUEST_INTERVAL_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 5.0
REPORTED_UPDATE_AGE_DIAGNOSTIC_THRESHOLD_MS = 5_000
REPORTED_UPDATE_SKEW_DIAGNOSTIC_THRESHOLD_MS = 250
DEFAULT_SEED = 20261015
PHASES = ("liquidity", "expiry", "category", "spread", "snapshot_change")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    data = _canonical(value)
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
        self.lock = asyncio.Lock()

    async def _send(
        self,
        method: str,
        base: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> tuple[Any, bytes, int, int, int]:
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
        for attempt in range(MAX_RETRIES_PER_PUBLIC_READ + 1):
            started_ns = time.time_ns()
            if first_started_ns is None:
                first_started_ns = started_ns
            self.request_attempts += 1
            try:
                async with self.client.stream(
                    method,
                    base + path,
                    params=params,
                    json=json_body,
                ) as response:
                    if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                        try:
                            delay = float(response.headers.get("Retry-After", "1"))
                        except ValueError:
                            delay = 1.0
                        await response.aclose()
                        await asyncio.sleep(min(MAX_RETRY_DELAY_SECONDS, max(0.2, delay)))
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
                    response.raise_for_status()
                    parsed = json.loads(body)
                    received_ns = time.time_ns()
                    return parsed, body, first_started_ns, received_ns, attempt + 1
            except (httpx.HTTPError, json.JSONDecodeError) as error:
                last_error = error
                if attempt == 0:
                    await asyncio.sleep(0.5)
        raise RuntimeError("Public read retry budget exhausted") from last_error

    async def discover(self, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        value, body, started_ns, received_ns, attempt_count = await self._send(
            "GET", GAMMA, "/markets", params=params
        )
        if not isinstance(value, list) or len(value) > DISCOVERY_LIMIT:
            raise ValueError("Gamma returned an unexpected or oversized market page")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError("Gamma market page contains a non-object row")
        return value, {
            "requested_at_ns": started_ns,
            "received_at_ns": received_ns,
            "request_attempts": attempt_count,
            "response_sha256": _sha256(body),
            "response_bytes": len(body),
            "response_payload": body.decode("utf-8"),
        }

    async def books(self, asset_ids: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if (
            not asset_ids
            or len(asset_ids) > MAX_MARKETS * 2
            or len(set(asset_ids)) != len(asset_ids)
        ):
            raise ValueError("Invalid or oversized paired-book request")
        body = [{"token_id": asset_id} for asset_id in asset_ids]
        value, wire, started_ns, received_ns, attempt_count = await self._send(
            "POST", CLOB, "/books", json_body=body
        )
        if not isinstance(value, list) or len(value) > len(asset_ids):
            raise ValueError("CLOB returned an unexpected or oversized book batch")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError("CLOB book batch contains a non-object row")
        return value, {
            "requested_at_ns": started_ns,
            "received_at_ns": received_ns,
            "request_attempts": attempt_count,
            "request_asset_count": len(asset_ids),
            "response_book_count": len(value),
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
    for query_id, params in _query_plan(now_ns, seed):
        page, receipt = await client.discover(params)
        response_candidate_count += len(page)
        query_reports.append(
            {"query_id": query_id, "parameters": params, "candidate_count": len(page), **receipt}
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
    seed: int,
    sequence: int,
    frozen_control_ids: list[str] | None = None,
    history: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    if not 1 <= target <= MAX_MARKETS or not 0 <= control_count <= target:
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
    remaining_rows = [row for row in eligible if row["market_id"] not in set(active_controls)]
    rotation_target = min(max(0, target - len(active_controls)), len(remaining_rows))
    phase = PHASES[(sequence - 1) % len(PHASES)]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in remaining_rows:
        groups[_stratum(row, phase, history)].append(row)
    quotas = _allocate_quotas(groups, rotation_target)
    rotation: list[dict[str, Any]] = []
    probabilities: dict[str, dict[str, Any]] = {}
    rotation_seed = seed + sequence * 1_000_003
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
                    "conditional on the pre-frozen stable control cohort"
                ),
                "selection_stratum": probability["stratum"],
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
        "rotation_population_after_controls": len(remaining_rows),
        "rotation_target": rotation_target,
        "rotation_strata": {
            stratum: {"population": len(groups[stratum]), "quota": quotas[stratum]}
            for stratum in sorted(groups)
        },
        "selected_count": len(cohort),
        "selection_excludes_price_edge": True,
        "probability_scope": "conditional on the bounded query-response union and frozen stable control IDs",
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
            "rotating_markets": sum(
                row["cohort_role"] == "rotating_stratified" for row in selected
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
            "positive_single_match_fee_sensitivity_by_quantity": report["counts"][
                "positive_single_match_fee_sensitivity_by_quantity"
            ],
            "positive_fragmentation_safe_fee_sensitivity_by_quantity": report["counts"][
                "positive_fragmentation_safe_fee_sensitivity_by_quantity"
            ],
            "fee_unavailable_pairs": report["counts"]["fee_unavailable_pairs"],
        },
        "market_observations": [
            {
                "market_id": row["market_id"],
                "question": row["question"],
                "cohort_role": row["cohort_role"],
                "valid": row["audit"]["valid"],
                "reason": row["audit"].get("reason"),
                "top_pair_gross_edge_per_share": row["audit"].get("top_pair_gross_edge_per_share"),
                "gross_positive_quantities": row["gross_positive_quantities"],
                "positive_minimum_notional_quantities": row["positive_minimum_notional_quantities"],
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
        "coverage_kind": "intermittent_public_snapshots",
        "orders_submitted": False,
        "limitations": report["limitations"],
    }


async def run_scan(
    root: Path,
    *,
    target_markets: int = DEFAULT_MARKETS,
    control_count: int = DEFAULT_CONTROL_MARKETS,
    seed: int = DEFAULT_SEED,
    quantity_grid: tuple[str, ...] = DEFAULT_QUANTITIES,
    transport: httpx.AsyncBaseTransport | None = None,
    request_interval_seconds: float = REQUEST_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Run one atomic market-universe and paired-book snapshot cycle."""
    if not 30 <= target_markets <= MAX_MARKETS or not 0 <= control_count <= target_markets:
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
                raise RuntimeError(
                    "No eligible V1 binary markets were found in the bounded query union"
                )
            selected, selection_plan, control_ids = select_cohort(
                eligible,
                target=target_markets,
                control_count=control_count,
                seed=seed,
                sequence=sequence,
                frozen_control_ids=frozen_control_ids,
                history=history,
            )
            if not selected:
                raise RuntimeError("No markets were selected from the eligible bounded universe")
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

            requested_assets = [row["outcomes"][side] for row in selected for side in ("yes", "no")]
            raw_books, book_receipt = await client.books(requested_assets)
            books_by_asset: dict[str, dict[str, Any]] = {}
            duplicate_book_assets: set[str] = set()
            for raw in raw_books:
                asset = str(raw.get("asset_id") or raw.get("assetId") or "")
                if not asset or asset in books_by_asset:
                    duplicate_book_assets.add(asset or "missing_asset_id")
                    continue
                books_by_asset[asset] = raw
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
                "positive_single_match": Counter(),
                "positive_fragmentation_safe": Counter(),
            }
            for row in selected:
                two_books: dict[str, dict[str, Any]] = {}
                for side in ("yes", "no"):
                    asset = row["outcomes"][side]
                    if asset in books_by_asset:
                        two_books[asset] = books_by_asset[asset]
                audit: dict[str, Any]
                if duplicate_book_assets:
                    audit = {
                        "valid": False,
                        "reason": "duplicate_or_missing_asset_response",
                        "quantities": [],
                    }
                else:
                    audit = audit_pair_snapshot(
                        row,
                        two_books,
                        captured_ns=book_receipt["received_at_ns"],
                        batch_started_ns=book_receipt["requested_at_ns"],
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
                        "raw_market_metadata_sha256": row["raw_market_metadata_sha256"],
                        "audit": audit,
                        "gross_positive_quantities": gross_positive_quantities,
                        "positive_minimum_notional_quantities": positive_minimum_quantities,
                        "positive_single_match_quantities": positive_single_quantities,
                        "positive_fragmentation_safe_quantities": positive_safe_quantities,
                        "books": market_books,
                        "book_source_sha256": book_receipt["response_sha256"],
                    }
                )

            captured_ns = book_receipt["received_at_ns"]
            captured = datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC)
            source_code_hash = _sha256(
                Path(__file__).read_bytes()
                + Path(__file__).with_name("opportunity_audit.py").read_bytes()
                + Path(__file__).with_name("economic_feasibility_v3.py").read_bytes()
                + Path(__file__).with_name("continuous_analysis.py").read_bytes()
                + Path(__file__).with_name("coverage_pilot.py").read_bytes()
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
                                "raw_market_metadata_sha256",
                            )
                        }
                        for row in selected
                    ],
                },
                "source_requests": {
                    "public_http_attempts": client.request_attempts,
                    "gamma_pages": discovery["queries"],
                    "clob_books": book_receipt,
                },
                "counts": counts,
                "market_observations": observations,
                "limitations": [
                    "These snapshots are intermittent and do not establish quote lifetime or continuous coverage.",
                    "The query-response union is bounded and selected by public API query filters; it is not the full venue universe.",
                    "Selection probabilities are conditional on that query union; rotating probabilities condition on the frozen control cohort.",
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
                "gamma_response_hashes": [page["response_sha256"] for page in discovery["queries"]],
                "clob_response_sha256": book_receipt["response_sha256"],
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
            compressed = gzip.compress(_canonical(report), compresslevel=6, mtime=0)
            if len(compressed) > MAX_RESPONSE_BYTES:
                raise ValueError("Finalized observation snapshot exceeds its artifact bound")
            if total_bytes + len(compressed) + MAX_ANALYSIS_RESERVE_BYTES >= MAX_ROOT_BYTES:
                raise ValueError(
                    "Observatory evidence budget would be exceeded; no scan was committed"
                )
            final_snapshot = root / snapshot_rel
            with final_snapshot.open("xb") as handle:
                handle.write(compressed)
                handle.flush()
                os.fsync(handle.fileno())
            fd = os.open(final_snapshot.parent, os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            continuous_analysis = update_finalized_analysis(root)
            try:
                measurement_pilot = record_coverage_pilot(root, report)
            except Exception as error:  # keep the public observation writer authoritative
                measurement_pilot = {
                    "study_id": "VERITAS-M2-COVERAGE-PILOT-001",
                    "protocol_version": "veritas-coverage-pilot-v1",
                    "status": "recording_error",
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                    "orders_submitted": False,
                    "authenticated_requests": False,
                }
            report["measurement_pilot"] = measurement_pilot
            latest = _summary(report)
            latest["continuous_analysis"] = continuous_analysis
            latest["measurement_pilot"] = measurement_pilot
            _atomic_json(root / "latest-summary.json", latest)
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
