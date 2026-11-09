#!/usr/bin/env python3
"""Run one bounded, read-only finalized Reality source analysis batch."""

from __future__ import annotations

import argparse
import errno
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from midas.veritas.finalized_source_analysis import (
    MAX_SEGMENTS_PER_RUN,
    MAX_SOURCE_BYTES_PER_RUN,
    update_finalized_source_analysis,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Veritas observatory data root")
    parser.add_argument(
        "--max-segments",
        type=int,
        default=MAX_SEGMENTS_PER_RUN,
        help="Maximum new segments in this run",
    )
    parser.add_argument(
        "--max-source-mib",
        type=int,
        default=MAX_SOURCE_BYTES_PER_RUN // 1024**2,
        help="Maximum new finalized source MiB in this run",
    )
    args = parser.parse_args()
    ci_values = {
        key: os.environ.get(key)
        for key in (
            "MIDAS_VERITAS_CI_TEST",
            "MIDAS_VERITAS_CI_PARENT_UNIT",
            "MIDAS_VERITAS_CI_PARENT_INVOCATION_ID",
            "MIDAS_VERITAS_CI_CAMPAIGN_PATH",
            "MIDAS_VERITAS_CI_CAMPAIGN_SHA256",
            "MIDAS_VERITAS_CI_CAMPAIGN_ID",
            "MIDAS_VERITAS_CI_SOURCE_ROOT",
            "MIDAS_VERITAS_CI_SCENARIO",
        )
    }
    ci_mode = ci_values["MIDAS_VERITAS_CI_TEST"] is not None
    analysis_options = {}
    if ci_mode:
        parent_unit = ci_values["MIDAS_VERITAS_CI_PARENT_UNIT"]
        parent_invocation = ci_values["MIDAS_VERITAS_CI_PARENT_INVOCATION_ID"]
        if (
            ci_values["MIDAS_VERITAS_CI_TEST"] != "midas-veritas-systemd-ci-v1"
            or parent_unit != "midas-veritas-source-analysis-ci.service"
            or not parent_invocation
            or len(parent_invocation) != 32
            or any(character not in "0123456789abcdef" for character in parent_invocation)
            or "midas-heavy-veritas-" not in Path("/proc/self/cgroup").read_text()
        ):
            raise SystemExit("Veritas CI overrides require the guarded CI transient worker")
        state = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                parent_unit,
                "-p",
                "ActiveState",
                "-p",
                "InvocationID",
                "--value",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        values = state.stdout.splitlines()
        if state.returncode or values != ["active", parent_invocation]:
            raise SystemExit("Veritas CI parent service identity could not be verified")
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except OSError as error:
            if error.errno not in {errno.EAFNOSUPPORT, errno.EPERM}:
                raise SystemExit(
                    "Veritas CI network restriction probe returned an unexpected error"
                ) from error
        else:
            probe.close()
            raise SystemExit("Veritas CI worker can create an IPv4 socket")
        scenario = ci_values["MIDAS_VERITAS_CI_SCENARIO"]
        if scenario == "worker_failure":
            raise SystemExit(42)
        if scenario == "watchdog":
            time.sleep(120)
        if scenario != "success" and scenario != "watchdog":
            raise SystemExit("unsupported Veritas CI worker scenario")
        analysis_options = {
            "campaign_path": Path(ci_values["MIDAS_VERITAS_CI_CAMPAIGN_PATH"] or ""),
            "expected_campaign_sha256": ci_values["MIDAS_VERITAS_CI_CAMPAIGN_SHA256"],
            "expected_campaign_id": ci_values["MIDAS_VERITAS_CI_CAMPAIGN_ID"],
            "expected_source_root": Path(ci_values["MIDAS_VERITAS_CI_SOURCE_ROOT"] or ""),
        }
    summary = update_finalized_source_analysis(
        args.root,
        max_segments=args.max_segments,
        max_source_bytes=args.max_source_mib * 1024**2,
        **analysis_options,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "readiness": summary["readiness"],
                "batch_processed_segment_count": summary["batch_processed_segment_count"],
                "processed_segment_count": summary["processed_segment_count"],
                "pending_segment_count": summary["pending_segment_count"],
                "pending_source_bytes": summary["pending_source_bytes"],
                "last_processed_ordinal": summary["last_processed_ordinal"],
                "summary_sha256": summary["summary_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
