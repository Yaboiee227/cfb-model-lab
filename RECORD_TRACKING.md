# Automated Record Tracking

The NFL and CFB models use the same grading logic but completely separate folders, weekly files, and record summaries. The record measures **projection performance**, not wagering performance.

## Permanent tracking principle
The model creates the projection position. The locked publication-time market number is the benchmark used to grade that position.

Each game can produce three independent projection grades:

1. **ATS projection** — compare the model spread with the saved market spread. The side that receives more value/cushion from the model is the projection position, and that side is graded against the saved market spread.
2. **Total projection** — model total below the saved market total = Under projection; model total above the saved market total = Over projection. Grade against the saved market total.
3. **Straight-Up projection** — the team the model projects to win. Grade only whether that team wins the game. The saved moneyline is reference metadata only and does not affect the SU W/L result.

ATS, Totals, and Straight Up are intentionally independent. A model may project one team to win outright while projecting the opponent as the ATS side versus the market.

### Pittsburgh example
- Saved market: Pittsburgh -2, total 46, Pittsburgh moneyline -110.
- Model: Pittsburgh -7, total 42, Pittsburgh projected to win.
- Final: Pittsburgh wins by 4; combined score 40.
- ATS projection position: **Pittsburgh -2 — WIN**.
- Total projection position: **Under 46 — WIN**.
- Straight-Up projection position: **Pittsburgh SU — WIN**. The -110 price is stored for reference but does not alter the grade.

## Source of truth
A weekly projection file freezes the model projection and the market spread/total/moneylines observed when the projection was published. Grading always uses those saved numbers. A later or closing line may be stored in `closing*` fields for optional CLV research, but it never changes the official projection grade.

`projectedSpreadHome` and `marketSpreadHome` are home-team-centric: negative means the home team is favored; positive means the home team is the underdog.

## Edge cases
- Model spread equals saved market spread: ATS `NO_PICK`, excluded.
- Model total equals saved market total: totals `NO_PICK`, excluded.
- Pick'em market: `0` is graded normally.
- Overtime: official final score including OT is used.
- Straight-up tie: `TIE`, excluded from SU W/L percentage.
- Postponed/cancelled/manual void: `VOID`, excluded.
- Non-final game: `PENDING`, excluded until a later run.
- Missing saved spread or total required for that category: `REVIEW`; never inferred or backfilled.
- Missing moneyline does not change the Straight-Up grade because SU is based only on the winner, but the missing price remains visible as unavailable reference metadata.
- Unmatched source game or failed source sanity check: workflow fails before publishing changed records.

## Locking and audit
Run `python scripts/lock_projections.py <file>` before kickoff. This records a SHA-256 digest over immutable grading fields. The grader refuses to run if a locked file changes. Git history provides the second audit layer.

The immutable grading fields include game ID, teams, kickoff, model spread, model total, projected winner, saved market spread, saved market total, saved home/away moneylines, market source, and market timestamp.

## Migrated CFB baseline
The audited 2026 Week 7 record is preserved in `cfb/record-baseline.json`. Future generated CFB weeks merge with that baseline instead of replacing it. Once a week exists as generated JSON, it supersedes the matching baseline week to prevent double counting.

## Score source
`scripts/score_sources.py` is the only ESPN-specific module. It checks ESPN's displayed final team score against the sum of returned period/OT linescores when available. The rest of the grader is source-agnostic so this module can be swapped later.

## Schedule and Eastern Time
GitHub cron is UTC. Fixed UTC times shift by one local hour when Eastern Time enters or leaves daylight saving time. The jobs are deliberately scheduled away from the top of the hour to reduce scheduler congestion:
- CFB: Sunday 15:17 UTC (11:17am EDT / 10:17am EST), catch-up 21:17 UTC (5:17pm EDT / 4:17pm EST).
- NFL: Tuesday 15:17 UTC (11:17am EDT / 10:17am EST), catch-up 21:17 UTC (5:17pm EDT / 4:17pm EST).

## Pages deployment
The grading workflows explicitly dispatch `.github/workflows/deploy-pages.yml` after a successful non-dry-run grade. This is necessary because commits made with the built-in `GITHUB_TOKEN` do not themselves trigger a Pages build.

## Weekly checklist
1. Publish the week's projections into the league's `projections/week-XX.json` with model spread, model total, projected winner, and the saved publication-time market spread, total, moneylines, source, and timestamp.
2. Lock it before the first kickoff and commit the locked file.
3. Do not edit locked immutable fields after kickoff.
4. Scheduled workflow grades only matched games; final games are graded, non-final games remain pending.
5. Catch-up run is idempotent because results are rebuilt by game ID and summaries are recomputed from result files rather than incrementing counters.
6. Verify the Actions run is green, the grading log was updated, and the site shows the new timestamp/week/pending state.
7. Corrections go through `manual-overrides.json`, never by editing generated result files.

## Dry run
Use Actions → Run workflow with `dry_run=true`, or run the grader with `--scores <mock-file> --dry-run`.

## Troubleshooting
- Missed schedule: use `workflow_dispatch`.
- Wrong official score: verify it, add a reasoned `SET_FINAL` override, rerun.
- Unmatched team: update `data/team-aliases.json` or save ESPN `sourceGameId`; rerun.
- Voided game: add a `VOID` override with reason and timestamp.
- Source down: workflow fails and the previous record remains published.
- Lock violation: restore the originally published values from Git history; never relock altered post-kickoff lines.
- Record updated in GitHub but site did not refresh: verify the `Deploy CB Model Projections Pages` workflow and the Pages source setting below.

## Repository settings
1. Settings → Actions → General → Workflow permissions: enable **Read and write permissions**. The record workflows request `contents: write`, `issues: write`, and `actions: write`.
2. Settings → Pages → Build and deployment → Source: select **GitHub Actions** so `deploy-pages.yml` can publish the refreshed static site.
3. GitHub Actions failure email/notification preferences remain controlled by your GitHub account.
