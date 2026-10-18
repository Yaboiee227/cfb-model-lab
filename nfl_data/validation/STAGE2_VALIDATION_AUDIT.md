# NFL Stage 2 Validation Audit

**Verdict:** `PASS_HISTORICAL_RESEARCH_VALIDATION__PROSPECTIVE_RELEASE_STILL_REQUIRED`  
**Canonical unseen games:** 816 (2023-2025)  
**Release implication:** historical research validation passes; recommendation/betting-signal release remains HOLD pending prospective evidence.

## Prediction error

- Spread MAE: **10.2564**; RMSE: **13.2903**; bias: **-0.0126**.
- Total MAE: **10.5001**; RMSE: **13.4958**; bias: **-1.2723**.
- Market-reference spread MAE: **9.7445**.
- Market-reference total MAE: **10.1207**.

| Season | N | Spread MAE | Spread RMSE | Total MAE | Total RMSE |
| --- | --- | --- | --- | --- | --- |
| 2023 | 272 | 10.5036 | 13.7234 | 10.5069 | 13.6117 |
| 2024 | 272 | 10.0135 | 13.185 | 10.0708 | 13.1663 |
| 2025 | 272 | 10.2521 | 12.9507 | 10.9227 | 13.7034 |

## Straight-up accuracy

Canonical winner direction: **515-300** (accuracy **0.6319**, 95% Wilson [0.5982, 0.6643]). Actual ties/model pick'ems are excluded from decided accuracy.

## Historical market-benchmark directional grading

These are not released-bet records. They grade the model's direction versus the historical market reference at different disagreement thresholds.

| Threshold | ATS W-L-P | ATS win% | Total W-L-P | Total win% |
| --- | --- | --- | --- | --- |
| 0.0 | 418-379-19 | 0.5245 | 409-402-5 | 0.5043 |
| 1.0 | 306-286-14 | 0.5169 | 298-312-4 | 0.4885 |
| 2.0 | 221-220-12 | 0.5011 | 206-233-3 | 0.4692 |
| 3.0 | 143-147-7 | 0.4931 | 148-161-3 | 0.479 |
| 4.0 | 95-104-2 | 0.4774 | 95-100-2 | 0.4872 |
| 5.0 | 61-65-0 | 0.4841 | 59-56-2 | 0.513 |

## Win probability

Status: **DISPLAY_VALIDATED_RESEARCH_ONLY**. Moneyline-edge release allowed: **False**.

## CLV policy

**NOT_CLAIMED** — A genuine CLV statistic requires a timestamped executable price at the decision time plus a consistently defined closing price. Historical schedule market references can benchmark prediction accuracy/direction, but they do not prove the price the model could have executed. Prospective timestamped market captures will be used for future CLV-style analysis only when execution/timing is verifiable.

## Leakage controls

- **outer_walk_forward:** 2023 trained on prior seasons; 2024 trained on prior seasons; 2025 trained on prior seasons.
- **hyperparameter_policy:** Core/tuning operations use only training-era data; promoted rating dynamics were selected on 2022 only and frozen for 2023-2025.
- **pregame_features:** Historical feature rows are constructed from prior completed games only. Current-game outcomes never enter their own features.
- **preprocessing:** Median imputation and standardization are fit on training rows only and then applied to unseen rows.
- **market_policy:** Market references are not canonical model features or tuning targets; used only after prediction for benchmark comparison.
- **win_probability:** Probability calibration uses canonical OOS margin predictions; market moneylines are not used in fitting.

## Sample / overfitting warnings

- 816 unseen games is useful for error estimation, but still small for slicing many betting thresholds/features.
- Threshold records are multiple comparisons; an attractive historical bucket is not automatically a release rule.
- The market benchmark is more accurate than the independent model on aggregate MAE, which is a strong warning against claiming market-beating predictive superiority.
- Historical backtests are not a substitute for prospectively frozen weekly predictions.
- The totals model retains measurable negative bias; the tested sequential correction did not earn robust promotion.
- Win probability is validated for research/display, not for moneyline-edge or staking claims.

## Stage 2 handoff

> Historical validation is consolidated and passes as research validation, not as proof of betting edge. The canonical architecture has 816 outer-OOS games across 2023-2025, with market-independent spread/total predictions, season-by-season error metrics, SU grading, historical market-benchmark ATS/total direction records, and separately walk-forward-validated display win probability. Genuine historical CLV/ROI is not claimed because executable decision-time prices are not verified. Proceed to Stage 3 using timestamped personnel, weather/roof, rest/travel and market snapshots as context/execution gates without retroactively changing the frozen canonical Week 6 prediction.
