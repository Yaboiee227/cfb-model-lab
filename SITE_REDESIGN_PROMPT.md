# CB Model Projections — Master Site Redesign Prompt

## Mission
Redesign **CB Model Projections** into a premium, fast, mobile-first football analytics product for **College Football and the NFL**. It should feel credible enough for serious model research while remaining understandable to a first-time visitor.

The product is a **projection and validation interface, not a sportsbook and not a picks page**. It must clearly separate:
- independent model projection,
- market reference or captured book price,
- model/market disagreement,
- projection reliability / uncertainty,
- release-gate status,
- and any future validated recommendation state.

A large model/market disagreement must never be presented as automatically more confident or more actionable. Historical NFL calibration specifically showed that larger raw gaps did not monotonically produce better ATS/OU performance, so the interface must not visually equate gap size with betting confidence.

## Non-negotiable technical constraints
- Keep the site static and deployable on GitHub Pages.
- Use semantic HTML, CSS, and vanilla JavaScript only. No framework or build step.
- Preserve the existing live CFB product until the redesign is explicitly approved for deployment.
- **Do not merge NFL development output to `main` or publish NFL pages/data until the full validation and prospective-readiness process is explicitly approved.**
- Design the data architecture now for both leagues, even if NFL remains hidden/HOLD until approved.
- Keep weekly content data-driven. Extend the current data contract cleanly rather than hard-coding league-specific content into page markup.
- Preserve existing data-loading and grading logic unless a change is explicitly required by the redesign/data-contract migration.
- Preserve dark/light theme, responsive desktop table + mobile cards, search/filter/sort, bookmarks, sharing, CSV export, record tracker, research tabs, methodology, glossary, support, and responsible-gambling disclaimer.
- Never present HOLD projections as released wagers.
- Never label a model/market gap as an “edge” in a way that implies validated profitability unless that league/market has actually earned a release threshold.
- Keep model output, market data, reliability, gate state, and recommendation state visually distinct.
- Do not display account-executable language for a public sportsbook web capture unless the user’s actual account price is verified.

## League architecture
Add a persistent **CFB / NFL league switcher** near the product identity, with league state driven by data rather than duplicate pages.

Each league must carry its own:
- model version,
- current week,
- validation state,
- projection architecture description,
- record/audit history,
- research categories,
- market-capture source state,
- reliability policy,
- and release policy.

The NFL must be able to appear as **Research / HOLD** before it is ever allowed to appear as a released betting product. League switching must never imply both leagues have equal validation maturity.

Recommended top-level data state per league:
- `league`: `CFB` or `NFL`
- `modelVersion`
- `week`
- `updatedAt`
- `projectionState`: `LIVE`, `RESEARCH`, or `HOLD`
- `recommendationState`: `LIVE`, `HOLD`, or `NOT_VALIDATED`
- `prospectiveValidationState`
- `marketExecutionState`
- `websitePublishAllowed`

The UI must honor `websitePublishAllowed=false` as a hard display/publication guard during development exports.

## Brand and visual direction
The product name is **CB Model Projections**.

Visual tone: modern football command center + professional quantitative dashboard. Athletic without looking like a sportsbook clone. Use a deep midnight/navy base, electric lime as the primary model color, cyan/blue for market/reference data, amber for caution/HOLD states, and restrained green/red only for graded outcomes or truly validated release states. Light mode should feel like premium sports analytics, not a generic admin panel.

Design traits:
- Bold condensed-feeling scoreboard typography using system fonts only.
- Strong hierarchy and large numeric readouts.
- Subtle field-grid / yard-line motifs rather than literal football graphics.
- Layered panels, thin borders, controlled glow, crisp spacing, and strong contrast.
- Rounded corners should feel intentional and tighter than generic SaaS cards.
- Motion should be subtle and respect `prefers-reduced-motion`.
- Avoid casino styling, flashing odds, neon overload, fake urgency, or language such as “lock,” “hammer,” “guaranteed,” or “free money.”

## Core status vocabulary
Use a consistent status system across leagues.

### Projection state
- **LIVE** — projection architecture approved for public production use.
- **RESEARCH** — projection is generated and auditable but still under validation.
- **HOLD** — insufficient evidence or unresolved critical state.

