# CB Model Projections — NFL Project Spec

**Status:** Active development on `nfl-model-development`  
**Production branch:** `main` remains CFB production until explicit NFL release review.  
**League separation:** NFL and CFB models, data, validation evidence, records, and release states remain independent even when they share the same static website interface.

## Project goal

Build an NFL projection model that produces game point spreads, game totals, projected scores, and calibrated win probability derived from the canonical spread. Validate it honestly, track it prospectively, operate it weekly with an immutable audit trail, and integrate it into the existing CB Model Projections GitHub Pages site.

The model is a projection/research product. Model-vs-market differences are descriptive until prospective evidence earns any stronger release language.

## Required public disclaimer

> All content on CB Model Projections is model-generated and provided for research and entertainment purposes only. It is not betting advice and not an official wager recommendation. Past performance does not guarantee future results. Must be 21+ (or the legal age in your jurisdiction). If you or someone you know has a gambling problem, call 1-800-GAMBLER.

## Canonical six-stage workflow

1. **Core model / spread and totals architecture**
2. **Historical + walk-forward validation**
3. **Context + market execution layer**
4. **Confidence / edge / release calibration**
5. **Weekly production / audit / tracking system**
6. **Website / operating interface**

Stages are reviewed in order. Existing work may satisfy a later stage technically, but a later stage is not considered released until earlier evidence gates are satisfied.

---

# Stage 1 — Core model / spread and totals architecture

**Stage status:** `COMPLETE / LOCKED_FOR_WEEK6_RESEARCH`  
**Audit result:** PASS  
**Production/recommendation release:** HOLD

## Modeling philosophy

The canonical NFL model is deliberately compact. Feature families are promoted only when they improve leakage-safe out-of-sample prediction and remain reasonably stable across unseen seasons. More variables are not assumed to be better.

No manual narrative point adjustments are allowed. Context such as quarterback changes, injuries, weather, or travel may gate reliability/release without changing the numeric projection unless a coefficient has earned promotion through validation.

## Canonical spread architecture

**Canonical spread:** `frozen core + defensive coverage + market-independent win Elo + margin rating`

The core spread model is ridge regression trained on pregame-only team/matchup features including:
- blended net EPA differential,
- blended net success-rate differential,
- last-3 net EPA differential,
- last-3 net success-rate differential,
- pass matchup differential,
- rush matchup differential,
- explosive-pass matchup differential,
- explosive-rush matchup differential,
- sack matchup differential,
- neutral early-down pass-rate differential,
- rest differential,
- neutral-site indicator.

The promoted defensive coverage layer adds leakage-safe coverage information that survived robustness testing.

Two recursive market-independent rating features are also promoted:
- **win Elo differential** — updated only after completed games,
- **margin-rating differential** — updated from prior-game scoring residuals only.

Frozen rating dynamics selected from 2022-only tuning for the final architecture:
- win Elo K: `40`
- win Elo HFA parameter: `35` Elo points
- offseason regression: `0.25`
- margin-rating learning rate: `0.05`
- margin-rating HFA parameter: `3.0` points
- ridge lambda for the final rating model: `100`

The rating features are inputs to the fitted spread model; they are not manual point additions after the model runs.

### Spread sign convention

- `canonical_home_margin > 0` means the home team is projected to win by that many points.
- Site-facing home spread = `-canonical_home_margin`.

## Canonical totals architecture

**Canonical total:** `frozen core only`

The totals model is a separate ridge regression with core inputs including:
- blended offensive EPA sum,
- blended defensive EPA-allowed sum,
- blended offensive success-rate sum,
- blended defensive success-rate-allowed sum,
- last-3 offensive EPA sum,
- last-3 defensive EPA-allowed sum,
- passing matchup strength sum,
- rushing matchup strength sum,
- explosive-pass context sum,
- explosive-rush context sum,
- sack context sum,
- neutral early-down pass-rate sum,
- rest sum,
- absolute rest difference,
- neutral-site indicator.

Drive/pace, red-zone, weather, turnover, special-teams and other candidate additions have not earned inclusion in the canonical total.

## Projected scores

Projected scores are presentation derivatives rather than separately fitted score models:

- projected home points = `(model_total + canonical_home_margin) / 2`
- projected away points = `(model_total - canonical_home_margin) / 2`

## Early-season regression and priors

Core team metrics use current-season information blended with prior-season information through a pseudo-game shrinkage parameter `k` selected using training data only:

`blended_metric = (games_before * current_metric + k * prior_metric) / (games_before + k)`

Recursive ratings also regress between seasons; the final architecture uses offseason regression `0.25`.

## Home field / neutral site

Home influence is learned, not manually added after prediction. The core model learns its normal home environment and includes a `neutral_site` feature; recursive ratings use frozen HFA dynamics selected on 2022 only. No discretionary HFA points are layered onto final predictions.

## Missing-data handling

For numeric model features:
- preprocessing is fit on training data only,
- missing values use the training-set median,
- scaling uses training-set mean and standard deviation,
- the frozen preprocessing is applied to unseen rows.

Missing current personnel/weather information is a reliability/release-state issue, not an invented point adjustment.

## Win probability

Win probability is derived from the **canonical home-margin projection**, not sportsbook moneylines.

A two-parameter logistic calibration maps canonical projected home margin to home-win probability. It was walk-forward tested on unseen 2024 and 2025 seasons before becoming display eligible.

Policy:
- research/display probability is allowed,
- moneyline edge, bet recommendation and staking claims are not allowed,
- hard-QB state breaks remain visibly out-of-distribution.

## Market policy

The canonical model is market-independent. Sportsbook prices may be used only as timestamped comparison/calibration benchmarks after the model prediction is generated.

Until Stage 4 is earned, public-facing terminology should use **Model-Market Difference** or **Model-Market Disagreement**, not validated `edge`.

## Feature-state registry

### Promoted in canonical spread
- core efficiency/matchup/rest/neutral architecture
- defensive coverage
- recursive win Elo
- recursive margin rating

### Promoted in canonical total
- frozen core total architecture only

### Validated presentation layer
- canonical-margin win probability calibration

### Shadow challenger
- `FTN50`: 50% canonical spread + 50% FTN QB/process challenger
- historically robust enough for prospective shadow comparison
- not canonical until prospective evidence supports promotion

### Context/release gate only
- confirmed starting QB and late QB changes
- official injuries/inactives
- weather/wind and roof state
- travel/time-zone/static venue context
- market freshness/execution status

### Tested but not promoted as incremental production weight
- additive QB value
- historical injury/personnel burden
- NGS tracking families
- trench/OL continuity additions
- drive/pace additions
- red-zone efficiency
- turnover/luck additions after promoted stack
- special teams/kicking
- penalties
- coaching/process candidates
- personnel/formation candidates
- standalone travel/time-zone/roof/surface coefficients
- direct market blend

## Primary source contract

| Layer | Primary source | Role |
|---|---|---|
| Teams / IDs | nflverse teams/players | Canonical identifiers |
| Schedule / results | nflverse schedules | Game IDs, dates, venues, rest, realized results |
| Play-by-play | nflverse PBP | EPA, success, passing/rushing, matchup features |
| Team efficiency | derived from nflverse PBP/team stats | Core model |
| Defensive coverage / advanced player | timestamp-safe nflverse/PFR/FTN-derived research pipelines | Promoted coverage or shadow research depending on family |
| Depth charts / rosters | nflverse + official team depth charts | Current context |
| Injuries / inactives | official NFL/team reports | Hard context/release gate |
| Weather | NWS hourly forecast + venue/roof metadata | Prospective context/release gate |
| Market | direct public sportsbook captures; Covers/Action for QA | Benchmark only |
| External models | nfelo / transparent public models where available | Benchmark/shadow only |

## Canonical output contract

Prediction outputs include league, season/week/game ID, teams, kickoff/date, canonical home margin, model home spread, model total, projected scores and win probabilities.

Model metadata include model version, snapshot ID/timestamp, architecture, spread/total reliability, empirical intervals, hard-QB flag, personnel state and weather/roof state.

Market comparison includes source/book, observed timestamp, market spread/total, model-market differences and execution verification.

Release metadata include release state, blockers, recommendation state and website publication state.

## Freeze/versioning rules

