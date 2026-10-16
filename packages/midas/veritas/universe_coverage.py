"""Hash-verified coverage audit for finalized public observatory snapshots."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, median
from typing import Any

from .continuous_analysis import _event_from_snapshot
from .discovery_frame_analysis import analyze_snapshot_frames, summarize_frame_marginals
from .observatory import _category_metadata

ANALYSIS_VERSION = "veritas-market-universe-coverage-v1"
MAX_SNAPSHOTS = 500
MAX_COMPRESSED_SNAPSHOT_BYTES = 48 * 1024**2
MAX_UNCOMPRESSED_SNAPSHOT_BYTES = 48 * 1024**2
MAX_TOTAL_COMPRESSED_BYTES = 1024**3
MAX_RESPONSE_BYTES = 48 * 1024**2
EXPECTED_GAMMA_FRAMES = 6


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_snapshot(path: Path) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Snapshot input must be a regular file: {path.name}")
    compressed = path.read_bytes()
    if len(compressed) > MAX_COMPRESSED_SNAPSHOT_BYTES:
        raise ValueError(f"Compressed snapshot exceeds byte bound: {path.name}")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as handle:
            content = handle.read(MAX_UNCOMPRESSED_SNAPSHOT_BYTES + 1)
        if len(content) > MAX_UNCOMPRESSED_SNAPSHOT_BYTES:
            raise ValueError(f"Uncompressed snapshot exceeds byte bound: {path.name}")
        value = json.loads(content)
    except (OSError, EOFError, gzip.BadGzipFile, json.JSONDecodeError) as error:
        raise ValueError(f"Unreadable finalized snapshot: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Snapshot must contain a JSON object: {path.name}")
    expected_scan_id = path.name.removesuffix(".json.gz")
    if value.get("scan_id") != expected_scan_id:
        raise ValueError(f"Snapshot filename and scan ID disagree: {path.name}")
    return value, compressed


def _verify_snapshot(snapshot: dict[str, Any], path: Path, compressed: bytes) -> dict[str, Any]:
    if (
        snapshot.get("orders_submitted") is not False
        or snapshot.get("authenticated_requests") is not False
    ):
        raise ValueError(f"Snapshot violates the read-only boundary: {path.name}")
    source = snapshot.get("source_requests")
    discovery = snapshot.get("discovery")
    selection = snapshot.get("selection")
    if (
        not isinstance(source, dict)
        or not isinstance(discovery, dict)
        or not isinstance(selection, dict)
    ):
        raise ValueError(f"Snapshot is missing source, discovery, or selection data: {path.name}")
    pages = source.get("gamma_pages")
    plan = selection.get("plan")
    if not isinstance(pages, list) or len(pages) != EXPECTED_GAMMA_FRAMES:
        raise ValueError(f"Snapshot must retain six Gamma query responses: {path.name}")
    if discovery.get("queries") != pages or not isinstance(plan, dict):
        raise ValueError(f"Snapshot Gamma lineage or selection plan is inconsistent: {path.name}")

    frame_result = analyze_snapshot_frames(pages)
    response_hashes: list[str] = []
    raw_by_id: dict[str, dict[str, Any]] = {}
    for page in pages:
        payload = page["response_payload"].encode("utf-8")
        digest = _sha256(payload)
        response_hashes.append(digest)
        for raw in json.loads(payload):
            raw_id = raw.get("id")
            if raw_id is not None and str(raw_id):
                raw_by_id.setdefault(str(raw_id), raw)

    clob = source.get("clob_books")
    if not isinstance(clob, dict) or not isinstance(clob.get("response_payload"), str):
        raise ValueError(f"Snapshot is missing its retained public book response: {path.name}")
    clob_payload = clob["response_payload"].encode("utf-8")
    clob_digest = _sha256(clob_payload)
    if clob_digest != clob.get("response_sha256") or len(clob_payload) != clob.get(
        "response_bytes"
    ):
        raise ValueError(f"Book response receipt digest or size mismatch: {path.name}")
    if len(clob_payload) > MAX_RESPONSE_BYTES:
        raise ValueError(f"Book response exceeds byte bound: {path.name}")

    captured_ns = snapshot.get("captured_ns")
    source_code_sha256 = snapshot.get("source_code_sha256")
    if not isinstance(captured_ns, int) or captured_ns <= 0:
        raise ValueError(f"Snapshot capture timestamp is invalid: {path.name}")
    if not isinstance(source_code_sha256, str) or len(source_code_sha256) != 64:
        raise ValueError(f"Snapshot source code hash is invalid: {path.name}")
    evidence_material = {
        "gamma_response_hashes": response_hashes,
        "clob_response_sha256": clob_digest,
        "source_code_sha256": source_code_sha256,
        "captured_ns": captured_ns,
        "selection_seed": plan.get("seed"),
        "sequence": plan.get("sequence"),
    }
    evidence_digest = _sha256(_canonical(evidence_material))
    scan_id = snapshot["scan_id"]
    if snapshot.get("snapshot_evidence_sha256") != evidence_digest or not scan_id.endswith(
        evidence_digest[:12]
    ):
        raise ValueError(f"Snapshot evidence digest mismatch: {path.name}")

    universe = discovery.get("universe")
    if not isinstance(universe, list) or any(not isinstance(row, dict) for row in universe):
        raise ValueError(f"Snapshot discovery universe is malformed: {path.name}")
    universe_by_id = {str(row.get("market_id")): row for row in universe}
    if len(universe_by_id) != len(universe) or set(universe_by_id) != set(raw_by_id):
        raise ValueError(f"Snapshot discovered IDs do not match retained responses: {path.name}")
    for market_id, row in universe_by_id.items():
        expected_metadata_hash = row.get("raw_market_metadata_sha256")
        if expected_metadata_hash != _sha256(_canonical(raw_by_id[market_id])):
            raise ValueError(f"Market metadata digest mismatch for {market_id} in {path.name}")

    stored_eligible = sum(bool(row.get("eligible_for_pair_observation")) for row in universe)
    count_checks = {
        "query_candidate_records": frame_result["candidate_records"],
        "unique_market_ids": frame_result["unique_ids"],
        "duplicate_records_across_queries": frame_result["candidate_records"]
        - frame_result["unique_ids"],
        "identity_conflicts": frame_result["identity_conflicts"],
        "eligible_pair_markets": stored_eligible,
        "excluded_market_ids": len(universe) - stored_eligible,
        "query_count": len(pages),
    }
    count_matches = {key: discovery.get(key) == value for key, value in count_checks.items()}
    if not all(count_matches.values()):
        raise ValueError(f"Stored discovery counters disagree with source evidence: {path.name}")

    replay = _event_from_snapshot(snapshot, path)
    if (
        replay.get("scan_id") != scan_id
        or replay.get("snapshot_evidence_sha256") != evidence_digest
        or replay.get("attempted_market_pairs") != len(snapshot.get("market_observations", []))
    ):
        raise ValueError(f"Current source replay identity mismatch: {path.name}")

    selected = selection.get("selected_markets")
    observations = snapshot.get("market_observations")
    if not isinstance(selected, list) or not isinstance(observations, list):
        raise ValueError(f"Snapshot selection or observation list is malformed: {path.name}")
    selected_ids = [str(row.get("market_id")) for row in selected if isinstance(row, dict)]
    observed_ids = [str(row.get("market_id")) for row in observations if isinstance(row, dict)]
    if len(selected_ids) != len(selected) or len(observed_ids) != len(observations):
        raise ValueError(f"Snapshot selection or observation row is malformed: {path.name}")
    if selected_ids != observed_ids:
        raise ValueError(f"Snapshot selected cohort differs from observed books: {path.name}")

    replay_counts = replay.get("counts", {})
    age_counts = replay_counts.get("reported_update_age_bands_by_leg", {})
    stale_counts = replay_counts.get("reported_update_age_above_5s_by_leg", {})
    replay_summary = {
        "analysis_source_code_sha256": replay.get("analysis_source_code_sha256"),
        "opportunity_audit_source_code_sha256": replay.get("opportunity_audit_source_code_sha256"),
        "attempted_market_pairs": replay.get("attempted_market_pairs"),
        "valid_quality_pairs": replay.get("valid_quality_pairs"),
        "counts": {
            "invalid_reasons": replay_counts.get("invalid_reasons", {}),
            "reported_update_age_bands_by_leg": age_counts,
            "reported_update_age_above_5s_by_leg": stale_counts,
            "reported_update_timestamp_skew_bands": replay_counts.get(
                "reported_update_timestamp_skew_bands", {}
            ),
            "reported_update_timestamp_skew_above_250ms_pairs": replay_counts.get(
                "reported_update_timestamp_skew_above_250ms_pairs", 0
            ),
        },
        "positive_top_gross_pairs": replay.get("positive_top_gross_pairs", 0),
        "gross_candidate_count": len(replay.get("gross_candidates", [])),
    }

    return {
        "scan_id": scan_id,
        "captured_ns": captured_ns,
        "source_code_sha256": source_code_sha256,
        "snapshot_evidence_sha256": evidence_digest,
        "gamma_response_hashes": response_hashes,
        "compressed_snapshot_sha256": _sha256(compressed),
        "frame_result": frame_result,
        "raw_by_id": raw_by_id,
        "universe_by_id": universe_by_id,
        "selected": selected,
        "observations": observations,
        "discovery": {
            "eligible_pair_markets": stored_eligible,
            "excluded_market_ids": len(universe) - stored_eligible,
            "queries": [
                {"query_id": page["query_id"], "response_sha256": page["response_sha256"]}
                for page in pages
            ],
        },
        "selection_plan": plan,
        "capture_counts": snapshot.get("counts", {}),
        "observation_summary": replay_summary,
        "collection_bounds": snapshot.get("collection_bounds", {}),
        "source_http_attempts": snapshot.get("source_requests", {}).get("public_http_attempts", 0),
    }


def _decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite():
        return None
    return result


def _band_counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _range(values: list[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "mean": None, "max": None}
    return {
        "count": len(values),
        "min": min(values),
        "median": median(values),
        "mean": round(mean(values), 3),
        "max": max(values),
    }


def _timestamp_ns(raw: dict[str, Any]) -> int | None:
    end_date = raw.get("endDate")
    if not isinstance(end_date, str):
        return None
    try:
        value = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return None
    return int(value.timestamp() * 1_000_000_000)


def _profile(
    raw: dict[str, Any], stored: dict[str, Any] | None, captured_ns: int
) -> dict[str, Any]:
    categories, primary, _ = _category_metadata(raw)
    if stored and stored.get("eligible_for_pair_observation"):
        categories = [str(value) for value in stored.get("categories", categories)]
        primary = str(stored.get("primary_category") or primary)

    liquidity = _decimal(raw.get("liquidityNum", raw.get("liquidity")))
    if liquidity is None:
        liquidity_band = "unknown"
    elif liquidity >= Decimal("10000"):
        liquidity_band = "high"
    elif liquidity >= Decimal("1000"):
        liquidity_band = "medium"
    elif liquidity > 0:
        liquidity_band = "low"
    else:
        liquidity_band = "zero"

    end_ns = _timestamp_ns(raw)
    if end_ns is None:
        expiry_band = "unknown"
    else:
        remaining = end_ns - captured_ns
        expiry_band = (
            "near_7d"
            if remaining <= 7 * 86_400_000_000_000
            else "medium_90d"
            if remaining <= 90 * 86_400_000_000_000
            else "long"
        )

    bid = _decimal(raw.get("bestBid"))
    ask = _decimal(raw.get("bestAsk"))
    spread = _decimal(raw.get("spread"))
    if spread is None and bid is not None and ask is not None and ask >= bid:
        spread = ask - bid
    spread_band = (
        "unknown"
        if spread is None
        else "tight_le_0.01"
        if spread <= Decimal("0.01")
        else "medium_le_0.05"
        if spread <= Decimal("0.05")
        else "wide_gt_0.05"
    )
    return {
        "categories": sorted(set(categories)),
        "primary_category": primary or "unknown",
        "liquidity_band": liquidity_band,
        "expiry_band": expiry_band,
        "spread_band": spread_band,
        "eligible": bool(stored and stored.get("eligible_for_pair_observation")),
        "exclusion_reason": stored.get("exclusion_reason") if stored else "missing_universe_row",
    }


def _profile_summary(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    primary = Counter(str(row.get("primary_category") or "unknown") for row in profiles)
    categories = Counter(
        category for row in profiles for category in set(row.get("categories", []))
    )
    return {
        "market_records": len(profiles),
        "distinct_market_ids": len({str(row.get("market_id")) for row in profiles}),
        "eligible_market_records": sum(bool(row.get("eligible")) for row in profiles),
        "excluded_market_records": sum(not bool(row.get("eligible")) for row in profiles),
        "primary_category_counts": dict(sorted(primary.items())),
        "nonexclusive_category_counts": dict(sorted(categories.items())),
        "liquidity_band_counts": _band_counts(
            [str(row.get("liquidity_band") or "unknown") for row in profiles]
        ),
        "expiry_band_counts": _band_counts(
            [str(row.get("expiry_band") or "unknown") for row in profiles]
        ),
        "spread_band_counts": _band_counts(
            [str(row.get("spread_band") or "unknown") for row in profiles]
        ),
        "exclusion_reason_counts": dict(
            sorted(
                Counter(
                    str(row.get("exclusion_reason") or "none")
                    for row in profiles
                    if not row.get("eligible")
                ).items()
            )
        ),
    }


def analyze_market_universe_coverage(snapshots_dir: Path) -> dict[str, Any]:
    """Summarize saved market discovery without network or campaign access."""
    if snapshots_dir.is_symlink() or not snapshots_dir.is_dir():
        raise ValueError("Snapshot input must be a real directory")
    paths = sorted(snapshots_dir.glob("scan-*.json.gz"))
    if not paths or len(paths) > MAX_SNAPSHOTS:
        raise ValueError("Snapshot count is empty or exceeds the analysis bound")
    if any(path.is_symlink() for path in paths):
        raise ValueError("Symlink snapshots are not valid analysis inputs")
    ordered_paths: list[tuple[int, str, Path, str]] = []
    seen_scan_ids: set[str] = set()
    compressed_bytes = 0
    for path in paths:
        snapshot, compressed = _read_snapshot(path)
        captured_ns = snapshot.get("captured_ns")
        scan_id = snapshot.get("scan_id")
        if not isinstance(captured_ns, int) or captured_ns <= 0 or not isinstance(scan_id, str):
            raise ValueError(f"Snapshot ordering metadata is invalid: {path.name}")
        if scan_id in seen_scan_ids:
            raise ValueError("Snapshot IDs must be unique")
        seen_scan_ids.add(scan_id)
        compressed_bytes += len(compressed)
        if compressed_bytes > MAX_TOTAL_COMPRESSED_BYTES:
            raise ValueError("Total compressed snapshot bytes exceed the analysis bound")
        ordered_paths.append((captured_ns, scan_id, path, _sha256(compressed)))
        del snapshot, compressed
    ordered_paths.sort(key=lambda row: (row[0], row[1]))

    all_profiles: dict[str, dict[str, Any]] = {}
    ever_eligible_profiles: dict[str, dict[str, Any]] = {}
    total_exclusion_incidence: Counter[str] = Counter()
    unique_reason_ids: dict[str, set[str]] = defaultdict(set)
    global_conditions: dict[str, set[str]] = defaultdict(set)
    global_assets: dict[str, set[str]] = defaultdict(set)
    per_scan_eligible_profiles: list[list[dict[str, Any]]] = []
    frame_results: list[dict[str, Any]] = []
    source_manifest: list[dict[str, Any]] = []
    response_manifest: list[dict[str, str]] = []
    observations_per_market: dict[str, list[tuple[int, str | None]]] = defaultdict(list)
    attempted: list[int] = []
    valid: list[int] = []
    invalid: list[int] = []
    unique_union_sizes: list[int] = []
    eligible_union_sizes: list[int] = []
    age_bands: dict[str, Counter[str]] = {"yes": Counter(), "no": Counter()}
    age_above_five_seconds: Counter[str] = Counter()
    skew_bands: Counter[str] = Counter()
    skew_above_250ms = 0
    invalid_reasons: Counter[str] = Counter()
    selected_by_phase: Counter[str] = Counter()
    selected_by_role: Counter[str] = Counter()
    selected_by_stratum: Counter[str] = Counter()
    selection_probability_values: list[float] = []
    selection_probability_basis: Counter[str] = Counter()
    response_attempts = 0
    source_code_hashes: Counter[str] = Counter()
    replay_code_hashes: Counter[str] = Counter()
    current_classifier_matches = 0
    capture_quality_valid_pairs = 0
    capture_replay_mismatch_scans: list[dict[str, Any]] = []
    latest_scan_profiles: list[dict[str, Any]] = []
    latest_scan_eligible_profiles: list[dict[str, Any]] = []
    selected_market_ids: set[str] = set()
    selected_condition_ids: set[str] = set()
    selected_asset_ids: set[str] = set()
    global_market_identity: dict[str, tuple[str | None, tuple[str, ...]]] = {}
    global_identity_conflict_ids: set[str] = set()
    captured_ns_values: list[int] = []
    scan_ids: list[str] = []
    latest_scan_counts: dict[str, int] = {}
    latest_scan_collection_bounds: dict[str, Any] = {}
    latest_selected_condition_ids: set[str] = set()
    latest_selected_assets: set[str] = set()
    latest_payoff_verified_assets: set[str] = set()
    positive_top_gross_pairs = 0
    total_candidate_events = 0

    for scan_index, (ordered_captured_ns, ordered_scan_id, path, expected_digest) in enumerate(
        ordered_paths
    ):
        snapshot, compressed = _read_snapshot(path)
        if _sha256(compressed) != expected_digest:
            raise ValueError(f"Snapshot changed during analysis: {path.name}")
        scan = _verify_snapshot(snapshot, path, compressed)
        if scan["captured_ns"] != ordered_captured_ns or scan["scan_id"] != ordered_scan_id:
            raise ValueError(f"Snapshot ordering metadata changed during analysis: {path.name}")
        del snapshot, compressed
        raw_by_id = scan["raw_by_id"]
        universe_by_id = scan["universe_by_id"]
        profiles: list[dict[str, Any]] = []
        eligible_profiles: list[dict[str, Any]] = []
        captured_ns_values.append(scan["captured_ns"])
        scan_ids.append(scan["scan_id"])
        frame_results.append(scan["frame_result"])
        unique_union_sizes.append(len(raw_by_id))
        eligible_count = int(scan["discovery"].get("eligible_pair_markets", 0))
        eligible_union_sizes.append(eligible_count)
        response_attempts += int(scan["source_http_attempts"])
        source_code_hashes[scan["source_code_sha256"]] += 1
        if scan["frame_result"]["eligible_ids"] == eligible_count:
            current_classifier_matches += 1

        for market_id, raw in raw_by_id.items():
            stored = universe_by_id[market_id]
            profile = _profile(raw, stored, scan["captured_ns"])
            profile["market_id"] = market_id
            profiles.append(profile)
            all_profiles[market_id] = profile
            reason = profile.get("exclusion_reason")
            if not profile["eligible"] and isinstance(reason, str):
                total_exclusion_incidence[reason] += 1
                unique_reason_ids[reason].add(market_id)
            if profile["eligible"]:
                eligible_profiles.append(profile)
                ever_eligible_profiles[market_id] = profile

            condition = raw.get("conditionId")
            condition_id = str(condition) if condition is not None else None
            outcomes = raw.get("clobTokenIds")
            if isinstance(outcomes, str):
                try:
                    outcomes = json.loads(outcomes)
                except json.JSONDecodeError:
                    outcomes = None
            assets = (
                tuple(sorted(str(value) for value in outcomes))
                if isinstance(outcomes, list)
                else ()
            )
            if condition_id:
                global_conditions[market_id].add(condition_id)
            global_assets[market_id].update(assets)
            identity = (condition_id, assets)
            prior_identity = global_market_identity.get(market_id)
            if prior_identity is not None and prior_identity != identity:
                global_identity_conflict_ids.add(market_id)
            else:
                global_market_identity[market_id] = identity

        per_scan_eligible_profiles.append(eligible_profiles)

        if scan_index == len(ordered_paths) - 1:
            latest_scan_profiles = profiles
            latest_scan_eligible_profiles = eligible_profiles
            latest_scan_counts = {
                "gamma_market_ids": len(raw_by_id),
                "eligible_market_ids": eligible_count,
                "excluded_market_ids": int(scan["discovery"].get("excluded_market_ids", 0)),
                "selected_market_ids": len(scan["selected"]),
            }
            latest_scan_collection_bounds = scan["collection_bounds"]
            latest_selected_condition_ids = {
                str(observation["condition"])
                for observation in scan["observations"]
                if observation.get("condition")
            }
            latest_selected_assets = {
                str(asset)
                for observation in scan["observations"]
                for asset in (
                    observation.get("outcomes", {}).values()
                    if isinstance(observation.get("outcomes"), dict)
                    else []
                )
                if asset
            }
            latest_payoff_verified_assets = {
                str(payoff[field])
                for observation in scan["observations"]
                for audit in [observation.get("audit")]
                if isinstance(audit, dict)
                for payoff in [audit.get("payoff_identity")]
                if isinstance(payoff, dict)
                for field in ("yes_asset_id", "no_asset_id")
                if payoff.get(field)
            }

        plan = scan["selection_plan"]
        selected_by_phase[str(plan.get("phase") or "unknown")] += len(scan["selected"])
        for selected in scan["selected"]:
            market_id = str(selected["market_id"])
            role = str(selected.get("cohort_role") or "unknown")
            stratum = str(selected.get("selection_stratum") or "unclassified")
            selected_by_role[role] += 1
            selected_by_stratum[stratum] += 1
            probability_basis = str(selected.get("selection_probability_basis") or "unknown")
            selection_probability_basis[probability_basis] += 1
            probability = _decimal(selected.get("selection_probability"))
            if probability is not None and probability <= 1:
                selection_probability_values.append(float(probability))
            selected_market_ids.add(market_id)

        for observation in scan["observations"]:
            market_id = str(observation["market_id"])
            audit = observation.get("audit")
            if not isinstance(audit, dict):
                continue
            quotes = {
                "best_bid_by_leg": audit.get("best_bid_by_leg"),
                "best_ask_by_leg": audit.get("best_ask_by_leg"),
            }
            fingerprint = None
            asks = quotes["best_ask_by_leg"]
            if (
                isinstance(asks, dict)
                and asks.get("yes") is not None
                and asks.get("no") is not None
                and all(isinstance(value, dict) for value in quotes.values())
            ):
                fingerprint = _sha256(_canonical(quotes))
            observations_per_market[market_id].append((scan["captured_ns"], fingerprint))

            condition = observation.get("condition")
            if condition is not None:
                condition_value = str(condition)
                selected_condition_ids.add(condition_value)
                assets = observation.get("outcomes")
                if isinstance(assets, dict):
                    for side in ("yes", "no"):
                        if assets.get(side):
                            selected_asset_ids.add(str(assets[side]))
                payoff = audit.get("payoff_identity")
                if isinstance(payoff, dict):
                    for field in ("yes_asset_id", "no_asset_id"):
                        if payoff.get(field):
                            selected_asset_ids.add(str(payoff[field]))
        summary = scan["observation_summary"]
        attempted_count = (
            int(summary.get("attempted_market_pairs", len(scan["observations"])))
            if isinstance(summary, dict)
            else len(scan["observations"])
        )
        valid_count = int(summary.get("valid_quality_pairs", 0)) if isinstance(summary, dict) else 0
        if not 0 <= valid_count <= attempted_count:
            raise ValueError(f"Invalid pair-quality counters in {scan['scan_id']}")
        attempted.append(attempted_count)
        valid.append(valid_count)
        invalid.append(attempted[-1] - valid[-1])
        capture_counts = scan["capture_counts"]
        capture_valid = (
            int(capture_counts.get("valid_quality_pairs", 0))
            if isinstance(capture_counts, dict)
            else 0
        )
        capture_quality_valid_pairs += capture_valid
        if capture_valid != valid_count:
            capture_replay_mismatch_scans.append(
                {
                    "scan_id": scan["scan_id"],
                    "capture_recorded_valid_pairs": capture_valid,
                    "current_replay_valid_pairs": valid_count,
                }
            )
        for field in ("analysis_source_code_sha256", "opportunity_audit_source_code_sha256"):
            code_hash = summary.get(field) if isinstance(summary, dict) else None
            if isinstance(code_hash, str):
                replay_code_hashes[code_hash] += 1

        replay_counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
        positive_top_gross_pairs += int(summary.get("positive_top_gross_pairs", 0))
        total_candidate_events += int(summary.get("gross_candidate_count", 0))
        reasons = (
            replay_counts.get("invalid_reasons", {}) if isinstance(replay_counts, dict) else {}
        )
        if isinstance(reasons, dict):
            for reason, count in reasons.items():
                if isinstance(count, int) and count >= 0:
                    invalid_reasons[str(reason)] += count
        if isinstance(replay_counts, dict):
            for side in ("yes", "no"):
                age_counts = replay_counts.get("reported_update_age_bands_by_leg", {}).get(side, {})
                if isinstance(age_counts, dict):
                    age_bands[side].update(
                        {str(band): int(count) for band, count in age_counts.items()}
                    )
                stale_count = replay_counts.get("reported_update_age_above_5s_by_leg", {}).get(
                    side, 0
                )
                if isinstance(stale_count, int):
                    age_above_five_seconds[side] += stale_count
            skew_counts = replay_counts.get("reported_update_timestamp_skew_bands", {})
            if isinstance(skew_counts, dict):
                skew_bands.update({str(band): int(count) for band, count in skew_counts.items()})
            skew_above_250ms += int(
                replay_counts.get("reported_update_timestamp_skew_above_250ms_pairs", 0)
            )

        for page in scan["discovery"].get("queries", []):
            response_manifest.append(
                {
                    "scan_id": scan["scan_id"],
                    "query_id": str(page["query_id"]),
                    "response_sha256": str(page["response_sha256"]),
                }
            )
        source_manifest.append(
            {
                "scan_id": scan["scan_id"],
                "captured_ns": scan["captured_ns"],
                "snapshot_evidence_sha256": scan["snapshot_evidence_sha256"],
                "compressed_snapshot_sha256": scan["compressed_snapshot_sha256"],
                "source_code_sha256": scan["source_code_sha256"],
            }
        )
        del raw_by_id, universe_by_id, profiles, eligible_profiles, scan

    comparisons = 0
    changed_comparisons = 0
    repeated_markets = 0
    for samples in observations_per_market.values():
        ordered = sorted(samples)
        comparable = [
            (captured_ns, fingerprint) for captured_ns, fingerprint in ordered if fingerprint
        ]
        if len(comparable) >= 2:
            repeated_markets += 1
            for (_, previous), (_, current) in zip(comparable, comparable[1:], strict=False):
                comparisons += 1
                changed_comparisons += previous != current

    intervals_seconds = [
        (later - earlier) / 1_000_000_000
        for earlier, later in zip(captured_ns_values, captured_ns_values[1:], strict=False)
    ]
    distinct_conditions = {
        condition for conditions in global_conditions.values() for condition in conditions
    }
    distinct_assets = {asset for assets in global_assets.values() for asset in assets}
    selected_market_condition_conflicts = sum(
        len(conditions) > 1 for conditions in global_conditions.values()
    )
    probabilities = sorted(selection_probability_values)
    probability_stats = {
        "count_numeric_conditional_probabilities": len(probabilities),
        "min": min(probabilities) if probabilities else None,
        "median": median(probabilities) if probabilities else None,
        "max": max(probabilities) if probabilities else None,
        "scope": "conditional on the bounded query-response union and frozen controls",
    }
    mean_valid_yield = round(sum(valid) / sum(attempted), 4) if sum(attempted) else None
    return {
        "schema_version": 1,
        "analysis_version": ANALYSIS_VERSION,
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "analysis_module_sha256": _sha256(Path(__file__).read_bytes()),
            "current_replay_source_code_hash_counts": dict(sorted(replay_code_hashes.items())),
            "snapshot_count": len(ordered_paths),
            "first_captured_ns": captured_ns_values[0],
            "last_captured_ns": captured_ns_values[-1],
            "first_scan_id": scan_ids[0],
            "last_scan_id": scan_ids[-1],
            "compressed_snapshot_bytes": compressed_bytes,
            "gamma_response_count": len(response_manifest),
            "gamma_response_manifest_sha256": _sha256(
                _canonical(
                    sorted(
                        response_manifest,
                        key=lambda row: (row["scan_id"], row["query_id"]),
                    )
                )
            ),
            "snapshot_manifest_sha256": _sha256(_canonical(source_manifest)),
            "source_code_hash_counts": dict(sorted(source_code_hashes.items())),
            "gamma_response_hashes_verified": True,
            "clob_response_hashes_verified": True,
            "snapshot_evidence_hashes_verified": True,
            "read_only_evidence": True,
            "snapshots": source_manifest,
        },
        "collection_protocol": {
            "coverage_kind": "intermittent_public_snapshots",
            "gamma_frames_per_scan": EXPECTED_GAMMA_FRAMES,
            "mean_query_candidate_records_per_scan": round(
                mean(row["candidate_records"] for row in frame_results), 2
            ),
            "mean_unique_market_ids_per_bounded_union": round(mean(unique_union_sizes), 2),
            "min_unique_market_ids_per_bounded_union": min(unique_union_sizes),
            "max_unique_market_ids_per_bounded_union": max(unique_union_sizes),
            "mean_v1_eligible_market_ids_per_bounded_union": round(mean(eligible_union_sizes), 2),
            "min_v1_eligible_market_ids_per_bounded_union": min(eligible_union_sizes),
            "max_v1_eligible_market_ids_per_bounded_union": max(eligible_union_sizes),
            "first_to_last_interval_seconds": _range(intervals_seconds),
            "mean_attempted_market_pairs_per_scan": round(mean(attempted), 2),
            "total_attempted_market_pairs": sum(attempted),
            "total_quality_valid_market_pairs": sum(valid),
            "capture_recorded_quality_valid_market_pairs": capture_quality_valid_pairs,
            "capture_vs_current_replay_valid_pair_delta": sum(valid) - capture_quality_valid_pairs,
            "scans_with_capture_vs_replay_count_mismatch": len(capture_replay_mismatch_scans),
            "capture_vs_replay_count_mismatches": capture_replay_mismatch_scans,
            "total_invalid_market_pairs": sum(invalid),
            "invalid_pair_reasons": dict(sorted(invalid_reasons.items())),
            "quality_valid_yield": mean_valid_yield,
            "positive_top_gross_pairs": positive_top_gross_pairs,
            "candidate_events": total_candidate_events,
            "http_attempts": response_attempts,
            "latest_collection_bounds": latest_scan_collection_bounds,
        },
        "identity_coverage": {
            "distinct_gamma_market_ids_over_window": len(all_profiles),
            "distinct_market_ids_eligible_at_least_once": len(ever_eligible_profiles),
            "distinct_condition_ids_over_window": len(distinct_conditions),
            "distinct_outcome_asset_ids_over_window": len(distinct_assets),
            "market_ids_with_multiple_condition_ids_over_time": selected_market_condition_conflicts,
            "market_ids_with_source_identity_conflicts": len(global_identity_conflict_ids),
            "latest_scan": {
                "scan_id": scan_ids[-1],
                **latest_scan_counts,
                "distinct_selected_condition_ids": len(latest_selected_condition_ids),
                "distinct_selected_outcome_asset_ids": len(latest_selected_assets),
                "distinct_payoff_verified_outcome_asset_ids": len(latest_payoff_verified_assets),
            },
            "selected_market_ids_over_window": len(selected_market_ids),
            "selected_condition_ids_over_window": len(selected_condition_ids),
            "selected_outcome_asset_ids_over_window": len(selected_asset_ids),
            "markets_are_counted_by_gamma_market_id; contracts_by_condition_id; outcomes_by_asset_id": True,
        },
        "metadata_coverage": {
            "latest_scan_bounded_union": _profile_summary(latest_scan_profiles),
            "latest_scan_v1_eligible_population": _profile_summary(latest_scan_eligible_profiles),
            "distinct_market_ids_seen_over_window_latest_metadata": _profile_summary(
                list(all_profiles.values())
            ),
            "distinct_market_ids_ever_eligible_latest_eligible_metadata": _profile_summary(
                list(ever_eligible_profiles.values())
            ),
            "eligible_market_scan_observations": _profile_summary(
                [profile for rows in per_scan_eligible_profiles for profile in rows]
            ),
            "excluded_market_scan_observations_by_reason": dict(
                sorted(total_exclusion_incidence.items())
            ),
            "distinct_market_ids_ever_excluded_by_reason": {
                key: len(value) for key, value in sorted(unique_reason_ids.items())
            },
        },
        "sampling": {
            "selection_probabilities": probability_stats,
            "selected_slots_by_phase": dict(sorted(selected_by_phase.items())),
            "selected_slots_by_cohort_role": dict(sorted(selected_by_role.items())),
            "selected_slots_by_selection_stratum": dict(sorted(selected_by_stratum.items())),
            "selection_probability_basis_counts": dict(sorted(selection_probability_basis.items())),
            "per_frame_marginal_value": summarize_frame_marginals(frame_results),
            "current_classifier_matches_stored_eligible_count_scans": current_classifier_matches,
            "classifier_replay_scan_count": len(ordered_paths),
        },
        "freshness_and_sampled_activity": {
            "reported_book_update_age_bands_by_leg": {
                side: dict(sorted(counts.items())) for side, counts in age_bands.items()
            },
            "reported_book_update_age_above_5s_by_leg": dict(
                sorted(age_above_five_seconds.items())
            ),
            "reported_cross_outcome_timestamp_skew_bands": dict(sorted(skew_bands.items())),
            "reported_cross_outcome_timestamp_skew_above_250ms_pairs": skew_above_250ms,
            "markets_with_at_least_one_repeated_comparable_sample": repeated_markets,
            "sampled_top_of_book_comparisons": comparisons,
            "sampled_top_of_book_changed_comparisons": changed_comparisons,
            "sampled_top_of_book_change_fraction": (
                round(changed_comparisons / comparisons, 4) if comparisons else None
            ),
            "interpretation": (
                "Sampled book changes between selected intermittent snapshots are an activity proxy, "
                "not venue update frequency or continuous per-market coverage."
            ),
        },
        "limitations": [
            "The six-page query union is bounded and selected by upstream filters; it is not the venue-wide universe.",
            "Selection probabilities apply only within each observed query union and conditional on frozen controls.",
            "Category, liquidity, expiry, and spread summaries describe observed metadata, not all venue markets.",
            "Markets, condition contracts, and outcome asset IDs are counted separately; a selected V1 pair normally has two assets.",
            "Reported update-age fields are source timestamp ages at snapshot time; sampled state changes are not an update-rate estimate.",
            "Snapshots are intermittent and cannot establish quote duration, continuous coverage, order arrival, or fills.",
            "V1 eligibility is limited to the supported same-condition binary payoff relationship; other structures remain excluded or unverified.",
        ],
        "orders_submitted": False,
        "authenticated_requests": False,
    }
