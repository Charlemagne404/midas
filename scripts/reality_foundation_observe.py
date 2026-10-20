"""Passive operational receipt. Does not trace or signal any production process."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from midas.reality.resources import snapshot


def unit(name):
    result = subprocess.check_output(
        [
            "systemctl",
            "--user",
            "show",
            name,
            "-p",
            "MainPID",
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "NRestarts",
            "-p",
            "ControlGroup",
            "-p",
            "ActiveEnterTimestamp",
            "-p",
            "UnitFileState",
        ],
        text=True,
    )
    return dict(line.split("=", 1) for line in result.splitlines())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    production = Path.home() / "midas-reality"
    main = Path.home() / "midas"
    out = dict(
        captured_at=datetime.now(UTC).isoformat(),
        services={},
        samples=[],
        protected_sha256={},
        api={},
    )
    for name in (
        "midas-api",
        "midas-reality",
        "midas-reality-shadow",
        "midas-reality-shadow-successor",
        "midas-autonomy-48h-001.timer",
        "midas-veritas-gap-detail-v2.timer",
    ):
        out["services"][name] = unit(name if "." in name else name + ".service")
    recorder = out["services"]["midas-reality"]
    pid = recorder["MainPID"]
    for index in range(6):
        out["samples"].append(
            dict(
                at=datetime.now(UTC).isoformat(),
                resources=snapshot(recorder["ControlGroup"]),
                smaps_rollup=Path(f"/proc/{pid}/smaps_rollup").read_text(),
                process_io=Path(f"/proc/{pid}/io").read_text(),
                recorder_status=json.loads(
                    (production / "data/recordings/reality/status.json").read_text()
                ),
            )
        )
        if index < 5:
            time.sleep(10)
    for path in [
        main / "data/autonomy/48H-001/campaign.json",
        main / "data/autonomy/48H-001/manifest.json",
        main / "data/autonomy/48H-001/STATUS.md",
        *[
            production / f"data/research/reality/forward/{name}/{file}"
            for name in ("mission2", "mission2-successor-20261016")
            for file in ("campaign.json", "status.json")
        ],
    ]:
        if path.is_file():
            out["protected_sha256"][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for endpoint in ("health", "reality/overview", "arena/research-activity"):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:8000/api/{endpoint}", timeout=5
            ) as response:
                out["api"][endpoint] = json.load(response)
        except Exception as error:
            out["api"][endpoint] = dict(error=str(error))
    summary = Path.home() / "midas-veritas/data/veritas-gap-detail-v2/gap-detail-summary-v2.json"
    out["veritas_v2_summary"] = json.loads(summary.read_text())
    out["veritas_v2_summary_sha256"] = hashlib.sha256(summary.read_bytes()).hexdigest()
    out["repositories"] = {}
    for path in (
        main,
        production,
        Path.home() / "midas-veritas",
        Path(__file__).resolve().parents[1],
    ):
        out["repositories"][str(path)] = dict(
            head=subprocess.check_output(
                ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
            ).strip(),
            status=subprocess.check_output(
                ["git", "-C", str(path), "status", "--short"], text=True
            ),
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
