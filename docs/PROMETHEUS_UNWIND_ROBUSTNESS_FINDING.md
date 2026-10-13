# Fixed recovery robustness: two fresh cohorts

Both preregistered 150-group cohorts completed. Policies, thresholds and execution assumptions were unchanged; no fitting, selection or promotion occurred.

| Seed | Sell minus hold mean | Grouped 95% interval | Sell minus repair mean | Grouped 95% interval |
|---|---:|---|---:|---|
| 423071 | 0.032160 | [0.0, 0.08789333333333332] | 0.025689 | [0.0, 0.07495111111111111] |
| 453071 | 0.022631 | [-0.038933333333333334, 0.09973333333333334] | 0.024346 | [-0.02065911111111111, 0.08811613333333325] |

Neither cohort establishes a robust mean improvement over hold or repair: every corresponding interval includes zero. Tail loss improved descriptively in both. Worst loss improved from -5.304 to -3.99 in cohort one, but remained -8.832 in cohort two.

Selling filled in two and five standard-execution groups respectively. Across both cohorts, eight conservative requests produced no fills. Optimistic execution had no residual inventory at saved sell proposal times. No primary comparison was conditioned on filled groups.

Verification covered 3,600 saved replays with independent rational/Decimal accounting, 308 recomputed proposals and 33 requests. Separate root checks verified 3,752 exported payloads and reexecuted all four policies for every intervention-filled source/execution pair: 28 exact reproductions.

The worst sell case in cohort one was selected descriptively for event reduction. A fixed loss threshold of one virtual USD retained -1.755 virtual USD while reducing eight events to three, in ten trials. Two executions of the reduced case matched exactly. This is a valid economic loss, not a software defect. Single optional-event deletion minimality does not prove global minimality.

Limits: same generator revision, sparse interventions, hypothetical fills/costs, correlated execution variants, multiple uncorrected comparisons, no empirical profitability or guaranteed loss bounds. Fresh seeds do not establish revision-level generalization.

Next priority: generator revision audit that removes family/settlement parity coupling while preserving the existing generator and archives. Do not retune these opened cohorts.
