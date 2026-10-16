"""Bounded source replay for quality-valid positive gross candidate pointers."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .continuous_analysis import VERSION as SNAPSHOT_ANALYSIS_VERSION
from .opportunity_audit_v2 import audit_pair_snapshot, normalize_market

VERSION = "veritas-gross-candidate-source-replay-v2"
MAX_CANDIDATES = 256
MAX_SNAPSHOT_COUNT = 128
MAX_TOTAL_COMPRESSED_BYTES = 96 * 1024**2
MAX_COMPRESSED_SNAPSHOT_BYTES = 48 * 1024**2
MAX_DECOMPRESSED_SNAPSHOT_BYTES = 48 * 1024**2
MAX_EVENT_BYTES = 2 * 1024**2
SCAN_ID = re.compile(r"scan-\d{8}T\d{6}Z-[0-9a-f]{12}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_code_sha256() -> str:
    """Hash the replay and its economic-audit dependencies for artifact lineage."""
    digest = hashlib.sha256()
    for name in ("candidate_replay.py", "opportunity_audit_v2.py", "economics.py"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid_{field}")
    return value


def _decimal(value: Any, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"invalid_{field}") from error
    if not parsed.is_finite():
        raise ValueError(f"invalid_{field}")
    return parsed


def _verify_response(record: Any, field: str) -> tuple[str, str]:
    if not isinstance(record, dict):
        raise ValueError(f"missing_{field}_response")
    payload = record.get("response_payload")
    digest = record.get("response_sha256")
    if not isinstance(payload, str) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError(f"invalid_{field}_response_identity")
    wire = payload.encode("utf-8")
    if _sha256(wire) != digest:
        raise ValueError(f"{field}_response_digest_mismatch")
    response_bytes = record.get("response_bytes")
    if response_bytes is not None and _integer(response_bytes, f"{field}_response_bytes") != len(
        wire
    ):
        raise ValueError(f"{field}_response_length_mismatch")
    return payload, digest


def _read_snapshot(path: Path, scan_id: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("snapshot_missing_or_unsafe")
    if path.stat().st_size > MAX_COMPRESSED_SNAPSHOT_BYTES:
        raise ValueError("snapshot_compressed_size_exceeds_bound")
    try:
        with gzip.open(path, "rb") as handle:
            raw = handle.read(MAX_DECOMPRESSED_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_DECOMPRESSED_SNAPSHOT_BYTES:
            raise ValueError("snapshot_decompressed_size_exceeds_bound")
        value = json.loads(raw)
    except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as error:
        raise ValueError("snapshot_unreadable") from error
    if not isinstance(value, dict) or value.get("scan_id") != scan_id:
        raise ValueError("snapshot_identity_mismatch")
    return value


def _read_event(root: Path, scan_id: str) -> dict[str, Any]:
    event_dir = root / "analysis-events" / "v4"
    path = event_dir / f"{scan_id}.json"
    if root.joinpath("analysis-events").is_symlink() or event_dir.is_symlink():
        raise ValueError("analysis_event_directory_unsafe")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_EVENT_BYTES:
        raise ValueError("analysis_event_missing_or_unsafe")
    try:
        event = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("analysis_event_unreadable") from error
    if not isinstance(event, dict) or event.get("scan_id") != scan_id:
        raise ValueError("analysis_event_identity_mismatch")
    if event.get("analysis_version") != SNAPSHOT_ANALYSIS_VERSION:
        raise ValueError("analysis_event_version_mismatch")
    claimed = event.get("analysis_event_sha256")
    payload = dict(event)
    payload.pop("analysis_event_sha256", None)
    if not isinstance(claimed, str) or claimed != _sha256(_canonical(payload)):
        raise ValueError("analysis_event_digest_mismatch")
    return event


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


def _independent_asks(
    book: dict[str, Any], side: str, tick_size: Decimal
) -> list[tuple[Decimal, Decimal]]:
    raw_asks = book.get("asks")
    if not isinstance(raw_asks, list) or not raw_asks:
        raise ValueError(f"independent_{side}_ask_levels_missing")
    by_price: dict[Decimal, Decimal] = {}
    for level in raw_asks:
        if not isinstance(level, dict):
            raise ValueError(f"independent_{side}_ask_level_invalid")
        price = _decimal(level.get("price"), f"{side}_ask_price")
        size = _decimal(level.get("size"), f"{side}_ask_size")
        if price < 0 or price > 1 or size <= 0 or price % tick_size != 0:
            raise ValueError(f"independent_{side}_ask_level_out_of_bounds")
        by_price[price] = by_price.get(price, Decimal(0)) + size
    return sorted(by_price.items())


def _independent_depth(
    asks: list[tuple[Decimal, Decimal]], quantity: Decimal
) -> tuple[bool, Decimal, list[dict[str, str]]]:
    remaining = quantity
    notional = Decimal(0)
    used: list[dict[str, str]] = []
    for price, available in asks:
        take = min(remaining, available)
        if take > 0:
            level_cost = take * price
            notional += level_cost
            remaining -= take
            used.append({"price": str(price), "quantity": str(take), "notional": str(level_cost)})
        if remaining == 0:
            break
    return remaining == 0, notional, used


def _validate_snapshot_source(
    snapshot: dict[str, Any], candidate: dict[str, Any]
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[list[dict[str, Any]]],
    dict[str, dict[str, Any]],
]:
    interval = candidate.get("source_interval")
    if not isinstance(interval, dict):
        raise ValueError("candidate_source_interval_missing")
    scan_id = interval.get("scan_id")
    if not isinstance(scan_id, str) or not SCAN_ID.fullmatch(scan_id):
        raise ValueError("candidate_scan_id_invalid")
    expected_file = f"snapshots/{scan_id}.json.gz"
    if (
        interval.get("snapshot_file") != expected_file
        or snapshot.get("snapshot_file") != expected_file
    ):
        raise ValueError("snapshot_relative_path_mismatch")
    if snapshot.get("snapshot_evidence_sha256") != interval.get("snapshot_evidence_sha256"):
        raise ValueError("snapshot_evidence_digest_mismatch")
    source_code_sha256 = snapshot.get("source_code_sha256")
    if (
        not isinstance(source_code_sha256, str)
        or not SHA256.fullmatch(source_code_sha256)
        or source_code_sha256 != interval.get("snapshot_source_code_sha256")
    ):
        raise ValueError("snapshot_source_code_digest_mismatch")
    captured_ns = _integer(snapshot.get("captured_ns"), "captured_ns")
    if captured_ns != interval.get("captured_ns"):
        raise ValueError("snapshot_capture_time_mismatch")
    if snapshot.get("captured_at_utc") != interval.get("captured_at_utc"):
        raise ValueError("snapshot_capture_label_mismatch")
    if (
        snapshot.get("orders_submitted") is not False
        or snapshot.get("authenticated_requests") is not False
    ):
        raise ValueError("snapshot_read_only_boundary_invalid")

    source_requests = snapshot.get("source_requests")
    selection = snapshot.get("selection")
    if not isinstance(source_requests, dict) or not isinstance(selection, dict):
        raise ValueError("snapshot_source_material_missing")
    gamma_pages = source_requests.get("gamma_pages")
    plan = selection.get("plan")
    if not isinstance(gamma_pages, list) or not gamma_pages or not isinstance(plan, dict):
        raise ValueError("snapshot_discovery_source_material_missing")
    discovery = snapshot.get("discovery")
    if not isinstance(discovery, dict) or discovery.get("queries") != gamma_pages:
        raise ValueError("snapshot_gamma_lineage_mismatch")

    gamma_payloads: list[str] = []
    gamma_hashes: list[str] = []
    for page in gamma_pages:
        payload, digest = _verify_response(page, "gamma")
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("gamma_response_unreadable") from error
        if not isinstance(parsed, list) or any(not isinstance(row, dict) for row in parsed):
            raise ValueError("gamma_response_shape_invalid")
        gamma_payloads.append(payload)
        gamma_hashes.append(digest)

    clob = source_requests.get("clob_books")
    clob_payload, clob_digest = _verify_response(clob, "clob")
    if not isinstance(clob, dict):
        raise ValueError("clob_response_shape_invalid")
    plan_selected = selection.get("selected_markets")
    if not isinstance(plan_selected, list):
        raise ValueError("snapshot_selection_missing")
    observation_rows = snapshot.get("market_observations")
    if not isinstance(observation_rows, list):
        raise ValueError("snapshot_market_observations_missing")
    observations_by_market: dict[str, dict[str, Any]] = {}
    for row in observation_rows:
        if not isinstance(row, dict):
            raise ValueError("snapshot_market_observation_invalid")
        market_id = str(row.get("market_id") or "")
        if not market_id or market_id in observations_by_market:
            raise ValueError("snapshot_market_observation_identity_invalid")
        observations_by_market[market_id] = row

    requested_assets: list[str] = []
    for market in plan_selected:
        if not isinstance(market, dict):
            raise ValueError("snapshot_selected_market_invalid")
        market_id = str(market.get("market_id") or "")
        outcomes = market.get("outcomes")
        if not isinstance(outcomes, dict):
            # The first snapshot schema kept token identity on each observation
            # rather than duplicating normalized metadata in the selected row.
            observation = observations_by_market.get(market_id)
            outcomes = observation.get("outcomes") if isinstance(observation, dict) else None
        if not isinstance(outcomes, dict) or any(
            not isinstance(outcomes.get(side), (str, int)) or not str(outcomes[side])
            for side in ("yes", "no")
        ):
            raise ValueError("snapshot_selected_market_outcomes_missing")
        requested_assets.extend(str(outcomes[side]) for side in ("yes", "no"))
    request_body = [{"token_id": asset} for asset in requested_assets]
    request_sha256 = clob.get("request_sha256")
    if not isinstance(request_sha256, str) or request_sha256 != _sha256(_canonical(request_body)):
        raise ValueError("clob_request_digest_mismatch")
    if _integer(clob.get("request_asset_count"), "clob_request_asset_count") != len(
        requested_assets
    ):
        raise ValueError("clob_request_asset_count_mismatch")
    try:
        raw_books = json.loads(clob_payload)
    except json.JSONDecodeError as error:
        raise ValueError("clob_response_unreadable") from error
    if not isinstance(raw_books, list) or any(not isinstance(book, dict) for book in raw_books):
        raise ValueError("clob_response_shape_invalid")
    actual_assets = [str(book.get("asset_id") or book.get("assetId") or "") for book in raw_books]
    if (
        len(raw_books) != _integer(clob.get("response_book_count"), "clob_response_book_count")
        or len(actual_assets) != len(requested_assets)
        or len(set(actual_assets)) != len(actual_assets)
        or set(actual_assets) != set(requested_assets)
    ):
        raise ValueError("clob_response_asset_set_mismatch")
    books_by_asset = dict(zip(actual_assets, raw_books, strict=True))

    evidence_material = {
        "gamma_response_hashes": gamma_hashes,
        "clob_response_sha256": clob_digest,
        "source_code_sha256": source_code_sha256,
        "captured_ns": captured_ns,
        "selection_seed": plan.get("seed"),
        "sequence": plan.get("sequence"),
    }
    calculated_evidence = _sha256(_canonical(evidence_material))
    claimed_evidence = snapshot.get("snapshot_evidence_sha256")
    if (
        not isinstance(claimed_evidence, str)
        or claimed_evidence != calculated_evidence
        or not scan_id.endswith(calculated_evidence[:12])
    ):
        raise ValueError("snapshot_evidence_material_mismatch")
    return (
        source_requests,
        clob,
        [json.loads(payload) for payload in gamma_payloads],
        books_by_asset,
    )


def _event_candidate_row(candidate: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    interval = candidate["source_interval"]
    for field in (
        "snapshot_file",
        "snapshot_evidence_sha256",
        "snapshot_source_code_sha256",
        "captured_at_utc",
        "captured_ns",
    ):
        event_field = (
            "snapshot_source_code_sha256" if field == "snapshot_source_code_sha256" else field
        )
        if event.get(event_field) != interval.get(field):
            raise ValueError("analysis_event_source_interval_mismatch")
    if event.get("analysis_event_sha256") != interval.get("analysis_event_sha256"):
        raise ValueError("analysis_event_digest_pointer_mismatch")
    rows = event.get("market_rows")
    market_id = candidate.get("market_id")
    if not isinstance(rows, list) or not isinstance(market_id, str):
        raise ValueError("analysis_event_market_rows_missing")
    matches = [row for row in rows if isinstance(row, dict) and row.get("market_id") == market_id]
    if len(matches) != 1:
        raise ValueError("analysis_event_market_row_not_unique")
    row = matches[0]
    edge = _decimal(row.get("top_pair_gross_edge_per_share"), "event_gross_edge")
    candidate_edge = _decimal(
        candidate.get("top_pair_gross_edge_per_share"), "candidate_gross_edge"
    )
    if (
        row.get("valid") is not True
        or edge <= 0
        or edge != candidate_edge
        or row.get("sampled_book_state_hash") != interval.get("sampled_book_state_hash")
    ):
        raise ValueError("analysis_event_candidate_row_mismatch")
    positive_count = 0
    for market_row in rows:
        if isinstance(market_row, dict) and market_row.get("valid") is True:
            value = market_row.get("top_pair_gross_edge_per_share")
            if isinstance(value, str) and _decimal(value, "event_market_edge") > 0:
                positive_count += 1
    if event.get("positive_top_gross_pairs") != positive_count:
        raise ValueError("analysis_event_positive_count_mismatch")
    return row


def _replay_one(
    scan_id: str,
    candidates: list[dict[str, Any]],
    snapshot: dict[str, Any],
    event: dict[str, Any],
    quantity: str,
    source_requests: dict[str, Any],
    clob: dict[str, Any],
    gamma_responses: list[list[dict[str, Any]]],
    books_by_asset: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    discovery = snapshot.get("discovery")
    observations = snapshot.get("market_observations")
    selection = snapshot.get("selection")
    quantity_grid = snapshot.get("quantity_grid")
    if (
        not isinstance(discovery, dict)
        or not isinstance(discovery.get("universe"), list)
        or not isinstance(observations, list)
        or not isinstance(selection, dict)
        or not isinstance(selection.get("selected_markets"), list)
        or not isinstance(quantity_grid, list)
        or quantity not in [str(value) for value in quantity_grid]
    ):
        raise ValueError("snapshot_analysis_inputs_missing")
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        interval = candidate.get("source_interval")
        if not isinstance(interval, dict) or interval.get("scan_id") != scan_id:
            raise ValueError("candidate_scan_identity_mismatch")
        market_id = candidate.get("market_id")
        if not isinstance(market_id, str) or not market_id:
            raise ValueError("candidate_market_id_invalid")
        _event_candidate_row(candidate, event)

        raw_matches = [
            market
            for response in gamma_responses
            for market in response
            if str(market.get("id") or "") == market_id
        ]
        raw_hashes = {_sha256(_canonical(market)) for market in raw_matches}
        metadata_digest = next(iter(raw_hashes)) if len(raw_hashes) == 1 else None
        if not raw_matches or metadata_digest is None:
            raise ValueError("gamma_market_metadata_missing_or_conflicted")
        if interval.get("raw_market_metadata_sha256") not in (None, metadata_digest):
            raise ValueError("candidate_market_metadata_digest_mismatch")
        normalized, exclusion = normalize_market(raw_matches[0])
        if normalized is None:
            raise ValueError(f"unsupported_candidate_payoff_relationship:{exclusion}")

        universe_rows = [
            row
            for row in discovery["universe"]
            if isinstance(row, dict) and str(row.get("market_id") or "") == market_id
        ]
        selected_rows = [
            row
            for row in selection["selected_markets"]
            if isinstance(row, dict) and str(row.get("market_id") or "") == market_id
        ]
        observation_rows = [
            row
            for row in observations
            if isinstance(row, dict) and str(row.get("market_id") or "") == market_id
        ]
        if len(universe_rows) != 1 or len(selected_rows) != 1 or len(observation_rows) != 1:
            raise ValueError("snapshot_candidate_identity_not_unique")
        universe, selected, observation = universe_rows[0], selected_rows[0], observation_rows[0]
        if universe.get("eligible_for_pair_observation") is not True:
            raise ValueError("snapshot_market_not_eligible_for_pair_observation")
        normalized_fields = (
            "market_id",
            "condition",
            "protocol",
            "pair_semantics",
            "outcomes",
            "negative_risk",
            "minimum_order_notional_usdc",
            "tick_size",
            "fee_regime",
        )
        for field in normalized_fields:
            # The universe row is the normalized record in every snapshot
            # schema. Older selected rows contain only selection metadata, so
            # compare the fields they actually recorded and recover the rest
            # from the hashed Gamma payload plus observation lineage.
            if field not in universe or universe.get(field) != normalized.get(field):
                raise ValueError("gamma_market_normalization_mismatch")
            if field in selected and selected.get(field) != normalized.get(field):
                raise ValueError("gamma_market_normalization_mismatch")
        if (
            universe.get("raw_market_metadata_sha256") != metadata_digest
            or selected.get("raw_market_metadata_sha256") != metadata_digest
            or observation.get("raw_market_metadata_sha256") != metadata_digest
        ):
            raise ValueError("snapshot_market_metadata_lineage_mismatch")

        clob_payload, clob_digest = _verify_response(source_requests.get("clob_books"), "clob")
        if observation.get("book_source_sha256") != clob_digest:
            raise ValueError("snapshot_book_response_lineage_mismatch")
        outcome_ids = normalized["outcomes"]
        expected_assets = {outcome_ids["yes"], outcome_ids["no"]}
        recorded_books = observation.get("books")
        if not isinstance(recorded_books, dict) or set(recorded_books) != expected_assets:
            raise ValueError("snapshot_candidate_books_incomplete")
        sanitized_books: dict[str, dict[str, Any]] = {}
        for asset_id in expected_assets:
            raw_book = books_by_asset.get(asset_id)
            if not isinstance(raw_book, dict):
                raise ValueError("clob_candidate_book_missing")
            sanitized = _sanitize_book(raw_book)
            if recorded_books.get(asset_id) != sanitized:
                raise ValueError("snapshot_book_payload_differs_from_hashed_clob_response")
            sanitized_books[asset_id] = sanitized
        if observation.get("condition") != normalized.get("condition") or observation.get(
            "outcomes"
        ) != normalized.get("outcomes"):
            raise ValueError("snapshot_candidate_payoff_identity_mismatch")

        audit = audit_pair_snapshot(
            normalized,
            sanitized_books,
            captured_ns=_integer(clob.get("received_at_ns"), "clob_received_at_ns"),
            batch_started_ns=_integer(clob.get("requested_at_ns"), "clob_requested_at_ns"),
            quantities=tuple(str(value) for value in quantity_grid),
        )
        if audit.get("valid") is not True:
            raise ValueError("independent_source_audit_rejected_candidate_book_pair")
        tick_size = _decimal(normalized.get("tick_size"), "market_tick_size")
        asks_by_leg = {
            side: _independent_asks(sanitized_books[outcome_ids[side]], side, tick_size)
            for side in ("yes", "no")
        }
        top_asks = {side: levels[0][0] for side, levels in asks_by_leg.items()}
        replayed_edge = Decimal(1) - top_asks["yes"] - top_asks["no"]
        candidate_edge = _decimal(
            candidate.get("top_pair_gross_edge_per_share"), "candidate_gross_edge"
        )
        if replayed_edge <= 0 or replayed_edge != candidate_edge:
            raise ValueError("independent_source_gross_edge_mismatch")
        stored_audit = observation.get("audit")
        if not isinstance(stored_audit, dict) or stored_audit.get("valid") is not True:
            raise ValueError("snapshot_stored_audit_not_quality_valid")
        if (
            _decimal(stored_audit.get("top_pair_gross_edge_per_share"), "stored_gross_edge")
            != replayed_edge
        ):
            raise ValueError("snapshot_stored_gross_edge_mismatch")
        if (
            _decimal(audit.get("top_pair_gross_edge_per_share"), "audit_gross_edge")
            != replayed_edge
        ):
            raise ValueError("independent_gross_arithmetic_disagrees_with_snapshot_audit")

        sampled_hashes = [
            str(sanitized_books[outcome_ids[side]].get("hash") or "") for side in ("yes", "no")
        ]
        if any(not value for value in sampled_hashes):
            raise ValueError("candidate_book_state_hash_missing")
        sampled_hash = _sha256("|".join(sampled_hashes).encode())
        if sampled_hash != interval.get("sampled_book_state_hash"):
            raise ValueError("candidate_sampled_book_state_hash_mismatch")

        quality = audit["quality"]
        ages = quality["reported_update_age_ms_by_leg"]
        skew_ms = int(quality["reported_update_timestamp_skew_ms"])
        legacy_valid = all(int(age) <= 5_000 for age in ages.values()) and skew_ms <= 250
        event_row = _event_candidate_row(candidate, event)
        if event_row.get("legacy_freshness_valid") is not legacy_valid:
            raise ValueError("analysis_event_legacy_freshness_mismatch")
        quantity_result = next(
            (
                row
                for row in audit["quantity_results"]
                if str(row.get("quantity_shares_per_leg")) == quantity
            ),
            None,
        )
        if not isinstance(quantity_result, dict):
            raise ValueError("candidate_quantity_result_missing")
        requested_quantity = _decimal(quantity, "candidate_quantity")
        full_depth_by_leg: dict[str, bool] = {}
        notional_by_leg: dict[str, Decimal] = {}
        used_depth_by_leg: dict[str, list[dict[str, str]]] = {}
        minimum_notional_by_leg: dict[str, Decimal] = {}
        minimum_shares_by_leg: dict[str, Decimal] = {}
        market_minimum = _decimal(
            normalized.get("minimum_order_notional_usdc"), "market_minimum_order_notional"
        )
        for side in ("yes", "no"):
            full_depth_by_leg[side], notional_by_leg[side], used_depth_by_leg[side] = (
                _independent_depth(asks_by_leg[side], requested_quantity)
            )
            minimum_notional_by_leg[side] = market_minimum
            minimum_shares_by_leg[side] = _decimal(
                sanitized_books[outcome_ids[side]].get("min_order_size"),
                f"{side}_minimum_order_shares",
            )
            if minimum_shares_by_leg[side] <= 0:
                raise ValueError(f"independent_{side}_minimum_order_shares_invalid")
        full_depth = all(full_depth_by_leg.values())
        minimum_notional_met = all(
            notional_by_leg[side] >= minimum_notional_by_leg[side] for side in ("yes", "no")
        )
        minimum_shares_met = all(
            requested_quantity >= minimum_shares_by_leg[side] for side in ("yes", "no")
        )
        minimum_constraints_met = minimum_notional_met and minimum_shares_met
        independent_gross_usdc = (
            requested_quantity - sum(notional_by_leg.values(), Decimal(0)) if full_depth else None
        )
        if (
            quantity_result.get("full_depth") is not full_depth
            or quantity_result.get("minimum_order_notional_satisfied") is not minimum_notional_met
            or quantity_result.get("minimum_order_shares_satisfied") is not minimum_shares_met
            or quantity_result.get("minimum_order_constraints_satisfied")
            is not minimum_constraints_met
            or (
                independent_gross_usdc is not None
                and _decimal(
                    quantity_result.get("full_depth_gross_edge_usdc"), "audit_depth_gross_edge"
                )
                != independent_gross_usdc
            )
        ):
            raise ValueError("independent_depth_arithmetic_disagrees_with_snapshot_audit")
        fee_status = str(quantity_result.get("fee_status") or "unknown")
        fee_evaluation = quantity_result.get("hypothetical_fee_evaluation")
        compact_fee_sensitivity = (
            {
                field: fee_evaluation.get(field)
                for field in (
                    "fee_rate_by_leg",
                    "fee_exponent_by_leg",
                    "net_hypothetical_single_match_worst_resolution",
                    "net_hypothetical_fragmentation_safe_lower_by_resolution",
                )
                if field in fee_evaluation
            }
            if isinstance(fee_evaluation, dict)
            else None
        )
        single_match_positive = quantity_result.get("positive_single_match_sensitivity") is True
        fragmentation_safe_positive = (
            quantity_result.get("positive_fragmentation_safe_sensitivity") is True
        )
        result_status = (
            "GROSS_POSITIVE_REPLAYED_ECONOMIC_SENSITIVITIES_POSITIVE"
            if full_depth
            and minimum_constraints_met
            and single_match_positive
            and fragmentation_safe_positive
            else "GROSS_POSITIVE_REPLAYED_ECONOMIC_GATES_NOT_ALL_POSITIVE"
        )
        results.append(
            {
                "scan_id": scan_id,
                "market_id": market_id,
                "status": result_status,
                "top_pair_gross_edge_per_share": str(replayed_edge),
                "independent_arithmetic": {
                    "method": "decimal_best_ask_and_sorted_depth_replay-v2",
                    "best_ask_by_leg": {side: str(price) for side, price in top_asks.items()},
                    "top_pair_gross_edge_per_share": str(replayed_edge),
                    "quantity_shares_per_leg": quantity,
                    "full_depth_by_leg": full_depth_by_leg,
                    "displayed_notional_by_leg_usdc": {
                        side: str(value) for side, value in notional_by_leg.items()
                    },
                    "depth_levels_used_by_leg": used_depth_by_leg,
                    "full_depth_gross_edge_usdc": (
                        str(independent_gross_usdc) if independent_gross_usdc is not None else None
                    ),
                    "minimum_order_notional_usdc_by_leg": {
                        side: str(value) for side, value in minimum_notional_by_leg.items()
                    },
                    "minimum_order_shares_by_leg": {
                        side: str(value) for side, value in minimum_shares_by_leg.items()
                    },
                },
                "payoff_identity": audit["payoff_identity"],
                "source_integrity": {
                    "snapshot_evidence_material_verified": True,
                    "gamma_response_payloads_verified": True,
                    "clob_response_payload_verified": True,
                    "analysis_event_digest_verified": True,
                    "raw_market_metadata_verified": True,
                    "raw_book_payload_verified": True,
                },
                "freshness": {
                    "request_to_receipt_duration_ms": quality["batch_duration_ms"],
                    "request_to_receipt_gate_passed": quality["batch_duration_ms"] <= 5_000,
                    "reported_update_age_ms_by_leg": ages,
                    "reported_update_timestamp_skew_ms": skew_ms,
                    "legacy_age_and_skew_gate_passed": legacy_valid,
                    "batch_atomicity_verified": False,
                    "sequence_verified": False,
                    "upstream_queue_age_identified": False,
                },
                "quantity_qualification": {
                    "quantity_shares_per_leg": quantity,
                    "full_displayed_depth": full_depth,
                    "gross_edge_usdc": (
                        str(independent_gross_usdc) if independent_gross_usdc is not None else None
                    ),
                    "minimum_order_notional_usdc_by_leg": {
                        side: str(value) for side, value in minimum_notional_by_leg.items()
                    },
                    "minimum_order_shares_by_leg": {
                        side: str(value) for side, value in minimum_shares_by_leg.items()
                    },
                    "minimum_order_notional_satisfied_both_legs": minimum_notional_met,
                    "minimum_order_shares_satisfied_both_legs": minimum_shares_met,
                    "minimum_order_constraints_satisfied_both_legs": minimum_constraints_met,
                    "fee_status": fee_status,
                    "fee_sensitivity_basis": (
                        "shared_versioned_fee_model_recomputed_from_replayed_depth"
                    ),
                    "single_match_fee_sensitivity_positive": single_match_positive,
                    "fragmentation_safe_fee_sensitivity_positive": fragmentation_safe_positive,
                    "fee_sensitivity": compact_fee_sensitivity,
                },
                "promotion_status": "BLOCKED_NO_SEQUENCE_OR_ORDER_ARRIVAL_EVIDENCE",
            }
        )
    return results


def replay_gross_candidate_evidence(
    source_root: Path,
    candidates: list[dict[str, Any]],
    *,
    quantity: str = "20",
) -> dict[str, Any]:
    """Verify candidate pointers against hashed public responses and replay raw books."""
    source_sha256 = source_code_sha256()
    if not candidates:
        return {
            "version": VERSION,
            "source_code_sha256": source_sha256,
            "candidate_count": 0,
            "replayed_candidate_count": 0,
            "complete": True,
            "status": "NO_POSITIVE_CANDIDATES_TO_REPLAY",
            "candidates": [],
        }
    if len(candidates) > MAX_CANDIDATES:
        return {
            "version": VERSION,
            "source_code_sha256": source_sha256,
            "candidate_count": len(candidates),
            "replayed_candidate_count": 0,
            "complete": False,
            "status": "REPLAY_LIMIT_EXCEEDED",
            "candidates": [],
        }

    try:
        if source_root.is_symlink() or not source_root.is_dir():
            raise ValueError("source_root_missing_or_unsafe")
        root = source_root.resolve(strict=True)
        snapshots_dir = root / "snapshots"
        if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
            raise ValueError("snapshot_directory_missing_or_unsafe")
    except (OSError, ValueError) as error:
        return {
            "version": VERSION,
            "source_code_sha256": source_sha256,
            "candidate_count": len(candidates),
            "replayed_candidate_count": 0,
            "complete": False,
            "status": "SOURCE_REPLAY_FAILED",
            "candidates": [{"status": "SOURCE_REPLAY_FAILED", "reason": str(error)[:200]}],
        }

    groups: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    for candidate in candidates:
        interval = candidate.get("source_interval") if isinstance(candidate, dict) else None
        scan_id = interval.get("scan_id") if isinstance(interval, dict) else None
        if not isinstance(scan_id, str) or not SCAN_ID.fullmatch(scan_id):
            failures.append(
                {"status": "SOURCE_REPLAY_FAILED", "reason": "candidate_scan_id_invalid"}
            )
            continue
        groups.setdefault(scan_id, []).append(candidate)
    if len(groups) > MAX_SNAPSHOT_COUNT:
        return {
            "version": VERSION,
            "source_code_sha256": source_sha256,
            "candidate_count": len(candidates),
            "replayed_candidate_count": 0,
            "complete": False,
            "status": "REPLAY_LIMIT_EXCEEDED",
            "candidates": failures,
        }

    snapshot_bytes = 0
    replayed: list[dict[str, Any]] = []
    for scan_id, group in sorted(groups.items()):
        path = snapshots_dir / f"{scan_id}.json.gz"
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("snapshot_missing_or_unsafe")
            size = path.stat().st_size
            if size > MAX_COMPRESSED_SNAPSHOT_BYTES:
                raise ValueError("snapshot_compressed_size_exceeds_bound")
            snapshot_bytes += size
            if snapshot_bytes > MAX_TOTAL_COMPRESSED_BYTES:
                raise ValueError("total_candidate_snapshot_bytes_exceed_bound")
            for candidate in group:
                interval = candidate.get("source_interval")
                if not isinstance(interval, dict) or interval.get("snapshot_file") != (
                    f"snapshots/{scan_id}.json.gz"
                ):
                    raise ValueError("candidate_snapshot_relative_path_mismatch")
            snapshot = _read_snapshot(path, scan_id)
            source_requests, clob, gamma_responses, books_by_asset = _validate_snapshot_source(
                snapshot, group[0]
            )
            event = _read_event(root, scan_id)
            for candidate in group:
                replayed.extend(
                    _replay_one(
                        scan_id,
                        [candidate],
                        snapshot,
                        event,
                        quantity,
                        source_requests,
                        clob,
                        gamma_responses,
                        books_by_asset,
                    )
                )
        except (OSError, ValueError, TypeError, KeyError, InvalidOperation) as error:
            failures.extend(
                {
                    "scan_id": scan_id,
                    "market_id": candidate.get("market_id"),
                    "status": "SOURCE_REPLAY_FAILED",
                    "reason": str(error)[:200],
                }
                for candidate in group
            )

    results = replayed + failures
    replayed_count = len(replayed)
    complete = replayed_count == len(candidates) and not failures
    status = "ALL_GROSS_CANDIDATES_REPLAYED" if complete else "SOURCE_REPLAY_FAILED"
    return {
        "version": VERSION,
        "source_code_sha256": source_sha256,
        "candidate_count": len(candidates),
        "replayed_candidate_count": replayed_count,
        "snapshot_count": len(groups),
        "snapshot_compressed_bytes_read": snapshot_bytes,
        "complete": complete,
        "status": status,
        "candidates": results,
    }
