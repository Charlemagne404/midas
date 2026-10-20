"""Disposable archive accelerators, actual process death, and source isolation."""

import json
import signal
import subprocess
import sys
from pathlib import Path

import pytest
from midas.reality import recovery, storage
from midas.reality.reconstruction import Engine
from midas.reality.replay import replay
from midas.reality.storage import Store, manifest, read_manifest

FIXTURE = json.loads((Path(__file__).parent / "fixtures/reality/observed.json").read_text())


def archive(root):
    store = Store(root, reserve=1)
    engine = Engine()
    for original in [FIXTURE["discovery"], *FIXTURE["frames"]]:
        fields = {
            k: v
            for k, v in original.items()
            if k not in {"kind", "payload", "ordinal", "schema_version"}
        }
        engine.consume(store.append(original["kind"], original["payload"], **fields))
    engine.consume(store.append("checkpoint", dict(state_sha256=engine.digest())))
    store.close()
    return engine, manifest(root)


def test_accelerator_skips_prefix_decode_but_hashes_every_segment(tmp_path, monkeypatch):
    expected, catalog = archive(tmp_path)
    recovery.save(tmp_path, expected, catalog)
    checked = []
    original = recovery.file_hash

    def check(path):
        checked.append(path.name)
        return original(path)

    monkeypatch.setattr(recovery, "file_hash", check)
    monkeypatch.setattr(storage, "_record_stream", lambda *a, **k: pytest.fail("prefix decoded"))
    actual, status = recovery.recover(tmp_path, catalog)
    assert actual.__dict__ == expected.__dict__
    assert checked == [s["file"] for s in catalog["segments"]]
    assert status["mode"] == "checkpoint_and_verified_tail"
    assert status["segments_reconstructed"] == 0


def test_checkpoint_tail_replay_and_repeated_restart(tmp_path):
    expected, catalog = archive(tmp_path)
    recovery.save(tmp_path, expected, catalog)
    store = Store(tmp_path, reserve=1)
    expected.consume(store.append("gap", dict(reason="fixture_interruption")))
    expected.consume(store.append("frame", FIXTURE["frames"][0]["payload"]))
    expected.consume(store.append("checkpoint", dict(state_sha256=expected.digest())))
    store.close()
    complete = manifest(tmp_path)
    actual, status = recovery.recover(tmp_path, complete)
    full, _ = replay(tmp_path, complete)
    assert actual.__dict__ == expected.__dict__ == full.__dict__
    assert status["segments_reconstructed"] == 1
    recovery.save(tmp_path, actual, complete)
    again, status = recovery.recover(tmp_path, complete)
    assert again.__dict__ == actual.__dict__
    assert status["segments_reconstructed"] == 0


@pytest.mark.parametrize(
    "fault", ["truncated", "checksum", "implementation", "prefix", "oversized"]
)
def test_bad_checkpoint_falls_back_without_mutating_archive(tmp_path, monkeypatch, fault):
    expected, catalog = archive(tmp_path)
    recovery.save(tmp_path, expected, catalog)
    path = tmp_path / recovery.CHECKPOINT_NAME
    if fault == "truncated":
        path.write_bytes(b"short")
    elif fault == "checksum":
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
    elif fault == "implementation":
        monkeypatch.setattr(recovery, "implementation_identity", lambda: "changed")
    elif fault == "prefix":
        # A checkpoint copied from a different source/catalog must not be accepted.
        path2 = tmp_path / "other"
        engine2, catalog2 = archive(path2)
        recovery.save(path2, engine2, catalog2)
        path.write_bytes((path2 / recovery.CHECKPOINT_NAME).read_bytes())
    else:
        with path.open("r+b") as f:
            f.truncate(recovery.MAX_CHECKPOINT_BYTES + 1)
    before = {p.name: p.read_bytes() for p in tmp_path.glob("*.seg")}
    actual, status = recovery.recover(tmp_path, catalog)
    assert status["mode"] == "full_replay" and status["fallback_reason"]
    assert actual.__dict__ == expected.__dict__
    assert before == {p.name: p.read_bytes() for p in tmp_path.glob("*.seg")}


