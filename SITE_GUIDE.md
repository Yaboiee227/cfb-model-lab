# CB Model Projections — Site Guide

CB Model Projections is a static GitHub Pages website built with HTML, CSS, and vanilla JavaScript. All weekly content is loaded from simple CSV/JSON files so routine updates do not require editing the front-end code.

## 1. Site structure

```text
/
├── index.html              # Single-page site structure and SEO metadata
├── styles.css              # Responsive dark/light design system
├── script.js               # Data loading, filters, record tracker, chart, bookmarks, sharing
├── data/
│   ├── config.json         # Season/week/status/model version/disclaimer/support link
│   ├── projections.csv     # Weekly projections + market comparison data
│   ├── results.csv         # Completed projection results used by record tracker
│   └── research.json       # Research Hub tabs/cards
├── SITE_GUIDE.md           # This file
└── .nojekyll               # Keeps GitHub Pages from applying Jekyll processing
```

The navigation is a single-page sticky header with anchors to Projections, Record, Research, Methodology, Glossary, Support, and About.

## 2. Weekly projections data

Edit `data/projections.csv`. Keep the header names exactly as shown:

```csv
season,week,date,kickoffET,gameId,awayTeam,awayConference,homeTeam,homeConference,projectedAwayPoints,projectedHomePoints,modelSpreadHome,modelTotal,homeWinProbability,awayWinProbability,marketSpreadHome,marketTotal,marketSource,marketObservedAt,executionVerified,dataQuality,signalStrength,releaseStatus,notes
2026,8,2026-10-24,3:30 PM,2026-10-24-AWAY-HOME,Away Team,ACC,Home Team,SEC,24.8,28.1,-3.3,52.9,62.4,37.6,-2.5,54.5,DraftKings public reference,2026-10-24 12:30 ET,false,1.0,MEDIUM,HOLD - READINESS,Research only
```

### Projection field notes

- `gameId`: unique stable identifier. Recommended format `YYYY-MM-DD-AWAY-HOME`.
- `modelSpreadHome`: spread from the HOME team's perspective. Negative = home favorite; positive = home underdog.
- `homeWinProbability` / `awayWinProbability`: percentages from 0–100. The site converts these to a display-only implied American moneyline.
- `marketSpreadHome`: current comparison line from the HOME team's perspective.
- `marketTotal`: current comparison total.
- `executionVerified`: `true` only if the price has actually been verified as executable in the intended jurisdiction; public-reference prices can remain `false`.
- `dataQuality`: use 0–1 (for example `0.95`) or 0–100. The site formats it as a percentage.
- `releaseStatus`: descriptive model/readiness status. The website does not convert this into a betting recommendation.
- Blank numeric fields are allowed when a baseline or current market number is unavailable.

## 3. Results / record tracker data

Edit `data/results.csv` after games are completed. The tracker automatically calculates ATS and straight-up records overall, by week, and by conference.

```csv
season,week,date,gameId,awayTeam,homeTeam,conference,awayScore,homeScore,modelSpreadHome,marketSpreadHome,modelTotal,marketTotal,homeWinProbability,atsProjection,atsResult,suProjection,suResult
2026,8,2026-10-24,2026-10-24-AWAY-HOME,Away Team,Home Team,SEC,21,31,-3.3,-2.5,52.9,54.5,62.4,Home Team -2.5,WIN,Home Team,WIN
```

Allowed grading values:
- `atsResult`: `WIN`, `LOSS`, or `PUSH`
- `suResult`: `WIN` or `LOSS`

This tracker is explicitly for **model projection performance**, not a wager ledger.

## 4. Research Hub data

Edit `data/research.json`. Each category becomes a tab.

```json
{
  "updated": "October 24, 2026 · game-day research",
  "categories": [
    {
      "id": "availability",
      "label": "Injuries & availability",
      "short": "Availability",
      "status": "Live audit",
      "summary": "Key availability context for the slate.",
      "items": [
        {
          "title": "Starting QB status",
          "detail": "Latest verified context goes here.",
          "tag": "QB watch"
        }
      ]
    }
  ]
}
```

