"""Arena job support for deterministic Frontier paired replays over pinned local inputs."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, TypeAdapter, model_validator

from midas.arena.artifacts import atomic_bytes
from midas.core.models import Model
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import BookSnapshot, FrontierMarket, FrontierModel
from midas.frontier.relationships import Relationship
from midas.frontier.replay import PairedReplayComparison, ReplayResult, paired_deterministic_replay

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_STORE_BYTES = 128 * 1024 * 1024
MAX_SNAPSHOT_COUNT = 1000
MAX_RESULT_BYTES = 8 * 1024 * 1024


class FrontierReplayJobSpec(Model):
    """References only an immutable, content-addressed input snapshot under Arena."""

    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FrontierReplaySnapshot(FrontierModel):
    schema_version: Literal[1] = 1
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_version: str = Field(min_length=1, max_length=240)
    as_of_utc: datetime
    relationship_limit: int = Field(ge=1, le=500)
    scenarios: tuple[ExecutionScenario, ExecutionScenario]
    markets: tuple[FrontierMarket, ...] = Field(max_length=100)
    books: tuple[BookSnapshot, ...] = Field(max_length=200)
    verified_relationships: tuple[Relationship, ...] = Field(max_length=500)

    @model_validator(mode="after")
    def snapshot_is_pinned_and_bounded(self) -> FrontierReplaySnapshot:
        if self.as_of_utc.tzinfo is None or self.as_of_utc.utcoffset() is None:
            raise ValueError("Frontier Arena replay timestamp must include a timezone")
        if self.scenarios[0].name == self.scenarios[1].name:
            raise ValueError("Frontier Arena replay scenarios must have unique names")
        payload = self.model_dump(mode="json", exclude={"snapshot_id"})
        if _sha256_json(payload) != self.snapshot_id:
            raise ValueError("Frontier Arena replay snapshot identity does not match its inputs")
        return self


class FrontierReplayJobArtifact(FrontierModel):
    schema_version: Literal[1] = 1
    job_id: str = Field(pattern=r"^job-[a-f0-9]{24}$")
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    comparison: PairedReplayComparison
    replays: tuple[ReplayResult, ReplayResult]
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def result_is_pinned(self) -> FrontierReplayJobArtifact:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() is None:
            raise ValueError("Frontier Arena result time must include a timezone")
        if tuple(arm.run_id for arm in self.comparison.arms) != tuple(
            replay.run_id for replay in self.replays
        ):
            raise ValueError("Frontier Arena replay arms do not match the comparison")
        if tuple(arm.result_sha256 for arm in self.comparison.arms) != tuple(
            replay.result_sha256 for replay in self.replays
        ):
            raise ValueError("Frontier Arena replay result hashes do not match the comparison")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if _sha256_json(payload) != self.result_sha256:
            raise ValueError("Frontier Arena replay result hash does not match its payload")
        return self


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def make_snapshot(
    *,
    code_version: str,
    as_of_utc: datetime,
    relationship_limit: int,
    scenarios: tuple[ExecutionScenario, ExecutionScenario],
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    verified_relationships: tuple[Relationship, ...],
) -> FrontierReplaySnapshot:
    data = {
        "schema_version": 1,
        "code_version": code_version,
        "as_of_utc": TypeAdapter(datetime).dump_python(as_of_utc.astimezone(UTC), mode="json"),
        "relationship_limit": relationship_limit,
        "scenarios": [item.model_dump(mode="json") for item in scenarios],
        "markets": [item.model_dump(mode="json") for item in markets],
        "books": [item.model_dump(mode="json") for item in books],
        "verified_relationships": [item.model_dump(mode="json") for item in verified_relationships],
    }
    snapshot_id = _sha256_json(data)
    return FrontierReplaySnapshot.model_validate({"snapshot_id": snapshot_id, **data})


def _snapshot_directory(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("Arena root cannot be a symlink")
    directory = root / "frontier-replay-snapshots"
    if directory.is_symlink():
        raise ValueError("Frontier replay snapshot directory cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store_snapshot(root: Path, snapshot: FrontierReplaySnapshot) -> str:
    directory = _snapshot_directory(root)
    path = directory / f"{snapshot.snapshot_id}.json"
    if path.is_symlink():
        raise ValueError("Frontier replay snapshot cannot be a symlink")
    encoded = _canonical_json(snapshot.model_dump(mode="json"))
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Frontier replay snapshot exceeds the 8 MiB artifact bound")
    if path.exists():
        current = path.read_bytes()
        if current != encoded:
            raise ValueError("Content-addressed Frontier replay snapshot changed")
        return hashlib.sha256(current).hexdigest()

    total_bytes = 0
    count = 0
    for index, item in enumerate(directory.glob("*.json")):
        if index >= MAX_SNAPSHOT_COUNT:
            raise ValueError("Frontier replay snapshot inventory exceeds its scan bound")
        if item.is_symlink() or not item.is_file():
            raise ValueError("Frontier replay snapshot inventory contains an unsafe entry")
        count += 1
        total_bytes += item.stat().st_size
    if count >= MAX_SNAPSHOT_COUNT or total_bytes + len(encoded) > MAX_SNAPSHOT_STORE_BYTES:
        raise ValueError("Frontier replay snapshot store budget is exhausted")
    atomic_bytes(path, encoded)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_snapshot(root: Path, spec: FrontierReplayJobSpec) -> FrontierReplaySnapshot:
    directory = root / "frontier-replay-snapshots"
    path = directory / f"{spec.snapshot_id}.json"
    if (
        root.is_symlink()
        or directory.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_SNAPSHOT_BYTES
    ):
        raise ValueError("Pinned Frontier replay snapshot is unavailable or unsafe")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != spec.snapshot_sha256:
        raise ValueError("Pinned Frontier replay snapshot file hash does not match the job")
    try:
        snapshot = FrontierReplaySnapshot.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Pinned Frontier replay snapshot is invalid") from error
    if snapshot.snapshot_id != spec.snapshot_id:
        raise ValueError("Pinned Frontier replay snapshot identity does not match the job")
    return snapshot


def execute_frontier_replay_job(
    root: Path,
    job_id: str,
    spec: FrontierReplayJobSpec,
    progress: Any,
) -> FrontierReplayJobArtifact:
    if not re.fullmatch(r"job-[a-f0-9]{24}", job_id):
        raise ValueError("Invalid Arena job identity")
    progress.phase("validating-pinned-frontier-inputs")
    snapshot = load_snapshot(root, spec)
    progress(0, 3)
    progress.phase("paired-deterministic-replay")
    comparison, replays = paired_deterministic_replay(
        snapshot.markets,
        snapshot.books,
        scenarios=snapshot.scenarios,
        verified_relationships=snapshot.verified_relationships,
        as_of_utc=snapshot.as_of_utc,
        code_version=snapshot.code_version,
        relationship_limit=snapshot.relationship_limit,
    )
    progress(1, 3)
    payload = {
        "schema_version": 1,
        "job_id": job_id,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_sha256": spec.snapshot_sha256,
        "created_at_utc": TypeAdapter(datetime).dump_python(datetime.now(UTC), mode="json"),
        "comparison": comparison.model_dump(mode="json"),
        "replays": [item.model_dump(mode="json") for item in replays],
    }
    result_sha256 = _sha256_json(payload)
    artifact = FrontierReplayJobArtifact.model_validate({"result_sha256": result_sha256, **payload})
    encoded = _canonical_json(artifact.model_dump(mode="json"))
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError("Frontier Arena replay result exceeds the 8 MiB artifact bound")
    jobs_root = root / "jobs"
    job_directory = jobs_root / job_id
    output_path = job_directory / "frontier-replay-result.json"
    if (
        root.is_symlink()
        or jobs_root.is_symlink()
        or job_directory.is_symlink()
        or not job_directory.is_dir()
        or output_path.is_symlink()
    ):
        raise ValueError("Arena job result path is unavailable or unsafe")
    progress.phase("publishing-hash-verified-result")
    atomic_bytes(output_path, encoded)
    progress(2, 3)
    return artifact


def read_frontier_replay_artifact(root: Path, job_id: str) -> FrontierReplayJobArtifact:
    if not re.fullmatch(r"job-[a-f0-9]{24}", job_id):
        raise ValueError("Invalid Arena job identity")
    jobs_root = root / "jobs"
    path = jobs_root / job_id / "frontier-replay-result.json"
    if (
        root.is_symlink()
        or jobs_root.is_symlink()
        or path.parent.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_RESULT_BYTES
    ):
        raise FileNotFoundError("Frontier Arena replay result is unavailable")
    try:
        artifact = FrontierReplayJobArtifact.model_validate(json.loads(path.read_bytes()))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Frontier Arena replay result failed integrity validation") from error
    if artifact.job_id != job_id:
        raise ValueError("Frontier Arena replay result belongs to a different job")
    return artifact


def verify_frontier_replay_job_result(
    root: Path, job_id: str, record: dict[str, Any]
) -> FrontierReplayJobArtifact:
    """Bind a completed artifact back to its durable Arena job configuration/result."""
    configuration = record.get("configuration")
    result_ref = record.get("result")
    if (
        record.get("job_id") != job_id
        or not isinstance(configuration, dict)
        or configuration.get("kind") != "frontier_replay"
        or record.get("state") != "COMPLETED"
        or record.get("exit_status") != 0
        or not isinstance(result_ref, dict)
        or result_ref.get("artifact") != "frontier-replay-result.json"
    ):
        raise ValueError("Completed Frontier replay result is unavailable")
    replay_spec_value = configuration.get("frontier_replay")
    if not isinstance(replay_spec_value, dict):
        raise ValueError("Arena job has no pinned Frontier replay configuration")
    replay_spec = FrontierReplayJobSpec.model_validate(replay_spec_value)
    artifact = read_frontier_replay_artifact(root, job_id)
    if (
        artifact.snapshot_id != replay_spec.snapshot_id
        or artifact.snapshot_sha256 != replay_spec.snapshot_sha256
        or artifact.result_sha256 != result_ref.get("frontier_replay_sha256")
        or artifact.comparison.comparison_id != result_ref.get("comparison_id")
        or artifact.snapshot_id != result_ref.get("snapshot_id")
    ):
        raise ValueError("Frontier replay result does not match its durable job record")
    return artifact
