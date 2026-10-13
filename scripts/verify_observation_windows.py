"""Recompute frozen public windows and independently check receipt-time partitions."""

import argparse
import json
from pathlib import Path

from midas.arena.artifacts import artifact_path, sha256
from midas.arena.observations import ObservationSpec, load, windows
from midas.laboratory.datasets import Manifest, read_events


def verify(root: Path, identity: str) -> dict:
    record, rows = load(root, identity)
    directory = artifact_path(root, "observations", identity)
    manifest = Manifest.model_validate_json((directory / "source-manifest.json").read_text())
    events = read_events(directory / "source.jsonl")
    spec = ObservationSpec.model_validate(record["configuration"])
    rebuilt, quality = windows(events, manifest.instrument_ids, spec)
    if rows != rebuilt or quality != record["quality"]:
        raise ValueError("Frozen windows or quality differ from original recording")
    by_id = {e.event_id: e for e in events}
    partitions = {p: [] for p in ("train", "validation", "test")}
    for row in rows:
        inputs = [by_id[name] for name in row["event_ids"]]
        receipts = [e.received_ts_ms for e in inputs]
        if len(inputs) != 2 or len({e.asset_id for e in inputs}) != 2:
            raise ValueError("Paired instruments are missing or split")
        if row["first_received_ms"] != min(receipts) or row["available_at_ms"] != max(receipts):
            raise ValueError("Availability is not the latest actual receipt")
        if by_id[row["metadata_event_id"]].received_ts_ms > min(receipts):
            raise ValueError("Metadata was not available at window time")
        if any(e.exchange_ts_ms is None or e.exchange_ts_ms > e.received_ts_ms for e in inputs):
            raise ValueError("Window includes future or absent exchange timestamps")
        if row["partition"] in partitions:
            partitions[row["partition"]].append(row)
    for first, second in (("train", "validation"), ("validation", "test")):
        last = max(r["available_at_ms"] for r in partitions[first])
        earliest = min(r["first_received_ms"] for r in partitions[second])
        if earliest <= last + spec.embargo_ms:
            raise ValueError("Chronological embargo is not preserved")
    return {
        "observation_id": identity,
        "source_content_sha256": record["source_content_sha256"],
        "rows_sha256": record["rows_sha256"],
        "windows_verified": len(rows),
        "quality": quality,
        "execution_labels": 0,
        "producer_sha256": sha256(Path(__file__)),
        "scope": "Source/row hashes, full builder recomputation and separate receipt/metadata/embargo checks; no empirical executions or model training.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.root, args.identity)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
