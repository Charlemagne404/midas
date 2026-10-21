"""Disposable fixture verification of the deferred full-store procedure."""

import importlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from midas.reality import recovery
from midas.reality.reconstruction import Engine
from midas.reality.storage import Store

REALITY_PACKAGES = Path(recovery.__file__).resolve().parents[2]
os.environ["MIDAS_REALITY_VALIDATION_PACKAGES"] = str(REALITY_PACKAGES)

validation = importlib.import_module("scripts.reality_full_scale_validation")

os.environ["MIDAS_REALITY_VALIDATION_SOURCE_SHA256"] = validation.IMPLEMENTATION_SOURCE_SHA256


def fixture(tmp_path):
    source = tmp_path / "source"
    store = Store(source, reserve=1)
    store.append("gap", {"reason": "synthetic_one"})
    store.append("gap", {"reason": "synthetic_two"})
    store.close()
    return source


def test_full_scale_matrix_includes_replay_and_checkpoint_interruption():
    phases = validation.RECOVERY_PHASES

    assert phases[:6] == (
        "readonly_probe",
        "cold",
        "fast",
        "corrupt",
        "interrupt_save",
        "after_interrupt_save",
    )
    assert phases[6:] == ("interrupt", "after_interrupt")


def staged_fixture(tmp_path):
    source = fixture(tmp_path)
    catalog, identities, boundary = validation.inventory(source)
    output = tmp_path / "recovery-stage"
    output.mkdir()
    view = output / "view"
    view.mkdir()
    validation.write(output / "catalog.json", catalog)
    validation.write(output / "identities.json", identities)
    validation.write(output / "boundary.json", boundary)
    validation.write(output / "admission.json", dict(pid="863193", memory_events={"max": 0}))
    validation.write(output / "staging-policy.json", dict(with_endurance=False))
    for info in catalog["segments"]:
        (view / info["file"]).symlink_to(source / info["file"])
        validation.write((view / info["file"]).with_suffix(".json"), info)
    policy = dict(
        source_root=str(source.resolve()),
        staging_root=str(output.resolve()),
        source_reads="allowed",
        filesystem_mutation="denied except below staging_root",
    )
    expected_file = view / catalog["segments"][0]["file"]
    validation.write(output / "readonly_probe-landlock.json", policy)
    validation.write(
        output / "readonly_probe.json",
        dict(
            denied_source_file=str(expected_file),
            catalog_segment_sha256=catalog["segments"][0]["sha256"],
            source_write_denied=True,
            implementation_source_sha256=boundary["implementation_source_sha256"],
            recovery_implementation_sha256=boundary["recovery_implementation_sha256"],
            policy=policy,
        ),
    )
    return source, output, catalog, identities, boundary


def test_inventory_pins_finalized_only_without_claiming_hash_verification(tmp_path):
    source = fixture(tmp_path)
    open_tail = source / "00000000000000000003-active.open"
    open_tail.write_bytes(b"active")
    original_tail = open_tail.read_bytes()
    catalog, identities, summary = validation.inventory(source)
    assert len(catalog["segments"]) == len(identities) == 1
    assert summary["last_ordinal"] == 2
    assert summary["kinds"]["gap"] == 2
    assert summary["implementation_packages"] == str(REALITY_PACKAGES)
    assert summary["implementation_source_sha256"] == validation.IMPLEMENTATION_SOURCE_SHA256
    assert summary["recovery_implementation_sha256"] == validation.RECOVERY_IMPLEMENTATION_SHA256
    assert summary["excluded_open"][0]["observed_bytes"] == 6
    assert "NOT yet verified" in summary["scope"]
    assert open_tail.read_bytes() == original_tail


