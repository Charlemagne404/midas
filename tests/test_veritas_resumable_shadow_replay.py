from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from midas.reality.reconstruction import Engine
from midas.reality.research_schema import digest
from midas.reality.shadow_campaign import freeze
from midas.reality.shadow_source import Context
from midas.reality.storage import MAGIC, Store, atomic_json, canonical, manifest
from test_reality_foundry import START, market, snapshot

from scripts.benchmark_shadow_consume import (
    _resolve_isolated_path,
    run_resumable_once,
    stable_sha256,
)

RUN_ID = "b" * 64
PRODUCER_HASH = "a" * 64


def make_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    raw = tmp_path / "raw"
    store = Store(raw, reserve=1, segment_bytes=1)
    engine = Engine()

    def add(kind: str, payload: object, ms: int, **kwargs: object) -> None:
        row = store.append(
            kind,
            payload,
            received_ns=START + ms * 10**6,
            monotonic_ns=ms * 10**6,
            **kwargs,
        )
        engine.consume(row)

    add(
        "gap",
        dict(reason="process_start", reconstruction_version=4, implementation_sha256=PRODUCER_HASH),
        0,
    )
    add("public_market_metadata", "fixture metadata", 0, market_id="1")
    add("discovery", "fixture universe", 0, cohort=[market()])
    for ms in (0, 100, 200, 300, 400, 500):
        add("frame", snapshot(ms, moved=ms > 0), ms)
    add("checkpoint", dict(state_sha256=engine.digest()), 500)
    store.close()

    training = tmp_path / "training"
    report_dir = training / "runs" / RUN_ID
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps({"targets": {}, "state": "labeled_fixture_no_model"}), encoding="utf-8"
    )
    monkeypatch.setattr("time.time_ns", lambda: START - 10**9)
    campaign_root = tmp_path / "campaigns" / "fixture"
    campaign = freeze(
        campaign_root,
        raw,
        training,
        RUN_ID,
        PRODUCER_HASH,
        {},
        fixture=True,
        start_ns=START,
        days=1,
    )
    campaign["identity"]["reserve_bytes"] = 1
    campaign["campaign_id"] = digest(campaign["identity"])
    campaign_path = campaign_root / "campaign.json"
    atomic_json(campaign_path, campaign)

    first_segment = manifest(raw)["segments"][0]
    runtime = dict(
        campaign_id=campaign["campaign_id"],
        context=Context().snapshot(),
        cursor=dict(
            segment=Path(first_segment["file"]).stem,
            offset=len(MAGIC),
            ordinal=first_segment["first"] - 1,
        ),
        next_decision={},
        next_observation={},
        counters=dict(records=0, lagged_frames_skipped=0, source_checkpoints=0),
    )
    runtime_bytes = canonical(runtime)
    snapshot_path = tmp_path / "input-runtime.json"
    atomic_json(
        snapshot_path,
        dict(
            schema_version=1,
            campaign_id=campaign["campaign_id"],
            runtime=runtime,
            runtime_sha256=stable_sha256(runtime),
            persisted_runtime_json=runtime_bytes.decode("utf-8"),
            persisted_runtime_sha256=hashlib.sha256(runtime_bytes).hexdigest(),
        ),
    )
    return campaign, runtime, campaign_path, snapshot_path


def run_chunk(
    tmp_path: Path,
    campaign: dict[str, object],
    runtime: dict[str, object],
    campaign_path: Path,
    snapshot_path: Path,
    name: str,
    *,
    segments: int,
    should_stop=lambda: False,
) -> dict[str, object]:
    return run_resumable_once(
        campaign,
        runtime,
        stable_sha256(runtime),
        hashlib.sha256(canonical(runtime)).hexdigest(),
        campaign_path=campaign_path,
        runtime_snapshot_path=snapshot_path,
        work_dir=tmp_path / "canaries" / name,
        segment_target=segments,
        checkpoint_interval_seconds=60,
        allow_current_code=True,
        include_research_events=True,
        include_final_runtime=True,
        should_stop=should_stop,
        allowed_root=tmp_path / "canaries",
    )