### Recommendation state
- **RELEASED** — only when a league/market-specific threshold has earned both retrospective and prospective evidence.
- **HOLD** — projection exists, but recommendation criteria are not satisfied.
- **NOT VALIDATED** — no betting-signal threshold has earned promotion.

### Projection reliability
Reliability is **not betting confidence**. Use the current NFL semantics as the model:
- **A — Final-gate verified**: normal-state projection and all required personnel/environment/price gates verified.
- **B — Standard model, gates pending**: no major state break, but final pregame checks remain.
- **C — Elevated state/environment uncertainty**: returning QB, major non-QB absences, unresolved Monday status, wind/roof/forecast uncertainty, etc.
- **D — Out of distribution**: confirmed expected-starter QB break or another state not represented by validated model behavior.

Never turn A/B/C/D into a betting-star rating. A highly reliable projection can still have no validated betting recommendation.

## Information architecture
Use a sticky navigation with these destinations:
1. Home / Command Center
2. Projections
3. Record
4. Research
5. Methodology
6. Glossary
7. Support
8. About

The league switcher should remain visible in the header on desktop and mobile.

## Home / Command Center
Above the fold, visitors should immediately understand:
- which league they are viewing,
- what the site is,
- when that league was last updated,
- current week and number of games loaded,
- whether projections are LIVE / RESEARCH / HOLD,
- whether recommendations are RELEASED / HOLD / NOT VALIDATED,
- prospective-validation status,
- current model version,
- and that the site is research-first.

Use a two-column hero on desktop and stacked layout on mobile. The left side carries the brand statement and primary actions. The right side is a compact **Model Command Center** with separate cards for:
- Projection readiness
- Recommendation readiness
- Prospective sample status
- Market-price state
- Data/gate completeness

Do not combine these into one vague “confidence” meter.

Under the hero, show slate-summary metrics appropriate to the active league, such as:
- games loaded,
- median projected total,
- largest favorite by model,
- games with final personnel gates verified,
- games with current market capture,
- and count of HOLD / out-of-distribution games.

If a league has no released recommendations, do not show “top picks” or “best bets.”

## Projections
This is the core product area. Make it the visual priority after the hero.

### Controls
- Team search
- Week filter
- Conference filter for CFB / division or conference filter for NFL
- Date filter
- Projection-state filter
- Reliability-tier filter
- Market-capture-state filter
- Sort control
- Reset
- Export filtered CSV

### Desktop table columns
Default columns should prioritize interpretation over density:
- Game / kickoff
- Model score or projected margin
- Model spread
- Market spread
- Model/market disagreement
- Model total
- Market total
- Projection reliability
- Personnel/environment state
- Recommendation state
- Save / share

Optional expanded/detail columns may include:
- Market source
- Market capture time
- Price/odds
- Win probability
- Model-implied moneyline
- Data completeness
- League/model version

### Mobile cards
Each game card should surface with minimal taps:
- matchup + kickoff,
- model projected score/margin,
- model vs market spread,
- model vs market total,
- reliability tier,
- gate status,
- recommendation/HOLD state,
- save/share.

Do not squeeze the desktop table into mobile.

### Visual language
- Model values = lime / primary model color.
- Market/reference values = cyan / blue.
- HOLD / unresolved gates = amber.
- Out-of-distribution state = strong amber/red-accented caution treatment, not a “bad bet” label.
- Green/red is reserved mainly for graded outcomes or an explicitly validated released recommendation state.
- Larger model/market disagreement can be numerically prominent, but **not visually promoted as higher betting confidence**.

### Market-price semantics
Every market display should expose:
- source/book,
- capture timestamp,
- whether it is schedule/reference data, public book-board capture, or account-verified executable price,
- line and price/odds when available.

Suggested badges:
- `REFERENCE ONLY`
- `PUBLIC BOOK CAPTURE`
- `ACCOUNT VERIFIED`

Never call a public web-board capture “executable” without account verification.

## Game detail view
Each game should open into a richer analysis panel/page with five clearly separated blocks:

1. **Projection**
   - projected score/margin,
   - projected spread,
   - projected total,
   - model architecture/version.