def test_inventory_reconciles_open_tail_renamed_during_snapshot(tmp_path, monkeypatch):
    source = fixture(tmp_path)
    store = Store(source, reserve=1)
    store.append("gap", {"reason": "synthetic_three"})
    store.close()
    finalized = sorted(source.glob("*.seg"))[-1]
    sidecar = finalized.with_suffix(".json")
    open_tail = finalized.with_suffix(".open")
    pending_sidecar = tmp_path / sidecar.name
    finalized.rename(open_tail)
    sidecar.rename(pending_sidecar)
    original_stat = Path.stat
    rotated = False

    def rotate_before_open_stat(path, *args, **kwargs):
        nonlocal rotated
        if path == open_tail and not rotated:
            open_tail.rename(finalized)
            pending_sidecar.rename(sidecar)
            rotated = True
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", rotate_before_open_stat)
    catalog, identities, summary = validation.inventory(source)

    assert rotated
    assert len(catalog["segments"]) == len(identities) == 2
    assert summary["last_ordinal"] == 3
    assert summary["excluded_open"] == []
    assert summary["unmatched_finalized"] == []
    assert summary["capture_attempts"] == 2
    assert summary["capture_retry_events"] == [
        dict(
            attempt=1,
            unmatched_finalized=[],
            open_tail_rotations=[
                dict(
                    file=open_tail.name,
                    finalized_file=finalized.name,
                    finalized_bytes=finalized.stat().st_size,
                )
            ],
        )
    ]


def test_candidate_source_hash_is_required_and_exact(tmp_path):
    packages = tmp_path / "packages"
    reality = packages / "midas" / "reality"
    reality.mkdir(parents=True)
    (reality / "recovery.py").write_text("IDENTITY = 'candidate'\n")
    expected = validation.reality_source_sha256(packages)

    assert validation.require_reality_source_sha256(packages, expected) == expected
    with pytest.raises(ValueError, match="does not match"):
        validation.require_reality_source_sha256(packages, "0" * 64)


