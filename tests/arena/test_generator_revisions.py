import pytest
from midas.arena.datasets import DatasetSpec, build
from midas.arena.generator_revisions import GeneratorRevision
from midas.arena.tournaments import TournamentSpec, run_tournament
from midas.laboratory.runtime import execute
from midas.laboratory.spec import generate


def test_settlement_revision_changes_no_observable_or_execution_inputs():
    original = generate("volatile", 483071)
    before = original.model_dump(mode="json")
    revised = GeneratorRevision().apply(original)
    assert original.model_dump(mode="json") == before
    a, b = before.copy(), revised.model_dump(mode="json")
    for value in (a, b):
        value.pop("warnings")
        for event in value["events"]:
            if event["kind"] == "settle":
                event["payload"].pop("payout")
    assert a == b
    assert GeneratorRevision().apply(original) == revised
    legacy = next(e.payload["payout"] for e in original.events if e.kind == "settle")
    assert list(legacy.values()) == [str(int(i == original.seed % 2)) for i in range(2)]


def test_revision_breaks_family_parity_coupling_in_fixed_sample():
    families = ("calm", "volatile", "thin", "deep", "one_sided", "disappearing")
    old, new = {f: set() for f in families}, {f: set() for f in families}
    for i in range(120):
        family = families[i % len(families)]
        scenario = generate(family, 483071 + i)
        for target, value in [(old, scenario), (new, GeneratorRevision().apply(scenario))]:
            payout = next(e.payload["payout"] for e in value.events if e.kind == "settle")
            target[family].add(tuple(payout.values()))
    assert all(len(values) == 1 for values in old.values())
    assert all(len(values) == 2 for values in new.values())


def test_settlement_revision_survives_sorted_json_round_trip():
    import json

    from midas.laboratory.spec import Scenario

    original = generate("calm", 483071)
    loaded = Scenario.model_validate(
        json.loads(json.dumps(original.model_dump(mode="json"), sort_keys=True))
    )
    revised = [GeneratorRevision().apply(scenario) for scenario in (original, loaded)]
    payouts = [
        next(e.payload["payout"] for e in scenario.events if e.kind == "settle")
        for scenario in revised
    ]
    assert payouts[0] == payouts[1]


def test_rejects_recorded_and_frozen_dataset_rewrites():
    with pytest.raises(ValueError, match="generated"):
        GeneratorRevision().apply(generate("calm", 7).model_copy(update={"provenance": "RECORDED"}))
    with pytest.raises(ValueError, match="fresh challenge"):
        TournamentSpec(dataset_id="dataset-test", generator_revision=GeneratorRevision())


def test_revised_execution_passes_accounting_and_is_reproducible():
    revised = GeneratorRevision().apply(generate("volatile", 483103))
    first, second = execute(revised), execute(revised)
    assert first["passed"] and first["complete"]
    assert (first["result_hash"], first["journal_hash"]) == (
        second["result_hash"],
        second["journal_hash"],
    )


def test_native_tournaments_preserve_origin_and_pre_settlement_journals(tmp_path):
    manifest = build(tmp_path, DatasetSpec(episodes=30, seed=1717))
    challenge = DatasetSpec(episodes=30, seed=483071)
    args = dict(
        dataset_id=manifest["dataset_id"],
        challenge=challenge,
        max_episodes=2,
        execution_models=("standard",),
    )
    first = run_tournament(tmp_path, TournamentSpec(**args))
    second = run_tournament(
        tmp_path, TournamentSpec(**args, generator_revision=GeneratorRevision())
    )
    import json

    from midas.arena.artifacts import read_replay

    old = json.loads((tmp_path / "tournaments" / first["tournament_id"] / "rows.json").read_text())
    new = json.loads((tmp_path / "tournaments" / second["tournament_id"] / "rows.json").read_text())
    assert len(old) == len(new) == 8
    for a, b in zip(old, new, strict=True):
        assert a["scenario_origin_hash"] == b["scenario_origin_hash"]
        reports = [
            read_replay(
                tmp_path / "tournaments" / m["tournament_id"] / "replays" / (r["id"] + ".json")
            )
            for m, r in [(first, a), (second, b)]
        ]
        prefixes = []
        for report in reports:
            result = report["result"]
            scenario = result["scenario"]
            settle = next(e["time_ms"] for e in scenario["events"] if e["kind"] == "settle")
            prefixes.append(
                [e for e in result["journal"] if e["time_ms"] < scenario["epoch_ms"] + settle]
            )
        assert prefixes[0] == prefixes[1]
