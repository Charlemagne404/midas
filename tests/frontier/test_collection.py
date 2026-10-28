from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import timedelta
from decimal import Decimal
from multiprocessing import get_context
from multiprocessing.connection import Connection
from pathlib import Path

import pytest
from midas.frontier.adapters.base import (
    AdapterError,
    RejectedResponseEvidence,
    build_capabilities,
)
from midas.frontier.adapters.coinbase import CoinbaseSpotConfig
from midas.frontier.adapters.kraken import KrakenSpotConfig
from midas.frontier.collection import (
    BoundedSourceCollector,
    CollectionCheckpoint,
    CollectionJournal,
    CollectionRunSpec,
    CollectionSourceBusy,
)
from midas.frontier.models import (
    COINBASE_MARKET_DATA_TERMS_VERSION,
    AdapterConfig,
    BookLevel,
    Capability,
    FrontierModel,
    MarketBatch,
    RawObservation,
    SourceHealth,
    SourceState,
    Venue,
)
from midas.frontier.storage import FrontierStore, FrontierStoreError

from tests.frontier.builders import T0, book, market


class FakeTransport:
    def __init__(self) -> None:
        self.request_count = 0


class FakeAdapter:
    venue = Venue.POLYMARKET

    def __init__(
        self,
        *,
        fail_instruments: set[str] | None = None,
        fail_discovery: bool = False,
        enabled: bool = True,
        venue: Venue = Venue.POLYMARKET,
        config: AdapterConfig | None = None,
    ) -> None:
        self.venue = venue
        self.config = config or AdapterConfig(enabled=enabled, live_public_probe_enabled=enabled)
        self.capabilities = build_capabilities(
            self.venue,
            "fixture-adapter-1",
            {
                Capability.MARKET_DISCOVERY: ("Fixture discovery", None),
                Capability.BOOK_SNAPSHOT: ("Fixture book snapshot", None),
            },
        )
        self.transport = FakeTransport()
        self.fail_instruments = fail_instruments or set()
        self.fail_discovery = fail_discovery
        self.failures: list[tuple[str, str]] = []
        self.market_values = (market(self.venue, "collection-fixture"),)
        self.market_capture: RawObservation | None = None
        self.pending_captures: list[RawObservation] = []
        self.discovery_calls = 0
        self.book_calls: list[str] = []

    @staticmethod
    def _raw(kind: str, identity: str, venue: Venue = Venue.POLYMARKET) -> RawObservation:
        body = json.dumps({"kind": kind, "identity": identity}, sort_keys=True)
        return RawObservation(
            venue=venue,
            observation_kind=kind,
            request_url=f"https://fixture.example/{kind}/{identity}",
            http_status=200,
            request_started_at_utc=T0,
            received_at_utc=T0,
            raw_body=body,
            raw_sha256=hashlib.sha256(body.encode()).hexdigest(),
            adapter_version="fixture-adapter-1",
        )

    async def health(self) -> SourceHealth:
        return SourceHealth(
            venue=self.venue,
            state=SourceState.DEGRADED if self.failures else SourceState.HEALTHY,
            supported_capabilities=(Capability.MARKET_DISCOVERY, Capability.BOOK_SNAPSHOT),
            unsupported_capabilities=tuple(
                item
                for item in Capability
                if item not in {Capability.MARKET_DISCOVERY, Capability.BOOK_SNAPSHOT}
            ),
        )

    async def discover_markets(self, limit: int = 20):
        self.transport.request_count += 1
        self.discovery_calls += 1
        if self.fail_discovery:
            raise AdapterError("FIXTURE_DISCOVERY_FAILURE", "Fixture source discovery failed")
        self.market_capture = self._raw("market_listing", "one", self.venue)
        self.pending_captures.append(self.market_capture)
        value = self.market_values[0]
        provenance = value.provenance.model_copy(
            update={
                "raw_sha256": self.market_capture.raw_sha256,
                "observation_id": "fixture-market",
            }
        )
        self.market_values = (value.model_copy(update={"provenance": provenance}),)
        return self.market_values[:limit]

    async def fetch_book(self, market_value, instrument_id: str, depth: int = 20):
        self.transport.request_count += 1
        self.book_calls.append(instrument_id)
        if instrument_id in self.fail_instruments:
            raise AdapterError("FIXTURE_BOOK_FAILURE", "Fixture book request failed")
        capture = self._raw("book_snapshot", instrument_id, self.venue)
        self.pending_captures.append(capture)
        value = book(market_value, instrument_id, "0.40")
        provenance = value.provenance.model_copy(
            update={"raw_sha256": capture.raw_sha256, "observation_id": capture.raw_sha256}
        )
        return value.model_copy(update={"provenance": provenance})

    def take_captures(self) -> tuple[RawObservation, ...]:
        result = tuple(self.pending_captures)
        self.pending_captures.clear()
        return result

    def report_failure(self, code: str, message: str) -> None:
        self.failures.append((code, message))


