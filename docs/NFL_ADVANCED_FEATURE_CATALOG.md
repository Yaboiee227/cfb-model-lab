# NFL Advanced Feature Catalog

Status: DEVELOPMENT ONLY / HOLD  
Branch: `nfl-model-development`

This catalog translates the advanced-stat inventory into an NFL modeling plan. Inclusion here does **not** imply predictive weight. Every feature must be timestamp-safe, available at the historical cutoff, and prove incremental value in blocked/walk-forward validation before promotion. The public website remains out of scope until the complete NFL process is reviewed.

## Feature-state vocabulary

- **BUILD NOW** — reproducible historical/current data are available and the feature is worth immediate leakage-safe testing.
- **VALIDATE** — available or derivable, but usefulness is uncertain; coefficient starts at zero.
- **QA / BENCHMARK** — useful for cross-checking or context, but not a core model input yet.
- **PROSPECTIVE** — current-week data are useful but historical timestamp-safe coverage is insufficient; log forward before weighting.
- **HOLD / NARRATIVE** — football context may matter, but the variable is too subjective/noisy to receive weight without unusually strong evidence.

## Priority A — build and walk-forward test now

| Group | Candidate features | Primary source / derivation | Initial role |
| --- | --- | --- | --- |
| Core efficiency | EPA/play, pass EPA, rush EPA, early-down EPA, success rate, explosive rate | nflverse PBP | BUILD NOW |
| Opponent adjustment | ridge/iterative offense-defense adjustment, recency weighting, uncertainty | historical PBP | VALIDATE; raw baseline must remain comparison |
| QB production | dropback EPA, CPOE, ANY/A, success, INT/sack rates, scramble EPA | nflverse PBP/player | BUILD NOW |
| QB NGS | time to throw, xCOMP%, CPOE, intended/completed air yards, AYTS, aggressiveness | nflverse NGS / NFL NGS; history 2016+ | BUILD NOW; weighted rolling pregame |
| QB replacement | starter value, backup value, starter-to-backup delta, uncertainty/shrinkage | QB rolling metrics + depth/injury status | BUILD NOW; largest individual personnel candidate |
| Passing pressure | pressure %, hurry/hit/blitz context, pocket time, bad throw %, on-target %, throwaway rate | PFR advanced + PBP | BUILD NOW / VALIDATE |
| Rushing NGS | RYOE, RYOE/attempt, expected rush yards, efficiency, 8+ box %, TLOS | nflverse NGS / NFL NGS; history 2016+ | BUILD NOW |
| Receiving NGS | separation, cushion, YAC, expected YAC, YACOE, air-yards share, catch % | nflverse NGS / NFL NGS; history 2016+ | BUILD NOW as usage-weighted team/room features |
| Drive efficiency | points/drive, EPA/drive, yards/drive, plays/drive, three-and-out, scoring-drive rate | PBP fixed-drive derivation | VALIDATE; prior drive/pace v1 did not earn totals promotion |
| Finishing drives | red-zone TD, goal-to-go, points per scoring opportunity | PBP | VALIDATE with strong shrinkage |
| Pace / script | neutral seconds/play, expected possessions, no-huddle proxy, neutral pass rate/PROE proxy | PBP | VALIDATE; totals coefficient currently zero after prior test |
| Game-state splits | leading/tied/trailing, early/late down, late-and-close | PBP | VALIDATE; minimum-play/sample gates |
| Special teams | kicking/punting/return EPA, FG distance efficiency, hidden field position | PBP + kicker stats | VALIDATE |
| Turnover regression | fumble recovery, INT rate vs expectation proxies, pressure-driven turnover risk | PBP/PFR | VALIDATE; regress heavily |
| Fourth downs | go rate vs model, conversion efficiency, decision quality | nfl4th / PBP | VALIDATE |
| Penalties | penalty EPA/yards/rate by type, offensive/defensive pre-snap penalties | PBP | VALIDATE |
| Personnel usage | 11/12/13/21 groupings, defenders in box, pass rushers, personnel EPA | PBP personnel fields where populated | BUILD/VALIDATE |
| OL continuity | starter snaps, starts together, LT/C availability, replacement quality | rosters/depth/injuries/snap counts | BUILD NOW |
| Defensive disruption | sack/pressure rate, blitz context, TFL, explosive allowed, success allowed | PBP/PFR | BUILD NOW |
| Situation | HFA, rest, short week, bye, travel, timezone, altitude | schedule + venue geography | VALIDATE; coefficients start at zero |
| Weather | wind/gust, precip, temperature, roof/open-air state | timestamped NWS + venue/roof data | VALIDATE; totals first |

## Priority B — useful but source/history constrained

