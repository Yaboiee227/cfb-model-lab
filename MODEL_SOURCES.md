# CB Model Projections — Vetted Source & Resource Registry

Last consolidated: 2026-10-20

This file is the source-of-truth registry for external data, information, benchmark, market, and research resources vetted for the CB Model Projections CFB and NFL systems.

## Governing rules

1. A source being listed here does **not** mean every field or metric from that source is a canonical model feature.
2. Canonical, challenger, benchmark, contextual, market, and discovery layers must remain separate.
3. No new feature may affect a canonical projection without leakage-safe historical testing, walk-forward/out-of-sample validation, prospective frozen-week evidence, and explicit promotion.
4. Preserve observation timestamps, source URLs/provenance, model versions, frozen projections, publication-time market numbers, and honest postgame grades.
5. Never reconstruct pregame information after results are known.
6. Market prices and external models are comparison/benchmark information unless a separately validated feature is explicitly promoted. Direct market blending is not approved.
7. Missing, late, stale, or unavailable data stays missing/stale. Do not infer or backfill it after kickoff.

### Status vocabulary

- **APPROVED PRIMARY FACTUAL** — trusted factual/structured source eligible for production ingestion where coverage and timestamps are adequate.
- **APPROVED MARKET REFERENCE** — approved source for observed market prices or movement; not a canonical predictive input by default.
- **APPROVED EXTERNAL BENCHMARK** — independent model/rating used for comparison and challenger research; no canonical influence.
- **APPROVED CHALLENGER / CONTEXT** — may be captured and tested prospectively, but cannot alter canonical output until promoted.
- **APPROVED CROSS-CHECK / QA** — corroboration or quality-control source; not preferred over a stronger primary source when one exists.
- **FALLBACK / OPTIONAL** — usable when a preferred source is unavailable, with provenance and limitations recorded.
- **DISCOVERY ONLY** — useful for finding potential data/resources; never feed directly into production without separate vetting.
- **SOURCE APPROVED, FEATURE NOT PROMOTED** — the source is useful, but specific candidate features have failed or not yet passed promotion requirements.

---

# CFB — primary factual and structured data

## CollegeFootballData (CFBD)
- Official site/API: https://collegefootballdata.com/ and https://api.collegefootballdata.com/
- Status: **APPROVED PRIMARY FACTUAL / STRUCTURED BACKBONE**
- Uses: schedules, games, teams, conferences, play-by-play where covered, drives, team/player statistics, recruiting/talent information, historical lines where available, and other structured CFB facts.
- Important: external rating fields exposed through CFBD (for example SP+, FPI, or other rating systems) retain their own benchmark status; their presence in CFBD does not make them canonical CB features.
- Preserve season/week coverage notes and timestamps. API keys must remain server-side or in GitHub Actions secrets.

## cfbfastR
- Project/ecosystem: cfbfastR / sportsdataverse
- Status: **APPROVED PRIMARY/CROSS-CHECK DATA TOOL**
- Uses: historical/play-by-play research, EPA-style analysis, feature prototyping, and cross-checking structured CFB data.
- Any derived metric must still pass CB leakage-safe validation before promotion.

## ESPN college-football scoreboard and summary endpoints
- Scoreboard: https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard
- Summary: https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=EVENT_ID
- Status: **APPROVED FALLBACK / LIVE-GAME CONTEXT**
- Uses: schedules, scores, game status, broadcasts, possession/situation, box score, player stats, play-by-play, drives, and win-probability fields when available.
- Limitation: unofficial/undocumented endpoints. Use graceful fallback behavior and never treat endpoint availability as guaranteed.

## NCAA, conference, and official team athletic-department sources
- Status: **APPROVED PRIMARY FACTUAL**
- Uses: official schedules, rosters, coaching changes, availability/injury information when officially published, depth/role changes, venue information, suspensions, and announcements.
- Prefer official school/conference availability information over aggregators when timestamps are comparable.

## Sports Reference / College Football at Sports-Reference
- Site: https://www.sports-reference.com/cfb/
- Status: **APPROVED CROSS-CHECK / HISTORICAL RESEARCH**
- Uses: historical schedules/results, team/player/coaching records, era/context checks, and validation research.

## TeamRankings
- Site: https://www.teamrankings.com/college-football/
- Status: **APPROVED CROSS-CHECK / CHALLENGER CONTEXT**
- Uses: team statistical comparisons, situational splits, pace/efficiency cross-checks, and hypothesis generation.
- No raw trend or ranking receives automatic model weight.