def test_source_corruption_never_hidden_by_checkpoint(tmp_path):
    engine, catalog = archive(tmp_path)
    recovery.save(tmp_path, engine, catalog)
    segment = tmp_path / catalog["segments"][0]["file"]
    data = bytearray(segment.read_bytes())
    data[-1] ^= 1
    segment.write_bytes(data)
    with pytest.raises(ValueError, match="source checksum mismatch"):
        recovery.recover(tmp_path, catalog)


def test_failed_checkpoint_replace_keeps_previous_valid_snapshot(tmp_path, monkeypatch):
    engine, catalog = archive(tmp_path)
    recovery.save(tmp_path, engine, catalog)
    before = (tmp_path / recovery.CHECKPOINT_NAME).read_bytes()

    def fail(*args):
        raise OSError("injected checkpoint replacement failure")

    monkeypatch.setattr(recovery.os, "replace", fail)
    with pytest.raises(OSError):
        recovery.save(tmp_path, engine, catalog)
    assert (tmp_path / recovery.CHECKPOINT_NAME).read_bytes() == before
    assert not (tmp_path / "recovery-v1.tmp").exists()
    actual, _ = recovery.recover(tmp_path, catalog)
    assert actual.digest() == engine.digest()


def test_real_sigkill_preserves_fsynced_records_and_quarantines_tail(tmp_path):
    script = """
import os, signal, sys
from pathlib import Path
from midas.reality.storage import Store
s = Store(Path(sys.argv[1]), reserve=1)
s.append("gap", {"reason":"kill_fixture"})
s.file.write(b"incomplete")
s.file.flush()
os.fsync(s.file.fileno())
os.kill(os.getpid(), signal.SIGKILL)
"""
    child = subprocess.run([sys.executable, "-c", script, str(tmp_path)], check=False)
    assert child.returncode == -signal.SIGKILL
    resumed = Store(tmp_path, reserve=1)
    assert resumed.ordinal == 1 and resumed.counts["gap"] == 1
    assert list(tmp_path.glob("*.tail"))[0].read_bytes() == b"incomplete"
    resumed.append("gap", dict(reason="recovered_interruption"))
    resumed.close()
    repeated = Store(tmp_path, reserve=1)
    assert repeated.ordinal == 2 and repeated.counts["gap"] == 2
    repeated.close()
    assert len(list(read_manifest(tmp_path, manifest(tmp_path)))) == 2


def test_interrupted_finalization_rebuilds_missing_sidecar(tmp_path):
    engine, catalog = archive(tmp_path)
    segment = tmp_path / catalog["segments"][0]["file"]
    before = segment.read_bytes()
    segment.with_suffix(".json").unlink()
    store = Store(tmp_path, reserve=1)
    assert store.ordinal == engine.last_ordinal
    store.close()
    assert segment.read_bytes() == before
    full, _ = replay(tmp_path, manifest(tmp_path))
    assert full.digest() == engine.digest()


def test_independent_source_roots_contain_storage_failure(tmp_path):
    one = Store(tmp_path / "one", reserve=1, budget=100)
    two = Store(tmp_path / "two", reserve=1)
    with pytest.raises(OSError):
        one.append("gap", dict(reason="capacity"))
    two.append("gap", dict(reason="independent_source_fixture"))
    one.close()
    two.close()
    assert len(list(read_manifest(tmp_path / "two", manifest(tmp_path / "two")))) == 1


def test_manifest_ordinal_overlap_rejected_before_writer_activation(tmp_path):
    _, catalog = archive(tmp_path)
    path = tmp_path / catalog["segments"][0]["file"]
    sidecar = path.with_suffix(".json")
    info = json.loads(sidecar.read_text())
    info["first"] += 1
    sidecar.write_text(json.dumps(info))
    with pytest.raises(ValueError):
        Store(tmp_path, reserve=1, verify_existing=False, defer_open=True)


def test_frame_metadata_does_not_retain_full_depth():
    from midas.reality.collector import frame_metadata

    normalized, constraints, invalid = frame_metadata(FIXTURE["frames"][0]["payload"])
    assert not invalid and normalized
    assert all(
        set(v) == {"event_type", "asset_id", "market", "exchange_timestamp"} for v in normalized
    )
    assert all(set(v) == {"asset_id", "tick_size"} for v in constraints)


