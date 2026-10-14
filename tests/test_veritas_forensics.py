import hashlib
import json
import sqlite3
import zlib
from pathlib import Path

import pytest
from midas.reality.research_schema import digest
from midas.reality.storage import canonical
from midas.veritas.forensics import analyze_forward_campaign


def write_campaign(root: Path) -> None:
    identity = {"horizons_ms": [100, 300], "source_kind": "genuine_public_recording"}
    (root / "campaign.json").write_text(
        json.dumps({"campaign_id": digest(identity), "identity": identity})
    )
    db = sqlite3.connect(root / "shadow.sqlite")
    db.executescript(
        """
        create table events(seq integer primary key,kind text,occurred_ns integer,body blob,previous_sha text,sha text);
        create table decisions(id text primary key,ns integer,condition text,market_id text,family_id text,day text,source_ordinal integer,event_seq integer,commit_ns integer);
        create table outcomes(decision_id text,horizon integer,status text,event_seq integer,primary key(decision_id,horizon));
        """
    )
    previous = "0" * 64

    def append(kind: str, body: dict, when: int) -> int:
        nonlocal previous
        encoded = canonical(body)
        sha = digest([previous, kind, when, hashlib.sha256(encoded).hexdigest()])
        cursor = db.execute(
            "insert into events(kind,occurred_ns,body,previous_sha,sha) values(?,?,?,?,?)",
            (kind, when, zlib.compress(encoded), previous, sha),
        )
        previous = sha
        return int(cursor.lastrowid)

    valid = {
        "id": "a" * 64,
        "decision_ns": 1000,
        "condition": "condition-a",
        "market_id": "market-a",
        "family_id": "family-a",
        "day_utc": "2026-10-14",
        "features": {
            "theoretical_edge_per_unit_before_fees": "-0.02",
            "market": {"categories": ["Politics"]},
        },
        "baseline": {"opportunity": False},
        "quality_reason": None,
        "policies": [
            {"policy": "test", "action": "abstain", "reason": "no_initial_supported_discrepancy"}
        ],
    }
    invalid = {
        "id": "b" * 64,
        "decision_ns": 2000,
        "condition": "condition-b",
        "market_id": "market-b",
        "family_id": "family-b",
        "day_utc": "2026-10-14",
        "features": None,
        "baseline": None,
        "quality_reason": "stale_book",
        "policies": [{"policy": "test", "action": "abstain", "reason": "stale_book"}],
    }
    for item in (valid, invalid):
        event_seq = append("decision", item, item["decision_ns"])
        db.execute(
            "insert into decisions values(?,?,?,?,?,?,?,?,?)",
            (
                item["id"],
                item["decision_ns"],
                item["condition"],
                item["market_id"],
                item["family_id"],
                item["day_utc"],
                event_seq,
                event_seq,
                item["decision_ns"] + 1,
            ),
        )
    followups = [
        (valid["id"], 100, "observed_public_measurement", None),
        (valid["id"], 300, "censored", "future_observation_unavailable"),
        (invalid["id"], 100, "censored", "invalid_at_decision"),
        (invalid["id"], 300, "censored", "invalid_at_decision"),
    ]
    for uid, horizon, status, reason in followups:
        event = {
            "decision_id": uid,
            "horizon_ms": horizon,
            "labels": {"status": status, "reason": reason},
        }
        event_seq = append("followup", event, 3000 + horizon)
        db.execute("insert into outcomes values(?,?,?,?)", (uid, horizon, status, event_seq))
    db.commit()
    db.close()


def test_forward_forensics_separates_initial_invalid_from_future_censoring(tmp_path):
    write_campaign(tmp_path)

    report = analyze_forward_campaign(tmp_path)

    assert report["coverage"]["decisions"] == 2
    assert report["coverage"]["valid_initial_decisions"] == 1
    assert report["coverage"]["invalid_initial_decisions"] == 1
    assert report["decision_quality_reasons"] == {"eligible": 1, "stale_book": 1}
    assert report["outcomes"]["counts_by_status"] == {
        "observed_public_measurement": 1,
        "censored": 3,
    }
    assert report["outcomes"]["censor_reasons_by_initial_validity"] == {
        "valid_initial_state": {"future_observation_unavailable": 1},
        "invalid_initial_state": {"invalid_at_decision": 2},
    }
    assert report["actual_orders_submitted"] == 0
    assert report["realized_money"] is None


def test_forward_forensics_reads_sqlite_without_changing_it(tmp_path):
    write_campaign(tmp_path)
    path = tmp_path / "shadow.sqlite"
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    report = analyze_forward_campaign(tmp_path)

    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["journal_snapshot"]["read_only"] is True
    assert report["journal_snapshot"]["sqlite_integrity_check"] == {
        "performed": False,
        "result": None,
    }
    assert before == after


def test_forward_forensics_can_run_an_explicit_integrity_check(tmp_path):
    write_campaign(tmp_path)

    report = analyze_forward_campaign(tmp_path, verify_database_integrity=True)

    assert report["journal_snapshot"]["sqlite_integrity_check"] == {
        "performed": True,
        "result": "ok",
    }


def test_forward_forensics_bounds_query_size(tmp_path):
    write_campaign(tmp_path)

    with pytest.raises(ValueError, match="Unbounded"):
        analyze_forward_campaign(tmp_path, limit=50_001)


def test_forward_forensics_rejects_changed_frozen_identity(tmp_path):
    write_campaign(tmp_path)
    path = tmp_path / "campaign.json"
    plan = json.loads(path.read_text())
    plan["identity"]["source_kind"] = "changed"
    path.write_text(json.dumps(plan))

    with pytest.raises(ValueError, match="identity hash"):
        analyze_forward_campaign(tmp_path)


def test_forward_forensics_rejects_mismatched_event_kind(tmp_path):
    write_campaign(tmp_path)
    db = sqlite3.connect(tmp_path / "shadow.sqlite")
    row = db.execute("select event_seq from decisions where id=?", ("a" * 64,)).fetchone()
    db.execute("update events set kind='followup' where seq=?", row)
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="non-decision event"):
        analyze_forward_campaign(tmp_path)