## CFBTrack
- Status: **APPROVED CONTEXT / RESEARCH**
- Uses: coaching/program research and historical context where applicable.
- Cross-check material facts with an official source or a second reliable source before production use.

## FootballDB
- Site: https://www.footballdb.com/
- Status: **APPROVED CROSS-CHECK / HISTORICAL RESEARCH**
- Uses: schedules, historical results, standings, coaching/team context, and factual cross-checks.

---

# NFL — primary factual and structured data

## Official NFL / NFL Football Operations / official team sources
- League: https://www.nfl.com/
- Football Operations: https://operations.nfl.com/
- Status: **APPROVED PRIMARY FACTUAL**
- Uses: injury reports, practice status, final inactives, roster/transaction information, schedules, rules, stadium/roof or operational information, and official announcements.
- Final inactives and official injury designations take priority over speculative personnel reporting.

## nflverse / nflfastR data ecosystem
- Documentation/ecosystem: https://nflverse.nflverse.com/
- Status: **APPROVED PRIMARY FACTUAL / STRUCTURED BACKBONE**
- Uses: schedules, historical spread/total lines, play-by-play, EPA/success-rate research, team/player stats, roster/depth-chart data where available, and reproducible historical model inputs.
- Preserve data release/update timing. Derived features must use only records available before the target game.

## NFL Next Gen Stats
- Site: https://nextgenstats.nfl.com/
- Status: **APPROVED OFFICIAL FACTUAL / CHALLENGER DATA**
- Uses: tracking-based player/team context and independent feature research.
- Current model decision: the previously tested additive NGS feature layer is **not promoted** to the canonical NFL model. Continue only as challenger/context unless new leakage-safe evidence supports promotion.

## Pro Football Reference (PFR)
- Site: https://www.pro-football-reference.com/
- Status: **APPROVED CROSS-CHECK / CHALLENGER RESEARCH**
- Uses: historical schedules/results, player/team stats, advanced passing/rushing/receiving/defensive data, coaching/history, and validation cross-checks.
- Note source update timing for weekly advanced fields before using them in pregame research.

## NFL Savant
- Site: https://nflsavant.com/
- Status: **APPROVED CHALLENGER / VALIDATION**
- Uses: independent NFL statistical views, play/player research, tendency checks, and feature validation.

## RBSDM
- Site: https://rbsdm.com/
- Status: **APPROVED CHALLENGER / VALIDATION**
- Uses: EPA/play, success rate, quarterback, play-calling, fourth-down, and related independent efficiency views.
- Useful as an independent check; do not blindly duplicate nflverse-derived information into the model.

## SumerSports
- Site: https://sumersports.com/
- Status: **APPROVED CHALLENGER / CONTEXT**
- Uses: independent football analytics, roster/player/team evaluation, methodology comparison, and feature research.

## nfelo
- Site: https://nfelo.com/
- Status: **APPROVED EXTERNAL BENCHMARK / CHALLENGER**
- Canonical influence: **NO**
- Uses: Elo/power-rating comparison, weekly matchup comparison, model disagreement analysis, and methodology research.

## FTN / DVOA and related FTN metrics
- Site: https://ftnfantasy.com/
- Status: **APPROVED CHALLENGER / BENCHMARK**
- Uses: DVOA-style independent efficiency comparison and candidate feature research.
- Current model decision: **FTN50 remains shadow/prospective only**. Previously tested red-zone and turnover additions were **not promoted**.

---

# Personnel, injuries, depth and trench context

## Official NFL injury reports and final inactives
- Status: **APPROVED PRIMARY FACTUAL**
- Uses: current player availability, practice participation, game status, and final release gates.

## SICScore
- Site: https://sicscore.com/
- Status: **APPROVED CHALLENGER / PERSONNEL CONTEXT**
- Uses: injury-impact research and independent severity/context assessment.
- Do not convert proprietary injury scores directly into model points without testing. Authentication-gated observations must preserve timestamp/provenance.

## ProFootballDoc
- Status: **APPROVED CHALLENGER / PERSONNEL CONTEXT**
- Uses: independent injury analysis and return-to-play context.
- Official injury/inactive information remains primary for factual availability state.

## PFF
- Site: https://www.pff.com/
- Status: **APPROVED CHALLENGER / PLAYER & TRENCH CONTEXT**
- Uses: player grades, line/coverage/player evaluation, depth changes, and hypothesis generation for both NFL and CFB.
- Paid/proprietary grades are not canonical by default. Tested trench/additive layers have not been promoted unless separately documented.

