"""Versioned eight-read successor for bounded Veritas public discovery.

This path keeps the six established discovery frames, adds a direct lookup of
the frozen control cohort, and then requests the selected books in one batch.
It writes to a separate root and deliberately does not update the v1 pilot or
the v2 observer's incremental-analysis state.
"""

from __future__ import annotations

import fcntl
import gzip
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .control_retrieval import summarize_control_rows
from .observatory import (
    CONTROL_COHORT_VERSION,
    DEFAULT_CONTROL_MARKETS,
    DEFAULT_MARKETS,
    DEFAULT_QUANTITIES,
    DEFAULT_SEED,
    DISCOVERY_QUERIES,
    LEGACY_CONTROL_COHORT_VERSION,
    MAX_ACTIVITY_MARKETS,
    MAX_ANALYSIS_RESERVE_BYTES,
    MAX_MARKETS,
    MAX_RESPONSE_BYTES,
    MAX_RETRIES_PER_PUBLIC_READ,
    MAX_ROOT_BYTES,
    MAX_STATE_BYTES,
    REQUEST_INTERVAL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    PublicReadClient,
    _atomic_json,
    _book_state_hash,
    _canonical,
    _enrich_candidate,
    _reported_age_band,
    _reported_skew_band,
    _safe_json,
    _sanitize_book,
    _sha256,
    _summary,
    discover_universe,
    select_cohort,
)
from .opportunity_audit_v2 import audit_pair_snapshot, normalize_market

VERSION = "veritas-public-observatory-discovery-successor-v2"
FRAME_PROTOCOL = "stratified-gamma-page-rotation-v2+direct-frozen-control-v1+economic-audit-v2"
MAX_CONTROL_MARKETS = DEFAULT_CONTROL_MARKETS
MAX_PUBLIC_READS_PER_SCAN = DISCOVERY_QUERIES + 2
MAX_PUBLIC_HTTP_ATTEMPTS_PER_SCAN = MAX_PUBLIC_READS_PER_SCAN * (MAX_RETRIES_PER_PUBLIC_READ + 1)
MAX_CUMULATIVE_RESPONSE_BYTES = 64 * 1024**2
MAX_CONTROL_FILE_BYTES = 1_000_000
MAX_SNAPSHOT_BYTES = 48 * 1024**2
DEFAULT_REQUEST_INTERVAL_SECONDS = REQUEST_INTERVAL_SECONDS

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_OBSERVATORY_ROOT = _REPOSITORY_ROOT / "data" / "veritas-observatory"
DEFAULT_ROOT = _REPOSITORY_ROOT / "data" / "veritas-observatory-discovery-successor-001"
DEFAULT_CONTROL_FILE = ACTIVE_OBSERVATORY_ROOT / "control-cohort.json"


def _isolated_root(root: Path) -> Path:
    requested = root.expanduser()
    if requested.is_symlink():
        raise ValueError("Discovery-successor root cannot be a symlink")
    resolved = requested.resolve(strict=False)
    active = ACTIVE_OBSERVATORY_ROOT.resolve(strict=False)
    if resolved == active or resolved.is_relative_to(active) or active.is_relative_to(resolved):
        raise ValueError("Discovery-successor root must be separate from the active observer root")
    return resolved


def _read_control_cohort(path: Path) -> tuple[list[str], str, str]:
    control_path = path.expanduser()
    if control_path.is_symlink() or not control_path.is_file():
        raise ValueError("Frozen control cohort must be a regular, non-symlink file")
    before = control_path.stat()
    if before.st_size > MAX_CONTROL_FILE_BYTES:
        raise ValueError("Frozen control cohort exceeds its byte bound")
    payload = control_path.read_bytes()
    after = control_path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("Frozen control cohort changed while it was being read")
    try:
        record = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Frozen control cohort is not valid JSON") from error
    if not isinstance(record, dict) or record.get("version") not in {
        CONTROL_COHORT_VERSION,
        LEGACY_CONTROL_COHORT_VERSION,
    }:
        raise ValueError("Frozen control cohort has an unsupported version")
    market_ids = record.get("market_ids")
    if (
        not isinstance(market_ids, list)
        or not 1 <= len(market_ids) <= MAX_CONTROL_MARKETS
        or any(not isinstance(value, (str, int)) or isinstance(value, bool) for value in market_ids)
    ):
        raise ValueError("Frozen control cohort must contain 1..8 market IDs")
    ids = [str(value) for value in market_ids]
    if len(ids) != len(set(ids)) or any(not value.isdecimal() for value in ids):
        raise ValueError("Frozen control IDs must be unique decimal market IDs")
    return ids, str(record["version"]), _sha256(payload)


