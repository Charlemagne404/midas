"""Runtime PostgreSQL test, skipped unless an explicit PostgreSQL test URL is supplied."""

import os
import uuid

import pytest
from midas.paper.broker import AccountConfig, ExecutionModel, audit, summary
from midas.simulation.fixtures import DEMO_EPOCH, binary_fixture

from apps.api.paper import PaperBroker
from apps.api.storage import Store


@pytest.mark.skipif(
    not os.environ.get("MIDAS_TEST_POSTGRES_URL"),
    reason="PostgreSQL runtime unavailable; set MIDAS_TEST_POSTGRES_URL",
)
async def test_postgres_paper_atomic_recovery():
    url = os.environ["MIDAS_TEST_POSTGRES_URL"]
    assert url.startswith("postgresql+asyncpg://")
    store = Store(url)
    await store.initialize()
    key = "pg-test-" + uuid.uuid4().hex
    config = AccountConfig(execution=ExecutionModel.preset("optimistic"))
    broker = PaperBroker(store, key, config)
    await broker.start(DEMO_EPOCH)
    market, books = binary_fixture()
    await broker.apply(
        {
            "id": "signal",
            "kind": "observe",
            "ts": DEMO_EPOCH,
            "market": market.model_dump(mode="json"),
            "books": {a: b.model_dump(mode="json") for a, b in books.items()},
        }
    )
    submit = next(x for x in broker.state["pending"] if x["kind"] == "submit")
    await broker.apply(
        {"id": submit["id"], "kind": "action", "ts": submit["due"], "action_id": submit["id"]}
    )
    match = next(
        x for x in broker.state["pending"] if x["kind"] == "match" and x["order"] == submit["order"]
    )
    command = {"id": match["id"], "kind": "action", "ts": match["due"], "action_id": match["id"]}
    with pytest.raises(RuntimeError):
        await broker.apply(command, crash="after_commit")
    restored = PaperBroker(store, key, config)
    await restored.start(DEMO_EPOCH + 100)
    await restored.apply(command)
    assert summary(restored.state)["hypothetical_fills"] == 1
    assert not audit(restored.state)
    await store.close()