## Sports Info Solutions (SIS)
- Site: https://www.sportsinfosolutions.com/
- Status: **APPROVED CHALLENGER / PLAYER CONTEXT**
- Uses: charting/player/depth evaluation and feature research where licensed/accessed.
- No automatic canonical influence.

## Pro Football Network (PFN) Impact / offensive-line rankings
- Site: https://www.profootballnetwork.com/nfl-hq/rankings/offensive-line
- Status: **APPROVED QA / BENCHMARK**
- Uses: offensive-line context, lineup-change QA, and comparison against CB trench assumptions.
- No automatic model weight.

## Action Network quarterback rankings / personnel research
- Site: https://www.actionnetwork.com/
- Status: **APPROVED QA / CONTEXT**
- Uses: quarterback/personnel comparison and research cross-checking.
- No arbitrary QB point adjustments are approved.

---

# Weather, venue, roof, rest and travel context

## National Weather Service / weather.gov
- API/docs: https://www.weather.gov/documentation/services-web-api
- API base: https://api.weather.gov/
- Status: **APPROVED PRIMARY FACTUAL**
- Uses: pregame forecast, wind, precipitation, temperature, alerts, and weather uncertainty.
- Record forecast issue/observation time. Never substitute postgame observed weather for the pregame forecast used by the model.

## RotoWire NFL Weather
- Site: https://www.rotowire.com/football/weather.php
- Status: **APPROVED CROSS-CHECK / CONTEXT**
- Uses: game-level weather and dome-status cross-checks.
- NWS/official venue information remains preferred when conflicts exist.

## Action Network and Covers weather views
- Status: **APPROVED CROSS-CHECK / CONTEXT**
- Uses: secondary weather checks and market-facing context.

## Official venue/team/league roof-status pages
- Status: **APPROVED PRIMARY FACTUAL / RELEASE-GATE CONTEXT**
- Uses: dome/retractable-roof status and venue operational information when published.
- Example previously used: official Colts/venue roof information. Prefer the relevant team/stadium/league source for each game.

## Rest, bye, short-week, travel and timezone information
- Status: **APPROVED DERIVED CONTEXT**
- Primary factual inputs should come from vetted schedules/venues (CFBD, nflverse, official league/team schedules).
- Current model decision: standalone travel/timezone coefficients are **not promoted**. Rest/travel can remain contextual or be retested as challengers.

---

# Sportsbook and odds sources

## FanDuel
- Site: https://sportsbook.fanduel.com/
- Status: **APPROVED MARKET REFERENCE**
- Uses: publication-time spread, total, moneyline, price/juice, and movement snapshots.
- Market data never changes an already frozen model projection.

## DraftKings Sportsbook
- Site: https://sportsbook.draftkings.com/
- Status: **APPROVED MARKET REFERENCE**
- Uses: publication-time spread, total, moneyline, price/juice, and movement snapshots.

## The Odds API
- Site: https://the-odds-api.com/
- Status: **APPROVED LICENSED MARKET-DATA TRANSPORT / FEED**
- Uses: server-side/GitHub-Actions collection of sportsbook quotes, including FanDuel and DraftKings, timestamps, movement, and historical odds when the plan supports it.
- API keys must never be exposed in the static frontend.

## BetMGM
- Site: https://sports.betmgm.com/
- Status: **APPROVED CROSS-MARKET QA / FROZEN BENCHMARK**
- Uses: independent line check and frozen market comparison.

## Pinnacle
- Site: https://www.pinnacle.com/
- Status: **APPROVED MARKET BENCHMARK / CONTEXT**
- Uses: market-efficiency comparison and hypothesis/validation research when an observable compliant data source is available.
- Not a canonical model input.

## ESPN sportsbook/odds lines
- Status: **FALLBACK / OPTIONAL MARKET CROSS-CHECK**
- Uses: secondary quote check when a preferred licensed/current quote is unavailable.
- Must be timestamped and labeled by source/book where possible.

---

# Betting-market research, trends and line context

## Action Network
- Site: https://www.actionnetwork.com/
- Status: **APPROVED CONTEXT / MARKET & INJURY RESEARCH**
- Uses: injury research, market context, line movement, public information, quarterback/position research, and situational hypothesis generation.
- Trends do not directly alter canonical projections without testing.

## Covers
- Site: https://www.covers.com/
- Status: **APPROVED CONTEXT / CROSS-MARKET QA**
- Uses: standings, records, ATS records, weekly betting trends, odds/market cross-checks, injury/weather context, and historical research.
- ATS/trend tables are research context only unless a feature is separately validated and promoted.

