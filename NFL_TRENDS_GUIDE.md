# NFL Trends — Operating Guide

## What this feature does

The NFL Trends section is a static, manually maintained research layer. It does **not** scrape Action Network, does **not** change the frozen NFL model, and does **not** change reliability grades, confidence, projections, or official ATS/SU record tracking.

One weekly JSON file powers all three surfaces:

1. Compact trend-alignment badges on the NFL projection board.
2. The **Trends** tab in the NFL game research detail drawer.
3. The dedicated **NFL Trends** page with filters and top-aligned games.

The current data file is `nfl_data/site/nfl-trends.json`.

## Alignment rules

The only alignment function is `determineTrendAlignment()` in `trends.js`. It calls `determineModelLeans()` and applies these rules:

- **ATS** → compares `pointsTo` with the model's spread side versus the market spread.
- **SU** → compares `pointsTo` with the calibrated home-win side.
- **TOTAL** → compares `pointsTo` with model total versus market total.
- **SITUATIONAL** → uses the `alignmentTarget` you explicitly enter (`spread`, `moneyline`, `total`, or `none`).
- `pointsTo: none` is informational and gets no align/conflict judgment.
- Spread differences inside `spreadNeutralBand` are treated as **no model lean**.
- Totals inside `totalNeutralBand` are treated as **no model lean**.
- Win probability inside the configured band around 50% is treated as **no model lean**.
- Pick'em / near-push situations therefore do not create forced alignment labels.

Default neutral bands:

- spread: 0.25 points
- total: 1.0 point
- moneyline/win side: 0.5 percentage points around 50%

These are presentation rules only. They do not feed back into the projection.

## Weekly JSON entry

Start from `nfl_data/templates/nfl-trends-template.json` and replace the current `nfl_data/site/nfl-trends.json`.

Each trend requires:

- `id`
- `gameId`
- `season`
- `week`
- `matchup.away`
- `matchup.home`
- `subject` (away team, home team, or `TOTAL`)
- `trendType` (`ATS`, `SU`, `TOTAL`, `SITUATIONAL`)
- `alignmentTarget` (`spread`, `moneyline`, `total`, `none`)
- `text` — your own short paraphrase, maximum 180 characters
- `pointsTo` (`home`, `away`, `over`, `under`, `none`)
- `sampleSize`
- `record`
- `sourceName`
- `sourceUrl`
- optional `tags`

Use canonical team codes from the NFL projections file. Examples: `JAX`, `LA`, `WAS`, `LAC`. The validator rejects common aliases such as `JAC`, `LAR`, `WSH`, and `SD`.

## Mock-data mode

Open the NFL site with:

`?league=nfl&mockTrends=1#trends`

This loads `nfl_data/templates/nfl-trends-example.json`. Every example is explicitly labeled mock/synthetic and is not factual source content.

To show the in-page validator panel, use:

`?league=nfl&validateTrends=1#trends`

## Validation

Run locally or in GitHub Actions:

```bash
python scripts/validate_nfl_trends.py
node --check trends.js
```

The validator checks:

- JSON parseability
- required fields
- current week / stale-week warning
- unique trend IDs
- exact game IDs from the NFL projections package
- exact team/matchup codes
- team aliases / typos
- season/week consistency
- trend type and alignment-target consistency
- directional side validity
- short text length
- sample size and record fields
- source name/link
- separate trend-results outcome values

Publication CI should fail on validation errors.

## Stale-week behavior

The file-level `season` and `week` identify the currently loaded weekly trend package.

If it does not match the site's current NFL week:

- projection-board trend badges do not treat the file as current;
- game-detail trend content is hidden as stale;
- the Trends page displays an archived/stale banner;
- the source data remains viewable for research but cannot look current.

## Trend alignment results tracker

Use the separate `nfl_data/site/nfl-trend-results.json` file. Never put these results into the official model `results.csv`.

Result fields:

- `trendId`
- `gameId`
- `season`
- `week`
- `pointedSide`
- `alignmentAtPublish` (`aligns`, `conflicts`, `neutral`, `informational`)
- `marketType` (`spread`, `moneyline`, `total`, `none`)
- `outcome` (`win`, `loss`, `push`, `void`, `pending`)
- `finalScore`
- `gradedAt`
- `notes`

The page reports aligned-trend results separately with a small-sample warning.

## Weekly update checklist

1. Open Action Network's current NFL betting primer.
2. Confirm the primer week matches the NFL site current week.
3. Review each game manually.
4. Select only trends you want to summarize.
5. Rewrite each trend in your own short factual words; do not copy article prose.
6. Enter the correct game ID and canonical team abbreviations.
7. Enter trend type, alignment target, pointed side, sample size, record, source credit, and optional tags.
8. Update file-level `season`, `week`, and `lastUpdated`.
9. Run `python scripts/validate_nfl_trends.py`.
10. Test `?league=nfl&validateTrends=1#trends`.
11. Test projection badges, dedicated Trends page filters, and the game-detail Trends tab.
12. Test dark mode and light mode.
13. Test mobile width and keyboard navigation.
14. Publish only after CI is green.
15. After games are final, grade the separate `nfl-trend-results.json` tracker if desired.

## Testing checklist

- CFB mode does not show or load NFL Trends UI.
- NFL nav contains one-click **Trends** link.
- Current-week trends show on projection badges.
- Previous-week trends never appear as current badges.
- Aligns / Conflicts / No model lean / Informational each show icon + text, not color alone.
- `Aligns with model only` filter removes conflicting/informational trends.
- Team and type filters work together.
- Trend source link opens the original source in a new tab.
- Game detail opens with Overview / Trends / Context tabs.
- Trend alignment does not modify any projection field.
- Official model record remains untouched.
- Empty weekly trend file renders every game with `No trends entered yet` rather than failing.
- Mock mode is visibly labeled.
- Full site disclaimer remains unchanged.

## Source-use note

Review Action Network's current Terms of Use before each publishing workflow. Keep every trend summary in your own words, do not scrape or automatically copy the source page, keep entries short and factual, and always credit/link the original source. If the source's terms or permissions change, update this workflow before publishing additional summaries.
