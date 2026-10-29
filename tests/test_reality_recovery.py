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
from midas.reality.storage import Store, manifest

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
    assert actual.digest() == expected.digest()
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
    assert actual.digest() == expected.digest() == full.digest()
    assert status["segments_reconstructed"] == 1
    recovery.save(tmp_path, actual, complete)
    again, status = recovery.recover(tmp_path, complete)
    assert again.digest() == actual.digest()
    assert status["segments_reconstructed"] == 0


def test_new_empty_segment_before_checkpoint_prefix_keeps_accelerator(tmp_path, monkeypatch):
    expected, catalog = archive(tmp_path)
    legacy_identity = next(iter(recovery.COMPATIBLE_IMPLEMENTATIONS))
    with monkeypatch.context() as scoped:
        scoped.setattr(recovery, "implementation_identity", lambda: legacy_identity)
        recovery.save(tmp_path, expected, catalog)

    empty = tmp_path / "00000000000000000001-00000000000000000000000000000000.seg"
    empty.write_bytes(storage.MAGIC)
    storage.atomic_json(empty.with_suffix(".json"), storage.describe(empty))
    current = manifest(tmp_path)
    assert current["segments"][0]["file"] == empty.name
    assert current["segments"][0]["count"] == 0

    prefix_files = {segment["file"] for segment in catalog["segments"]}
    hashed = []
    original_hash = recovery.file_hash

    def track_hash(path):
        hashed.append(path.name)
        return original_hash(path)

    original_stream = storage._record_stream

    def reject_checkpoint_decode(source, path, *args, **kwargs):
        if path.name in prefix_files:
            pytest.fail("checkpoint prefix must be hashed without decoding")
        return original_stream(source, path, *args, **kwargs)

    monkeypatch.setattr(recovery, "file_hash", track_hash)
    monkeypatch.setattr(storage, "_record_stream", reject_checkpoint_decode)
    actual, status = recovery.recover(tmp_path, current)

    assert actual.digest() == expected.digest()
    assert status["mode"] == "checkpoint_and_verified_tail"
    assert status["fallback_reason"] is None
    assert status["prefix_segments_hashed"] == len(catalog["segments"])
    assert hashed == [segment["file"] for segment in catalog["segments"]]
    assert status["segments_reconstructed"] == 1
    assert status["reconstructed_bytes"] == current["segments"][0]["bytes"]


def test_checkpoint_match_rejects_new_nonempty_segment_before_prefix():
    saved = [{"file": "saved.seg", "count": 1}]
    current = [{"file": "new-before.seg", "count": 1}, saved[0]]
    with pytest.raises(ValueError, match="inserted records before the checkpoint prefix"):
        recovery._match_checkpoint_prefix(current, saved)


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
    assert actual.digest() == expected.digest()
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
    assert actual.digest() == engine.digest()
    assert status["mode"] == "checkpoint_and_verified_tail"
