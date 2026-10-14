# Reality Mission 2 — requirement and completion audit

Status: **accepted for engineering handoff**. Gates A–G and all twelve hard
completion conditions are verified within the public-observation scope below.
Scientific model eligibility and multi-week performance remain insufficient;
those are explicitly later evidence milestones, not invented completion claims.
Final authoritative snapshots are in `REALITY_GATE_G_CHECKPOINT.json`. The full
backend run had two shared fixture timeouts under CPU throttling; the unchanged
four-test module passed at one CPU. Every non-skipped case is covered by a passing
run, and original failures are retained alongside their rechecks.

## Request sections 1–28

| Section | Requirement | Authoritative evidence and limits |
|---|---|---|
| 1 | Preserve and inspect the baseline | Protected main is clean at `8acab229…`; `REALITY_GATE_G_BASELINE_IDENTITIES.json` matches Laboratory/Arena identities to Gate A. Development is `project/reality` in its separate worktree. |
| 2 | Sustainable continuous recording | `deploy/reality.json`, `reality-storage-policy.json`, five-minute capacity service/timer, `operations.py`; 24 GiB raw + separate 24 GiB archive, 20 GiB reserve, finite retention stop, no raw pruning. Current capacity is timestamped in gate checkpoints. |
| 3 | Independent operation and safe deployment | `scripts/reality_deployment.py`, collector resource/lease tests, systemd units and unchanged collector PID 2288376 through B–G. Frontend/API own isolated preview state. |
| 4 | Broader, unbiased panel evidence | Eight-market bounded stratified selection, frozen seed, complete bounded discovery response/rejection records, selection roles and liquidity/expiry/update metadata. Bounded discovery is explicitly not a representative sample of the whole venue. |
| 5 | Protocol diversity and exclusions | `panel.py`, `discovery.py`, recorded payoff/fees/ticks/lifecycle. Verified same-condition V1 CTF only. V2/UpDown and augmented ambiguity remain excluded rather than fabricated. Gate A documents official/public-response investigation. |
| 6 | Timing and quality | UTC/monotonic receipt and processing/persistence samples, gaps, revision-4 reconstruction, clock health and independent REST comparisons. No venue sequencing guarantee or one-way/order-submission latency claim. |
| 7 | Versioned genuine datasets | Accepted dataset `23201960…`, immutable source manifests/code/row hashes, causal full-depth features and separate hypothetical context. `REALITY_GATE_G_RESEARCH_INTEGRITY.json` rechecks all 13,216 rows. |
| 8 | Legitimate observation labels | `research_measurements.py`, versioned horizon/tolerance rules, known/censored distinctions and source arithmetic audit in Gate B. Quote/depth persistence, moves, displayed cost, disruption and quoted-exit values remain public measurements. |
| 9 | No manufactured execution truth | Dataset validators, scenario and registry schemas, shadow journal audits and UI boundary: actual fills/queue/impact remain unknown. No order path, wallet or authenticated trading API exists. |
| 10 | Leakage and evaluation isolation | Chronological train/validation/test, embargo, connected families/time grouping, held-out families, consumed overlapping-period ledger. Gate G rechecks structure and ledger; Gate B audited raw source and regenerated exact rows. Cross-day coverage remains insufficient. |
| 11 | Empirical execution calibration | Accepted calibration `8e29bed2…`, joint observable resampling, receipt dynamics, spreads/depth/change distributions and unknowns. Private matching/acknowledgment/impact are not fitted as observed facts. |
| 12 | Four explicit execution assumptions | `execution_research.py`, immutable assumption identities, original-price limits, fees, capital, partial/unmatched payoff and recovery bounds. Optimistic/intermediate/conservative/stress are compared on matched candidates. |
| 13 | Preserved simulator comparison | Calibration report contains 304 synthetic controls across 19 families/seeds 0–15 versus genuine observations; original presets and artifacts are preserved. Synthetic opportunity frequency is not real-market prevalence. |
| 14 | Real-target Arena workflow | `model_training.py`, Arena lightweight model/MLP reuse, train-only preprocessing and immutable portable registry. Accepted run `9f593b0e…` has 13 control/learner artifacts, all currently verified. |
| 15 | Proper prediction evaluation | Frozen report contains Brier/log loss/calibration, precision/recall when meaningful, regression MAE/RMSE/tails, grouped exploratory intervals and family/category/day slices. Single-day/conditional coverage prevents broad accuracy claims. |
| 16 | Eligibility gates | Coverage, compatibility, calibration, reproducibility, baseline-relative/grouped improvement and economic-usefulness checks. Experimental prediction probes cannot authorize policy action. No scientific champion. |
| 17 | Honest insufficiency and future work | Final-test risk tree worsens versus constant; depth heuristic wins; quote labels positive-only, adverse moves zero, no initial opportunities. Durable seven-day coverage trigger and weekly bounded future plan configured, no auto-promotion. |
| 18 | Live causal shadow decisions | Frozen code/models/rules plus append-only journal, durable commit markers, exact input books/features/source hashes, policy decisions and latency. Collector and shadow services are independent of the UI. |
| 19 | Later public follow-up and hypothetical economics | New synchronized receipts only, actual decision/commit chronology, explicit missingness, all four horizons and scenario/unmatched/recovery accounting. `shadow_audit.py` independently replays real inputs and known labels. |
| 20 | Genuine forward protocol | Campaign `adf91d04…` frozen before its fourteen-day start, immutable models/controls/analysis/risk/selection rules; no opened-period retuning. Gate G source audit verifies 344 prospective decisions, 102 valid initial states and eight observed follow-ups in a consistent journal snapshot. |
| 21 | Economic feasibility and sensitivity | Declared fee curve/rounding reserve, depth/minimum size, quantity/capital grids, finance/settlement/redemption assumptions and unmatched recovery bounds. No actual profitability is identified. |
| 22 | Nine native dashboard areas | `Reality.tsx`, bounded `/api/reality`, overview/explorer/history/opportunities/calibration/models/shadow/forward/operations. Real data, frozen artifacts, evidence drill-downs, UTC, no synthetic banner on Reality. |
| 23 | Usable, bounded interface | Explanations, responsive desktop/390-pixel layouts, loading/error/empty states, search/filters, sampled replay, bounded windows/pages, artifact hashes and raw offsets. Historical update-rate lower bounds are explicitly sampled, not venue message intensity. |
| 24 | Independent scientific verification | 130 focused backend passes at Gate F, source arithmetic/regeneration, corruption/leakage/grouping/period-reuse tests, current immutable artifact checks and independent prospective raw replay. Full 740-test regression completed: 737 passed, one optional PostgreSQL skip, two shared fixture timeouts. The unchanged four-test module passed at one CPU. All 739 non-skipped cases have passing coverage across the full run and resolved recheck. |
| 25 | Stress coverage | Numeric labeled fixtures prove gaps, missing legs, closure/ticks, thin depth, partial positions, large sizes and recovery failure. Real calibration records depth retention down to ~0.003 and real gap/resync dynamics. Rare public stresses are not evidence of hypothetical execution or general stress performance. |
| 26 | Engineering/research measurements | Gate B dataset build/audit/reproduction timings, Gate C calibration timings, Gate D fitting/reproduction/resource evidence, Gate F bounded API latency/bytes, Gate G recorded inference/support-gate timing and shadow/raw audit counts. No extra heavy fitting solely for benchmarking. |
| 27 | Continuous durable operation | Enabled collector, shadow and capacity/archive/research/integrity timers; user lingering enabled. File-only workers, disk bounds, writer exclusion, recovery/checkpoints, terminal states and alerts. PrivateNetwork isolation is requested but unsupported by this host's user namespace; code contains no shadow order/network path. |
| 28 | Comprehensive documentation | `REALITY_CALIBRATION_LABORATORY.md`, README and roadmap cover architecture, semantics, methods, findings, operations, UI and future coverage. This ledger and the completed Gate G checkpoint disclose actual scope, outcomes, warnings and future evidence needs. |

