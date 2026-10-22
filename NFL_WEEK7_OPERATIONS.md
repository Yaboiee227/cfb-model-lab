# NFL Week 7 operating handoff — October 22, 2026

All 14 Canonical V1 and FTN50 forecasts remain frozen at `20261021T114427Z`. No new coefficient or feature is promoted. Week 6 official projections/results remain untouched; prior site display files are archived under `nfl_data/site/archive/week6-before-week7/`.

## Current state

- `nfl_data/site/projections.csv`: 14 research forecasts with the preexisting 2026 canonical-margin display calibration (no new fit). Market columns remain blank until a verified sportsbook observation is available; Covers percentage-priced thresholds remain separate in the board.
- `nfl_data/prospective/week7/operations/factor_register_20261022.json`: explicit state of every major factor family; presence in a catalog is not proof of capture, testing or promotion.
- `operations/officiating_20261022.json`: 14 reported lead referees from Football Zebras. RotoWire repeats that source, so it is not independent confirmation. Exact seven-person crews, substitutions and historical statistics are not verified. RefMetrics retrieved assignment page is Week 6. Football Zebras has a London/Paris prose inconsistency; official venue remains Paris.
- Official injury tables for 26 Thursday/Sunday teams and 10 NWS game-window forecasts are preserved in the staged board. Blank final status does not imply clearance. Monday reports, all final inactives, final roof decisions and gust coverage remain open.
- Giants have announced McCarthy after the model freeze. Jackson and Mayfield return decisions require official confirmation. Love practice status, Eagles starter/IR context, line clusters, activations and suspensions require game-specific follow-up. No arbitrary injury points.
- Week 7 Action Network/Evan Abrams primer exists, but detailed per-game trend records were not verified. Current trend display is explicitly pending; Week 6 trends archived. Nick Giffen's Week 7 Luck dashboard is located but numeric values were not captured. Neither layer changes projections or confidence.
- SIC/Chao medical interpretation stays contextual. Its October 21 article says Jackson had not practiced, conflicting with the official limited-participation report. Official report wins. No proprietary health score invented.
- The current nfelo.com endpoint was captured at 17:20:39 UTC for all 14 matching Week 7 games, separately under `operations/nfelo_benchmark_20261022T172039Z.json`. Publication time is unknown; retrieval time and source hash are retained. Sagarin/DVOA coverage remains incomplete. No full-readiness percentage or final-ready claim.

## Scheduled operations

The existing hourly **Pregame Model Refresh** task (`6ad6d415efcc8191bc0fd5d557b7a289`) was verified enabled and updated with Week 7 paths/rules. Its CFB instructions were preserved. Hourly polling is not a guarantee of exact T−60 execution; inspect actual runs and notify on gaps.

The new `nfl-week7-market-locks.yml` workflow is NFL-only. It requests FD/DK spreads/totals during the final 35 minutes, but only locks quotes whose source timestamps AND actual capture fall within T−30 to kickoff. Source timestamps must be at most five minutes old. Exact teams and kickoff must match. Captures retain both books; the first qualifying observation selects FanDuel, or DraftKings if FanDuel fails. That deterministic choice is declared before outcomes. Locks never overwrite, including after a later line move. No account execution, ROI or closing-line-value claim.

The job shares the market concurrency group and respects the existing quota reserve. Its scheduled dates cover the October 22/25/26 slate across UTC midnight, and the script rejects dates outside 2026 Week 7. GitHub scheduling can be delayed. Failed requests/missing secrets/stale quotes are logged and fail the run; uploaded artifacts preserve evidence if repository writes fail. No missing lock is reconstructed later.

## Remaining checkpoints (Eastern)

| Kickoff group | Inactive review | Approx. one-hour refresh | Eligible lock window |
|---|---|---|---|
| Thu 8:15 PM | 6:45 PM | 7:15 PM | 7:45–8:15 PM |
| Sun Paris 9:30 AM | 8:00 AM | 8:30 AM | 9:00–9:30 AM |
| Sun 1:00 PM | 11:30 AM | noon | 12:30–1:00 PM |
| Sun 4:05 PM | 2:35 PM | 3:05 PM | 3:35–4:05 PM |
| Sun 4:25 PM | 2:55 PM | 3:25 PM | 3:55–4:25 PM |
| Sun 8:20 PM | 6:50 PM | 7:20 PM | 7:50–8:20 PM |
| Mon 8:15 PM | 6:45 PM | 7:15 PM | 7:45–8:15 PM |

Friday: official Sunday final reports; Saturday: Monday final reports. Each refresh must check new transactions, IR/suspensions, expected starters and role changes, not just injury-table rows. Log source publication time separately from retrieval time. Preserve schedule discrepancies as blockers; do not silently re-key frozen games.

## Postgame and validation

Use `grade_nfl_paired_snapshot.py` on the NFL research branch with sourced FINAL scores and the preserved locks. Grade all 14 frozen pairs without hindsight exclusions. ATS/totals remain unavailable without eligible locks; SU/error measures remain possible. The existing Tuesday production record tracker is not assumed to consume the new paired Week 7 format automatically. Until verified, paired grading is an explicit remaining operation rather than a falsely completed integration.

Run `python scripts/audit_nfl_week7_release.py`, `python scripts/nfl_week7_operations.py --check`, `python -m unittest discover -s tests -p test_nfl_week7_operations.py -v`, and `python scripts/validate_nfl_trends.py`. Checks prove artifact integrity and gate behavior, not predictive accuracy.

## Source review

- https://www.footballzebras.com/2026/10/week-7-referee-assignments-2026/
- https://www.rotowire.com/football/article/nfl-referee-assignments-betting-trends-by-crew-133202
- https://www.refmetrics.com/nfl/referee-assignments-today
- https://www.nfl.com/injuries/
- https://www.actionnetwork.com/nfl/nfl-betting-primer-trends-stats-systems-for-every-game
- https://www.actionnetwork.com/nfl/nfl-week-7-luck-rankings-dashboard-edges-for-games-ints-sacks-fgs-more
- https://sicscore.com/news/2026-nfl-week-7-injury-report-latest-injuries-practice-updates-and-player-statuses

Keep canonical, challenger, benchmark, market and contextual layers separate. CFB code/data and historical results are outside these changes.