## Bet Labs
- Status: **APPROVED HYPOTHESIS-GENERATION / CONTEXT ONLY**
- Uses: situational trend discovery and research questions.
- No trend-mining rule may enter the canonical model without leakage-safe testing and multiple-testing discipline.

## Killer Sports
- Status: **APPROVED HYPOTHESIS-GENERATION / CONTEXT ONLY**
- Uses: historical/situational query research.
- Same restrictions as Bet Labs: no direct trend weighting.

---

# Prediction markets

## Kalshi
- Site/API: https://kalshi.com/ and https://docs.kalshi.com/
- Status: **APPROVED PREDICTION-MARKET BENCHMARK / CONTEXT**
- Uses: pregame contract price/probability, liquidity/volume where available, and disagreement analysis.
- Canonical influence: **NO** unless a future challenger is validated and explicitly promoted.

## Polymarket
- Site/docs: https://polymarket.com/ and https://docs.polymarket.com/
- Status: **APPROVED PREDICTION-MARKET BENCHMARK / CONTEXT**
- Uses: pregame market probabilities/prices, volume/liquidity where available, and comparison with CB win probability.
- Use scheduled snapshots rather than relying on unsupported browser calls. Preserve event matching and timestamps.

---

# Official external model benchmarks

## ESPN / Bill Connelly SP+
- Official 2026 publication: https://www.espn.com/college-football/story/_/id/49868647/2026-college-football-sp+-rankings-all-138-fbs-teams
- Sport: CFB
- Status: **APPROVED EXTERNAL BENCHMARK**
- Canonical influence: **NO**
- Uses: weekly snapshot, model-vs-SP+ comparison, MAE/error comparison, agreement/disagreement analysis, challenger research.
- Only official ESPN/Bill Connelly SP+ publications should be authoritative for the CB benchmark. Mirrors are not authoritative.

## Jeff Sagarin College Football Ratings
- Official source: https://sagarin.com/sports/cfsend.htm
- Status: **APPROVED EXTERNAL BENCHMARK**
- Canonical influence: **NO**
- Uses: Predictor/implied-margin comparison, schedule-strength comparison, MAE/error comparison, and challenger research.
- Use only values actually available before kickoff and preserve the observation timestamp and published home-field value.

## Jeff Sagarin NFL Ratings
- Official source: https://sagarin.com/sports/nflsend.htm
- Status: **APPROVED EXTERNAL BENCHMARK**
- Canonical influence: **NO**
- Uses: Predictor/implied-margin comparison, schedule-strength context, and weekly disagreement research.

## ESPN FPI
- Publisher: ESPN
- Status: **APPROVED EXTERNAL BENCHMARK / CHALLENGER**
- Canonical influence: **NO**
- Uses: independent CFB rating/probability comparison and disagreement analysis.
- Capture the value actually published before kickoff; do not reconstruct historical pregame FPI from a postgame page.

## FEI
- Status: **APPROVED EXTERNAL BENCHMARK / CHALLENGER**
- Canonical influence: **NO**
- Uses: independent CFB efficiency/rating comparison and feature research.

## Massey Ratings
- Site: https://masseyratings.com/
- Status: **APPROVED EXTERNAL BENCHMARK / CHALLENGER**
- Canonical influence: **NO**
- Uses: independent CFB rating, schedule-strength, and consensus comparison.

## Market-implied ratings
- Source: publication-time sportsbook prices from approved market sources.
- Status: **APPROVED BENCHMARK ONLY**
- Uses: compare model estimates to market consensus, quantify disagreement, closing-line research, and calibration/decision analysis.
- Direct market blending into the canonical model is **not approved**.

---

# Officiating

## RefMetrics
- NCAA football: https://www.refmetrics.com/ncaa-football/
- NFL: https://www.refmetrics.com/nfl/
- Status: **APPROVED CONTEXT / CHALLENGER SOURCE**
- Canonical influence: **NO until validated**
- Uses: referee/crew assignment capture, penalties, penalty yards/types, home/away splits, crew histories, sample-size-aware challenger research, and uncertainty research.
- Capture assignments prospectively when available. Missing/late assignments remain missing. Never reconstruct a pregame assignment after the game.
- Raw ATS/Over trends are context only. Small samples should be shrunk toward league/conference averages before challenger testing.

---

# News and reporting cross-checks

