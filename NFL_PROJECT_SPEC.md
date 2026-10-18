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

**Stage status:** `LOCKED_FOR_WEEK6_RESEARCH`  
**Audit result:** PASS  
**Production/recommendation release:** HOLD

## 1. Modeling philosophy

The canonical NFL model is deliberately compact. Feature families are promoted only when they improve leakage-safe out-of-sample prediction and remain reasonably stable across unseen seasons. More variables are not assumed to be better.

The model must remain interpretable enough to diagnose:
- what information entered the prediction,
- when that information was available,
- how early-season estimates are shrunk,
- how missing values are handled,
- whether sportsbook information entered the model,
- and which research layers were tested but rejected.

No manual narrative point adjustments are allowed. Context such as quarterback changes, injuries, weather, or travel may gate reliability/release without changing the numeric projection unless a coefficient has earned promotion through validation.

## 2. Canonical spread architecture

**Canonical spread:**

`frozen core + defensive coverage + market-independent win Elo + margin rating`

The core spread model is ridge regression trained on pregame-only team/matchup features. Its feature set includes:
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

The promoted defensive coverage layer adds leakage-safe defensive coverage information that survived robustness testing.

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
- Example: home margin `+4.0` becomes model home spread `-4.0`.

## 3. Canonical totals architecture

**Canonical total:**

`frozen core only`

The totals model is a separate ridge regression. It does not automatically inherit every spread feature. Core total inputs include:
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

Drive/pace, red-zone, weather, turnover, special-teams and other candidate additions have not earned inclusion in the canonical total. The total remains intentionally simpler because those expansions failed or lacked timestamp-safe historical evidence.

## 4. Projected scores

Projected scores are presentation derivatives of the canonical margin and total:

- projected home points = `(model_total + canonical_home_margin) / 2`
- projected away points = `(model_total - canonical_home_margin) / 2`

They are not separately fitted score models.

## 5. Early-season regression and priors

Core team metrics use current-season information blended with prior-season information through a pseudo-game shrinkage parameter `k` selected using training data only.

For a team metric with both current and prior values:

`blended_metric = (games_before * current_metric + k * prior_metric) / (games_before + k)`

This prevents one or two early games from overwhelming prior information. As the season progresses, current-season data naturally receives more weight.

The recursive rating systems also regress between seasons. The final win-Elo/margin-rating architecture uses an offseason regression factor of `0.25`.

## 6. Home field and neutral-site handling

Home-field influence is learned rather than manually added after prediction.

- The core spread model is trained directly on home margin, so its intercept/ordered home-away features learn the normal home environment.
- `neutral_site` is an explicit core feature so neutral/international games can differ from standard home games.
- Recursive win Elo and margin ratings use their own frozen HFA dynamics selected on 2022 only and then validated out of sample.

No extra discretionary home-field points may be layered onto the final prediction.

## 7. Missing-data handling

For numeric model features:
- preprocessing is fit on training data only,
- missing values are median-imputed using the training-set median,
- features are standardized using training-set mean and standard deviation,
- the same frozen preprocessing is then applied to the unseen test/current rows.

Missing current personnel/weather information is not silently imputed into a point adjustment. It remains an explicit reliability/release-state issue.

## 8. Win probability

Win probability is derived from the **canonical home-margin projection**, not from sportsbook moneylines.

A two-parameter logistic calibration maps canonical projected home margin to home-win probability. The mapping was walk-forward tested on unseen 2024 and 2025 seasons before becoming display eligible.

Current 2026 presentation mapping is fit on the historical canonical OOS predictions from 2023-2025 after the validation design passed its predeclared display gates.

Policy:
- **Allowed:** research/display win probability and implied moneyline as a mathematical presentation derivative.
- **Not allowed:** calling the probability a validated moneyline edge, bet recommendation, or staking signal.
- hard-QB state breaks remain visibly labeled out-of-distribution even when a probability is displayed.

## 9. Market policy

The canonical model is market-independent.

Sportsbook spreads/totals/moneylines are permitted only as:
- timestamped comparison benchmarks,
- market-disagreement diagnostics,
- historical calibration references,
- prospective tracking fields.

Market lines are **not** model features or tuning targets for the canonical projection. Historical market-blend experiments did not earn promotion.

Until Stage 4 is prospectively earned, public-facing terminology should use **Model-Market Difference** or **Model-Market Disagreement**, not validated `edge`.

## 10. Promoted, shadow, contextual and rejected families

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
- historically robust enough for shadow/prospective comparison
- not canonical until prospective evidence supports promotion

