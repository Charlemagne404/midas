from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path


RELEASE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "runtime"
    / "veritas-gap-detail-v2-20261020"
)


def test_v2_release_preserves_v1_lineage_and_blocks_deterministic_retries(
    tmp_path: Path,
):
    program = textwrap.dedent(
        """
        import json
        from pathlib import Path

        from midas.reality.storage import Store, file_hash
        from midas.veritas import gap_detail_analysis as analysis
        from midas.veritas.gap_detail_control import read_control, run_v2_batch

        assert Path(analysis.__file__).is_relative_to(Path.cwd() / "packages")
        START = 1_792_000_000_000_000_000
        analysis.verify_campaign = lambda plan: None
        root = Path(__import__("os").environ["V2_TEST_ROOT"])
        raw = root / "raw"
        raw.mkdir(parents=True)
        store = Store(raw, reserve=1, segment_bytes=32 * 1024**2)
        markets = [
            {
                "id": f"market-{index}",
                "condition": f"condition-{index}",
                "tokens": {f"asset-yes-{index}": "Yes", f"asset-no-{index}": "No"},
            }
            for index in range(1, 130)
        ]
        store.rotate()
        store.append(
            "gap", {"reason": "process_start"},
            received_ns=START - 1_000_000_000, monotonic_ns=0,
        )
        store.append("discovery", "fixture universe", received_ns=START, cohort=markets)
        store.rotate()
        store.append(
            "gap",
            {
                "reason": "book_resynchronization",
                "affected_assets": {
                    f"asset-yes-{index}": "timestamp_regression"
                    for index in range(1, 130)
                },
            },
            received_ns=START + 10_000_001,
            monotonic_ns=1,
        )
        store.rotate()
        store.append(
            "gap", {"reason": "connection_failure"},
            received_ns=START + 20_000_002, monotonic_ns=2,
        )
        store.close()

        campaign = root / "campaign.json"
        campaign.write_text(json.dumps({
            "campaign_id": "fixture-campaign",
            "identity": {
                "raw_root": str(raw.resolve()),
                "start_ns": START,
                "end_ns": START + 100_000_000,
            },
        }))
        campaign_sha256 = file_hash(campaign)
        output = root / "output"
        kwargs = {
            "campaign_path": campaign,
            "expected_campaign_sha256": campaign_sha256,
            "expected_campaign_id": "fixture-campaign",
            "expected_source_root": raw,
            "max_segments": 16,
        }
        v1 = analysis.update_finalized_gap_detail_analysis(
            output, output_version="v1", **kwargs
        )
        v1_state = output / "gap-detail-state-v1.json"
        v1_state_hash = file_hash(v1_state)
        v2 = analysis.update_finalized_gap_detail_analysis(
            output, output_version="v2", **kwargs
        )

        assert v1["analysis_version"].endswith("-v1")
        assert v2["analysis_version"].endswith("-v2")
        assert len(v2["campaign_window_affected_market_counts"]) == 129
        assert v2["campaign_window_gap_counts_by_reason"] == {
            "book_resynchronization": 1,
            "connection_failure": 1,
        }
        assert v2["source_lineage"]["campaign_sha256"] == campaign_sha256
        assert v2["source_lineage"]["source_root"] == str(raw.resolve())
        assert v2["source_lineage"]["processed_segment_count"] == 3
        assert file_hash(v1_state) == v1_state_hash
        assert (output / "gap-detail-state-v1.json").is_file()
        assert (output / "gap-detail-state-v2.json").is_file()
        assert len(list((output / "gap-detail-events" / "v1").glob("*.json"))) == 3
        assert len(list((output / "gap-detail-events" / "v2").glob("*.json"))) == 3

        blocked_root = root / "blocked"
        attempts = [0]
        def deterministic_failure(*args, **kwargs):
            attempts[0] += 1
            raise ValueError("pinned source prefix rejected")

        first = run_v2_batch(blocked_root, updater=deterministic_failure)
        second = run_v2_batch(blocked_root, updater=deterministic_failure)
        assert first["status"] == second["status"] == "BLOCKED"
        assert first["last_error"] == "pinned source prefix rejected"
        assert read_control(blocked_root)["status"] == "BLOCKED"
        assert attempts[0] == 1
        """
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(RELEASE_ROOT / "packages"), env.get("PYTHONPATH", "")]
    )
    env["V2_TEST_ROOT"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=RELEASE_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