def test_split_resumable_replay_matches_one_uninterrupted_window(tmp_path, monkeypatch):
    campaign, runtime, campaign_path, snapshot_path = make_inputs(tmp_path, monkeypatch)
    whole = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "whole", segments=4
    )
    first = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "split", segments=2
    )
    second = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "split", segments=2
    )

    for key in (
        "ending_cursor",
        "records_processed_total",
        "frames_processed_total",
        "engine_state_sha256",
        "context_state_sha256",
        "decision_count",
        "observation_count",
        "followup_status_counts",
        "research_semantics_sha256",
    ):
        assert second[key] == whole[key], key
    assert first["run_termination"] == "segment_bound"
    assert second["run_termination"] == "segment_bound"
    assert (
        second["final_journal_verification"]["events"]
        > first["final_journal_verification"]["events"]
    )


def test_interrupted_record_replays_idempotently_from_prior_cursor(tmp_path, monkeypatch):
    campaign, runtime, campaign_path, snapshot_path = make_inputs(tmp_path, monkeypatch)
    whole = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "whole", segments=20
    )

    from scripts import benchmark_shadow_consume as runner

    original_consume = runner.ResumableShadow.consume
    failed = False

    def fail_after_frame(self, record, ref):
        nonlocal failed
        original_consume(self, record, ref)
        if record["kind"] == "frame" and not failed:
            failed = True
            raise RuntimeError("fixture interruption after durable per-record effects")

    monkeypatch.setattr(runner.ResumableShadow, "consume", fail_after_frame)
    with pytest.raises(RuntimeError, match="fixture interruption"):
        run_chunk(
            tmp_path, campaign, runtime, campaign_path, snapshot_path, "recovered", segments=20
        )
    monkeypatch.setattr(runner.ResumableShadow, "consume", original_consume)
    resumed = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "recovered", segments=20
    )

    assert failed
    assert resumed["ending_cursor"] == whole["ending_cursor"]
    assert resumed["records_processed_total"] == whole["records_processed_total"]
    assert resumed["context_state_sha256"] == whole["context_state_sha256"]
    assert resumed["engine_state_sha256"] == whole["engine_state_sha256"]
    assert resumed["decision_count"] == whole["decision_count"]
    assert resumed["observation_count"] == whole["observation_count"]
    assert resumed["research_semantics_sha256"] == whole["research_semantics_sha256"]


def test_missing_decision_commit_marker_is_repaired_before_followup(tmp_path, monkeypatch):
    campaign, runtime, campaign_path, snapshot_path = make_inputs(tmp_path, monkeypatch)
    whole = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "whole", segments=20
    )

    from scripts import benchmark_shadow_consume as runner

    original_append = runner.shadow_store.Journal.append
    interrupted = False

    def fail_before_commit_marker(self, kind, body, now=None):
        nonlocal interrupted
        if kind == "decision_committed" and not interrupted:
            interrupted = True
            raise RuntimeError("fixture interruption between decision transactions")
        return original_append(self, kind, body, now)

    monkeypatch.setattr(runner.shadow_store.Journal, "append", fail_before_commit_marker)
    with pytest.raises(RuntimeError, match="between decision transactions"):
        run_chunk(
            tmp_path, campaign, runtime, campaign_path, snapshot_path, "recovered", segments=20
        )
    monkeypatch.setattr(runner.shadow_store.Journal, "append", original_append)
    resumed = run_chunk(
        tmp_path, campaign, runtime, campaign_path, snapshot_path, "recovered", segments=20
    )

    assert interrupted
    assert resumed["recovered_uncommitted_decisions"] == 1
    assert resumed["ending_cursor"] == whole["ending_cursor"]
    assert resumed["context_state_sha256"] == whole["context_state_sha256"]
    assert resumed["decision_count"] == whole["decision_count"]
    assert resumed["research_semantics_sha256"] == whole["research_semantics_sha256"]


