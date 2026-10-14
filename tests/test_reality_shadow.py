"""Explicit simulated-time fixtures; never counted as real prospective evidence."""

import copy
import json
import sqlite3
from pathlib import Path

import pytest
from midas.reality.research_schema import digest
from midas.reality.shadow_audit import audit
from midas.reality.shadow_campaign import freeze, verify
from midas.reality.shadow_report import report
from midas.reality.shadow_source import Context, Tail
from midas.reality.shadow_store import Journal
from midas.reality.shadow_worker import Shadow
from midas.reality.storage import MAGIC, atomic_json, canonical, describe, file_hash, manifest
from test_reality_foundry import START, tape


def setup(tmp_path, monkeypatch, *, gap=None, times=(0, 110, 310, 1010, 5010)):
    raw = tmp_path / "raw"
    tape(raw, times=times, gap_at=gap)
    training = tmp_path / "training"
    directory = training / "runs" / ("b" * 64)
    directory.mkdir(parents=True)
    atomic_json(directory / "report.json", dict(targets={}, state="labeled_fixture_no_model"))
    clock = [START - 10**9]
    monkeypatch.setattr("time.time_ns", lambda: clock[0])
    monkeypatch.setattr("time.monotonic_ns", lambda: 10**12 + clock[0] - START)
    root = tmp_path / "campaigns" / "fixture"
    plan = freeze(root, raw, training, "b" * 64, "a" * 64, {}, fixture=True, start_ns=START, days=1)
    worker = Shadow(root, plan)
    return worker, clock, plan


def advance(worker, clock, until=None):
    while True:
        item = worker.tail.next()
        if item is None:
            return
        row, ref = item
        clock[0] = row["received_ns"] + 10**6
        worker.consume(row, ref)
        if until == row["ordinal"]:
            return


def close(worker):
    worker.tail.close()
    worker.journal.close()


def test_live_tail_and_context_exact_checkpoint_recovery(tmp_path):
    raw = tmp_path / "raw"
    tape(raw, times=(0, 100, 200))
    tail = Tail(raw)
    context = Context()
    while item := tail.next():
        assert item[1]["canonical_record_sha256"] == digest(item[0])
        context.consume(*item)
        saved = context.snapshot()
        restored = Context.restore(json.loads(canonical(saved)))
        assert context.engine.digest() == restored.engine.digest()
        context = restored
    assert context.checkpoints == 1
    assert context.engine.last_ordinal == manifest(raw)["segments"][-1]["last"]
    tail.close()
    bad = copy.deepcopy(saved)
    bad["engine"]["gaps"] += 1
    with pytest.raises(ValueError, match="corruption"):
        Context.restore(bad)


def test_verified_empty_rotated_segments_do_not_reset_global_ordinal(tmp_path):
    raw = tmp_path / "raw"
    source = tape(raw, times=(0, 100))
    final_ordinal = source["segments"][-1]["last"]
    empty = raw / ("00000000000000000001-" + "f" * 32 + ".seg")
    empty.write_bytes(MAGIC)
    atomic_json(empty.with_suffix(".json"), describe(empty))
    tail = Tail(raw)
    seen = []
    while item := tail.next():
        seen.append(item[0]["ordinal"])
    assert seen == list(range(1, final_ordinal + 1))
    assert tail.cursor["ordinal"] == final_ordinal
    tail.close()


def test_frozen_prospective_decision_and_independent_public_followup(tmp_path, monkeypatch):
    worker, clock, plan = setup(tmp_path, monkeypatch)
    advance(worker, clock)
    assert worker.journal.summary()["decisions"] == 1
    seq, commit = worker.journal.db.execute("select event_seq,commit_ns from decisions").fetchone()
    decision = worker.journal.event(seq)
    assert plan["identity"]["frozen_ns"] < plan["identity"]["start_ns"] <= decision["decision_ns"]
    assert commit >= decision["decision_ns"]
    hseq = worker.journal.db.execute("select event_seq from outcomes where horizon=100").fetchone()[
        0
    ]
    result = worker.journal.event(hseq)
    assert result["labels"]["quote_persistence"] is False
    assert result["labels"]["depth_at_original_quotes"] == {"yes": "0", "no": "7"}
    assert float(result["labels"]["displayed_acquisition_cost"]) == 5.0
    assert result["effective_delays_ms"] == {"yes": 109.0, "no": 109.0}
    assert min(result["observed_future_received_ns"].values()) > commit
    assert result["taxonomy"]["actual_fills"] == "unknown_counterfactual"
    assert all(p["orders_submitted"] is False for p in decision["policies"])
    assert (
        next(p for p in decision["policies"] if p["policy"] == "prediction_gate")["reason"]
        == "insufficient_model_evidence"
    )
    assert (
        next(p for p in decision["policies"] if p["policy"] == "prometheus_control")["action"]
        == "abstain"
    )
    assert worker.journal.verify()["sqlite_integrity"] == "ok"
    proof = audit(worker.root)
    assert proof["prospective_decisions"] == 1
    assert proof["valid_decisions_raw_replayed"] == 1
    assert proof["observed_followups_independently_checked"] == 4
    summary = report(worker.root)
    assert summary["coverage"]["decisions"] == 1
    assert summary["policy_actions"]["no_trade"] == {"abstain": 1}
    assert summary["horizons"]["100"]["conditional_persistence"] == 0
    assert summary["actual_fills"] == "unknown_counterfactual"
    assert summary["realized_money"] is None
    close(worker)


