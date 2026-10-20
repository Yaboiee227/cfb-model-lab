# CB Model Projections — Approved Model & Benchmark Sources

This file is the source-of-truth registry for external model/benchmark resources approved for use with the CFB and NFL systems.

## Governing rule

External ratings may be saved and compared with CB Model Projections, but they do **not** become canonical model inputs automatically. Promotion requires leakage-safe historical testing, out-of-sample evidence, prospective frozen-week evidence, and an explicit review.

The canonical model remains independent of the market and of external rating systems unless a tested challenger is explicitly promoted.

## Official CFB benchmark sources

### SP+
- Publisher: ESPN / Bill Connelly
- Official 2026 source: https://www.espn.com/college-football/story/_/id/49868647/2026-college-football-sp+-rankings-all-138-fbs-teams
- Status: APPROVED EXTERNAL BENCHMARK
- Canonical influence: NO
- Uses: weekly snapshot, model-vs-SP+ comparison, MAE/error comparison, agreement/disagreement analysis, challenger research.

Only ESPN/Bill Connelly's official SP+ publication should be treated as the approved SP+ source. Mirrors or republished copies are not authoritative for the CB system.

### Jeff Sagarin College Football Ratings
- Publisher: Jeff Sagarin
- Official source: https://sagarin.com/sports/cfsend.htm
- Status: APPROVED EXTERNAL BENCHMARK
- Canonical influence: NO
- Uses: Predictor comparison, schedule-strength comparison, model-vs-Sagarin comparison, MAE/error comparison, challenger research.

Use the current official Sagarin output and its published home-field value when constructing a Sagarin implied margin. Preserve the observation timestamp and never reconstruct a pregame rating after results are known.

## Official NFL benchmark source

### Jeff Sagarin NFL Ratings
- Publisher: Jeff Sagarin
- Official source: https://sagarin.com/sports/nflsend.htm
- Status: APPROVED EXTERNAL BENCHMARK
- Canonical influence: NO
- Uses: Predictor comparison, schedule-strength comparison, model-vs-Sagarin comparison, MAE/error comparison, challenger research.

Use only values actually available before kickoff for prospective comparisons. A stale Sagarin update may be retained as a timestamped benchmark but must not be presented as current.

## Benchmark evaluation plan

For each weekly frozen projection, preserve the external benchmark values available at observation time where practical:

- CB projected margin / spread
- CB projected total
- CB projected winner / win probability
- official SP+ value or implied margin where available (CFB)
- official Sagarin Predictor/implied margin where available
- Sagarin schedule-strength context where useful
- saved publication-time market spread / total / moneyline
- observation timestamps and source URLs
- final score after the game

Evaluate external benchmarks prospectively using the same games and timing rules as the canonical model, including:

- margin MAE / RMSE
- straight-up accuracy
- ATS directional performance against the locked publication-time market number
- calibration where a probability is available and defensible
- performance by conference/division, favorite/underdog, home/away, and disagreement bucket
- whether agreement/disagreement with CB has incremental predictive value

No external benchmark can change an already frozen projection or its official grade.

## Machine-readable registry

See `data/approved-external-benchmarks.json` for the approved source URLs and allowed/prohibited uses used by future automation.