class FailOnceStore(FrontierStore):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.fail_once = True

    def append_observation(self, raw: RawObservation, normalized: FrontierModel) -> str:
        if self.fail_once:
            self.fail_once = False
            raise FrontierStoreError("Fixture storage interruption")
        return super().append_observation(raw, normalized)


class BlockingAdapter(FakeAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.discovery_entered = asyncio.Event()
        self.block_discovery = True

    async def discover_markets(self, limit: int = 20):
        if self.block_discovery:
            self.block_discovery = False
            self.discovery_entered.set()
            await asyncio.Event().wait()
        return await super().discover_markets(limit)


class StalledHealthAdapter(FakeAdapter):
    async def health(self) -> SourceHealth:
        await asyncio.Event().wait()
        raise AssertionError("stalled adapter health unexpectedly returned")


class WrongLineageAdapter(FakeAdapter):
    async def discover_markets(self, limit: int = 20):
        markets = await super().discover_markets(limit)
        return tuple(
            item.model_copy(
                update={"provenance": item.provenance.model_copy(update={"raw_sha256": "0" * 64})}
            )
            for item in markets
        )


class OversizedBookAdapter(FakeAdapter):
    async def fetch_book(self, market_value, instrument_id: str, depth: int = 20):
        value = await super().fetch_book(market_value, instrument_id, depth)
        extra_level = BookLevel(price=Decimal("0.41"), quantity=Decimal(1))
        return value.model_copy(update={"asks": (*value.asks, extra_level)})


def _attempt_collection_source_lease(root: str, venue: Venue, connection: Connection) -> None:
    try:
        with CollectionJournal(Path(root)).source_lease(venue):
            connection.send("acquired")
    except CollectionSourceBusy:
        connection.send("busy")
    finally:
        connection.close()


def test_collection_source_lease_is_shared_between_journals_and_scoped_by_venue(tmp_path):
    root = tmp_path / "frontier"
    first = CollectionJournal(root)
    second = CollectionJournal(root)

    with first.source_lease(Venue.POLYMARKET):
        with pytest.raises(CollectionSourceBusy, match="already active"):
            with second.source_lease(Venue.POLYMARKET):
                pass
        with second.source_lease(Venue.KRAKEN):
            pass

    with second.source_lease(Venue.POLYMARKET):
        pass


def test_collection_source_lease_excludes_another_process(tmp_path):
    root = tmp_path / "frontier"
    journal = CollectionJournal(root)
    context = get_context("fork")
    receiver, sender = context.Pipe(duplex=False)

    with journal.source_lease(Venue.POLYMARKET):
        worker = context.Process(
            target=_attempt_collection_source_lease,
            args=(str(root), Venue.POLYMARKET, sender),
        )
        worker.start()
        sender.close()
        assert receiver.poll(5)
        assert receiver.recv() == "busy"
        worker.join(5)
        if worker.is_alive():
            worker.terminate()
            worker.join()
        assert worker.exitcode == 0

    receiver.close()


def test_collection_source_lease_rejects_a_symlink(tmp_path):
    root = tmp_path / "frontier"
    journal = CollectionJournal(root)
    journal.initialize()
    target = tmp_path / "external-lock-target"
    target.write_text("untouched")
    lock_path = root / ".frontier-collection-polymarket.lock"
    lock_path.symlink_to(target)

    with pytest.raises(FrontierStoreError, match="unavailable or unsafe"):
        with journal.source_lease(Venue.POLYMARKET):
            pass

    assert target.read_text() == "untouched"


@pytest.mark.asyncio
async def test_initial_source_health_is_inside_the_finite_wall_time_budget(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = StalledHealthAdapter()

    result = await BoundedSourceCollector(adapter, store).start(
        market_limit=1,
        book_limit=0,
        max_wall_seconds=1,
    )

    assert result.state == "paused"
    assert result.failures[-1].code == "COLLECTION_WALL_LIMIT"
    assert result.source_health is None
    assert adapter.discovery_calls == 0
    latest = CollectionJournal(store.root).latest_checkpoint(result.run_id)
    assert latest.state == "paused"

    recovered = await BoundedSourceCollector(FakeAdapter(), store).start(
        market_limit=1,
        book_limit=0,
    )
    assert recovered.state == "completed"


@pytest.mark.asyncio
async def test_competing_collector_start_is_rejected_before_creating_an_orphan_run(tmp_path):
    root = tmp_path / "frontier"
    store = FrontierStore(root)
    adapter = BlockingAdapter()
    first_collector = BoundedSourceCollector(adapter, store)
    first_run = asyncio.create_task(first_collector.start(market_limit=1, book_limit=0))
    await adapter.discovery_entered.wait()

    second_collector = BoundedSourceCollector(FakeAdapter(), FrontierStore(root))
    try:
        with pytest.raises(CollectionSourceBusy, match="already active"):
            await second_collector.start(market_limit=1, book_limit=0)

        with sqlite3.connect(root / "frontier-collection.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM collection_runs").fetchone()[0] == 1
    finally:
        first_run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first_run


@pytest.mark.asyncio
async def test_finite_collection_persists_market_books_and_is_idempotent_on_resume(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)

    result = await collector.start(market_limit=1, book_limit=2)
    assert result.state == "completed"
    assert result.market_count == 1
    assert result.book_count == 2
    assert result.failed_book_count == 0
    assert result.request_count == 3
    assert len(result.market_observation_ids) == 1
    assert len(result.book_observation_ids) == 2
    assert len(result.diagnostic_observation_ids) == 0
    assert store.summary()["observations"] == 3

    resumed = await collector.resume(result.run_id)
    assert resumed == result
    assert adapter.discovery_calls == 1
    assert len(adapter.book_calls) == 2
    checkpoints = CollectionJournal(store.root).checkpoints(result.run_id)
    assert checkpoints[-1].state == "completed"
    assert [item.sequence for item in checkpoints] == list(range(len(checkpoints)))
    assert checkpoints[-1].completed_book_task_ids == tuple(
        task.task_id for task in checkpoints[-1].book_tasks
    )


@pytest.mark.asyncio
async def test_one_book_failure_is_recorded_without_stopping_other_source_tasks(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter(fail_instruments={"POLYMARKET:collection-fixture:YES"})
    collector = BoundedSourceCollector(adapter, store)

    result = await collector.start(market_limit=1, book_limit=2)
    assert result.state == "partial"
    assert result.book_count == 1
    assert result.failed_book_count == 1
    assert result.failures[0].code == "FIXTURE_BOOK_FAILURE"
    assert result.source_health is not None
    assert result.source_health.state == SourceState.DEGRADED
    assert len(adapter.book_calls) == 2
    assert store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_persisted_pending_capture_resumes_without_repeating_discovery(tmp_path):
    store = FailOnceStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)

    paused = await collector.start(market_limit=1, book_limit=1)
    assert paused.state == "paused"
    assert paused.pending_observation_count == 1
    assert adapter.discovery_calls == 1
    assert store.summary()["observations"] == 0
    latest_before = CollectionJournal(store.root).latest_checkpoint(paused.run_id)
    assert latest_before.pending_target == "market"
    assert latest_before.pending_observations[0].raw.observation_kind == "market_listing"

    resumed = await collector.resume(paused.run_id)
    assert resumed.state == "completed"
    assert resumed.pending_observation_count == 0
    assert resumed.market_count == 1
    assert resumed.book_count == 1
    assert adapter.discovery_calls == 1
    assert store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_pending_capture_resumes_with_a_reconstructed_collector(tmp_path):
    root = tmp_path / "frontier"
    interrupted_store = FailOnceStore(root)
    original_adapter = FakeAdapter()
    paused = await BoundedSourceCollector(original_adapter, interrupted_store).start(
        market_limit=1, book_limit=1
    )
    assert paused.state == "paused"

    restarted_adapter = FakeAdapter()
    restarted_store = FrontierStore(root)
    resumed = await BoundedSourceCollector(restarted_adapter, restarted_store).resume(paused.run_id)
    assert resumed.state == "completed"
    assert resumed.market_count == 1
    assert resumed.book_count == 1
    assert restarted_adapter.discovery_calls == 0
    assert len(restarted_adapter.book_calls) == 1
    assert restarted_store.summary()["observations"] == 2


async def _pause_configured_collection(tmp_path, venue, config):
    root = tmp_path / "frontier"
    store = FailOnceStore(root)
    adapter = FakeAdapter(venue=venue, config=config)
    result = await BoundedSourceCollector(adapter, store).start(market_limit=1, book_limit=0)
    assert result.state == "paused"
    assert result.pending_observation_count == 1
    return root, adapter, result, CollectionJournal(root)


@pytest.mark.asyncio
async def test_kraken_pair_config_survives_journal_and_restart_and_mismatch_fails_closed(
    tmp_path,
):
    config = KrakenSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        pairs=("XBTUSD", "ETHUSD"),
    )
    root, original_adapter, paused, journal = await _pause_configured_collection(
        tmp_path, Venue.KRAKEN, config
    )

    restored_spec = journal.run_spec(paused.run_id)
    assert restored_spec.adapter_config_type == "kraken_spot"
    assert type(restored_spec.adapter_config) is KrakenSpotConfig
    assert restored_spec.adapter_config.pairs == ("XBTUSD", "ETHUSD")
    untrusted_tag_spec = restored_spec.model_dump(mode="json")
    untrusted_tag_spec["adapter_config_type"] = "python:arbitrary.import"
    with pytest.raises(ValueError, match="not allowlisted"):
        CollectionRunSpec.model_validate(untrusted_tag_spec)

    listed_spec = journal.latest_run_checkpoints()[0][0]
    assert type(listed_spec.adapter_config) is KrakenSpotConfig
    assert listed_spec.adapter_config == config

    paused_checkpoint = journal.latest_checkpoint(paused.run_id)
    changed_adapter = FakeAdapter(
        venue=Venue.KRAKEN,
        config=config.model_copy(update={"pairs": ("ETHUSD",)}),
    )
    with pytest.raises(ValueError, match="configuration differs"):
        await BoundedSourceCollector(changed_adapter, FrontierStore(root), journal).resume(
            paused.run_id
        )
    assert changed_adapter.discovery_calls == 0
    assert changed_adapter.transport.request_count == 0
    assert journal.latest_checkpoint(paused.run_id) == paused_checkpoint

    restarted_adapter = FakeAdapter(venue=Venue.KRAKEN, config=config)
    resumed = await BoundedSourceCollector(restarted_adapter, FrontierStore(root), journal).resume(
        paused.run_id
    )
    assert resumed.state == "completed"
    assert restarted_adapter.discovery_calls == 0
    assert restarted_adapter.transport.request_count == 0
    assert original_adapter.discovery_calls == 1


@pytest.mark.asyncio
async def test_coinbase_product_and_terms_ack_config_survive_restart_and_are_pinned(tmp_path):
    config = CoinbaseSpotConfig(
        enabled=True,
        live_public_probe_enabled=True,
        probe_policy_block_reason=None,
        market_data_terms_version_acknowledged=COINBASE_MARKET_DATA_TERMS_VERSION,
        products=("BTC-USD", "ETH-USD"),
    )
    root, original_adapter, paused, journal = await _pause_configured_collection(
        tmp_path, Venue.COINBASE_EXCHANGE, config
    )

    restored_spec = journal.run_spec(paused.run_id)
    assert restored_spec.adapter_config_type == "coinbase_spot"
    assert type(restored_spec.adapter_config) is CoinbaseSpotConfig
    assert restored_spec.adapter_config.products == ("BTC-USD", "ETH-USD")
    assert (
        restored_spec.adapter_config.market_data_terms_version_acknowledged
        == COINBASE_MARKET_DATA_TERMS_VERSION
    )
    listed_spec = journal.latest_run_checkpoints()[0][0]
    assert type(listed_spec.adapter_config) is CoinbaseSpotConfig
    assert listed_spec.adapter_config == config

    changed_products = config.model_copy(update={"products": ("ETH-USD",)})
    changed_product_adapter = FakeAdapter(venue=Venue.COINBASE_EXCHANGE, config=changed_products)
    with pytest.raises(ValueError, match="configuration differs"):
        await BoundedSourceCollector(changed_product_adapter, FrontierStore(root), journal).resume(
            paused.run_id
        )
    assert changed_product_adapter.discovery_calls == 0
    assert changed_product_adapter.transport.request_count == 0

    changed_ack = config.model_copy(
        update={"market_data_terms_version_acknowledged": "fixture-other-terms"}
    )
    changed_ack_adapter = FakeAdapter(venue=Venue.COINBASE_EXCHANGE, config=changed_ack)
    with pytest.raises(ValueError, match="configuration differs"):
        await BoundedSourceCollector(changed_ack_adapter, FrontierStore(root), journal).resume(
            paused.run_id
        )
    assert changed_ack_adapter.discovery_calls == 0
    assert changed_ack_adapter.transport.request_count == 0

    restarted_adapter = FakeAdapter(venue=Venue.COINBASE_EXCHANGE, config=config)
    resumed = await BoundedSourceCollector(restarted_adapter, FrontierStore(root), journal).resume(
        paused.run_id
    )
    assert resumed.state == "completed"
    assert restarted_adapter.discovery_calls == 0
    assert restarted_adapter.transport.request_count == 0
    assert original_adapter.discovery_calls == 1


def test_legacy_collection_spec_without_a_config_tag_remains_readable():
    legacy = CollectionRunSpec(
        schema_version=1,
        run_version="frontier-finite-collection-1",
        run_id="33333333-3333-4333-8333-333333333333",
        venue=Venue.POLYMARKET,
        adapter_version="fixture-adapter-1",
        capability_manifest_sha256="a" * 64,
        adapter_config=AdapterConfig(enabled=False, live_public_probe_enabled=False),
        market_limit=1,
        book_limit=0,
        book_depth=5,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    payload = legacy.model_dump(mode="json")
    payload.pop("adapter_config_type")

    restored = CollectionRunSpec.model_validate(payload)

    assert restored.schema_version == 1
    assert restored.adapter_config_type == "base"
    assert type(restored.adapter_config) is AdapterConfig


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_config", "expected_code"),
    [
        (AdapterConfig(enabled=False, live_public_probe_enabled=False), "PUBLIC_PROBE_DISABLED"),
        (
            AdapterConfig(
                enabled=True,
                live_public_probe_enabled=True,
                probe_policy_block_reason="Fixture source-use hold",
            ),
            "SOURCE_USE_HELD",
        ),
    ],
)
async def test_resume_rechecks_probe_policy_before_recovering_pending_source_data(
    tmp_path, current_config, expected_code
):
    store = FailOnceStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)

    paused = await collector.start(market_limit=1, book_limit=0)
    assert paused.state == "paused"
    assert paused.pending_observation_count == 1
    checkpoint_before = CollectionJournal(store.root).latest_checkpoint(paused.run_id)
    request_count_before = adapter.transport.request_count

    adapter.config = current_config
    with pytest.raises(AdapterError) as error:
        await collector.resume(paused.run_id)

    assert error.value.code == expected_code
    assert adapter.transport.request_count == request_count_before
    assert CollectionJournal(store.root).latest_checkpoint(paused.run_id) == checkpoint_before