class DiscoverySuccessorClient(PublicReadClient):
    """Reuse the allowlisted reader while enforcing the successor's 8-read plan."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        min_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(
            transport=transport,
            min_interval_seconds=min_interval_seconds,
            max_requests=DISCOVERY_QUERIES + 1,
        )
        # The base constructor protects v2 at seven calls. This isolated path
        # explicitly reserves the eighth call for its single books batch.
        self.max_requests = MAX_PUBLIC_READS_PER_SCAN
        self.min_interval_seconds = min_interval_seconds
        self.frame_reads = 0
        self.control_lookup_done = False
        self.books_done = False
        self.response_bytes = 0

    def _account_response(self, receipt: dict[str, Any]) -> None:
        response_bytes = receipt.get("response_bytes")
        if not isinstance(response_bytes, int) or response_bytes < 0:
            raise ValueError("Public response receipt has an invalid byte count")
        self.response_bytes += response_bytes
        if self.response_bytes > MAX_CUMULATIVE_RESPONSE_BYTES:
            raise ValueError("Discovery-successor cumulative response budget exceeded")

    async def discover(self, params: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.control_lookup_done or self.frame_reads >= DISCOVERY_QUERIES:
            raise ValueError("Discovery successor accepts exactly six Gamma frame reads")
        rows, receipt = await super().discover(params)
        self._account_response(receipt)
        self.frame_reads += 1
        return rows, receipt

    async def direct_control_lookup(
        self, market_ids: list[str]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.frame_reads != DISCOVERY_QUERIES or self.control_lookup_done:
            raise ValueError("Direct control lookup must follow all six discovery frames")
        rows, receipt = await super().discover({"id": market_ids, "closed": "any"})
        self._account_response(receipt)
        self.control_lookup_done = True
        return rows, receipt

    async def books(self, asset_ids: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not self.control_lookup_done or self.books_done:
            raise ValueError("The batched books read must follow the direct control lookup")
        rows, receipt = await super().books(asset_ids)
        self._account_response(receipt)
        self.books_done = True
        return rows, receipt


def _same_market_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("condition") == right.get("condition")
        and left.get("protocol") == right.get("protocol")
        and left.get("pair_semantics") == right.get("pair_semantics")
        and left.get("outcomes") == right.get("outcomes")
    )


def _verified_control_overlay(
    frame_eligible: list[dict[str, Any]],
    discovery: dict[str, Any],
    market_ids: list[str],
    direct_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    """Return eligible frame rows plus only directly verified frozen controls."""
    rows_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unexpected_ids: set[str] = set()
    controls = set(market_ids)
    for raw in direct_rows:
        raw_id = raw.get("id")
        if raw_id is None:
            continue
        market_id = str(raw_id)
        if market_id not in controls:
            unexpected_ids.add(market_id)
        else:
            rows_by_id[market_id].append(raw)

    frame_by_id = {str(row["market_id"]): row for row in frame_eligible}
    discovered_by_id = {
        str(row.get("market_id")): row
        for row in discovery.get("universe", [])
        if isinstance(row, dict) and row.get("market_id") is not None
    }
    base_outcomes = summarize_control_rows(market_ids, direct_rows)
    if len(base_outcomes) < len(market_ids):
        raise ValueError("Direct control response did not classify every requested ID")

    selected_controls: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    direct_only_count = 0
    for market_id, base in zip(market_ids, base_outcomes[: len(market_ids)], strict=True):
        outcome = dict(base)
        frame_row = frame_by_id.get(market_id)
        frame_discovery = discovered_by_id.get(market_id)
        outcome["present_in_six_frame_union"] = frame_discovery is not None

        matches = rows_by_id.get(market_id, [])
        if unexpected_ids:
            outcome["classification"] = "direct_lookup_returned_unexpected_ids"
            outcome["unexpected_market_ids_set_sha256"] = _sha256(
                _canonical(sorted(unexpected_ids))
            )
        elif len(matches) != 1:
            # A missing or duplicate direct result cannot enter the stable
            # control cohort, even if the ID appeared in a Gamma frame.
            pass
        else:
            raw = matches[0]
            normalized, reason = normalize_market(raw)
            if normalized is None:
                outcome["classification"] = "returned_but_ineligible"
                outcome["ineligibility_reason"] = reason or "unknown_exclusion"
            elif frame_discovery is not None and not frame_discovery.get(
                "eligible_for_pair_observation", False
            ):
                outcome["classification"] = "conflict_with_ineligible_frame_record"
                outcome["frame_exclusion_reason"] = frame_discovery.get("exclusion_reason")
            elif frame_row is not None and not _same_market_identity(frame_row, normalized):
                outcome["classification"] = "identity_conflict_with_six_frame_record"
            else:
                candidate = _enrich_candidate(raw, normalized, ["frozen_control_id_lookup"])
                selected_controls.append(candidate)
                if frame_row is None:
                    direct_only_count += 1
                    outcome["classification"] = "eligible_direct_only_control"
                else:
                    outcome["classification"] = "eligible_current_market_metadata"

        outcomes.append(outcome)

    rotating_rows = [row for row in frame_eligible if str(row["market_id"]) not in controls]
    overlay = {
        "version": "veritas-direct-frozen-control-overlay-v1",
        "requested_market_count": len(market_ids),
        "eligible_control_count": len(selected_controls),
        "direct_only_eligible_control_count": direct_only_count,
        "rotating_frame_eligible_population": len(rotating_rows),
        "unexpected_market_id_count": len(unexpected_ids),
        "outcomes": outcomes,
        "limitations": [
            "Direct-ID metadata is a separate query receipt and is not part of the six-frame discovery denominator.",
            "A control enters the stable cohort only when exactly one direct row is returned, it is currently eligible, and its identity does not conflict with the frame record.",
            "Rotation probabilities remain conditional on the six-frame eligible population after frozen control IDs are removed.",
        ],
    }
    return [*rotating_rows, *selected_controls], overlay, direct_only_count


def _source_code_hash() -> str:
    digest = hashlib.sha256()
    for name in (
        "discovery_successor.py",
        "observatory.py",
        "opportunity_audit_v2.py",
        "economics.py",
        "control_retrieval.py",
    ):
        path = Path(__file__).with_name(name)
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _root_bytes(root: Path) -> int:
    return sum(
        path.stat().st_size for path in root.rglob("*") if path.is_file() and not path.is_symlink()
    )


def _collect_observations(
    selected: list[dict[str, Any]],
    raw_books: list[dict[str, Any]],
    book_receipt: dict[str, Any],
    quantity_grid: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    books_by_asset: dict[str, dict[str, Any]] = {}
    duplicate_assets: set[str] = set()
    for raw in raw_books:
        asset = str(raw.get("asset_id") or raw.get("assetId") or "")
        if not asset or asset in books_by_asset:
            duplicate_assets.add(asset or "missing_asset_id")
            continue
        books_by_asset[asset] = raw

    observations: list[dict[str, Any]] = []
    invalid_reasons: Counter[str] = Counter()
    age_bands: dict[str, Counter[str]] = {"yes": Counter(), "no": Counter()}
    age_above: Counter[str] = Counter()
    skew_bands: Counter[str] = Counter()
    skew_above = 0
    quantity_counts: dict[str, Counter[str]] = {
        "positive_full_depth_gross": Counter(),
        "positive_minimum_notional": Counter(),
        "positive_minimum_order_shares": Counter(),
        "positive_order_constraints": Counter(),
        "positive_single_match": Counter(),
        "positive_fragmentation_safe": Counter(),
    }

    for row in selected:
        two_books: dict[str, dict[str, Any]] = {}
        for side in ("yes", "no"):
            asset = row["outcomes"][side]
            if asset in books_by_asset:
                two_books[asset] = books_by_asset[asset]
        if duplicate_assets:
            audit: dict[str, Any] = {
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
                reported_update_age_threshold_ms=5_000,
                reported_update_skew_diagnostic_threshold_ms=250,
            )
        if not audit["valid"]:
            invalid_reasons[str(audit.get("reason") or "invalid_snapshot")] += 1
        else:
            quality = audit["quality"]
            for side, age_ms in quality["reported_update_age_ms_by_leg"].items():
                # Keep the same diagnostic bands as the existing observer.
                age_bands[side][_reported_age_band(age_ms)] += 1
                if age_ms > 5_000:
                    age_above[side] += 1
            skew = quality["reported_update_timestamp_skew_ms"]
            skew_bands[_reported_skew_band(skew)] += 1
            if quality["reported_update_timestamp_skew_above_diagnostic_threshold"]:
                skew_above += 1
            for result in audit["quantity_results"]:
                quantity = result["quantity_shares_per_leg"]
                if result["positive_full_depth_gross"]:
                    quantity_counts["positive_full_depth_gross"][quantity] += 1
                if (
                    result["positive_full_depth_gross"]
                    and result["minimum_order_notional_satisfied"]
                ):
                    quantity_counts["positive_minimum_notional"][quantity] += 1
                if result["positive_full_depth_gross"] and result["minimum_order_shares_satisfied"]:
                    quantity_counts["positive_minimum_order_shares"][quantity] += 1
                if (
                    result["positive_full_depth_gross"]
                    and result["minimum_order_constraints_satisfied"]
                ):
                    quantity_counts["positive_order_constraints"][quantity] += 1
                if result["positive_single_match_sensitivity"]:
                    quantity_counts["positive_single_match"][quantity] += 1
                if result["positive_fragmentation_safe_sensitivity"]:
                    quantity_counts["positive_fragmentation_safe"][quantity] += 1

        quantity_rows = audit.get("quantity_results", [])
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
                "gross_positive_quantities": [
                    item["quantity_shares_per_leg"]
                    for item in quantity_rows
                    if item.get("positive_full_depth_gross")
                ],
                "positive_minimum_notional_quantities": [
                    item["quantity_shares_per_leg"]
                    for item in quantity_rows
                    if item.get("positive_full_depth_gross")
                    and item.get("minimum_order_notional_satisfied")
                ],
                "positive_minimum_order_shares_quantities": [
                    item["quantity_shares_per_leg"]
                    for item in quantity_rows
                    if item.get("positive_full_depth_gross")
                    and item.get("minimum_order_shares_satisfied")
                ],
                "positive_order_constraints_quantities": [
                    item["quantity_shares_per_leg"]
                    for item in quantity_rows
                    if item.get("positive_full_depth_gross")
                    and item.get("minimum_order_constraints_satisfied")
                ],
                "positive_single_match_quantities": [
                    item["quantity_shares_per_leg"]
                    for item in quantity_rows
                    if item.get("positive_single_match_sensitivity")
                ],
                "positive_fragmentation_safe_quantities": [
                    item["quantity_shares_per_leg"]
                    for item in quantity_rows
                    if item.get("positive_fragmentation_safe_sensitivity")
                ],
                "books": market_books,
                "book_source_sha256": book_receipt["response_sha256"],
            }
        )

    counts = {
        "selected_markets": len(selected),
        "valid_quality_pairs": sum(bool(row["audit"]["valid"]) for row in observations),
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "reported_update_age_bands_by_leg": {
            side: dict(sorted(bands.items())) for side, bands in age_bands.items()
        },
        "reported_update_age_above_5s_by_leg": {
            side: age_above.get(side, 0) for side in ("yes", "no")
        },
        "reported_update_timestamp_skew_bands": dict(sorted(skew_bands.items())),
        "reported_update_timestamp_skew_above_250ms_pairs": skew_above,
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
        "positive_minimum_order_shares_by_quantity": {
            quantity: quantity_counts["positive_minimum_order_shares"].get(quantity, 0)
            for quantity in quantity_grid
        },
        "positive_order_constraints_by_quantity": {
            quantity: quantity_counts["positive_order_constraints"].get(quantity, 0)
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
    return observations, counts


def _successor_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(report)
    summary["analysis_version"] = VERSION
    summary.pop("measurement_pilot", None)
    summary["authenticated_requests"] = False
    summary["source_public_read_calls"] = report["source_requests"]["public_read_calls"]
    summary["source_response_bytes"] = report["source_requests"]["response_bytes"]
    summary["discovery"]["frame_protocol"] = FRAME_PROTOCOL
    summary["discovery"]["direct_control_lookup"] = {
        "version": report["direct_control_lookup"]["version"],
        "requested_market_count": report["direct_control_lookup"]["requested_market_count"],
        "eligible_control_count": report["direct_control_lookup"]["eligible_control_count"],
        "direct_only_eligible_control_count": report["direct_control_lookup"][
            "direct_only_eligible_control_count"
        ],
        "unexpected_market_id_count": report["direct_control_lookup"]["unexpected_market_id_count"],
    }
    summary["selection"].update(
        {
            "frame_eligible_population": report["selection"]["frame_eligible_population"],
            "rotating_frame_eligible_population": report["selection"][
                "rotating_frame_eligible_population"
            ],
            "direct_only_eligible_control_count": report["direct_control_lookup"][
                "direct_only_eligible_control_count"
            ],
        }
    )
    summary["collection_bounds"] = report["collection_bounds"]
    summary["coverage_kind"] = "intermittent_public_snapshots_with_direct_control_overlay"
    return summary


async def run_discovery_successor(
    root: Path = DEFAULT_ROOT,
    *,
    control_file: Path = DEFAULT_CONTROL_FILE,
    target_markets: int = DEFAULT_MARKETS,
    seed: int = DEFAULT_SEED,
    quantity_grid: tuple[str, ...] = DEFAULT_QUANTITIES,
    transport: httpx.AsyncBaseTransport | None = None,
    request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Run one isolated six-frame + direct-controls + batch-books scan."""
    if not 30 <= target_markets <= MAX_MARKETS:
        raise ValueError("Discovery successor supports 30..50 selected markets")
    if not 1 <= len(quantity_grid) <= 10 or len(set(quantity_grid)) != len(quantity_grid):
        raise ValueError("Quantity grid must contain 1..10 unique values")
    if request_interval_seconds < 0.2:
        raise ValueError("Public read interval must be at least 0.2 seconds")

    root = _isolated_root(Path(root))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink():
        raise ValueError("Discovery-successor root cannot be a symlink")
    root = root.resolve()
    snapshots = root / "snapshots"
    snapshots.mkdir(exist_ok=True, mode=0o700)
    if snapshots.is_symlink():
        raise ValueError("Discovery-successor snapshot directory cannot be a symlink")
    lock_path = root / "run.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("A discovery-successor scan already owns this root") from error

        total_bytes = _root_bytes(root)
        if total_bytes + MAX_ANALYSIS_RESERVE_BYTES >= MAX_ROOT_BYTES:
            raise ValueError("Discovery-successor evidence budget reached")
        state_path = root / "state.json"
        state = _safe_json(state_path, max_bytes=MAX_STATE_BYTES) if state_path.exists() else {}
        if state is None:
            state = {}
        if state and state.get("version") != VERSION:
            raise ValueError("Discovery-successor state belongs to an unsupported version")
        sequence = state.get("next_sequence", 1)
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise ValueError("Malformed discovery-successor sequence")
        history = state.get("snapshot_history", {})
        if not isinstance(history, dict):
            raise ValueError("Malformed discovery-successor activity history")
        control_ids, control_version, control_sha256 = _read_control_cohort(Path(control_file))
        if len(control_ids) > target_markets:
            raise ValueError("Frozen control cohort cannot exceed the selected-market target")

        client = DiscoverySuccessorClient(
            transport=transport,
            min_interval_seconds=request_interval_seconds,
        )
        try:
            discovery_started_ns = time.time_ns()
            frame_eligible, discovery = await discover_universe(
                client, now_ns=discovery_started_ns, seed=seed
            )
            direct_rows, direct_receipt = await client.direct_control_lookup(control_ids)
            eligible_pool, control_overlay, direct_only_count = _verified_control_overlay(
                frame_eligible, discovery, control_ids, direct_rows
            )
            if not eligible_pool:
                raise RuntimeError("No eligible markets remain after direct control verification")

            selected, selection_plan, _ = select_cohort(
                eligible_pool,
                target=target_markets,
                control_count=len(control_ids),
                seed=seed,
                sequence=sequence,
                frozen_control_ids=control_ids,
                history=history,
            )
            selection_plan["augmented_selection_population"] = len(eligible_pool)
            selection_plan["bounded_eligible_population"] = len(frame_eligible)
            selection_plan["probability_scope"] = (
                "rotating inclusion is conditional on the six-frame eligible union after all "
                "frozen-control IDs are removed; stable controls are conditional on the "
                "pre-frozen control cohort and direct-ID eligibility"
            )
            if not selected:
                raise RuntimeError("No markets were selected from the verified bounded universe")
            requested_assets = [row["outcomes"][side] for row in selected for side in ("yes", "no")]
            raw_books, book_receipt = await client.books(requested_assets)
            if (
                client.requests != MAX_PUBLIC_READS_PER_SCAN
                or client.frame_reads != DISCOVERY_QUERIES
                or not client.control_lookup_done
                or not client.books_done
            ):
                raise RuntimeError(
                    "Discovery-successor request plan did not reconcile to eight reads"
                )

            observations, counts = _collect_observations(
                selected, raw_books, book_receipt, quantity_grid
            )
            captured_ns = book_receipt["received_at_ns"]
            captured = datetime.fromtimestamp(captured_ns / 1_000_000_000, UTC)
            source_code_sha256 = _source_code_hash()
            direct_only_ids = {
                row["market_id"]
                for row in selected
                if row["cohort_role"] == "stable_random_control"
                and row["market_id"] not in {item["market_id"] for item in frame_eligible}
            }
            selection_summary = {
                "plan": selection_plan,
                "frame_eligible_population": len(frame_eligible),
                "rotating_frame_eligible_population": control_overlay[
                    "rotating_frame_eligible_population"
                ],
                "direct_only_control_ids_sha256": _sha256(_canonical(sorted(direct_only_ids))),
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
            }
            gamma_receipts = discovery["queries"]
            evidence_material = {
                "gamma_response_hashes": [row["response_sha256"] for row in gamma_receipts],
                "direct_control_response_sha256": direct_receipt["response_sha256"],
                "clob_response_sha256": book_receipt["response_sha256"],
                "control_cohort_sha256": control_sha256,
                "source_code_sha256": source_code_sha256,
                "captured_ns": captured_ns,
                "selection_seed": seed,
                "sequence": sequence,
                "read_count": client.requests,
            }
            snapshot_evidence_sha256 = _sha256(_canonical(evidence_material))
            scan_id = (
                f"scan-a2-{captured.strftime('%Y%m%dT%H%M%SZ')}-{snapshot_evidence_sha256[:12]}"
            )
            snapshot_rel = f"snapshots/{scan_id}.json.gz"
            for row in observations:
                if row["gross_positive_quantities"]:
                    row["candidate_source"] = {
                        "snapshot_file": snapshot_rel,
                        "snapshot_evidence_sha256": snapshot_evidence_sha256,
                        "book_source_sha256": row["book_source_sha256"],
                        "raw_market_metadata_sha256": row["raw_market_metadata_sha256"],
                    }

            report: dict[str, Any] = {
                "schema_version": 1,
                "analysis_version": VERSION,
                "discovery_frame_protocol": FRAME_PROTOCOL,
                "quantity_grid": list(quantity_grid),
                "captured_at_utc": captured.isoformat(),
                "captured_ns": captured_ns,
                "coverage_kind": "intermittent_public_snapshots_with_direct_control_overlay",
                "collection_bounds": {
                    "target_markets": target_markets,
                    "maximum_markets": MAX_MARKETS,
                    "gamma_frame_reads_per_scan": DISCOVERY_QUERIES,
                    "gamma_control_reads_per_scan": 1,
                    "clob_books_reads_per_scan": 1,
                    "maximum_public_read_calls_per_scan": MAX_PUBLIC_READS_PER_SCAN,
                    "maximum_public_http_attempts_per_scan": MAX_PUBLIC_HTTP_ATTEMPTS_PER_SCAN,
                    "maximum_retries_per_public_read": MAX_RETRIES_PER_PUBLIC_READ,
                    "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
                    "maximum_response_bytes_per_read": MAX_RESPONSE_BYTES,
                    "maximum_cumulative_response_bytes": MAX_CUMULATIVE_RESPONSE_BYTES,
                    "minimum_request_interval_seconds": request_interval_seconds,
                    "maximum_root_bytes": MAX_ROOT_BYTES,
                },
                "control_cohort": {
                    "version": control_version,
                    "requested_market_count": len(control_ids),
                    "market_ids_set_sha256": _sha256(_canonical(sorted(control_ids))),
                    "source_file_sha256": control_sha256,
                },
                "source_code_sha256": source_code_sha256,
                "discovery": discovery,
                "direct_control_lookup": {
                    **control_overlay,
                    "request_receipt": direct_receipt,
                },
                "selection": selection_summary,
                "source_requests": {
                    "public_read_calls": client.requests,
                    "public_http_attempts": client.request_attempts,
                    "response_bytes": client.response_bytes,
                    "gamma_pages": gamma_receipts,
                    "direct_control_lookup": direct_receipt,
                    "clob_books": book_receipt,
                },
                "counts": counts,
                "market_observations": observations,
                "snapshot_evidence_sha256": snapshot_evidence_sha256,
                "scan_id": scan_id,
                "snapshot_file": snapshot_rel,
                "limitations": [
                    "Six Gamma discovery pages remain a bounded query union, not a venue-wide denominator.",
                    "Frozen-control lookup results are reported separately from the six-frame discovery population.",
                    "Rotation probabilities are conditional on the bounded six-frame eligible population and the frozen control cohort.",
                    "The snapshot-change stratum is based on intermittent snapshots, not venue WebSocket update rates.",
                    "A batched books response does not prove atomicity, venue sequence ordering, upstream queue age, quote persistence, or fills.",
                    "Only same-condition V1 binary pairs are evaluated economically; other payoff structures remain excluded.",
                    "This version does not write to or advance the v1 measurement pilot or finalized-source analysis state.",
                ],
                "orders_submitted": False,
                "authenticated_requests": False,
            }
            compressed = gzip.compress(_canonical(report), compresslevel=6, mtime=0)
            if len(compressed) > MAX_SNAPSHOT_BYTES:
                raise ValueError("Discovery-successor snapshot exceeds its artifact bound")
            if total_bytes + len(compressed) + MAX_ANALYSIS_RESERVE_BYTES >= MAX_ROOT_BYTES:
                raise ValueError("Discovery-successor root budget would be exceeded")
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

            for observation in observations:
                state_hash = _book_state_hash(observation["books"], observation)
                if not state_hash:
                    continue
                market_history = history.setdefault(observation["market_id"], [])
                market_history.append({"captured_ns": captured_ns, "state_hash": state_hash})
                history[observation["market_id"]] = market_history[-12:]
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
            next_state = {
                "version": VERSION,
                "next_sequence": sequence + 1,
                "last_scan_id": scan_id,
                "last_captured_ns": captured_ns,
                "snapshot_history": history,
            }
            if len(_canonical(next_state)) > MAX_STATE_BYTES:
                raise ValueError("Discovery-successor activity state exceeds its byte bound")
            _atomic_json(state_path, next_state)
            latest = _successor_summary(report)
            _atomic_json(root / "latest-summary.json", latest)
            return report
        finally:
            await client.close()


def require_fixed_pilot_stop(pilot_root: Path = ACTIVE_OBSERVATORY_ROOT) -> None:
    """Refuse CLI activation until the fixed v1 pilot's immutable stop time."""
    latest_path = pilot_root / "latest-summary.json"
    summary = _safe_json(latest_path, max_bytes=MAX_STATE_BYTES)
    if summary is None:
        raise RuntimeError("Cannot verify the fixed v1 pilot stop time")
    pilot = summary.get("measurement_pilot")
    if not isinstance(pilot, dict):
        raise RuntimeError("Cannot verify the fixed v1 pilot stop time")
    end = pilot.get("ends_at_utc")
    if not isinstance(end, str):
        raise RuntimeError("Fixed v1 pilot has no recorded stop time")
    try:
        end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError("Fixed v1 pilot stop time is malformed") from error
    if end_at.tzinfo is None or datetime.now(UTC) < end_at.astimezone(UTC):
        raise RuntimeError("Discovery successor is held until the fixed v1 pilot stop time")
