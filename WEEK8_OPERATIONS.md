# Week 8 CFB Production Runbook — October 20–22, 2026

## Objective

Operate Week 8 as a rolling, pregame-only production cycle. Maximize legitimate information capture without contaminating the canonical CB projection with hindsight or unvalidated external signals.

## Core rule

Collect broadly. Promote narrowly. Freeze independently.

The canonical CB projection must be generated from a reproducible, authorized established model. Week 8 currently has no such production projection and remains HOLD; see `cfb/projections/week-08-status.json`. SP+, Sagarin, RefMetrics, market data and other external/context sources are preserved for comparison, audit and challenger research unless a feature has already earned canonical status through leakage-safe validation.

## Active integration boundary — October 20, 2026

The current production pass is intentionally limited to the seven FBS games played Tuesday, Wednesday and Thursday, October 20–22.

Machine-readable scope:
- `cfb/pregame/week-08-active-through-thursday.json`
- active schedule slice: `cfb/pregame/week-08-schedule-through-thursday.json`
- active audit output: `cfb/pregame/week-08-research-coverage-through-thursday.json`

Friday, October 23 and Saturday, October 24 are **PAUSED** for this pass. Do not ingest new Friday/Saturday pregame context, create publication locks, generate recommendations, or grade those games until explicit resumption. The full Week 8 schedule and immutable research foundation remain preserved so work can resume without reconstruction.

This pause does not authorize changing any frozen projection. It only changes the active operational queue.

## Current architecture integration

Week 8 now follows the project-wide separation rules:

- **Canonical layer:** only previously validated and explicitly promoted CFB features may influence the production model.
- **Frozen research foundation:** `cfb/research-locks/week-08-foundation-full.json` is immutable, market-independent, prospective and research-only. It cannot be silently relabeled as canonical.
- **Challenger/shadow layer:** new feature families, richer models, agent-assisted research and experimental infrastructure may generate evidence but cannot promote themselves.
- **Benchmark layer:** official SP+, official Sagarin, RefMetrics, sportsbooks and prediction markets remain comparison inputs unless separately validated and promoted.
- **Context layer:** injuries, QB availability, weather, travel/rest, coaching/news and trends are timestamped with source provenance. Unknown stays unknown and no unvalidated manual point adjustment is invented.
- **Source registry:** `MODEL_SOURCES.md` governs source roles and provenance expectations. Infrastructure such as routing/agent tooling may accelerate collection and validation, but never becomes a source of canonical football truth by itself.

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

### Friday, October 23 — PAUSED
- UMass at UConn — 7:00 PM ET
- Duke at Virginia — 7:00 PM ET
- Army at Tulsa — 8:30 PM ET
- Air Force at Wyoming — 9:00 PM ET
- NC State at Stanford — 10:30 PM ET

No Friday processing is authorized in the current pass.

### Saturday, October 24 — PAUSED
Use the authoritative FBS schedule feed as the slate source when this phase is resumed. Saturday games span noon ET through late night; each game remains independently refreshable until its own freeze cutoff.

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

For Week 8 research comparisons, preserve the already-frozen market-independent foundation and its projection digest. Do not regenerate it after kickoff or from later information.

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
- game is inside the active operational scope
- canonical inputs are pre-kickoff
- no post-result leakage
- team aliases/source IDs match
- frozen foundation digest matches its prospective lock where used for research comparison
- QB/personnel state is current enough
- material weather is current enough
- market benchmark exists or is explicitly missing
- external benchmark freshness is labeled
- RefMetrics assignment is AVAILABLE / NOT YET POSTED / PARTIAL / STALE as appropriate
- unresolved material issues are visible

### 5. ONE-HOUR REFRESH
The recurring Pregame Model Refresh process checks active NFL and FBS games roughly one hour before kickoff for late-breaking referee, personnel, QB, weather, market and benchmark/context information.

A late update can affect the still-open canonical game state only when the underlying feature is already authorized by the established model framework. New/unvalidated information is recorded as context/challenger evidence and cannot silently change the CB projection.

