import json

import pytest
from midas.core.models import Source
from midas.laboratory.datasets import load_dataset, read_events, validate
from midas.market_data.polymarket import normalize_book

from scripts.capture_public_series import capture, publish_exclusive


class FakeClient:
    def __init__(self, fail=False, unsupported=False):
        self.closed = False
        self.calls = 0
        self.fail = fail
        self.raw = {
            "id": "one",
            "question": "Fixture",
            "version": "unknown" if unsupported else "v1",
            "conditionId": "0x" + "a" * 64,
            "outcomes": '["Yes","No"]',
            "clobTokenIds": '["101","202"]',
            "active": True,
            "closed": False,
            "acceptingOrders": True,
            "negRisk": False,
            "feesEnabled": False,
        }

    async def discover_wire(self, limit):
        return [self.raw], json.dumps([self.raw])

    async def book(self, asset, condition):
        self.calls += 1
        if self.fail and self.calls == 2:
            raise RuntimeError("fixture disconnect")
        raw = {
            "asset_id": asset,
            "market": condition,
            "asks": [{"price": "0.55", "size": "20"}],
            "bids": [{"price": "0.45", "size": "20"}],
            "tick_size": "0.01",
            "min_order_size": "1",
            "timestamp": str(1000 + self.calls),
        }
        return normalize_book(raw, Source.LIVE, 2000 + self.calls), raw, json.dumps(raw)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_public_capture_preserves_wire_and_publishes_valid_observations(
    tmp_path, monkeypatch
):
    async def no_wait(delay):
        return None

    monkeypatch.setattr("scripts.capture_public_series.asyncio.sleep", no_wait)
    monkeypatch.setattr("scripts.capture_public_series.now_ms", lambda: 2000)
    client = FakeClient()
    result = await capture(
        tmp_path / "captures",
        tmp_path / "datasets",
        samples=2,
        capture_id="fixture-series",
        client=client,
    )
    assert result["state"] == "COMPLETED"
    assert result["events"] == 5
    assert result["samples_completed"] == 2
    assert client.closed
    path, manifest = load_dataset(tmp_path / "datasets", "fixture-series")
    validation = validate(path, manifest)
    assert validation["valid"] and not validation["receipt_out_of_order"]
    events = read_events(path)
    assert events[0].kind == "public_metadata"
    assert not any(e.kind == "attested_metadata" for e in events)
    assert all(json.loads(e.raw_wire_json) for e in events)
    assert not manifest.market_metadata[0].payout_verified
    assert result["unique_quote_books_by_asset"] == {"101": 1, "202": 1}
    assert result["execution_labels_available"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["disconnect", "unsupported"])
async def test_incomplete_capture_retained_and_never_catalogued(tmp_path, mode):
    client = FakeClient(fail=mode == "disconnect", unsupported=mode == "unsupported")
    with pytest.raises((ValueError, RuntimeError)):
        await capture(
            tmp_path / "captures",
            tmp_path / "datasets",
            samples=2,
            capture_id="failed-series",
            client=client,
        )
    directory = tmp_path / "captures/failed-series"
    state = json.loads((directory / "state.json").read_text())
    assert state["state"] == "FAILED" and state["samples_completed"] == 0
    assert not list((tmp_path / "datasets").glob("*.manifest.json"))
    assert (directory / "discovery.json").exists()
    assert client.closed
    if mode == "disconnect":
        assert state["events"] == 2


def test_publication_cannot_replace_existing_recording(tmp_path):
    path = tmp_path / "existing.jsonl"
    publish_exclusive(path, b"original")
    with pytest.raises(FileExistsError):
        publish_exclusive(path, b"replacement")
    assert path.read_bytes() == b"original"
