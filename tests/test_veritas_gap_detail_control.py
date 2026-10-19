from __future__ import annotations

import pytest
from midas.veritas.gap_detail_control import read_control, reset_control, run_v2_batch


def test_deterministic_failure_blocks_future_timer_batches_until_reset(tmp_path):
    calls = 0

    def fail(root, **kwargs):
        nonlocal calls
        calls += 1
        raise ValueError("pinned source failed validation")

    first = run_v2_batch(tmp_path / "v2", updater=fail)
    second = run_v2_batch(tmp_path / "v2", updater=fail)

    assert first["status"] == second["status"] == "BLOCKED"
    assert first["last_error"] == "pinned source failed validation"
    assert calls == 1

    rearmed = reset_control(tmp_path / "v2", reason="source validation fixed and rechecked")
    assert rearmed["status"] == "ARMED"
    assert [item["event"] for item in rearmed["history"]] == [
        "deterministic_failure",
        "operator_reset",
    ]

    def pass_batch(root, *, output_version):
        assert output_version == "v2"
        return {
            "status": "catching_up",
            "batch_processed_segment_count": 1,
            "processed_segment_count": 1,
            "pending_segment_count": 2,
            "summary_sha256": "a" * 64,
        }

    resumed = run_v2_batch(tmp_path / "v2", updater=pass_batch)
    assert resumed["status"] == "CATCHING_UP"
    assert resumed["consecutive_failures"] == 0
    assert resumed["summary_sha256"] == "a" * 64
    assert read_control(tmp_path / "v2") == resumed


def test_transient_failures_are_bounded_then_blocked(tmp_path):
    calls = 0

    def fail(root, **kwargs):
        nonlocal calls
        calls += 1
        raise OSError("temporary storage error")

    root = tmp_path / "v2"
    assert run_v2_batch(root, updater=fail)["status"] == "RETRY_WAIT"
    assert run_v2_batch(root, updater=fail)["status"] == "RETRY_WAIT"
    assert run_v2_batch(root, updater=fail)["status"] == "BLOCKED"
    assert run_v2_batch(root, updater=fail)["status"] == "BLOCKED"
    assert calls == 3
    assert read_control(root)["consecutive_failures"] == 3


def test_unexpected_failures_block_future_batches(tmp_path):
    calls = 0

    def fail(root, **kwargs):
        nonlocal calls
        calls += 1
        raise TypeError("unclassified pipeline failure")

    root = tmp_path / "v2"
    first = run_v2_batch(root, updater=fail)
    second = run_v2_batch(root, updater=fail)

    assert first["status"] == second["status"] == "BLOCKED"
    assert first["last_error_type"] == "TypeError"
    assert calls == 1


def test_control_digest_detects_manual_edit(tmp_path):
    root = tmp_path / "v2"
    reset_control(root)
    path = root / "gap-detail-run-control-v2.json"
    path.write_text(path.read_text().replace('"status":"ARMED"', '"status":"BLOCKED"'))

    with pytest.raises(ValueError, match="digest mismatch"):
        read_control(root)