def test_future_mutation_cannot_alter_persisted_decision(tmp_path, monkeypatch):
    worker, clock, _ = setup(tmp_path, monkeypatch)
    advance(worker, clock, until=4)
    seq = worker.journal.db.execute("select event_seq from decisions").fetchone()[0]
    frozen = worker.journal.event(seq)
    advance(worker, clock)
    assert worker.journal.event(seq) == frozen
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        worker.journal.db.execute("update events set occurred_ns=0 where seq=?", (seq,))
    close(worker)


def test_gap_and_partial_future_are_unknown_not_negative(tmp_path, monkeypatch):
    worker, clock, _ = setup(tmp_path, monkeypatch, gap=110)
    advance(worker, clock)
    result = worker.journal.event(
        worker.journal.db.execute("select event_seq from outcomes where horizon=100").fetchone()[0]
    )
    assert result["labels"]["status"] == "censored"
    assert result["labels"]["quote_persistence"] is None
    assert result["labels"]["market_disruption"] is True
    close(worker)


def test_restart_preserves_exact_source_cursor_pending_and_no_duplicate_decision(
    tmp_path, monkeypatch
):
    worker, clock, plan = setup(tmp_path, monkeypatch)
    advance(worker, clock, until=4)
    worker.save()
    root = worker.root
    before = file_hash(root / "campaign.json")
    close(worker)
    restored = Shadow(root, plan)
    advance(restored, clock)
    assert restored.journal.summary()["decisions"] == 1
    assert restored.journal.summary()["followups"]["observed_public_measurement"] >= 1
    assert restored.ctx.checkpoints == 1
    assert file_hash(root / "campaign.json") == before
    close(restored)


def test_unavailable_future_timeout_stays_unknown_and_caught_up_only(tmp_path, monkeypatch):
    worker, clock, _ = setup(tmp_path, monkeypatch, times=(0,))
    advance(worker, clock)
    clock[0] = START + 8 * 10**9
    worker.expire_unavailable(clock[0])
    outcomes = [
        worker.journal.event(seq)
        for (seq,) in worker.journal.db.execute("select event_seq from outcomes")
    ]
    assert len(outcomes) == 4
    assert all(r["labels"]["quote_persistence"] is None for r in outcomes)
    assert not worker.pending
    close(worker)


def test_frozen_campaign_corruption_and_overlap_are_rejected(tmp_path, monkeypatch):
    worker, clock, plan = setup(tmp_path, monkeypatch)
    changed = copy.deepcopy(plan)
    changed["identity"]["risk"]["persistence_threshold"] = 0.1
    with pytest.raises(ValueError, match="corruption"):
        verify(changed)
    with pytest.raises(ValueError, match="overlaps"):
        freeze(
            tmp_path / "campaigns" / "other",
            Path(plan["identity"]["raw_root"]),
            Path(plan["identity"]["training_root"]),
            "b" * 64,
            "a" * 64,
            {},
            fixture=True,
            start_ns=START,
            days=1,
        )
    close(worker)


def test_corrupt_event_bytes_are_detected_independently(tmp_path):
    store = Journal(tmp_path, budget=16 * 1024**2, reserve=1)
    with store.db:
        store.append("fixture", dict(observed=1))
    store.db.execute("drop trigger immutable_events_update")
    with store.db:
        store.db.execute("update events set sha=?", ("f" * 64,))
    with pytest.raises(ValueError, match="hash-chain"):
        store.verify()
    store.close()
