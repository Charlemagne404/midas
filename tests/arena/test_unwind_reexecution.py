import json

import pytest
from midas.arena.artifacts import atomic_json, atomic_replay, sha256
from midas.arena.datasets import research_hash
from midas.arena.unwind import UnwindSpec
from midas.laboratory.runtime import Environment
from midas.laboratory.spec import generate

from scripts.reproduce_unwind import reproduce


@pytest.fixture
def saved(tmp_path):
    identity = "unwind-reexecution"
    directory = tmp_path / "unwinds" / identity
    result = Environment(generate("deep", 493071).model_copy(update={"strategy": "no_trade"})).run()
    row = {
        "id": "0-standard-no_trade",
        "policy": "no_trade",
        "result_hash": result["result_hash"],
        "journal_hash": result["journal_hash"],
    }
    atomic_json(directory / "rows.json", [row])
    atomic_json(
        directory / "manifest.json",
        {
            "state": "COMPLETED",
            "source_hash": research_hash(),
            "rows_sha256": sha256(directory / "rows.json"),
            "configuration": {"unwind": UnwindSpec().model_dump(mode="json")},
        },
    )
    atomic_replay(
        directory / "replays" / (row["id"] + ".json"),
        {"row": row, "result": result, "intervention_decisions": []},
    )
    return tmp_path, identity, row["id"]


def test_exact_no_trade_reexecution(saved):
    root, identity, row = saved
    assert reproduce(root, identity, row)["verified"]


@pytest.mark.parametrize("change", ["source", "rows"])
def test_reexecution_refuses_changed_evidence(saved, change):
    root, identity, row = saved
    directory = root / "unwinds" / identity
    if change == "source":
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["source_hash"] = "another source"
        path.write_text(json.dumps(manifest))
    else:
        path = directory / "rows.json"
        path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError):
        reproduce(root, identity, row)
