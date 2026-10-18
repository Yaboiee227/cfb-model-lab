# NFL Stage 4 — Confidence / Edge / Release Calibration Policy

**Stage:** 4 — Confidence / Edge / Release Calibration  
**Current state:** framework may be completed now; betting-release evidence is not yet earned  
**Automatic threshold promotion:** prohibited

## Purpose

Stage 4 determines what language the product may use around confidence, model-market disagreement, betting relevance and recommendation release. It must prevent a common failure mode: converting a large numerical disagreement into a presumed edge without prospective evidence.

The current NFL model is a validated projection engine. It is not yet a validated betting recommendation engine.

## 1. Terminology contract

### Reliability

`Reliability` describes how trustworthy the model context is for that game relative to the validated architecture: stable QB state, resolved personnel, weather/roof certainty, source completeness and model-domain fit.

Reliability is **not** a claim that the side/total is more likely to cover.

### Model-market disagreement

Difference between the frozen canonical model and a timestamped market benchmark.

Until prospective calibration earns stronger language, use:

- `Model-Market Difference`
- `Model-Market Disagreement`
- `Projection Difference`

Do not label the raw difference `edge` on the public site.

### Betting confidence

A future release-layer quantity that may exist only after a prospectively validated mapping from frozen model/market/context inputs to observed market outcomes.

No betting confidence score is currently released.

## 2. Prospective evidence milestones

These milestones permit **review**, never automatic promotion.

### Projection beta review

Minimum evidence:

- at least **40 completed prospective games**,
- across at least **3 distinct frozen weeks**,
- immutable prediction snapshots verified,
- grading pipeline complete,
- no material leakage/process failure.

Passing this milestone may support public `Research/Beta` NFL projections. It does not authorize PLAY/LEAN betting labels.

### Recommendation calibration review

Minimum evidence:

- at least **75 completed prospective games**,
- across at least **5 distinct frozen weeks**,
- context/market timestamps complete enough for the evaluated subset,
- enough observations within any proposed decision bucket to avoid a one-week/small-sample rule,
- no automatic promotion from a single favorable bucket.

Passing this milestone permits a formal Stage 4 calibration review. It does not automatically release recommendations.

## 3. Candidate calibration dimensions

Evaluate prospectively frozen outcomes across:

- absolute spread disagreement buckets,
- signed spread disagreement,
- absolute total disagreement buckets,
- signed total disagreement,
- reliability grade,
- hard-QB vs non-hard-QB state,
- elevated-weather vs normal environment,
- public-board-only vs executable-price-verified subset,
- canonical vs FTN50 challenger performance,
- week/time stability.

Historical thresholds may be used as descriptive priors only. They cannot become release rules without prospective confirmation.

## 4. Metrics required for any future release rule

For each proposed rule/bucket, track when applicable:

- sample size and number of distinct weeks,
- W-L-P versus the exact timestamped spread/total benchmark,
- win rate excluding pushes,
- Wilson confidence interval,
- model MAE/bias inside the bucket,
- comparison with adjacent buckets,
- stability across weeks,
- hard-QB/weather composition,
- public-board movement,
- verified CLV only for executable-price observations,
- price/juice assumptions.

A raw win percentage without uncertainty and sample context is insufficient.

## 5. Non-monotonicity rule

Stage 2 showed that larger historical model-market disagreement did not monotonically improve ATS or totals results.

Therefore:

- no `bigger difference = higher betting confidence` rule is allowed by default,
- proposed thresholds must be supported by prospective bucket behavior,
- isolated profitable-looking bins are treated as multiple-comparison risks until repeated.

## 6. Release states

### `HOLD`

Default state. Used whenever no validated betting threshold exists or a required context/execution gate is unresolved.

### `RESEARCH_BETA`

May be used for projections after the projection-beta review is explicitly passed. It is not a wager recommendation.

### `LEAN`

Locked. May only be introduced after recommendation calibration review and an explicit promotion decision supported by prospective evidence.

### `PLAY`

Locked. Requires stronger prospective evidence than LEAN, stable calibration, verified price assumptions and explicit promotion.

No automatic code path may upgrade HOLD to LEAN/PLAY solely because model-market disagreement exceeds a numeric threshold.

## 7. Alternative-line policy

Alternative-line recommendations remain locked until:

1. the main-market side/total release logic is prospectively validated,
2. exact alt-line prices are executable/timestamped,
3. probability/price tradeoffs are calibrated rather than guessed,
4. the alt-line policy is tested prospectively.

The model may display hypothetical or descriptive alternative thresholds for research, but they must not be labeled recommended bets.

## 8. Confidence display policy for website

Before recommendation calibration is earned, the NFL website may show:

- projection reliability,
- empirical prediction intervals,
- win probability (research/display validated),
- model-market disagreement,
- contextual flags,
- validation sample size/state,
- HOLD / Research status.

It may not show:

- betting confidence percentages,
- `edge` badges implying validated profitability,
- unit sizing,
- PLAY/LEAN labels,
- ROI/CLV claims unsupported by verified execution data.

## 9. Promotion review standard

A future recommendation rule can be considered only if:

- prospective sample milestone is met,
- the exact rule was defined before evaluating the decisive future sample or is subsequently revalidated on a new holdout period,
- results are not driven by one week or one context subgroup,
- uncertainty bounds are reported,
- pricing assumptions are realistic,
- context/execution completeness is adequate,
- there is no evidence of leakage or frozen-snapshot mutation.

## Stage 4 handoff

> Stage 4 framework is complete when the calibration dimensions, milestones, metrics, terminology and promotion rules are fixed. Current evidence remains insufficient for betting-release language because the prospective registry contains no completed Week 6 games yet. Keep recommendation state HOLD, accumulate prospectively frozen outcomes, and continue to Stage 5 production/audit verification so the evidence can be collected correctly.