async def test_http_response_bound_closes_stream_and_preserves_observed_prefix():
    import base64

    import httpx
    from midas.reality.transport import bounded_get

    class Body(httpx.AsyncByteStream):
        closed = False
        emitted = 0

        async def __aiter__(self):
            for _ in range(20):
                self.emitted += 1
                yield b"x" * 65536

        async def aclose(self):
            self.closed = True

    body = Body()
    saved = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=body))
    ) as client:
        with pytest.raises(httpx.HTTPError):
            await bounded_get(
                client,
                "https://fixture.invalid/feed",
                limit=65536,
                append=lambda kind, payload: saved.append((kind, payload)),
            )
    assert body.closed and body.emitted == 2
    assert saved[0][0] == "http_response_limit"
    evidence = saved[0][1]
    assert evidence["reason"] == "http_response_limit"
    assert base64.b64decode(evidence["observed_wire_prefix_base64"]) == b"x" * 131072


async def test_http_compressed_response_rejected_before_decoding():
    import httpx
    from midas.reality.transport import bounded_get

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b"not-decoded")
            )
        )
    ) as client:
        with pytest.raises(httpx.HTTPError):
            await bounded_get(client, "https://fixture.invalid/feed")


def test_resynchronizing_health_is_explicit_even_with_old_fresh_observations():
    from midas.reality.collector import collection_health

    assert collection_health("AWAITING_DATA", 95, 6, 6, 100, 10) == "resynchronizing"


def test_tail_collision_preserves_both_recovery_artifacts(tmp_path):
    path = tmp_path / "00000000000000000001-header.open"
    path.write_bytes(storage.MAGIC[:3])
    original_tail = path.with_suffix(".tail")
    original_tail.write_bytes(b"prior-evidence")
    store = Store(tmp_path, reserve=1)
    store.close()
    assert original_tail.read_bytes() == b"prior-evidence"
    assert sorted(p.read_bytes() for p in tmp_path.glob("*.tail")) == [
        storage.MAGIC[:3],
        b"prior-evidence",
    ]


def test_auto_rotate_failure_poisoned_writer_does_not_append_again(tmp_path, monkeypatch):
    store = Store(tmp_path, reserve=1, segment_bytes=1)

    def fail(*args, **kwargs):
        raise OSError("injected finalize failure")

    monkeypatch.setattr(store, "rotate", fail)
    with pytest.raises(OSError):
        store.append("gap", dict(reason="fixture"))
    assert store.ordinal == 1 and store.write_failed
    with pytest.raises(OSError, match="previously failed"):
        store.append("gap", dict(reason="must_not_write"))
    store.close()
    restored = Store(tmp_path, reserve=1)
    assert restored.ordinal == 1
    restored.close()


async def test_trickling_http_response_has_total_deadline():
    import asyncio

    import httpx
    from midas.reality.transport import bounded_get

    class Body(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            while True:
                await asyncio.sleep(0.01)
                yield b"x"

        async def aclose(self):
            self.closed = True

    body = Body()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, stream=body))
    ) as client:
        with pytest.raises(httpx.ReadTimeout, match="total request deadline"):
            await bounded_get(client, "https://fixture.invalid/feed", timeout=0.03)
    assert body.closed


@pytest.mark.parametrize("margin, accepted", [(4194303, False), (4194304, True)])
def test_resource_gate_preserves_four_mib_boundary(monkeypatch, margin, accepted):
    from midas.reality import resources

    value = dict(
        memory_high_margin_bytes=margin,
        host_mem_available_bytes=4 * 1024**3,
        host_pressure={
            "cpu": {"some": {"avg10": "0"}},
            "memory": {"some": {"avg10": "0"}},
            "io": {"full": {"avg10": "0"}},
        },
    )
    monkeypatch.setattr(resources, "snapshot", lambda group: value)
    if accepted:
        assert resources.require_safe("fixture") is value
    else:
        with pytest.raises(ValueError, match="4 MiB"):
            resources.require_safe("fixture")


