"""Reconcile historical Reality book-comparison records with their persisted REST bodies.

This is a read-only, targeted audit. It verifies only the finalized segments that
contain the saved comparison, its raw independent-book body, or its response-time
local lineage frame; every selected segment is checked against the pinned catalog.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

FORMAT = "midas-reality-framed-zlib-v1"


def _json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or unsafe audit input: {path}")
    return json.loads(path.read_text())


def _event_assets(event: Any) -> set[str]:
    if not isinstance(event, dict):
        return set()
    assets = {event["asset_id"]} if isinstance(event.get("asset_id"), str) else set()
    changes = event.get("price_changes")
    if isinstance(changes, list):
        assets.update(
            item["asset_id"]
            for item in changes
            if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
        )
    return assets


def reconcile_divergence(
    audit_case: dict[str, Any],
    comparison_record: dict[str, Any],
    independent_record: dict[str, Any],
    response_frame: dict[str, Any],
) -> dict[str, Any]:
    """Verify one saved comparison against its linked body and response lineage."""
    from midas.reality.quality import levels
    from midas.reality.storage import canonical

    comparison = comparison_record.get("payload")
    if (
        comparison_record.get("kind") != "book_comparison"
        or comparison_record.get("ordinal") != audit_case.get("record_ordinal")
        or not isinstance(comparison, dict)
        or comparison.get("assessment") != "stable_local_lineage_divergence"
    ):
        raise ValueError("Pinned comparison record does not match its audit case")

    raw_ordinal = comparison.get("raw_ordinal")
    if (
        independent_record.get("kind") != "independent_book"
        or independent_record.get("ordinal") != raw_ordinal
        or raw_ordinal != audit_case.get("raw_ordinal")
        or not isinstance(independent_record.get("payload"), str)
    ):
        raise ValueError("Independent book record does not match the saved raw ordinal")

    body = json.loads(independent_record["payload"])
    asset = comparison.get("asset_id")
    condition = comparison.get("condition")
    response_ns = comparison.get("response_ns")
    if not isinstance(body, dict):
        raise ValueError("Persisted independent-book body is not an object")
    body_depth = {side: levels(body.get(side)) for side in ("bids", "asks")}
    body_depth_sha256 = hashlib.sha256(canonical(body_depth)).hexdigest()
    body_timestamp_ms = int(body["timestamp"])
    body_link_valid = (
        body.get("asset_id") == asset
        and body.get("market") == condition
        and body_timestamp_ms == comparison.get("source_timestamp_ms")
        and body.get("hash") == comparison.get("source_native_hash")
        and independent_record.get("asset") == asset
        and independent_record.get("received_ns") == response_ns
    )

    lineage = comparison.get("after_lineage")
    if (
        not isinstance(lineage, list)
        or len(lineage) != 2
        or type(lineage[0]) is not int
        or type(lineage[1]) is not int
        or lineage[0] < 0
        or lineage[1] < 0
        or comparison.get("before_lineage") != lineage
        or response_frame.get("ordinal") != lineage[0]
        or response_frame.get("kind") != "frame"
    ):
        raise ValueError("Comparison does not identify a stable response-time frame lineage")
    frame_payload = response_frame.get("payload")
    if not isinstance(frame_payload, str):
        raise ValueError("Response-time lineage frame does not contain a text payload")
    frame_events = json.loads(frame_payload)
    frame_events = frame_events if isinstance(frame_events, list) else [frame_events]
    frame_index = lineage[1]
    if frame_index >= len(frame_events) or asset not in _event_assets(frame_events[frame_index]):
        raise ValueError("Response-time frame lineage does not contain the comparison asset")
    response_frame_event = frame_events[frame_index]
    raw_local_timestamp = response_frame_event.get("timestamp")
    local_source_timestamp_ms = None
    if type(raw_local_timestamp) is int and raw_local_timestamp >= 0:
        local_source_timestamp_ms = raw_local_timestamp
    elif (
        isinstance(raw_local_timestamp, str)
        and 0 < len(raw_local_timestamp) <= 32
        and raw_local_timestamp.isdecimal()
    ):
        local_source_timestamp_ms = int(raw_local_timestamp)
    frame_received_ns = response_frame.get("received_ns")
    if not isinstance(frame_received_ns, int) or not isinstance(response_ns, int):
        raise ValueError("Comparison or local frame lacks receive-time provenance")
    if frame_received_ns > response_ns:
        raise ValueError("Response-time local lineage frame was received after the REST response")

    local_hash = comparison.get("local_depth_sha256")
    external_hash = comparison.get("independent_depth_sha256")
    prior_replay_lineage = audit_case.get(
        "replay_lineage_at_durable_record", audit_case.get("local_lineage")
    )
    replay_lineage_unchanged = prior_replay_lineage == lineage and (
        audit_case.get("replay_state_advanced_after_response") is False
        or audit_case.get("local_lineage_agrees_with_after") is True
    )
    local_hash_source = "comparison_record" if isinstance(local_hash, str) else None
    if not isinstance(local_hash, str) and replay_lineage_unchanged:
        replay_hash = audit_case.get("local_depth_sha256")
        if isinstance(replay_hash, str) and len(replay_hash) == 64:
            # At an unchanged lineage, the durable replay state is also the
            # response-time local state, even when the historical comparison
            # payload predates persistence of this digest.
            local_hash = replay_hash
            local_hash_source = "full_replay_unchanged_response_lineage"
    if not body_link_valid or body_depth_sha256 != external_hash:
        classification = "INDEPENDENT_BODY_LINK_OR_HASH_UNVERIFIED"
    elif not isinstance(local_hash, str) or len(local_hash) != 64:
        classification = "RESPONSE_TIME_DEPTH_HASH_UNAVAILABLE"
    elif local_hash == body_depth_sha256:
        classification = "RECORDED_DIVERGENCE_NOT_REPRODUCED_AT_RESPONSE"
    else:
        classification = "STABLE_RESPONSE_TIME_DEPTH_MISMATCH_DIRECTION_UNKNOWN"

    return dict(
        record_ordinal=comparison_record["ordinal"],
        raw_ordinal=raw_ordinal,
        response_lineage=lineage,
        response_local_frame_verified=True,
        response_local_frame_received_ns=frame_received_ns,
        response_to_local_frame_age_ns=response_ns - frame_received_ns,
        independent_body_link_valid=body_link_valid,
        independent_body_verified=(body_link_valid and body_depth_sha256 == external_hash),
        independent_body_depth_sha256=body_depth_sha256,
        independent_level_counts={side: len(body_depth[side]) for side in ("bids", "asks")},
        independent_body_matches_recorded_depth_hash=(body_depth_sha256 == external_hash),
        recorded_response_local_depth_sha256=local_hash,
        recorded_independent_depth_sha256=external_hash,
        response_local_hash_matches_body=(local_hash == body_depth_sha256),
        prior_audit_local_hash=audit_case.get("local_depth_sha256"),
        prior_audit_hash_matches_response_hash=(audit_case.get("local_depth_sha256") == local_hash),
        response_local_level_counts=audit_case.get("local_level_counts"),
        response_local_depth_hash_source=local_hash_source,
        source_timestamp_comparison=dict(
            websocket_frame_timestamp_ms=local_source_timestamp_ms,
            rest_book_timestamp_ms=body_timestamp_ms,
            websocket_minus_rest_ms=(
                local_source_timestamp_ms - body_timestamp_ms
                if local_source_timestamp_ms is not None
                else None
            ),
            limitation=(
                "Descriptive source timestamps only; no shared sequence or atomic snapshot "
                "guarantee is documented."
            ),
        ),
        prior_audit_replay_lineage_at_durable_record=prior_replay_lineage,
        prior_replay_state_advanced_after_response=(
            prior_replay_lineage != comparison.get("after_lineage")
            if prior_replay_lineage is not None
            else None
        ),
        body_timestamp_ms=body_timestamp_ms,
        response_ns=response_ns,
        classification=classification,
        interpretation=(
            "A stable local-versus-REST depth mismatch establishes unequal observed views at the "
            "response lineage; without a provider sequence or atomic cross-interface snapshot, "
            "it does not identify which view was incomplete."
        ),
    )


def _write_new(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def reconcile_archive(source: Path, validation_root: Path, output: Path) -> dict[str, Any]:
    """Verify all saved stable-lineage divergences at their pinned archive boundary."""
    from midas.reality.storage import _read_manifest_for_replay

    from scripts.reality_full_scale_validation import validate_staged_output

    source = source.resolve(strict=True)
    validation_root = validation_root.resolve(strict=True)
    output = output.resolve()
    if not output.is_relative_to(validation_root) or output.is_relative_to(source):
        raise ValueError("Write the reconciliation receipt inside the isolated validation root")
    catalog, identities, boundary, _ = validate_staged_output(source, validation_root)
    cold = _json(validation_root / "cold.json")
    if (
        cold.get("phase") != "cold"
        or cold.get("boundary_catalog_sha256") != boundary["catalog_sha256"]
        or cold.get("boundary_identities_sha256") != boundary["identities_sha256"]
        or cold.get("ordinal") != boundary["last_ordinal"]
    ):
        raise ValueError("Cold receipt is not bound to the pinned archive boundary")
    quality = cold.get("source_quality_audit")
    cases = quality.get("stable_lineage_divergences") if isinstance(quality, dict) else None
    if not isinstance(cases, list):
        raise ValueError("Cold receipt lacks the stable-lineage audit cases")

    nonempty = [item for item in catalog["segments"] if item["count"]]
    ends = [item["last"] for item in nonempty]

    def segment_for(ordinal: int) -> dict[str, Any]:
        index = bisect.bisect_left(ends, ordinal)
        if index == len(nonempty):
            raise ValueError(f"Ordinal lies beyond the pinned boundary: {ordinal}")
        item = nonempty[index]
        if not item["first"] <= ordinal <= item["last"]:
            raise ValueError(f"Ordinal does not lie in a pinned segment: {ordinal}")
        return item

    needed_by_case: list[tuple[dict[str, Any], int, int, int]] = []
    selected: dict[str, dict[str, Any]] = {}
    for case in cases:
        comparison_ordinal = case.get("record_ordinal")
        raw_ordinal = case.get("raw_ordinal")
        lineage = case.get("after_lineage")
        if (
            type(comparison_ordinal) is not int
            or type(raw_ordinal) is not int
            or not isinstance(lineage, list)
            or len(lineage) != 2
            or type(lineage[0]) is not int
            or type(lineage[1]) is not int
            or lineage[0] < 0
            or lineage[1] < 0
        ):
            raise ValueError("Cold receipt has an incomplete stable-lineage case")
        frame_ordinal = lineage[0]
        needed_by_case.append((case, comparison_ordinal, raw_ordinal, frame_ordinal))
        for ordinal in (comparison_ordinal, raw_ordinal, frame_ordinal):
            info = segment_for(ordinal)
            selected[info["file"]] = info

    view = validation_root / "view"
    ordinals = {
        ordinal
        for _, comparison, raw, frame in needed_by_case
        for ordinal in (comparison, raw, frame)
    }
    records: dict[int, dict[str, Any]] = {}
    for info in selected.values():
        source_link = view / info["file"]
        if (
            not source_link.is_symlink()
            or source_link.resolve(strict=True) != source / info["file"]
        ):
            raise ValueError(f"Pinned source-view link changed: {info['file']}")
        sidecar = _json(view / Path(info["file"]).with_suffix(".json"))
        if sidecar != info:
            raise ValueError(f"Pinned segment sidecar changed: {info['file']}")
        manifest = {"schema_version": 1, "format": FORMAT, "segments": [info]}
        for record in _read_manifest_for_replay(view, manifest, previous=info["first"] - 1):
            if record["ordinal"] in ordinals:
                records[record["ordinal"]] = record
    if ordinals != records.keys():
        raise ValueError("One or more targeted source records were not found")

    reconciled = [
        reconcile_divergence(case, records[comparison], records[raw], records[frame])
        for case, comparison, raw, frame in needed_by_case
    ]
    totals: dict[str, int] = {}
    for item in reconciled:
        classification = item["classification"]
        totals[classification] = totals.get(classification, 0) + 1
    document = dict(
        schema_version=1,
        source=str(source),
        source_modified=False,
        validation_root=str(validation_root),
        implementation_packages=boundary["implementation_packages"],
        implementation_source_sha256=boundary["implementation_source_sha256"],
        recovery_implementation_sha256=boundary["recovery_implementation_sha256"],
        boundary_catalog_sha256=boundary["catalog_sha256"],
        boundary_identities_sha256=boundary["identities_sha256"],
        boundary_segment_count=boundary["segment_count"],
        boundary_ordinal=boundary["last_ordinal"],
        boundary_archive_bytes=boundary["archive_bytes"],
        divergence_cases=len(reconciled),
        verification_complete=all(
            item["independent_body_verified"] and item["response_local_frame_verified"]
            for item in reconciled
        ),
        verified_segment_count=len(selected),
        verified_segment_files=sorted(selected),
        classifications=totals,
        cases=reconciled,
        sequence_limitation=(
            "The documented source schema does not expose a monotonic event sequence; this audit "
            "verifies persisted evidence and does not prove provider-side event completeness."
        ),
    )
    _write_new(output, document)
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = reconcile_archive(args.source, args.validation_root, args.output)
    print(
        json.dumps(
            {
                "divergence_cases": document["divergence_cases"],
                "verified_segment_count": document["verified_segment_count"],
                "classifications": document["classifications"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
