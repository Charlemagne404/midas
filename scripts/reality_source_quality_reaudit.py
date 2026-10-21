#!/usr/bin/env python3
"""Recheck persisted Reality gap examples and REST bodies for a pinned cold audit.

This reads only finalized segments referenced by the cold receipt. It never
opens an active ``.open`` segment and writes one bounded receipt under the
independent staging root.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STAGING_ROOT = Path("/mnt/continental-cloud/data/midas-reality-staging").resolve()


def read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular non-symlink JSON file: {path}")
    return json.loads(path.read_text())


def source_tree_sha256(packages: Path) -> str:
    files = sorted((packages / "midas/reality").glob("*.py"))
    if not files:
        raise ValueError("Reality package source is empty")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def gap_observation(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload")
    if record.get("kind") != "gap" or not isinstance(payload, dict):
        raise ValueError("Pinned gap example does not resolve to a gap record")
    if "affected_assets" in payload:
        field = "affected_assets"
    elif "assets" in payload:
        field = "assets"
    else:
        field = None
    assets = payload.get(field) if field is not None else None
    result: dict[str, Any] = dict(
        ordinal=record.get("ordinal"),
        reason=payload.get("reason", "unknown"),
        assets_field=field,
    )
    if isinstance(assets, list):
        result["assets_count"] = len(assets)
        result["assets_sample"] = assets[:8]
    elif isinstance(assets, dict):
        result["assets_count"] = len(assets)
        result["assets_sample"] = list(assets)[:8]
        result["assets_issue_sample"] = [
            dict(
                asset_id=str(asset)[:256],
                issue=issue[:500]
                if isinstance(issue, str)
                else issue
                if issue is None or type(issue) in (int, float, bool)
                else type(issue).__name__,
            )
            for asset, issue in list(assets.items())[:8]
        ]
    elif field is not None:
        result["assets_value_type"] = type(assets).__name__
    return result


def segment_index_for_ordinal(segments: list[dict[str, Any]], ordinal: int) -> int:
    """Map a durable ordinal to its nonempty catalog segment.

    Empty finalized segments have first=last=0. Exclude them before bisecting,
    since their zero ``last`` values break the sorted-end invariant.
    """
    indexed = [
        (index, item)
        for index, item in enumerate(segments)
        if int(item.get("count", 0)) > 0
    ]
    ends = [int(item["last"]) for _, item in indexed]
    position = bisect.bisect_left(ends, ordinal)
    if position >= len(indexed):
        raise ValueError(f"Target ordinal is beyond the pinned boundary: {ordinal}")
    original_index, info = indexed[position]
    if not int(info["first"]) <= ordinal <= int(info["last"]):
        raise ValueError(f"Target durable ordinal is missing from the pinned boundary: {ordinal}")
    return original_index


def hash_segment_records(
    source: Path,
    info: dict[str, Any],
    targets: set[int],
) -> dict[int, dict[str, Any]]:
    """Verify a selected segment and return only its specifically requested rows."""
    from midas.reality.storage import _HashingReader, _record_stream

    name = info.get("file")
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".seg"):
        raise ValueError("Unsafe segment identity")
    path = source / name
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Pinned source segment is not a regular file: {name}")

    digest = hashlib.sha256()
    kinds: Counter[str] = Counter()
    matches: dict[int, dict[str, Any]] = {}
    first = last = count = 0
    with path.open("rb") as stream:
        for record, _ in _record_stream(_HashingReader(stream, digest), path):
            ordinal = record.get("ordinal")
            if type(ordinal) is not int or ordinal <= 0:
                raise ValueError(f"Invalid durable ordinal in {name}")
            if count and ordinal != last + 1:
                raise ValueError(f"Non-contiguous durable ordinals in {name}")
            first = first or ordinal
            last = ordinal
            count += 1
            kinds[record.get("kind", "unknown")] += 1
            if ordinal in targets:
                if ordinal in matches:
                    raise ValueError(f"Duplicate durable ordinal {ordinal}")
                matches[ordinal] = record

    actual = dict(
        schema_version=1,
        file=path.name,
        sha256=digest.hexdigest(),
        bytes=path.stat().st_size,
        first=first,
        last=last,
        count=count,
        kinds=dict(kinds),
    )
    if actual != info:
        raise ValueError(f"Selected source segment no longer matches its pinned manifest: {name}")
    return matches


def verify_independent_book_record(
    raw_record: dict[str, Any],
    related: list[dict[str, Any]],
    records_by_ordinal: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Rehash an independent REST body and verify its linked comparison records."""
    from midas.reality.quality import levels
    from midas.reality.storage import canonical

    raw_ordinal = raw_record.get("ordinal")
    if raw_record.get("kind") != "independent_book" or type(raw_ordinal) is not int:
        raise ValueError("REST body ordinal is not an independent_book record")
    raw_payload = raw_record.get("payload")
    body = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    if not isinstance(body, dict):
        raise ValueError(f"REST body at ordinal {raw_ordinal} is malformed")

    hashes: set[str] = set()
    comparison_ordinals = []
    for divergence in related:
        asset = divergence.get("asset_id")
        condition = divergence.get("condition")
        if body.get("asset_id") != asset or body.get("market") != condition:
            raise ValueError(f"REST body identity mismatch at ordinal {raw_ordinal}")
        normalized = {side: levels(body.get(side)) for side in ("bids", "asks")}
        computed = hashlib.sha256(canonical(normalized)).hexdigest()
        comparison_ordinal = int(divergence["record_ordinal"])
        comparison = records_by_ordinal[comparison_ordinal]
        comparison_payload = comparison.get("payload")
        if (
            comparison.get("kind") != "book_comparison"
            or not isinstance(comparison_payload, dict)
            or comparison_payload.get("raw_ordinal") != raw_ordinal
            or comparison_payload.get("asset_id") != asset
            or comparison_payload.get("condition") != condition
            or comparison_payload.get("independent_depth_sha256") != computed
            or divergence.get("independent_depth_sha256") != computed
        ):
            raise ValueError(f"REST depth hash or link mismatch at ordinal {raw_ordinal}")
        hashes.add(computed)
        comparison_ordinals.append(comparison_ordinal)

    if len(hashes) != 1:
        raise ValueError(f"Linked comparisons disagree on the REST body at ordinal {raw_ordinal}")
    return dict(
        raw_ordinal=raw_ordinal,
        comparison_ordinals=comparison_ordinals,
        comparison_count=len(comparison_ordinals),
        independent_depth_hash=next(iter(hashes)),
        body_and_comparison_hash_match=True,
    )