For this Week 8 pass, the CFB queue ends after the Thursday games. Friday/Saturday are not eligible for this refresh until the active scope is explicitly extended.

### 6. PER-GAME FREEZE
Freeze each active game independently before kickoff using the v2 lock mechanism.

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

All comparisons must preserve model version, projection digest, observation timestamp and source provenance.

## Promotion discipline

Nothing new becomes canonical because it sounds useful, comes from an external model, or agrees with one result.

Required path:
1. collect prospectively
2. verify source/timing integrity
3. build a challenger
4. leakage-safe historical/walk-forward test
5. out-of-sample comparison
6. prospective frozen-week evidence
7. explicit promotion decision

Agent/LLM tooling may assist steps 1–6 but cannot execute step 7 on its own.

## Week 8 immediate priority

1. Complete Tuesday's final pregame refreshes, publication-time market locks and freeze/audit requirements without reconstructing anything after kickoff.
2. Keep Wednesday's New Mexico State–Sam Houston state current through its own final window.
3. Keep Thursday's Liberty–Kennesaw State, James Madison–App State and East Carolina–Memphis states current through their independent final windows.
4. After the Thursday slate is frozen/processed, **STOP**. Do not begin Friday ingestion until explicit resumption.

The goal is not maximum feature count in the final equation. The goal is maximum defensible information capture plus the most accurate validated canonical prediction possible.


## Tuesday–Wednesday afternoon handoff — October 20, 4:18 PM ET

The four-game priority source pass is captured; final-hour checks and publication locks are not yet complete. No game has been graded in this pass. No frozen foundation, timestamp, coefficient or validation decision was changed.

| Game | Latest useful evidence | Remaining material work | T−30 window opens (ET) |
| --- | --- | --- | --- |
| MTSU at FIU | Official recent QB baselines; both teams last played Oct. 13; current NWS hourly API | Final availability/depth; FIU third-party player-name mismatch; final wind/gust check | Tue 6:30 PM |
| Missouri State at Delaware | Direct team previews; latest NWS hourly API | Both Tuesday starters unresolved; reconcile conflicting Missouri QB summaries | Tue 6:30 PM |
| South Alabama at Marshall | Official Sun Belt game-day report; Marshall recent three-QB rotation; NWS hourly API | Marshall starter/rotation; South Alabama's three game-time decisions; final refresh | Tue 7:00 PM |
| NM State at Sam Houston | Oct. 20 Sam Houston preview; recent QB and freshman OL context; NWS hourly API | Wednesday final personnel/roles, weather and fresh market checks | Wed 7:30 PM |

- Source captures: `cfb/pregame-refresh/week-08-sunbelt-tuesday-availability-2026-10-20.json` and `week-08-nws-tuesday-wednesday-2026-10-20.json`. Preserve report issue time separately from actual retrieval time.
- The NWS capture covers kickoff through +4h. Nearby forecast grids are not on-field measurements; API gusts are unavailable, not zero. It supersedes older cached table summaries without deleting those snapshots.
- FIU officially advertises 7:02 PM ET. Preserve the frozen 7:00 PM kickoff identity and conservative lock cutoff.
- Official SP+ remains blocked by source verification; RefMetrics retrieval is stale Week 7. These are explicit benchmark gaps, not inferred values.
- `scripts/build_week8_pregame.py` rebuilds Tuesday effective state, unified active state and both Tuesday/Wednesday readiness audits. Source overlays and immutable locks are inputs, never generated replacements.
- Public status: `week-8.html`; it reads saved game states and lock files on load. Research Hub now distinguishes current Week 8 preparation from historical Week 7 grades.
- Existing scheduled CFB refresh prompts now carry the Tuesday–Thursday boundary; NFL instructions are unchanged. Hourly polling is best effort and cannot guarantee an exact minute. The existing GitHub market-lock workflow remains responsible for configured T−30 captures; inspect actual lock records rather than assuming a scheduled run succeeded.
- Canonical HOLD remains the overriding release gate. Research locks may be captured and graded independently without promoting their projections.