- A prospective prediction snapshot is immutable once frozen.
- New injury/weather/market information may update contextual release fields without rewriting the frozen numeric prediction.
- Architecture changes require a new version and separate validation.
- Canonical and challenger models must be graded on identical games/timestamps.

## Stage 1 limitations carried forward

1. The independent model is not proven superior to the market.
2. Canonical total retains negative historical bias; tested sequential correction did not earn robust promotion.
3. Current QB/injury/weather context has no validated additive point coefficients.
4. Betting confidence, moneyline edge, alternative-line logic and recommendation thresholds remain locked pending prospective evidence.

## Stage 1 handoff

> Stage 1 is locked. Canonical NFL spread = frozen core efficiency/matchup architecture + validated defensive coverage + market-independent recursive win Elo + margin rating. Canonical total = frozen core only. Win probability is separately validated for display/research only. Market lines never enter canonical fitting. QB/injuries/weather are contextual gates with zero arbitrary point adjustment. FTN50 remains a shadow challenger. Predictions are immutable after freeze.

---

# Stage 2 — Historical + walk-forward validation

**Stage status:** `COMPLETE / HISTORICAL RESEARCH VALIDATED`  
**Audit verdict:** `PASS_HISTORICAL_RESEARCH_VALIDATION__PROSPECTIVE_RELEASE_STILL_REQUIRED`  
**Recommendation/betting-signal release:** HOLD

## Validation design

The final canonical architecture has **816 outer out-of-sample regular-season games** across 2023-2025:
- 2023: 272 unseen games,
- 2024: 272 unseen games,
- 2025: 272 unseen games.

Core training/tuning uses only prior-era information. Promoted rating dynamics were selected using 2022 only and frozen for the 2023-2025 outer tests.

Historical feature rows use prior completed games only. Current-game outcomes do not enter their own inputs. Median imputation and standardization are fitted on training rows only.

Sportsbook references are not canonical model features or tuning targets.

## Aggregate prediction error

| Metric | Spread / home margin | Total |
|---|---:|---:|
| Games | 816 | 816 |
| MAE | 10.2564 | 10.5001 |
| RMSE | 13.2903 | 13.4958 |
| Bias (prediction - actual) | -0.0126 | -1.2723 |

Market-reference comparison:
- spread-reference MAE: **9.7445**,
- total-reference MAE: **10.1207**.

The market reference is more accurate on aggregate raw MAE; therefore Stage 2 does **not** support claiming that the independent model is generally more accurate than the market.

## Season-by-season prediction error

| Season | N | Spread MAE | Spread RMSE | Total MAE | Total RMSE |
|---|---:|---:|---:|---:|---:|
| 2023 | 272 | 10.5036 | 13.7234 | 10.5069 | 13.6117 |
| 2024 | 272 | 10.0135 | 13.1850 | 10.0708 | 13.1663 |
| 2025 | 272 | 10.2521 | 12.9507 | 10.9227 | 13.7034 |

## Final-score display error

Projected team scores are derived from canonical total + margin and are not independently fitted.

Across **1,632 team-score observations**:
- combined team-score MAE: **7.5138**,
- combined team-score RMSE: **9.4706**,
- combined bias: **-0.6361** points,
- home-score MAE/RMSE: **7.5684 / 9.5828**,
- away-score MAE/RMSE: **7.4593 / 9.3571**.

## Straight-up accuracy

Canonical winner direction:
- **515 wins / 300 losses** on decided games,
- accuracy **63.19%**,
- 95% Wilson interval **[59.82%, 66.43%]**.

Actual ties and exact model pick'ems are excluded from decided accuracy.

## Historical market-benchmark directional grading

These are **not released-bet records**. They only grade which side/total direction the model preferred relative to the historical market-reference line.

| Minimum model-market difference | ATS W-L-P | ATS win rate | Total W-L-P | Total win rate |
|---|---:|---:|---:|---:|
| >0 points | 418-379-19 | 52.45% | 409-402-5 | 50.43% |
| >=1 point | 306-286-14 | 51.69% | 298-312-4 | 48.85% |
| >=2 points | 221-220-12 | 50.11% | 206-233-3 | 46.92% |
| >=3 points | 143-147-7 | 49.31% | 148-161-3 | 47.90% |
| >=4 points | 95-104-2 | 47.74% | 95-100-2 | 48.72% |
| >=5 points | 61-65-0 | 48.41% | 59-56-2 | 51.30% |

