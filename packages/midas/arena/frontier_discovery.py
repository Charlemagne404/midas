"""Arena artifacts for bounded Frontier discovery-scope comparisons."""

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
from midas.frontier.discovery_comparison import (
    DiscoveryScopeComparison,
    compare_discovery_scopes,
)
from midas.frontier.economics import ExecutionScenario
from midas.frontier.models import BookSnapshot, FrontierMarket, FrontierModel, JointStateMap
from midas.frontier.relationships import Relationship, VerificationState
from midas.frontier.replay import ReplayResult

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_STORE_BYTES = 128 * 1024 * 1024
MAX_SNAPSHOT_COUNT = 1000
MAX_RESULT_BYTES = 32 * 1024 * 1024
MAX_REPLAYS = 6


class FrontierDiscoveryJobSpec(Model):
    """References one immutable, content-addressed comparison input."""

    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class FrontierDiscoverySnapshot(FrontierModel):
    schema_version: Literal[1] = 1
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_version: str = Field(min_length=1, max_length=240)
    as_of_utc: datetime
    relationship_limit: int = Field(ge=1, le=500)
    scenario: ExecutionScenario
    markets: tuple[FrontierMarket, ...] = Field(max_length=100)
    books: tuple[BookSnapshot, ...] = Field(max_length=200)
    verified_relationships: tuple[Relationship, ...] = Field(max_length=500)
    state_mappings: dict[str, dict[str, str]] = Field(default_factory=dict)
    instrument_mappings: dict[str, dict[str, str]] = Field(default_factory=dict)
    joint_state_mappings: tuple[JointStateMap, ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def snapshot_is_pinned_and_bounded(self) -> FrontierDiscoverySnapshot:
        if self.as_of_utc.tzinfo is None or self.as_of_utc.utcoffset() is None:
            raise ValueError("Frontier discovery timestamp must include a timezone")
        canonical_ids = [item.canonical_id for item in self.markets]
        source_ids = [(item.venue, item.native_market_id) for item in self.markets]
        if len(canonical_ids) != len(set(canonical_ids)) or len(source_ids) != len(set(source_ids)):
            raise ValueError("Frontier discovery snapshot market identities must be unique")
        market_index = {item.canonical_id: item for item in self.markets}
        source_market_ids = set(source_ids)
        instrument_ids = {
            (market.venue, market.native_market_id, instrument.native_instrument_id)
            for market in self.markets
            for instrument in market.instruments
        }
        if any(
            (book.venue, book.native_market_id) not in source_market_ids
            or (book.venue, book.native_market_id, book.native_instrument_id) not in instrument_ids
            for book in self.books
        ):
            raise ValueError("Frontier discovery snapshot contains a book outside its markets")
        if len(
            {(book.venue, book.native_market_id, book.native_instrument_id) for book in self.books}
        ) != len(self.books):
            raise ValueError("Frontier discovery snapshot contains duplicate instrument books")
        relationship_ids = {item.relationship_id for item in self.verified_relationships}
        if len(relationship_ids) != len(self.verified_relationships) or any(
            item.state != VerificationState.VERIFIED
            or item.left_market_id not in market_index
            or item.right_market_id not in market_index
            for item in self.verified_relationships
        ):
            raise ValueError("Frontier discovery snapshot contains an invalid relationship")
        if (
            set(self.state_mappings) - relationship_ids
            or set(self.instrument_mappings) - relationship_ids
        ):
            raise ValueError("Frontier discovery mapping references an unpinned relationship")
        if any(
            not set(item.market_ids).issubset(market_index) for item in self.joint_state_mappings
        ):
            raise ValueError("Frontier discovery joint-state map references an unpinned market")
        payload = self.model_dump(mode="json", exclude={"snapshot_id"})
        if _sha256_json(payload) != self.snapshot_id:
            raise ValueError("Frontier discovery snapshot identity does not match its inputs")
        return self


class FrontierDiscoveryJobArtifact(FrontierModel):
    schema_version: Literal[1] = 1
    job_id: str = Field(pattern=r"^job-[a-f0-9]{24}$")
    snapshot_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at_utc: datetime
    comparison: DiscoveryScopeComparison
    replays: tuple[ReplayResult, ...] = Field(min_length=1, max_length=MAX_REPLAYS)
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def result_is_pinned(self) -> FrontierDiscoveryJobArtifact:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() is None:
            raise ValueError("Frontier discovery result time must include a timezone")
        replay_ids = {item.run_id for item in self.replays}
        expected_ids = {run_id for arm in self.comparison.arms for run_id in arm.replay_run_ids}
        candidate_ids = {item.candidate_id for replay in self.replays for item in replay.candidates}
        summarized_ids = {
            item.candidate_id for arm in self.comparison.arms for item in arm.candidates
        }
        if replay_ids != expected_ids or not summarized_ids.issubset(candidate_ids):
            raise ValueError("Frontier discovery comparison does not match its pinned replays")
        payload = self.model_dump(mode="json", exclude={"result_sha256"})
        if _sha256_json(payload) != self.result_sha256:
            raise ValueError("Frontier discovery result hash does not match its payload")
        return self


def make_snapshot(
    *,
    code_version: str,
    as_of_utc: datetime,
    relationship_limit: int,
    scenario: ExecutionScenario,
    markets: tuple[FrontierMarket, ...],
    books: tuple[BookSnapshot, ...],
    verified_relationships: tuple[Relationship, ...],
    state_mappings: dict[str, dict[str, str]] | None = None,
    instrument_mappings: dict[str, dict[str, str]] | None = None,
    joint_state_mappings: tuple[JointStateMap, ...] = (),
) -> FrontierDiscoverySnapshot:
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise ValueError("Frontier discovery timestamp must include a timezone")
    data = {
        "schema_version": 1,
        "code_version": code_version,
        "as_of_utc": TypeAdapter(datetime).dump_python(as_of_utc.astimezone(UTC), mode="json"),
        "relationship_limit": relationship_limit,
        "scenario": scenario.model_dump(mode="json"),
        "markets": [
            item.model_dump(mode="json")
            for item in sorted(markets, key=lambda item: item.canonical_id)
        ],
        "books": [
            item.model_dump(mode="json")
            for item in sorted(
                books,
                key=lambda item: (
                    item.venue.value,
                    item.native_market_id,
                    item.native_instrument_id,
                    item.provenance.observation_id,
                ),
            )
        ],
        "verified_relationships": [
            item.model_dump(mode="json")
            for item in sorted(verified_relationships, key=lambda item: item.relationship_id)
        ],
        "state_mappings": state_mappings or {},
        "instrument_mappings": instrument_mappings or {},
        "joint_state_mappings": [
            item.model_dump(mode="json")
            for item in sorted(joint_state_mappings, key=lambda item: item.mapping_id)
        ],
    }
    return FrontierDiscoverySnapshot.model_validate({"snapshot_id": _sha256_json(data), **data})


def _snapshot_directory(root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("Arena root cannot be a symlink")
    directory = root / "frontier-discovery-snapshots"
    if directory.is_symlink():
        raise ValueError("Frontier discovery snapshot directory cannot be a symlink")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store_snapshot(root: Path, snapshot: FrontierDiscoverySnapshot) -> str:
    try:
        validated_snapshot = FrontierDiscoverySnapshot.model_validate(
            snapshot.model_dump(mode="json", exclude_unset=True)
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Frontier discovery snapshot failed its storage validation") from error
    encoded = _canonical_json(validated_snapshot.model_dump(mode="json"))
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Frontier discovery snapshot exceeds the 8 MiB artifact bound")
    directory = _snapshot_directory(root)
    path = directory / f"{validated_snapshot.snapshot_id}.json"
    if path.is_symlink():
        raise ValueError("Frontier discovery snapshot cannot be a symlink")
    if path.exists():
        current = path.read_bytes()
        if current != encoded:
            raise ValueError("Content-addressed Frontier discovery snapshot changed")
        return hashlib.sha256(current).hexdigest()
    total_bytes = 0
    count = 0
    for index, item in enumerate(directory.glob("*.json")):
        if index >= MAX_SNAPSHOT_COUNT:
            raise ValueError("Frontier discovery snapshot inventory exceeds its scan bound")
        if item.is_symlink() or not item.is_file():
            raise ValueError("Frontier discovery snapshot inventory contains an unsafe entry")
        count += 1
        total_bytes += item.stat().st_size
    if count >= MAX_SNAPSHOT_COUNT or total_bytes + len(encoded) > MAX_SNAPSHOT_STORE_BYTES:
        raise ValueError("Frontier discovery snapshot store budget is exhausted")
    atomic_bytes(path, encoded)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_snapshot(root: Path, spec: FrontierDiscoveryJobSpec) -> FrontierDiscoverySnapshot:
    try:
        validated_spec = FrontierDiscoveryJobSpec.model_validate(spec.model_dump(mode="json"))
    except (TypeError, ValueError) as error:
        raise ValueError("Pinned Frontier discovery job spec failed validation") from error
    directory = root / "frontier-discovery-snapshots"
    path = directory / f"{validated_spec.snapshot_id}.json"
    if (
        root.is_symlink()
        or directory.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_SNAPSHOT_BYTES
    ):
        raise ValueError("Pinned Frontier discovery snapshot is unavailable or unsafe")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != validated_spec.snapshot_sha256:
        raise ValueError("Pinned Frontier discovery snapshot file hash does not match the job")
    try:
        snapshot = FrontierDiscoverySnapshot.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Pinned Frontier discovery snapshot is invalid") from error
    if snapshot.snapshot_id != validated_spec.snapshot_id:
        raise ValueError("Frontier discovery snapshot identity does not match the job")
    return snapshot


def execute_frontier_discovery_job(
    root: Path,
    job_id: str,
    spec: FrontierDiscoveryJobSpec,
    progress: Any,
) -> FrontierDiscoveryJobArtifact:
    if not re.fullmatch(r"job-[a-f0-9]{24}", job_id):
        raise ValueError("Invalid Arena job identity")
    progress.phase("validating-pinned-discovery-inputs")
    snapshot = load_snapshot(root, spec)
    progress(0, 3)
    progress.phase("comparing-discovery-scopes")
    comparison, generated_replays = compare_discovery_scopes(
        snapshot.markets,
        snapshot.books,
        verified_relationships=snapshot.verified_relationships,
        state_mappings=snapshot.state_mappings,
        instrument_mappings=snapshot.instrument_mappings,
        joint_state_mappings=snapshot.joint_state_mappings,
        scenario=snapshot.scenario,
        as_of_utc=snapshot.as_of_utc,
        code_version=snapshot.code_version,
        relationship_limit=snapshot.relationship_limit,
    )
    unique_replays: dict[str, ReplayResult] = {}
    for replay in generated_replays:
        previous = unique_replays.setdefault(replay.run_id, replay)
        if previous != replay:
            raise ValueError("Discovery profiles produced conflicting results for one replay ID")
    replays = tuple(unique_replays[key] for key in sorted(unique_replays))
    if not 1 <= len(replays) <= MAX_REPLAYS:
        raise ValueError("Frontier discovery replay artifact count exceeds its bound")
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
    artifact = FrontierDiscoveryJobArtifact.model_validate(
        {"result_sha256": _sha256_json(payload), **payload}
    )
    encoded = _canonical_json(artifact.model_dump(mode="json"))
    if len(encoded) > MAX_RESULT_BYTES:
        raise ValueError("Frontier discovery result exceeds the 32 MiB artifact bound")
    jobs_root = root / "jobs"
    job_directory = jobs_root / job_id
    output_path = job_directory / "frontier-discovery-result.json"
    if (
        root.is_symlink()
        or jobs_root.is_symlink()
        or job_directory.is_symlink()
        or not job_directory.is_dir()
        or output_path.is_symlink()
    ):
        raise ValueError("Arena discovery result path is unavailable or unsafe")
    progress.phase("publishing-hash-verified-discovery-result")
    atomic_bytes(output_path, encoded)
    progress(2, 3)
    return artifact


def read_frontier_discovery_artifact(root: Path, job_id: str) -> FrontierDiscoveryJobArtifact:
    if not re.fullmatch(r"job-[a-f0-9]{24}", job_id):
        raise ValueError("Invalid Arena job identity")
    jobs_root = root / "jobs"
    path = jobs_root / job_id / "frontier-discovery-result.json"
    if (
        root.is_symlink()
        or jobs_root.is_symlink()
        or path.parent.is_symlink()
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_RESULT_BYTES
    ):
        raise FileNotFoundError("Frontier Arena discovery result is unavailable")
    try:
        artifact = FrontierDiscoveryJobArtifact.model_validate(json.loads(path.read_bytes()))
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("Frontier discovery result failed integrity validation") from error
    if artifact.job_id != job_id:
        raise ValueError("Frontier discovery result belongs to a different job")
    return artifact


def verify_frontier_discovery_job_result(
    root: Path, job_id: str, record: dict[str, Any]
) -> FrontierDiscoveryJobArtifact:
    configuration = record.get("configuration")
    result_ref = record.get("result")
    if (
        record.get("job_id") != job_id
        or not isinstance(configuration, dict)
        or configuration.get("kind") != "frontier_discovery"
        or record.get("state") != "COMPLETED"
        or record.get("exit_status") != 0
        or not isinstance(result_ref, dict)
        or result_ref.get("artifact") != "frontier-discovery-result.json"
    ):
        raise ValueError("Completed Frontier discovery result is unavailable")
    spec_value = configuration.get("frontier_discovery")
    if not isinstance(spec_value, dict):
        raise ValueError("Arena job has no pinned Frontier discovery configuration")
    spec = FrontierDiscoveryJobSpec.model_validate(spec_value)
    artifact = read_frontier_discovery_artifact(root, job_id)
    if (
        artifact.snapshot_id != spec.snapshot_id
        or artifact.snapshot_sha256 != spec.snapshot_sha256
        or artifact.result_sha256 != result_ref.get("frontier_discovery_sha256")
        or artifact.comparison.comparison_id != result_ref.get("comparison_id")
        or artifact.snapshot_id != result_ref.get("snapshot_id")
    ):
        raise ValueError("Frontier discovery result does not match its durable Arena job record")
    return artifact


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
