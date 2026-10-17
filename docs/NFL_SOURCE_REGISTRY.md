# NFL Source Registry and Validation Policy

Status: DEVELOPMENT ONLY / HOLD
Branch: `nfl-model-development`
Last audited: 2026-10-17

This registry defines how external NFL information may enter the model. A source being useful does **not** automatically give its variables predictive weight. Every derived feature must remain timestamp-safe, reproducible where practical, and pass historical or prospective validation before promotion.

## Verification standard

Every source is evaluated on five separate questions before data can affect a projection:

1. **Authority** — Is the source official/canonical, a derivative of another feed, a proprietary model, or editorial research?
2. **Definition** — Is the metric definition clear enough to reproduce or at least interpret consistently?
3. **Timestamp safety** — Can we prove the observation existed before the game being predicted?
4. **Historical coverage** — Can the same definition be reconstructed for walk-forward backtests, or is it current/prospective only?
5. **Independent value** — Does the feature improve unseen-game prediction after controlling for information already in the model?

A source may pass factual verification while still receiving zero predictive weight.

## Source tiers

### Tier 1 — canonical / official inputs

These sources establish facts and are preferred when available.

- **nflverse / nflfastR** — schedules, play-by-play, weekly/team/player data, rosters, depth-chart related datasets, Next Gen mirrors where available. Treat nflverse as a high-quality structured distribution/research layer, not the NFL's official status authority.
- **NFL.com official injury reports** — practice participation, injury designation/body part and official game status.
- **NFL official inactives / transactions / team announcements** — game-day availability and starter/roster overrides.
- **NFL Next Gen Stats** — official tracking-derived QB, rushing, receiving and selected team/player metrics.
- **National Weather Service / api.weather.gov** — official U.S. hourly stadium-location forecast feed for outdoor/open-roof games.
- **NFL Football Operations / official stadium or team communication** — retractable roof status and venue operating rules when available.

Policy: Tier 1 facts can be used directly after timestamp and identity validation. Future information is never allowed into historical pregame snapshots.

### Tier 2 — independent football analytics / cross-checks

- **NFL Savant** — open advanced presentation layer and downloadable play-by-play. Audit note: NFL Savant states its PBP is sourced from `nflreadpy / nflfastR`; therefore it is **not an independent confirmation** of nflverse PBP values. Use it for convenience, calculations/definition QA and presentation checks, not as a second independent raw-data vote.
- **RBSDM** — EPA/play, success rate, QB, neutral pass frequency, pass-over-expected, fourth-down, luck and series-success views. Use as independent calculation/feature research only after metric-definition checks.
- **SumerSports** — offensive/defensive EPA, success, personnel and formation tendencies. Current pages expose timestamped personnel/formation usage and EPA splits. Use for scheme/personnel matchup research; historical comparability must be verified before backtest promotion.
- **Pro Football Reference advanced stats** — pressure, blitz, hurry, knockdown, bad throw, on-target, air yards, YAC, RPO/play-action and related advanced player/team context. Audit note: 2026 advanced passing page states updates occur Wednesday after the week's games, so ingestion must honor that publication lag.
- **nfelo** — open team/QB predictive framework, QB Elo and EPA/CPOE/QBR aggregation. Use as an **external predictive benchmark** and candidate QB/replacement-value comparison, not as hidden core-model truth.
- **ESPN QBR** — proprietary QB efficiency signal incorporating passing, rushing, sacks, fumbles/penalties and game context. Use as secondary QB-quality evidence only when timestamp-safe; do not attempt to treat it as a fully reproducible raw feature.
- **Pro Football Network Impact / OL Impact** — pass-protection/run-block and line grades. Audit note: PFN says grades can change after games and methodology can evolve; cite/store the week/version timestamp. Current OL methodology is opponent-adjusted and OL history is available from 2019 on.

Policy: Tier 2 metrics must be compared against the canonical layer. They may become model features only after leakage-safe walk-forward validation. External model predictions are benchmarks, not automatic ensemble components.

## Tier 3 — injury intelligence

- **SICScore / Sports Injury Central** — player SIC scores, team/position health scores, injury cluster analysis, medical return/performance context.
- **Official NFL injury reports** remain the factual status authority.

Audited interpretation of SICScore:
- SIC describes its score as a proprietary algorithmic health rating for players, position groups and teams.
- Individual scores are health/performance-expectation grades, not official playing-status probabilities.
- SIC explicitly says its team score intentionally does not account for coaching, scheme or matchup.
- SIC's betting-performance claims are self-reported marketing claims; they are **not** accepted as model-validation evidence unless independently reproduced.
- The proprietary formula is not sufficiently transparent to reconstruct historical values from public inputs. Historical predictive use therefore requires archived timestamped SIC observations; otherwise validate prospectively.

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
- NFL official status and inactive lists always override a conflicting SIC expectation on whether a player is active.

## Tier 4 — market / betting context

- **Direct sportsbook quotes** — preferred executable price source at decision time.
- **Covers** — opening/current odds, line movement and community consensus/context.
- **Action Network Betting Primer** — live lines, listed starting QBs, Bet Labs systems, public context, key-number history, weather and team records.
- **Action Network QB value / power rankings** — independent point-spread-value benchmark for starter/backup changes.

Audited interpretation:
- Covers states that its displayed odds are supplied by sportsbooks but are subject to a **small delay**. Therefore Covers can validate market direction and history but cannot certify the executable release price.
- Covers states that its displayed consensus is powered by **Covers Contests/community picks**. It must not be mislabeled as verified sportsbook ticket percentage or handle percentage.
- Action's weekly Primer explicitly includes live lines, listed starting QBs, Bet Labs systems, public context, key numbers, weather and records. These are heterogeneous data families and must remain separated in ingestion.
- Starting-QB fields from Action, schedule feeds or other media sources are provisional. Official injury/game status and game-day inactive/team confirmation override them.
- Historical betting systems/trends from Action/Covers are hypotheses, not priors; multiple-testing and selection bias are major risks.

