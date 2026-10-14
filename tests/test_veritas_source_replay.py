"""Synthetic source replay checks; no live Reality observations are fixtures."""

from __future__ import annotations

import json
import sqlite3
import zlib
from pathlib import Path
from typing import Any

import pytest
from midas.reality.foundry import source_records
from midas.reality.research_measurements import features, pair_quality
from midas.reality.research_schema import FEATURE_VERSION, LABEL_VERSION, digest
from midas.reality.shadow_campaign import source_files
from midas.reality.shadow_source import Context
from midas.reality.shadow_worker import spec_for
from midas.reality.storage import Store, canonical, file_hash, manifest
from midas.veritas.source_replay import MAX_DECISIONS, _lag_band, reconcile_forward_sources

START = 1_792_000_000_000_000_000
CONDITION = "0x" + "1" * 64
CONDITION_TWO = "0x" + "2" * 64


def test_lag_bands_respect_the_frozen_limit():
    assert _lag_band(250 * 10**6, 250 * 10**6) == "100_ms_to_limit"
    assert _lag_band(251 * 10**6, 250 * 10**6) == "above_frozen_limit"
    assert _lag_band(51 * 10**6, 50 * 10**6) == "above_frozen_limit"


def _market(
    market_id: str = "1",
    condition: str = CONDITION,
    yes_token: str = "11",
    no_token: str = "12",
) -> dict[str, Any]:
    return dict(
        id=market_id,
        condition=condition,
        protocol="v1",
        tokens={yes_token: "Yes", no_token: "No"},
        payoff=dict(
            pair="same_condition_yes_no_ctf", combined_terminal_claim="1", unit="collateral_unit"
        ),
        fee_regime=dict(enabled=True, schedule=dict(rate=0.04, exponent=1, takerOnly=True)),
        event_ids=["fixture-event"],
        categories=["Fixture"],
        negative_risk=False,
        negative_risk_group=None,
        liquidity="5000",
        minimum_order_size="5",
        tick_size=".01",
        end_ns=START + 10**12,
        metadata_ordinal=2,
        public_market_constraints=dict(minimum_tick_size=".01"),
    )


