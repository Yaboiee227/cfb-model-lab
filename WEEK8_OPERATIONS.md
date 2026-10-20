# Week 8 CFB Production Runbook — October 20–24, 2026

## Objective

Operate Week 8 as a rolling, pregame-only production cycle. Maximize legitimate information capture without contaminating the canonical CB projection with hindsight or unvalidated external signals.

## Core rule

Collect broadly. Promote narrowly. Freeze independently.

The canonical CB projection is generated from the established model framework. SP+, Sagarin, RefMetrics, market data and other external/context sources are preserved for comparison, audit and challenger research unless a feature has already earned canonical status through leakage-safe validation.

## Week 8 timing

### Tuesday, October 20
- Middle Tennessee at FIU — 7:00 PM ET
- Missouri State at Delaware — 7:00 PM ET
- South Alabama at Marshall — 7:30 PM ET

### Wednesday, October 21
- New Mexico State at Sam Houston — 8:00 PM ET

### Thursday, October 22
- Liberty at Kennesaw State — 7:00 PM ET
- James Madison at Appalachian State — 7:00 PM ET
- East Carolina at Memphis — 7:30 PM ET

### Friday, October 23
- UMass at UConn — 7:00 PM ET
- Duke at Virginia — 7:00 PM ET
- Army at Tulsa — 8:30 PM ET
- Air Force at Wyoming — 9:00 PM ET
- NC State at Stanford — 10:30 PM ET

### Saturday, October 24
Use the authoritative FBS schedule feed as the slate source. Saturday games span noon ET through late night; each game remains independently refreshable until its own freeze cutoff.

## Per-game production stages

### 1. OPEN
Create/refresh the game state with teams, kickoff, venue, conferences and source IDs.

### 2. BASELINE
Load the freshest leakage-safe canonical inputs available:
- opponent-adjusted efficiency
- EPA/success/explosiveness/havoc where available
- drive/scoring efficiency
- pace/possessions
- strength of schedule
- run/pass matchup indicators
- special teams
- rest/travel/venue context
- canonical personnel inputs already validated for use

Generate the independent CB baseline before consulting external benchmarks for influence.

### 3. CONTEXT REFRESH
Capture but do not automatically blend:
- injuries and availability
- starting QB status
- depth/personnel changes
- weather, wind, precipitation, roof and field conditions
- travel/rest/time-zone factors
- current sportsbook spread/total/moneyline and observation time
- official SP+ snapshot where available
- official Sagarin snapshot where current enough to be useful
- RefMetrics referee/crew assignment and officiating context when available
- other approved factual sources

Every item must carry a source and observation timestamp when practical. Unknown stays unknown.

### 4. PRODUCTION AUDIT
Before freeze, check:
- canonical inputs are pre-kickoff
- no post-result leakage
- team aliases/source IDs match
- QB/personnel state is current enough
- material weather is current enough
- market benchmark exists or is explicitly missing
- external benchmark freshness is labeled
- RefMetrics assignment is AVAILABLE / NOT YET POSTED / PARTIAL / STALE as appropriate
- unresolved material issues are visible

### 5. ONE-HOUR REFRESH
The recurring Pregame Model Refresh automation checks NFL and FBS games roughly one hour before kickoff for late-breaking referee, personnel, QB, weather, market and benchmark/context information.

A late update can affect the still-open canonical game state only when the underlying feature is already authorized by the established model framework. New/unvalidated information is recorded as context/challenger evidence and cannot silently change the CB projection.

### 6. PER-GAME FREEZE
Freeze each game independently before kickoff using the v2 lock mechanism.

The immutable grading identity includes:
- game/team identity
- kickoff
- CB projected spread
- CB projected total
- CB projected winner
- publication-time market spread/total/moneyline
- market source and observation timestamp

External benchmarks/context remain separately timestamped so they cannot delay or mutate the canonical lock.

### 7. POSTGAME GRADING
After FINAL status:
- ATS projection grade
- Total projection grade
- Straight-up grade
- canonical margin error
- canonical total error
- benchmark errors when comparable
- calibration inputs where defensible

No missing pregame market value is reconstructed after the fact.

## Week 8 research comparisons

Track prospectively:
- CB vs official SP+
- CB vs official Sagarin
- CB vs publication-time market
- CB/SP+/Sagarin agreement and disagreement buckets
- RefMetrics officiating context as a shadow/challenger feature family
- performance by conference, home/away, favorite/underdog and data-quality state

## Promotion discipline

Nothing new becomes canonical because it sounds useful or agrees with one result.

Required path:
1. collect prospectively
2. verify source/timing integrity
3. build a challenger
4. leakage-safe historical/walk-forward test
5. out-of-sample comparison
6. prospective frozen-week evidence
7. explicit promotion decision

## Week 8 immediate priority

Tuesday games first. Wednesday, Thursday, Friday and Saturday remain open for fresh legitimate information until their own game-level freeze windows.

The goal is not maximum feature count in the final equation. The goal is maximum defensible information capture plus the most accurate validated canonical prediction possible.