@pytest.mark.asyncio
async def test_disabled_source_makes_no_adapter_call_and_failures_are_source_local(tmp_path):
    disabled_store = FrontierStore(tmp_path / "disabled")
    disabled_adapter = FakeAdapter(enabled=False)
    disabled = BoundedSourceCollector(disabled_adapter, disabled_store)
    with pytest.raises(AdapterError, match="public-probe flag"):
        await disabled.start(market_limit=1, book_limit=0)
    assert disabled_adapter.discovery_calls == 0
    assert not CollectionJournal(disabled_store.root).path.exists()

    failed_store = FrontierStore(tmp_path / "failed-source")
    failed_adapter = FakeAdapter(fail_discovery=True)
    failed = await BoundedSourceCollector(failed_adapter, failed_store).start(
        market_limit=1, book_limit=0
    )
    assert failed.state == "failed"
    assert failed.market_count == 0
    assert failed.failures[0].code == "FIXTURE_DISCOVERY_FAILURE"

    healthy_store = FrontierStore(tmp_path / "healthy-source")
    healthy_adapter = FakeAdapter()
    healthy = await BoundedSourceCollector(healthy_adapter, healthy_store).start(
        market_limit=1, book_limit=0
    )
    assert healthy.state == "completed"
    assert healthy.market_count == 1
    assert healthy_adapter.discovery_calls == 1


