"""Capture one bounded, read-only direct Gamma lookup for frozen controls."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from midas.veritas.control_retrieval import retrieve_control_metadata
from midas.veritas.observatory import PublicReadClient


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _atomic_gzip_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.is_symlink() or path.exists() or path.is_symlink():
        raise ValueError("Evidence output must be a new file in a non-symlink directory")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
                compressed.write(_canonical(record))
            raw.flush()
            os.fsync(raw.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


async def _run(control_file: Path, output_file: Path) -> dict[str, Any]:
    if control_file.is_symlink() or not control_file.is_file():
        raise ValueError("Control cohort must be a regular, non-symlink file")
    source_bytes = control_file.read_bytes()
    source = json.loads(source_bytes)
    if source.get("version") not in {
        "veritas-control-cohort-v1",
        "veritas-public-observatory-v1",
    } or not isinstance(source.get("market_ids"), list):
        raise ValueError("Unsupported frozen control cohort record")

    client = PublicReadClient(min_interval_seconds=1.0, max_requests=1)
    try:
        record = await retrieve_control_metadata(client, source["market_ids"])
        record["captured_at_ns"] = time.time_ns()
        record["evidence"] = {
            "control_cohort_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "control_cohort_market_count": len(source["market_ids"]),
            "public_request_count": client.requests,
            "http_attempt_count": client.request_attempts,
            "source": "Gamma public GET /markets by explicit market IDs",
            "raw_source_response_retained": True,
        }
        _atomic_gzip_json(output_file, record)
        return record
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--control-file",
        type=Path,
        default=Path("data/veritas-observatory/control-cohort.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="New gzip JSON evidence path; defaults to the ignored probe directory",
    )
    args = parser.parse_args()
    output_path = (
        args.output
        or Path("data/veritas-observatory/control-retrieval-probes")
        / f"control-retrieval-{time.time_ns()}.json.gz"
    )
    result = asyncio.run(_run(args.control_file, output_path))
    response = result["response"]
    print(
        json.dumps(
            {
                "version": result["version"],
                "captured_at_ns": result["captured_at_ns"],
                "evidence_path": str(output_path),
                "response_sha256": response["request_receipt"]["response_sha256"],
                "returned_market_count": response["returned_market_count"],
                "outcomes": response["outcomes"],
                "public_request_count": result["evidence"]["public_request_count"],
                "http_attempt_count": result["evidence"]["http_attempt_count"],
                "orders_submitted": False,
                "authenticated_requests": False,
            },
            sort_keys=True,
        )
    )
