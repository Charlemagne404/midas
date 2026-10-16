"""Immutable prospective period, source rules, models and analysis plan."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import struct
import time
import zlib
from pathlib import Path
from typing import Any

from .execution_research import families
from .model_registry import load
from .research_schema import FEATURE_VERSION, LABEL_VERSION, LIMITATIONS, digest
from .storage import MAGIC, MAX_RECORD, atomic_json, file_hash, records

VERSION = "reality-forward-campaign-v1"
SUCCESSOR_VERSION = "reality-forward-campaign-v2"
BOOTSTRAP_VERSION = "reality-cold-start-bootstrap-v1"
FILES = (
    "shadow_campaign.py",
    "shadow_source.py",
    "shadow_store.py",
    "shadow_policy.py",
    "shadow_worker.py",
    "execution_research.py",
    "research_measurements.py",
    "research_schema.py",
    "reconstruction.py",
    "storage.py",
    "model_features.py",
    "model_registry.py",
    "model_fitting.py",
    "model_metrics.py",
    "foundry.py",
)


def source_files() -> dict[str, Path]:
    result = {"reality/" + n: Path(__file__).with_name(n) for n in FILES}
    base = Path(__file__).parents[1]
    for directory in ("arbitrage", "core", "economics", "risk"):
        result.update(
            {
                directory + "/" + p.name: p
                for p in (base / directory).glob("*.py")
                if p.name != "__init__.py"
            }
        )
    return result


def _source_segment(raw: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError("Bootstrap source segment path is unsafe")
    path = Path(name)
    if path.suffix not in {".seg", ".open"}:
        raise ValueError("Bootstrap source segment suffix is invalid")
    stem = path.stem
    candidates = [raw / (stem + suffix) for suffix in (".seg", ".open")]
    present = [candidate for candidate in candidates if candidate.exists()]
    if len(present) != 1:
        raise ValueError("Bootstrap source segment is missing or ambiguous")
    result = present[0]
    if result.is_symlink() or not result.is_file():
        raise ValueError("Bootstrap source segment is not a regular file")
    return result


def _prefix_hash(path: Path, end: int) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = end
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Bootstrap source prefix is truncated")
            value.update(chunk)
            remaining -= len(chunk)
    return value.hexdigest()


def _read_source_record(
    raw: Path, reference: dict[str, Any], *, expected_kind: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    segment_name = reference.get("segment")
    if not isinstance(segment_name, str):
        raise ValueError("Bootstrap source segment reference is invalid")
    source = _source_segment(raw, segment_name)
    offset = reference.get("offset")
    if not isinstance(offset, int) or offset < len(MAGIC):
        raise ValueError("Bootstrap source record offset is invalid")
    with source.open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError("Bootstrap source framing is invalid")
        stream.seek(offset)
        header = stream.read(36)
        if len(header) != 36:
            raise ValueError("Bootstrap source record header is truncated")
        length, checksum = struct.unpack(">I32s", header)
        if not 0 < length <= MAX_RECORD:
            raise ValueError("Bootstrap source record length is invalid")
        compressed = stream.read(length)
        if len(compressed) != length or hashlib.sha256(compressed).digest() != checksum:
            raise ValueError("Bootstrap source record checksum mismatch")
        decoder = zlib.decompressobj()
        encoded = decoder.decompress(compressed, MAX_RECORD + 1)
        if len(encoded) > MAX_RECORD or not decoder.eof or decoder.unused_data:
            raise ValueError("Bootstrap source record compression is invalid")
        row = json.loads(encoded)
        end = stream.tell()
    if (
        row.get("schema_version") != 1
        or row.get("kind") != expected_kind
        or row.get("ordinal") != reference.get("ordinal")
        or row.get("received_ns") != reference.get("received_ns")
        or end != reference.get("end_offset")
    ):
        raise ValueError("Bootstrap source record does not match its pinned reference")
    canonical_hash = hashlib.sha256(encoded).hexdigest()
    compressed_hash = checksum.hex()
    prefix_sha = _prefix_hash(source, end)
    if any(
        reference.get(field) is not None and reference[field] != actual
        for field, actual in (
            ("canonical_record_sha256", canonical_hash),
            ("compressed_record_sha256", compressed_hash),
            ("prefix_sha256", prefix_sha),
        )
    ):
        raise ValueError("Bootstrap source record or prefix changed")
    sealed_sha: str | None = None
    if source.suffix == ".seg":
        catalog_path = source.with_suffix(".json")
        if catalog_path.is_symlink() or not catalog_path.is_file():
            raise ValueError("Bootstrap finalized segment catalog is missing")
        catalog = json.loads(catalog_path.read_text())
        sealed_sha = file_hash(source)
        if (
            catalog.get("sha256") != sealed_sha
            or catalog.get("bytes") != source.stat().st_size
            or not catalog.get("first", 0) <= row["ordinal"] <= catalog.get("last", 0)
        ):
            raise ValueError("Bootstrap finalized segment integrity mismatch")
        pinned_sha = reference.get("segment_sha256")
        if pinned_sha is not None and pinned_sha != sealed_sha:
            raise ValueError("Bootstrap finalized segment hash changed")
    normalized = dict(
        segment=source.stem + ".seg",
        offset=offset,
        end_offset=end,
        ordinal=row["ordinal"],
        received_ns=row["received_ns"],
        monotonic_ns=row["monotonic_ns"],
        compressed_record_sha256=compressed_hash,
        canonical_record_sha256=canonical_hash,
        prefix_sha256=prefix_sha,
        segment_sha256=sealed_sha,
        segment_seal_status=("sealed" if sealed_sha else "pending_until_finalization"),
    )
    return row, normalized


def _latest_discovery(
    raw: Path, start_ns: int, *, max_scan_bytes: int = 64 * 1024**2
) -> tuple[dict[str, Any], dict[str, Any]]:
    files = sorted(
        path
        for path in raw.iterdir()
        if path.name[:1].isdigit() and path.suffix in {".seg", ".open"}
    )
    if any(path.is_symlink() for path in files):
        raise ValueError("Bootstrap source contains a symlink")
    scanned = 0
    for source in reversed(files):
        size = source.stat().st_size
        if scanned + size > max_scan_bytes:
            break
        scanned += size
        if source.suffix == ".seg":
            catalog_path = source.with_suffix(".json")
            if catalog_path.is_symlink() or not catalog_path.is_file():
                raise ValueError("Bootstrap finalized segment catalog is missing")
            catalog = json.loads(catalog_path.read_text())
            if catalog.get("sha256") != file_hash(source) or catalog.get("bytes") != size:
                raise ValueError("Bootstrap finalized segment integrity mismatch")
        offset = len(MAGIC)
        candidate: dict[str, Any] | None = None
        for row, end in records(source, incomplete=source.suffix == ".open"):
            if row.get("kind") == "discovery" and row.get("received_ns", 0) < start_ns:
                candidate = dict(
                    segment=source.stem + ".seg",
                    offset=offset,
                    end_offset=end,
                    ordinal=row["ordinal"],
                    received_ns=row["received_ns"],
                )
            offset = end
        if candidate is not None:
            row, reference = _read_source_record(raw, candidate, expected_kind="discovery")
            return row, reference
    raise ValueError("No recent verified discovery exists within the bootstrap scan bound")


def _verify_bootstrap(identity: dict[str, Any]) -> None:
    bootstrap = identity.get("bootstrap")
    parent_ref = identity.get("parent_campaign")
    if not isinstance(bootstrap, dict) or bootstrap.get("version") != BOOTSTRAP_VERSION:
        raise ValueError("Successor campaign bootstrap is missing or unsupported")
    if not isinstance(parent_ref, dict):
        raise ValueError("Successor campaign parent reference is missing")
    parent_path = Path(parent_ref.get("path", ""))
    if parent_path.name != "campaign.json" or parent_path.is_symlink() or not parent_path.is_file():
        raise ValueError("Successor campaign parent file is missing")
    if file_hash(parent_path) != parent_ref.get("sha256"):
        raise ValueError("Successor campaign parent file changed")
    parent = json.loads(parent_path.read_text())
    verify(parent, check_code=False)
    if parent.get("campaign_id") != parent_ref.get("campaign_id"):
        raise ValueError("Successor campaign does not reference its declared parent")
    if identity.get("raw_root") != parent["identity"].get("raw_root"):
        raise ValueError("Successor campaign source differs from its parent")
    raw = Path(identity["raw_root"])
    producer_row, producer_ref = _read_source_record(
        raw, bootstrap.get("producer_ref", {}), expected_kind="gap"
    )
    if (
        producer_row.get("payload", {}).get("reason") != "process_start"
        or producer_row.get("payload", {}).get("implementation_sha256")
        != bootstrap.get("producer_hash")
        or bootstrap.get("producer_hash")
        not in parent["identity"].get("allowed_producer_hashes", [])
    ):
        raise ValueError("Successor producer epoch is not verified by its parent")
    discovery_row, discovery_ref = _read_source_record(
        raw, bootstrap.get("discovery_ref", {}), expected_kind="discovery"
    )
    cursor = bootstrap.get("cursor", {})
    if cursor != dict(
        segment=discovery_ref["segment"].removesuffix(".seg"),
        offset=discovery_ref["offset"],
        ordinal=discovery_ref["ordinal"] - 1,
    ):
        raise ValueError("Successor bootstrap cursor does not begin at its pinned discovery")
    if not producer_row["received_ns"] <= discovery_row["received_ns"] < identity["start_ns"]:
        raise ValueError("Successor bootstrap source times are inconsistent")
    if (
        bootstrap.get("producer_ref") != producer_ref
        or bootstrap.get("discovery_ref") != discovery_ref
    ):
        raise ValueError("Successor bootstrap source references changed")
    epoch = bootstrap.get("source_epoch", {})
    if epoch.get("reconstruction_version") not in (1, 2, 3, 4):
        raise ValueError("Successor bootstrap reconstruction version is invalid")
    if epoch.get("reconstruction_version") != producer_row.get("payload", {}).get(
        "reconstruction_version", 1
    ):
        raise ValueError("Successor bootstrap reconstruction version changed")
    status = bootstrap.get("collector_status", {})
    if bootstrap.get("checkpoint_validation") != (
        "source-state digest comparisons are disabled for this cold-start context; "
        "record and segment integrity checks remain active"
    ):
        raise ValueError("Successor cold-start checkpoint contract is invalid")
    started_ns = status.get("started_ns")
    observed_ordinal = status.get("ordinal")
    if (
        not isinstance(started_ns, int)
        or not isinstance(observed_ordinal, int)
        or started_ns <= 0
        or observed_ordinal < discovery_row["ordinal"]
        or abs(started_ns - producer_row["received_ns"]) > 10 * 10**9
    ):
        raise ValueError("Successor bootstrap collector continuity evidence is invalid")


def verify(plan: dict[str, Any], *, check_code: bool = True) -> None:
    if digest(plan["identity"]) != plan["campaign_id"]:
        raise ValueError("Campaign identity corruption")
    i = plan["identity"]
    if (
        i["frozen_ns"] >= i["start_ns"]
        or i["start_ns"] >= i["end_ns"]
        or i["end_ns"] - i["start_ns"] > 30 * 86400 * 10**9
    ):
        raise ValueError("Campaign was not frozen before a bounded future period")
    if i["version"] not in {VERSION, SUCCESSOR_VERSION}:
        raise ValueError("Campaign version is unsupported")
    if i["feature_version"] != FEATURE_VERSION or i["label_version"] != LABEL_VERSION:
        raise ValueError("Campaign measurement version incompatible")
    if i["version"] == SUCCESSOR_VERSION:
        _verify_bootstrap(i)
    if check_code and {n: file_hash(p) for n, p in source_files().items()} != i["code"]:
        raise ValueError("Use frozen campaign code; no mid-period implementation retuning")


def _freeze_code(root: Path) -> None:
    for name, path in source_files().items():
        target = root / "code" / "midas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    for package in ("", "reality", "arbitrage", "core", "economics", "risk"):
        folder = root / "code" / "midas" / package
        (folder / "__init__.py").write_text(
            "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
        )


def freeze_successor(
    root: Path,
    parent_root: Path,
    producer_ref: dict[str, Any],
    *,
    start_ns: int | None = None,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    """Freeze a cold-start successor at a verified public discovery boundary.

    The parent campaign remains immutable and may overlap only as this
    successor's declared direct parent. Source history before the cursor is
    intentionally not replayed into the successor.
    """
    parent_path = parent_root / "campaign.json"
    parent = json.loads(parent_path.read_text())
    verify(parent, check_code=False)
    parent_identity = parent["identity"]
    raw = Path(parent_identity["raw_root"])
    if (
        root.resolve() == parent_root.resolve()
        or root.parent.resolve() != parent_root.parent.resolve()
    ):
        raise ValueError("Successor must be a sibling of its direct parent campaign")
    if root.exists():
        if not (root / "campaign.json").is_file():
            raise ValueError("Successor directory already exists without a campaign")
        existing = json.loads((root / "campaign.json").read_text())
        if not isinstance(existing, dict):
            raise ValueError("Existing successor campaign is not an object")
        verify(existing)
        return {str(key): value for key, value in existing.items()}

    now = time.time_ns()
    start = start_ns if start_ns is not None else now + 2 * 10**9
    if duration_seconds is None:
        duration_seconds = (parent_identity["end_ns"] - parent_identity["start_ns"]) // 10**9
    end = start + duration_seconds * 10**9
    discovery_row, discovery_ref = _latest_discovery(raw, start)
    producer_row, normalized_producer_ref = _read_source_record(
        raw, producer_ref, expected_kind="gap"
    )
    producer_hash = producer_row.get("payload", {}).get("implementation_sha256")
    if producer_row.get("payload", {}).get(
        "reason"
    ) != "process_start" or producer_hash not in parent_identity.get("allowed_producer_hashes", []):
        raise ValueError("Successor producer reference is not a parent-approved process start")
    status_path = raw / "status.json"
    if status_path.is_symlink() or not status_path.is_file():
        raise ValueError("Successor requires current collector status evidence")
    status_live = json.loads(status_path.read_text())
    state = status_live.get("state", "")
    if not isinstance(state, str) or not (
        state.startswith("RECORDING") or state.startswith("DEGRADED")
    ):
        raise ValueError("Successor requires an active Reality recorder")
    collector_status = {
        key: status_live.get(key)
        for key in ("state", "started_ns", "updated_ns", "ordinal", "sequence_verified")
    }
    started_ns = collector_status["started_ns"]
    if (
        not isinstance(started_ns, int)
        or abs(started_ns - producer_row["received_ns"]) > 10 * 10**9
        or not isinstance(collector_status["ordinal"], int)
        or collector_status["ordinal"] < discovery_row["ordinal"]
    ):
        raise ValueError("Current collector status does not corroborate the pinned producer epoch")
    bootstrap = dict(
        version=BOOTSTRAP_VERSION,
        method="verified_cold_start_at_discovery; prior_source_history_not_replayed",
        checkpoint_validation=(
            "source-state digest comparisons are disabled for this cold-start context; "
            "record and segment integrity checks remain active"
        ),
        cursor=dict(
            segment=discovery_ref["segment"].removesuffix(".seg"),
            offset=discovery_ref["offset"],
            ordinal=discovery_ref["ordinal"] - 1,
        ),
        producer_ref=normalized_producer_ref,
        producer_hash=producer_hash,
        discovery_ref=discovery_ref,
        source_epoch=dict(
            reconstruction_version=producer_row["payload"].get("reconstruction_version", 1),
            stale_ns=producer_row["payload"].get("stale_ns"),
        ),
        collector_status=collector_status,
    )
    identity = copy.deepcopy(parent_identity)
    identity.update(
        version=SUCCESSOR_VERSION,
        frozen_ns=now,
        start_ns=start,
        end_ns=end,
        parent_campaign=dict(
            path=str(parent_path.resolve()),
            campaign_id=parent["campaign_id"],
            sha256=file_hash(parent_path),
        ),
        bootstrap=bootstrap,
        allowed_producer_hashes=[producer_hash],
        code={name: file_hash(path) for name, path in source_files().items()},
    )
    plan = dict(campaign_id=digest(identity), identity=identity, limitations=parent["limitations"])
    verify(plan)

    parent_sha = file_hash(parent_path)
    for sibling in root.parent.glob("*/campaign.json"):
        if sibling.resolve() == parent_path.resolve():
            if file_hash(sibling) != parent_sha:
                raise ValueError("Direct parent campaign changed during successor freeze")
            continue
        old_plan = json.loads(sibling.read_text())
        old = old_plan["identity"]
        if old.get("source_kind") == identity["source_kind"] and max(old["start_ns"], start) <= min(
            old["end_ns"], end
        ):
            raise ValueError("Successor period overlaps an unrelated frozen campaign")

    root.mkdir(parents=True, exist_ok=False)
    _freeze_code(root)
    atomic_json(root / "campaign.json", plan)
    return plan


def freeze(
    root: Path,
    raw: Path,
    training: Path,
    run_id: str,
    producer_hash: str,
    selection: dict[str, Any],
    *,
    fixture: bool = False,
    start_ns: int | None = None,
    days: int = 14,
    duration_seconds: int | None = None,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    if (root / "campaign.json").exists():
        plan = json.loads((root / "campaign.json").read_text())
        verify(plan)
        return dict(plan)
    now = time.time_ns()
    start = start_ns or now + 2 * 10**9
    report_path = training / "runs" / run_id / "report.json"
    report = json.loads(report_path.read_text())
    models = {}
    eligible = {}
    for target, data in report["targets"].items():
        if not data.get("selected_by_validation"):
            continue
        model = load(training, data["selected_by_validation"])
        models[target] = dict(
            model_id=model["info"]["model_id"],
            weights_sha256=model["info"]["weights_sha256"],
            metadata_sha256=model["info"]["identity"]["metadata_sha256"],
        )
        eligible[target] = data.get("eligibility", {}).get("policy_eligible", False)
    identity = dict(
        version=VERSION,
        source_kind="labeled_fixture" if fixture else "genuine_public_recording",
        frozen_ns=now,
        start_ns=start,
        end_ns=start + (duration_seconds if duration_seconds is not None else days * 86400) * 10**9,
        raw_root=str(raw.resolve()),
        training_root=str(training.resolve()),
        training_run_id=run_id,
        training_report_sha256=file_hash(report_path),
        models=models,
        eligibility_at_freeze=eligible,
        allowed_producer_hashes=[producer_hash],
        allowed_reconstruction_versions=[4],
        market_selection=selection,
        feature_version=FEATURE_VERSION,
        label_version=LABEL_VERSION,
        scenarios=[a.manifest() for a in families()],
        horizons_ms=[100, 300, 1000, 5000],
        future_tolerance_ms=500,
        followup_availability_grace_ms=2000,
        max_freshness_ms=5000,
        max_skew_ms=250,
        max_decision_input_lag_ms=250,
        baseline_stride_ms=30000,
        opportunity_stride_ms=5000,
        observatory_stride_ms=5000,
        quantity="5",
        capital="100",
        settlement_lock_days=7,
        max_decisions=400000,
        max_observations=4000000,
        evidence_budget_bytes=4 * 1024**3,
        reserve_bytes=20 * 1024**3,
        risk=dict(
            max_positions=5,
            max_opportunity_capital="25",
            max_market_exposure="25",
            max_family_exposure="50",
            max_total_exposure="50",
            persistence_threshold=0.9,
            disruption_threshold=0.1,
        ),
        risk_objective="Avoid unsupported hypothetical risk; reserve worst-case acquisition capital for declared seven-day lock; no inferred settlement proceeds",
        controls=[
            "no_trade",
            "mathematical_filter",
            "prometheus_control",
            "conservative_risk",
            "prediction_gate",
            "recovery_guard",
        ],
        analysis=dict(
            version="reality-prospective-analysis-v1",
            promotion=False,
            threshold_retuning=False,
            paired_on="Same recorded source/decision across controls and scenarios",
            grouping="Connected event/condition/negative-risk families and UTC time blocks; shared feed remains correlated",
            reported="Decision behavior, censoring, public persistence/depth/price changes and per-trial hypothetical bounds; no summed realized P&L",
            recovery="Declared quoted-bid unwind only where later observed depth supports quantity/minimum; otherwise retain unmatched bounds",
            eligibility="Experimental probes do not authorize a policy; no champion manufactured",
        ),
        code={n: file_hash(p) for n, p in source_files().items()},
        toolchain={n: importlib.metadata.version(n) for n in ("numpy", "scikit-learn")},
    )
    plan = dict(campaign_id=digest(identity), identity=identity, limitations=LIMITATIONS)
    verify(plan)
    for path in root.parent.glob("*/campaign.json"):
        old = json.loads(path.read_text())["identity"]
        if old["source_kind"] == identity["source_kind"] and max(old["start_ns"], start) <= min(
            old["end_ns"], identity["end_ns"]
        ):
            raise ValueError("Forward period overlaps an existing frozen campaign")
    for name, path in source_files().items():
        target = root / "code" / "midas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    for package in ("", "reality", "arbitrage", "core", "economics", "risk"):
        folder = root / "code" / "midas" / package
        (folder / "__init__.py").write_text(
            "from pkgutil import extend_path\n__path__ = extend_path(__path__, __name__)\n"
        )
    atomic_json(root / "campaign.json", plan)
    return plan
