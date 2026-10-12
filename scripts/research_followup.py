"""Bounded evidence-driven latency research, using existing supervised Arena jobs."""

import argparse
import fcntl
import json
import signal
import time
from pathlib import Path
from typing import Any

from midas.arena import jobs
from midas.arena.artifacts import artifact_path, atomic_bytes, atomic_json, sha256
from midas.arena.datasets import DatasetSpec, research_hash
from midas.arena.economic_regimes import EconomicRegime
from midas.arena.tournaments import GateSpec, TournamentSpec
from midas.economics.attestation import digest
from midas.laboratory.campaigns import revision

from scripts.attribute_arena_losses import amount, analyze
from scripts.compare_arena import compare


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def producer_hashes() -> dict[str, str]:
    return {
        str(p.resolve()): sha256(p)
        for p in (
            Path(__file__),
            Path(__file__).with_name("compare_arena.py"),
            Path(__file__).with_name("attribute_arena_losses.py"),
        )
    }


def seed_ranges(root: Path) -> list[tuple[int, int]]:
    ranges = []
    for kind, filename in (
        ("datasets", "manifest.json"),
        ("tournaments", "manifest.json"),
        ("jobs", "job.json"),
    ):
        for path in (root / kind).glob("*/" + filename):
            record = read(path)
            if kind == "datasets":
                spec = record["spec"]
            elif kind == "jobs":
                spec = record["configuration"].get("dataset") or (
                    record["configuration"].get("tournament") or {}
                ).get("challenge")
            else:
                spec = record["configuration"].get("challenge")
            if spec:
                ranges.append((spec["seed"], spec["seed"] + spec["episodes"]))
    for path in (root / "directors").glob("*/manifest.json"):
        ranges.extend(tuple(pair) for pair in read(path).get("reserved_seed_ranges", []))
    return ranges


def guard(root: Path, record: dict[str, Any]) -> None:
    if record.get("preregistration_sha256"):
        directory = artifact_path(root, "directors", record["director_id"])
        frozen_path = directory / "preregistration.json"
        if sha256(frozen_path) != record["preregistration_sha256"]:
            raise ValueError("Frozen preregistration changed")
        frozen = read(frozen_path)
        mutable = {"state", "cycles", "steps", "current_stage"}
        if any(record.get(key) != value for key, value in frozen.items() if key not in mutable):
            raise ValueError("Follow-up configuration changed after preregistration")
        if [s["name"] for s in record["steps"]] != [s["name"] for s in frozen["steps"]]:
            raise ValueError("Preregistered step sequence changed")
        for source_path, expected in record["producer_hashes"].items():
            if sha256(directory / "source" / Path(source_path).name) != expected:
                raise ValueError("Captured producer source changed")
    if record["source_hash"] != research_hash() or record["producer_hashes"] != producer_hashes():
        raise ValueError("Research source changed since follow-up preregistration")
    for identity, expected in record["model_artifact_hashes"].items():
        directory = artifact_path(root, "models", identity)
        model = read(directory / "manifest.json")
        weights = directory / ("policy.zip" if model["family"] == "ppo" else "parameters.json")
        if model["artifact_sha256"] != expected or sha256(weights) != expected:
            raise ValueError("Frozen model weights changed")


