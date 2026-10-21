#!/usr/bin/env python3
"""Pin a current finalized prefix and stage it read-only for candidate startup."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

MAX_STAGED_OUTPUT_BYTES = 256 * 1024**2
MIN_FREE_BYTES = 1024**3


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load validation module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_staged_sidecar(path: Path, content: bytes) -> None:
    """Atomically publish one rebuildable staging copy without per-file fsync."""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(content)
        stream.flush()
    os.replace(temporary, path)


def raw_fingerprint(identities: list[dict]) -> str:
    digest = hashlib.sha256()
    for item in identities:
        digest.update(
            f"{item['file']}\0{item['device']}\0{item['inode']}\0{item['size']}\0"
            f"{item['mtime_ns']}\0{item['sidecar_sha256']}\n".encode()
        )
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    args = parser.parse_args()

    repository = args.repository.resolve(strict=True)
    packages = args.packages.resolve(strict=True)
    source = args.source.resolve(strict=True)
    baseline = args.baseline.resolve(strict=True)
    candidate_root = args.candidate_root.absolute()
    staging_root = args.staging_root.absolute()
    if not candidate_root.is_relative_to(repository / "data/recordings"):
        raise ValueError("Candidate view must be under the isolated candidate recordings root")
    if candidate_root.exists() or candidate_root.is_symlink():
        raise ValueError("Candidate view path already exists")
    if staging_root.exists() or staging_root.is_symlink():
        raise ValueError("Staging receipt path already exists")
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Raw source root is missing or unsafe")

    sys.path.insert(0, str(packages))
    from midas.reality import recovery
    from midas.reality.storage import canonical

    validation = load_module(
        Path("/home/charlie/midas/scripts/reality_full_scale_validation.py"),
        "midas_current_suffix_inventory",
    )
    if validation.REALITY_PACKAGES_DIRECTORY != packages:
        raise ValueError("Inventory selected an unexpected Reality package tree")

    baseline_result = json.loads((baseline / "result.json").read_text())
    baseline_cold = json.loads((baseline / "cold.json").read_text())
    baseline_catalog = json.loads((baseline / "catalog.json").read_text())
    baseline_identities = json.loads((baseline / "identities.json").read_text())
    if baseline_result.get("recovery_matrix") != "PASSED":
        raise ValueError("Baseline full-store recovery matrix is not passed")
    if len(baseline_catalog.get("segments", [])) != baseline_result["boundary"]["segment_count"]:
        raise ValueError("Baseline full-store catalog count differs from its matrix boundary")

    catalog, identities, inventory = validation.inventory(source)
    segments = catalog["segments"]
    prior_segments = baseline_catalog["segments"]
    if segments[: len(prior_segments)] != prior_segments:
        raise ValueError("Current finalized catalog no longer preserves the verified R10 prefix")
    if identities[: len(baseline_identities)] != baseline_identities:
        raise ValueError("Current finalized file identities no longer preserve the R10 prefix")
    if inventory.get("unmatched_finalized"):
        raise ValueError("Current inventory contains an unpaired finalized segment")
    suffix = segments[len(prior_segments) :]
    suffix_bytes = sum(item["bytes"] for item in suffix)
    catalog_sha256 = hashlib.sha256(canonical(catalog)).hexdigest()
    identities_sha256 = hashlib.sha256(canonical(identities)).hexdigest()
    baseline_checkpoint = baseline / "valid.checkpoint"
    checkpoint_sha256 = hashlib.sha256(baseline_checkpoint.read_bytes()).hexdigest()
    if checkpoint_sha256 != baseline_cold["recovery"]["checkpoint_sha256"]:
        raise ValueError("R10 checkpoint differs from its cold-recovery receipt")

    sidecar_bytes = sum(
        (source / Path(info["file"]).with_suffix(".json")).stat().st_size
        for info in segments
    )
    checkpoint_bytes = baseline_checkpoint.stat().st_size
    estimated_output_bytes = (
        sidecar_bytes
        + checkpoint_bytes
        + len(canonical(catalog))
        + len(canonical(identities))
        + 16 * 1024**2
    )
    if estimated_output_bytes > MAX_STAGED_OUTPUT_BYTES:
        raise ValueError(
            f"Estimated candidate staging output exceeds {MAX_STAGED_OUTPUT_BYTES} bytes"
        )
    if shutil.disk_usage(candidate_root.parent).free < MIN_FREE_BYTES + estimated_output_bytes:
        raise ValueError("Candidate NVMe staging would cross its 1 GiB free-space reserve")

    candidate_root.mkdir(parents=True, mode=0o700)
    staging_root.mkdir(parents=True, mode=0o700)
    for info, identity in zip(segments, identities, strict=True):
        name = info["file"]
        raw_segment = source / name
        if raw_segment.is_symlink() or not raw_segment.is_file():
            raise ValueError(f"Raw finalized segment is missing or linked: {name}")
        if raw_segment.stat().st_size != identity["size"]:
            raise ValueError(f"Raw finalized segment size changed: {name}")
        os.symlink(raw_segment, candidate_root / name)
        sidecar = source / Path(name).with_suffix(".json")
        target_sidecar = candidate_root / sidecar.name
        with sidecar.open("rb") as stream:
            raw_sidecar = stream.read()
            if hashlib.sha256(raw_sidecar).hexdigest() != identity["sidecar_sha256"]:
                raise ValueError(f"Raw finalized sidecar changed while staging: {name}")
            write_staged_sidecar(target_sidecar, raw_sidecar)

    checkpoint_target = candidate_root / recovery.CHECKPOINT_NAME
    shutil.copyfile(baseline_checkpoint, checkpoint_target)
    if hashlib.sha256(checkpoint_target.read_bytes()).hexdigest() != checkpoint_sha256:
        raise ValueError("Staged checkpoint hash changed")
    sync_directory(candidate_root)

    catalog_path = staging_root / "current-catalog.json"
    identities_path = staging_root / "current-identities.json"
    boundary_path = staging_root / "current-boundary.json"
    write_json(catalog_path, catalog)
    write_json(identities_path, identities)
    boundary = {
        "captured_ns": time.time_ns(),
        "implementation_source_sha256": validation.IMPLEMENTATION_SOURCE_SHA256,
        "boundary_catalog_sha256": catalog_sha256,
        "boundary_identities_sha256": identities_sha256,
        "segment_count": len(segments),
        "last_ordinal": inventory["last_ordinal"],
        "archive_bytes": inventory["archive_bytes"],
        "state_sha256": None,
        "recovery": {"checkpoint_sha256": checkpoint_sha256},
        "verified_r10_prefix": {
            "evidence_sha256": hashlib.sha256((baseline / "result.json").read_bytes()).hexdigest(),
            "catalog_sha256": baseline_result["boundary"]["catalog_sha256"],
            "identities_sha256": baseline_result["boundary"]["identities_sha256"],
            "segment_count": len(prior_segments),
            "last_ordinal": baseline_result["boundary"]["last_ordinal"],
            "archive_bytes": baseline_result["boundary"]["archive_bytes"],
            "state_sha256": baseline_cold["state_sha256"],
            "checkpoint_sha256": checkpoint_sha256,
            "suffix_segment_count": len(suffix),
            "suffix_bytes": suffix_bytes,
        },
        "source_inventory": inventory,
        "source_link_fingerprint": raw_fingerprint(identities),
        "candidate_root": str(candidate_root),
        "raw_source_root": str(source),
    }
    write_json(boundary_path, boundary)

    catalog_after, identities_after, inventory_after = validation.inventory(source)
    if (
        catalog_after["segments"][: len(segments)] != segments
        or identities_after[: len(identities)] != identities
    ):
        raise ValueError("Raw source changed inside the pinned current-boundary prefix")
    unexpected = {entry.name for entry in candidate_root.iterdir()} - {
        name
        for info in segments
        for name in (info["file"], Path(info["file"]).with_suffix(".json").name)
    } - {recovery.CHECKPOINT_NAME}
    if unexpected:
        raise ValueError("Candidate view has unexpected files: " + ", ".join(sorted(unexpected)[:10]))
    print(json.dumps({
        "status": "STAGED",
        "source_segments": len(segments),
        "source_bytes": inventory["archive_bytes"],
        "last_ordinal": inventory["last_ordinal"],
        "r10_verified_prefix_segments": len(prior_segments),
        "r10_verified_prefix_bytes": baseline_result["boundary"]["archive_bytes"],
        "appended_suffix_segments": len(suffix),
        "appended_suffix_bytes": suffix_bytes,
        "staged_sidecar_bytes": sidecar_bytes,
        "estimated_output_bytes": estimated_output_bytes,
        "catalog_sha256": catalog_sha256,
        "identities_sha256": identities_sha256,
        "source_link_fingerprint": boundary["source_link_fingerprint"],
        "source_inventory_after": inventory_after,
        "candidate_root": str(candidate_root),
        "staging_root": str(staging_root),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
