#!/usr/bin/env python3
"""Create disposable campaign, source, and schema-v1 data for systemd CI."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from midas.reality.research_schema import FEATURE_VERSION, LABEL_VERSION, digest
from midas.reality.shadow_campaign import source_files
from midas.reality.storage import Store, file_hash
from midas.veritas import finalized_source_analysis as analysis

FIXTURE_ROOT = Path.home() / "midas-veritas-ci"
OUTPUT_ROOT = FIXTURE_ROOT / "output"
START = 1_792_000_000_000_000_000
CONDITION = "0x" + "1" * 64
PRODUCER_HASH = "a" * 64
LEGACY_CODE_FILES = {
    "economics.py": "0fc69b88d160acd3123bbff38ed6480d9ae9853b48429b3f739200d6cba5eda8",
    "finalized_source_analysis.py": "e6304b6547dc5d285baab4aae3940b0fe7a6828712d995bb677aad582a44f016",
    "reality/execution_research.py": "99aaf3d1f1d00a3440392f373db8b661c8420ab1bb4713fc9e4fe2340831e5c1",
    "reality/reconstruction.py": "ed7ca007f8fdb62c00aa25ebf4692e0c54eb0a9c0b06c9712e092a87c28c30cb",
    "reality/research_measurements.py": "35200c42beef6c169b7244d56d93b30229c1394217faf4dd072853814f05b084",
    "reality/research_schema.py": "fa31024164ae1e20b579403e79417c1eaa8fc2670d154153aae247546d8f9f33",
    "reality/shadow_campaign.py": "fbca040df77c90182fa7b94375590f89e95289b21e31a8990da390d1241c9aed",
    "reality/shadow_source.py": "6e0cb3811a8e32a81e9003a79de0ab778eccc28ff9e725f2163d58decf31b327",
    "reality/shadow_worker.py": "0b745947399dc33898bdba41df4f0b183ba87477f5dcddecb7ae2d26f29e3c6d",
    "reality/storage.py": "551966d10c2494dd6fcb50988bf32c26558ff6a02d6bd68617f8593b1f5ec3cc",
    "scripts/veritas_source_analysis.py": "783b4c15b2f360c134319502d2037b0bfb110a3a2b7154dbce8e2a77e2454f9d",
}


def market() -> dict:
    return dict(
        id="1",
        condition=CONDITION,
        protocol="v1",
        tokens={"11": "Yes", "12": "No"},
        payoff=dict(
            pair="same_condition_yes_no_ctf", combined_terminal_claim="1", unit="collateral_unit"
        ),
        fee_regime=dict(enabled=True, schedule=dict(rate=0.04, exponent=1, takerOnly=True)),
        event_ids=["fixture-event"],
        categories=["Fixture"],
        negative_risk=False,
        negative_risk_group=None,
        liquidity="5000",
        minimum_order_size="2",
        tick_size=".01",
        end_ns=START + 10**12,
        metadata_ordinal=2,
        public_market_constraints=dict(minimum_tick_size=".01"),
    )


def frame(yes_ask: str) -> str:
    events = []
    for token, bid, ask in (("11", ".35", yes_ask), ("12", ".50", ".55")):
        events.append(
            dict(
                event_type="book",
                asset_id=token,
                market=CONDITION,
                timestamp=str(START // 10**6),
                hash=f"fixture-{token}-{ask}",
                bids=[dict(price=bid, size="100")],
                asks=[dict(price=ask, size="20")],
            )
        )
    return json.dumps(events)


def make_research_fixture() -> tuple[Path, str]:
    raw = FIXTURE_ROOT / "raw"
    raw.mkdir(mode=0o700)
    store = Store(raw, reserve=1, segment_bytes=32 * 1024**2)
    store.rotate()
    store.append(
        "gap",
        dict(reason="process_start", reconstruction_version=4, implementation_sha256=PRODUCER_HASH),
        received_ns=START - 1_000_000_000,
        monotonic_ns=0,
    )
    store.append("public_market_metadata", "fixture metadata", received_ns=START, market_id="1")
    store.rotate()
    store.append("discovery", "fixture universe", received_ns=START, cohort=[market()])
    store.rotate()
    store.append("frame", frame(".40"), received_ns=START + 1_000_000, monotonic_ns=1_000_000)
    store.rotate()
    store.append("frame", frame(".50"), received_ns=START + 2_000_000, monotonic_ns=2_000_000)
    store.close()

    campaign_dir = FIXTURE_ROOT / "campaign"
    campaign_dir.mkdir(mode=0o700)
    identity = dict(
        version="reality-forward-campaign-v1",
        frozen_ns=START - 2 * 10**9,
        start_ns=START,
        end_ns=START + 100 * 10**6,
        raw_root=str(raw.resolve()),
        allowed_producer_hashes=[PRODUCER_HASH],
        allowed_reconstruction_versions=[4],
        feature_version=FEATURE_VERSION,
        label_version=LABEL_VERSION,
        horizons_ms=[100, 300, 1000, 5000],
        future_tolerance_ms=500,
        max_freshness_ms=5000,
        max_skew_ms=250,
        quantity="5",
        capital="100",
        code={name: file_hash(path) for name, path in source_files().items()},
    )
    plan = dict(campaign_id=digest(identity), identity=identity)
    campaign_path = campaign_dir / "campaign.json"
    campaign_path.write_text(json.dumps(plan))
    return raw, file_hash(campaign_path)


def main() -> int:
    if FIXTURE_ROOT.exists() or OUTPUT_ROOT.exists():
        raise SystemExit("refusing to overwrite existing disposable Veritas CI fixtures")
    FIXTURE_ROOT.mkdir(parents=True, mode=0o700)
    OUTPUT_ROOT.mkdir(parents=True, mode=0o700)
    source_root, campaign_sha = make_research_fixture()
    campaign_path = FIXTURE_ROOT / "campaign" / "campaign.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    # Seed disposable progress with the supported historical code identity,
    # then convert the sealed schema-v2 state to the exact v1 shape that the
    # production migration accepts. Ledger entries and provenance are created
    # by the actual candidate analyzer.
    original_identity = analysis._code_identity
    analysis._code_identity = lambda: dict(LEGACY_CODE_FILES)
    try:
        analysis.update_finalized_source_analysis(
            OUTPUT_ROOT,
            max_segments=1,
            campaign_path=campaign_path,
            expected_campaign_sha256=campaign_sha,
            expected_campaign_id=campaign["campaign_id"],
            expected_source_root=source_root,
        )
    finally:
        analysis._code_identity = original_identity
    legacy_path = OUTPUT_ROOT / "source-analysis-state-v1.json"
    current_path = OUTPUT_ROOT / "source-analysis-state-v2.json"
    current_state = json.loads(current_path.read_text(encoding="utf-8"))
    current_state.pop("state_sha256")
    current_state.pop("migration", None)
    current_state["schema_version"] = 1
    analysis._atomic_json(
        legacy_path,
        analysis._sealed(current_state, "state_sha256"),
        maximum=analysis.MAX_STATE_BYTES,
    )
    current_path.unlink()
    pressure_file = FIXTURE_ROOT / "pressure" / "io"
    pressure_file.parent.mkdir(parents=True, mode=0o700)
    pressure_file.write_text(
        "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n",
        encoding="ascii",
    )
    pristine = FIXTURE_ROOT / "recovery-v1"
    shutil.copytree(OUTPUT_ROOT, pristine)
    config = {
        "campaign_sha256": campaign_sha,
        "campaign_id": campaign["campaign_id"],
        "source_root": str(source_root),
        "campaign_path": str(campaign_path),
        "checkpoint_path": str(legacy_path),
        "checkpoint_sha256": analysis.file_hash(legacy_path),
        "event_count": len(list((OUTPUT_ROOT / "source-analysis-events" / "v1").glob("*.json"))),
        "cursor_ordinal": json.loads(legacy_path.read_text(encoding="utf-8"))["last_ordinal"],
        "pressure_file": str(pressure_file),
        "pristine_root": str(pristine),
        "output_root": str(OUTPUT_ROOT),
    }
    (FIXTURE_ROOT / "fixture.json").write_text(json.dumps(config, sort_keys=True) + "\n")
    print(json.dumps(config, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
