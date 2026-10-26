import json

from midas.reality.reconstruction import Engine

from scripts.reality_source_anomaly_audit import ReplayAnomalyAudit

ASSET = "token-a"
ASSET_B = "token-b"
CONDITION = "condition-a"


def frame(ordinal, received_ns, event):
    return {
        "ordinal": ordinal,
        "received_ns": received_ns,
        "kind": "frame",
        "payload": json.dumps(event, sort_keys=True),
    }


def source_records():
    book = {
        "event_type": "book",
        "asset_id": ASSET,
        "market": CONDITION,
        "timestamp": "10",
        "hash": "native-book-hash",
        "bids": [{"price": "0.6", "size": "1"}],
        "asks": [{"price": "0.5", "size": "1"}],
    }
    return [
        {
            "ordinal": 1,
            "received_ns": 1,
            "kind": "gap",
            "payload": {"reason": "process_start", "reconstruction_version": 5},
        },
        {
            "ordinal": 2,
            "received_ns": 2,
            "kind": "discovery",
            "cohort": [{"condition": CONDITION, "tokens": [ASSET]}],
        },
        frame(3, 3, book),
        frame(4, 4, book),
        frame(
            5,
            5,
            {
                "event_type": "price_change",
                "market": CONDITION,
                "timestamp": "9",
                "price_changes": [{"asset_id": ASSET, "side": "BUY", "price": "0.7", "size": "2"}],
            },
        ),
        {
            "ordinal": 6,
            "received_ns": 6,
            "kind": "gap",
            "payload": {"reason": "book_resynchronization"},
        },
        frame(7, 7, {**book, "timestamp": "9", "hash": "replacement-book-hash"}),
    ]


def replay_fixture(records, audit=None):
    engine = Engine()
    original_event = Engine.event
    original_consume = Engine.consume
    if audit is not None:

        def audited_event(current, raw, record, index):
            return audit.wrap_event(current, raw, record, index, original_event)

        def audited_consume(current, record):
            return audit.wrap_consume(current, record, original_consume)

        Engine.event = audited_event
        Engine.consume = audited_consume
    try:
        for record in records:
            engine.consume(record)
    finally:
        Engine.event = original_event
        Engine.consume = original_consume
    return engine


def test_anomaly_audit_is_observational_and_localizes_replay_signals():
    records = source_records()
    baseline = replay_fixture(records)
    audit = ReplayAnomalyAudit()
    observed = replay_fixture(records, audit)

    assert observed.digest() == baseline.digest()
    assert observed.counts == baseline.counts
    assert audit.document()["counts"] == {
        "duplicate": 1,
        "timestamp_regression": 1,
        "snapshot_source_time_regression_after_gap": 1,
        "crossed": 3,
    }
    assert audit.examples["duplicate"][0]["duplicate_of"] == {
        "ordinal": 3,
        "event_index": 0,
        "event_type": "book",
    }
    assert (
        audit.examples["timestamp_regression"][0]["assets"][0]["incoming_source_timestamp_ms"] == 9
    )
    assert (
        audit.examples["snapshot_source_time_regression_after_gap"][0]["assets"][0][
            "last_gap_ordinal"
        ]
        == 6
    )
    assert audit.examples["crossed"][0]["assets"][0]["current"]["top"] == {
        "bid": "0.6",
        "ask": "0.5",
    }


def test_anomaly_audit_counts_each_affected_asset_in_batched_events():
    def book(asset):
        return {
            "event_type": "book",
            "asset_id": asset,
            "market": CONDITION,
            "timestamp": "10",
            "bids": [{"price": "0.4", "size": "1"}],
            "asks": [{"price": "0.6", "size": "1"}],
        }

    records = [
        {
            "ordinal": 1,
            "received_ns": 1,
            "kind": "gap",
            "payload": {"reason": "process_start", "reconstruction_version": 5},
        },
        {
            "ordinal": 2,
            "received_ns": 2,
            "kind": "discovery",
            "cohort": [{"condition": CONDITION, "tokens": [ASSET, ASSET_B]}],
        },
        frame(3, 3, book(ASSET)),
        frame(4, 4, book(ASSET_B)),
        frame(
            5,
            5,
            {
                "event_type": "price_change",
                "market": CONDITION,
                "timestamp": "9",
                "price_changes": [
                    {"asset_id": ASSET, "side": "BUY", "price": "0.5", "size": "2"},
                    {"asset_id": ASSET_B, "side": "BUY", "price": "0.5", "size": "2"},
                ],
            },
        ),
    ]
    audit = ReplayAnomalyAudit()

    engine = replay_fixture(records, audit)

    assert engine.counts["timestamp_regression"] == 2
    assert audit.document()["counts"]["timestamp_regression"] == 2
    assert audit.document()["by_event_type"]["timestamp_regression"] == {"price_change": 2}
    assert audit.examples["timestamp_regression"][0]["count_delta"] == 2
