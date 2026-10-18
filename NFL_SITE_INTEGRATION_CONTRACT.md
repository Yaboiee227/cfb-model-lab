# NFL Stage 6 — Existing CB Model Projections Integration Contract

## Purpose

Stage 6 does **not** create a separate NFL website. The NFL prediction system is integrated into the existing **CB Model Projections** static site as a second league within the same research interface.

The live CFB production site on `main` remains the production default until an explicit NFL release review authorizes the NFL league option for production. Technical integration and branch preview are allowed while `websitePublishAllowed` remains false.

## Product rule

The site is designed as a shared football-model research interface with a top-level league switch:

- **College Football** — existing CFB model and current production behavior.
- **NFL** — canonical NFL spread/total research model with its own data, validation state, context and release permissions.

Changing leagues changes the data source and league-specific context; it does not duplicate the site shell or mix league evidence.

## Existing CFB architecture to preserve

The current site is static GitHub Pages using semantic HTML, CSS and vanilla JavaScript. Weekly content is data-driven. Existing CFB behavior must remain intact, including:

- command center / model status
- projections desktop table and mobile cards
- search, date filters and sorting
- bookmarks/stars and sharing
- CSV export
- record tracker
- research hub
- methodology / glossary / support / responsible-gambling language
- explicit HOLD states

The current CFB site consumes data such as `data/config.json` and `data/projections.csv`. NFL integration follows the same presentation pattern while keeping NFL files under their own data root.

## Current Stage 6 state

Stages 1–5 are complete at the architecture/infrastructure level. Stage 6 is the current technical integration layer.

- Canonical NFL Week 6 snapshot is immutable.
- Stage 2 historical validation is complete.
- Stage 3 context/market execution policy is locked; live pregame gates continue to refresh.
- Stage 4 calibration governance is complete, but recommendation evidence is not earned.
- Stage 5 weekly production/audit infrastructure is complete and prospectively accumulating evidence.
- Stage 6 branch integration may show NFL research projections while all betting/recommendation language remains HOLD.

## NFL production-release conditions

NFL data may be generated and rendered for branch/internal research preview before public production release. The production `main` site must not expose NFL as an approved public league option unless all of the following are true:

1. An explicit production release review has been completed.
2. The approved NFL release artifact authorizes the intended publication mode.
3. The chosen NFL architecture is identified by an immutable model/snapshot version.
4. Prospective-validation state is displayed honestly.
5. HOLD projections are not presented as wagers.
6. Public sportsbook web-board observations are labeled as benchmarks unless account execution was verified.
7. Betting confidence, PLAY/LEAN, alt-line recommendations, ROI and CLV remain hidden unless their separate evidence gates are explicitly passed.
8. CFB production data and behavior are unchanged by the NFL deployment.

`websitePublishAllowed = false` currently means **no production NFL release**. It does not prevent branch-level technical preview or CI verification.

## NFL data source of truth

The Stage 6 research export is derived from:

- canonical prospective snapshot
- FTN50 shadow snapshot for comparison only
- latest timestamped public-book capture
- personnel / QB release gates
- weather / roof release gates
- reliability tiers
- validated display win probability
- multi-week prospective validation registry

Current Week 6 research export:

`nfl_data/research_exports/week6_cfb_style_research_latest.csv`

Current canonical snapshot:

`NFL_2026_W6_PRELOCK_20261017T225656Z`

Current site adapter output:

`nfl_data/site/`

## Site data layout

Current development layout:

```text
data/                 # production CFB data path
nfl_data/site/        # NFL branch/research site package
  config.json
  projections.csv
  results.csv
  research.json
```

Recommended production structure after an explicit release decision may evolve toward league-scoped roots, but NFL generation must never silently overwrite CFB production data.

## League switch behavior

The interface exposes a persistent CFB / NFL selector near the brand/header on the development branch.

Selection rules:

- Default to the user’s last selected league when valid.
- Default to CFB for first-time visitors.
- Update command-center labels, current week, validation state, projections, record and research content when the league changes.
- Preserve theme preference across leagues.
- Preserve league-specific filters and bookmarks without mixing CFB and NFL game IDs.
- NFL bookmarks use an NFL-specific storage key.
- Include league context in deep links and NFL exports.

## Projection-field mapping

NFL site export is compatible with the existing projections presentation while retaining NFL-specific state.

| Existing site concept | NFL source |
| --- | --- |
| `season` | 2026 |
| `week` | NFL week |
| `date` | `gameday` |
| `kickoffET` | `gametime_et` |
| `gameId` | NFL canonical `game_id` |
| `awayTeam` | `away_team` |
| `homeTeam` | `home_team` |
| `projectedAwayPoints` | `(model_total - canonical_home_margin) / 2` |
| `projectedHomePoints` | `(model_total + canonical_home_margin) / 2` |
| `modelSpreadHome` | `canonical_home_spread` |
| `modelTotal` | `model_total` |
| `marketSpreadHome` | `public_book_home_spread` |
| `marketTotal` | `public_book_total` |
| `marketSource` | `public_book` + benchmark label |
| `marketObservedAt` | `public_book_capture_utc` |
| `executionVerified` | `user_account_execution_verified` |
| `releaseStatus` | `recommendation` / release gate |
| `notes` | release blockers + reliability context |

NFL-specific fields retained in the export/API contract:

