"""Gymnasium decisions around the unchanged Midas broker, fills, risk and accounting."""

from decimal import Decimal
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from midas.arbitrage.engine import BinaryStrategy
from midas.arena.datasets import DatasetSpec
from midas.arena.features import FEATURES, extract
from midas.core.models import Evaluation, Status
from midas.laboratory.runtime import Environment, NoTrade
from midas.laboratory.spec import Scenario, generate
from midas.paper.broker import ExecutionModel, transition


class SizedStrategy(BinaryStrategy):
    def __init__(self, scenario: Scenario, fraction: Decimal):
        super().__init__(scenario.account.limits.max_age_ms, scenario.account.limits.min_edge)
        self.fraction = fraction

    def evaluate(self, *args: Any, **kwargs: Any) -> Evaluation:
        result = super().evaluate(*args, **kwargs)
        if result.status != Status.VERIFIED or self.fraction == 1:
            return result
        quantity = (result.quantity * self.fraction).quantize(Decimal(".01"))
        return super().evaluate(*args, **{**kwargs, "quantity": quantity})


class ControlledEnvironment(Environment):
    """Override strategy choice only. Production transition always enforces hard risk."""

    def __init__(self, scenario: Scenario, retain: bool = False):
        self.selected_action = 0
        self.decisions: list[dict[str, Any]] = []
        super().__init__(scenario, retain)

    def _apply(self, command: dict[str, Any]) -> None:
        strategy: BinaryStrategy
        if command["kind"] == "observe":
            strategy = (
                NoTrade()
                if self.selected_action == 0
                else SizedStrategy(
                    self.scenario, Decimal(".5") if self.selected_action == 2 else Decimal(1)
                )
            )
        else:
            strategy = BinaryStrategy()
        self.state = transition(self.state, command, strategy)
        for action in self.state["pending"]:
            self.clock.schedule(
                action["due"], action["id"], "action", {"action_id": action["id"]}, 20
            )


