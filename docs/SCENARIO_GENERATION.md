# Scenario generation

Frozen Scenario JSON records schema version, ID/family/provenance, seed, market and
outcome instruments, initial books/account, strategy/risk/execution configuration,
observation/processing latency, virtual epoch/horizon, scheduled events, cost assumptions,
dataset identity and expected invariants. All price/size/money fields use decimal strings.
ScenarioEvent defines an ID, relative time, priority, kind and payload. Event IDs must
be unique. Epoch-relative schedules also support captures preceding the demo epoch.

```python
from midas.laboratory.spec import generate
from midas.laboratory.runtime import execute
scenario = generate("liquidity_shock", 42)
result = execute(scenario)
assert result["economically_verified"] is False
```

The 19 generated families are calm, volatile, thin, deep, disappearing, liquidity_shock,
oscillating, divergent, near_resolution, unresolved, rounding, fees, low_capital,
one_sided, network_partition, metadata_conflict, cancel_race, uncertain_order and
ledger_mutation. Names describe parameterized fixtures, not empirically calibrated
regimes. Generation uses local seeded Random, integer tick prices, multiple depth
levels and scheduled changes. The last family is an explicit oracle-calibration mutation.

Declarative events support observation, market replacement, fault rules, cancellation,
expiration, settlement, pause/stop control, duplicate actions, checkpoints and controlled
ledger mutation. The virtual heap independently supports cancellation and replacement.
No settlement event means unresolved capital; settlement timing is an assumption.
`generate` returns reusable standalone scenarios; campaign generation resets capital
for each episode, pairs seed/data across strategy/model variants, and caps the low-capital
family by its sampled small portfolio and the campaign's explicit capital ceiling.

Campaign seeds are `(base_seed + episode_index) mod 2**32`, and families cycle in
configuration order. Strategy/model Cartesian sweeps use identical market events,
fee assumptions and risk limits. Scalar fee, latency and liquidity overrides are
supported; recorded fee evidence cannot be overridden. Multi-value automated
fee/latency/liquidity sweeps and correlated multi-market episodes remain deferred.

Properties/state-machine tests generate additional seeds, checkpoint boundaries,
schedule priorities and fractional payout vectors. The adversarial search mutates
timing around boundary values and combines faults. Million-run Extreme configurations
are optional and remain subject to disk, wall-time and worker budgets; no million-run
campaign was executed for Milestone 3.