Larger historical disagreement did not produce monotonically better results. Therefore a simple “bigger difference = stronger edge” rule is rejected at Stage 2 and must be rebuilt prospectively in Stage 4.

## Win-probability calibration

Canonical-margin win probability is separately walk-forward validated for research/display:

- 2024 test: Brier **0.215097**, log loss **0.620264**, directional accuracy **67.65%**, ECE **0.08955**.
- 2025 test: Brier **0.225016**, log loss **0.639583**, directional accuracy **61.99%**, ECE **0.044824**.

Both folds passed the predeclared display gates. Moneyline-edge release remains **false**.

## CLV policy

**Historical verified CLV is NOT CLAIMED.**

A genuine CLV measurement requires:
1. a timestamped executable price at the model decision time, and
2. a consistently defined closing price from a comparable market.

Historical schedule-line fields are useful for MAE comparison, market-direction grading and calibration research, but they do not prove an executable entry price. They cannot support ROI, verified CLV or a claim of betting edge.

Prospective timestamped market captures will support future CLV-style evaluation only when timing/execution is verifiable.

## Leakage controls

- Outer walk-forward is time ordered.
- Hyperparameters are selected only from training-era data.
- Pregame features use prior completed games only.
- Imputation/scaling are fit on training data only.
- Market references are post-prediction benchmarks only.
- Win probability uses canonical OOS model margins and no sportsbook moneyline in fitting.

## Sample-size / overfitting warnings

- 816 unseen games is meaningful for error estimation but still limited for many threshold/feature slices.
- Historical threshold tables involve multiple comparisons.
- An attractive historical bucket cannot automatically become a release rule.
- Backtests cannot replace prospective frozen-week evidence.
- The market benchmark's lower aggregate MAE is a strong warning against overclaiming.
- The total's negative bias remains a known limitation.
- Display win probability is not moneyline-edge validation.

## Stage 2 deliverables

- `scripts/audit_nfl_stage2_validation.py`
- `.github/workflows/nfl-stage2-validation-audit.yml`
- `nfl_data/validation/stage2_validation_audit.json`
- `nfl_data/validation/STAGE2_VALIDATION_AUDIT.md`
- `scripts/audit_nfl_stage2_score_metrics.py`
- `nfl_data/validation/stage2_final_score_metrics.json`

The CI audit additionally verifies that production CFB `data/` files remain unchanged.

## Stage 2 handoff

> Stage 2 is complete as historical research validation, not proof of betting edge. The canonical architecture has 816 outer-OOS games from 2023-2025, with spread/total MAE and RMSE, derived final-score error, 63.19% SU accuracy on decided games, historical market-benchmark ATS/total directional grading, and separately walk-forward-validated display win probability. Larger historical model-market differences did not monotonically improve ATS/total results. Genuine historical CLV/ROI is not claimed because executable decision-time prices are not verified. Proceed to Stage 3 using timestamped QB/personnel, weather/roof, rest/travel and market snapshots as context/execution gates without retroactively changing the frozen Week 6 prediction.

---

# Running stage status

| Stage | Status | Release meaning |
|---|---|---|
| 1. Core architecture | **COMPLETE / LOCKED** | Canonical research architecture frozen |
| 2. Historical + walk-forward validation | **COMPLETE / HISTORICAL RESEARCH VALIDATED** | Historical projection validation passes; no betting-edge release |
| 3. Context + market execution | **NEXT / INFRASTRUCTURE BUILT / FINAL GATES ACTIVE** | Audit timestamped context and execution rules next |
| 4. Confidence / edge / release | **LOCKED / PROSPECTIVE EVIDENCE REQUIRED** | No validated betting threshold |
| 5. Weekly production / audit | **INFRASTRUCTURE BUILT** | Week 6 is first immutable prospective sample |
| 6. Website / operating interface | **TECHNICAL PREVIEW BUILT / PRODUCTION HOLD** | Shared CFB/NFL interface exists on NFL branch; production CFB site unchanged |
