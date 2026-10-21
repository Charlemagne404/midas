"""The local collector canary must adapt the observed fixture envelope."""

import json

import pytest

from scripts.reality_fixture_canary import (
    FIXTURE_PATH,
    full_book_coverage_seconds,
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
