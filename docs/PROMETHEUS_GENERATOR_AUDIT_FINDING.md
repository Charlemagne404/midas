# Fixed-policy settlement revision audit

Two matched 100-group studies compare legacy seed-parity settlement with hashed settlement. Books, account, execution assumptions and fixed policy decisions before settlement are identical. No training, retuning or promotion occurred.

| Policy | Revised minus legacy mean P&L | Grouped 95% interval |
|---|---:|---|
| arbitrage | -0.092667 | [-0.3183333333333333, 0.09068333333333327] |
| conservative | -0.013533 | [-0.3386966666666666, 0.33077666666666644] |
| model-33cddb0d92024c2bb0a3b34a | -0.038533 | [-0.28074499999999997, 0.21383999999999945] |
| model-ef77bbbd7d1f4be78c41c0b6 | -0.053333 | [-0.1366666666666667, 0.0] |
| model-f587b98d06f34441bb040877 | -0.053333 | [-0.1366666666666667, 0.0] |
| no_trade | 0.000000 | [0.0, 0.0] |
| random | 0.140467 | [-0.026666666666666665, 0.4160666666666667] |

All reported mean-change intervals include zero. Both classifier policies have identical aggregate outcomes: mean 1.353024→1.299690 and downside score 1.353024→0.823690. Their sampled tail loss rises from zero to0.476. PPO mean1.503117→1.464584 and downside score-1.277683→-1.719723. No unique research champion is designated.

The terminal payout changes in48 source groups. Verification covers4200 saved replays,45696 journal states using independent rational/Decimal arithmetic and2100 matching pre-settlement journal/decision pairs. Root bundle verification checks4391 payloads. Separate reexecution reloads production logistic, MLP and PPO weights and deterministic controls for24 selected episodes, matching exact requests, scores, observations and financial/journal hashes.

Interpretation: changing an unobserved terminal-outcome assumption can worsen sampled downside even when observable inputs and decisions stay fixed. The audit does not establish a statistically decisive mean effect, a generally robust policy, causal market behavior or empirically calibrated execution. Logistic and MLP tie here; neural complexity provides no demonstrated incremental policy benefit on this cohort.

Limits: one fixed seed cohort; deterministic settlement-only revision; same price paths and execution model; multiple comparisons without correction; source-group variants remain correlated. Training and classifier labels were not revised. The source hash and explicit revision are stored in both manifests.

Next: broader market-path/family ordering revisions and chronological public-observation quality. Do not select thresholds against this opened challenge.