Policy:
- Opening/current/closing lines are stored separately with source and capture timestamp.
- Closing lines are never available to a historical pregame feature row unless the simulated prediction time is actually at close.
- Public betting %, handle %, historical systems and editorial picks are **research/context variables only** until independently backtested.
- The core football projection remains market-independent. Market information may be used for comparison, residual research, CLV and executable-edge gating only after validation.
- Direct book quote beats aggregator quote for release/execution decisions.

## Tier 5 — weather / environment

Primary:
- **NWS hourly forecast at stadium coordinates** for U.S. venues. NWS documents point-to-grid hourly forecast endpoints and provides forecast data at roughly 2.5 km grid resolution.
- venue roof/surface metadata
- official roof decision when available

Secondary / QA:
- **RotoWire NFL Weather**
- Action Network weather / Chaos context
- Covers weather pages

Audited RotoWire interpretation:
- RotoWire displays game-specific temperature, precipitation, wind/direction and dome context.
- Its page references Forecast.io and Weather.com hourly forecasts plus editorial interpretation.
- It is useful as a human-readable cross-check, but NWS remains primary for U.S. outdoor forecasts because NWS is official and machine-readable.
- RotoWire's qualitative claims such as weather being a "minimal" or "significant" factor are not model coefficients.

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

## Next Gen Stats audit

NFL Next Gen Stats is authoritative for the tracking-derived metrics it publishes, but availability varies by season and player qualification threshold.

Verified public families include:
- Passing: time to throw, completed/intended air yards, air-yards differential, aggressiveness, longest completed air distance, air yards to sticks, attempts/yards/TD/INT, passer rating, completion %, expected completion % and completion % above expectation.
- Rushing: expected rushing yards, RYOE, RYOE/attempt, rush percentage over expected and related tracking metrics.
- Receiving/tracking: separation/cushion and expected-YAC family where published.
- NFL tracking infrastructure also supports location, speed, acceleration, formations, coverage/route classifications and predictive models such as completion probability, expected rushing yards and win probability.

Important restrictions:
- A metric appearing in an NFL article/model does **not** mean a stable historical bulk feed exists for it.
- Public leaderboard qualification thresholds create missing-not-at-random player samples; missing NGS rows are never zeros.
- Definitions/models can evolve. Store season/source version and test cross-season stability before pooling.
- Our canonical nflverse NGS ingestion has already verified leakage-safe historical/current coverage for the fields actually present in that feed; unsupported fields remain unavailable rather than imputed.

## Current-week source hierarchy

1. Schedule/game identity: nflverse + NFL official QA
2. Team/play efficiency: nflverse PBP; external analytics for calculation QA
3. QB performance: nflverse PBP/player stats + official NGS/PFR; nfelo/QBR/Action QB value as benchmarks
4. QB availability: NFL official injury status, team communication and game-day inactive list; depth chart as supporting evidence
5. Injuries: NFL official status + depth/snaps; SICScore as medical-impact layer
6. OL/trenches: PBP/PFR + injury/depth continuity; PFN/SumerSports secondary context
7. Skill-position personnel: usage/snaps/targets + injuries; NGS/SumerSports context
8. Weather: NWS + official roof status; RotoWire/Action/Covers QA
9. Market: direct sportsbook quotes; Covers/Action secondary aggregation and movement context
10. Release: model projection first, then market comparison, executable quote verification and confidence/release gates

## Cross-source disagreement rules

When sources conflict, do not average blindly.

- **Player active/inactive:** NFL official inactive/status/team announcement wins.
- **Practice status:** NFL official injury report wins.
- **Medical effectiveness expectation:** SIC may supplement but never overwrite official active/inactive facts.
- **Starting QB:** official team/game-day confirmation wins; injury report + latest depth chart next; schedule/media listed QB is only provisional.
- **Play-by-play statistic:** canonical nflverse calculation is primary; derivative sites using nflfastR do not count as independent confirmations.
- **NGS metric:** official NFL NGS definition/feed is primary.
- **Weather:** official roof decision first; NWS forecast primary for U.S. outdoor conditions; secondary sites are QA.
- **Betting price:** executable direct-book quote wins; aggregators are secondary.
- **Consensus/public:** preserve provider definition; never translate community picks into sportsbook money/handle without direct evidence.

Every disagreement that could move a projection materially should create a QA flag rather than silently picking a number.

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
- referee trends without stable crew assignment and enough samples
- rivalry/revenge/look-ahead narratives
- external model projections blended without an untouched validation sample

Use multiple-testing controls, minimum sample sizes, blocked/walk-forward validation and prospective logging.

## Additional accuracy resources to maintain

- nflverse / nflfastR
- NFL official injury/inactive/transaction feeds
- NFL Next Gen Stats
- National Weather Service
- NFL Savant (derivative QA, not independent raw-data confirmation)
- RBSDM
- SumerSports
- Pro Football Reference advanced stats
- nfelo / nfelo QB model
- ESPN QBR
- Pro Football Network Impact / OL Impact
- Covers
- Action Network
- SICScore
- RotoWire weather

## Release rule

No source, including a paid/proprietary one, bypasses the model's validation framework. NFL remains `HOLD` until the full pipeline, QA, walk-forward tests, prospective validation and executable-market checks are complete. No website publication is permitted before that process is completed and explicitly reviewed.