def test_resumable_path_guard_rejects_protected_source(tmp_path):
    canaries = tmp_path / "canaries"
    raw = tmp_path / "raw"
    raw.mkdir()
    with pytest.raises(ValueError, match="below"):
        _resolve_isolated_path(
            raw / "shadow",
            allowed_root=canaries,
            protected_roots=[raw],
        )


def test_resume_rejects_changed_initial_runtime_identity(tmp_path, monkeypatch):
    campaign, runtime, campaign_path, snapshot_path = make_inputs(tmp_path, monkeypatch)
    run_chunk(tmp_path, campaign, runtime, campaign_path, snapshot_path, "identity", segments=1)

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    changed = copy.deepcopy(snapshot["runtime"])
    changed["next_decision"]["fixture"] = 1
    snapshot["runtime"] = changed
    snapshot["runtime_sha256"] = stable_sha256(changed)
    persisted = canonical(changed)
    snapshot["persisted_runtime_json"] = persisted.decode("utf-8")
    snapshot["persisted_runtime_sha256"] = hashlib.sha256(persisted).hexdigest()
    atomic_json(snapshot_path, snapshot)

    with pytest.raises(ValueError, match="identity changed"):
        run_resumable_once(
            campaign,
            changed,
            stable_sha256(changed),
            hashlib.sha256(persisted).hexdigest(),
            campaign_path=campaign_path,
            runtime_snapshot_path=snapshot_path,
            work_dir=tmp_path / "canaries" / "identity",
            segment_target=1,
            checkpoint_interval_seconds=60,
            allow_current_code=True,
            include_research_events=False,
            include_final_runtime=False,
            allowed_root=tmp_path / "canaries",
        )


def test_cli_writes_bounded_result_only_inside_private_workdir(tmp_path, monkeypatch):
    campaign, _runtime, campaign_path, snapshot_path = make_inputs(tmp_path, monkeypatch)
    import scripts.benchmark_shadow_consume as runner

    cache = tmp_path / "empty-pycache"
    cache.mkdir()
    monkeypatch.setattr(sys, "pycache_prefix", str(cache))
    monkeypatch.setattr(runner, "_canary_root", lambda: tmp_path / "canaries")
    work_dir = tmp_path / "canaries" / "cli"
    result_path = work_dir / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_shadow_consume.py",
            "--campaign",
            str(campaign_path),
            "--runtime-snapshot",
            str(snapshot_path),
            "--allow-current-code",
            "--segments",
            "2",
            "--repetitions",
            "1",
            "--work-dir",
            str(work_dir),
            "--output",
            str(result_path),
        ],
    )

    runner.main()

    output = json.loads(result_path.read_text(encoding="utf-8"))
    assert output["campaign_id"] == campaign["campaign_id"]
    assert output["repetitions"][0]["run_termination"] == "segment_bound"
    assert (work_dir / "work-manifest.json").is_file()
    assert (work_dir / "shadow.sqlite").is_file()
    assert work_dir.stat().st_mode & 0o077 == 0


def test_cli_rejects_unsafe_output_before_replay(tmp_path, monkeypatch):
    _, _, campaign_path, snapshot_path = make_inputs(tmp_path, monkeypatch)
    import scripts.benchmark_shadow_consume as runner

    cache = tmp_path / "empty-pycache"
    cache.mkdir()
    monkeypatch.setattr(sys, "pycache_prefix", str(cache))
    canary_root = tmp_path / "canaries"
    monkeypatch.setattr(runner, "_canary_root", lambda: canary_root)
    called = False

    def unexpected_replay(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("unsafe output reached replay")

    monkeypatch.setattr(runner, "run_resumable_once", unexpected_replay)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_shadow_consume.py",
            "--campaign",
            str(campaign_path),
            "--runtime-snapshot",
            str(snapshot_path),
            "--allow-current-code",
            "--segments",
            "2",
            "--repetitions",
            "1",
            "--work-dir",
            str(canary_root / "unsafe"),
            "--output",
            str(tmp_path / "outside.json"),
        ],
    )

    with pytest.raises(ValueError, match="must be below"):
        runner.main()
    assert not called
    assert not (canary_root / "unsafe").exists()