def test_real_kill_before_checkpoint_replace_preserves_prior_checkpoint(tmp_path):
    engine, catalog = archive(tmp_path)
    recovery.save(tmp_path, engine, catalog)
    before = (tmp_path / recovery.CHECKPOINT_NAME).read_bytes()
    code = """
import os, signal, sys
from pathlib import Path
from midas.reality import recovery
from midas.reality.replay import replay
from midas.reality.storage import manifest
root=Path(sys.argv[1]); catalog=manifest(root)
engine,_=replay(root,catalog)
recovery.os.replace=lambda *a: os.kill(os.getpid(),signal.SIGKILL)
recovery.save(root,engine,catalog)
"""
    child = subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=False)
    assert child.returncode == -signal.SIGKILL
    assert (tmp_path / recovery.CHECKPOINT_NAME).read_bytes() == before
    actual, status = recovery.recover(tmp_path, catalog)
    assert actual.__dict__ == engine.__dict__
    assert status["mode"] == "checkpoint_and_verified_tail"


def test_recovery_capsule_builder_only_writes_disposable_output(tmp_path, monkeypatch):
    from scripts import reality_recovery_snapshot as tool

    source, output = tmp_path / "source", tmp_path / "capsule"
    engine, catalog = archive(source)
    before = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    monkeypatch.setattr(tool, "admission", lambda: {"fixture": True})
    monkeypatch.setattr(
        sys, "argv", ["snapshot", "--snapshot", str(source), "--output", str(output)]
    )
    tool.main()
    assert before == {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    (source / recovery.CHECKPOINT_NAME).write_bytes(
        (output / recovery.CHECKPOINT_NAME).read_bytes()
    )
    actual, status = recovery.recover(source, catalog)
    assert status["segments_reconstructed"] == 0 and actual.__dict__ == engine.__dict__


def test_tail_directory_synced_before_original_is_truncated(tmp_path, monkeypatch):
    store = Store(tmp_path, reserve=1)
    store.append("gap", dict(reason="fixture"))
    path = store.path
    store.file.write(b"partial")
    store.file.flush()
    store.file.close()
    store.file = None
    store.lock.close()
    original_size = path.stat().st_size
    barriers = []
    original_sync = storage.sync_dir

    def barrier(root):
        if path.exists() and list(tmp_path.glob("*.tail")):
            barriers.append(path.stat().st_size)
        original_sync(root)

    monkeypatch.setattr(storage, "sync_dir", barrier)
    recovered = Store(tmp_path, reserve=1)
    recovered.close()
    assert barriers[0] == original_size


def test_split_frame_write_is_identical_to_existing_wire_format(tmp_path):
    import hashlib
    import struct
    import zlib

    store = Store(tmp_path, reserve=1)
    record = store.append("gap", dict(reason="wire_fixture"), received_ns=123, monotonic_ns=456)
    path = store.path
    store.close()
    compressed = zlib.compress(storage.canonical(record), 3)
    expected = (
        storage.MAGIC
        + struct.pack(">I32s", len(compressed), hashlib.sha256(compressed).digest())
        + compressed
    )
    assert path.with_suffix(".seg").read_bytes() == expected


def test_paused_record_reader_releases_compression_and_json_scratch(tmp_path):
    import base64
    import random
    import tracemalloc

    payload = base64.b64encode(random.Random(7).randbytes(1024**2)).decode()
    store = Store(tmp_path, reserve=1)
    store.append("fixture", payload)
    path = store.path.with_suffix(".seg")
    store.close()
    iterator = storage.records(path)
    tracemalloc.start()
    try:
        record, _ = next(iterator)
        retained, _ = tracemalloc.get_traced_memory()
        assert record["payload"] == payload
        # One decoded payload plus bounded framing/JSON metadata may remain.
        # Holding compressed bytes AND the raw JSON bytes exceeds this bound.
        assert retained < 2 * len(payload)
    finally:
        iterator.close()
        tracemalloc.stop()


def test_staging_monitor_failure_terminates_only_disposable_builder(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    archive(source)
    before = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    code = """
import subprocess, sys, time
from scripts import reality_recovery_snapshot as tool
calls=0
def admission():
 global calls
 calls+=1
 if calls>1: raise subprocess.CalledProcessError(1, "fixture-systemctl")
 return {"recorder_pid":123}
tool.admission=admission
tool.replay=lambda *args: time.sleep(15)
sys.argv=["builder","--snapshot",sys.argv[1],"--output",sys.argv[2]]
tool.main()
"""
    child = subprocess.run(
        [sys.executable, "-c", code, str(source), str(output)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert child.returncode == -signal.SIGTERM
    assert "Staging resource guard abort" in child.stderr
    assert before == {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    assert not output.exists()
