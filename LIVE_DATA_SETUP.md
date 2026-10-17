# CB Model Projections — Live Games & Live Markets Setup

## What was added

The live suite keeps the site fully static on GitHub Pages. Browser code never contains a paid-provider API key.

### Browser/live-game modules
- `live-suite-loader.js` — loads the live suite after the existing site.
- `live-data.js` — ESPN scoreboard + game-summary adapter, game matching, polling, Page Visibility handling, short detail cache, mock mode.
- `live-ui.js` — Home-page Game-day Center, All/Live/Upcoming/Final filters, next-kickoff countdown, pause toggle, projection-row live status, change highlighting.
- `game-detail.js` — shareable `#game=EVENT_ID` full game sheet with Overview, Live Graphics, Box Score, Player Stats, Play-by-Play, Markets, and Model vs. Game tabs.
- `live-graphics.js` — field position, current drive, win-probability and score-margin graphics with graceful fallbacks.
- `markets-sportsbooks.js` — FanDuel/DraftKings reader for the static sportsbook snapshot.
- `markets-prediction.js` — Kalshi/Polymarket reader for the static prediction-market snapshot.
- `live-start.js` — startup, keyboard accessibility, disclaimer and glossary additions.
- `live-suite.css` — live-system styles, mobile full-screen game sheet, reduced-motion support.

### Data/config files
- `data/team-aliases.json` — team-name aliases used when ESPN/market names differ from `projections.csv`.
- `data/mock-live.json` — complete mock live-game + market dataset.
- `data/markets-sportsbooks.json` — generated FanDuel/DraftKings snapshot/history file.
- `data/markets-prediction.json` — generated Kalshi/Polymarket snapshot/history file.

### Scheduled data jobs
- `.github/workflows/refresh-sportsbook-markets.yml`
- `.github/workflows/refresh-prediction-markets.yml`

## Live-score architecture

The browser reads ESPN's public college-football site endpoints:

- Scoreboard: `https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`
- Game summary: `https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=EVENT_ID`

These endpoints are public but unofficial and undocumented. The site therefore treats every rich field as optional. If play-by-play, field position, drives, win probability, box score, or player statistics are absent, that component shows “Not available for this game” instead of failing.

The main scoreboard checks every 30 seconds only when at least one game is live. If no game is live, polling stops and one wake-up is scheduled for the next kickoff. Network refresh also stops while the tab is hidden or the user has paused updates.

Game-summary responses are cached briefly so reopening a detail sheet is fast.

## Sportsbook architecture

FanDuel and DraftKings are not scraped. The site uses a licensed odds data provider through a scheduled GitHub Action. The default workflow is configured for **The Odds API** and requests only:

- FanDuel
- DraftKings
- moneyline (`h2h`)
- spread (`spreads`)
- total (`totals`)

The secret key exists only inside GitHub Actions. The Action writes public market data to `data/markets-sportsbooks.json`, preserving the first seen line as the opening snapshot and adding compact movement history.

The workflow first checks the ESPN scoreboard. It skips the paid odds request unless a game is live or a kickoff is within six hours.

### The Odds API cost reality

As of October 2026, the provider advertises a free Starter plan with **500 credits/month**. A U.S.-region NCAAF request for three markets (`h2h`, `spreads`, `totals`) consumes three credits. This is enough for setup/testing and limited use, but not enough for continuous five-minute game-day collection across a season. The first paid API plan is currently **$30/month for 20,000 credits**.

Because GitHub Actions' minimum scheduled interval is five minutes and scheduled runs can be delayed, sportsbook data should be described as **near-live**, not instant. The browser may re-read the generated JSON more often, but the underlying file only changes when the scheduled Action runs.

## Configure the sportsbook key

1. Create an account with The Odds API and copy the API key.
2. Open the `cfb-model-lab` repository on GitHub.
3. Open **Settings → Secrets and variables → Actions**.
4. Choose **New repository secret**.
5. Name it exactly `ODDS_API_KEY`.
6. Paste the key and save it.
7. Open **Actions → Refresh sportsbook markets → Run workflow** once to test.
8. Confirm `data/markets-sportsbooks.json` receives a current `generatedAt` value and game rows.

The workflow declares `contents: write`. If the final commit/push step is blocked by repository policy, review **Settings → Actions → General → Workflow permissions** and make sure the workflow is allowed to write repository contents.

Never put `ODDS_API_KEY` in JavaScript, JSON committed to the repo, HTML, a query string, or a public issue.

