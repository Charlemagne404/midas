# Opportunity persistence at first venue arrival

Target: `persistence`. Label version: `original-quote-first-arrival-1`.

The binary label asks whether the first risk-admitted proposal's original share
quantity remains mathematically VERIFIED at its earliest scheduled submission
arrival, within its original allocated capital and both original leg-price
limits. It evaluates the actual generated venue state before either original
order submits. All earlier events are advanced through the unchanged simulator.

A positive label is not proof of two-leg completion. Processing delay, capacity
allocation, adverse ticks, the second leg's later arrival and subsequent market
changes can still prevent fills. A quote can remain mathematically profitable
and still receive a negative label because it violates an original order limit.
No arrival before the episode horizon is a negative label.

## Timestamp and information boundaries

The private venue uses exchange timestamps, rather than delayed observer receipt
timestamps. Label evaluation records this clock convention and a hash of the raw
venue state. An exchange timestamp later than arrival is invalid. The normalization
is confined to label evaluation; the raw venue books are not modified.

Features remain the 19 allowlisted values captured before the original risk
admission. Arrival times, private venue quotes, settlement outcomes, scenario IDs
and seeds are metadata or labels, never features. Persistence rows also retain
the original completion and unmatched-share outcomes for later descriptive
audits. Labeling does not alter the financial replay. Related execution variants
stay inside the same episode partition.

## Training and policy use

The existing base-rate, logistic, tree and PyTorch MLP trainers support this
binary target. The completion heuristic is excluded. Probability gates permit
persistence scores at or above their threshold; independent mathematical
eligibility and risk admission remain required. Reduced-size execution is not
separately calibrated by a full-proposal score.

Training and normalization use the training partition; selection uses validation.
The final partition must remain protected. New target quality, calibration and
actual policy outcomes must be evaluated before claiming decision improvement.
The model describes generated hypothetical quote behavior, not empirical fill
probability or real profitability.

## Initial production study

Preregister a fresh 1,001-group dataset beginning at seed 183071, using seven
families (thin, deep, calm, liquidity_shock, volatile, one_sided, disappearing),
three execution assumptions and first-admitted scope. The odd family schedule
varies settlement parity within each family, although settlement is not used by
this label. These seeds are separate from the opened adaptive studies.

Then fit logistic and MLP candidates with seeds 11 and 29, using the existing
bounded validation-only sweep and declared simplicity tolerance. Keep all final
classifier tests unopened during selection. A later matched policy comparison
requires its own preregistration and fresh source identities; classifier metrics
alone cannot establish policy benefit.
