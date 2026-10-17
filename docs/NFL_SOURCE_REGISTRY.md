# NFL Source Registry and Validation Policy

Status: DEVELOPMENT ONLY / HOLD
Branch: `nfl-model-development`

This registry defines how external NFL information may enter the model. A source being useful does **not** automatically give its variables predictive weight. Every derived feature must remain timestamp-safe, reproducible where practical, and pass historical or prospective validation before promotion.

## Source tiers

### Tier 1 — canonical / official inputs

These sources establish facts and are preferred when available.

- **nflverse / nflfastR** — schedules, play-by-play, weekly/team/player data, rosters, depth-chart related datasets, Next Gen mirrors where available.
- **NFL.com official injury reports** — practice participation, game designation, body part and official status.
- **NFL official inactives / transactions / team announcements** — game-day starter and availability overrides.
- **NFL Next Gen Stats** — official tracking-derived QB, rushing and receiving metrics.
- **National Weather Service / api.weather.gov** — official hourly stadium-location forecasts for outdoor/open-roof games.
- **NFL Football Operations / official stadium or team communication** — retractable roof status and venue operating rules when available.

Policy: Tier 1 facts can be used directly after timestamp and identity validation. Future information is never allowed into historical pregame snapshots.

## Tier 2 — independent football analytics / cross-checks

- **NFL Savant** — open play-by-play based advanced metrics and downloadable historical play-by-play. Use for independent QA and feature research.
- **RBSDM** — EPA/play, success rate, QB, neutral pass frequency, pass over expected, fourth-down, luck and series-success views. Use as independent cross-check and candidate-feature research.
- **SumerSports** — offensive/defensive EPA, success, personnel and formation tendencies. Use for scheme/personnel matchup research and independent QA.
- **Pro Football Reference advanced stats** — pressure, blitz, hurry, knockdown, bad throw, on-target, air yards, YAC and other advanced player/team context.
- **nfelo** — open-source team/QB predictive framework, QB Elo, EPA/CPOE/QBR aggregation and QB value research. Use as a benchmark and candidate QB/replacement-value source, not as a hidden blend into the core projection.
- **ESPN QBR** — secondary QB quality signal when timestamp-safe.
- **Pro Football Network OL Impact** — current pass-block/run-block context and offensive-line QA. Treat as a research/context layer until historical coverage and predictive stability are established.

Policy: Tier 2 metrics must be compared against the canonical layer. They may become model features only after leakage-safe walk-forward validation. External model predictions are benchmarks, not automatic ensemble components.

## Tier 3 — injury intelligence

- **SICScore / Sports Injury Central** — player SIC scores, team/position health scores, injury cluster analysis, medical return/performance context.
- **Official NFL injury reports** remain the factual status authority.

Planned derived features:
- player health score
- team offense/defense health differential
- position-group health differential
- starter absence / limitation probability
- injury-cluster score (OL, secondary, pass rush, receiver room)
- expected replacement quality

Policy:
- SICScore is an impact/medical intelligence layer, not the official availability authority.
- Authenticated SIC data must be timestamped when captured.
- Do not store usernames, passwords, session cookies or tokens in GitHub, Google Sheets, logs or generated CSVs.
- Historical predictive use requires archived pregame SIC values or a reproducible proxy; otherwise use it prospectively and validate forward.

## Tier 4 — market / betting context

- **Direct sportsbook quotes** — preferred executable price source at decision time.
- **Covers** — opening/current odds, line movement, matchup pages, consensus/public information, injury/weather QA and historical odds where available.
- **Action Network Betting Primer** — live lines, starting QBs, systems, public splits, key numbers, weather, team records and weekly contextual research.
- **Action Network QB value / power rankings** — independent point-spread value benchmark for starter/backup QB changes.

Policy:
- Opening/current/closing lines are stored separately with timestamps.
- Closing lines are never available to a historical pregame feature row unless the snapshot time is actually at close.
- Public betting %, handle %, historical systems and editorial picks are **research/context variables only** until independently backtested.
- The core football projection remains market-independent. Market information may be used for comparison, residual research, CLV and executable-edge gating only after validation.
- Direct book quote beats aggregator quote for release/execution decisions.

## Tier 5 — weather / environment

Primary:
- NWS hourly forecast at stadium coordinates
- venue roof/surface metadata
- official roof decision when available

Secondary / QA:
- RotoWire NFL Weather
- Action Network weather / Chaos context
- Covers weather pages

Candidate features:
- sustained wind
- gust speed
- precipitation probability/intensity
- temperature
- humidity where reliable
- crosswind/headwind orientation when stadium orientation is available
- roof/open-air state
- surface

Policy: forecasts must be timestamped. Current forecasts cannot be backfilled into historical games. Weather coefficients remain zero until historical/prospective tests show incremental value.

## Current-week source hierarchy

1. Schedule/game identity: nflverse + NFL official QA
2. Team/play efficiency: nflverse PBP; RBSDM/NFL Savant/SumerSports QA
3. QB: nflverse PBP/player stats + NGS/PFR; nfelo and Action QB value as benchmarks
4. Injuries: NFL official status + depth/snaps; SICScore impact layer
5. OL/trenches: PBP/PFR + injury/depth continuity; PFN/SumerSports secondary context
6. Skill-position personnel: usage/snaps/targets + injuries; SumerSports personnel tendencies
7. Weather: NWS + roof status; RotoWire/Action/Covers QA
8. Market: direct sportsbook quotes; Covers/Action secondary aggregation and movement context
9. Release: model projection first, then market comparison, executable quote verification and confidence/release gates

## High-risk feature classes

The following must never be promoted from a single correlation or a compelling narrative:

- historical betting systems / trends
- public betting percentages
- short-window ATS/OU records
- turnover margin
- red-zone conversion in small samples
- one-week injury narratives
- subjective power rankings
- weather thresholds chosen after seeing results
- external model projections blended without an untouched validation sample

Use multiple-testing controls, minimum sample sizes, blocked/walk-forward validation and prospective logging.

## Additional accuracy resources to maintain

- nflverse / nflfastR
- NFL official injury/inactive/transaction feeds
- NFL Next Gen Stats
- National Weather Service
- NFL Savant
- RBSDM
- SumerSports
- Pro Football Reference advanced stats
- nfelo / nfelo QB model
- ESPN QBR
- Pro Football Network OL Impact
- Covers
- Action Network
- SICScore
- RotoWire weather

## Release rule

No source, including a paid/proprietary one, bypasses the model's validation framework. NFL remains `HOLD` until the full pipeline, QA, walk-forward tests, prospective validation and executable-market checks are complete. No website publication is permitted before that process is completed and explicitly reviewed.
