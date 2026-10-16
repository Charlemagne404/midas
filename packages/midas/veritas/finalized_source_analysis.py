"""Bounded, resumable analysis of finalized Reality Mission 2 source segments.

This reader never opens ``.open`` files and never imports or controls the Reality
writer. Its input campaign and source root are pinned for the live operation.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, cast

from midas.reality.execution_research import fee_rate
from midas.reality.research_measurements import pair_quality
from midas.reality.research_schema import digest
from midas.reality.shadow_campaign import verify as verify_campaign
from midas.reality.shadow_source import Context
from midas.reality.shadow_worker import spec_for
from midas.reality.storage import MAGIC, file_hash, records

from .economics import walk_asks

VERSION = "veritas-finalized-reality-source-analysis-v1"
DEFAULT_CAMPAIGN_PATH = Path(
    "/home/charlie/midas-reality/data/research/reality/forward/mission2/campaign.json"
)
DEFAULT_CAMPAIGN_SHA256 = "aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5"
DEFAULT_CAMPAIGN_ID = "adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46"
DEFAULT_SOURCE_ROOT = Path("/home/charlie/midas-reality/data/recordings/reality")

MAX_CAMPAIGN_BYTES = 2_000_000
MAX_CATALOG_BYTES = 128 * 1024
MAX_CATALOG_TOTAL_BYTES = 32 * 1024**2
MAX_CATALOG_SEGMENTS = 100_000
MAX_SEGMENT_BYTES = 16 * 1024**2
MAX_SEGMENTS_PER_RUN = 128
MAX_SOURCE_BYTES_PER_RUN = 32 * 1024**2
MAX_STATE_BYTES = 24 * 1024**2
MAX_SUMMARY_BYTES = 4 * 1024**2
MAX_EVENT_BYTES = 256 * 1024
MAX_EVENTS_BYTES = 256 * 1024**2
MAX_MARKETS = 20_000
MAX_EDGE_BINS = 50_000
MAX_RECENT_MARKETS = 20

_SEGMENT_CATALOG = re.compile(r"(?P<first>[0-9]{20})-(?P<uuid>[0-9a-f]{32})\.json\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any], *, maximum: int) -> int:
    data = _canonical(value)
    if len(data) > maximum:
        raise ValueError(f"Analysis artifact exceeds its bound: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return len(data)


def _sealed(value: dict[str, Any], key: str) -> dict[str, Any]:
    result = dict(value)
    result[key] = _sha256(_canonical(value))
    return result


def _read_sealed(path: Path, *, maximum: int, key: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f"Unsafe or oversized source-analysis artifact: {path.name}")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid source-analysis artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Invalid source-analysis object: {path.name}")
    stored = value.pop(key, None)
    if not isinstance(stored, str) or stored != _sha256(_canonical(value)):
        raise ValueError(f"Source-analysis artifact digest mismatch: {path.name}")
    value[key] = stored
    return value


def _code_identity() -> dict[str, str]:
    reality = Path(__file__).parents[1] / "reality"
    return {
        "finalized_source_analysis.py": file_hash(Path(__file__)),
        "scripts/veritas_source_analysis.py": file_hash(
            Path(__file__).parents[3] / "scripts" / "veritas_source_analysis.py"
        ),
        "economics.py": file_hash(Path(__file__).with_name("economics.py")),
        **{
            f"reality/{name}": file_hash(reality / name)
            for name in (
                "execution_research.py",
                "reconstruction.py",
                "research_measurements.py",
                "research_schema.py",
                "shadow_campaign.py",
                "shadow_source.py",
                "shadow_worker.py",
                "storage.py",
            )
        },
    }


def _read_campaign(
    campaign_path: Path,
    *,
    expected_campaign_sha256: str,
    expected_campaign_id: str | None,
    expected_source_root: Path | None,
) -> tuple[dict[str, Any], str, Path]:
    if campaign_path.is_symlink() or not campaign_path.is_file():
        raise ValueError("Pinned Mission 2 campaign is missing or unsafe")
    if campaign_path.stat().st_size > MAX_CAMPAIGN_BYTES:
        raise ValueError("Pinned Mission 2 campaign exceeds its bound")
    campaign_sha256 = file_hash(campaign_path)
    if campaign_sha256 != expected_campaign_sha256:
        raise ValueError("Pinned Mission 2 campaign file hash changed")
    try:
        plan = json.loads(campaign_path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError("Pinned Mission 2 campaign cannot be read") from error
    if not isinstance(plan, dict):
        raise ValueError("Pinned Mission 2 campaign is not an object")
    verify_campaign(plan)
    campaign_id = plan.get("campaign_id")
    if expected_campaign_id is not None and campaign_id != expected_campaign_id:
        raise ValueError("Pinned Mission 2 campaign identity changed")
    identity = plan.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("Pinned Mission 2 campaign identity is invalid")
    raw_value = identity.get("raw_root")
    if not isinstance(raw_value, str):
        raise ValueError("Pinned Mission 2 campaign has no source root")
    raw_root = Path(raw_value)
    expected = expected_source_root.resolve() if expected_source_root else raw_root.resolve()
    if raw_root.is_symlink() or raw_root.resolve() != expected or not raw_root.is_dir():
        raise ValueError("Mission 2 campaign source root differs from the pinned root")
    return plan, campaign_sha256, raw_root


def _read_catalogs(raw_root: Path) -> list[dict[str, Any]]:
    """Read only finalized sidecars; catalog hashing is cheap and detects prefix edits."""
    entries: list[tuple[str, Path]] = []
    try:
        with os.scandir(raw_root) as iterator:
            for entry in iterator:
                match = _SEGMENT_CATALOG.fullmatch(entry.name)
                if match:
                    entries.append((entry.name, Path(entry.path)))
                elif entry.name[:1].isdigit() and entry.name.endswith(".json"):
                    raise ValueError("Malformed numeric finalized Reality catalog name")
    except OSError as error:
        raise ValueError("Finalized Reality source directory cannot be scanned") from error
    entries.sort(key=lambda item: item[0])
    if len(entries) > MAX_CATALOG_SEGMENTS:
        raise ValueError("Finalized Reality source catalog count exceeds its bound")

    result: list[dict[str, Any]] = []
    total_catalog_bytes = 0
    prior_last = 0
    for name, sidecar in entries:
        if sidecar.is_symlink() or not sidecar.is_file():
            raise ValueError("Finalized Reality catalog sidecar is unsafe")
        size = sidecar.stat().st_size
        if size > MAX_CATALOG_BYTES:
            raise ValueError("Finalized Reality catalog sidecar exceeds its bound")
        total_catalog_bytes += size
        if total_catalog_bytes > MAX_CATALOG_TOTAL_BYTES:
            raise ValueError("Finalized Reality catalog set exceeds its bound")
        try:
            info = json.loads(sidecar.read_text())
        except (OSError, ValueError) as error:
            raise ValueError(f"Invalid finalized Reality catalog: {name}") from error
        if not isinstance(info, dict):
            raise ValueError(f"Invalid finalized Reality catalog: {name}")
        file_name = name.removesuffix(".json") + ".seg"
        kinds = info.get("kinds")
        first = cast(int, info.get("first"))
        last = cast(int, info.get("last"))
        count = cast(int, info.get("count"))
        segment_bytes = cast(int, info.get("bytes"))
        if (
            set(info)
            != {"schema_version", "file", "sha256", "bytes", "first", "last", "count", "kinds"}
            or info.get("schema_version") != 1
            or info.get("file") != file_name
            or not isinstance(info.get("sha256"), str)
            or _SHA256.fullmatch(info["sha256"]) is None
            or not all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in (first, last, count, segment_bytes)
            )
            or not isinstance(kinds, dict)
            or sum(value for value in kinds.values() if isinstance(value, int) and value >= 0)
            != count
            or any(
                not isinstance(kind, str)
                or not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for kind, value in kinds.items()
            )
        ):
            raise ValueError(f"Malformed or non-contiguous finalized Reality catalog: {name}")
        if count == 0:
            if first != 0 or last != 0 or segment_bytes != len(MAGIC) or kinds:
                raise ValueError(f"Malformed empty finalized Reality catalog: {name}")
        elif (
            first != prior_last + 1
            or last != first + count - 1
            or segment_bytes <= len(MAGIC)
            or name[:20] != f"{first:020d}"
        ):
            raise ValueError(f"Non-contiguous finalized Reality catalog: {name}")
        segment_path = raw_root / file_name
        if segment_path.is_symlink() or not segment_path.is_file():
            raise ValueError(f"Finalized Reality segment is missing or unsafe: {file_name}")
        try:
            if segment_path.stat().st_size != segment_bytes:
                raise ValueError(
                    f"Finalized Reality segment size differs from catalog: {file_name}"
                )
        except OSError as error:
            raise ValueError(
                f"Finalized Reality segment cannot be inspected: {file_name}"
            ) from error
        result.append(info)
        if count:
            prior_last = last
    return result


def _prefix_hash(catalogs: list[dict[str, Any]], count: int) -> str:
    chain = bytes(32)
    for info in catalogs[:count]:
        chain = hashlib.sha256(chain + _canonical(info)).digest()
    return chain.hex()


def _new_cumulative() -> dict[str, Any]:
    return {
        "raw_records_replayed": 0,
        "record_kinds": {},
        "verified_source_checkpoints": 0,
        "campaign_window_ns": None,
        "source_receipt_window_ns": {"first": None, "last": None},
        "period_record_kinds": {},
        "gap_reasons_in_window": {},
        "period_frame_records": 0,
        "frames_excluded_unsupported_producer": 0,
        "frames_excluded_unsupported_reconstruction": 0,
        "receiver_clock_regression_frames": 0,
        "touched_market_frame_states": 0,
        "quality_valid_states": 0,
        "quality_invalid_reason_counts": {},
        "positive_top_ask_pair_states": 0,
        "quantity_requested": None,
        "quantity_depth_complete_states": 0,
        "positive_top_with_quantity_depth_states": 0,
        "positive_full_depth_pre_fee_states": 0,
        "positive_full_depth_minimum_notional_satisfied_states": 0,
        "fee_regime_available_states": 0,
        "fee_regime_unavailable_states": 0,
        "top_edge_histogram": {},
        "markets": {},
    }


def _increment(mapping: dict[str, int], key: str, amount: int = 1) -> None:
    mapping[key] = int(mapping.get(key, 0)) + amount


def _increment_market(cumulative: dict[str, Any], market: dict[str, Any], field: str) -> None:
    market[field] = int(market.get(field, 0)) + 1
    cumulative[field] = int(cumulative.get(field, 0)) + 1


def _edge_summary(histogram: dict[str, int]) -> dict[str, Any] | None:
    if not histogram:
        return None
    values = sorted((Decimal(edge), count) for edge, count in histogram.items())
    total = sum(count for _, count in values)

    def nearest_rank(fraction: Decimal) -> str:
        target = max(1, int((fraction * total).to_integral_value(rounding=ROUND_CEILING)))
        running = 0
        for value, count in values:
            running += count
            if running >= target:
                return str(value)
        raise AssertionError("Edge histogram count is inconsistent")

    return {
        "count": total,
        "minimum": str(values[0][0]),
        "p25_nearest_rank": nearest_rank(Decimal("0.25")),
        "median_nearest_rank": nearest_rank(Decimal("0.50")),
        "p75_nearest_rank": nearest_rank(Decimal("0.75")),
        "maximum": str(values[-1][0]),
        "positive_count": sum(count for value, count in values if value > 0),
    }


def _market_row(cumulative: dict[str, Any], condition: str, market_id: str) -> dict[str, Any]:
    markets: dict[str, Any] = cumulative["markets"]
    item = markets.get(condition)
    if item is None:
        if len(markets) >= MAX_MARKETS:
            raise ValueError("Distinct source market count exceeded its bound")
        item = {
            "market_id": market_id,
            "condition": condition,
            "touched_market_frame_states": 0,
            "quality_valid_states": 0,
            "quality_invalid_states": 0,
            "positive_top_ask_pair_states": 0,
            "quantity_depth_complete_states": 0,
            "positive_full_depth_pre_fee_states": 0,
            "positive_full_depth_minimum_notional_satisfied_states": 0,
            "fee_regime_available_states": 0,
            "fee_regime_unavailable_states": 0,
            "quality_reasons": {},
        }
        markets[condition] = item
    elif item["market_id"] != market_id:
        raise ValueError("A source condition changed market identity")
    return item


def _consume_record(
    record: dict[str, Any],
    ref: dict[str, Any],
    context: Context,
    cumulative: dict[str, Any],
    *,
    identity: dict[str, Any],
    spec: Any,
    quantity: Decimal,
) -> tuple[int, int, int]:
    """Consume one record, returning in-window frame/touched/valid counts for the event."""
    kind = record["kind"]
    cumulative["raw_records_replayed"] += 1
    _increment(cumulative["record_kinds"], kind)
    if kind == "checkpoint":
        cumulative["verified_source_checkpoints"] += 1
    now_ns = record["received_ns"]
    start_ns, end_ns = identity["start_ns"], identity["end_ns"]
    in_period = start_ns <= now_ns < end_ns
    if in_period:
        _increment(cumulative["period_record_kinds"], kind)
        window = cumulative["source_receipt_window_ns"]
        window["first"] = now_ns if window["first"] is None else min(window["first"], now_ns)
        window["last"] = now_ns if window["last"] is None else max(window["last"], now_ns)
        if kind == "gap":
            _increment(
                cumulative["gap_reasons_in_window"], record["payload"].get("reason", "unknown")
            )

    barrier = context.consume(record, ref)
    if kind != "discovery":
        context.history.clear()
        context.trades.clear()
    frame_count = touched_count = valid_count = 0
    if in_period and kind == "frame":
        frame_count = 1
        cumulative["period_frame_records"] += 1
        if context.producer_hash not in identity["allowed_producer_hashes"]:
            cumulative["frames_excluded_unsupported_producer"] += 1
        elif (
            context.engine.reconstruction_version not in identity["allowed_reconstruction_versions"]
        ):
            cumulative["frames_excluded_unsupported_reconstruction"] += 1
        else:
            if barrier == "receiver_clock_regression":
                cumulative["receiver_clock_regression_frames"] += 1
            for condition, market in context.cohort.items():
                tokens = list(market["tokens"])
                if not any(
                    token in context.engine.books
                    and context.engine.books[token]["last"][0] == record["ordinal"]
                    for token in tokens
                ):
                    continue
                touched_count += 1
                cumulative["touched_market_frame_states"] += 1
                item = _market_row(cumulative, condition, str(market["id"]))
                _increment(item, "touched_market_frame_states")
                reason = pair_quality(market, context.engine.books, now_ns, spec)
                if reason is None and any(token in context.bad for token in tokens):
                    reason = "independent_book_divergence"
                if reason is not None:
                    cumulative["quality_invalid_reason_counts"].setdefault(reason, 0)
                    _increment(cumulative["quality_invalid_reason_counts"], reason)
                    _increment(item["quality_reasons"], reason)
                    _increment(item, "quality_invalid_states")
                    continue

                valid_count += 1
                cumulative["quality_valid_states"] += 1
                _increment(item, "quality_valid_states")
                books = [context.engine.books[token] for token in tokens]
                best_asks = [min(book["asks"]) for book in books]
                top_edge = Decimal(1) - sum(best_asks, Decimal(0))
                edge_key = str(top_edge)
                _increment(cumulative["top_edge_histogram"], edge_key)
                if len(cumulative["top_edge_histogram"]) > MAX_EDGE_BINS:
                    raise ValueError("Distinct finalized-source edge values exceeded the bound")
                if top_edge > 0:
                    _increment_market(cumulative, item, "positive_top_ask_pair_states")

                walks = [
                    walk_asks(
                        [[str(price), str(size)] for price, size in sorted(book["asks"].items())],
                        quantity,
                    )
                    for book in books
                ]
                depth_complete = all(bool(walk["complete_at_requested_quantity"]) for walk in walks)
                if depth_complete:
                    _increment_market(cumulative, item, "quantity_depth_complete_states")
                    acquisition = sum(
                        (
                            Decimal(walk["displayed_notional_for_supported_quantity"])
                            for walk in walks
                        ),
                        Decimal(0),
                    )
                    minimum = market.get("minimum_order_size")
                    try:
                        minimum_notional = Decimal(str(minimum))
                        minimum_notional_satisfied = (
                            minimum_notional.is_finite() and minimum_notional > 0
                        ) and all(
                            Decimal(walk["displayed_notional_for_supported_quantity"])
                            >= minimum_notional
                            for walk in walks
                        )
                    except (ArithmeticError, TypeError, ValueError):
                        minimum_notional_satisfied = False
                    if top_edge > 0:
                        _increment_market(
                            cumulative, item, "positive_top_with_quantity_depth_states"
                        )
                    if quantity - acquisition > 0:
                        _increment_market(cumulative, item, "positive_full_depth_pre_fee_states")
                        if minimum_notional_satisfied:
                            _increment_market(
                                cumulative,
                                item,
                                "positive_full_depth_minimum_notional_satisfied_states",
                            )

                rate = fee_rate({"market": {"fee_regime": market.get("fee_regime")}})
                fee_field = (
                    "fee_regime_available_states"
                    if rate is not None
                    else "fee_regime_unavailable_states"
                )
                _increment_market(cumulative, item, fee_field)
    context.refs.clear()
    return frame_count, touched_count, valid_count


def _event_directory(root: Path) -> Path:
    base = root / "source-analysis-events"
    if base.is_symlink():
        raise ValueError("Source-analysis event root is a symlink")
    versioned = base / "v1"
    if versioned.is_symlink():
        raise ValueError("Source-analysis event version is a symlink")
    versioned.mkdir(parents=True, exist_ok=True, mode=0o700)
    return versioned


def _write_event(path: Path, event: dict[str, Any]) -> bool:
    sealed = _sealed(event, "analysis_event_sha256")
    data = _canonical(sealed)
    if len(data) > MAX_EVENT_BYTES:
        raise ValueError("Finalized-source analysis event exceeds its bound")
    if path.is_symlink():
        raise ValueError("Finalized-source analysis event path is a symlink")
    if path.exists():
        existing = _read_sealed(path, maximum=MAX_EVENT_BYTES, key="analysis_event_sha256")
        if _canonical(existing) != data:
            raise ValueError("Existing finalized-source event differs from replayed evidence")
        return False
    fd, name = tempfile.mkstemp(prefix=".pending-", suffix=".json", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            existing = _read_sealed(path, maximum=MAX_EVENT_BYTES, key="analysis_event_sha256")
            if _canonical(existing) != data:
                raise ValueError(
                    "Concurrent finalized-source event differs from replayed evidence"
                ) from None
            return False
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _analysis_bytes(root: Path) -> int:
    total = 0
    event_root = root / "source-analysis-events" / "v1"
    for path in event_root.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Source-analysis event artifact is unsafe")
        total += path.stat().st_size
    for pattern in (
        ".source-analysis-state-v1.json.*.tmp",
        ".source-research-summary.json.*.tmp",
    ):
        for path in root.glob(pattern):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Source-analysis temporary artifact is unsafe")
            total += path.stat().st_size
    for path in (
        root / "source-analysis-state-v1.json",
        root / "source-research-summary.json",
    ):
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Source-analysis state artifact is unsafe")
            total += path.stat().st_size
    return total


def _make_summary(
    state: dict[str, Any],
    catalogs: list[dict[str, Any]],
    *,
    empty_finalized_segment_count: int,
    batch_count: int,
    batch_bytes: int,
    campaign: dict[str, Any],
    campaign_sha256: str,
    code_hash: str,
) -> dict[str, Any]:
    processed = state["processed_segment_count"]
    pending = catalogs[processed:]
    identity = campaign["identity"]
    window = state["cumulative"]["source_receipt_window_ns"]
    now_ns = time.time_ns()
    if pending:
        status = "catching_up"
    else:
        status = "current"
    if pending:
        readiness = "catching_up_finalized_source"
    elif not processed:
        readiness = "waiting_for_finalized_source"
    elif now_ns < identity["end_ns"]:
        readiness = "collecting_frozen_campaign_window"
    elif window["last"] is None or window["last"] < identity["end_ns"] - 5 * 10**9:
        readiness = "awaiting_finalized_campaign_window_end"
    else:
        readiness = "ready_for_source_review"
    markets = list(state["cumulative"]["markets"].values())
    markets.sort(
        key=lambda item: (
            -item["touched_market_frame_states"],
            item["market_id"],
            item["condition"],
        )
    )
    cumulative = dict(state["cumulative"])
    cumulative["top_edge_distribution"] = _edge_summary(cumulative.pop("top_edge_histogram"))
    cumulative["market_count"] = len(cumulative.pop("markets"))
    return {
        "schema_version": 1,
        "analysis_version": VERSION,
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": campaign_sha256,
        "analysis_code_sha256": code_hash,
        "active_segment_read": False,
        "catalog_segment_count": len(catalogs),
        "empty_finalized_segment_count": empty_finalized_segment_count,
        "processed_segment_count": processed,
        "pending_segment_count": len(pending),
        "pending_source_bytes": sum(int(item["bytes"]) for item in pending),
        "processed_source_bytes": state["processed_source_bytes"],
        "last_processed_ordinal": state["last_ordinal"],
        "last_processed_segment_file": state["last_segment_file"],
        "prefix_catalog_sha256": state["prefix_catalog_sha256"],
        "batch_processed_segment_count": batch_count,
        "batch_processed_source_bytes": batch_bytes,
        "campaign_window_ns": {"start": identity["start_ns"], "end_exclusive": identity["end_ns"]},
        "readiness": readiness,
        "status": status,
        "cumulative": cumulative,
        "most_observed_markets": markets[:MAX_RECENT_MARKETS],
        "limitations": [
            "Only cataloged finalized segments are read; an active .open segment is never opened.",
            "Campaign-window filtering uses recorded receiver time; earlier records are replayed only to restore state.",
            "Repeated market-frame observations are correlated and are not independent opportunities or venue-wide prevalence.",
            "Displayed depth and hypothetical economics do not establish order arrival, matching, fills, or realized returns.",
            "The source is the frozen Mission 2 recording and does not represent new venue-wide public discovery.",
        ],
        "generated_at_utc": datetime.fromtimestamp(now_ns / 10**9, UTC).isoformat(
            timespec="seconds"
        ),
    }


def update_finalized_source_analysis(
    root: Path,
    *,
    max_segments: int = MAX_SEGMENTS_PER_RUN,
    max_source_bytes: int = MAX_SOURCE_BYTES_PER_RUN,
    campaign_path: Path = DEFAULT_CAMPAIGN_PATH,
    expected_campaign_sha256: str = DEFAULT_CAMPAIGN_SHA256,
    expected_campaign_id: str | None = DEFAULT_CAMPAIGN_ID,
    expected_source_root: Path | None = DEFAULT_SOURCE_ROOT,
) -> dict[str, Any]:
    """Process one bounded suffix of pinned, finalized source and persist a safe cursor."""
    if not 1 <= max_segments <= MAX_SEGMENTS_PER_RUN:
        raise ValueError(f"max_segments must be in 1..{MAX_SEGMENTS_PER_RUN}")
    if not 1 <= max_source_bytes <= MAX_SOURCE_BYTES_PER_RUN:
        raise ValueError(f"max_source_bytes must be in 1..{MAX_SOURCE_BYTES_PER_RUN}")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise ValueError("Veritas source-analysis output root is a symlink")
    lock_path = root / "source-analysis.lock"
    if lock_path.is_symlink():
        raise ValueError("Veritas source-analysis lock is a symlink")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "Another finalized-source analysis run owns the output root"
            ) from error

        campaign, campaign_sha256, raw_root = _read_campaign(
            campaign_path,
            expected_campaign_sha256=expected_campaign_sha256,
            expected_campaign_id=expected_campaign_id,
            expected_source_root=expected_source_root,
        )
        all_catalogs = _read_catalogs(raw_root)
        empty_finalized_segment_count = sum(1 for item in all_catalogs if item["count"] == 0)
        # Empty finalized headers have no source records and may share the next
        # ordinal's filename prefix with a later nonempty segment. They are
        # validated but excluded from the replay cursor so late empty catalogs
        # cannot reorder an already processed record prefix.
        catalogs = [item for item in all_catalogs if item["count"] > 0]
        code = _code_identity()
        code_hash = digest(code)
        event_dir = _event_directory(root)
        state_path = root / "source-analysis-state-v1.json"
        summary_path = root / "source-research-summary.json"
        if state_path.exists():
            stored_state = _read_sealed(state_path, maximum=MAX_STATE_BYTES, key="state_sha256")
            if (
                stored_state.get("schema_version") != 1
                or stored_state.get("analysis_version") != VERSION
                or stored_state.get("campaign_sha256") != campaign_sha256
                or stored_state.get("campaign_id") != campaign["campaign_id"]
                or stored_state.get("analysis_code_sha256") != code_hash
                or stored_state.get("analysis_code_files") != code
            ):
                raise ValueError("Source-analysis state is pinned to different campaign or code")
            state = dict(stored_state)
            state.pop("state_sha256", None)
            processed = state["processed_segment_count"]
            if not isinstance(processed, int) or not 0 <= processed <= len(catalogs):
                raise ValueError("Source-analysis processed prefix is inconsistent")
            if state["prefix_catalog_sha256"] != _prefix_hash(catalogs, processed):
                raise ValueError(
                    "Finalized Reality catalog prefix changed behind analysis progress"
                )
            expected_last = catalogs[processed - 1]["last"] if processed else 0
            if state["last_ordinal"] != expected_last:
                raise ValueError("Source-analysis ordinal cursor differs from catalog prefix")
            context = Context.restore(state["context"])
            if context.engine.last_ordinal != state["last_ordinal"]:
                raise ValueError("Restored source-analysis replay ordinal differs from cursor")
            cumulative = state["cumulative"]
        else:
            cumulative = _new_cumulative()
            identity = campaign["identity"]
            cumulative["campaign_window_ns"] = {
                "start": identity["start_ns"],
                "end_exclusive": identity["end_ns"],
            }
            cumulative["quantity_requested"] = str(identity["quantity"])
            state = {
                "schema_version": 1,
                "analysis_version": VERSION,
                "campaign_sha256": campaign_sha256,
                "campaign_id": campaign["campaign_id"],
                "analysis_code_sha256": code_hash,
                "analysis_code_files": code,
                "processed_segment_count": 0,
                "last_ordinal": 0,
                "last_segment_file": None,
                "processed_source_bytes": 0,
                "prefix_catalog_sha256": _prefix_hash([], 0),
                "last_event_sha256": None,
                "context": Context().snapshot(),
                "cumulative": cumulative,
            }
            context = Context()

        initial_bytes = _analysis_bytes(root)
        if initial_bytes > MAX_EVENTS_BYTES:
            raise ValueError("Finalized-source analysis artifacts exceed the storage bound")
        spec = spec_for(campaign)
        batch_count = batch_bytes = 0
        prior_catalog_prefix = state["prefix_catalog_sha256"]
        started_processed = state["processed_segment_count"]
        for index in range(started_processed, len(catalogs)):
            if batch_count >= max_segments:
                break
            info = catalogs[index]
            segment_bytes = int(info["bytes"])
            if segment_bytes > MAX_SEGMENT_BYTES:
                raise ValueError("A finalized Reality segment exceeds the per-segment bound")
            if batch_count and batch_bytes + segment_bytes > max_source_bytes:
                break
            if segment_bytes > max_source_bytes:
                raise ValueError("A finalized Reality segment exceeds the per-run byte bound")
            segment_path = raw_root / info["file"]
            if file_hash(segment_path) != info["sha256"]:
                raise ValueError(f"Finalized Reality segment checksum mismatch: {info['file']}")

            record_count = 0
            first_ordinal = segment_last_ordinal = 0
            kind_counts: Counter[str] = Counter()
            segment_frames = segment_touched = segment_valid = 0
            offset = len(MAGIC)
            replay_ordinal = state["last_ordinal"]
            with segment_path.open("rb") as headers:
                for record, end_offset in records(segment_path):
                    expected_ordinal = replay_ordinal + 1
                    if record.get("ordinal") != expected_ordinal:
                        raise ValueError("Finalized Reality source ordinal is discontinuous")
                    if not record_count:
                        first_ordinal = record["ordinal"]
                    segment_last_ordinal = record["ordinal"]
                    record_count += 1
                    kind_counts[record["kind"]] += 1
                    headers.seek(offset + 4)
                    compressed_sha256 = headers.read(32).hex()
                    ref = {
                        "segment": info["file"],
                        "segment_sha256": info["sha256"],
                        "ordinal": record["ordinal"],
                        "offset": offset,
                        "end_offset": end_offset,
                        "compressed_record_sha256": compressed_sha256,
                        "canonical_record_sha256": digest(record),
                        "received_ns": record["received_ns"],
                        "monotonic_ns": record["monotonic_ns"],
                    }
                    frame_count, touched_count, valid_count = _consume_record(
                        record,
                        ref,
                        context,
                        cumulative,
                        identity=campaign["identity"],
                        spec=spec,
                        quantity=Decimal(campaign["identity"]["quantity"]),
                    )
                    replay_ordinal = record["ordinal"]
                    segment_frames += frame_count
                    segment_touched += touched_count
                    segment_valid += valid_count
                    offset = end_offset
            if (
                record_count != info["count"]
                or first_ordinal != info["first"]
                or dict(sorted(kind_counts.items())) != dict(sorted(info["kinds"].items()))
                or segment_last_ordinal != info["last"]
            ):
                raise ValueError(f"Finalized Reality catalog contents differ: {info['file']}")
            last_ordinal = replay_ordinal

            new_prefix = hashlib.sha256(
                bytes.fromhex(prior_catalog_prefix) + _canonical(info)
            ).hexdigest()
            context_snapshot = context.snapshot()
            event = {
                "schema_version": 1,
                "analysis_version": VERSION,
                "analysis_code_sha256": code_hash,
                "campaign_id": campaign["campaign_id"],
                "campaign_sha256": campaign_sha256,
                "segment_index": index + 1,
                "source_segment": info["file"],
                "source_segment_sha256": info["sha256"],
                "source_catalog": info,
                "prior_prefix_catalog_sha256": prior_catalog_prefix,
                "prefix_catalog_sha256": new_prefix,
                "record_count": record_count,
                "record_kinds": dict(sorted(kind_counts.items())),
                "campaign_window_frame_records": segment_frames,
                "touched_market_frame_states": segment_touched,
                "quality_valid_states": segment_valid,
                "post_context_sha256": _sha256(_canonical(context_snapshot)),
                "post_cumulative_sha256": _sha256(_canonical(cumulative)),
            }
            event_path = event_dir / f"{index + 1:020d}.json"
            event_data_size = len(_canonical(_sealed(event, "analysis_event_sha256")))
            if not event_path.exists() and initial_bytes + event_data_size > MAX_EVENTS_BYTES:
                raise ValueError("Finalized-source analysis event store would exceed its bound")
            event_created = _write_event(event_path, event)

            prior_event = state["last_event_sha256"]
            prior_event = prior_event or ("0" * 64)
            event_sha256 = _read_sealed(
                event_path, maximum=MAX_EVENT_BYTES, key="analysis_event_sha256"
            )["analysis_event_sha256"]
            state.update(
                processed_segment_count=index + 1,
                last_ordinal=last_ordinal,
                last_segment_file=info["file"],
                processed_source_bytes=state["processed_source_bytes"] + segment_bytes,
                prefix_catalog_sha256=new_prefix,
                last_event_sha256=_sha256(bytes.fromhex(prior_event) + bytes.fromhex(event_sha256)),
                context=context_snapshot,
                cumulative=cumulative,
            )
            sealed_state = _sealed(state, "state_sha256")
            prior_state_size = state_path.stat().st_size if state_path.exists() else 0
            state_size = _atomic_json(state_path, sealed_state, maximum=MAX_STATE_BYTES)
            initial_bytes += (
                (event_data_size if event_created else 0) + state_size - prior_state_size
            )
            prior_catalog_prefix = new_prefix
            batch_count += 1
            batch_bytes += segment_bytes

        if not state_path.exists():
            _atomic_json(state_path, _sealed(state, "state_sha256"), maximum=MAX_STATE_BYTES)
        summary = _make_summary(
            state,
            catalogs,
            batch_count=batch_count,
            batch_bytes=batch_bytes,
            empty_finalized_segment_count=empty_finalized_segment_count,
            campaign=campaign,
            campaign_sha256=campaign_sha256,
            code_hash=code_hash,
        )
        summary = _sealed(summary, "summary_sha256")
        serialized_summary_size = len(_canonical(summary))
        prior_summary_size = summary_path.stat().st_size if summary_path.exists() else 0
        if initial_bytes + serialized_summary_size - prior_summary_size > MAX_EVENTS_BYTES:
            raise ValueError("Finalized-source analysis summary would exceed its storage bound")
        _atomic_json(summary_path, summary, maximum=MAX_SUMMARY_BYTES)
        return summary


def read_finalized_source_summary(root: Path) -> dict[str, Any] | None:
    path = root / "source-research-summary.json"
    if not path.exists():
        return None
    summary = _read_sealed(path, maximum=MAX_SUMMARY_BYTES, key="summary_sha256")
    if summary.get("analysis_version") != VERSION or summary.get("schema_version") != 1:
        raise ValueError("Unsupported finalized-source summary")
    return summary