### Context/release gate only
- confirmed starting QB and late QB changes
- official injuries/inactives
- weather and wind
- roof state
- travel/time-zone/static venue context
- current market freshness/execution status

### Tested but not promoted as incremental production weight
- additive QB value
- historical injury/personnel burden
- NGS tracking families
- trench/OL continuity additions
- drive/pace additions
- red-zone efficiency
- turnover/luck regression additions after the promoted stack
- special teams and kicking
- penalties
- coaching/process candidates
- personnel/formation candidates
- standalone travel/time-zone/roof/surface coefficients
- direct market blend

Rejected/no-promotion features remain available for research diagnostics but may not alter the canonical Week 6 projection.

## 11. Primary data/source contract

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

Secondary sources are QA/diagnostic sources and must not silently replace a canonical source without a timestamped change to the project spec.

## 12. Canonical output contract

Every game should export these groups when available.

### Prediction
- league
- season/week/game ID
- away/home teams
- kickoff/date
- canonical home margin
- model home spread
- model total
- projected away points
- projected home points
- home win probability
- away win probability

### Model metadata
- model version
- snapshot ID/timestamp
- architecture label
- spread reliability
- total reliability
- empirical error intervals
- hard-QB state flag
- personnel state
- weather/roof state

### Market comparison
- source/book
- observed timestamp
- market home spread
- market total
- model-market spread difference
- model-market total difference
- execution verified yes/no

### Release metadata
- release state
- release blockers
- recommendation state
- website publication allowed

## 13. Freeze/versioning rules

- A prediction snapshot is immutable once frozen for prospective grading.
- New injury/weather/market information may update the contextual release layer without rewriting the original canonical numeric prediction.
- Architecture changes require a new version and separate validation; historical results may not be used to retroactively edit a frozen forecast.
- Canonical and challenger models must be graded on the same games and timestamps.

## 14. Stage 1 verification result

Stage 1 is considered complete because:
- the spread and total architectures are explicitly defined,
- inputs and sources are documented,
- early-season regression is explicit,
- missing-data behavior is deterministic and training-only,
- home/neutral handling is explicit,
- win probability is a separate validated display calibration,
- market data are excluded from canonical fitting,
- promoted/rejected/shadow/context feature families are separated,
- output and freeze contracts are defined.

### Stage 1 known limitations carried into later stages

1. Historical spread MAE remains materially larger than market-reference MAE; the model is an independent research projection engine, not proven superior to the market.
2. The canonical total has historical negative prediction bias (predicted minus actual about `-1.27` points in 2023-2025 OOS). A sequential correction did not earn robust promotion, so the raw model remains frozen.
3. Current QB/injury/weather context does not have validated additive point coefficients.
4. Betting confidence, moneyline edge, alternative-line logic, and recommendation thresholds remain locked until prospective calibration earns them.

---

# Running stage status

| Stage | Status | Release meaning |
|---|---|---|
| 1. Core architecture | **COMPLETE / LOCKED** | Canonical research architecture frozen |
| 2. Historical + walk-forward validation | **AUDIT NEXT** | Existing validation will be checked against full required metric contract |
| 3. Context + market execution | **INFRASTRUCTURE BUILT / FINAL GATES ACTIVE** | Current-context layer exists; game-day data remain timestamp-sensitive |
| 4. Confidence / edge / release | **LOCKED / PROSPECTIVE EVIDENCE REQUIRED** | No validated betting threshold |
| 5. Weekly production / audit | **INFRASTRUCTURE BUILT** | Week 6 is first immutable prospective sample |
| 6. Website / operating interface | **TECHNICAL PREVIEW BUILT / PRODUCTION HOLD** | Shared CFB/NFL interface exists on NFL branch; production CFB site unchanged |

## Stage 1 handoff

> Stage 1 is locked. Canonical NFL spread = frozen core efficiency/matchup architecture + validated defensive coverage + market-independent recursive win Elo + margin rating. Canonical total = frozen core only. Win probability is a separately validated logistic calibration of canonical home margin and is display/research only. Market lines never enter canonical fitting. QB/injuries/weather are contextual release gates with zero arbitrary point adjustment. FTN50 remains a shadow challenger. Predictions are immutable after freeze. Move next to Stage 2 and audit the existing 2023-2025 walk-forward validation against MAE/RMSE, SU, ATS/totals benchmark grading, win-probability calibration, CLV limitations, sample uncertainty and leakage controls.