def create_plan(root: Path, baseline_id: str, seed: int, episodes: int = 60) -> dict[str, Any]:
    if not 30 <= episodes <= 100:
        raise ValueError("Follow-up requires 30..100 groups per cycle")
    baseline_path = artifact_path(root, "tournaments", baseline_id)
    baseline = read(baseline_path / "manifest.json")
    report_path = baseline_path / "economic-regimes.json"
    reference = read(baseline_path / "economic-study-reference.json")
    if reference["baseline_tournament_id"] != baseline_id or reference["report_sha256"] != sha256(
        report_path
    ):
        raise ValueError("Frozen input study identity changed")
    study = read(report_path)
    source = research_hash()
    identity = (
        "director-followup-"
        + digest([sha256(report_path), seed, episodes, source, producer_hashes()])[:24]
    )
    destination = artifact_path(root, "directors", identity) / "manifest.json"
    with (root / "research-planning.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if destination.exists():
            record = read(destination)
            guard(root, record)
            return record
        if baseline["source_hash"] != source or study["source_hash"] != source:
            raise ValueError("Follow-up requires the same simulator source as its evidence")
        baseline_spec = TournamentSpec.model_validate(baseline["configuration"])
        if (
            len(baseline_spec.gates) != 1
            or baseline_spec.model_ids
            or baseline_spec.economic_regime
        ):
            raise ValueError("Follow-up requires one frozen gate and an unperturbed baseline")
        gate = baseline_spec.gates[0]
        baseline_score = next(
            r["score"] for r in baseline["leaderboard"] if r["policy"] == gate.identity
        )
        candidates = []
        for condition in study["conditions"]:
            directory = artifact_path(root, "tournaments", condition["tournament_id"])
            manifest = read(directory / "manifest.json")
            if (
                sha256(directory / "rows.json") != condition["rows_sha256"]
                or manifest["rows_sha256"] != condition["rows_sha256"]
                or manifest["leaderboard"] != condition["leaderboard"]
            ):
                raise ValueError("Input study observations changed")
            if manifest["model_artifact_hashes"] != baseline["model_artifact_hashes"]:
                raise ValueError("Input study changed model weights")
            regime = condition["economic_regime"]
            if not regime:
                continue
            economic = EconomicRegime.model_validate(regime)
            if (
                economic.depth_multiplier != 1
                or economic.taker_fee_rate is not None
                or economic.costs is not None
                or not economic.additional_submission_latency_ms
            ):
                continue
            paired = next(
                p
                for p in study["paired_comparisons"][condition["name"]]["policies"]
                if p["policy"] == gate.identity
            )
            score = next(
                r["score"] for r in manifest["leaderboard"] if r["policy"] == gate.identity
            )
            if baseline_score > 0 and score <= 0 and paired["episode_bootstrap_95"][1] < 0:
                candidates.append((score - baseline_score, condition["name"], manifest, economic))
        if not candidates:
            raise ValueError("No supported latency-reversal question; no follow-up submitted")
        _, name, selected, economic = min(candidates, key=lambda c: (c[0], c[1]))
        attribution = analyze(root, selected["tournament_id"], gate.identity)
        losses: dict[str, Any] = {}
        for item in attribution["episodes"]:
            losses[item["family"]] = losses.get(item["family"], 0) + min(amount(item["net_pnl"]), 0)
        stressed = [f for f in sorted(losses, key=lambda f: (losses[f], f)) if losses[f] < 0][:2]
        controls = [f for f in ("calm", "deep") if f not in stressed]
        if len(stressed + controls) % 2 == 0:
            controls.append(
                next(
                    f
                    for f in ("thin", "one_sided", "liquidity_shock")
                    if f not in stressed + controls
                )
            )
        families = tuple(stressed + controls)
        if not stressed:
            raise ValueError("Observed loss families required")
        challenge = DatasetSpec(
            episodes=episodes,
            seed=seed,
            families=families,
            label_target="unmatched",
            decision_scope="first_admitted",
            observation_latency_ms=baseline_spec.challenge.observation_latency_ms
            if baseline_spec.challenge
            else 100,
        )
        DatasetSpec.model_validate({**challenge.model_dump(mode="json"), "seed": seed + episodes})
        if any(seed < end and start < seed + 2 * episodes for start, end in seed_ranges(root)):
            raise ValueError("Follow-up seed range overlaps existing research or reserved plans")
        delay = economic.additional_submission_latency_ms
        if not 2 <= delay <= 5000:
            raise ValueError("Delay must support bounded half/double follow-up")
        record = {
            "director_id": identity,
            "director_version": "adaptive-latency-1",
            "state": "PLANNED",
            "created_at": time.time(),
            "code_revision": revision(),
            "source_hash": source,
            "producer_hashes": producer_hashes(),
            "model_artifact_hashes": baseline["model_artifact_hashes"],
            "research_question": "Does the observed latency reversal recur on fresh directed challenge families, and how does it change at the next preregistered delay?",
            "hypothesis": "Residual-leg losses persist under delay on independent generated identities.",
            "planning_rule": "Select the largest downside-score reversal among pure-latency conditions with negative paired mean CI; prioritize the two largest losing families, retain calm/deep controls, and use an odd family count so seed-parity settlement varies within families.",
            "input_study": {
                "study_id": study["study_id"],
                "path": str(report_path.resolve()),
                "sha256": sha256(report_path),
                "selected_condition": name,
            },
            "input_attribution": attribution,
            "baseline_template": baseline_spec.model_dump(mode="json"),
            "gate": gate.model_dump(mode="json"),
            "challenge_template": challenge.model_dump(mode="json"),
            "family_seed_parity_counts": {
                family: {
                    str(parity): sum(
                        challenge.families[i % len(challenge.families)] == family
                        and (seed + i) % 2 == parity
                        for i in range(episodes)
                    )
                    for parity in (0, 1)
                }
                for family in challenge.families
            },
            "initial_delay_ms": delay,
            "adaptive_rule": {
                "nonpositive_gate_downside_score": "half initial delay",
                "positive_gate_downside_score": "double initial delay",
                "policy_retuning": False,
            },
            "reserved_seed_ranges": [
                [seed, seed + episodes],
                [seed + episodes, seed + 2 * episodes],
            ],
            "budget": {
                "maximum_cycles": 2,
                "maximum_jobs": 4,
                "groups_per_cycle": episodes,
                "maximum_variants": 2 * 2 * episodes * 3 * 5,
                "worker_cpu_cores": 1,
                "worker_memory_mb": 4096,
                "job_wall_seconds": 1800,
                "coordinator_wall_seconds": 9000,
            },
            "cycles": [],
            "steps": [
                {"name": f"cycle {cycle + 1}: {condition}", "state": "PENDING", "artifact": None}
                for cycle in range(2)
                for condition in ("baseline", "delay")
            ],
            "current_stage": None,
            "limitations": [
                "Directed family selection uses previously observed failures; results do not represent all synthetic families",
                "Two conditions in each cycle share source groups; cycles use disjoint seeds",
                "Adaptive delay assignment is exploratory; no estimated population break-even frontier",
                "Frozen gate and weights; no selection, retraining or promotion from challenge outcomes",
                "Synthetic hypothetical outcomes; no empirical calibration or real profitability",
            ],
        }
        guard(root, record)
        for source_path in record["producer_hashes"]:
            source_file = Path(source_path)
            atomic_bytes(destination.parent / "source" / source_file.name, source_file.read_bytes())
        frozen = destination.parent / "preregistration.json"
        atomic_json(frozen, record)
        record["preregistration_sha256"] = sha256(frozen)
        atomic_json(destination, record)
        return record


def job_spec(record: dict[str, Any], cycle: int, condition: str) -> jobs.JobSpec:
    template = record["baseline_template"]
    challenge = {**record["challenge_template"], "seed": record["reserved_seed_ranges"][cycle][0]}
    delay = record["initial_delay_ms"] if cycle == 0 else record["cycles"][0]["next_delay_ms"]
    config = {
        **template,
        "challenge": challenge,
        "max_episodes": challenge["episodes"],
        # Directed challenges produce descriptive comparisons, not promotion.
        "minimum_champion_episodes": 2000,
        "economic_regime": None
        if condition == "baseline"
        else EconomicRegime(additional_submission_latency_ms=delay).model_dump(mode="json"),
    }
    return jobs.JobSpec(
        kind="tournament",
        tournament=TournamentSpec.model_validate(config),
        max_wall_seconds=record["budget"]["job_wall_seconds"],
    )


def finish_cycle(root: Path, record: dict[str, Any], cycle: int) -> None:
    steps = record["steps"][cycle * 2 : cycle * 2 + 2]
    control, candidate = (step["artifact"]["identity"] for step in steps)
    comparison = compare(root, control, candidate)
    directory = artifact_path(root, "tournaments", candidate)
    manifest = read(directory / "manifest.json")
    gate = GateSpec.model_validate(record["gate"]).identity
    score = next(r["score"] for r in manifest["leaderboard"] if r["policy"] == gate)
    paired = next(p for p in comparison["policies"] if p["policy"] == gate)
    attribution = analyze(root, candidate, gate)
    initial = record["initial_delay_ms"]
    next_delay = initial // 2 if score <= 0 else initial * 2
    outcome = {
        "cycle": cycle + 1,
        "comparison": comparison,
        "loss_attribution": attribution,
        "gate_downside_score": score,
        "next_delay_ms": next_delay,
        "rule_fired": "nonpositive_gate_downside_score"
        if score <= 0
        else "positive_gate_downside_score",
    }
    record["cycles"].append(outcome)
    finding_id = record["director_id"] + f"-cycle-{cycle + 1}"
    finding = {
        "finding_id": finding_id,
        "director_id": record["director_id"],
        "tournament_id": candidate,
        "title": f"Adaptive latency follow-up cycle {cycle + 1} completed",
        "research_question": record["research_question"],
        "hypothesis": record["hypothesis"],
        "code_revision": record["code_revision"],
        "source_hash": record["source_hash"],
        "seed": record["reserved_seed_ranges"][cycle][0],
        "configuration": manifest["configuration"],
        "outcome": outcome,
        "created_at": time.time(),
        "interpretation": f"Frozen gate downside score {score:.3f}; paired mean change {paired['mean_pnl_difference']:.3f}, grouped 95% interval {paired['episode_bootstrap_95']}. {attribution['losing_variants']} losing variants. No model or threshold change follows.",
        "caveats": record["limitations"],
        "next_experiment": f"Preregistered next cycle uses {next_delay}ms additional delay on disjoint seeds."
        if cycle == 0
        else "Budget complete. Investigate opportunity-persistence or recovery semantics before proposing revised policies; keep these challenge cases out of validation selection.",
    }
    atomic_json(artifact_path(root, "findings", finding_id) / "manifest.json", finding)


def tick(root: Path, identity: str) -> dict[str, Any]:
    directory = artifact_path(root, "directors", identity)
    with (directory / "coordinator.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = directory / "manifest.json"
        record = read(path)
        if record["state"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            return record
        guard(root, record)
        record.setdefault("started_at", time.time())
        if time.time() - record["started_at"] > record["budget"]["coordinator_wall_seconds"]:
            raise TimeoutError("Coordinator wall budget exceeded")
        record["state"] = "RUNNING"
        for index, step in enumerate(record["steps"]):
            if step["state"] == "COMPLETED":
                continue
            cycle = index // 2
            if cycle > len(record["cycles"]):
                raise ValueError("Adaptive prerequisite cycle missing")
            record["current_stage"] = step["name"]
            spec = job_spec(record, cycle, "baseline" if index % 2 == 0 else "delay")
            if not step.get("job_id"):
                # Publish intent before submission. Recover a job created before a
                # coordinator crash without creating a second matching job.
                step.setdefault("submission_intent_at", time.time())
                atomic_json(path, record)
                existing = [read(p) for p in (root / "jobs").glob("*/job.json")]
                matches = [
                    j
                    for j in existing
                    if j["configuration"] == spec.model_dump(mode="json")
                    and j["submitted_source_hash"] == record["source_hash"]
                    and j["created_at"] >= step["submission_intent_at"]
                ]
                if len(matches) > 1:
                    raise ValueError("Ambiguous recovered submission; no duplicate job launched")
                job = matches[0] if matches else jobs.create(root, spec)
                step["job_id"] = job["job_id"]
                step["state"] = "RUNNING"
                step["artifact"] = {"kind": "jobs", "identity": job["job_id"]}
                atomic_json(path, record)
            job = jobs.inspect(root, step["job_id"])
            if (
                job["configuration"] != spec.model_dump(mode="json")
                or job["submitted_source_hash"] != record["source_hash"]
            ):
                raise ValueError("Follow-up job changed configuration or source")
            step["progress"] = job.get("progress")
            if job["state"] in {"FAILED", "CANCELLED"}:
                step["state"] = job["state"]
                record.update(state=job["state"], error=job.get("error"), current_stage=None)
                atomic_json(path, record)
                return record
            if job["state"] != "COMPLETED":
                atomic_json(path, record)
                return record
            tournament = read(
                artifact_path(root, "tournaments", job["result"]["tournament_id"]) / "manifest.json"
            )
            if (
                tournament["configuration"] != spec.tournament.model_dump(mode="json")
                or tournament["source_hash"] != record["source_hash"]
                or tournament["model_artifact_hashes"] != record["model_artifact_hashes"]
            ):
                raise ValueError("Completed follow-up differs from frozen specification")
            step.update(
                state="COMPLETED",
                completed_at=time.time(),
                artifact={"kind": "tournaments", "identity": tournament["tournament_id"]},
            )
            if index % 2 == 1:
                finish_cycle(root, record, cycle)
            atomic_json(path, record)
        record.update(state="COMPLETED", completed_at=time.time(), current_stage=None)
        atomic_json(path, record)
        return record


def stop(root: Path, identity: str, state: str = "CANCELLED", error: str | None = None) -> None:
    directory = artifact_path(root, "directors", identity)
    with (directory / "coordinator.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "manifest.json"
        record = read(path)
        if record["state"] == "COMPLETED":
            return
        for index, step in enumerate(record["steps"]):
            if step.get("submission_intent_at") and not step.get("job_id"):
                spec = job_spec(record, index // 2, "baseline" if index % 2 == 0 else "delay")
                matches = [
                    job
                    for file in (root / "jobs").glob("*/job.json")
                    if (job := read(file))["configuration"] == spec.model_dump(mode="json")
                    and job["submitted_source_hash"] == record["source_hash"]
                    and job["created_at"] >= step["submission_intent_at"]
                ]
                if len(matches) > 1:
                    raise ValueError("Ambiguous recovered submission during cancellation")
                if matches:
                    step["job_id"] = matches[0]["job_id"]
            if step.get("job_id") and jobs.inspect(root, step["job_id"])["state"] in {
                "QUEUED",
                "RUNNING",
            }:
                jobs.cancel(root, step["job_id"])
                step["state"] = "CANCELLED"
        record.update(state=state, error=error, current_stage=None)
        atomic_json(path, record)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--baseline", required=True)
    plan.add_argument("--seed", type=int, required=True)
    plan.add_argument("--episodes", type=int, default=60)
    for action in ("tick", "run", "stop"):
        command = sub.add_parser(action)
        command.add_argument("--director", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        record = create_plan(args.root, args.baseline, args.seed, args.episodes)
        print(json.dumps({"director_id": record["director_id"], "state": record["state"]}))
    elif args.command == "stop":
        stop(args.root, args.director)
    elif args.command == "tick":
        record = tick(args.root, args.director)
        print(
            json.dumps(
                {
                    "director_id": record["director_id"],
                    "state": record["state"],
                    "current_stage": record["current_stage"],
                }
            )
        )
    else:

        def interrupted(signum: int, frame: Any) -> None:
            raise KeyboardInterrupt("Coordinator interrupted")

        signal.signal(signal.SIGTERM, interrupted)
        try:
            while True:
                record = tick(args.root, args.director)
                print(
                    json.dumps(
                        {"state": record["state"], "current_stage": record["current_stage"]}
                    ),
                    flush=True,
                )
                if record["state"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
                time.sleep(15)
        except (Exception, KeyboardInterrupt) as error:
            stop(
                args.root,
                args.director,
                "CANCELLED" if isinstance(error, KeyboardInterrupt) else "FAILED",
                str(error),
            )
            raise