- `league = NFL`
- `shadowModelSpreadHome`
- `spreadReliability`
- `totalReliability`
- `spread68Low`
- `spread68High`
- `total68Low`
- `total68High`
- `personnelState`
- `hardQbStateBreak`
- `qbExpectedStarter`
- `qbOperationalPointAdjustment`
- `weatherRoofState`
- `weatherElevatedUncertainty`
- `finalInactivesResolved`
- `releaseBlockers`
- `preferredArchitecture`
- `winProbabilityState`
- `websitePublishAllowed`

## Win probability

NFL win probability may be displayed because the canonical-margin probability layer passed its separate walk-forward research/display validation gate.

Policy:

- label it as calibrated research probability,
- do not call it a moneyline edge,
- do not derive stake sizing from it,
- keep hard-QB/out-of-distribution context visible,
- do not allow probability display eligibility to bypass Stage 4 recommendation calibration.

## Model vs shadow presentation

The public-facing research projection remains the canonical architecture unless an explicit future promotion review changes it.

FTN50 is a challenger/shadow model. Before promotion it may appear only in research/detail context, clearly labeled **Shadow / challenger**, and must not silently replace the canonical projection.

## NFL reliability language

NFL reliability tiers are model-state / uncertainty indicators, not betting-confidence labels.

- **B** — standard model, final gates may still be pending
- **C** — elevated state/environment uncertainty
- **D** — out-of-distribution / hard-QB-break state

Do not convert B/C/D into cover probabilities, stake sizes or PLAY/LEAN recommendations without Stage 4 prospective calibration approval.

## Market language

Use:

- **Model spread**
- **Market reference / benchmark**
- **Model / market difference**

Avoid language that treats a large difference as an edge that is automatically actionable.

If `user_account_execution_verified` is false, display the market as a public reference/benchmark.

## Projection audit / record tracker

NFL record tracking grades frozen projections and benchmark direction, not released wagers.

Required breakdowns after prospective games accumulate:

- canonical spread MAE
- canonical total MAE
- signed bias
- canonical vs FTN50 same-game comparison
- model-vs-market direction record by descriptive disagreement bucket
- hard-QB vs normal-QB split
- elevated-weather split
- frozen-week history

The NFL UI should use language such as **Prospective projection audit** or **Market direction** rather than implying that benchmark grading is an official betting record. It must not show ROI or CLV unless the underlying evidence policy explicitly permits those claims.

## Research hub additions for NFL

NFL research categories include:

- QB / personnel
- official inactives
- offensive line / trench state where available
- weather / roof
- market snapshots
- efficiency / explosiveness
- opponent adjustment
- prospective validation
- canonical vs shadow comparison
- weekly production workflow

## Live-score adapter

The existing CFB live-score module points to college-football endpoints. NFL support uses league-aware routing rather than modifying CFB matching behavior in place.

Conceptually:

```js
const leagueAdapters = {
  CFB: { scoreboardSport: 'college-football', dataRoot: 'data/' },
  NFL: { scoreboardSport: 'nfl', dataRoot: 'nfl_data/site/' }
};
```

League-specific team aliases and future live-state adapters must remain league scoped.

## Development-branch UI requirements

NFL mode must visibly enforce the research state:

- NFL title/description and league switch
- canonical spread, total and projected score
- calibrated research win probability
- public market benchmark and timestamp
- **Model / market difference**, not validated edge
- reliability grade, not betting confidence
- personnel/QB and weather/roof context
- HOLD/release blockers
- historical OOS sample and prospective sample status
- FTN50 only as labeled shadow/challenger
- NFL-specific bookmark storage
- NFL-specific CSV export including league, validation/context and release fields
- alternative-line recommendation UI hidden while locked

## Deployment safety

Before any production merge to `main`:

1. Run CFB regression checks with CFB selected.
2. Run NFL branch-preview checks with NFL selected.
3. Syntax-check the shared JavaScript files.
4. Verify no CFB data file was overwritten by NFL generation.
5. Verify mobile projection cards for both leagues.
6. Verify record/research filters remain league scoped.
7. Verify HOLD and research-only language is visible.
8. Verify `Model / market difference` is used instead of validated-edge language.
9. Verify the NFL challenger is clearly labeled shadow/challenger.
10. Verify alternative-line, unit-sizing and recommendation UI remains hidden/locked.
11. Verify production release permissions before exposing NFL from `main`.
12. Verify static GitHub Pages behavior still requires no build step.

## Current status

- Integration target: **existing CB Model Projections site**
- Separate NFL site: **NO**
- NFL branch: `nfl-model-development`
- CFB production branch: `main`
- Stage 6 technical integration: **ACTIVE / BRANCH PREVIEW**
- NFL recommendation release: **HOLD**
- NFL production website release: **HOLD**
- Current site package: **RESEARCH ONLY**
- Production merge: **NOT AUTHORIZED YET**

## Stage 6 completion standard

Stage 6 technical integration is complete when CI verifies:

- shared-site loader order and league routing,
- valid JavaScript syntax,
- NFL site data package contract,
- NFL/CFB bookmark and data isolation,
- canonical/shadow distinction,
- research/HOLD terminology,
- reliability and context visibility,
- release-permission enforcement,
- production CFB data protection.

Technical Stage 6 completion does **not** itself authorize merging NFL into production `main`. That later action remains an explicit release decision informed by prospective evidence and the approved publication mode.