def test_collection_journal_detects_checkpoint_tampering_and_enforces_append_only(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    # A created run has a durable, independently verifiable first checkpoint.
    import asyncio

    result = asyncio.run(BoundedSourceCollector(adapter, store).start(market_limit=1, book_limit=0))
    journal = CollectionJournal(store.root)
    checkpoints = journal.checkpoints(result.run_id)
    assert checkpoints[-1].state == "completed"

    import sqlite3

    with sqlite3.connect(journal.path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE collection_checkpoints SET checkpoint_json='{}' WHERE run_id=? AND sequence=0",
            (result.run_id,),
        )
    with sqlite3.connect(journal.path) as connection:
        first_digest = str(
            connection.execute(
                "SELECT row_sha256 FROM collection_checkpoints "
                "WHERE run_id=? ORDER BY sequence LIMIT 1",
                (result.run_id,),
            ).fetchone()[0]
        )
    with sqlite3.connect(journal.path) as connection:
        connection.execute(
            "INSERT INTO collection_checkpoints VALUES(?,?,?,?,?)",
            (result.run_id, len(checkpoints), "0" * 64, "{}", "0" * 64),
        )
    with pytest.raises(FrontierStoreError, match="chain integrity"):
        journal.checkpoints(result.run_id)
    with pytest.raises(FrontierStoreError, match="chain integrity"):
        journal.verified_source_health_checkpoint(first_digest)
    with pytest.raises(FrontierStoreError, match="chain integrity"):
        journal.latest_run_checkpoints()


def test_collection_run_pages_scan_past_held_sources_across_bounded_batches(tmp_path):
    journal = CollectionJournal(tmp_path / "frontier")
    disabled = AdapterConfig(enabled=False, live_public_probe_enabled=False)

    def add_run(index: int, venue: Venue) -> str:
        run_id = f"{index:08x}-1111-4111-8111-{index:012x}"
        journal.create_run(
            CollectionRunSpec(
                run_id=run_id,
                venue=venue,
                adapter_version="fixture-adapter-1",
                capability_manifest_sha256="a" * 64,
                adapter_config=disabled,
                market_limit=1,
                book_limit=0,
                book_depth=5,
                max_evidence_bytes=4 * 1024 * 1024,
                max_wall_seconds=30,
                created_at_utc=T0,
            )
        )
        journal.append_checkpoint(
            CollectionCheckpoint(
                run_id=run_id,
                sequence=0,
                updated_at_utc=T0,
                state="completed",
            )
        )
        return run_id

    oldest_polymarket = add_run(1, Venue.POLYMARKET)
    for index in range(2, 67):
        add_run(index, Venue.KALSHI)
    newest_polymarket = add_run(67, Venue.POLYMARKET)

    page = journal.latest_run_checkpoints(
        limit=2,
        excluded_venues=(Venue.KALSHI,),
    )
    assert [spec.run_id for spec, _, _ in page] == [newest_polymarket, oldest_polymarket]
    assert all(spec.venue is Venue.POLYMARKET for spec, _, _ in page)


def test_unknown_source_health_checkpoint_lookup_is_read_only(tmp_path):
    journal = CollectionJournal(tmp_path / "uncreated-frontier-root")
    assert journal.verified_source_health_checkpoint("a" * 64) is None
    assert not journal.path.exists()


def test_latest_source_health_checkpoints_are_bounded_read_only_and_use_latest_health(tmp_path):
    journal = CollectionJournal(tmp_path / "frontier")
    assert journal.latest_source_health_checkpoints() == ()
    assert not journal.path.exists()

    run_spec = CollectionRunSpec(
        run_id="f79d58bb-e799-4718-93f1-a94bb7492f21",
        venue=Venue.POLYMARKET,
        adapter_version="fixture-adapter-v1",
        capability_manifest_sha256="f" * 64,
        adapter_config=AdapterConfig(enabled=False, live_public_probe_enabled=False),
        market_limit=1,
        book_limit=0,
        book_depth=1,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(run_spec)
    first_digest = journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=0,
            updated_at_utc=T0 + timedelta(seconds=1),
            state="completed",
            source_health=SourceHealth(
                venue=Venue.POLYMARKET,
                state=SourceState.HEALTHY,
                checked_at_utc=T0,
                last_success_at_utc=T0,
            ),
        )
    )
    journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=1,
            updated_at_utc=T0 + timedelta(seconds=2),
            state="completed",
        )
    )
    latest_digest = journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=2,
            updated_at_utc=T0 + timedelta(seconds=4),
            state="partial",
            source_health=SourceHealth(
                venue=Venue.POLYMARKET,
                state=SourceState.DEGRADED,
                checked_at_utc=T0 + timedelta(seconds=3),
                last_success_at_utc=T0,
            ),
        )
    )
    journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=3,
            updated_at_utc=T0 + timedelta(seconds=5),
            state="completed",
            source_health=SourceHealth(
                venue=Venue.POLYMARKET,
                state=SourceState.NOT_PROBED,
            ),
        )
    )

    selected = journal.latest_source_health_checkpoints()
    assert len(selected) == 1
    assert selected[0][1].sequence == 2
    assert selected[0][2] == latest_digest
    assert selected[0][2] != first_digest
    assert journal.latest_source_health_checkpoints(excluded_venues=(Venue.POLYMARKET,)) == ()
    with pytest.raises(ValueError, match="listing limit"):
        journal.latest_source_health_checkpoints(limit=21)


