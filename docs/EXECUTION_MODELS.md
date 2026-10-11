# Explicit paper execution assumptions

| Preset | Added latency | Jitter | Observed liquidity fraction | Adverse ticks |
| --- | --- | --- | --- | --- |
| optimistic | 0 ms | 0 | 1.0 | 0 |
| standard | 200 ms | uniform 0–50 ms | 0.8 | 0 |
| conservative | 750 ms | uniform 0–250 ms | 0.5 | 1 |

Market-specific seconds delay and documented 250 ms `itode` delay are added when
public metadata establishes them. An unknown market delay rejects paper admission.
Fixed or uniform latency, jitter, acknowledgment delay, quantity availability and
adverse ticks are configurable in the API. These distributions are assumptions,
not empirical measurements. Seeds and all parameters are retained.

Each leg independently submits, matches at its scheduled time and acknowledges.
Limits stay at the evaluated price; adverse movement may expire a leg instead of
filling above its approved limit. Internal IOC corresponds to partial-fill-and-expire
semantics, not a claimed exact implementation of exchange FAK collateral targets.
Lost/out-of-order acknowledgments cannot create another submission. Fees are recomputed
by the virtual venue independently from scanner bounds. No maker queue/rebate revenue,
competing orders, sells or market-impact inference exists.

When present data cannot establish continuity, the broker expires rather than invents
a fill. It does not fill retroactively across downtime. Consumed liquidity is never
blindly replenished by repeated snapshots. Models are recorded per position and remain
fixed for its lifecycle even when the control selects a different future preset.

`POST /api/experiments` runs the production state machine on the clearly labeled
synthetic fixture. `compare=true` runs identical strategy/seed/data under the three
presets. History is persistent; artifacts retain dataset hash, economic/strategy/risk
versions, execution configuration, input commands, timestamps, seed, portfolio evolution,
errors and reproducibility hash. Download with `GET /api/experiments/{id}`. Custom
parameters are replayable through the same JSON request; preset CLI examples:

```bash
.venv/bin/python scripts/paper_lab.py --seed 7 --model standard --fault withdraw
.venv/bin/python scripts/paper_lab.py --seed 7 --compare
```

The recorded default comparison gives 0.50 optimistic, 0.40 standard and 0 conservative
**virtual** settled P&L on an artificial ten-share opportunity. This demonstrates model
sensitivity, not live economic potential. All values derive from the supplied fixture
and resulting journal. Full evidence: `MILESTONE_2_DIFFERENTIAL.json`.
