# NFL Step 7 — Existing CB Model Projections Integration Contract

## Purpose

Step 7 does **not** create a separate NFL website. The validated NFL prediction model will be added to the existing **CB Model Projections** static site as a second league within the same research interface.

The live CFB production site on `main` remains untouched until an explicit NFL release review authorizes integration.

## Product rule

The site becomes a shared football-model research interface with a top-level league switch:

- **College Football** — existing CFB model and current production behavior.
- **NFL** — NFL canonical spread/total model after release review.

Changing leagues changes the data source and league-specific context; it should not duplicate the site shell.

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

The current CFB site consumes data such as `data/config.json` and `data/projections.csv`. NFL integration should follow the same pattern rather than hardcoding weekly NFL games into page markup.

## NFL release conditions

NFL data may be generated for internal/site-preview use before public release, but the production site must not expose NFL as a public league option unless all of the following are true:

1. An explicit release review has been completed.
2. `website_publish_allowed` is true in the approved NFL release artifact.
3. The chosen NFL architecture is identified by an immutable model/snapshot version.
4. Prospective-validation state is displayed honestly.
5. HOLD projections are not presented as wagers.
6. Public sportsbook web-board observations are labeled as benchmarks unless account execution was verified.
7. CFB production data and behavior are unchanged by the NFL deployment.

## NFL data source of truth

Before public release, the preferred internal export is derived from:

- canonical prospective snapshot
- FTN50 shadow snapshot for comparison only
- latest timestamped public-book capture
- personnel / QB release gates
- weather / roof release gates
- reliability tiers
- multi-week prospective validation registry

Current Week 6 research export:

`nfl_data/research_exports/week6_cfb_style_research_latest.csv`

Current canonical snapshot:

`NFL_2026_W6_PRELOCK_20261017T225656Z`

## Site data layout

Recommended production structure after release approval:

```text
data/
  cfb/
    config.json
    projections.csv
    results.csv
    research.json
    team-aliases.json
  nfl/
    config.json
    projections.csv
    results.csv
    research.json
    team-aliases.json
```

Until Step 7 is authorized, NFL site-ready files stay under `nfl_data/site/` on `nfl-model-development` and must not replace anything under the production `data/` directory on `main`.

## League switch behavior

The interface should expose a persistent CFB / NFL selector near the brand/header.

Selection rules:

- Default to the user’s last selected league when valid.
- Default to CFB for first-time visitors until NFL public release is authorized.
- Update command-center labels, current week, validation state, projections, record and research content when the league changes.
- Preserve theme preference across leagues.
- Preserve league-specific filters and bookmarks without mixing CFB and NFL game IDs.
- Include `league` in bookmark keys, deep links and exports.

## Projection-field mapping

NFL site export should be compatible with the existing projections presentation while retaining NFL-specific state.

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

NFL-only fields retained in the export/API contract:

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
- `websitePublishAllowed`

## Win probability

Do not invent an NFL win-probability conversion solely for website completeness. If a validated NFL probability layer is unavailable, the UI should show `—` for win probability rather than deriving an unvalidated probability from the point spread.

## Model vs shadow presentation

The public projection value remains the approved canonical architecture unless an explicit promotion review changes it.

FTN50 is a challenger/shadow model. Before promotion it may appear only in research/detail context, clearly labeled **Shadow / challenger**, and must not silently replace the canonical projection.

## NFL reliability language

NFL reliability tiers are model-state / uncertainty indicators, not betting-confidence labels.

- **B** — standard model, final gates may still be pending
- **C** — elevated state/environment uncertainty
- **D** — out-of-distribution / hard-QB-break state

Do not convert B/C/D into stake sizes or PLAY/LEAN recommendations without Step 5 prospective calibration approval.

## Market language

Use:

- **Model spread**
- **Market reference**
- **Model/market difference**

Avoid language that treats a large difference as an edge that is automatically actionable.

If `user_account_execution_verified` is false, display the market as a public reference/benchmark.

## Record tracker

NFL record tracking must grade predictions, not implied bets.

Required breakdowns after prospective games accumulate:

- canonical spread MAE
- canonical total MAE
- signed bias
- canonical vs FTN50 same-game comparison
- model-vs-market direction record by descriptive disagreement bucket
- hard-QB vs normal-QB split
- elevated-weather split
- frozen-week history

The record UI should not show ROI or CLV unless the underlying NFL evidence policy explicitly permits those claims.

## Research hub additions for NFL

NFL research categories should include:

- QB / personnel
- official inactives
- offensive line / trench state
- weather / roof
- market snapshots
- pace / drives
- efficiency / explosiveness
- opponent adjustment
- prospective validation
- canonical vs shadow comparison

## Live-score adapter

The existing CFB live-score module points to ESPN college-football endpoints. NFL support should use a league-aware adapter rather than modifying CFB matching behavior in place.

Conceptually:

```js
const leagueAdapters = {
  CFB: { scoreboardSport: 'college-football', dataRoot: 'data/cfb/' },
  NFL: { scoreboardSport: 'nfl', dataRoot: 'data/nfl/' }
};
```

League-specific team aliases should be loaded from the active league data root.

## Deployment safety

Before merging Step 7 to `main`:

1. Run CFB regression checks with CFB selected.
2. Run NFL preview checks with NFL selected.
3. Verify no CFB data file was overwritten by NFL generation.
4. Verify mobile projection cards for both leagues.
5. Verify record/research filters remain league-scoped.
6. Verify HOLD and research-only language is visible.
7. Verify public NFL option is hidden or disabled whenever `website_publish_allowed` is false.
8. Verify static GitHub Pages deployment still works with no build step.

## Current status

- Integration target: **existing CB Model Projections site**
- Separate NFL site: **NO**
- NFL branch: `nfl-model-development`
- CFB production branch: `main`
- NFL public website release: **HOLD**
- Step 7 contract: **PREPARED**
- Production integration: **NOT STARTED / NOT AUTHORIZED**
