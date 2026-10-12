# Refitted feature ablations

Supervised training and sweep candidates accept `excluded_features`, a list of
unique names from the fixed observable feature schema. At least one input must
remain. Fixed constant and heuristic controls cannot request a mask.

Excluded raw inputs become zero before fitting the training-only scaler and the
model. The same serialized mask applies before inference and support checks.
The schema and existing neural layer sizes remain compatible; excluded channels
carry no information. Inference still rejects nonfinite raw feature vectors.
Normalization statistics for excluded columns are zero mean and unit scale.
Masks are recorded in configuration, parameters and checkpoints; reload rejects
configuration/parameter disagreement. Legacy models default to no exclusions.

The Research Director offers a fixed twelve-fit study: logistic and 32-unit MLP
models, seeds 11 and 29, and full input / no direct depth / no declared execution
inputs. Other training settings remain fixed. MLP stopping uses validation loss.

The sweep persists pairwise changes in validation Brier score after refitting,
averaged across optimization seeds and grouped by underlying source episode.
Positive changes mean removal worsened prediction. A 2000-replicate source-group
bootstrap preserves correlated execution variants. Optimization seeds are not
additional market observations. Model selection continues to use validation only;
the study does not open final tests or promote a policy.

These comparisons reuse validation data and are exploratory, with no multiplicity
correction. Removing depth columns retains derived quantity/edge proxies. Removing
execution inputs investigates dependence on declared simulator assumptions; it
does not establish real fill probabilities. Feature removal does not prove
causality, economic value, or generalization. Only-edge, reward and historical
input ablations remain separate future experiments.