def test_latest_source_health_checkpoint_listing_rejects_a_broken_chain(tmp_path):
    from midas.frontier.collection import _canonical_json

    journal = CollectionJournal(tmp_path / "frontier")
    run_spec = CollectionRunSpec(
        run_id="b43698ca-8919-413e-952a-5ec4821be120",
        venue=Venue.POLYMARKET,
        adapter_version="fixture-adapter-v1",
        capability_manifest_sha256="f" * 64,
        adapter_config=AdapterConfig(enabled=False, live_public_probe_enabled=False),
        market_limit=1,
        book_limit=0,
        book_depth=1,
        max_evidence_bytes=1024 * 1024,
        max_wall_seconds=30,
        created_at_utc=T0,
    )
    journal.create_run(run_spec)
    journal.append_checkpoint(
        CollectionCheckpoint(
            run_id=run_spec.run_id,
            sequence=0,
            updated_at_utc=T0 + timedelta(seconds=1),
            state="completed",
            source_health=SourceHealth(
                venue=Venue.POLYMARKET,
                state=SourceState.HEALTHY,
                checked_at_utc=T0,
            ),
        )
    )
    corrupted = CollectionCheckpoint(
        run_id=run_spec.run_id,
        sequence=1,
        updated_at_utc=T0 + timedelta(seconds=3),
        state="partial",
        source_health=SourceHealth(
            venue=Venue.POLYMARKET,
            state=SourceState.DEGRADED,
            checked_at_utc=T0 + timedelta(seconds=2),
            last_success_at_utc=T0,
        ),
    )
    encoded = _canonical_json(corrupted.model_dump(mode="json"))
    digest = hashlib.sha256(encoded).hexdigest()
    with sqlite3.connect(journal.path) as connection:
        connection.execute(
            "INSERT INTO collection_checkpoints VALUES(?,?,?,?,?)",
            (run_spec.run_id, 1, "0" * 64, encoded.decode(), digest),
        )
    with pytest.raises(FrontierStoreError, match="chain integrity"):
        journal.latest_source_health_checkpoints()