## Hard completion boundary

| Condition | Status | Evidence |
|---|---|---|
| 1. Reliable bounded collector | Verified at current checkpoints | Active original PID, no automatic restarts/failures, sustainable budget/forecast/reserve/timers. |
| 2. Broader observations and measured quality | Verified, bounded scope | Eight-market panel and recorded candidate/quality evidence; selection bias and unsequenced continuity remain explicit. |
| 3. Reproducible timestamp-safe datasets | Verified | Gate B raw audit/exact regeneration plus current full structural/hash check. |
| 4. Correct observable labels | Verified within public-data scope | Independent source arithmetic and censoring tests; no fill labels. |
| 5. Real versus synthetic comparison | Verified | Hash-pinned Gate C report and preserved synthetic controls. |
| 6. Calibrated components and uncertainty scenarios | Verified | Joint public kernel plus four explicit execution assumptions and unknowns. |
| 7. Trained workflow or demonstrated insufficiency | Verified | Frozen real-target run and negative held-out findings; no eligible model. |
| 8. Live shadow without orders | Verified | Active original shadow PID, frozen code and actual order count zero. |
| 9. Genuine prospective accumulation | Verified | Independent current campaign chronology/raw/follow-up audit. |
| 10. Meaningful native interface | Verified | Nine areas, frontend/browser evidence and corrected active-segment inspection. |
| 11. Passing tests and integrity with disclosures | Verified across full run and targeted rechecks | 739 unique backend cases passed, one optional PostgreSQL skip; initial two fixture timeouts resolved by unchanged four-test recheck at one CPU. All 27 frontend tests, typing/lint/build, five legacy browser scenarios and corrected Reality rechecks pass. Source, shadow, model/dataset, archive and protected Arena audits pass. Initial failures/warnings remain disclosed. |
| 12. Protected historical evidence unchanged | Verified | All payload metadata predates Mission 2, entire content census, 63 retained Laboratory replay hashes, protected 162k/18k counts and baseline code identity. Full 52,323-row Arena replay verification exactly matches seven datasets, 45 models, 27 completed tournaments and the two pre-existing partial tournaments in the preservation baseline. |

All twelve conditions are accepted against the cited current-state evidence.
No required engineering work remains in Mission 2. Multi-week population
conclusions, wider protocol support, adequate cross-day target coverage and
independent decision usefulness remain later scientific milestones. No model
promotion, main-branch merge, external push or real trading was performed.
