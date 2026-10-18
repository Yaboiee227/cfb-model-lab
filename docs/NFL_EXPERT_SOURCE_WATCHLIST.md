# NFL Expert Source Watchlist

Status: ACTIVE RESEARCH / VALIDATION REQUIRED
Last reviewed: 2026-10-18

This watchlist formalizes expert/proprietary NFL sources that can improve the weekly research and game-day context pipeline. Inclusion here does **not** grant automatic predictive weight. Each signal must remain timestamped, source-labeled, separable from the canonical model, and prospectively graded before promotion.

## 1. Evan Abrams / Action Network

Primary resources:
- Weekly NFL Betting Primer: https://www.actionnetwork.com/nfl/nfl-betting-primer-trends-stats-systems-for-every-game
- Action author page: https://www.actionnetwork.com/article/author/evan-abrams/
- X: https://x.com/evanhabrams

Role in pipeline:
- betting systems/trends research
- key-number and historical score context
- public-betting context, preserving Action's own definitions
- listed starting-QB cross-check
- current market/line movement cross-check
- weather/Chaos context
- backup-QB historical research
- Action/Sean Koerner live QB point-spread-value benchmark

Current 2026 Primer structure includes Matchups, Systems, Public, Key #'s, Weather, Records and Teams. These families must be ingested separately rather than collapsed into one signal.

Policy:
- editorial systems, trends and public percentages remain context-only until independently backtested
- listed starting QBs are provisional; official NFL/team game-day confirmation overrides
- Action market values are secondary to executable direct-book quotes
- QB point values are external benchmarks until our own prospective validation supports a replacement-QB adjustment
- preserve article/post timestamp and exact source URL for every captured item

## 2. Dr. David Chao / Pro Football Doc / Sports Injury Central (SIC)

Primary resources:
- SIC dashboard: https://sicscore.com/dashboard
- SIC home/methodology: https://sicscore.com/
- SIC Score methodology: https://sicscore.com/features/sic-score
- X: https://x.com/profootballdoc

Role in pipeline:
- medical/injury effectiveness analysis
- player health score
- team health score
- position-group injury clusters
- expected limitation/performance-risk context
- potential market-lag injury mismatches

SIC explicitly describes its score as a proprietary health rating for players, position groups and teams, and states that the team score intentionally does not account for coaching, scheme or matchup. That makes it useful as a relatively clean injury/health layer.

Policy:
- NFL official injury report, transactions and inactive lists remain the factual playing-status authority
- SIC may refine expected effectiveness but never override official active/inactive facts
- capture SIC values with timestamp because the proprietary score can change as medical information changes
- do not store credentials, cookies, tokens or paid-session data in the repository
- self-reported historical betting performance is not model-validation evidence unless independently reproduced
- validate SIC differentials prospectively before assigning numeric points to spreads/totals

## 3. Dr. Nick Giffen / Action Network Luck Rankings

Primary resources:
- Author page: https://www.actionnetwork.com/article/author/nick-giffen
- 2026 Luck Rankings primer/methodology: https://www.actionnetwork.com/nfl/nfl-luck-rankings-2026-primer-updates-and-how-to-use-action-networks-predictive-model/
- X: https://x.com/rotodoc

Role in pipeline:
- expected-score benchmark
- luck/regression signal
- side and total challenger signal
- identification of teams whose actual results may overstate/understate underlying performance

2026 methodology notes:
- Luck Rankings are Version 3.1
- Expected Score is built from play-by-play/game situations and adjusts for offensive/defensive strength and injuries
- Luck Score >= 1.9 is treated by Action as an official luck-based side threshold
- Luck Score 1.5-1.9 is a lean
- Luck Total > +1.5 or < -1.5 is the official total threshold, with official totals beginning Week 3

Policy:
- Luck Rankings are an external predictive model/challenger, not a direct canonical-model input
- log weekly side/total signals, thresholds, source timestamp and closing result
- compare against canonical, shadow, market and actual outcomes prospectively
- test incremental value after controlling for market spread/total before any promotion
- do not use current-week or future Luck Rankings to rewrite frozen historical/prospective snapshots

## Priority use order

For game-day decisions/research:
1. NFL official status/inactives/transactions
2. Direct sportsbook market quotes
3. Dr. Chao/SIC medical effectiveness and health differential
4. Evan Abrams/Action Primer and live QB-value research
5. Nick Giffen Luck Rankings as a separate expected-score/regression challenger
6. Other editorial trends/picks as context only

## Promotion criteria

No expert signal receives model weight merely because the source is respected. Promotion requires:
- timestamp-safe observations
- enough historical or prospective samples
- walk-forward/prospective performance versus existing baselines
- incremental value after market and canonical-model controls
- stability across weeks/seasons
- no leakage from closing information into earlier prediction timestamps

Until those tests are passed, these sources improve context, QA, reliability and challenger research while the canonical NFL projection remains unchanged.