def audit(
    *,
    source: Path,
    packages: Path,
    catalog_path: Path,
    identities_path: Path,
    cold_path: Path,
    output: Path,
) -> dict[str, Any]:
    from midas.reality.storage import canonical

    if source.is_symlink():
        raise ValueError("Source root must not be a symbolic link")
    source = source.resolve(strict=True)
    packages = packages.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Source root must be a regular directory")
    if output.is_symlink() or output.exists():
        raise ValueError("Audit output must be a new, non-symlink file")
    output_parent = output.parent.resolve(strict=True)
    if not output_parent.is_relative_to(STAGING_ROOT) or output.parent.is_symlink():
        raise ValueError("Audit output must be under the independent staging root")

    catalog = read_json(catalog_path)
    identities = read_json(identities_path)
    cold = read_json(cold_path)
    quality = cold.get("source_quality_audit")
    if not isinstance(quality, dict):
        raise ValueError("Cold receipt has no source-quality audit")
    catalog_digest = hashlib.sha256(canonical(catalog)).hexdigest()
    identities_digest = hashlib.sha256(canonical(identities)).hexdigest()
    implementation_digest = source_tree_sha256(packages)
    if catalog_digest != cold.get("boundary_catalog_sha256"):
        raise ValueError("Catalog no longer matches the cold receipt boundary")
    if identities_digest != cold.get("boundary_identities_sha256"):
        raise ValueError("Source identities no longer match the cold receipt boundary")
    if implementation_digest != cold.get("implementation_source_sha256"):
        raise ValueError("Reality candidate packages differ from the cold receipt")
    segments = catalog.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("Pinned catalog has no segment list")
    divergences = quality.get("stable_lineage_divergences")
    if not isinstance(divergences, list):
        raise ValueError("Cold divergence audit is malformed")
    divergence_by_raw: dict[int, list[dict[str, Any]]] = defaultdict(list)
    divergence_by_record: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in divergences:
        raw_ordinal = item.get("raw_ordinal")
        record_ordinal = item.get("record_ordinal")
        if type(raw_ordinal) is not int or type(record_ordinal) is not int:
            raise ValueError("Divergence lacks durable source ordinals")
        divergence_by_raw[raw_ordinal].append(item)
        divergence_by_record[record_ordinal].append(item)

    gap_examples = [
        example
        for examples in quality.get("gap_examples", {}).values()
        for example in examples
    ]
    gap_by_ordinal = {
        int(item["ordinal"]): item for item in gap_examples if type(item.get("ordinal")) is int
    }
    target_ordinals = set(divergence_by_raw) | set(divergence_by_record) | set(gap_by_ordinal)
    selected: dict[int, int] = {}
    for ordinal in target_ordinals:
        index = segment_index_for_ordinal(segments, ordinal)
        selected[index] = index

    records_by_ordinal: dict[int, dict[str, Any]] = {}
    for index in sorted(selected):
        wanted = {n for n in target_ordinals if int(segments[index]["first"]) <= n <= int(segments[index]["last"])}
        records_by_ordinal.update(hash_segment_records(source, segments[index], wanted))
    if records_by_ordinal.keys() != target_ordinals:
        missing = sorted(target_ordinals - records_by_ordinal.keys())
        raise ValueError(f"Target durable records were not found: {missing[:8]}")

    body_receipts = []
    for raw_ordinal, related in sorted(divergence_by_raw.items()):
        raw_record = records_by_ordinal[raw_ordinal]
        body_receipts.append(
            verify_independent_book_record(raw_record, related, records_by_ordinal)
        )

    gap_receipts = []
    for ordinal, example in sorted(gap_by_ordinal.items()):
        actual = gap_observation(records_by_ordinal[ordinal])
        if actual["reason"] != example.get("reason"):
            raise ValueError(f"Gap reason mismatch at durable ordinal {ordinal}")
        gap_receipts.append(actual)

    result = dict(
        schema_version=1,
        created_at=datetime.now(UTC).isoformat(),
        source=str(source),
        source_read_policy="finalized selected segments opened read-only; no .open segment accessed",
        candidate_packages=str(packages),
        implementation_source_sha256=implementation_digest,
        boundary_catalog_sha256=catalog_digest,
        boundary_identities_sha256=identities_digest,
        cold_receipt=str(cold_path),
        verified_selected_segments=len(selected),
        selected_segment_bytes=sum(int(segments[i]["bytes"]) for i in selected),
        selected_target_records=len(target_ordinals),
        stable_lineage_divergence_records=len(divergences),
        independent_rest_bodies_rehashed=len(body_receipts),
        all_independent_rest_hashes_match=True,
        rest_bodies=body_receipts,
        corrected_gap_examples=gap_receipts,
        gap_reason_counts=quality.get("gap_reasons", {}),
        limitation=(
            "Matching persisted REST bodies revalidate their recorded hashes. A cross-interface depth "
            "mismatch still cannot establish which upstream view was complete without a provider sequence "
            "or atomic snapshot contract."
        ),
    )
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if len(encoded) > 8 * 1024**2:
        raise ValueError("Re-audit receipt exceeds its 8 MiB bound")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=".source-quality-reaudit.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(encoded + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        if output.exists() or output.is_symlink():
            raise ValueError("Audit output appeared while the receipt was being written")
        os.replace(temporary, output)
        temporary = None
        directory_fd = os.open(output.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--identities", type=Path, required=True)
    parser.add_argument("--cold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import sys

    sys.path.insert(0, str(args.packages.resolve(strict=True)))
    result = audit(
        source=args.source,
        packages=args.packages,
        catalog_path=args.catalog,
        identities_path=args.identities,
        cold_path=args.cold,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "verified_selected_segments": result["verified_selected_segments"],
                "selected_segment_bytes": result["selected_segment_bytes"],
                "independent_rest_bodies_rehashed": result["independent_rest_bodies_rehashed"],
                "gap_examples": len(result["corrected_gap_examples"]),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