## Prediction-market architecture

Kalshi and Polymarket are also written to a scheduled static snapshot. No secret key is required for the public read-only data used here.

- Kalshi base: `https://external-api.kalshi.com/trade-api/v2`
- Polymarket Gamma base: `https://gamma-api.polymarket.com`

The scheduled job uses ESPN's active/upcoming games as the candidate list, then matches market titles/outcomes to both teams using `data/team-aliases.json`. If both teams cannot be matched confidently, the site shows **No market listed / no reliable game match** rather than guessing.

Each matched source stores current home/away probability, volume/liquidity when available, timestamp, and compact price history.

Using a server-side GitHub Action also removes dependence on browser CORS behavior. If either public API changes its browser policy or endpoint shape, the live site still fails gracefully source-by-source.

## Team aliases

The canonical key in `data/team-aliases.json` should match the name in `data/projections.csv`. Add aliases when an external source uses a materially different name.

Example:

```json
"Miami (OH)": ["Miami Ohio", "Miami RedHawks", "Miami OH"]
```

The matching layer already ignores case, punctuation and most spacing differences, so aliases are only needed for genuinely different names or abbreviations.

## Record tracker / final results

Live scores never write to the record tracker.

When a game becomes Final, the game-detail view can calculate an **on-screen** ATS and Straight-Up result using the tracked pregame line, but it is explicitly temporary. `data/results.csv` remains the source of truth for the Record section.

Weekly grading workflow:
1. Let games finish.
2. Verify the final score and the exact tracked comparison spread used for grading.
3. Add/update the completed row in `data/results.csv` using the site's existing schema.
4. Commit the file.
5. The Record section will then update from that file.

Market snapshot files are research context only and never affect the record.

## Mock-data testing

Use:

`https://yaboiee227.github.io/cfb-model-lab/?mock=1`

or press **Mock mode** in the Game-day Center.

Mock mode provides:
- one in-progress Alabama @ Tennessee game,
- one upcoming Notre Dame @ BYU game,
- one Final Penn State @ Michigan game,
- box score/player/drive/play/win-probability data,
- FanDuel + DraftKings opening/current movement,
- Kalshi + Polymarket prices and history.

Turn mock mode off from the same button to return to public live data.

## Test checklist

### Home page
- All / Live / Upcoming / Final filters switch without a page reload.
- Live cards show score, quarter/clock, network, and possession when available.
- With no live game, the next-kickoff countdown appears.
- Pause live updates stops network polling.
- Hiding the browser tab stops polling; returning refreshes it.
- A score/state update briefly highlights the matched projection row/card.

### Game detail
- Click a live/upcoming/final game to open the sheet.
- URL becomes `#game=EVENT_ID`.
- Browser Back closes the sheet.
- Escape and the close button close it.
- Arrow keys move between focused tabs.
- Missing ESPN fields show a graceful “not available” state.
- On phones, the game sheet fills the screen.

### Markets
- FanDuel and DraftKings show only when present in the generated snapshot.
- Opening/current values and update times display.
- Moneyline comparison uses normalized no-vig probability when both sides exist.
- Kalshi/Polymarket show only when a confident match exists.
- A missing/rate-limited source shows a source-level unavailable message without breaking the page.

### Record integrity
- In-progress games do not change ATS or SU records.
- A Final game may show a temporary on-screen grade.
- Record cards/tables change only after `data/results.csv` is updated.

## Reliability notes

- **ESPN:** free/public site data, but unofficial and undocumented. Fields can change without notice.
- **The Odds API:** legitimate licensed odds aggregation; API key required. Usage is credit-limited.
- **Kalshi:** public read-only market data is available without authentication; endpoint/market taxonomy can still change.
- **Polymarket:** public Gamma/CLOB market data does not require a private trading key for read-only discovery, but browser CORS behavior is not relied on here.
- **GitHub Actions:** five minutes is the shortest schedule interval. Scheduled jobs are not guaranteed to start exactly on the minute and can be delayed. In public repositories, scheduled workflows can be disabled after 60 days without repository activity.
- **Snapshots:** line/price history begins when the workflows begin collecting. This build does not fabricate historical prices from before collection started.
- **Location:** market availability varies by location. The site provides no betting/trading links, promo codes, or affiliate links.

If any source changes or goes down, update only its adapter/workflow. The main projection model, `projections.csv`, `results.csv`, and the rest of the site remain independent.
