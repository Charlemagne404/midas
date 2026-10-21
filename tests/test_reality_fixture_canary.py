"""The local collector canary must adapt the observed fixture envelope."""

import json
from pathlib import Path

import pytest

from scripts.reality_fixture_canary import (
    FIXTURE_PATH,
    build_markets,
    cgroup_directory,
    fresh_book_count_at_boundary,
    full_book_coverage_seconds,
    manifest_record_count,
    parse_event_counts,
    parse_pressure,
    pressure_peaks,
    select_book_template,
)


def test_book_template_selects_event_from_array_payload():
    fixture = json.loads(FIXTURE_PATH.read_text())
    decoded = json.loads(fixture["frames"][0]["payload"])
    expected = next(event for event in decoded if event["event_type"] == "book")

    template = select_book_template(fixture)

    assert template == {"bids": expected["bids"], "asks": expected["asks"]}
    assert template["bids"]
    assert template["asks"]


def test_book_template_rejects_fixture_without_two_sided_book():
    fixture = {"frames": [{"payload": json.dumps([{"event_type": "last_trade_price"}])}]}
    with pytest.raises(ValueError, match="no book event"):
        select_book_template(fixture)


def test_synthetic_expansion_fixture_fills_ten_market_panel():
    from midas.reality.panel import select_panel

    markets, _ = build_markets()
    selected, _ = select_panel(
        markets,
        10,
        now_ns=1_792_589_900_000_000_000,
        seed=20261014,
    )

    assert len(selected) == 10
    assert len({market["liquidity"] for market in selected}) >= 3


def test_full_book_coverage_uses_last_first_update_across_all_tokens():
    status = {
        "started_ns": 1_000_000_000,
        "expected_books": 2,
        "observation_coverage": {
            "token-a": {"first_received_ns": 1_200_000_000},
            "token-b": {"first_received_ns": 2_250_000_000},
        },
    }

    assert full_book_coverage_seconds(status) == 1.25


def test_full_book_coverage_rejects_incomplete_or_pre_start_timestamps():
    incomplete = {
        "started_ns": 1_000,
        "observation_coverage": {"token-a": {"first_received_ns": None}},
    }
    pre_start = {
        "started_ns": 1_000,
        "expected_books": 1,
        "observation_coverage": {"token-a": {"first_received_ns": 999}},
    }

    assert full_book_coverage_seconds(incomplete) is None
    assert full_book_coverage_seconds(pre_start) is None


def test_full_book_coverage_requires_every_expected_token():
    status = {
        "started_ns": 1_000,
        "expected_books": 2,
        "observation_coverage": {"token-a": {"first_received_ns": 1_100}},
    }

    assert full_book_coverage_seconds(status) is None


def test_fresh_book_count_uses_pre_shutdown_durable_boundary():
    state = {
        "books": {
            "fresh": {"internally_consistent": True, "received_ns": 90},
            "inconsistent": {"internally_consistent": False, "received_ns": 99},
            "stale": {"internally_consistent": True, "received_ns": 1},
        }
    }

    assert fresh_book_count_at_boundary(state, boundary_ns=100, stale_seconds=0.00000002) == (
        1,
        3,
    )


def test_fresh_book_count_rejects_missing_or_invalid_boundary():
    with pytest.raises(ValueError, match="pre-shutdown"):
        fresh_book_count_at_boundary({}, boundary_ns=100, stale_seconds=60)
    with pytest.raises(ValueError, match="pre-shutdown"):
        fresh_book_count_at_boundary({"books": {}}, boundary_ns=True, stale_seconds=60)


def test_manifest_record_count_uses_finalized_segment_index():
    assert manifest_record_count({"segments": [{"count": 3}, {"count": 5}]}) == 8


def test_manifest_record_count_rejects_invalid_indexes():
    with pytest.raises(ValueError, match="segment"):
        manifest_record_count({})
    with pytest.raises(ValueError, match="invalid segment"):
        manifest_record_count({"segments": [{"count": True}]})


def test_cgroup_directory_resolves_unified_hierarchy():
    contents = "12:memory:/legacy\n0::/user.slice/user-1000.slice/job.service\n"

    assert cgroup_directory(contents, root=Path("/cg")) == Path(
        "/cg/user.slice/user-1000.slice/job.service"
    )
    assert cgroup_directory("12:memory:/legacy\n") is None


def test_cgroup_directory_rejects_path_traversal():
    with pytest.raises(ValueError, match="Invalid cgroup"):
        cgroup_directory("0::/user.slice/../../etc")


def test_event_counters_parse_zero_as_integer():
    events = parse_event_counts("high 12\nmax 0\noom 0\n")

    assert events == {"high": 12, "max": 0, "oom": 0}
    assert not events["max"]


def test_event_counters_reject_invalid_values():
    with pytest.raises(ValueError, match="event counter"):
        parse_event_counts("oom -1\n")


def test_pressure_parser_and_peak_summary():
    contents = "some avg10=0.50 avg60=0.25 avg300=0.10 total=20\nfull avg10=0.10 avg60=0.05 avg300=0.02 total=5\n"
    assert parse_pressure(contents)["some"]["avg10"] == 0.5
    peaks = pressure_peaks(
        [{"io.pressure": contents}, {"io.pressure": contents.replace("0.50", "1.50")}],
        "io.pressure",
    )
    assert peaks["some_avg10_max_percent"] == 1.5
    assert peaks["full_avg60_max_percent"] == 0.05


def test_pressure_parser_rejects_invalid_values():
    with pytest.raises(ValueError, match="pressure sample"):
        parse_pressure("some avg10=invalid\n")