class ArenaEnv(gym.Env[Any, Any]):
    """One action per observed decision, with private venue events advanced internally.

    Reward is change in Laboratory cost-adjusted realized P&L, less incremental
    maximum drawdown and unmatched inventory penalties, and invalid action penalties.
    Unresolved inventory never earns theoretical profits. Penalties are explicit
    research preferences and not broker ledger charges or hard loss guarantees.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        spec: DatasetSpec | None = None,
        indices: list[int] | None = None,
        execution_models: tuple[str, ...] = ("standard",),
        retain: bool = False,
        scenario: Scenario | None = None,
    ) -> None:
        super().__init__()
        self.dataset_spec = spec or DatasetSpec()
        self.indices = indices if indices is not None else list(range(self.dataset_spec.episodes))
        if not self.indices:
            raise ValueError("Environment needs eligible episode identities")
        self.execution_models = execution_models
        self.retain = retain
        self.fixed_scenario = scenario
        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            -np.inf, np.inf, shape=(len(FEATURES) + 1,), dtype=np.float32
        )
        self.env: ControlledEnvironment | None = None
        self.previous_score = 0.0
        self.penalty = 0.0
        self.invalid_penalty = 0.0
        self.max_unmatched = 0.0
        self.max_drawdown = 0.0
        self.action_count = [0, 0, 0]
        self.action_explanation: dict[str, Any] = {}

    def _advance(self) -> None:
        assert self.env is not None
        while not self.env.finished:
            event = self.env.clock.peek()
            if (
                event
                and event.kind == "decision"
                and event.time <= self.env.scenario.epoch_ms + self.env.scenario.horizon_ms
            ):
                return
            self.env.step()
            portfolio = self.env.portfolio()
            self.max_unmatched = max(
                self.max_unmatched, abs(float(portfolio.get("net_exposure_shares", 0)))
            )
            self.max_drawdown = max(self.max_drawdown, float(portfolio.get("max_drawdown", 0)))

    def decision_features(self) -> tuple[list[float], bool]:
        assert self.env is not None
        observation = self.env.observe()
        event = self.env.clock.peek()
        if event and event.kind == "decision":
            observation["time_ms"] = event.time
        self.feature_error: str | None = None
        try:
            return extract(
                observation, self.env.scenario.account, self.env.scenario.observation_latency_ms
            )
        except ValueError as error:
            if not str(error).startswith("Future "):
                raise
            # Malformed time evidence causes deterministic abstention. The policy
            # receives a sentinel, never future book prices or future timestamp data.
            self.feature_error = str(error)
            return [0.0] * len(FEATURES), False

    def observation(self) -> tuple[Any, bool]:
        features, eligible = self.decision_features()
        # Fixed documented units, no held-out fitting. CPU PPO benefits from bounded scale.
        scale = np.array(
            [
                1,
                1,
                100,
                100,
                100,
                1,
                15000,
                1,
                100,
                100,
                100,
                100,
                1,
                1000,
                1000,
                1,
                10,
                1000,
                1000,
            ],
            dtype=np.float32,
        )
        return np.concatenate(
            [np.array(features, dtype=np.float32) / scale, [float(eligible)]]
        ).astype(np.float32), eligible

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[Any, dict[str, Any]]:
        super().reset(seed=seed)
        if self.fixed_scenario is not None:
            scenario = self.fixed_scenario
        else:
            index = int(self.np_random.choice(self.indices))
            model = str(self.np_random.choice(self.execution_models))
            execution = ExecutionModel.preset(model).model_copy(
                update={"seed": self.dataset_spec.seed + index}
            )
            scenario = generate(
                self.dataset_spec.families[index % len(self.dataset_spec.families)],
                self.dataset_spec.seed + index,
                execution,
            ).model_copy(
                update={"observation_latency_ms": self.dataset_spec.observation_latency_ms}
            )
        self.env = ControlledEnvironment(scenario, self.retain)
        self.previous_score, self.penalty = 0.0, 0.0
        self.invalid_penalty, self.max_unmatched, self.max_drawdown = 0.0, 0.0, 0.0
        self.action_count = [0, 0, 0]
        self.action_explanation = {}
        self._advance()
        observation, eligible = self.observation()
        return observation, {"eligible": eligible}

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        if self.env is None or self.env.finished:
            raise ValueError("Reset before stepping a terminated environment")
        observation, eligible = self.observation()
        invalid = not self.action_space.contains(action) or (int(action) != 0 and not eligible)
        selected = 0 if invalid else int(action)
        self.action_count[selected] += 1
        self.env.selected_action = selected
        self.env.decisions.append(
            {
                "time_ms": self.env.observe()["time_ms"],
                "action": selected,
                "requested_action": str(action),
                "invalid": invalid,
                "feature_error": self.feature_error,
                "explanation": dict(self.action_explanation),
                "observation": observation.tolist(),
            }
        )
        self.env.step()
        self._advance()
        result = self.env.result()
        if not result["passed"]:
            raise ValueError(f"Invariant violation terminates training: {result['errors']}")
        self.invalid_penalty += 0.1 if invalid else 0
        # Only increases in these quantities reduce reward; terminal settlement does
        # not refund an exposure penalty already incurred during an earlier decision.
        self.penalty = self.invalid_penalty + 0.02 * self.max_unmatched + self.max_drawdown
        score = float(result["metrics"]["net_simulated_pnl"]) - self.penalty
        reward = score - self.previous_score
        self.previous_score = score
        observation, eligible = self.observation()
        info = {
            "eligible": eligible,
            "invalid_action": invalid,
            "net_simulated_pnl": result["metrics"]["net_simulated_pnl"],
            "reward_penalty": self.penalty,
            "action_counts": list(self.action_count),
        }
        if self.env.finished:
            info["result"] = result
            info["decision_trace"] = self.env.decisions
        return observation, reward, self.env.finished, False, info