Recommended categories already supported by the current file: availability, weather, market, efficiency, tempo, schedule, roster, situational.

## 5. Site configuration

Edit `data/config.json` when the week/model/status changes.

```json
{
  "siteName": "CB Model Projections",
  "season": 2026,
  "currentWeek": 8,
  "lastUpdated": "October 24, 2026 · 12:30 PM ET",
  "modelVersion": "Your current model version",
  "spreadValidation": "HOLD",
  "totalValidation": "HOLD",
  "publicationStatus": "Research only · no released bets",
  "venmoUrl": "https://venmo.com/u/Kaleb_InThe_Cut",
  "repoUrl": "https://github.com/Yaboiee227/cfb-model-lab",
  "disclaimer": "All content on CB Model Projections is model-generated and provided for research and entertainment purposes only. It is not betting advice and not an official wager recommendation. Past performance does not guarantee future results. Must be 21+ (or the legal age in your jurisdiction). If you or someone you know has a gambling problem, call 1-800-GAMBLER."
}
```

## 6. GitHub Pages setup

For a new or restored deployment:

1. Push the files above to the repository's `main` branch.
2. Open the GitHub repository.
3. Go to **Settings → Pages**.
4. Under **Build and deployment**, set Source to **Deploy from a branch**.
5. Choose branch **main** and folder **/(root)**.
6. Save.
7. Open the Pages URL after the deployment workflow succeeds.

For this repository the public URL is:

`https://yaboiee227.github.io/cfb-model-lab/`

## 7. Weekly update checklist

Use this order so the public data stays internally consistent:

1. **Update `data/config.json`** — season/week, timestamp, model version, validation states.
2. **Replace/update `data/projections.csv`** — current slate, model projections, win probabilities, market references, data quality, status.
3. **Update `data/research.json`** — current injuries/availability, weather, market movement, efficiency/context notes.
4. **Update `data/results.csv`** — append completed projection grades from prior games. Never delete historical rows unless correcting a data error.
5. Commit/push all data changes to `main`.
6. Confirm the GitHub Pages workflow completed successfully.
7. Open the live site and spot-check: one early game, one late game, filters, dark/light mode, record totals, and Research Hub.
8. Confirm the footer/projections disclaimer is still visible.

## 8. Features included

- Responsive desktop table + mobile cards
- Team search
- Week, conference, and date filters
- Sort by kickoff, win probability, spread gap, total gap, or data quality
- Dark/light mode stored locally in the browser
- Bookmark games locally (`localStorage`)
- Shareable game links using `?game=<gameId>#projections`
- Filtered CSV export
- Automatic overall/weekly/conference ATS + SU record calculations
- Vanilla-JavaScript cumulative ATS chart
- Research Hub tabs driven by JSON
- SEO description + Open Graph tags
- Keyboard focus states, skip link, semantic labels, high contrast, reduced-motion support

## 9. Good next enhancements

- Add a dedicated `history/` folder for archived weekly projection CSVs.
- Add team logos only if a reliable, lightweight asset source is maintained in-repo.
- Add a comparison toggle for opening line vs current line vs closing line.
- Add a calibration chart for win-probability buckets once enough graded data exists.
- Add CLV tracking once market-closing data is consistently captured.
- Add a static `404.html` that redirects deep links to the main page.
- Add a social-share image (`og:image`) and favicon set for stronger link previews.
- Add an optional conference/team URL query filter for shareable filtered views.
- Add an automated GitHub Action later to validate CSV column names and JSON syntax before Pages deploys.

## 10. Important publication rule

Keep model output, current market comparison, and release/validation status separate. A large model/market gap is a research signal and does not become an official wager recommendation simply because the number is large.