2. **Market comparison**
   - market line/total,
   - source and timestamp,
   - disagreement amount,
   - price movement if captured historically.

3. **Reliability / uncertainty**
   - reliability tier and reason,
   - empirical projection-error ranges when available,
   - explicit label: “Projection reliability — not betting confidence.”

4. **Release gates**
   - starter/inactive state,
   - QB-state break,
   - weather/roof,
   - market execution verification,
   - data freshness.

5. **Research context**
   - efficiency,
   - coverage,
   - QB/personnel,
   - trench,
   - pace,
   - turnover/luck,
   - special teams,
   - weather,
   - market observations,
   - and status of each research family where useful.

For NFL, explicitly support “context-only / no promotion” families so rejected model features can still be shown as matchup context without implying they carry learned coefficient weight.

## Alternative-line UI
Design the component now, but keep it disabled behind data state until validated.

When inactive, display:
- `Alternative line logic: HOLD — base recommendation threshold not yet validated.`

When a future league/market earns activation, an alt-line block may show:
- base projected line,
- supported alternative line,
- estimated probability / fair price if validated,
- available book price,
- model-vs-price comparison,
- validation/sample status.

Do not derive or recommend an alt line simply by adding raw model/market gap to the current spread.

## Record Tracker
Make the record section feel like a transparent audit page, not a promotional win-rate graphic.

Separate at minimum:
- projection accuracy,
- market-reference comparison,
- recommendation record if recommendations ever become released,
- prospective validation sample.

Possible metrics:
- spread MAE / RMSE,
- total MAE / RMSE,
- calibration/error-band coverage,
- ATS/OU research grading by historical disagreement bucket,
- prospective weeks/games locked before kickoff,
- graded projection count,
- weekly error trend,
- conference/division breakdown.

Clearly state whether a chart grades **projections**, **historical research rules**, or **released wagers**. Never merge those categories into one win-rate number.

## Research Hub
Research should feel like an evidence center. Keep category tabs generated by data and support:
- availability / personnel,
- weather / roof,
- market,
- efficiency,
- opponent adjustment,
- coverage,
- QB,
- tracking/NGS,
- trench,
- pace / drives,
- turnover/luck,
- special teams,
- penalties,
- schedule / travel,
- situational context,
- validation / calibration.

Each research family can expose a model-use state:
- `PROMOTED CORE`
- `PROMOTED RESEARCH LAYER`
- `CONTEXT ONLY`
- `NO PROMOTION`
- `PROSPECTIVE ONLY`
- `HOLD / UNAVAILABLE`

This is important: the site should demonstrate that the model became more selective as validation got stricter, rather than implying every available statistic is used.

## Methodology
Explain the pipeline in plain English using seven steps:
1. Build leakage-safe team strength
2. Adjust and shrink historical information
3. Validate candidate feature families independently
4. Freeze only features that survive walk-forward robustness
5. Produce independent matchup projections
6. Compare with timestamped market/context data
7. Lock and validate prospectively before any release decision

Add a simple “what is actually in the model?” panel for each league.

For the NFL research architecture, be able to show:
- Spread: core + defensive coverage + market-independent recursive ratings
- Total: core only
- Injuries/weather/other rejected families: current-state context/release gates unless and until validated

Explicitly explain why:
- a stat can matter to football but fail to add incremental predictive value,
- a large model/market gap is not automatically a wager,
- market can beat an independent projection while still being kept out of the core model,
- and prospective validation is required before betting thresholds are activated.

## Glossary
Keep fast definitions for:
- spread,
- ATS,
- moneyline,
- total,
- push,
- win probability,
- model projection,
- market reference,
- model/market disagreement,
- projection reliability,
- betting confidence,
- release gate,
- out-of-distribution,
- prospective validation,
- account-verified price,
- HOLD.

## Support and About
Support should be tasteful and secondary. Make clear it is optional and that site content remains free. About should position the site as a transparent front end for model projections, validation, and football research.