def test_cold_replay_resumes_from_a_verified_segment_checkpoint(tmp_path, monkeypatch):
    source = tmp_path / "multi-segment-source"
    store = Store(source, reserve=1, segment_bytes=1)
    for number in range(5):
        store.append("gap", {"reason": f"synthetic_{number}"})
    store.close()
    catalog, identities, boundary = validation.inventory(source)
    assert len(catalog["segments"]) >= 3
    output = tmp_path / "chunked-stage"
    output.mkdir()
    root = output / "view"
    root.mkdir()
    validation.write(output / "catalog.json", catalog)
    validation.write(output / "identities.json", identities)
    validation.write(output / "boundary.json", boundary)
    for info in catalog["segments"]:
        (root / info["file"]).symlink_to(source / info["file"])
        validation.write((root / info["file"]).with_suffix(".json"), info)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    original_replay = recovery.replay
    calls = 0

    def stop_before_second_chunk(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated isolated worker interruption")
        return original_replay(*args, **kwargs)

    monkeypatch.setattr(validation, "COLD_CHUNK_SEGMENTS", 2)
    monkeypatch.setattr(recovery, "replay", stop_before_second_chunk)
    with pytest.raises(RuntimeError, match="simulated isolated worker interruption"):
        validation.resumable_reconstruction(root, catalog, boundary, "cold", None, {"value": True})
    progress_path = output / "cold-progress.json"
    assert json.loads(progress_path.read_text())["next_segment_index"] == 2

    monkeypatch.setattr(recovery, "replay", original_replay)
    engine, status = validation.resumable_reconstruction(
        root, catalog, boundary, "cold", None, {"value": True}
    )
    verified, recovery_status = recovery.recover(root, catalog)

    assert status["mode"] == "resumable_full_replay"
    assert status["prefix_segments_restored"] == 2
    assert status["segments_reconstructed"] == len(catalog["segments"])
    assert engine.__dict__ == verified.__dict__
    assert recovery_status["mode"] == "checkpoint_and_verified_tail"
    assert before == {path.name: path.read_bytes() for path in source.iterdir()}


def test_inventory_rejects_missing_sidecar_inside_boundary(tmp_path):
    source = fixture(tmp_path)
    (source / "00000000000000000001-orphan.seg").write_bytes(b"bad")
    with pytest.raises(ValueError, match="without sidecar"):
        validation.inventory(source)


def test_source_quality_audit_confirms_historical_hash_mismatch_without_assigning_blame():
    engine = Engine()
    engine.books["asset-1"] = dict(
        last=[10, 2],
        snapshot=[1, 2],
        received_ns=150,
        issue=None,
        bids={Decimal("0.5"): Decimal("2")},
        asks={Decimal("0.6"): Decimal("3")},
    )
    record = dict(
        kind="book_comparison",
        ordinal=12,
        payload=dict(
            assessment="stable_local_lineage_divergence",
            asset_id="asset-1",
            condition="condition-1",
            raw_ordinal=11,
            before_lineage=[10, 2],
            after_lineage=[10, 2],
            local_depth_sha256="e" * 64,
            independent_depth_sha256="f" * 64,
            request_ns=100,
            response_ns=200,
            round_trip_ns=100,
            source_timestamp_ms=1,
            source_native_hash="native-hash",
        ),
    )

    observed = validation.source_quality_observation(engine, record)

    assert observed["classification"] == "CONFIRMED_DEPTH_HASH_MISMATCH_DIRECTION_UNKNOWN"
    assert observed["replay_state_advanced_after_response"] is False
    assert observed["local_depth_sha256"] == "e" * 64
    assert observed["replay_depth_sha256_at_durable_record"] != "e" * 64
    assert observed["local_hash_matches_independent"] is False
    assert observed["local_age_at_response_ns"] == 50
    assert "cannot identify which view was incomplete" in observed["limitation"]


def test_source_quality_audit_does_not_use_later_durable_state_as_response_state():
    engine = Engine()
    engine.books["asset-1"] = dict(
        last=[13, 0],
        snapshot=[10, 0],
        received_ns=300,
        issue=None,
        bids={Decimal("0.5"): Decimal("2")},
        asks={Decimal("0.6"): Decimal("3")},
    )
    record = dict(
        kind="book_comparison",
        ordinal=20,
        payload=dict(
            assessment="stable_local_lineage_divergence",
            asset_id="asset-1",
            condition="condition-1",
            raw_ordinal=19,
            before_lineage=[10, 0],
            after_lineage=[10, 0],
            local_depth_sha256="a" * 64,
            independent_depth_sha256="a" * 64,
            response_ns=200,
        ),
    )

    observed = validation.source_quality_observation(engine, record)

    assert observed["classification"] == "RECORDED_DIVERGENCE_NOT_REPRODUCED_AT_RESPONSE"
    assert observed["replay_state_advanced_after_response"] is True
    assert observed["local_depth_sha256"] == "a" * 64
    assert observed["local_age_at_response_ns"] is None


def test_source_quality_audit_does_not_treat_two_missing_hashes_as_a_match():
    observed = validation.source_quality_observation(
        Engine(),
        dict(
            kind="book_comparison",
            ordinal=20,
            payload=dict(
                assessment="stable_local_lineage_divergence",
                asset_id="asset-1",
                before_lineage=[17, 0],
                after_lineage=[17, 0],
                independent_depth_sha256=None,
            ),
        ),
    )

    assert observed["classification"] == "COMPARISON_HASH_UNAVAILABLE"
    assert observed["local_hash_matches_independent"] is False


def test_source_quality_audit_preserves_gap_reason_and_bounded_asset_sample():
    assets = [f"asset-{number}" for number in range(12)]
    observed = validation.source_quality_observation(
        Engine(),
        dict(
            kind="gap",
            ordinal=42,
            payload=dict(reason="book_resynchronization", assets=assets),
        ),
    )

    assert observed["reason"] == "book_resynchronization"
    assert observed["assets_field"] == "assets"
    assert observed["assets_count"] == len(assets)
    assert observed["assets_sample"] == assets[:8]


def test_source_quality_audit_reads_affected_assets_from_recorder_payload():
    affected = [f"token-{number}" for number in range(12)]
    observed = validation.source_quality_observation(
        Engine(),
        dict(
            kind="gap",
            ordinal=43,
            payload=dict(
                reason="book_resynchronization",
                affected_assets=affected,
                assets=["obsolete-field"],
            ),
        ),
    )

    assert observed["assets_field"] == "affected_assets"
    assert observed["assets_count"] == len(affected)
    assert observed["assets_sample"] == affected[:8]


def test_source_quality_audit_summarizes_recorder_asset_to_issue_mapping():
    affected = {f"token-{number}": "top_divergence" for number in range(12)}
    observed = validation.source_quality_observation(
        Engine(),
        dict(
            kind="gap",
            ordinal=43,
            payload=dict(reason="book_resynchronization", affected_assets=affected),
        ),
    )

    assert observed["assets_field"] == "affected_assets"
    assert observed["assets_count"] == len(affected)
    assert observed["assets_sample"] == list(affected)[:8]
    assert observed["assets_issue_sample"] == [
        dict(asset_id=asset, issue="top_divergence") for asset in list(affected)[:8]
    ]


def test_source_quality_audit_keeps_absent_affected_assets_unknown():
    observed = validation.source_quality_observation(
        Engine(),
        dict(kind="gap", ordinal=44, payload={"reason": "connection_failure"}),
    )

    assert observed["assets_field"] is None
    assert "assets_count" not in observed


def test_failed_admission_does_not_create_snapshot(tmp_path, monkeypatch):
    source = fixture(tmp_path)
    output = tmp_path / "never-created"

    def reject():
        raise ValueError("resource gate")

    monkeypatch.setattr(validation, "admission", reject)
    with pytest.raises(ValueError, match="resource gate"):
        validation.run(source, output)
    assert not output.exists()


def test_only_transient_host_pressure_gate_failures_are_retryable():
    assert validation.is_transient_pressure_rejection(
        ValueError(
            "Isolated staging admission rejected: host io full PSI above 4.0% over 10 seconds"
        )
    )
    assert validation.is_transient_pressure_rejection(
        ValueError(
            "Isolated staging admission rejected: critical service telemetry unavailable "
            "during unit transition: midas-reality-api.service (deactivating)"
        )
    )
    assert not validation.is_transient_pressure_rejection(
        ValueError(
            "Isolated staging admission rejected: critical service "
            "midas-reality-api.service CPU pressure is unavailable"
        )
    )
    assert not validation.is_transient_pressure_rejection(
        ValueError("Isolated staging admission rejected: protected recorder has less than 32 MiB")
    )
    assert not validation.is_transient_pressure_rejection(
        ValueError("Staging filesystem fell below its reserved free space")
    )


def test_start_admission_window_resets_after_a_transient_pressure_spike(monkeypatch):
    good = {"pid": "863193", "memory_events": {"max": 0, "oom": 0, "oom_kill": 0}}
    pressure = ValueError(
        "Isolated staging admission rejected: host io full PSI above 4.0% over 10 seconds"
    )
    responses = [pressure, good, good, good, good, pressure, *([good] * 12)]
    calls = []
    sleeps = []

    def fake_admission(baseline_events=None):
        calls.append(baseline_events)
        result = responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(validation, "admission", fake_admission)
    monkeypatch.setattr(validation.time, "sleep", sleeps.append)

    result = validation.wait_for_sustained_admission()

    assert result is good
    assert len(responses) == 0
    assert len(sleeps) == 17
    assert all(value is None or value == good["memory_events"] for value in calls)


def test_resume_validates_staged_boundary_and_allows_new_source_suffix(tmp_path):
    source, output, catalog, identities, boundary = staged_fixture(tmp_path)

    resumed = validation.validate_staged_output(source, output)

    assert resumed[0] == catalog
    assert resumed[1] == identities
    assert resumed[2]["catalog_sha256"] == boundary["catalog_sha256"]
    validation.validate_readonly_probe(output, catalog, boundary)


def test_resume_requires_contiguous_receipts_bound_to_pinned_boundary(tmp_path):
    _, output, _, _, boundary = staged_fixture(tmp_path)
    identity = ["a" * 64, "b" * 64, boundary["last_ordinal"], boundary["kinds"]["gap"]]
    validation.write(
        output / "cold.json",
        dict(
            phase="cold",
            boundary_catalog_sha256=boundary["catalog_sha256"],
            boundary_identities_sha256=boundary["identities_sha256"],
            implementation_source_sha256=boundary["implementation_source_sha256"],
            recovery_implementation_sha256=boundary["recovery_implementation_sha256"],
            state_sha256=identity[0],
            internal_sha256=identity[1],
            ordinal=identity[2],
            gaps=identity[3],
            recovery=dict(
                mode="full_replay",
                segments_reconstructed=boundary["segment_count"],
                archive_bytes=boundary["archive_bytes"],
            ),
        ),
    )
    phases = ("readonly_probe", "cold", "fast", "restart")

    completed, expected, _ = validation.completed_phases(
        output, phases, json.loads((output / "catalog.json").read_text()), boundary
    )

    assert completed == {"readonly_probe", "cold"}
    assert expected == identity
    validation.write(
        output / "restart.json",
        dict(
            phase="restart",
            boundary_catalog_sha256=boundary["catalog_sha256"],
            boundary_identities_sha256=boundary["identities_sha256"],
            implementation_source_sha256=boundary["implementation_source_sha256"],
            recovery_implementation_sha256=boundary["recovery_implementation_sha256"],
            state_sha256=identity[0],
            internal_sha256=identity[1],
            ordinal=identity[2],
            gaps=identity[3],
            recovery=dict(mode="checkpoint"),
        ),
    )
    with pytest.raises(ValueError, match="after an incomplete phase"):
        validation.completed_phases(
            output, phases, json.loads((output / "catalog.json").read_text()), boundary
        )


def test_recovery_matrix_and_real_interruption_preserve_source(tmp_path):
    source = fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    catalog, _, boundary = validation.inventory(source)
    staging = tmp_path / "staging"
    staging.mkdir()
    view = staging / "view"
    view.mkdir()
    validation.write(staging / "catalog.json", catalog)
    validation.write(staging / "boundary.json", boundary)
    for info in catalog["segments"]:
        (view / info["file"]).symlink_to(source / info["file"])
    expected = None
    environment = dict(os.environ)
    candidate_packages = str(Path(recovery.__file__).resolve().parents[2])
    environment["PYTHONPATH"] = candidate_packages + os.pathsep + environment.get("PYTHONPATH", "")
    environment["MIDAS_REALITY_VALIDATION_PACKAGES"] = candidate_packages
    environment["MIDAS_REALITY_VALIDATION_SOURCE_SHA256"] = validation.reality_source_sha256(
        Path(candidate_packages)
    )
    for phase in (
        "cold",
        "fast",
        "restart",
        "corrupt",
        "stale",
        "interrupt",
        "after_interrupt",
        "interrupt_save",
        "after_interrupt_save",
    ):
        process = subprocess.run(
            [
                sys.executable,
                str(Path(validation.__file__).resolve()),
                "worker",
                "--source",
                str(view),
                "--phase",
                phase,
            ],
            capture_output=True,
            text=True,
            env=environment,
            timeout=20,
        )
        if phase in ("interrupt", "interrupt_save"):
            assert process.returncode == -9, process.stderr
            continue
        assert process.returncode == 0, process.stderr
        result = json.loads((staging / f"{phase}.json").read_text())
        if expected is None:
            expected = result["internal_sha256"]
            (staging / "valid.checkpoint").write_bytes(
                (view / recovery.CHECKPOINT_NAME).read_bytes()
            )
        assert result["internal_sha256"] == expected
        assert result["ordinal"] == result["gaps"] == 2
        if phase in ("fast", "restart", "after_interrupt_save"):
            assert result["recovery"]["segments_reconstructed"] == 0
        if phase in ("corrupt", "stale", "after_interrupt"):
            assert result["recovery"]["mode"] == "full_replay"
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}
