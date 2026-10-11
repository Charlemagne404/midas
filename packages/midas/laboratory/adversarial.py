"""Sequence search and deterministic delta debugging of invariant failures."""

import random
from typing import Any

from midas.economics.attestation import digest
from midas.laboratory.runtime import execute
from midas.laboratory.spec import FAMILIES, Scenario, ScenarioEvent, generate


def failure_category(result: dict[str, Any]) -> str | None:
    if result["passed"]:
        return None
    if result["classification"] == "CONTROLLED_MUTATION":
        return "independent_ledger"
    return str(result["errors"][0].split(":", 1)[0])


def minimize(scenario: Scenario, budget: int = 128) -> dict[str, Any]:
    original = execute(scenario)
    target = failure_category(original)
    if target is None:
        raise ValueError("A loss or model uncertainty is not an invariant failure")
    events = list(scenario.events)
    attempts = 0
    width = 2
    while len(events) >= 2 and attempts < budget:
        chunk = max(1, (len(events) + width - 1) // width)
        reduced = False
        for start in range(0, len(events), chunk):
            candidate = events[:start] + events[start + chunk :]
            trial = scenario.model_copy(update={"events": tuple(candidate)})
            attempts += 1
            if failure_category(execute(trial, retain=False)) == target:
                events = candidate
                width = max(2, width - 1)
                reduced = True
                break
            if attempts >= budget:
                break
        if not reduced:
            if width >= len(events):
                break
            width = min(len(events), width * 2)
    minimized = scenario.model_copy(update={"events": tuple(events)})
    # Prove single-event deletion minimality when budget permits; never claim global minimum.
    minimal = True
    for index in range(len(events)):
        if attempts >= budget:
            minimal = False
            break
        attempts += 1
        if (
            failure_category(
                execute(
                    scenario.model_copy(
                        update={"events": tuple(events[:index] + events[index + 1 :])}
                    ),
                    retain=False,
                )
            )
            == target
        ):
            minimal = False
            break
    reproduced = execute(minimized)
    return {
        "id": digest([original["scenario_hash"], target])[:24],
        "severity": "ERROR",
        "component": "accounting" if target == "independent_ledger" else "laboratory",
        "classification": original["classification"],
        "invariant": target,
        "status": "CONTROLLED"
        if original["classification"] == "CONTROLLED_MUTATION"
        else "UNRESOLVED",
        "expected": "Every committed fill conserves collateral and matches independently calculated charges",
        "actual": reproduced["errors"],
        "original_scenario": scenario.model_dump(mode="json"),
        "minimized_scenario": minimized.model_dump(mode="json"),
        "original_events": len(scenario.events),
        "minimized_events": len(events),
        "minimization_attempts": attempts,
        "single_deletion_minimal": minimal,
        "original_result_hash": original["result_hash"],
        "reproduction_result_hash": reproduced["result_hash"],
        "strategy_version": reproduced["strategy_version"],
        "simulator_version": reproduced["simulator_version"],
        "journal": reproduced["journal"],
        "seed": scenario.seed,
        "financial_consequence": "Corrupted simulated ledger; financial metrics are invalid until reconciled",
        "reproduction": ".venv/bin/python scripts/laboratory.py reproduce --incident <artifact.json>",
        "regression_reference": "tests/laboratory/test_adversarial.py",
    }


def mutate_sequence(scenario: Scenario, seed: int) -> Scenario:
    rng = random.Random(seed)
    events = list(scenario.events)
    if events:
        index = rng.randrange(len(events))
        selected = events[index]
        events[index] = selected.model_copy(
            update={"time_ms": max(0, selected.time_ms + rng.choice([-250, -1, 0, 1, 250]))}
        )
    for n in range(rng.randint(1, 3)):
        kind, payload = rng.choice(
            [
                ("fault", {"action_kind": "match", "fault": "withdraw"}),
                ("fault", {"action_kind": "ack", "fault": "lost_ack"}),
                ("cancel", {"delay_ms": rng.choice([0, 1, 250, 1000])}),
                ("duplicate", {}),
                ("control", {"paused": True}),
                ("expire", {"delay_ms": 0}),
            ]
        )
        events.append(
            ScenarioEvent.model_validate(
                {
                    "id": f"search:{seed}:{n}",
                    "time_ms": rng.choice([0, 1, 200, 201, 250, 1000]),
                    "kind": kind,
                    "payload": payload,
                }
            )
        )
    return scenario.model_copy(update={"events": tuple(events)})


def search(seed: int, trials: int = 100, controlled: bool = False) -> dict[str, Any]:
    rng = random.Random(seed)
    discoveries = []
    losses = passed = 0
    for i in range(trials):
        family = (
            "ledger_mutation"
            if controlled and i == 0
            else rng.choice([f for f in FAMILIES if f != "ledger_mutation"])
        )
        scenario = mutate_sequence(generate(family, (seed + i) % 2**32), seed + i)
        result = execute(scenario, retain=False)
        if not result["passed"]:
            discoveries.append(minimize(scenario))
        else:
            passed += 1
            losses += result["classification"] == "LEGITIMATE_LOSS"
    return {
        "seed": seed,
        "trials": trials,
        "passed": passed,
        "legitimate_losses": losses,
        "discoveries": discoveries,
        "controlled_mutation_enabled": controlled,
        "note": "Synthetic search; zero discoveries is bounded evidence, not proof of correctness",
    }