## Responsive behavior
- Design from mobile upward.
- Keep sticky header and league switcher usable on narrow screens.
- Avoid horizontal overflow outside intentionally scrollable data tables.
- Projection cards on mobile should surface matchup, projected margin/score, model vs market spread, model vs market total, reliability, gate status, and HOLD/release state with minimal taps.
- Touch targets must be at least ~42px.
- Game-detail blocks should collapse into a logical stacked order rather than accordion overload.

## Accessibility
- Maintain semantic landmarks and labels.
- Preserve skip link.
- Strong visible focus state.
- High color contrast in both themes.
- Do not rely on color alone to communicate status.
- Respect reduced motion.
- Charts need accessible labels and nearby textual summaries.
- Reliability/gate icons must always have visible text equivalents.

## Product principles
1. **Projection first, market second.** The model is independently generated and then compared with the market.
2. **Reliability is not betting confidence.** Model uncertainty and recommendation evidence are separate concepts.
3. **Context is part of the workflow.** Injuries, weather, roof, travel, depth and price freshness live beside the projection even when they do not have learned coefficients.
4. **Readiness is visible.** Validation HOLD states are not hidden or softened.
5. **No false precision.** Use one decimal where appropriate and show empirical uncertainty when available.
6. **Rejected features remain transparent.** Context can be useful without being in the learned model.
7. **Fast weekly maintenance.** Routine updates come from data files, not manual page edits.
8. **Trust over hype.** The product should look more rigorous as validation gets stricter, not more promotional.
9. **No accidental release.** A research export must not silently become a public recommendation feed.
10. **One product, two leagues.** CFB and NFL share the design system but preserve separate validation maturity and model semantics.

## Suggested redesign data contract
Plan for a normalized projection object like:

```json
{
  "league": "NFL",
  "season": 2026,
  "week": 6,
  "gameId": "2026_06_NYJ_NE",
  "awayTeam": "NYJ",
  "homeTeam": "NE",
  "kickoff": "2026-10-18T13:00:00-04:00",
  "model": {
    "homeMargin": 11.0,
    "homeSpread": -11.0,
    "total": 46.4,
    "version": "NFL_RESEARCH_2026_W6"
  },
  "market": {
    "source": "BetMGM",
    "sourceType": "PUBLIC_BOOK_CAPTURE",
    "capturedAt": "2026-10-17T22:59:10Z",
    "homeSpread": -7.0,
    "homeSpreadOdds": 1.88,
    "total": 43.5,
    "overOdds": 1.90,
    "underOdds": 1.93,
    "accountExecutableVerified": false
  },
  "disagreement": {
    "spread": 4.0,
    "total": 2.9
  },
  "reliability": {
    "spreadTier": "C",
    "totalTier": "C",
    "label": "Projection reliability — not betting confidence"
  },
  "gates": {
    "personnel": "MAJOR_NONQB_ABSENCES",
    "weatherRoof": "FINAL_FORECAST_PENDING",
    "executionPrice": "NOT_ACCOUNT_VERIFIED"
  },
  "recommendation": {
    "state": "HOLD",
    "reason": "NO_VALIDATED_EDGE_THRESHOLD",
    "altLineState": "HOLD"
  },
  "websitePublishAllowed": false
}
```

The production data adapter should be able to map both legacy CFB data and future NFL normalized data into a common rendering layer without forcing the model pipelines themselves to become identical.

## Definition of done
The redesign specification is satisfied when:
- the product has a coherent premium visual system in dark and light mode,
- CFB and NFL can share one shell with a clear league switcher,
- each league preserves its own validation/readiness state,
- all existing functional IDs and required legacy data hooks still work or have a documented migration mapping,
- projections are easy to scan on desktop and mobile,
- projection reliability, market disagreement, and recommendation state are visually distinct,
- HOLD and out-of-distribution states are obvious,
- public market capture is not mislabeled as account-executable pricing,
- research and record sections look intentionally designed rather than appended,
- alt-line UI exists but remains disabled until validated,
- there are no broken filters, charts, bookmarks, deep links, exports, or data loads,
- GitHub Pages can deploy directly from the repository root with no build step,
- the responsible-gambling disclaimer remains visible,
- weekly updates still require data-file changes rather than manual page edits,
- and **nothing is merged/published from the NFL development branch until explicit final approval after prospective-readiness review.**
