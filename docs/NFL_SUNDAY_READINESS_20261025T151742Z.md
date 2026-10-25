# NFL Sunday readiness audit — October 25, 2026

Observed 2026-10-25T11:17:42.582406-04:00. All 14 frozen Week 7 projections verify against their manifest; all 12 Sunday games have Canonical and FTN50 coverage. Eleven games had not started at observation.

**Status: projection coverage complete; final game-day gates remain pending.** Canonical V1 and FTN50 remain frozen, research-only HOLD. No numerical injury/weather/referee overrides, promotion, or website publication.

| Game | Canonical fair spread | Total | Referee reported | Remaining review |
|---|---:|---:|---|---|
| PIT at NO | PIT -3.34 | 41.97 | Bill Vinovich | Already started; prior pregame capture preserved |
| CIN at BAL | BAL -4.03 | 46.92 | Shawn Smith | Official Ravens announcement October 24: Lamar Jackson OUT; Tyler Huntley to start. Preserve frozen numbers; flag QB-regime/reliability risk. |
| CLE at TEN | TEN -0.69 | 39.38 | Scott Novak | Cleveland OL/interior DL losses; Ward and Williams questionable. Tennessee Ridley/Spears/safety questions pending. Canonical and FTN50 disagree on winner. |
| IND at MIN | MIN -6.00 | 41.02 | Brad Rogers | Colts Tyler Warren and Sauce Gardner OUT. Vikings activated Jordan Mason October 24; activation does not itself confirm game-day availability. |
| MIA at NYJ | MIA -0.47 | 43.09 | Brad Allen | Hall remains officially questionable (quad); Sunday reports lean unavailable, not yet official inactive confirmation. Check Parham/Nwangwu and Miami LB/safety depth. |
| NYG at HOU | HOU -3.73 | 46.25 | Land Clark | Giants McCarthy starter announcement after freeze remains a QB-regime flag. Both teams have OL/secondary losses. Tank Dell questionable. |
| SF at ATL | SF -5.68 | 47.01 | Clay Martin | San Francisco WR/front-seven losses, including Evans, Samuel and Bosa. Christian Kirk QUESTIONABLE; league article mislabels Kirk as Kirksey, so retain official team identity. Atlanta OL/defense cluster and multiple questionable defenders. Official stadium event page lists roof OPEN. |
| TB at CAR | CAR -6.12 | 44.99 | Carl Cheffers | Mayfield expected to start per team reporting, still questionable until inactive review. Tampa Egbuka/Goedeke/Winfield OUT. Largest canonical versus FTN50 spread disagreement. |
| DEN at ARI | DEN -2.68 | 43.11 | Craig Wrolstad | Arizona Jeremiyah Love OUT; Carson Beck, Budda Baker and defensive depth questionable. Denver Surtain/Coleman questions require final review. |
| GB at DET | DET -4.08 | 50.01 | Alex Moore | Green Bay Love no final injury designation; Zaire Franklin OUT. League table retains Branch and Mays questionable despite league article claiming no Lions designations; keep unresolved until official inactives. |
| LA at LV | LA -5.96 | 46.65 | Ron Torbert | Rams Nacua/McDuffie QUESTIONABLE, Landman OUT. Raiders Washington and league-table Walker question unresolved; Rams article showed Walker without designation. Do not infer clearance from full practice. |
| KC at SEA | SEA -1.60 | 42.85 | John Hussey | Chiefs Rice/Moore/Brashard Smith OUT; Sneed QUESTIONABLE. Seattle Charbonnet/Surratt/Thomas OUT plus defensive questions. Bradford activation/return requires game-day confirmation. Seattle rain forecast remains context, without an arbitrary totals adjustment. |

## Weather and venue checks

Fresh NWS game-window hourly forecasts were captured for all remaining exposed/retractable venues. Baltimore 62–66 F, 2–3 mph; Nashville 72–76 F, 0–5 mph; East Rutherford 65–67 F, 2 mph; Charlotte 67–70 F, 10 mph; Atlanta 67–70 F, 10–15 mph with roof officially listed open. Houston 78–82 F, 10 mph and Arizona 80–82 F, 0–5 mph are outside conditions pending roof decisions. Seattle 51–55 F, 2–3 mph, chance light rain; this does not support an unqualified heavy-rain adjustment. Gust detail unavailable. Minnesota, Detroit and Las Vegas are indoor games. Paris receives no post-kickoff pregame rewrite.

## Required remaining windows

| Kickoff ET | Official inactives review | Market lock window |
|---|---|---|
| 1:00 PM | 11:30 AM | 12:30–12:59 PM |
| 4:05 PM | 2:35 PM | 3:35–4:04 PM |
| 4:25 PM | 2:55 PM | 3:55–4:24 PM |
| 8:20 PM | 6:50 PM | 7:50–8:19 PM |

Record exact seconds: markets must be captured strictly before kickoff. These are checkpoints, not a claim that monitoring is scheduled. Only eligible FanDuel/DraftKings quotes in the configured window can become locks. No usable new direct-book quote was verified in this audit. Current spread/gap fields remain unresolved rather than relabeling Thursday thresholds as current.

## Provisional Sunday reporting

Hall unlikely; Nacua optimistic; Ward warmup decision; Baker expected. Reports remain provisional; Surtain blurb names the wrong opponent. Source: https://www.nfl.com/news/week-7-injuries-sunday-pregame-2026-nfl-season

## Integrity and limitations

- This is a current audit, not a scheduled monitor.
- No final-window FD/DK market locks verified during this pre-window audit; old October 22 market thresholds are not current prices or grading locks. Current gaps remain null until fresh verified prices are captured.
- Raw team pages can contain stale headings or opponent tables. Explicit league sections and dated team announcements control; disagreements remain flagged.
- Questionable or full practice/activation is not final game-day availability.
- Head referees reported; full weekly crew substitutions unverified. RefMetrics N/A has no numeric influence.
- Houston and Arizona roof decisions unresolved. NWS hourly wind does not establish zero gusts.
- SIC, Abrams and Giffen received no newly verified numerical signals in this audit and no canonical weight.

- Structured audit: `nfl_data/prospective/week7/pregame_refresh/20261025T151742Z_SUNDAY_AUDIT.json`
- Source captures: `nfl_data/prospective/week7/context_captures/20261025T151411Z`
- Verification: existing three integrity tests passed; manifest hashes unchanged.

## Sources

- ravens: https://www.baltimoreravens.com/news/lamar-jackson-out-against-bengals-week-7-tyler-huntley-third-straight-start
- jets: https://www.newyorkjets.com/news/jets-injury-report-week-7-vs-dolphins-friday-10-23-2026
- bucs: https://www.buccaneers.com/news/buccaneers-panthers-injury-report-oct-23-week-7-2026
- rams: https://www.therams.com/news/rams-injury-report-week-7-2026-at-raiders-puka-nacua-trent-mcduffie-questionable-nate-landman-out
- vikings: https://www.vikings.com/news/jordan-mason-activated-colts-game-week-7-2026
- packers: https://www.packers.com/news/packers-rule-out-zaire-franklin-list-four-questionable-vs-lions-week-7-injury-report
- chiefs: https://www.chiefs.com/news/week-7-injury-report-chiefs-vs-seahawks-2026
- seahawks: https://www.seahawks.com/news/2026-week-7-injury-report-chiefs-at-seahawks
- roof_atl: https://www.mercedesbenzstadium.com/falcons-gameday/san-francisco-49ers
- refs: https://www.footballzebras.com/2026/10/week-7-referee-assignments-2026/
- refmetrics: https://www.refmetrics.com/nfl/official-assignments-today
