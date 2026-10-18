# NFL Trends — Operating Guide

## System
The NFL Trends section is a static, manually maintained research layer. It never scrapes a third-party page, never changes the frozen NFL model, and never changes reliability, confidence, projections, or official ATS/SU record tracking.

One weekly file, `nfl_data/site/nfl-trends.json`, powers the NFL projection badges, the NFL game-detail Trends tab, and the dedicated NFL Trends page.

## Alignment rules
`determineTrendAlignment()` in `trends.js` is the single alignment function.

- ATS compares with the model spread side versus the market spread.
- SU compares with the calibrated win side.
- TOTAL compares model total versus market total.
- SITUATIONAL uses the entered `alignmentTarget`: spread, moneyline, total, or none.
- `pointsTo: none` is informational.
- Spread differences within 0.25 points are `No model lean`.
- Total differences within 1.0 point are `No model lean`.
- Win probabilities within 0.5 percentage points of 50% are `No model lean`.

Alignment is presentation context only.

## Required trend fields
- id
- gameId
- season / week
- matchup.away / matchup.home
- subject (away team, home team, or TOTAL)
- trendType: ATS, SU, TOTAL, SITUATIONAL
- alignmentTarget: spread, moneyline, total, none
- text: your own short paraphrase, maximum 180 characters
- pointsTo: home, away, over, under, none
- sampleSize
- record
- sourceName / sourceUrl
- optional tags

Use canonical NFL codes such as JAX, LA, WAS and LAC. The validator rejects common aliases and unmatched games.

## Mock and validator modes
Mock UI: `?league=nfl&mockTrends=1#trends`

Show the in-page validator: `?league=nfl&validateTrends=1#trends`

The mock file is `nfl_data/templates/nfl-trends-example.json`; all sample trends are explicitly synthetic.

## Validation
Run:

```bash
python scripts/validate_nfl_trends.py
node --check trends.js
```

Validation covers required fields, unique IDs, game/team matching, week/season consistency, aliases/typos, type/target/side consistency, text length, sample and record fields, source links, and trend-result outcome values.

## Stale-week behavior
If the trends file week does not match the current NFL week, the site labels it archived/stale, excludes it from projection badges, and hides it from current game-detail trend panels.

## Separate results tracker
Use `nfl_data/site/nfl-trend-results.json`. Do not add trend alignment grades to the official NFL `results.csv`.

Fields: trendId, gameId, season, week, pointedSide, alignmentAtPublish, marketType, outcome, finalScore, gradedAt, notes.

## Weekly checklist
1. Open the current Action Network NFL betting primer.
2. Verify the week.
3. Review every matchup manually.
4. Choose only trends you want to summarize.
5. Rewrite each in your own short factual words; do not copy article prose.
6. Enter the exact game ID and canonical team codes.
7. Enter type, alignment target, side, sample size, record, source credit/link and tags.
8. Update season, week and lastUpdated.
9. Run `python scripts/validate_nfl_trends.py`.
10. Test `?league=nfl&validateTrends=1#trends`.
11. Test projection badges, Trends filters and game-detail Trends tab.
12. Test dark/light mode, mobile width and keyboard navigation.
13. Publish only after CI passes.
14. Grade the separate trend tracker after final games if desired.

## Source-use note
Review Action Network's current Terms of Use before each weekly publishing workflow. Keep every trend summary in your own words, do not scrape or automatically copy the source page, keep entries short and factual, and always credit and link the original source.
