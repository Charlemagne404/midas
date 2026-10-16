#!/usr/bin/env python3
"""Profile the complete Reality shadow consume path on finalized source data.

The campaign plan, model artifacts, and finalized recording segments are
read-only inputs. By default, each repetition uses a fresh temporary journal.
The optional work-directory mode keeps an isolated journal and resumes from
its durable source cursor. No collector, campaign journal, network client, or
order API is opened for writing.
"""

from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
import resource
import signal
import sqlite3
import sys
import tempfile
import time
import uuid
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from midas.reality import shadow_campaign, shadow_source, shadow_store, shadow_worker, storage
from midas.reality.research_schema import digest as research_digest
from midas.reality.shadow_source import Context, Tail
from midas.reality.shadow_worker import Shadow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--runtime-snapshot", required=True, type=Path)
    parser.add_argument("--segments", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--allow-current-code", action="store_true")
    parser.add_argument("--include-research-events", action="store_true")
    parser.add_argument(
        "--work-dir",
        type=Path,
        help=(
            "Persist an isolated replay journal under data/veritas-canaries and resume it on "
            "later invocations. Existing directories must have a matching run manifest."
        ),
    )
    parser.add_argument(
        "--checkpoint-interval-seconds",
        type=float,
        default=60.0,
        help="Maximum real elapsed seconds between durable isolated replay checkpoints.",
    )
    parser.add_argument(
        "--runtime-snapshot-output",
        type=Path,
        help="Write the last repetition's read-only replay runtime for a successor window.",
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def stable_json(value: Any) -> bytes:
    """Serialize comparison data identically across frozen and branch code."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(stable_json(value)).hexdigest()


def _path_overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _canary_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "veritas-canaries"


def _resolve_isolated_path(
    requested: Path,
    *,
    allowed_root: Path,
    protected_roots: list[Path],
) -> Path:
    absolute = requested.absolute()
    for component in (absolute, *absolute.parents):
        if component.exists() and component.is_symlink():
            raise ValueError(f"Isolated replay path contains a symlink: {component}")
    resolved = absolute.resolve(strict=False)
    allowed = allowed_root.resolve(strict=False)
    if resolved == allowed or not resolved.is_relative_to(allowed):
        raise ValueError(f"Isolated replay path must be below {allowed}")
    for protected in protected_roots:
        root = protected.resolve(strict=False)
        if _path_overlaps(resolved, root):
            raise ValueError(f"Isolated replay path overlaps protected input: {root}")
    return resolved


def _write_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite isolated replay artifact: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(stable_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError(f"Refusing to replace an isolated replay symlink: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(stable_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _runtime_row(connection: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    result = connection.execute("select body,sha from runtime where key=?", (key,)).fetchone()
    if result is None:
        return None
    compressed, expected_sha = result
    if not isinstance(compressed, bytes) or not isinstance(expected_sha, str):
        raise ValueError(f"Isolated journal runtime row {key!r} is malformed")
    decompressor = zlib.decompressobj()
    decoded = decompressor.decompress(compressed, 256 * 1024**2 + 1)
    if (
        len(decoded) > 256 * 1024**2
        or not decompressor.eof
        or decompressor.unused_data
        or hashlib.sha256(decoded).hexdigest() != expected_sha
    ):
        raise ValueError(f"Isolated journal runtime row {key!r} failed its digest check")
    value = json.loads(decoded)
    if not isinstance(value, dict):
        raise ValueError(f"Isolated journal runtime row {key!r} is not an object")
    return value


def _verify_isolated_journal(
    database_path: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if database_path.is_symlink() or not database_path.is_file():
        raise ValueError("Isolated replay journal must be a regular file")
    connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("pragma query_only=on")
        if connection.execute("pragma integrity_check").fetchone() != ("ok",):
            raise ValueError("Isolated replay SQLite integrity check failed")
        prior = "0" * 64
        count = 0
        for seq, kind, occurred_ns, body, previous_sha, sha in connection.execute(
            "select seq,kind,occurred_ns,body,previous_sha,sha from events order by seq"
        ):
            if not isinstance(body, bytes):
                raise ValueError("Isolated replay journal event body is malformed")
            decoded = zlib.decompress(body)
            if (
                seq != count + 1
                or previous_sha != prior
                or research_digest([prior, kind, occurred_ns, hashlib.sha256(decoded).hexdigest()])
                != sha
            ):
                raise ValueError("Isolated replay event hash chain is invalid")
            prior = sha
            count += 1
        return _runtime_row(connection, "checkpoint"), dict(events=count, tail_sha256=prior)
    finally:
        connection.close()


def _source_cursor_evidence(raw_root: Path, runtime: dict[str, Any]) -> dict[str, Any]:
    context = runtime.get("context")
    source_clock = context.get("clock") if isinstance(context, dict) else None
    if source_clock is not None and (
        not isinstance(source_clock, (list, tuple))
        or len(source_clock) != 2
        or any(type(value) is not int for value in source_clock)
    ):
        raise ValueError("Replay runtime source clock is malformed")
    cursor = runtime.get("cursor")
    if not isinstance(cursor, dict):
        raise ValueError("Replay runtime has no source cursor")
    stem = cursor.get("segment")
    offset = cursor.get("offset")
    ordinal = cursor.get("ordinal")
    if (
        not isinstance(stem, str)
        or len(stem) != 53
        or not stem[:20].isdigit()
        or stem[20] != "-"
        or any(ch not in "0123456789abcdef" for ch in stem[21:])
        or type(offset) is not int
        or type(ordinal) is not int
        or offset < len(storage.MAGIC)
        or ordinal < 0
    ):
        raise ValueError("Replay runtime source cursor is malformed")
    if raw_root.is_symlink() or not raw_root.is_dir():
        raise ValueError("Replay source root must be a regular directory")
    segment = raw_root / f"{stem}.seg"
    catalog = raw_root / f"{stem}.json"
    if (
        segment.is_symlink()
        or catalog.is_symlink()
        or (raw_root / f"{stem}.open").exists()
        or not segment.is_file()
        or not catalog.is_file()
    ):
        raise ValueError("Replay cursor must point to a finalized regular source segment")
    info = json.loads(catalog.read_text(encoding="utf-8"))
    observed_sha = storage.file_hash(segment)
    if (
        info.get("file") != segment.name
        or info.get("bytes") != segment.stat().st_size
        or info.get("sha256") != observed_sha
        or offset > segment.stat().st_size
    ):
        raise ValueError("Replay cursor source segment disagrees with its finalized catalog")

    boundary = offset == len(storage.MAGIC) and ordinal == info.get("first", 0) - 1
    boundary_ordinal = info.get("first", 0) - 1
    if offset > len(storage.MAGIC):
        for row, end_offset in storage.records(segment):
            if end_offset > offset:
                raise ValueError("Replay cursor lies inside a source record")
            boundary_ordinal = row["ordinal"]
            if end_offset == offset:
                boundary = row["ordinal"] == ordinal
                break
    if not boundary or boundary_ordinal != ordinal:
        raise ValueError("Replay cursor offset and source ordinal are not an exact record boundary")
    return dict(
        segment=segment.name,
        segment_bytes=segment.stat().st_size,
        segment_sha256=observed_sha,
        catalog_sha256=storage.file_hash(catalog),
        offset=offset,
        ordinal=ordinal,
    )


def _module_hashes() -> dict[str, dict[str, str]]:
    modules = {
        "shadow_campaign": shadow_campaign,
        "shadow_source": shadow_source,
        "shadow_store": shadow_store,
        "shadow_worker": shadow_worker,
        "storage": storage,
    }
    hashes: dict[str, dict[str, str]] = {}
    for name, module in modules.items():
        module_file = getattr(module, "__file__", None)
        if not isinstance(module_file, str):
            raise ValueError(f"Implementation module {name} has no source file")
        module_path = Path(module_file).resolve()
        hashes[name] = {"path": str(module_path), "sha256": storage.file_hash(module_path)}
    runner = Path(__file__).resolve()
    hashes["benchmark_shadow_consume"] = {
        "path": str(runner),
        "sha256": storage.file_hash(runner),
    }
    return hashes


def process_peak_rss_bytes() -> int:
    """Read this process's peak resident set size in bytes when available."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024  # Linux reports kB here.
    except (OSError, ValueError, IndexError):
        pass
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def verify_module_roots(expected_root: Path) -> dict[str, str]:
    root = expected_root.resolve()
    paths: dict[str, str] = {}
    unexpected: list[str] = []
    for name, module in tuple(sys.modules.items()):
        if name != "midas" and not name.startswith("midas."):
            continue
        source = getattr(module, "__file__", None)
        if not source:
            continue
        path = Path(source).resolve()
        paths[name] = str(path)
        if not path.is_relative_to(root):
            unexpected.append(f"{name}: {path}")
    if unexpected:
        raise ValueError("MIDAS modules escaped selected code root: " + "; ".join(unexpected))
    return paths


def verify_current_code(plan: dict[str, Any]) -> None:
    shadow_campaign.verify(plan, check_code=False)


def read_inputs(
    campaign_path: Path, snapshot_path: Path, allow_current_code: bool
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    if sys.pycache_prefix is None:
        raise ValueError("Run with an isolated, empty PYTHONPYCACHEPREFIX")
    cache_root = Path(sys.pycache_prefix)
    if cache_root.exists() and any(cache_root.rglob("*.pyc")):
        raise ValueError("PYTHONPYCACHEPREFIX must not contain bytecode before the run")
    campaign = json.loads(campaign_path.read_text())
    snapshot = json.loads(snapshot_path.read_text())
    runtime = snapshot["runtime"]
    runtime_sha = stable_sha256(runtime)
    if snapshot.get("schema_version") != 1 or snapshot.get("runtime_sha256") != runtime_sha:
        raise ValueError("Runtime snapshot digest mismatch")
    persisted_runtime = snapshot.get("persisted_runtime_json")
    persisted_runtime_sha = snapshot.get("persisted_runtime_sha256")
    if not isinstance(persisted_runtime, str) or not isinstance(persisted_runtime_sha, str):
        raise ValueError("Snapshot lacks the original persisted runtime bytes and digest")
    persisted_bytes = persisted_runtime.encode("utf-8")
    if hashlib.sha256(persisted_bytes).hexdigest() != persisted_runtime_sha:
        raise ValueError("Persisted runtime source digest mismatch")
    if json.loads(persisted_bytes) != runtime:
        raise ValueError("Persisted runtime source does not match snapshot runtime")
    if snapshot.get("campaign_id") != campaign["campaign_id"]:
        raise ValueError("Runtime snapshot campaign identity mismatch")
    if runtime.get("campaign_id") != campaign["campaign_id"]:
        raise ValueError("Runtime checkpoint campaign identity mismatch")

    shadow_campaign.verify(campaign, check_code=not allow_current_code)
    if allow_current_code:
        expected_root = Path(__file__).resolve().parents[1] / "packages" / "midas"
        pinned_code = campaign_path.parent / "code" / "midas"
        for relative, expected in campaign["identity"]["code"].items():
            if storage.file_hash(pinned_code / relative) != expected:
                raise ValueError(f"Pinned campaign code mismatch: {relative}")
        # Keep all campaign identity and measurement checks, while permitting
        # the explicitly selected branch implementation under comparison.
        shadow_worker.__dict__["verify"] = verify_current_code
    else:
        expected_root = campaign_path.parent / "code" / "midas"
    verify_module_roots(expected_root)

    return campaign, runtime, runtime_sha, persisted_runtime_sha


def normalized_research_digest(db: Any) -> tuple[str, int, list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    decision_index: dict[str, int] = {}
    for kind, body in db.execute(
        "select kind,body from events where kind in ('decision','decision_committed','followup') order by seq"
    ):
        row = json.loads(zlib.decompress(body))
        if kind == "decision":
            decision_index[row.pop("id")] = len(decision_index)
        elif kind == "decision_committed":
            row["decision_id"] = decision_index.get(row.get("decision_id"), -1)
        elif kind == "followup":
            row["decision_id"] = decision_index.get(row.get("decision_id"), -1)
        normalized.append({"kind": kind, "row": row})
    return stable_sha256(normalized), len(normalized), normalized


def normalized_resumable_research_digest(db: Any) -> tuple[str, int, list[dict[str, Any]]]:
    """Hash research semantics without process-local journal sequence numbers."""
    source_rows = list(
        db.execute(
            "select seq,kind,body from events "
            "where kind in ('decision','decision_committed','followup') order by seq"
        )
    )
    decision_index: dict[str, int] = {}
    event_index: dict[int, int] = {}
    decision_count = 0
    for seq, kind, body in source_rows:
        if kind == "decision":
            row = json.loads(zlib.decompress(body))
            decision_index[row["id"]] = decision_count
            event_index[seq] = decision_count
            decision_count += 1

    normalized: list[dict[str, Any]] = []
    for _, kind, body in source_rows:
        row = json.loads(zlib.decompress(body))
        if kind == "decision":
            row.pop("id", None)
        elif kind == "decision_committed":
            row["decision_id"] = decision_index.get(row.get("decision_id"), -1)
            row["decision_event_seq"] = event_index.get(row.get("decision_event_seq"), -1)
        elif kind == "followup":
            row["decision_id"] = decision_index.get(row.get("decision_id"), -1)
        normalized.append({"kind": kind, "row": row})
    return stable_sha256(normalized), len(normalized), normalized


class ResumableShadow(Shadow):
    """Shadow worker whose replay-only clock state shares its runtime checkpoint."""

    def __init__(self, root: Path, plan: dict[str, Any], benchmark_state: dict[str, Any]) -> None:
        # The runner and worker share this mapping so every durable runtime
        # checkpoint includes the same replay counters and synthetic clock.
        self.benchmark_state = benchmark_state
        self._record_runtime_override: dict[str, Any] | None = None
        super().__init__(root, plan)

    def runtime(self) -> dict[str, Any]:
        if self._record_runtime_override is not None:
            return copy.deepcopy(self._record_runtime_override)
        value = super().runtime()
        value["resumable_benchmark"] = {
            **self.benchmark_state,
            "last_clock": list(self.last_clock) if self.last_clock else None,
        }
        return value


def _recover_uncommitted_decisions(worker: ResumableShadow, replay_clock_ns: int) -> int:
    """Finish the journal's second decision transaction after a crash window."""
    pending = list(
        worker.journal.db.execute(
            "select event_seq,id from decisions where commit_ns=0 order by event_seq"
        )
    )
    for event_seq, decision_id in pending:
        row = worker.journal.event(event_seq)
        # In replay mode the synthetic time at the cursor can precede the
        # decision that was committed just before interruption. Use its
        # recorded decision clock as the lower bound so no earlier source row
        # can become a forward label for that decision.
        committed_ns = max(replay_clock_ns, int(row["decision_ns"]))
        with worker.journal.db:
            worker.journal.append(
                "decision_committed",
                dict(
                    decision_id=decision_id,
                    decision_event_seq=event_seq,
                    committed_ns=committed_ns,
                ),
                committed_ns,
            )
            worker.journal.db.execute(
                "update decisions set commit_ns=? where id=? and commit_ns=0",
                (committed_ns, decision_id),
            )
    if pending:
        for item in worker.pending:
            commit = worker.journal.db.execute(
                "select commit_ns from decisions where id=?", (item["row"]["id"],)
            ).fetchone()
            if commit is not None:
                item["committed_ns"] = commit[0]
    return len(pending)


def _work_identity(
    campaign_path: Path,
    runtime_snapshot_path: Path,
    campaign: dict[str, Any],
    runtime: dict[str, Any],
    runtime_sha: str,
    persisted_runtime_sha: str,
    *,
    allow_current_code: bool,
) -> dict[str, Any]:
    identity = campaign["identity"]
    campaign_bytes = campaign_path.read_bytes()
    return dict(
        schema_version=1,
        experiment="veritas-shadow-consume-resumable-v1",
        campaign_id=campaign["campaign_id"],
        campaign_file_sha256=hashlib.sha256(campaign_bytes).hexdigest(),
        campaign_identity_sha256=stable_sha256(identity),
        runtime_snapshot_file_sha256=storage.file_hash(runtime_snapshot_path),
        runtime_snapshot_sha256=runtime_sha,
        persisted_runtime_sha256=persisted_runtime_sha,
        initial_cursor_evidence=_source_cursor_evidence(Path(identity["raw_root"]), runtime),
        source_root=str(Path(identity["raw_root"]).resolve()),
        implementation_hashes=_module_hashes(),
        implementation_mode="current_checkout" if allow_current_code else "campaign_pinned",
        implementation_code_hashes_checked_against_campaign=not allow_current_code,
    )


def _seed_replay_journal(
    work_dir: Path,
    campaign: dict[str, Any],
    runtime: dict[str, Any],
) -> None:
    identity = campaign["identity"]
    initial = copy.deepcopy(runtime)
    initial["resumable_benchmark"] = dict(
        schema_version=1,
        records_processed=0,
        frames_processed=0,
        last_clock=None,
    )
    journal = shadow_store.Journal(
        work_dir,
        budget=identity["evidence_budget_bytes"],
        reserve=identity["reserve_bytes"],
    )
    try:
        with journal.db:
            journal.save_runtime(initial)
    finally:
        journal.close()


def _open_replay_workdir(
    requested: Path,
    *,
    campaign_path: Path,
    runtime_snapshot_path: Path,
    campaign: dict[str, Any],
    runtime: dict[str, Any],
    runtime_sha: str,
    persisted_runtime_sha: str,
    allow_current_code: bool,
    allowed_root: Path | None = None,
) -> tuple[Path, int, dict[str, Any], dict[str, Any], dict[str, Any]]:
    canary_root = allowed_root or _canary_root()
    identity = campaign["identity"]
    work_dir = _resolve_isolated_path(
        requested,
        allowed_root=canary_root,
        protected_roots=[
            campaign_path.parent,
            Path(identity["raw_root"]),
            Path(identity["training_root"]),
        ],
    )
    work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if work_dir.is_symlink() or not work_dir.is_dir():
        raise ValueError("Replay work directory must be a regular directory")
    if work_dir.stat().st_mode & 0o077:
        raise ValueError("Replay work directory must be private to its owner")
    lock_path = work_dir / ".run.lock"
    if lock_path.is_symlink():
        raise ValueError("Replay work lock cannot be a symlink")
    lock_fd = os.open(
        lock_path,
        os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise RuntimeError("Another isolated replay process owns this work directory") from None

    try:
        identity_record = _work_identity(
            campaign_path,
            runtime_snapshot_path,
            campaign,
            runtime,
            runtime_sha,
            persisted_runtime_sha,
            allow_current_code=allow_current_code,
        )
        manifest_path = work_dir / "work-manifest.json"
        manifest = {"identity": identity_record, "identity_sha256": stable_sha256(identity_record)}
        if manifest_path.exists() or manifest_path.is_symlink():
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise ValueError("Replay work manifest must be a regular file")
            stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            stored_identity = stored_manifest.get("identity")
            if (
                not isinstance(stored_identity, dict)
                or stored_manifest.get("identity_sha256") != stable_sha256(stored_identity)
                or stored_identity != identity_record
            ):
                raise ValueError("Replay work directory identity changed; refusing resume")
        else:
            unexpected = [path.name for path in work_dir.iterdir() if path.name != lock_path.name]
            if unexpected:
                raise ValueError(
                    "Refusing to initialize a nonempty replay directory without a manifest"
                )
            _write_once(manifest_path, manifest)

        journal_path = work_dir / "shadow.sqlite"
        if journal_path.is_symlink():
            raise ValueError("Replay SQLite journal cannot be a symlink")
        if not journal_path.exists():
            _seed_replay_journal(work_dir, campaign, runtime)

        current_runtime, chain = _verify_isolated_journal(journal_path)
        if current_runtime is None:
            if chain["events"] != 0:
                raise ValueError("Replay journal has events but no runtime checkpoint")
            _seed_replay_journal(work_dir, campaign, runtime)
            current_runtime, chain = _verify_isolated_journal(journal_path)
        if current_runtime is None or current_runtime.get("campaign_id") != campaign["campaign_id"]:
            raise ValueError("Replay runtime belongs to another campaign")
        benchmark_state = current_runtime.get("resumable_benchmark")
        if (
            not isinstance(benchmark_state, dict)
            or benchmark_state.get("schema_version") != 1
            or type(benchmark_state.get("records_processed")) is not int
            or type(benchmark_state.get("frames_processed")) is not int
            or benchmark_state["records_processed"] < 0
            or not 0 <= benchmark_state["frames_processed"] <= benchmark_state["records_processed"]
        ):
            raise ValueError("Replay journal has no valid resumable benchmark checkpoint")
        last_clock = benchmark_state.get("last_clock")
        if last_clock is not None and (
            not isinstance(last_clock, list)
            or len(last_clock) != 2
            or any(type(value) is not int for value in last_clock)
        ):
            raise ValueError("Replay journal benchmark clock is malformed")
        _source_cursor_evidence(Path(identity["raw_root"]), current_runtime)
        return work_dir, lock_fd, current_runtime, benchmark_state, chain
    except BaseException:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        raise


def _commit_replay_checkpoint(
    worker: ResumableShadow,
    seals: list[dict[str, Any]],
) -> None:
    worker.journal.check_capacity()
    worker.counters["source_checkpoints"] = worker.ctx.checkpoints
    aliases = worker.ctx.families.identities()
    with worker.journal.db:
        for seal in seals:
            worker.journal.append("source_segment_sealed", seal)
        worker.journal.db.executemany(
            "insert or replace into family_map values(?,?)",
            [
                (key.removeprefix("condition:"), value)
                for key, value in aliases.items()
                if key.startswith("condition:")
            ],
        )
        # Cursor, context, benchmark clock, family map, and segment-seal events
        # become durable in one SQLite transaction.
        worker.journal.save_runtime(worker.runtime())
    worker.tail.seals.clear()
    worker.save()


def run_resumable_once(
    campaign: dict[str, Any],
    runtime: dict[str, Any],
    runtime_sha: str,
    persisted_runtime_sha: str,
    *,
    campaign_path: Path,
    runtime_snapshot_path: Path,
    work_dir: Path,
    segment_target: int,
    checkpoint_interval_seconds: float,
    allow_current_code: bool,
    include_research_events: bool,
    include_final_runtime: bool,
    should_stop: Callable[[], bool] = lambda: False,
    allowed_root: Path | None = None,
) -> dict[str, Any]:
    if segment_target <= 0:
        raise ValueError("Resumable replay segment target must be positive")
    if not math.isfinite(checkpoint_interval_seconds) or checkpoint_interval_seconds <= 0:
        raise ValueError("Checkpoint interval must be finite and positive")
    work_dir, lock_fd, current_runtime, benchmark_state, prior_chain = _open_replay_workdir(
        work_dir,
        campaign_path=campaign_path,
        runtime_snapshot_path=runtime_snapshot_path,
        campaign=campaign,
        runtime=runtime,
        runtime_sha=runtime_sha,
        persisted_runtime_sha=persisted_runtime_sha,
        allow_current_code=allow_current_code,
        allowed_root=allowed_root,
    )
    lock_held = True

    def release_lock() -> None:
        nonlocal lock_held
        if lock_held:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            lock_held = False

    real_time_ns = time.time_ns
    real_monotonic = time.monotonic
    real_monotonic_ns = time.monotonic_ns
    source_clock = current_runtime.get("context", {}).get("clock")
    last_clock = benchmark_state.get("last_clock")
    starting_clock = last_clock or source_clock
    wall_now = [int(starting_clock[0]) if starting_clock else 0]
    mono_now = [int(starting_clock[1]) if starting_clock else 0]
    time.time_ns = lambda: wall_now[0]
    time.monotonic = lambda: mono_now[0] / 10**9
    time.monotonic_ns = lambda: mono_now[0]

    original_verify = shadow_worker.__dict__["verify"]
    if allow_current_code:
        shadow_worker.__dict__["verify"] = verify_current_code

    worker: ResumableShadow | None = None
    first_ordinal: int | None = None
    last_ordinal: int | None = None
    records = frames = 0
    sealed = 0
    termination = "segment_bound"
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    last_checkpoint_at = wall_start
    start_cursor = copy.deepcopy(current_runtime["cursor"])
    recovered_uncommitted_decisions = 0
    processing_failed = False
    try:
        worker = ResumableShadow(work_dir, campaign, benchmark_state)
        verify_module_roots(Path(shadow_worker.__file__).resolve().parents[1])
        # The replay clock may begin at zero in fixture tapes. Force the first
        # tail directory scan instead of letting Tail's 500 ms throttle treat
        # its zero-valued initial check as recent.
        worker.tail.checked = -1.0
        worker.status = "WARMING_OR_LAGGED_SOURCE"
        worker.last_clock = tuple(last_clock) if last_clock else None
        worker.last_save = time.monotonic()
        recovered_uncommitted_decisions = _recover_uncommitted_decisions(worker, wall_now[0])
        while len(worker.tail.verified_seals) < segment_target:
            if should_stop():
                termination = "interrupted_checkpointed"
                break
            before_record = worker.runtime()
            item = worker.tail.next()
            if item is None:
                termination = "source_exhausted_or_waiting_for_seal"
                break
            row, ref = item
            segment_path = Path(campaign["identity"]["raw_root"]) / ref["segment"]
            if (
                not segment_path.is_file()
                or segment_path.is_symlink()
                or segment_path.with_suffix(".open").exists()
            ):
                raise ValueError("Replay advanced into a non-finalized or unsafe source segment")
            first_ordinal = first_ordinal if first_ordinal is not None else row["ordinal"]
            last_ordinal = row["ordinal"]
            records += 1
            frames += row["kind"] == "frame"
            benchmark_state["records_processed"] += 1
            benchmark_state["frames_processed"] += row["kind"] == "frame"
            wall_now[0] = row["received_ns"] + 1_000_000
            mono_now[0] = row["monotonic_ns"] + 1_000_000
            # Journal.decision() writes a runtime snapshot as part of its own
            # transaction. Keep that intermediate snapshot at the previous
            # record boundary; all effects from this record are idempotent if
            # it must be replayed after a process interruption.
            worker._record_runtime_override = before_record
            try:
                worker.consume(row, ref)
            finally:
                worker._record_runtime_override = None
            benchmark_state["last_clock"] = (
                list(worker.last_clock) if worker.last_clock else [wall_now[0], mono_now[0]]
            )
            new_seals = list(worker.tail.seals)
            sealed += len(new_seals)
            finished_bound = len(worker.tail.verified_seals) >= segment_target
            elapsed_checkpoint = time.perf_counter() - last_checkpoint_at
            if new_seals or finished_bound or elapsed_checkpoint >= checkpoint_interval_seconds:
                _commit_replay_checkpoint(worker, new_seals)
                last_checkpoint_at = time.perf_counter()
            if should_stop():
                termination = "interrupted_checkpointed"
                _commit_replay_checkpoint(worker, [])
                break

        assert worker is not None
        _commit_replay_checkpoint(worker, list(worker.tail.seals))
        if should_stop():
            termination = "interrupted_checkpointed"
        cpu_seconds = time.process_time() - cpu_start
        wall_seconds = time.perf_counter() - wall_start
        summary = worker.journal.summary()
        research_sha, research_events, research_rows = normalized_resumable_research_digest(
            worker.journal.db
        )
        context_sha = stable_sha256(worker.ctx.snapshot())
        end_runtime = worker.runtime()
        result = {
            "campaign_id": campaign["campaign_id"],
            "work_directory": str(work_dir),
            "run_termination": termination,
            "starting_cursor": start_cursor,
            "ending_cursor": worker.tail.cursor,
            "first_ordinal": first_ordinal,
            "last_ordinal": last_ordinal,
            "records_this_invocation": records,
            "frames_this_invocation": frames,
            "sealed_segments_verified_this_invocation": len(worker.tail.verified_seals),
            "segments_sealed_this_invocation": sealed,
            "records_processed_total": benchmark_state["records_processed"],
            "frames_processed_total": benchmark_state["frames_processed"],
            "engine_state_sha256": worker.ctx.engine.digest(),
            "context_state_sha256": context_sha,
            "decision_count": summary["decisions"],
            "observation_count": summary["observations"],
            "followup_status_counts": summary["followups"],
            "research_event_count": research_events,
            "research_semantics_sha256": research_sha,
            "journal_event_count": worker.journal.summary()["events"],
            "recovered_uncommitted_decisions": recovered_uncommitted_decisions,
            "cpu_seconds": cpu_seconds,
            "wall_seconds": wall_seconds,
            "max_rss_bytes_process": process_peak_rss_bytes(),
            "previous_journal_verification": prior_chain,
        }
        if include_research_events:
            result["research_semantics_rows"] = research_rows
        if include_final_runtime:
            result["_final_runtime"] = end_runtime
    except BaseException:
        processing_failed = True
        raise
    finally:
        try:
            if worker is not None:
                worker.tail.close()
                worker.journal.close()
        except BaseException:
            release_lock()
            raise
        finally:
            time.time_ns = real_time_ns
            time.monotonic = real_monotonic
            time.monotonic_ns = real_monotonic_ns
            shadow_worker.__dict__["verify"] = original_verify
            if processing_failed:
                release_lock()

    try:
        _, final_chain = _verify_isolated_journal(work_dir / "shadow.sqlite")
        result["final_journal_verification"] = final_chain
        _atomic_json(
            work_dir / "run-status.json",
            {
                "schema_version": 1,
                "campaign_id": campaign["campaign_id"],
                "updated_at_ns": time.time_ns(),
                "status": termination,
                "cursor": result["ending_cursor"],
                "records_processed_total": result["records_processed_total"],
                "frames_processed_total": result["frames_processed_total"],
                "journal": final_chain,
            },
        )
        return result
    finally:
        release_lock()


def run_once(
    campaign: dict[str, Any],
    runtime: dict[str, Any],
    runtime_sha: str,
    segment_target: int,
    include_research_events: bool,
    include_final_runtime: bool,
) -> dict[str, Any]:
    identity = campaign["identity"]
    raw_root = Path(identity["raw_root"])
    cursor = copy.deepcopy(runtime["cursor"])
    stem = cursor["segment"]
    if not stem:
        raise ValueError("Runtime cursor has no finalized source segment")
    sealed_path = raw_root / f"{stem}.seg"
    if (
        not sealed_path.is_file()
        or sealed_path.is_symlink()
        or (raw_root / f"{stem}.open").exists()
    ):
        raise ValueError("Benchmark cursor must point into a finalized regular segment")

    prior_clock = runtime.get("context", {}).get("clock")
    wall_now = [int(prior_clock[0]) if prior_clock else 0]
    mono_now = [int(prior_clock[1]) if prior_clock else 0]
    real_time_ns = time.time_ns
    real_monotonic = time.monotonic
    real_monotonic_ns = time.monotonic_ns
    time.time_ns = lambda: wall_now[0]
    # Shadow.save() and Tail.refresh() use the float monotonic API. Keep those
    # cadence checks on the same recorded clock as the nanosecond API; using
    # the host clock makes a faster implementation save less often and can
    # change the provenance histories emitted into decisions.
    time.monotonic = lambda: mono_now[0] / 10**9
    time.monotonic_ns = lambda: mono_now[0]
    try:
        with tempfile.TemporaryDirectory(prefix="veritas-shadow-consume-") as temp_dir:
            worker = Shadow(Path(temp_dir), campaign)
            verify_module_roots(Path(shadow_worker.__file__).resolve().parents[1])
            worker.ctx = Context.restore(copy.deepcopy(runtime["context"]))
            shadow_worker._restore_context_cohort_order(
                worker.ctx,
                raw_root,
                runtime.get("cohort_order"),
            )
            worker.tail.close()
            worker.tail = Tail(raw_root, cursor)
            worker.next_decision = copy.deepcopy(runtime["next_decision"])
            worker.next_observation = copy.deepcopy(runtime["next_observation"])
            worker.counters = copy.deepcopy(runtime["counters"])
            worker.pending = worker.journal.pending(identity["horizons_ms"])
            worker.status = "WARMING_OR_LAGGED_SOURCE"
            worker.last_clock = None
            worker.last_save = time.monotonic()

            first_ordinal: int | None = None
            last_ordinal: int | None = None
            records = frames = 0
            cpu_start = time.process_time()
            wall_start = time.perf_counter()
            try:
                while len(worker.tail.verified_seals) < segment_target:
                    item = worker.tail.next()
                    if item is None:
                        raise ValueError("Finalized source ended before the segment bound")
                    row, ref = item
                    segment_path = raw_root / ref["segment"]
                    if not segment_path.is_file() or segment_path.is_symlink():
                        raise ValueError("Tail returned a non-finalized or unsafe source segment")
                    first_ordinal = first_ordinal if first_ordinal is not None else row["ordinal"]
                    last_ordinal = row["ordinal"]
                    records += 1
                    frames += row["kind"] == "frame"
                    wall_now[0] = row["received_ns"] + 1_000_000
                    mono_now[0] = row["monotonic_ns"] + 1_000_000
                    worker.consume(row, ref)
                    for seal in worker.tail.seals:
                        with worker.journal.db:
                            worker.journal.append("source_segment_sealed", seal)
                    worker.tail.seals.clear()
                    if time.monotonic() - worker.last_save >= 5:
                        aliases = worker.ctx.families.identities()
                        with worker.journal.db:
                            worker.journal.db.executemany(
                                "insert or replace into family_map values(?,?)",
                                [
                                    (key.removeprefix("condition:"), value)
                                    for key, value in aliases.items()
                                    if key.startswith("condition:")
                                ],
                            )
                        totals = worker.journal.summary()
                        if (
                            totals["decisions"] >= identity["max_decisions"]
                            or totals["observations"] >= identity["max_observations"]
                        ):
                            raise ValueError(
                                "Frozen evidence-row limit reached in temporary journal"
                            )
                        worker.save()
                        worker.last_save = time.monotonic()
                worker.save()
                cpu_seconds = time.process_time() - cpu_start
                wall_seconds = time.perf_counter() - wall_start
                summary = worker.journal.summary()
                research_sha, research_events, research_rows = normalized_research_digest(
                    worker.journal.db
                )
                context_sha = stable_sha256(worker.ctx.snapshot())
                result = {
                    "runtime_snapshot_sha256": runtime_sha,
                    "start_cursor": runtime["cursor"],
                    "first_ordinal": first_ordinal,
                    "last_ordinal": last_ordinal,
                    "records": records,
                    "frames": frames,
                    "sealed_segments_verified": len(worker.tail.verified_seals),
                    "engine_state_sha256": worker.ctx.engine.digest(),
                    "context_state_sha256": context_sha,
                    "decision_count": summary["decisions"],
                    "observation_count": summary["observations"],
                    "followup_status_counts": summary["followups"],
                    "research_event_count": research_events,
                    "research_semantics_sha256": research_sha,
                    "source_ordinal_end": worker.tail.cursor["ordinal"],
                    "cpu_seconds": cpu_seconds,
                    "wall_seconds": wall_seconds,
                    "max_rss_bytes_process": process_peak_rss_bytes(),
                }
                if include_research_events:
                    result["research_semantics_rows"] = research_rows
                if include_final_runtime:
                    result["_final_runtime"] = worker.runtime()
                return result
            finally:
                worker.tail.close()
                worker.journal.close()
    finally:
        time.time_ns = real_time_ns
        time.monotonic = real_monotonic
        time.monotonic_ns = real_monotonic_ns


def main() -> None:
    args = parse_args()
    if args.segments <= 0 or args.repetitions <= 0:
        raise SystemExit("--segments and --repetitions must be positive")
    if args.work_dir is not None and args.repetitions != 1:
        raise SystemExit("--repetitions must be 1 when using resumable --work-dir mode")
    campaign, runtime, runtime_sha, persisted_runtime_sha = read_inputs(
        args.campaign, args.runtime_snapshot, args.allow_current_code
    )

    if args.work_dir is not None:
        canary_root = _canary_root()
        protected_roots = [
            args.campaign.parent,
            Path(campaign["identity"]["raw_root"]),
            Path(campaign["identity"]["training_root"]),
        ]
        work_dir = _resolve_isolated_path(
            args.work_dir,
            allowed_root=canary_root,
            protected_roots=protected_roots,
        )
        output_path = _resolve_isolated_path(
            args.output,
            allowed_root=work_dir,
            protected_roots=protected_roots,
        )
        reserved_names = {
            ".run.lock",
            "work-manifest.json",
            "shadow.sqlite",
            "shadow.sqlite-wal",
            "shadow.sqlite-shm",
            "status.json",
            "run-status.json",
        }
        if output_path.parent == work_dir and output_path.name in reserved_names:
            raise ValueError("Replay output path collides with an internal work artifact")
        if output_path.exists():
            raise FileExistsError(f"Refusing to overwrite replay result: {output_path}")
        snapshot_path: Path | None = None
        if args.runtime_snapshot_output is not None:
            snapshot_path = _resolve_isolated_path(
                args.runtime_snapshot_output,
                allowed_root=canary_root,
                protected_roots=protected_roots,
            )
            if snapshot_path.exists():
                raise FileExistsError(f"Refusing to overwrite runtime snapshot: {snapshot_path}")
            if snapshot_path.parent == work_dir and snapshot_path.name in reserved_names:
                raise ValueError("Runtime snapshot path collides with an internal work artifact")
            if snapshot_path == output_path:
                raise ValueError("Result and runtime snapshot must use separate artifact paths")

        stop_requested = False

        def request_stop(_signum: int, _frame: Any) -> None:
            nonlocal stop_requested
            stop_requested = True

        old_handlers = {
            signum: signal.signal(signum, request_stop)
            for signum in (signal.SIGTERM, signal.SIGINT)
        }
        try:
            results = [
                run_resumable_once(
                    campaign,
                    runtime,
                    runtime_sha,
                    persisted_runtime_sha,
                    campaign_path=args.campaign,
                    runtime_snapshot_path=args.runtime_snapshot,
                    work_dir=work_dir,
                    segment_target=args.segments,
                    checkpoint_interval_seconds=args.checkpoint_interval_seconds,
                    allow_current_code=args.allow_current_code,
                    include_research_events=args.include_research_events,
                    include_final_runtime=args.runtime_snapshot_output is not None,
                    should_stop=lambda: stop_requested,
                    allowed_root=canary_root,
                )
            ]
        finally:
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
    else:
        results = [
            run_once(
                campaign,
                runtime,
                runtime_sha,
                args.segments,
                args.include_research_events,
                args.runtime_snapshot_output is not None,
            )
            for _ in range(args.repetitions)
        ]
        output_path = args.output

    if args.runtime_snapshot_output is not None:
        runtime_output = results[-1].pop("_final_runtime")
        persisted_runtime = storage.canonical(runtime_output)
        # Canonical JSON stringifies integer mapping keys. Hash the same
        # normalized object that a later JSON reader will restore.
        snapshot_runtime = json.loads(persisted_runtime)
        snapshot = {
            "schema_version": 1,
            "campaign_id": campaign["campaign_id"],
            "runtime": snapshot_runtime,
            "runtime_sha256": stable_sha256(snapshot_runtime),
            "persisted_runtime_json": persisted_runtime.decode("utf-8"),
            "persisted_runtime_sha256": hashlib.sha256(persisted_runtime).hexdigest(),
        }
        if args.work_dir is not None:
            assert snapshot_path is not None
            _write_once(snapshot_path, snapshot)
        else:
            args.runtime_snapshot_output.parent.mkdir(parents=True, exist_ok=True)
            args.runtime_snapshot_output.write_bytes(stable_json(snapshot))
    output = {
        "schema_version": 1,
        "implementation_module": str(Path(shadow_worker.__file__).resolve()),
        "implementation_modules": {
            "shadow_campaign": str(Path(shadow_campaign.__file__).resolve()),
            "shadow_source": str(Path(shadow_source.__file__).resolve()),
            "shadow_store": str(Path(shadow_store.__file__).resolve()),
            "shadow_worker": str(Path(shadow_worker.__file__).resolve()),
            "storage": str(Path(storage.__file__).resolve()),
        },
        "python_bytecode_cache_prefix": sys.pycache_prefix,
        "implementation_code_hashes_checked_against_campaign": not args.allow_current_code,
        "pinned_campaign_code_verified": True,
        "campaign_id": campaign["campaign_id"],
        "campaign_identity_sha256": stable_sha256(campaign["identity"]),
        "runtime_snapshot_sha256": runtime_sha,
        "persisted_runtime_sha256": persisted_runtime_sha,
        "segment_target": args.segments,
        "repetitions": results,
    }
    if args.work_dir is not None:
        _write_once(output_path, output)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(stable_json(output))
    printable = copy.deepcopy(output)
    for repetition in printable["repetitions"]:
        repetition.pop("research_semantics_rows", None)
    print(json.dumps(printable, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