def _frame() -> str:
    events = []
    for condition, tokens in (
        (CONDITION, (("11", ".35", ".40", "10"), ("12", ".50", ".55", "20"))),
        (CONDITION_TWO, (("21", ".35", ".40", "10"), ("22", ".50", ".55", "20"))),
    ):
        for token, bid, ask, size in tokens:
            events.append(
                dict(
                    event_type="book",
                    asset_id=token,
                    market=condition,
                    timestamp=str(START // 10**6),
                    hash="fixture-native-" + token,
                    bids=[dict(price=bid, size="100")],
                    asks=[dict(price=ask, size=size)],
                )
            )
    return json.dumps(events)


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    raw = tmp_path / "raw"
    raw.mkdir()
    store = Store(raw, reserve=1)
    producer_hash = "a" * 64
    store.append(
        "gap",
        dict(reason="process_start", reconstruction_version=4, implementation_sha256=producer_hash),
        received_ns=START,
        monotonic_ns=0,
    )
    store.append(
        "public_market_metadata",
        "fixture metadata",
        received_ns=START,
        monotonic_ns=0,
        market_id="1",
    )
    store.append(
        "discovery",
        "fixture universe",
        received_ns=START,
        monotonic_ns=0,
        cohort=[_market(), _market("2", CONDITION_TWO, "21", "22")],
    )
    frame = store.append("frame", _frame(), received_ns=START + 10**6, monotonic_ns=10**6)
    store.close()
    source = manifest(raw)

    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    identity = dict(
        version="reality-forward-campaign-v1",
        frozen_ns=START - 10 * 10**9,
        start_ns=START - 5 * 10**9,
        end_ns=START + 50 * 10**9,
        raw_root=str(raw.resolve()),
        allowed_producer_hashes=[producer_hash],
        allowed_reconstruction_versions=[4],
        feature_version=FEATURE_VERSION,
        label_version=LABEL_VERSION,
        horizons_ms=[100, 300, 1000, 5000],
        future_tolerance_ms=500,
        max_freshness_ms=5000,
        max_skew_ms=250,
        max_decision_input_lag_ms=250,
        quantity="5",
        capital="100",
        code={name: _hash(path) for name, path in source_files().items()},
    )
    campaign_id = digest(identity)
    plan = dict(campaign_id=campaign_id, identity=identity)
    (campaign_root / "campaign.json").write_text(json.dumps(plan))

    ctx = Context()
    rows = []
    for record, ref in source_records(raw, source):
        ctx.consume(record, ref)
        if record["ordinal"] != frame["ordinal"]:
            continue
        for condition, market in ctx.cohort.items():
            decision_ns = record["received_ns"] + 10**6
            reason = pair_quality(market, ctx.engine.books, decision_ns, spec_for(plan))
            actual_features = actual_baseline = None
            if reason is None:
                actual_features, actual_baseline = features(
                    market,
                    ctx.engine.books,
                    decision_ns=decision_ns,
                    spec=spec_for(plan),
                    history={token: list(history) for token, history in ctx.history.items()},
                    trades=ctx.trades,
                )
            rows.append(
                dict(
                    schema_version=1,
                    campaign_id=campaign_id,
                    id=digest([campaign_id, condition, record["ordinal"]]),
                    condition=condition,
                    market_id=market["id"],
                    decision_ns=decision_ns,
                    source_input_lag_ns=decision_ns - record["received_ns"],
                    decision_ordinal=record["ordinal"],
                    source_record_ref={
                        **ref,
                        "segment_sha256": None,
                        "segment_seal_status": "pending_until_finalization",
                    },
                    source_state_sha256=ctx.engine.digest(),
                    producer_implementation_sha256=ctx.producer_hash,
                    reconstruction_version=ctx.engine.reconstruction_version,
                    quality_reason=reason,
                    features=actual_features,
                    baseline=actual_baseline,
                    feature_sources=ctx.lineage(market),
                )
            )
    assert len(rows) == 2

    db = sqlite3.connect(campaign_root / "shadow.sqlite")
    db.executescript(
        "create table events(seq integer primary key,kind text,occurred_ns integer,body blob);"
        "create table decisions(source_ordinal integer,id text,ns integer,condition text,market_id text,event_seq integer,unique(condition,source_ordinal));"
    )
    for event_seq, row in enumerate(rows, 1):
        db.execute(
            "insert into events values(?,'decision',?,?)",
            (event_seq, row["decision_ns"], zlib.compress(canonical(row))),
        )
        db.execute(
            "insert into decisions values(?,?,?,?,?,?)",
            (
                row["decision_ordinal"],
                row["id"],
                row["decision_ns"],
                row["condition"],
                row["market_id"],
                event_seq,
            ),
        )
    db.commit()
    db.close()
    return campaign_root, raw, rows


def _hash(path: Path) -> str:
    return file_hash(path)


def test_reconciles_finalized_records_and_ignores_active_segment(tmp_path):
    campaign, raw, rows = _fixture(tmp_path)
    (raw / "99999999999999999999-active.open").write_bytes(b"not a segment; do not open")

    report = reconcile_forward_sources(campaign, limit=5)

    assert report["passed_for_finalized_prefix"]
    assert report["active_segment_read"] is False
    assert report["source_segments"] == 1
    assert report["decision_sample_rows"] == len(rows)
    assert report["decisions_reproduced"] == len(rows)
    assert report["decisions_uncovered_after_finalized_prefix"] == 0
    assert report["source_lineage_references_expected"] > 0
    assert (
        report["source_lineage_references_resolved"] == report["source_lineage_references_expected"]
    )
    assert report["mismatches"] == {}
    timing = report["decision_timing"]["all"]
    assert timing["decisions"] == len(rows)
    assert timing["source_input_lag_ms"]["p50_nearest_rank_ms"] == "1"
    assert timing["maximum_leg_age_ms"]["maximum_ms"] == "1"
    assert timing["cross_outcome_skew_ms"]["maximum_ms"] == "0"
    assert report["decision_timing"]["by_quality_reason"]["eligible"]["decisions"] == len(rows)
    assert report["decision_timing"]["by_market"]["1"]["decisions"] == 1
    assert report["decision_timing"]["by_market"]["2"]["decisions"] == 1
    assert report["analysis_version"] == "veritas-source-replay-v2"


def test_reports_source_state_divergence(tmp_path):
    campaign, _, rows = _fixture(tmp_path)
    row = rows[0]
    row["source_state_sha256"] = "0" * 64
    db = sqlite3.connect(campaign / "shadow.sqlite")
    db.execute("update events set body=? where seq=1", (zlib.compress(canonical(row)),))
    db.commit()
    db.close()

    report = reconcile_forward_sources(campaign, limit=5)

    assert not report["passed_for_finalized_prefix"]
    assert report["mismatches"] == {"source_state_sha256": 1}


def test_replay_limits_are_enforced_before_io(tmp_path):
    with pytest.raises(ValueError, match="sample must be bounded"):
        reconcile_forward_sources(tmp_path / "missing", limit=MAX_DECISIONS + 1)
