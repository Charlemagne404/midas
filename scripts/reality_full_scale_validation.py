"""Read-only inventory and guarded, sequential recovery validation of Reality.

Run with candidate packages on PYTHONPATH. `inventory` reads only sidecars/stat;
it DOES NOT certify segment bytes. `run` requires sustained production headroom,
then places each worker in its own sandbox/cgroup. No production service actions.
Workers read immutable finalized source files through Landlock and write only to
independent staging state.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from midas.reality import recovery
from midas.reality.reconstruction import _canonical_chunks
from midas.reality.resources import snapshot
from midas.reality.storage import Store, _validate_manifest_metadata, canonical, manifest, records
from reality_readonly_sandbox import apply_readonly_source_policy, verify_source_write_denied
from reality_staging_admission import (
    PROTECTED_DISK_RESERVE_BYTES,
    STAGING_EXTRA_BYTES,
    validate_staging_admission,
)

STAGING_OUTPUT_ROOT = Path("/mnt/continental-cloud/data/midas-reality-staging")
STAGING_VOLUME_RESERVE_BYTES = 400 * 1024**3
STAGING_CPU_QUOTA_PERCENT = 15
STAGING_CPU_WEIGHT = 10


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def allowed_staging_path(path):
    return path.is_relative_to(Path("/tmp")) or path.is_relative_to(STAGING_OUTPUT_ROOT)


def inventory(source):
    """Pin exactly the sidecars listed at entry; fail on any broken boundary."""
    started = datetime.now(UTC).isoformat()
    sidecars = sorted(p for p in source.glob("*.json") if p.name[0].isdigit())
    segments, identities, kinds = [], [], Counter()
    previous = 0
    for sidecar in sidecars:
        raw = sidecar.read_bytes()
        info = json.loads(raw)
        if Path(info["file"]).name != info["file"] or not info["file"].endswith(".seg"):
            raise ValueError("Unsafe segment identity")
        path = source / info["file"]
        if sidecar != path.with_suffix(".json") or path.is_symlink() or sidecar.is_symlink():
            raise ValueError("Source must contain regular finalized files and sidecars")
        _validate_manifest_metadata(path, info)
        if info["count"]:
            if info["first"] != previous + 1:
                raise ValueError("Non-contiguous catalog")
            previous = info["last"]
        stat = path.stat()
        identities.append(dict(file=path.name, device=stat.st_dev, inode=stat.st_ino,
                               size=stat.st_size, mtime_ns=stat.st_mtime_ns,
                               sidecar_sha256=hashlib.sha256(raw).hexdigest()))
        segments.append(info)
        kinds.update(info["kinds"])
    if not segments:
        raise ValueError("Empty snapshot")
    catalog = dict(schema_version=1, format="midas-reality-framed-zlib-v1",
                   ordering="durable ordinal then frame array index", segments=segments)
    known = {i["file"] for i in segments}
    unmatched = sorted(p.name for p in source.glob("*.seg") if p.name not in known)
    # A rename can precede sidecar publication. Do not silently omit an interior file.
    if any(int(n.split("-", 1)[0]) <= previous for n in unmatched):
        raise ValueError("Finalized segment without sidecar inside pinned prefix")
    summary = dict(started_at=started, completed_at=datetime.now(UTC).isoformat(),
                   source=str(source), segment_count=len(segments), last_ordinal=previous,
                   archive_bytes=sum(i["bytes"] for i in segments), kinds=dict(kinds),
                   empty_segments=sum(i["count"] == 0 for i in segments),
                   catalog_sha256=hashlib.sha256(canonical(catalog)).hexdigest(),
                   identities_sha256=hashlib.sha256(canonical(identities)).hexdigest(),
                   last_segment=segments[-1], unmatched_finalized=unmatched,
                   excluded_open=[dict(file=p.name, observed_bytes=p.stat().st_size)
                                  for p in sorted(source.glob("*.open"))],
                   checkpoint_present=(source / recovery.CHECKPOINT_NAME).exists(),
                   scope="metadata only; content checksums NOT yet verified")
    return catalog, identities, summary


def admission(baseline_events=None):
    unit = subprocess.check_output(["systemctl", "--user", "show", "midas-reality.service",
                                    "-p", "MainPID", "-p", "ControlGroup"], text=True)
    values = dict(line.split("=", 1) for line in unit.splitlines())
    if int(values["MainPID"]) <= 0:
        raise ValueError("Protected recorder is unavailable")
    control_group = values["ControlGroup"]
    group = Path("/sys/fs/cgroup") / control_group.lstrip("/")
    sample = snapshot(control_group)
    max_text = (group / "memory.max").read_text().strip()
    memory_max = int(max_text) if max_text != "max" else None
    sample["memory_max_bytes"] = memory_max
    sample["memory_max_margin_bytes"] = (
        memory_max - sample["memory_current_bytes"] if memory_max is not None else None
    )
    sample["protected_cpu_stat"] = (group / "cpu.stat").read_text()
    io_stat = group / "io.stat"
    sample["protected_io_stat"] = io_stat.read_text() if io_stat.exists() else None
    validate_staging_admission(sample, baseline_events)
    return dict(pid=values["MainPID"], control_group=control_group, **sample)


def cgroup_metrics():
    relative = Path("/proc/self/cgroup").read_text().strip().split("::", 1)[1]
    group = Path("/sys/fs/cgroup") / relative.lstrip("/")
    return {name: (group / name).read_text() if (group / name).exists() else None for name in
            ("memory.current", "memory.peak", "memory.stat", "memory.events",
             "cpu.stat", "io.stat", "cpu.pressure", "memory.pressure", "io.pressure")}


def endurance(root, engine, catalog, seconds):
    """Two captured frames/second, isolated durable writes; no source subscriptions."""
    if seconds != 3600:
        raise ValueError("Endurance duration must be 3600 seconds")
    payloads = []
    for info in reversed(catalog["segments"]):
        for record, _ in records(root / info["file"]):
            if record["kind"] == "frame":
                payloads.append(record["payload"])
                if len(payloads) == 16:
                    break
        if len(payloads) == 16:
            break
    if not payloads:
        raise ValueError("No captured frames for replay")
    budget = sum(s["bytes"] for s in catalog["segments"]) + 128 * 1024**2
    store = Store(root, budget=budget, reserve=20 * 1024**3,
                  segment_bytes=8 * 1024**2, segment_seconds=3600,
                  verify_existing=False, defer_open=True)
    store.activate()
    engine.consume(store.append("gap", dict(reason="isolated_controlled_replay_start")))
    started, last_checkpoint, last_report = time.monotonic(), 0, 0
    frames, maximum_latency = 0, 0.0
    try:
        while time.monotonic() - started < seconds:
            before = time.monotonic()
            engine.consume(store.append("frame", payloads[frames % len(payloads)]))
            maximum_latency = max(maximum_latency, time.monotonic() - before)
            frames += 1
            elapsed = time.monotonic() - started
            if elapsed - last_checkpoint >= 60:
                engine.consume(store.append("checkpoint", dict(state_sha256=engine.digest())))
                store.rotate()
                recovery.save(root, engine, manifest(root))
                last_checkpoint = elapsed
            if elapsed - last_report >= 300:
                with (root.parent / "endurance-samples.jsonl").open("a") as out:
                    out.write(json.dumps(dict(at=datetime.now(UTC).isoformat(), elapsed=elapsed,
                              frames=frames, max_append_seconds=maximum_latency,
                              gc_counts=gc.get_count(), gc_stats=gc.get_stats(),
                              cgroup=cgroup_metrics())) + "\n")
                last_report = elapsed
            time.sleep(max(0, 0.5 - (time.monotonic() - before)))
        engine.consume(store.append("gap", dict(reason="isolated_controlled_replay_stop")))
        engine.consume(store.append("checkpoint", dict(state_sha256=engine.digest())))
    finally:
        store.close()
    complete = manifest(root)
    recovery.save(root, engine, complete)
    again, restored = recovery.recover(root, complete)
    if again.__dict__ != engine.__dict__:
        raise ValueError("Endurance clean restart changed internal state")
    write(root.parent / "endurance.json", dict(seconds=time.monotonic() - started, frames=frames,
          max_append_seconds=maximum_latency, restart=restored, ordinal=engine.last_ordinal,
          state_sha256=engine.digest(), cgroup=cgroup_metrics(),
          scope="captured raw payload replay; synchronous persistence; no network/reconnection test"))


def worker(root, phase):
    """Only called inside the staging unit; artifacts are under disposable root."""
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024**2, 64 * 1024**2))
    catalog = json.loads((root.parent / "catalog.json").read_text())
    boundary = json.loads((root.parent / "boundary.json").read_text())
    sandbox = apply_readonly_source_policy(Path(boundary["source"]), root.parent)
    source_file = root / catalog["segments"][0]["file"]
    verify_source_write_denied(source_file)
    write(root.parent / f"{phase}-landlock.json", sandbox)
    if phase == "readonly_probe":
        write(root.parent / "readonly_probe.json", dict(
            denied_source_file=str(source_file), source_sha256=catalog["segments"][0]["sha256"],
            policy=sandbox,
        ))
        return
    checkpoint = root / recovery.CHECKPOINT_NAME
    if checkpoint.is_symlink():
        raise ValueError("Checkpoint must be independent writable staging state")
    if phase in ("cold", "interrupt", "after_interrupt"):
        checkpoint.unlink(missing_ok=True)
    elif phase == "corrupt":
        checkpoint.write_bytes(b"intentionally invalid isolated checkpoint")
    elif phase == "stale":
        # Valid framing/checksum, incompatible reconstruction identity.
        data = json.loads((root.parent / "valid.checkpoint").read_bytes()[recovery.HEADER.size:])
        data["implementation"] = "stale-isolated-implementation"
        payload = canonical(data)
        checkpoint.write_bytes(recovery.HEADER.pack(recovery.MAGIC,
                               hashlib.sha256(payload).digest()) + payload)
    elif phase == "after_interrupt_save":
        if checkpoint.read_bytes() != (root.parent / "valid.checkpoint").read_bytes():
            raise ValueError("Interrupted save changed previously durable checkpoint")
    if phase == "interrupt":
        from midas.reality.reconstruction import Engine
        consume = Engine.consume

        def interrupted(self, record):
            consume(self, record)
            if self.last_ordinal >= 2:
                os.kill(os.getpid(), signal.SIGKILL)

        Engine.consume = interrupted
    started = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    base_memory = Path("/proc/self/smaps_rollup").read_text()
    base_gc = gc.get_stats()
    engine, status = recovery.recover(root, catalog)
    recovered_seconds = time.monotonic() - started
    if phase == "endurance":
        endurance(root, engine, catalog, 3600)
        return
    if engine.last_ordinal != sum(s["count"] for s in catalog["segments"]):
        raise ValueError("Record accounting mismatch")
    if engine.gaps != sum(s["kinds"].get("gap", 0) for s in catalog["segments"]):
        raise ValueError("Gap accounting mismatch")
    internal = hashlib.sha256()
    for chunk in _canonical_chunks(recovery._snapshot(engine)):
        internal.update(chunk)
    if phase == "interrupt_save":
        # Kill at atomic publication after tmp fsync. Existing checkpoint must survive.
        recovery.os.replace = lambda *a: os.kill(os.getpid(), signal.SIGKILL)
    save_started = time.monotonic()
    size = recovery.save(root, engine, catalog)
    after = resource.getrusage(resource.RUSAGE_SELF)
    result = dict(phase=phase, recovery=status, recovery_seconds=recovered_seconds,
                  save_seconds=time.monotonic() - save_started, checkpoint_bytes=size,
                  wall_seconds=time.monotonic() - started,
                  cpu_seconds=after.ru_utime + after.ru_stime - usage.ru_utime - usage.ru_stime,
                  peak_rss_kib=after.ru_maxrss, ordinal=engine.last_ordinal, gaps=engine.gaps,
                  counts=dict(engine.counts), state_sha256=engine.digest(),
                  internal_sha256=internal.hexdigest(), sequence_verified=False,
                  readiness_scope="reconstruction and checkpoint save; no collector/network start",
                  base_memory=base_memory, final_memory=Path("/proc/self/smaps_rollup").read_text(),
                  cgroup=cgroup_metrics(), gc_before=base_gc, gc_after=gc.get_stats(),
                  process_io=Path("/proc/self/io").read_text())
    write(root.parent / f"{phase}.json", result)


def run(source, output, with_endurance=False):
    # Mandatory gate is evaluated before staging setup or expensive I/O.
    initial = admission()
    for _ in range(12):
        time.sleep(5)
        if admission(initial["memory_events"])["pid"] != initial["pid"]:
            raise ValueError("Protected recorder identity changed")
    catalog, identities, summary = inventory(source)
    reserve = (
        STAGING_VOLUME_RESERVE_BYTES
        if output.is_relative_to(STAGING_OUTPUT_ROOT)
        else PROTECTED_DISK_RESERVE_BYTES
    )
    if shutil.disk_usage(output.parent).free < reserve + STAGING_EXTRA_BYTES:
        raise ValueError("Need the staging-volume reserve and 1 GiB staging allowance")
    output.mkdir(mode=0o700, exist_ok=False)
    write(output / "catalog.json", catalog)
    write(output / "identities.json", identities)
    write(output / "boundary.json", summary)
    root = output / "view"
    root.mkdir()
    # Reuse finalized source bytes without copying. Worker Landlock rules allow
    # reads across the filesystem and mutations only below this run-owned root.
    for info in catalog["segments"]:
        (root / info["file"]).symlink_to(source / info["file"])
        write((root / info["file"]).with_suffix(".json"), info)
    write(output / "admission.json", initial)
    write(output / "staging-policy.json", dict(
        memory_high_bytes=640 * 1024**2,
        memory_max_bytes=768 * 1024**2,
        memory_swap_max_bytes=0,
        cpu_quota_percent=STAGING_CPU_QUOTA_PERCENT,
        cpu_weight=STAGING_CPU_WEIGHT,
        nice=19,
        io_scheduling_class="idle",
        runtime_max_seconds=4200,
        output_max_bytes=256 * 1024**2,
        source_policy="Landlock read-only across /; writes allowed only below this output root",
    ))
    phases = ("readonly_probe", "cold", "fast", "restart", "corrupt", "stale", "interrupt",
              "after_interrupt", "interrupt_save", "after_interrupt_save")
    if with_endurance:
        phases += ("endurance",)
    expected = None
    for phase in phases:
        admission(initial["memory_events"])
        name = "midas-validation-" + uuid.uuid4().hex[:12]
        command = ["systemd-run", "--user", "--wait", "--pipe", "--unit=" + name,
                   "-p", "MemoryHigh=640M", "-p", "MemoryMax=768M", "-p", "MemorySwapMax=0",
                   "-p", f"CPUQuota={STAGING_CPU_QUOTA_PERCENT}%",
                   "-p", f"CPUWeight={STAGING_CPU_WEIGHT}", "-p", "Nice=19",
                   "-p", "IOSchedulingClass=idle",
                   "-p", "TasksMax=16", "-p", "RuntimeMaxSec=4200", "-p", "TimeoutStopSec=5",
                   "-p", "ProtectSystem=strict", "-p", "ProtectHome=read-only",
                   "-p", "ReadWritePaths=" + str(output), "-p", "PrivateNetwork=yes",
                   "-p", "NoNewPrivileges=yes", "-p", "LimitCORE=0",
                   "-p", "IOAccounting=yes", "-p", "RestrictAddressFamilies=AF_UNIX",
                   "--setenv=PYTHONDONTWRITEBYTECODE=1",
                   "--setenv=PYTHONPATH=" + os.environ["PYTHONPATH"],
                   sys.executable, str(Path(__file__).resolve()), "worker",
                   "--source", str(root), "--phase", phase]
        with (output / f"{phase}.log").open("w") as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            try:
                with (output / f"{phase}-monitor.jsonl").open("w") as monitor:
                    while child.poll() is None:
                        sample = admission(initial["memory_events"])
                        if sample["pid"] != initial["pid"]:
                            raise ValueError("Protected recorder changed")
                        owned = subprocess.check_output(["systemctl", "--user", "show", name,
                                  "-p", "ControlGroup", "-p", "MemoryPeak", "-p", "CPUUsageNSec",
                                  "-p", "IOReadBytes", "-p", "IOWriteBytes"], text=True)
                        cg = dict(line.split("=", 1) for line in owned.splitlines())["ControlGroup"]
                        details = {}
                        if cg:
                            for filename in ("memory.current", "memory.peak", "memory.stat",
                                             "memory.events", "cpu.stat", "io.stat",
                                             "cpu.pressure", "memory.pressure", "io.pressure"):
                                path = Path("/sys/fs/cgroup") / cg.lstrip("/") / filename
                                if path.exists():
                                    details[filename] = path.read_text()
                        monitor.write(json.dumps(dict(at=datetime.now(UTC).isoformat(),
                                      protected=sample, worker=owned, cgroup=details)) + "\n")
                        monitor.flush()
                        if shutil.disk_usage(output).free < reserve:
                            raise ValueError("Staging filesystem fell below its reserved free space")
                        time.sleep(5)
                child.wait()
            except BaseException:
                # The random owned unit is the ONLY unit this tool may stop.
                subprocess.run(["systemctl", "--user", "stop", name], check=False)
                child.wait(timeout=15)
                raise
        killed = phase in ("interrupt", "interrupt_save")
        if killed:
            status = subprocess.check_output(["systemctl", "--user", "show", name,
                                              "-p", "ExecMainCode", "-p", "ExecMainStatus"], text=True)
            write(output / f"{phase}-termination.json", dict(systemd=status))
            if "ExecMainCode=2\n" not in status or "ExecMainStatus=9\n" not in status:
                raise ValueError("Expected isolated SIGKILL did not occur")
            continue
        if child.returncode:
            raise ValueError(f"Worker failed: {phase}; inspect retained log")
        if phase in ("readonly_probe", "endurance"):
            continue
        result = json.loads((output / f"{phase}.json").read_text())
        identity = [result[k] for k in ("state_sha256", "internal_sha256", "ordinal", "gaps")]
        if expected is None:
            expected = identity
            shutil.copyfile(root / recovery.CHECKPOINT_NAME, output / "valid.checkpoint")
        if identity != expected:
            raise ValueError(f"Reconstruction differs: {phase}")
        fast = phase in ("fast", "restart", "after_interrupt_save")
        if fast and result["recovery"]["segments_reconstructed"] != 0:
            raise ValueError("Checkpoint did not eliminate prefix reconstruction")
        if fast and result["recovery"]["prefix_bytes_hashed"] != summary["archive_bytes"]:
            raise ValueError("Checkpoint did not verify all source bytes")
        if phase in ("corrupt", "stale", "after_interrupt") and result["recovery"]["mode"] != "full_replay":
            raise ValueError("Expected verified full replay fallback")
    staged_bytes = sum(p.stat().st_size for p in output.rglob("*")
                       if p.is_file() and not p.is_symlink())
    if staged_bytes > 256 * 1024**2:
        raise ValueError("Independent staging exceeds the 256 MiB bound")
    # Retained checkpoint must be the one surviving interrupted publication.
    final_catalog, final_identities, _ = inventory(source)
    if (final_catalog["segments"][:len(catalog["segments"])] != catalog["segments"]
            or final_identities[:len(identities)] != identities):
        raise ValueError("Source prefix changed")
    write(output / "result.json", dict(recovery_matrix="PASSED", boundary=summary,
           collector_readiness="UNTESTED", endurance="PASSED" if with_endurance else "UNTESTED",
           deployment="NOT PERFORMED"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "run", "worker"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--phase")
    parser.add_argument("--with-endurance", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    if args.command == "inventory":
        _, _, summary = inventory(source)
        write(args.output, summary)
    elif args.command == "worker":
        if not allowed_staging_path(source) or source.name != "view":
            raise ValueError("Worker view must be under an approved disposable staging root")
        worker(source, args.phase)
    else:
        output = args.output.resolve()
        if not allowed_staging_path(output) or output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Use a new output root under an approved staging location")
        run(source, output, args.with_endurance)


if __name__ == "__main__":
    main()