def test_latest_pinned_market_metadata_wins_without_discarding_capture_rows(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = FakeAdapter()
    collector = BoundedSourceCollector(adapter, store)
    earlier_raw = FakeAdapter._raw("market_listing", "earlier")
    later_raw = FakeAdapter._raw("market_listing", "later")
    base_market = market(Venue.POLYMARKET, "same-native-market")

    def captured_market(raw: RawObservation, title: str):
        provenance = base_market.provenance.model_copy(
            update={"raw_sha256": raw.raw_sha256, "observation_id": raw.raw_sha256}
        )
        return base_market.model_copy(update={"title": title, "provenance": provenance})

    earlier_id = store.append_observation(
        earlier_raw,
        MarketBatch(venue=Venue.POLYMARKET, markets=(captured_market(earlier_raw, "Earlier"),)),
    )
    later_id = store.append_observation(
        later_raw,
        MarketBatch(venue=Venue.POLYMARKET, markets=(captured_market(later_raw, "Latest"),)),
    )

    selected = collector._load_markets((earlier_id, later_id), Venue.POLYMARKET)
    assert len(selected) == 1
    assert selected[0].title == "Latest"
    assert store.summary()["observations"] == 2


@pytest.mark.asyncio
async def test_cancellation_is_checkpointed_and_run_can_resume(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = BlockingAdapter()
    collector = BoundedSourceCollector(adapter, store)
    task = asyncio.create_task(collector.start(market_limit=1, book_limit=0, max_wall_seconds=60))
    await asyncio.wait_for(adapter.discovery_entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    journal = CollectionJournal(store.root)
    with sqlite3.connect(journal.path) as connection:
        run_id = str(connection.execute("SELECT run_id FROM collection_runs").fetchone()[0])
    paused = journal.latest_checkpoint(run_id)
    assert paused.state == "paused"
    assert paused.failures[-1].code == "COLLECTION_CANCELLED"
    resumed = await collector.resume(paused.run_id)
    assert resumed.state == "completed"
    assert adapter.discovery_calls == 1


@pytest.mark.asyncio
async def test_market_lineage_failure_keeps_the_raw_capture_as_diagnostic(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = WrongLineageAdapter()
    result = await BoundedSourceCollector(adapter, store).start(market_limit=1, book_limit=0)

    assert result.state == "failed"
    assert result.failures[0].code == "CAPTURE_LINEAGE_MISMATCH"
    assert len(result.diagnostic_observation_ids) == 1
    row = store.observation(result.diagnostic_observation_ids[0])
    assert row is not None
    assert row["raw"]["raw_sha256"] == adapter.market_capture.raw_sha256
    assert row["normalized"]["error_code"] == "CAPTURE_LINEAGE_MISMATCH"


@pytest.mark.asyncio
async def test_oversized_response_rejection_is_checkpointed_without_body_capture(tmp_path):
    class OversizedDiscoveryAdapter(FakeAdapter):
        async def discover_markets(self, limit: int = 20):
            self.transport.request_count += 1
            self.discovery_calls += 1
            raise AdapterError(
                "RESPONSE_TOO_LARGE",
                "Response exceeds configured byte bound",
                response_diagnostic=RejectedResponseEvidence(
                    url="https://fixture.example/markets",
                    status_code=200,
                    request_started_at_utc=T0,
                    rejected_at_utc=T0 + timedelta(milliseconds=25),
                    request_elapsed_monotonic_ns=25_000_000,
                    max_response_bytes=1024,
                    declared_content_length_bytes=2048,
                    bytes_yielded_at_rejection=0,
                    rejection_stage="content_length",
                ),
            )

    store = FrontierStore(tmp_path / "frontier")
    adapter = OversizedDiscoveryAdapter()
    result = await BoundedSourceCollector(adapter, store).start(market_limit=1, book_limit=0)

    assert result.state == "failed"
    assert result.request_count == 1
    assert result.failures[0].code == "RESPONSE_TOO_LARGE"
    assert len(result.diagnostic_observation_ids) == 1
    diagnostic = store.observation(result.diagnostic_observation_ids[0])
    assert diagnostic is not None
    assert diagnostic["raw"]["raw_body"] == ""
    assert diagnostic["raw"]["raw_body_state"] == "not_captured_after_size_limit"
    assert diagnostic["raw"]["raw_sha256"] == hashlib.sha256(b"").hexdigest()
    assert diagnostic["normalized"]["failure_stage"] == "transport_rejection"
    assert diagnostic["normalized"]["response_rejection"]["declared_content_length_bytes"] == 2048


@pytest.mark.asyncio
async def test_book_depth_violation_is_rejected_with_raw_evidence(tmp_path):
    store = FrontierStore(tmp_path / "frontier")
    adapter = OversizedBookAdapter()
    result = await BoundedSourceCollector(adapter, store).start(
        market_limit=1, book_limit=1, book_depth=1
    )

    assert result.state == "partial"
    assert result.book_count == 0
    assert result.failed_book_count == 1
    assert result.failures[-1].code == "BOOK_DEPTH_EXCEEDED"
    assert len(result.diagnostic_observation_ids) == 1
    diagnostic = store.observation(result.diagnostic_observation_ids[0])
    assert diagnostic is not None
    assert diagnostic["normalized"]["error_code"] == "BOOK_DEPTH_EXCEEDED"


@pytest.mark.asyncio
async def test_oversized_store_row_is_terminal_partial_and_remains_checkpointed(tmp_path):
    class OversizedMarketAdapter(FakeAdapter):
        async def discover_markets(self, limit: int = 20):
            markets = await super().discover_markets(limit)
            payload = markets[0].model_dump(mode="python")
            payload["description"] = "x" * 600_000
            return (type(markets[0]).model_validate(payload),)

    store = FrontierStore(tmp_path / "frontier")
    adapter = OversizedMarketAdapter()
    collector = BoundedSourceCollector(adapter, store)
    result = await collector.start(market_limit=1, book_limit=0)

    assert result.state == "partial"
    assert result.failures[-1].code == "COLLECTION_ROW_LIMIT"
    assert result.pending_observation_count == 1
    assert store.summary()["observations"] == 0
    resumed = await collector.resume(result.run_id)
    assert resumed == result
