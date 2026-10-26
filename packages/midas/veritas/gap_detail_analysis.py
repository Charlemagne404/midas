"""Bounded, resumable indexing of gap records from finalized Reality segments.

This analysis is intentionally separate from the pinned Mission 2 source
analyzer. It reads cataloged ``.seg`` files only, stores gap metadata without
book payloads or asset identifiers, and never changes Reality or campaign data.
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
from pathlib import Path
from typing import Any, Literal, cast

from midas.reality.research_schema import digest
from midas.reality.shadow_campaign import verify as verify_campaign
from midas.reality.storage import MAGIC, file_hash, records

VERSION = "veritas-finalized-reality-gap-detail-v1"
OUTPUT_VERSIONS = ("v1", "v2")
DEFAULT_CAMPAIGN_PATH = Path(
    "/home/charlie/midas-reality/data/research/reality/forward/mission2/campaign.json"
)
DEFAULT_CAMPAIGN_SHA256 = "aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5"
DEFAULT_CAMPAIGN_ID = "adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46"
DEFAULT_SOURCE_ROOT = Path("/home/charlie/midas-reality/data/recordings/reality")

MAX_CATALOG_BYTES = 128 * 1024
MAX_CATALOG_TOTAL_BYTES = 32 * 1024**2
MAX_CATALOG_SEGMENTS = 100_000
MAX_SEGMENT_BYTES = 16 * 1024**2
MAX_SEGMENTS_PER_RUN = 128
MAX_SOURCE_BYTES_PER_RUN = 32 * 1024**2
MAX_EVENTS_BYTES = 256 * 1024**2
MAX_EVENT_BYTES = 256 * 1024
MAX_STATE_BYTES = 16 * 1024**2
MAX_SUMMARY_BYTES = 2 * 1024**2
MAX_GAPS_PER_SEGMENT = 4_096
MAX_TRACKED_ASSETS = 20_000
MAX_TRACKED_MARKETS = 20_000
MAX_GAP_REASONS = 128
MAX_GAP_ISSUES_PER_EVENT = 256
MAX_RECENT_GAPS = 20

_SEGMENT_CATALOG = re.compile(r"(?P<first>[0-9]{20})-(?P<uuid>[0-9a-f]{32})\.json\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _analysis_version(output_version: str) -> str:
    if output_version not in OUTPUT_VERSIONS:
        raise ValueError("Unsupported gap-detail output version")
    return f"veritas-finalized-reality-gap-detail-{output_version}"


def _atomic_json(path: Path, value: dict[str, Any], *, maximum: int) -> int:
    data = _canonical(value)
    if len(data) > maximum:
        raise ValueError(f"Gap-detail artifact exceeds its bound: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError(f"Gap-detail artifact path is a symlink: {path.name}")
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


def _read_sealed(path: Path, *, maximum: int, key: str, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError(f"Unsafe or oversized {label}: {path.name}")
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid {label}: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {label} object: {path.name}")
    stored = value.pop(key, None)
    if not isinstance(stored, str) or stored != _sha256(_canonical(value)):
        raise ValueError(f"{label} digest mismatch: {path.name}")
    value[key] = stored
    return value


def _code_identity() -> dict[str, str]:
    reality = Path(__file__).parents[1] / "reality"
    repo = Path(__file__).parents[3]
    return {
        "gap_detail_control.py": file_hash(Path(__file__).with_name("gap_detail_control.py")),
        "gap_detail_analysis.py": file_hash(Path(__file__)),
        "scripts/veritas_gap_detail_analysis.py": file_hash(
            repo / "scripts" / "veritas_gap_detail_analysis.py"
        ),
        **{
            f"reality/{name}": file_hash(reality / name)
            for name in ("research_schema.py", "shadow_campaign.py", "storage.py")
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
    for name in ("start_ns", "end_ns"):
        value = identity.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"Pinned Mission 2 campaign {name} is invalid")
    if identity["start_ns"] >= identity["end_ns"]:
        raise ValueError("Pinned Mission 2 campaign interval is invalid")
    raw_value = identity.get("raw_root")
    if not isinstance(raw_value, str):
        raise ValueError("Pinned Mission 2 campaign has no source root")
    raw_root = Path(raw_value)
    expected = expected_source_root.resolve() if expected_source_root else raw_root.resolve()
    if raw_root.is_symlink() or raw_root.resolve() != expected or not raw_root.is_dir():
        raise ValueError("Mission 2 campaign source root differs from the pinned root")
    return plan, campaign_sha256, raw_root


def _read_catalogs(raw_root: Path) -> tuple[list[dict[str, Any]], int]:
    """Validate finalized sidecars and return the nonempty replayable prefix."""
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

    all_catalogs: list[dict[str, Any]] = []
    total_bytes = 0
    prior_last = 0
    empty_count = 0
    for name, sidecar in entries:
        if sidecar.is_symlink() or not sidecar.is_file():
            raise ValueError("Finalized Reality catalog sidecar is unsafe")
        size = sidecar.stat().st_size
        if size > MAX_CATALOG_BYTES:
            raise ValueError("Finalized Reality catalog sidecar exceeds its bound")
        total_bytes += size
        if total_bytes > MAX_CATALOG_TOTAL_BYTES:
            raise ValueError("Finalized Reality catalog set exceeds its bound")
        try:
            info = json.loads(sidecar.read_text())
        except (OSError, ValueError) as error:
            raise ValueError(f"Invalid finalized Reality catalog: {name}") from error
        if not isinstance(info, dict):
            raise ValueError(f"Invalid finalized Reality catalog: {name}")
        expected_file = name.removesuffix(".json") + ".seg"
        kinds = info.get("kinds")
        first, last, count, segment_bytes = (
            info.get("first"),
            info.get("last"),
            info.get("count"),
            info.get("bytes"),
        )
        if (
            set(info)
            != {"schema_version", "file", "sha256", "bytes", "first", "last", "count", "kinds"}
            or info.get("schema_version") != 1
            or info.get("file") != expected_file
            or not isinstance(info.get("sha256"), str)
            or _SHA256.fullmatch(info["sha256"]) is None
            or not all(
                isinstance(value, int) and not isinstance(value, bool)
                for value in (first, last, count, segment_bytes)
            )
            or not isinstance(kinds, dict)
            or any(
                not isinstance(kind, str)
                or not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                for kind, value in kinds.items()
            )
            or sum(kinds.values()) != count
        ):
            raise ValueError(f"Malformed finalized Reality catalog: {name}")
        first = cast(int, first)
        last = cast(int, last)
        count = cast(int, count)
        segment_bytes = cast(int, segment_bytes)
        if count == 0:
            if first != 0 or last != 0 or segment_bytes != len(MAGIC) or kinds:
                raise ValueError(f"Malformed empty finalized Reality catalog: {name}")
            empty_count += 1
        elif (
            first != prior_last + 1
            or last != first + count - 1
            or segment_bytes <= len(MAGIC)
            or name[:20] != f"{first:020d}"
        ):
            raise ValueError(f"Non-contiguous finalized Reality catalog: {name}")
        segment_path = raw_root / expected_file
        if segment_path.is_symlink() or not segment_path.is_file():
            raise ValueError(f"Finalized Reality segment is missing or unsafe: {expected_file}")
        if segment_path.stat().st_size != segment_bytes:
            raise ValueError(
                f"Finalized Reality segment size differs from catalog: {expected_file}"
            )
        all_catalogs.append(info)
        if count:
            prior_last = last

    # Empty finalized headers carry no records and can sort alongside later
    # segments. Like the primary analyzer, keep them out of the replay cursor.
    return [item for item in all_catalogs if item["count"] > 0], empty_count


def _prefix_hash(catalogs: list[dict[str, Any]], count: int) -> str:
    chain = bytes(32)
    for info in catalogs[:count]:
        chain = hashlib.sha256(chain + _canonical(info)).digest()
    return chain.hex()


def _directory(root: Path, output_version: str) -> Path:
    base = root / "gap-detail-events"
    if base.is_symlink():
        raise ValueError("Gap-detail event root is a symlink")
    versioned = base / output_version
    if versioned.is_symlink():
        raise ValueError("Gap-detail event version is a symlink")
    versioned.mkdir(parents=True, exist_ok=True, mode=0o700)
    return versioned


def _initial_cumulative() -> dict[str, Any]:
    return {
        "all_period_gap_event_count": 0,
        "all_period_gap_counts_by_reason": {},
        "campaign_window_gap_event_count": 0,
        "campaign_window_gap_counts_by_reason": {},
        "campaign_window_affected_market_counts": {},
        "campaign_window_gap_events_without_reported_assets": 0,
        "campaign_window_unmapped_affected_asset_count": 0,
        "campaign_window_first_gap_received_ns": None,
        "campaign_window_last_gap_received_ns": None,
        "recent_gap_events": [],
    }


def _increment(
    mapping: dict[str, int],
    key: str,
    amount: int = 1,
    *,
    max_distinct: int = MAX_GAP_REASONS,
    overflow_message: str = "Distinct finalized gap reasons exceeded their bound",
) -> None:
    if key not in mapping and len(mapping) >= max_distinct:
        raise ValueError(overflow_message)
    mapping[key] = int(mapping.get(key, 0)) + amount


def _utc_ns(value: int) -> str:
    seconds, nanos = divmod(value, 10**9)
    whole = datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{whole}.{nanos:09d}Z"


def _market_map(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    cohort = record.get("cohort")
    if not isinstance(cohort, list):
        raise ValueError("Finalized discovery record has no cohort list")
    result: dict[str, dict[str, str]] = {}
    conditions: dict[str, str] = {}
    for market in cohort:
        if not isinstance(market, dict):
            raise ValueError("Finalized discovery record contains an invalid market")
        market_id = market.get("id")
        condition = market.get("condition")
        tokens = market.get("tokens")
        if not isinstance(market_id, (str, int)) or isinstance(market_id, bool):
            raise ValueError("Finalized discovery market id is invalid")
        if not isinstance(condition, str) or not condition:
            raise ValueError("Finalized discovery condition is invalid")
        if not isinstance(tokens, (dict, list)):
            raise ValueError("Finalized discovery market tokens are invalid")
        market_id_text = str(market_id)
        if condition in conditions and conditions[condition] != market_id_text:
            raise ValueError("A discovery condition changed market identity")
        conditions[condition] = market_id_text
        token_ids = tokens.keys() if isinstance(tokens, dict) else tokens
        for token in token_ids:
            if not isinstance(token, str) or not token:
                raise ValueError("Finalized discovery asset id is invalid")
            reference = {"market_id": market_id_text, "condition": condition}
            if token in result and result[token] != reference:
                raise ValueError("A discovered asset is assigned to multiple markets")
            result[token] = reference
            if len(result) > MAX_TRACKED_ASSETS:
                raise ValueError("Tracked source asset count exceeded its bound")
    if len(conditions) > MAX_TRACKED_MARKETS:
        raise ValueError("Tracked source market count exceeded its bound")
    return result


def _gap_detail(
    record: dict[str, Any],
    token_markets: dict[str, dict[str, str]],
    *,
    start_ns: int,
    end_ns: int,
    segment_index: int,
    segment_file: str,
) -> dict[str, Any]:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Finalized gap record payload is invalid")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason or len(reason) > 128:
        raise ValueError("Finalized gap record reason is invalid")
    received_ns = record.get("received_ns")
    ordinal = record.get("ordinal")
    if not isinstance(received_ns, int) or isinstance(received_ns, bool):
        raise ValueError("Finalized gap record receiver time is invalid")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool):
        raise ValueError("Finalized gap record ordinal is invalid")
    affected = payload.get("affected_assets")
    if affected is None:
        affected = {}
    if not isinstance(affected, dict):
        raise ValueError("Finalized gap affected-assets value is invalid")
    market_ids: set[str] = set()
    issues: Counter[str] = Counter()
    unmapped = 0
    for token, issue in affected.items():
        if not isinstance(token, str):
            raise ValueError("Finalized gap affected-asset id is invalid")
        reference = token_markets.get(token)
        if reference is None:
            unmapped += 1
        else:
            market_ids.add(reference["market_id"])
        normalized_issue = issue[:128] if isinstance(issue, str) and issue else "unspecified"
        if normalized_issue not in issues and len(issues) >= MAX_GAP_ISSUES_PER_EVENT:
            raise ValueError("Affected-asset issue categories exceeded their bound")
        issues[normalized_issue] += 1
    in_window = start_ns <= received_ns < end_ns
    return {
        "ordinal": ordinal,
        "received_ns": received_ns,
        "received_at_utc": _utc_ns(received_ns),
        "reason": reason,
        "in_campaign_window": in_window,
        "segment_index": segment_index,
        "segment_file": segment_file,
        "affected_asset_scope": "reported_assets" if affected else "not_reported",
        "affected_asset_count": len(affected),
        "affected_market_ids": sorted(market_ids),
        "unmapped_affected_asset_count": unmapped,
        "affected_asset_issue_counts": dict(sorted(issues.items())),
    }


def _write_event(path: Path, event: dict[str, Any]) -> bool:
    sealed = _sealed(event, "gap_event_sha256")
    data = _canonical(sealed)
    if len(data) > MAX_EVENT_BYTES:
        raise ValueError("Gap-detail segment event exceeds its bound")
    if path.is_symlink():
        raise ValueError("Gap-detail segment event path is a symlink")
    if path.exists():
        existing = _read_sealed(
            path, maximum=MAX_EVENT_BYTES, key="gap_event_sha256", label="gap-detail event"
        )
        if _canonical(existing) != data:
            raise ValueError("Existing gap-detail event differs from finalized source replay")
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
            existing = _read_sealed(
                path, maximum=MAX_EVENT_BYTES, key="gap_event_sha256", label="gap-detail event"
            )
            if _canonical(existing) != data:
                raise ValueError("Concurrent gap-detail event differs from source replay") from None
            return False
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _verify_event_chain(
    event_dir: Path,
    catalogs: list[dict[str, Any]],
    *,
    processed: int,
    campaign_id: str,
    campaign_sha256: str,
    code_hash: str,
    analysis_version: str,
    expected_chain: str | None,
) -> None:
    chain = "0" * 64
    prefix = _prefix_hash([], 0)
    for index, info in enumerate(catalogs[:processed]):
        path = event_dir / f"{index + 1:020d}.json"
        event = _read_sealed(
            path, maximum=MAX_EVENT_BYTES, key="gap_event_sha256", label="gap-detail event"
        )
        next_prefix = hashlib.sha256(bytes.fromhex(prefix) + _canonical(info)).hexdigest()
        if (
            event.get("schema_version") != 1
            or event.get("analysis_version") != analysis_version
            or event.get("analysis_code_sha256") != code_hash
            or event.get("campaign_id") != campaign_id
            or event.get("campaign_sha256") != campaign_sha256
            or event.get("segment_index") != index + 1
            or event.get("source_segment") != info["file"]
            or event.get("source_segment_sha256") != info["sha256"]
            or event.get("source_catalog") != info
            or event.get("prior_prefix_catalog_sha256") != prefix
            or event.get("prefix_catalog_sha256") != next_prefix
        ):
            raise ValueError("Gap-detail event lineage differs from the processed source prefix")
        event_sha = event["gap_event_sha256"]
        chain = _sha256(bytes.fromhex(chain) + bytes.fromhex(event_sha))
        prefix = next_prefix
    expected = expected_chain or ("0" * 64 if processed == 0 else None)
    if (
        expected is None
        or (processed and chain != expected)
        or (not processed and expected != chain)
    ):
        raise ValueError("Gap-detail event chain differs from persisted state")


def _artifact_bytes(root: Path, output_version: str) -> int:
    total = 0
    event_root = root / "gap-detail-events" / output_version
    if event_root.exists():
        if event_root.is_symlink() or not event_root.is_dir():
            raise ValueError("Gap-detail event store is unsafe")
        for path in event_root.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Gap-detail event artifact is unsafe")
            total += path.stat().st_size
    for pattern in (
        f".gap-detail-state-{output_version}.json.*.tmp",
        f".gap-detail-summary-{output_version}.json.*.tmp",
    ):
        for path in root.glob(pattern):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Gap-detail temporary artifact is unsafe")
            total += path.stat().st_size
    for path in (
        root / f"gap-detail-state-{output_version}.json",
        root / f"gap-detail-summary-{output_version}.json",
    ):
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise ValueError("Gap-detail state artifact is unsafe")
            total += path.stat().st_size
    return total


def _make_summary(
    state: dict[str, Any],
    catalogs: list[dict[str, Any]],
    *,
    empty_count: int,
    batch_count: int,
    batch_bytes: int,
    campaign: dict[str, Any],
    campaign_sha256: str,
    campaign_path: Path,
    source_root: Path,
    analysis_version: str,
    code_hash: str,
    code_identity: dict[str, str],
) -> dict[str, Any]:
    pending = catalogs[state["processed_segment_count"] :]
    identity = campaign["identity"]
    cumulative = state["cumulative"]
    return {
        "schema_version": 1,
        "analysis_version": analysis_version,
        "analysis_code_sha256": code_hash,
        "analysis_code_files": code_identity,
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": campaign_sha256,
        "source_lineage": {
            "campaign_path": str(campaign_path.resolve()),
            "campaign_id": campaign["campaign_id"],
            "campaign_sha256": campaign_sha256,
            "source_root": str(source_root.resolve()),
            "catalog_segment_count": len(catalogs) + empty_count,
            "processed_segment_count": state["processed_segment_count"],
            "prefix_catalog_sha256": state["prefix_catalog_sha256"],
            "last_ordinal": state["last_ordinal"],
        },
        "campaign_window_ns": {"start": identity["start_ns"], "end_exclusive": identity["end_ns"]},
        "catalog_segment_count": len(catalogs) + empty_count,
        "empty_finalized_segment_count": empty_count,
        "replayable_catalog_segment_count": len(catalogs),
        "processed_segment_count": state["processed_segment_count"],
        "pending_segment_count": len(pending),
        "pending_source_bytes": sum(int(item["bytes"]) for item in pending),
        "processed_source_bytes": state["processed_source_bytes"],
        "last_processed_ordinal": state["last_ordinal"],
        "last_processed_segment_file": state["last_segment_file"],
        "prefix_catalog_sha256": state["prefix_catalog_sha256"],
        "last_event_chain_sha256": state["last_event_chain_sha256"],
        "batch_processed_segment_count": batch_count,
        "batch_processed_source_bytes": batch_bytes,
        "campaign_window_gap_event_count": cumulative["campaign_window_gap_event_count"],
        "campaign_window_gap_counts_by_reason": cumulative["campaign_window_gap_counts_by_reason"],
        "campaign_window_affected_market_counts": cumulative[
            "campaign_window_affected_market_counts"
        ],
        "campaign_window_gap_events_without_reported_assets": cumulative[
            "campaign_window_gap_events_without_reported_assets"
        ],
        "campaign_window_unmapped_affected_asset_count": cumulative[
            "campaign_window_unmapped_affected_asset_count"
        ],
        "campaign_window_first_gap_received_ns": cumulative[
            "campaign_window_first_gap_received_ns"
        ],
        "campaign_window_last_gap_received_ns": cumulative["campaign_window_last_gap_received_ns"],
        "all_period_gap_event_count": cumulative["all_period_gap_event_count"],
        "all_period_gap_counts_by_reason": cumulative["all_period_gap_counts_by_reason"],
        "recent_gap_events": cumulative["recent_gap_events"],
        "active_segment_read": False,
        "status": "catching_up" if pending else "current",
        "limitations": [
            "Only cataloged finalized .seg files are read; active .open files are never opened.",
            "Gap received_ns is recorder receiver time, not an exchange quote timestamp.",
            "affected_market_ids map only assets named by the gap record and the latest preceding discovery record.",
            "A later frame is not proof that every affected book or the complete feed recovered.",
            "The analysis preserves gap events; it does not alter the primary source-analysis state or frozen campaign.",
        ],
        "generated_at_utc": datetime.fromtimestamp(time.time(), UTC).isoformat(timespec="seconds"),
    }


def update_finalized_gap_detail_analysis(
    root: Path,
    *,
    max_segments: int = MAX_SEGMENTS_PER_RUN,
    max_source_bytes: int = MAX_SOURCE_BYTES_PER_RUN,
    campaign_path: Path = DEFAULT_CAMPAIGN_PATH,
    expected_campaign_sha256: str = DEFAULT_CAMPAIGN_SHA256,
    expected_campaign_id: str | None = DEFAULT_CAMPAIGN_ID,
    expected_source_root: Path | None = DEFAULT_SOURCE_ROOT,
    output_version: Literal["v1", "v2"] = "v1",
) -> dict[str, Any]:
    """Process one bounded suffix of the pinned finalized source catalog."""
    if not 1 <= max_segments <= MAX_SEGMENTS_PER_RUN:
        raise ValueError(f"max_segments must be in 1..{MAX_SEGMENTS_PER_RUN}")
    if not 1 <= max_source_bytes <= MAX_SOURCE_BYTES_PER_RUN:
        raise ValueError(f"max_source_bytes must be in 1..{MAX_SOURCE_BYTES_PER_RUN}")
    analysis_version = _analysis_version(output_version)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise ValueError("Gap-detail output root is a symlink")
    lock_path = root / "gap-detail-analysis.lock"
    if lock_path.is_symlink():
        raise ValueError("Gap-detail analysis lock is a symlink")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another gap-detail analysis run owns the output root") from error

        campaign, campaign_sha256, raw_root = _read_campaign(
            campaign_path,
            expected_campaign_sha256=expected_campaign_sha256,
            expected_campaign_id=expected_campaign_id,
            expected_source_root=expected_source_root,
        )
        catalogs, empty_count = _read_catalogs(raw_root)
        code_identity = _code_identity()
        code_hash = digest(code_identity)
        event_dir = _directory(root, output_version)
        state_path = root / f"gap-detail-state-{output_version}.json"
        summary_path = root / f"gap-detail-summary-{output_version}.json"
        if state_path.exists():
            stored = _read_sealed(
                state_path, maximum=MAX_STATE_BYTES, key="state_sha256", label="gap-detail state"
            )
            if (
                stored.get("schema_version") != 1
                or stored.get("analysis_version") != analysis_version
                or stored.get("campaign_id") != campaign["campaign_id"]
                or stored.get("campaign_sha256") != campaign_sha256
                or stored.get("analysis_code_sha256") != code_hash
                or stored.get("analysis_code_files") != code_identity
            ):
                raise ValueError("Gap-detail state is pinned to different campaign or code")
            state = dict(stored)
            state.pop("state_sha256", None)
            processed = state.get("processed_segment_count")
            if not isinstance(processed, int) or not 0 <= processed <= len(catalogs):
                raise ValueError("Gap-detail processed prefix is inconsistent")
            if state.get("prefix_catalog_sha256") != _prefix_hash(catalogs, processed):
                raise ValueError("Finalized Reality catalog prefix changed behind gap analysis")
            expected_last = catalogs[processed - 1]["last"] if processed else 0
            if state.get("last_ordinal") != expected_last:
                raise ValueError("Gap-detail source ordinal differs from catalog prefix")
            token_markets = state.get("token_markets")
            cumulative = state.get("cumulative")
            if not isinstance(token_markets, dict) or not isinstance(cumulative, dict):
                raise ValueError("Gap-detail state cursor is invalid")
        else:
            state = {
                "schema_version": 1,
                "analysis_version": analysis_version,
                "analysis_code_sha256": code_hash,
                "analysis_code_files": code_identity,
                "campaign_id": campaign["campaign_id"],
                "campaign_sha256": campaign_sha256,
                "processed_segment_count": 0,
                "last_ordinal": 0,
                "last_segment_file": None,
                "processed_source_bytes": 0,
                "prefix_catalog_sha256": _prefix_hash([], 0),
                "last_event_chain_sha256": None,
                "token_markets": {},
                "cumulative": _initial_cumulative(),
            }
            token_markets = state["token_markets"]
            cumulative = state["cumulative"]

        initial_bytes = _artifact_bytes(root, output_version)
        if initial_bytes > MAX_EVENTS_BYTES:
            raise ValueError("Gap-detail analysis artifacts exceed the storage bound")
        _verify_event_chain(
            event_dir,
            catalogs,
            processed=state["processed_segment_count"],
            campaign_id=campaign["campaign_id"],
            campaign_sha256=campaign_sha256,
            code_hash=code_hash,
            analysis_version=analysis_version,
            expected_chain=state["last_event_chain_sha256"],
        )
        start_ns = campaign["identity"]["start_ns"]
        end_ns = campaign["identity"]["end_ns"]
        batch_count = batch_bytes = 0
        prior_prefix = state["prefix_catalog_sha256"]
        for index in range(state["processed_segment_count"], len(catalogs)):
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
            first_ordinal = last_ordinal = 0
            kind_counts: Counter[str] = Counter()
            gap_events: list[dict[str, Any]] = []
            replay_ordinal = state["last_ordinal"]
            for record, _ in records(segment_path):
                ordinal = record.get("ordinal")
                received_ns = record.get("received_ns")
                kind = record.get("kind")
                if (
                    not isinstance(ordinal, int)
                    or isinstance(ordinal, bool)
                    or ordinal != replay_ordinal + 1
                    or not isinstance(received_ns, int)
                    or isinstance(received_ns, bool)
                    or not isinstance(kind, str)
                ):
                    raise ValueError(
                        "Finalized Reality source record is malformed or discontinuous"
                    )
                if record_count == 0:
                    first_ordinal = ordinal
                last_ordinal = ordinal
                replay_ordinal = ordinal
                record_count += 1
                kind_counts[kind] += 1
                if kind == "discovery":
                    token_markets.clear()
                    token_markets.update(_market_map(record))
                elif kind == "gap":
                    if len(gap_events) >= MAX_GAPS_PER_SEGMENT:
                        raise ValueError("Gap count in one finalized segment exceeded its bound")
                    gap_events.append(
                        _gap_detail(
                            record,
                            token_markets,
                            start_ns=start_ns,
                            end_ns=end_ns,
                            segment_index=index + 1,
                            segment_file=info["file"],
                        )
                    )
            if (
                record_count != info["count"]
                or first_ordinal != info["first"]
                or last_ordinal != info["last"]
                or dict(sorted(kind_counts.items())) != dict(sorted(info["kinds"].items()))
            ):
                raise ValueError(f"Finalized Reality catalog contents differ: {info['file']}")

            for gap in gap_events:
                _increment(cumulative["all_period_gap_counts_by_reason"], gap["reason"])
                cumulative["all_period_gap_event_count"] += 1
                recent = cumulative["recent_gap_events"]
                recent.append(gap)
                del recent[:-MAX_RECENT_GAPS]
                if not gap["in_campaign_window"]:
                    continue
                _increment(cumulative["campaign_window_gap_counts_by_reason"], gap["reason"])
                cumulative["campaign_window_gap_event_count"] += 1
                if gap["affected_asset_scope"] == "not_reported":
                    cumulative["campaign_window_gap_events_without_reported_assets"] += 1
                cumulative["campaign_window_unmapped_affected_asset_count"] += gap[
                    "unmapped_affected_asset_count"
                ]
                for market_id in gap["affected_market_ids"]:
                    _increment(
                        cumulative["campaign_window_affected_market_counts"],
                        market_id,
                        max_distinct=MAX_TRACKED_MARKETS,
                        overflow_message=("Distinct gap-affected market count exceeded its bound"),
                    )
                received = gap["received_ns"]
                first = cumulative["campaign_window_first_gap_received_ns"]
                last = cumulative["campaign_window_last_gap_received_ns"]
                cumulative["campaign_window_first_gap_received_ns"] = (
                    received if first is None else min(first, received)
                )
                cumulative["campaign_window_last_gap_received_ns"] = (
                    received if last is None else max(last, received)
                )

            new_prefix = hashlib.sha256(bytes.fromhex(prior_prefix) + _canonical(info)).hexdigest()
            event = {
                "schema_version": 1,
                "analysis_version": analysis_version,
                "analysis_code_sha256": code_hash,
                "campaign_id": campaign["campaign_id"],
                "campaign_sha256": campaign_sha256,
                "segment_index": index + 1,
                "source_segment": info["file"],
                "source_segment_sha256": info["sha256"],
                "source_catalog": info,
                "source_catalog_sha256": _sha256(_canonical(info)),
                "prior_prefix_catalog_sha256": prior_prefix,
                "prefix_catalog_sha256": new_prefix,
                "record_count": record_count,
                "source_ordinal_start": first_ordinal,
                "source_ordinal_end": last_ordinal,
                "record_kinds": dict(sorted(kind_counts.items())),
                "gap_event_count": len(gap_events),
                "campaign_window_gap_event_count": sum(
                    bool(gap["in_campaign_window"]) for gap in gap_events
                ),
                "gap_events": gap_events,
            }
            event_path = event_dir / f"{index + 1:020d}.json"
            event_size = len(_canonical(_sealed(event, "gap_event_sha256")))
            if not event_path.exists() and initial_bytes + event_size > MAX_EVENTS_BYTES:
                raise ValueError("Gap-detail event store would exceed its storage bound")
            event_created = _write_event(event_path, event)
            event_sha = _read_sealed(
                event_path,
                maximum=MAX_EVENT_BYTES,
                key="gap_event_sha256",
                label="gap-detail event",
            )["gap_event_sha256"]
            prior_event = state["last_event_chain_sha256"] or ("0" * 64)
            state.update(
                processed_segment_count=index + 1,
                last_ordinal=last_ordinal,
                last_segment_file=info["file"],
                processed_source_bytes=state["processed_source_bytes"] + segment_bytes,
                prefix_catalog_sha256=new_prefix,
                last_event_chain_sha256=_sha256(
                    bytes.fromhex(prior_event) + bytes.fromhex(event_sha)
                ),
                token_markets=token_markets,
                cumulative=cumulative,
            )
            sealed_state = _sealed(state, "state_sha256")
            prior_state_size = state_path.stat().st_size if state_path.exists() else 0
            state_size = _atomic_json(state_path, sealed_state, maximum=MAX_STATE_BYTES)
            initial_bytes += (event_size if event_created else 0) + state_size - prior_state_size
            prior_prefix = new_prefix
            batch_count += 1
            batch_bytes += segment_bytes

        if not state_path.exists():
            _atomic_json(state_path, _sealed(state, "state_sha256"), maximum=MAX_STATE_BYTES)
        summary = _make_summary(
            state,
            catalogs,
            empty_count=empty_count,
            batch_count=batch_count,
            batch_bytes=batch_bytes,
            campaign=campaign,
            campaign_sha256=campaign_sha256,
            campaign_path=campaign_path,
            source_root=raw_root,
            analysis_version=analysis_version,
            code_hash=code_hash,
            code_identity=code_identity,
        )
        sealed_summary = _sealed(summary, "summary_sha256")
        summary_size = len(_canonical(sealed_summary))
        previous_summary_size = summary_path.stat().st_size if summary_path.exists() else 0
        if initial_bytes + summary_size - previous_summary_size > MAX_EVENTS_BYTES:
            raise ValueError("Gap-detail summary would exceed its storage bound")
        _atomic_json(summary_path, sealed_summary, maximum=MAX_SUMMARY_BYTES)
        return sealed_summary


def read_finalized_gap_detail_summary(
    root: Path, output_version: Literal["v1", "v2"] = "v1"
) -> dict[str, Any] | None:
    analysis_version = _analysis_version(output_version)
    path = root / f"gap-detail-summary-{output_version}.json"
    if not path.exists():
        return None
    summary = _read_sealed(
        path, maximum=MAX_SUMMARY_BYTES, key="summary_sha256", label="gap-detail summary"
    )
    if summary.get("analysis_version") != analysis_version or summary.get("schema_version") != 1:
        raise ValueError("Unsupported finalized gap-detail summary")
    return summary
