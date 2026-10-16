from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import zlib
from pathlib import Path
from typing import Any

import pytest
from midas.reality.research_schema import digest
from midas.reality.storage import MAGIC, canonical
from midas.veritas import censor_gap_audit as audit
from midas.veritas.censor_gap_audit import audit_censored_gap_records


def _source_fixture(root: Path) -> dict[str, dict[str, Any]]:
    root.mkdir()
    records: list[dict[str, Any]] = [
        {
            "schema_version": 1,
            "ordinal": 1,
            "received_ns": 1_000,
            "monotonic_ns": 1,
            "kind": "gap",
            "payload": {"reason": "book_resynchronization"},
        },
        {
            "schema_version": 1,
            "ordinal": 2,
            "received_ns": 2_000,
            "monotonic_ns": 2,
            "kind": "public_fee_metadata",
            "asset_id": "test-asset",
            "payload": {"fee_rate": "0"},
        },
    ]
    segment_name = f"{1:020d}-{'a' * 32}.seg"
    data = bytearray(MAGIC)
    references: dict[str, dict[str, Any]] = {}
    kinds: dict[str, int] = {}
    for record in records:
        raw = canonical(record)
        compressed = zlib.compress(raw)
        offset = len(data)
        data.extend(struct.pack(">I32s", len(compressed), hashlib.sha256(compressed).digest()))
        data.extend(compressed)
        references[str(record["ordinal"])] = {
            "segment": segment_name,
            "offset": offset,
            "end_offset": len(data),
            "ordinal": record["ordinal"],
            "received_ns": record["received_ns"],
            "compressed_record_sha256": hashlib.sha256(compressed).hexdigest(),
            "canonical_record_sha256": hashlib.sha256(raw).hexdigest(),
        }
        kinds[record["kind"]] = kinds.get(record["kind"], 0) + 1
    segment_path = root / segment_name
    segment_path.write_bytes(data)
    catalog = {
        "schema_version": 1,
        "file": segment_name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "first": 1,
        "last": 2,
        "count": 2,
        "kinds": kinds,
    }
    segment_path.with_suffix(".json").write_text(json.dumps(catalog))
    return references


def _campaign_fixture(
    root: Path,
    *,
    corrupt_digest: bool = False,
) -> None:
    source_root = root / "raw"
    references = _source_fixture(source_root)
    identity = {"raw_root": str(source_root.resolve()), "start_ns": 1, "end_ns": 10_000}
    campaign_id = digest(identity)
    (root / "campaign.json").write_text(
        json.dumps({"campaign_id": campaign_id, "identity": identity})
    )
    db = sqlite3.connect(root / "shadow.sqlite")
    db.executescript(
        """
        create table events(seq integer primary key,kind text,occurred_ns integer,body blob,previous_sha text,sha text);
        create table outcomes(decision_id text,horizon integer,status text,event_seq integer,primary key(decision_id,horizon));
        """
    )
    followups = [
        ("decision-a", 1_000, "recorded_gap:book_resynchronization", references["1"]),
        ("decision-a", 5_000, "recorded_gap:book_resynchronization", references["1"]),
        ("decision-b", 1_000, "book_issue:gap:book_resynchronization", references["2"]),
        ("decision-c", 300, "book_issue:gap:stale_book", references["2"]),
    ]
    if corrupt_digest:
        followups[0][3]["canonical_record_sha256"] = "f" * 64
    for sequence, (decision_id, horizon, reason, reference) in enumerate(followups, start=1):
        event = {
            "campaign_id": campaign_id,
            "decision_id": decision_id,
            "horizon_ms": horizon,
            "labels": {"status": "censored", "reason": reason},
            "termination_ref": reference,
        }
        body = canonical(event)
        event_sha = f"{sequence:064x}"
        db.execute(
            "insert into events values(?,?,?,?,?,?)",
            (sequence, "followup", sequence, zlib.compress(body), "0" * 64, event_sha),
        )
        db.execute(
            "insert into outcomes values(?,?,?,?)",
            (decision_id, horizon, "censored", sequence),
        )
    db.commit()
    db.close()


def test_audit_verifies_explicit_gap_refs_and_separates_indirect_book_issue_refs(
    tmp_path: Path,
) -> None:
    _campaign_fixture(tmp_path)

    report = audit_censored_gap_records(tmp_path)

    assert report["status"] == "verified"
    assert report["query"]["censored_outcome_limit"] == 50_000
    assert report["query"]["censored_outcomes_scanned"] == 4
    assert report["query"]["censored_outcome_event_bytes_read"] > 0
    assert report["query"]["truncated"] is False
    assert report["gap_censors"]["outcome_rows"] == 4
    assert report["gap_censors"]["unique_termination_records"] == 2
    assert report["gap_censors"]["unique_termination_record_kinds"] == {
        "gap": 1,
        "public_fee_metadata": 1,
    }
    assert report["gap_censors"]["explicit_recorded_gap_outcomes"] == 2
    assert report["gap_censors"]["unique_explicit_gap_records_verified"] == 1
    assert report["gap_censors"]["unique_explicit_gap_records_by_reason"] == {
        "book_resynchronization": 1,
    }
    assert report["gap_censors"]["book_issue_gap_outcomes"] == 2
    assert report["gap_censors"]["unique_book_issue_termination_records_by_source_kind"] == {
        "public_fee_metadata": 1,
    }
    assert report["gap_censors"]["book_issue_direct_gap_causality_verified"] is False
    assert report["source_verification"]["active_open_segments_read"] is False
    assert report["source_verification"]["finalized_segment_byte_limit"] == 128 * 1024**2
    assert report["source_verification"]["unique_finalized_segments_verified"] == 1


def test_audit_rejects_a_tampered_campaign_source_digest(tmp_path: Path) -> None:
    _campaign_fixture(tmp_path, corrupt_digest=True)

    with pytest.raises(ValueError, match="canonical record digest mismatch"):
        audit_censored_gap_records(tmp_path)


def test_audit_fails_closed_if_censored_outcome_query_would_truncate(tmp_path: Path) -> None:
    _campaign_fixture(tmp_path)

    with pytest.raises(ValueError, match="query was truncated"):
        audit_censored_gap_records(tmp_path, limit=2)


def test_audit_fails_closed_at_the_censored_event_byte_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _campaign_fixture(tmp_path)
    monkeypatch.setattr(audit, "MAX_OUTCOME_EVENT_BYTES", 1)

    with pytest.raises(ValueError, match="event bytes exceed their explicit bound"):
        audit_censored_gap_records(tmp_path)
