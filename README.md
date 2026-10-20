# CFB Model Lab — Step 7 Website Snapshot

Snapshot: Oct 17, 2026 • 9:06 AM ET
Model: Advanced Calibrated 0.9I - Validation-Aware Release Framework
Open games: 52
Released bets: 0
Spread validation: HOLD
Total validation: HOLD

## Files
- `index.html` — site entry point
- `styles.css` — responsive dark-mode dashboard styling
- `app.js` — search, filters, sorting, game-card rendering
- `data.js` — embedded frozen snapshot for direct/static hosting
- `data.json` — same snapshot in JSON for future automated refreshes
- `MODEL_SOURCES.md` — vetted CFB/NFL source and resource registry, source roles, governance, and promotion restrictions

## Sources & provenance
`MODEL_SOURCES.md` is the project source-of-truth registry for vetted external data, market, benchmark, challenger, contextual, news, weather, personnel, and research resources. A source appearing in the registry does not automatically make its metrics canonical model inputs. Canonical promotion still requires leakage-safe historical testing, walk-forward/out-of-sample validation, prospective frozen-week evidence, and explicit promotion.

## Deployment
Upload the folder to any static host (Replit, Render Static Site, Cloudflare Pages, Netlify, GitHub Pages, etc.).
No build step or external package is required.

## Data contract
The site is intentionally release-aware. It can display model projections while keeping betting recommendations blocked whenever validation/readiness gates are not cleared.