## NFL official news / team news
- Status: **APPROVED PRIMARY/CROSS-CHECK FACTUAL**
- Uses: official transactions, injuries, roster/coaching updates, game operations, and announcements.

## NCAA / conference / team official news
- Status: **APPROVED PRIMARY/CROSS-CHECK FACTUAL**
- Uses: availability, roster, coaching, disciplinary, schedule, and venue updates.

## CBS Sports NFL / College Football
- Site: https://www.cbssports.com/
- Status: **APPROVED CONTEXT / NEWS CROSS-CHECK**
- Uses: injury/news/recap context and research triage. Verify model-critical facts with primary sources when possible.

## Yahoo Sports
- Site: https://sports.yahoo.com/
- Status: **APPROVED CONTEXT / NEWS CROSS-CHECK**
- Uses: breaking-news/injury/context cross-checking. Verify model-critical facts with primary sources when possible.

---

# Discovery and infrastructure resources

## Public API catalogs / general API directories
- Status: **DISCOVERY ONLY**
- Uses: finding potential new feeds or APIs.
- A discovered API cannot feed production until its provenance, legality/terms, coverage, timing, reliability, schema, and leakage risks are separately vetted.

## GitHub / GitHub Actions / GitHub Pages
- Status: **APPROVED PROJECT INFRASTRUCTURE — NOT A MODEL DATA SOURCE**
- Uses: repository/version control, scheduled ingestion/snapshots, frozen artifacts, static-site hosting, automated grading, and source/model provenance.
- Secrets must stay in GitHub Actions/secure server-side configuration and must never be committed or exposed in GitHub Pages frontend code.

## Google Sheets
- Status: **APPROVED WORKSPACE / QA TOOL — NOT A MODEL DATA SOURCE**
- Uses: human-readable review, source/timestamp logging, weekly slate QA, injury/weather tracking, and results review.

## Python, CSV and JSON artifacts
- Status: **APPROVED MODEL/PIPELINE INFRASTRUCTURE — NOT EXTERNAL SOURCES**
- Uses: reproducible ingestion, feature engineering, validation, frozen-week snapshots, grading, and website delivery.

---

# Source-specific promotion decisions already made

The following decisions must remain explicit so source availability is not confused with feature approval:

- **Promoted/retained canonical NFL architecture:** core efficiency, defensive coverage, win Elo, margin rating, validated totals architecture, and calibrated display win probability as documented in model/version files.
- **Shadow only:** FTN50/process signal.
- **Not promoted/rejected in prior NFL source/feature audits:** FTN red-zone and turnover additions; additive Next Gen Stats layer; standalone trench coefficients; additional drive/pace layers; special-teams and kicking coefficients; penalty coefficients; standalone travel/timezone coefficients; historical injury-burden coefficients; arbitrary QB point adjustments; and direct market blending.
- Injuries/QB state, weather, roof, market freshness, and final inactives remain important **context/release gates** even when they are not direct canonical point coefficients.
- RefMetrics/officiating remains challenger/context with zero canonical influence until validated.

---

# Benchmark and challenger evaluation plan

For each weekly frozen projection, preserve the external values actually available at observation time where practical:

- CB projected margin/spread
- CB projected total
- CB projected winner and win probability
- official SP+ value/implied margin where available (CFB)
- official Sagarin Predictor/implied margin where available
- FPI/FEI/Massey/nfelo or other approved benchmark snapshots when used
- RefMetrics assignment/context when available before kickoff
- personnel/injury context and source state
- pregame weather/roof state and forecast timestamp
- publication-time spread/total/moneyline and price/juice
- prediction-market probability/price and liquidity fields when captured
- all source URLs and observation timestamps
- model version and frozen projection version
- final score only after the game

Evaluate benchmarks and challengers on the same frozen game set and timing rules as the canonical model, including:

- margin MAE / RMSE
- total MAE / RMSE where applicable
- straight-up accuracy
- ATS directional performance against the locked publication-time market number
- calibration/Brier/log loss where a defensible probability exists
- performance by conference/division, favorite/underdog, home/away, market-disagreement bucket, and relevant uncertainty buckets
- incremental value over the existing canonical model, not just standalone correlation
- prospective stability across multiple frozen weeks

No external source, benchmark, context item, or late-arriving data can change an already frozen projection or its official grade.

## Existing machine-readable benchmark registry

`data/approved-external-benchmarks.json` contains the currently approved external benchmark subset and allowed/prohibited uses. This Markdown file is the broader source-of-truth registry for all vetted source layers until a complete machine-readable source registry is added.