| Group | Candidate features | Source | Initial role |
| --- | --- | --- | --- |
| OL / pass rush win rates | PBWR, RBWR, PRWR, run-stop win rate | ESPN Analytics / NGS tracking | QA / BENCHMARK until reliable historical capture is established |
| Coverage tracking | separation allowed, coverage distance, CPOE allowed, closing speed | NFL NGS / tracking presentations | QA / PROSPECTIVE unless stable historical feed is available |
| Route-level efficiency | YPRR, TPRR, route type/depth/direction, contested rate | PFF/other tracking sources where licensed | HOLD unless reproducible history is available |
| Turnover-worthy plays | TWP rate | PFF or alternative proxy | QA; use reproducible PBP/PFR proxy first |
| Missed tackles / elusive | MTF, elusive rating, yards after contact | tracking/PFF or other providers | QA / PROSPECTIVE |
| Zone vs gap rushing | scheme rate and EPA | tracking / charting providers | PROSPECTIVE / candidate |
| Coverage shell | single-high/two-high/man/zone EPA | tracking/charting | PROSPECTIVE / candidate |
| Motion/alignment | motion rate, shifts, condensed/split formation, box count | tracking/SumerSports/NGS | PROSPECTIVE unless historical extract is stable |
| Injury health | player/team/position SIC, limitation probability, cluster health | NFL official + SICScore | PROSPECTIVE; historical proxy test separately |
| Referee crew | flags/game, type mix, home differential | officiating logs | VALIDATE only with strict multiple-testing controls |
| Surface/noise | turf/grass, stadium/noise context | venue metadata | VALIDATE / minor |

## Priority C — context or benchmark, not automatic model weight

- DVOA/DYAR, SRS, Elo/QB Elo, FPI, nfelo and other public models: benchmark disagreement and residual diagnostics first; no direct blend unless a frozen ensemble wins out-of-sample.
- Opening/current/closing lines, implied totals, key numbers, line movement, splits and CLV: market benchmark and release layer. The core football projection remains market-independent unless a separate residual model is validated.
- Action/Covers trends and historical systems: research only; large multiple-testing/selection-bias risk.
- One-score record, ATS record, revenge/look-ahead/sandwich/rivalry narratives: HOLD unless translated into an objective pregame variable and validated.
- Crowd size/noise, motivation, tanking: context/HOLD unless objective and timestamp-safe.

## NGS ingestion rules

NFL/nflverse NGS passing, rushing and receiving data are available at player-week level from 2016 onward. NGS applies minimum participation thresholds, so missing rows are **not equivalent to zero performance**. Team-level features must therefore be constructed with usage weights and missingness flags.

### Passing NGS candidates

- time to throw
- xCOMP% and CPOE
- intended/completed air yards and air-yards differential
- air yards to sticks
- aggressiveness / tight-window tendency
- longest completed air distance (diagnostic, likely low weight)

### Rushing NGS candidates

- RYOE and RYOE/attempt
- expected rush yards
- efficiency / path efficiency
- 8+ defenders in box rate
- time to line of scrimmage

### Receiving NGS candidates

- cushion
- separation
- intended air yards / air-yards share
- expected YAC, YAC and YACOE
- catch percentage

Each player feature needs a pregame rolling value, recency/shrinkage, team aggregation, and a replacement/default rule that does not use the target game's performance.

## Validation design for new features

1. **Availability audit** — confirm historical coverage by season/week/team/player and quantify missingness.
2. **Pregame freeze** — every target row must use only information observable before the target kickoff.
3. **Univariate test** — check incremental relationship with margin/total residuals after the existing baseline, not raw outcome correlation alone.
4. **Blocked tuning** — select transforms, shrinkage, windows and thresholds only inside training data.
5. **Outer walk-forward** — compare MAE/RMSE, calibration and ATS/OU behavior on unseen seasons/weeks.
6. **Robustness** — inspect season-by-season sign stability, sample-size sensitivity, outliers and collinearity.
7. **Promotion** — coefficient stays zero unless incremental performance is material and stable.
8. **Prospective validation** — freeze current architecture, log predictions/features before games, then evaluate.

## Anti-overfitting rules

- Do not add two versions of the same football concept merely because both are available (for example EPA/play plus multiple highly correlated efficiency composites) without regularization/selection.
- Prefer stable process metrics over outcome metrics: pressure over sacks, CPOE/xCOMP over raw completion %, RYOE over raw YPC, expected/usage-adjusted receiving over raw yards.
- Shrink red-zone, third-down, turnover, explosive-play and one-score metrics aggressively.
- Personnel changes should alter the **expected future unit**, not retroactively rewrite team performance.
- Proprietary metrics never receive weight merely because they are branded as advanced.

## Immediate build order

1. Historical/current NGS passing ingestion and QB rolling features.
2. QB starter/replacement-value layer with depth/injury timestamp rules.
3. NGS rushing and receiving aggregation.
4. PFR advanced pressure/accuracy/play-type features.
5. OL continuity and snap-weighted personnel losses.
6. Defensive disruption / coverage proxies available in canonical PBP/PFR.
7. Special teams and turnover-regression candidates.
8. Re-test totals after QB/personnel/weather additions; do not revive drive/pace weight without incremental evidence.
9. Add proprietary/prospective layers (SICScore, tracking-only splits) to frozen forward logs.
10. Only after historical + prospective release gates pass should any NFL website publication be considered.

## CFB reuse

The conceptual catalog also applies to the college model, but sources differ: PPA, SP+/FEI, recruiting/talent/returning production, transfer/roster turnover and FCS/conference adjustments are CFB-specific. No NFL coefficient or threshold should be copied into CFB or vice versa without separate validation.
