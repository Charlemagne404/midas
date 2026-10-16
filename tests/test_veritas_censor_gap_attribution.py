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
from midas.veritas import censor_gap_attribution as attribution
from midas.veritas.gap_detail_analysis import VERSION as GAP_VERSION
from midas.veritas.gap_detail_analysis import _canonical, _code_identity, _sealed


def _segment(
    path: Path, records: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    data = bytearray(MAGIC)
    references: dict[int, dict[str, Any]] = {}
    kinds: dict[str, int] = {}
    for record in records:
        raw = canonical(record)
        compressed = zlib.compress(raw)
        offset = len(data)
        data.extend(struct.pack(">I32s", len(compressed), hashlib.sha256(compressed).digest()))
        data.extend(compressed)
        references[record["ordinal"]] = {
            "segment": path.name,
            "offset": offset,
            "end_offset": len(data),
            "ordinal": record["ordinal"],
            "received_ns": record["received_ns"],
            "compressed_record_sha256": hashlib.sha256(compressed).hexdigest(),
            "canonical_record_sha256": hashlib.sha256(raw).hexdigest(),
        }
        kinds[record["kind"]] = kinds.get(record["kind"], 0) + 1
    path.write_bytes(data)
    catalog = {
        "schema_version": 1,
        "file": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "first": records[0]["ordinal"],
        "last": records[-1]["ordinal"],
        "count": len(records),
        "kinds": kinds,
    }
    path.with_suffix(".json").write_text(json.dumps(catalog))
    return catalog, references


def _event_entry(
    *,
    index: int,
    catalog: dict[str, Any],
    prior_prefix: str,
    gap_rows: list[dict[str, Any]],
    campaign_id: str,
    campaign_sha256: str,
    analysis_code_sha256: str,
) -> tuple[dict[str, Any], str, str]:
    prefix = hashlib.sha256(bytes.fromhex(prior_prefix) + _canonical(catalog)).hexdigest()
    source_catalog_sha = hashlib.sha256(_canonical(catalog)).hexdigest()
    body = {
        "schema_version": 1,
        "analysis_version": GAP_VERSION,
        "analysis_code_sha256": analysis_code_sha256,
        "campaign_id": campaign_id,
        "campaign_sha256": campaign_sha256,
        "segment_index": index,
        "source_segment": catalog["file"],
        "source_segment_sha256": catalog["sha256"],
        "source_catalog": catalog,
        "source_catalog_sha256": source_catalog_sha,
        "prior_prefix_catalog_sha256": prior_prefix,
        "prefix_catalog_sha256": prefix,
        "record_count": catalog["count"],
        "source_ordinal_start": catalog["first"],
        "source_ordinal_end": catalog["last"],
        "record_kinds": catalog["kinds"],
        "gap_event_count": len(gap_rows),
        "campaign_window_gap_event_count": sum(row["in_campaign_window"] for row in gap_rows),
        "gap_events": gap_rows,
    }
    sealed = _sealed(body, "gap_event_sha256")
    chain = hashlib.sha256(bytes(32) + bytes.fromhex(sealed["gap_event_sha256"])).hexdigest()
    return sealed, prefix, chain


def _fixture(root: Path, *, include_terminal_in_index: bool = True) -> tuple[Path, Path, Path]:
    campaign_root = root / "campaign"
    raw = campaign_root / "raw"
    raw.mkdir(parents=True)
    gap_root = root / "gap-index"
    event_dir = gap_root / "gap-detail-events" / "v1"
    event_dir.mkdir(parents=True)
    code_files = _code_identity()
    code_hash = digest(code_files)

    first_records = [
        {
            "schema_version": 1,
            "ordinal": 1,
            "received_ns": 1_100,
            "monotonic_ns": 1,
            "kind": "discovery",
            "cohort": [{"id": "42", "condition": "condition-42", "tokens": ["asset-42"]}],
        },
        {
            "schema_version": 1,
            "ordinal": 2,
            "received_ns": 2_000,
            "monotonic_ns": 2,
            "kind": "gap",
            "payload": {
                "reason": "book_resynchronization",
                "affected_assets": {"asset-42": "stale"},
            },
        },
    ]
    second_records = [
        {
            "schema_version": 1,
            "ordinal": 3,
            "received_ns": 3_000,
            "monotonic_ns": 3,
            "kind": "public_market_metadata",
            "market_id": "42",
            "payload": {},
        }
    ]
    segment1 = raw / f"{1:020d}-{'1' * 32}.seg"
    catalog1, references1 = _segment(segment1, first_records)
    segment2 = raw / f"{3:020d}-{'2' * 32}.seg"
    catalog2, references2 = _segment(segment2, second_records)
    references = references1 | references2

    identity = {"raw_root": str(raw.resolve()), "start_ns": 1_000, "end_ns": 10_000}
    campaign_id = digest(identity)
    plan = {"campaign_id": campaign_id, "identity": identity}
    plan_bytes = json.dumps(plan, sort_keys=True).encode()
    campaign_root.joinpath("campaign.json").write_bytes(plan_bytes)
    campaign_sha256 = hashlib.sha256(plan_bytes).hexdigest()

    db = sqlite3.connect(campaign_root / "shadow.sqlite")
    db.executescript(
        """
        create table events(seq integer primary key,kind text,occurred_ns integer,body blob,previous_sha text,sha text);
        create table decisions(id text primary key,ns integer,condition text,market_id text,family_id text,day text,source_ordinal integer,event_seq integer,commit_ns integer,unique(condition,source_ordinal));
        create table outcomes(decision_id text,horizon integer,status text,event_seq integer,primary key(decision_id,horizon));
        """
    )
    outcome_specs = [
        ("decision-book", "42", "book_issue:gap:book_resynchronization", references[3]),
        ("decision-explicit", "42", "recorded_gap:book_resynchronization", references[2]),
        ("decision-other-market", "43", "book_issue:gap:book_resynchronization", references[3]),
    ]
    for n, (decision_id, market_id, reason, reference) in enumerate(outcome_specs, start=1):
        decision_seq = 2 * n - 1
        followup_seq = 2 * n
        db.execute(
            "insert into decisions values(?,?,?,?,?,?,?,?,?)",
            (
                decision_id,
                1_500,
                f"condition-{market_id}",
                market_id,
                "family",
                "day",
                n,
                decision_seq,
                1_500,
            ),
        )
        decision_body = canonical({"decision_id": decision_id})
        db.execute(
            "insert into events values(?,?,?,?,?,?)",
            (
                decision_seq,
                "decision",
                1_500,
                zlib.compress(decision_body),
                "0" * 64,
                f"{decision_seq:064x}",
            ),
        )
        body = {
            "campaign_id": campaign_id,
            "decision_id": decision_id,
            "horizon_ms": 1_000,
            "labels": {"status": "censored", "reason": reason},
            "termination_ref": reference,
        }
        db.execute(
            "insert into events values(?,?,?,?,?,?)",
            (
                followup_seq,
                "followup",
                4_000,
                zlib.compress(canonical(body)),
                "0" * 64,
                f"{followup_seq:064x}",
            ),
        )
        db.execute(
            "insert into outcomes values(?,?,?,?)",
            (decision_id, 1_000, "censored", followup_seq),
        )
    db.commit()
    db.close()

    gap_row = {
        "ordinal": 2,
        "received_ns": 2_000,
        "reason": "book_resynchronization",
        "in_campaign_window": True,
        "affected_asset_scope": "reported_assets",
        "affected_asset_count": 1,
        "segment_index": 1,
        "segment_file": segment1.name,
        "affected_market_ids": ["42"],
        "unmapped_affected_asset_count": 0,
    }
    gap_event1, prefix, chain = _event_entry(
        index=1,
        catalog=catalog1,
        prior_prefix="0" * 64,
        gap_rows=[gap_row],
        campaign_id=campaign_id,
        campaign_sha256=campaign_sha256,
        analysis_code_sha256=code_hash,
    )
    event_path = event_dir / f"{1:020d}.json"
    event_path.write_text(json.dumps(gap_event1))
    processed_count = 1
    processed_bytes = catalog1["bytes"]
    last_ordinal = 2
    last_segment = segment1.name
    if include_terminal_in_index:
        gap_event2, prefix, chain2 = _event_entry(
            index=2,
            catalog=catalog2,
            prior_prefix=prefix,
            gap_rows=[],
            campaign_id=campaign_id,
            campaign_sha256=campaign_sha256,
            analysis_code_sha256=code_hash,
        )
        (event_dir / f"{2:020d}.json").write_text(json.dumps(gap_event2))
        chain = hashlib.sha256(
            bytes.fromhex(chain) + bytes.fromhex(gap_event2["gap_event_sha256"])
        ).hexdigest()
        processed_count = 2
        processed_bytes += catalog2["bytes"]
        last_ordinal = 3
        last_segment = segment2.name

    state = {
        "schema_version": 1,
        "analysis_version": GAP_VERSION,
        "analysis_code_sha256": code_hash,
        "campaign_id": campaign_id,
        "campaign_sha256": campaign_sha256,
        "processed_segment_count": processed_count,
        "processed_source_bytes": processed_bytes,
        "last_ordinal": last_ordinal,
        "last_segment_file": last_segment,
        "prefix_catalog_sha256": prefix,
        "last_event_chain_sha256": chain,
    }
    gap_root.joinpath("gap-detail-state-v1.json").write_text(
        json.dumps(_sealed(state, "state_sha256"))
    )
    summary = {
        "schema_version": 1,
        "analysis_version": GAP_VERSION,
        "analysis_code_sha256": code_hash,
        "analysis_code_files": code_files,
        "campaign_id": campaign_id,
        "campaign_sha256": campaign_sha256,
        "processed_segment_count": processed_count,
        "processed_source_bytes": processed_bytes,
        "last_processed_ordinal": last_ordinal,
        "last_processed_segment_file": last_segment,
        "prefix_catalog_sha256": prefix,
        "last_event_chain_sha256": chain,
        "catalog_segment_count": 2,
        "pending_segment_count": 0 if include_terminal_in_index else 1,
        "pending_source_bytes": 0 if include_terminal_in_index else catalog2["bytes"],
        "campaign_window_gap_event_count": 1,
        "campaign_window_gap_counts_by_reason": {"book_resynchronization": 1},
        "campaign_window_affected_market_counts": {"42": 1},
        "campaign_window_unmapped_affected_asset_count": 0,
        "campaign_window_gap_events_without_reported_assets": 0,
        "campaign_window_ns": {"start": 1_000, "end_exclusive": 10_000},
        "status": "complete" if include_terminal_in_index else "catching_up",
    }
    gap_root.joinpath("gap-detail-summary-v1.json").write_text(
        json.dumps(_sealed(summary, "summary_sha256"))
    )
    return campaign_root, gap_root, event_path


def test_attribution_links_matching_prior_market_gap_and_exact_record(tmp_path: Path) -> None:
    campaign_root, gap_root, _ = _fixture(tmp_path)

    report = attribution.audit_censored_gap_attribution(campaign_root, gap_root)

    assert report["status"] == "verified_complete_prefix"
    assert report["gap_detail_index"]["indexed_campaign_gap_events"] == 1
    assert report["source_verification"]["exact_source_references_verified"] is True
    assert report["gap_censors"]["link_status_counts"] == {
        "candidate_preceding_same_market_gap": 1,
        "exact_recorded_gap_reference_verified_and_indexed": 1,
        "no_prior_same_market_gap_in_indexed_prefix": 1,
    }
    book_row = next(row for row in report["outcomes"] if row["reason"].startswith("book_issue"))
    assert book_row["link_status"] == "candidate_preceding_same_market_gap"
    assert book_row["matched_gap"]["ordinal"] == 2
    assert book_row["matched_gap"]["age_to_termination_source_ns"] == 1_000
    explicit_row = next(
        row for row in report["outcomes"] if row["reason"].startswith("recorded_gap")
    )
    assert explicit_row["link_status"] == "exact_recorded_gap_reference_verified_and_indexed"
    assert explicit_row["matched_gap"]["age_to_termination_source_ns"] == 0
    assert report["gap_censors"]["unique_candidate_preceding_gap_events"] == 1
    assert (
        report["gap_censors"]["candidate_preceding_gap_age_bands_to_termination_receiver_time_ns"][
            "0_to_1s"
        ]
        == 1
    )
    assert report["gap_censors"]["same_market_preceding_gap_is_causal_proof"] is False
    assert report["result_sha256"]


def test_partial_gap_prefix_does_not_claim_unmatched_later_censor(tmp_path: Path) -> None:
    campaign_root, gap_root, _ = _fixture(tmp_path, include_terminal_in_index=False)

    report = attribution.audit_censored_gap_attribution(campaign_root, gap_root)

    assert report["status"] == "verified_partial_prefix"
    assert report["gap_detail_index"]["last_processed_ordinal"] == 2
    assert report["gap_censors"]["link_status_counts"]["termination_after_indexed_prefix"] == 1
    assert (
        report["gap_censors"]["link_status_counts"][
            "exact_recorded_gap_reference_verified_and_indexed"
        ]
        == 1
    )


def test_attribution_rejects_tampered_gap_detail_event_digest(tmp_path: Path) -> None:
    campaign_root, gap_root, event_path = _fixture(tmp_path)
    event = json.loads(event_path.read_text())
    event["gap_event_count"] = 999
    event_path.write_text(json.dumps(event))

    with pytest.raises(ValueError, match="digest mismatch"):
        attribution.audit_censored_gap_attribution(campaign_root, gap_root)
