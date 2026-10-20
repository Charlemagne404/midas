"""Passive production observation; never launches work or controls a service."""

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def request(path):
    started = time.monotonic()
    try:
        with urllib.request.urlopen(path, timeout=10) as response:
            payload = response.read()
            return {
                "http": response.status,
                "seconds": time.monotonic() - started,
                "bytes": len(payload),
                "body": json.loads(payload),
            }
    except Exception as error:
        return {"seconds": time.monotonic() - started, "error": str(error)}


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as error:
        return {"read_error": str(error)}


def frozen_hashes():
    home = Path.home()
    paths = [
        home / "midas/data/autonomy/48H-001/manifest.json",
        home / "midas/data/autonomy/48H-001/STATUS.md",
    ]
    paths.extend((home / "midas-reality/data/research/reality/forward").glob("*/campaign.json"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=3600)
    args = parser.parse_args()
    if args.seconds < 0:
        parser.error("duration must be nonnegative")
    home = Path.home()
    recorder = home / "midas-reality/data/recordings/reality/status.json"
    veritas = home / "midas-veritas/data/veritas-gap-detail-v2/gap-detail-summary-v2.json"
    baseline = frozen_hashes()
    started = time.monotonic()
    with args.output.open("x") as stream:
        while True:
            status = read_json(recorder)
            summary = read_json(veritas)
            row = {
                "time": time.time(),
                "elapsed": time.monotonic() - started,
                "api": request("http://127.0.0.1:8000/api/health"),
                "interface_api": request("http://127.0.0.1:8010/api/health"),
                "recorder": {
                    k: status.get(k)
                    for k in (
                        "updated_ns",
                        "last_observation_ns",
                        "ordinal",
                        "frames",
                        "gaps",
                        "state",
                        "fresh_books",
                        "expected_books",
                        "timing_uncertain_books",
                        "sequence_verified",
                        "max_append_seconds",
                        "storage_bytes",
                        "read_error",
                    )
                },
                "veritas": {
                    k: summary.get(k)
                    for k in (
                        "status",
                        "generated_at_utc",
                        "processed_segment_count",
                        "pending_segment_count",
                        "last_processed_ordinal",
                        "read_error",
                    )
                },
            }
            for endpoint in ("state", "analytics"):
                result = request("http://127.0.0.1:8000/api/" + endpoint)
                body = result.pop("body", {})
                if endpoint == "state":
                    result["processing_latency_ms"] = body.get("processing_latency_ms")
                row[endpoint] = result
            row["frozen_hashes_unchanged"] = frozen_hashes() == baseline
            stream.write(json.dumps(row) + "\n")
            stream.flush()
            remaining = args.seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            time.sleep(min(60, remaining))


if __name__ == "__main__":
    main()
