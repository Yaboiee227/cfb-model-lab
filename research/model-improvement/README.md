# Incremental model improvement

The current CFB and NFL prediction architectures and frozen outputs are preserved.

## Completed diagnostic

Run `python scripts/audit_projection_errors.py`. Output: `error-audit.json`. Forecasts are compared with stored grading references on identical games. These references are not verified closing prices. Each league and week stays separate because published records combine different model periods. Missing-reference exclusions are listed explicitly. Negative spread error means the model favored the home team too strongly.

The NFL Week 7 spread error is concentrated in several away blowouts that also surprised the market. This does not justify applying an 8.57-point correction to future games. The existing CFB study showed the strongest aggregate total-error improvement from tempo/possession, but had only two evaluation folds.

## Existing research continued

The foundation feature-family runner tests isolated box-score families against the existing locked foundation. These are yards/play, pass/rush efficiency, drive control, discipline, tempo/possession and recent form/rest. They are not an EPA or success-rate model. An extended run through completed Week 8 is retrospective research; the outcomes have already been observed and this is not a new blind holdout. Revised historical source bytes may differ from their original pregame availability.

Run `python scripts/cfb_foundation_feature_validation.py --as-of 2026-10-27T04:00:00Z --output cfb/validation/oct29-incremental-feature-review.json`. Existing eligibility thresholds remain unchanged. Eligibility permits isolated prospective shadow evaluation only. No family stacking or canonical promotion is authorized by this run.

## Next decision

Use the expanded evaluation to select at most one isolated family for a new prospective snapshot before future kickoffs. Require later untouched games to confirm incremental value. Preserve losing tests and avoid retroactively replacing published forecasts. EPA/success-rate ingestion requires separate source and timestamp validation before testing.

## Execution status

The October 29 extended ESPN historical fetch was blocked by environment network policy. No extended result exists and no family earned new eligibility. The completed frozen-integrity audit checked 56 CFB and 14 NFL saved records, finding zero checked-field issues. Venue labels and advanced calculations still require independent verification. `cfb-total-experiment.json` defines the next isolated hypothesis; it is not a running prospective candidate.

## Alternate-source extension completed

SportsDataverse season files replaced live endpoint fetching. Upstream remains ESPN-derived. 2025: 912 regular-season games and 100% box coverage. 2026 through the cutoff: 566 regular-season games and 100% box coverage. The two overlapping baseline evaluation weeks reproduce prior metrics within 1e-8. Extended research covers 173 games in three evaluation weeks. No family passes the unchanged eligibility criteria. Tempo/possession total MAE delta is -0.4253 points; this does not authorize promotion. The earlier proposed prospective tempo experiment is now on HOLD.

The runner uses saved prior-season HFA and preserves the existing foundation and feature definitions. This is revised-source retrospective research, not a blind prospective trial. It is also not a game-level EPA/success-rate test.

## EPA-only exploratory test

The dataset runner now supports `--epa`. It substitutes overall, passing and rushing EPA/play in the existing opponent-adjustment fitter and tests one isolated family. Missing EPA values are left missing; box-score yardage is never used as an EPA fallback. Success rate is absent from this source schema and is not substituted with first-down rate. No new possession estimate was implemented in this test.

Three evaluation weeks, 173 games: margin MAE delta +0.2657 points (worse); total MAE delta -0.1345 points (small improvement). Neither target passes the existing family rules. The historical EPA model training cutoff is unverified, so the result is exploratory regardless of apparent performance. No promotion or live projection change. Next research priority: explicit drive/possession estimates with validated definitions, and point-in-time EPA provenance before stronger claims.

## Drive-based testing

A new drive-count helper rejects duplicate drive IDs and excludes non-regulation periods, invalid period/play fields and drives without offensive plays. It retains kneel-only drives when the source counts them as offensive plays; this is recorded offensive-drive volume, not a verified non-kneel possession simulator. Tests cover team ownership and exclusions.

The opponent-adjusted combined expected drive-volume feature was evaluated alone on the same 173 games. Existing baseline-refit approach: total MAE delta -0.0935; fixed-baseline residual correction: +0.0089 (worse). Neither passes eligibility. Both baseline metric sets exactly reproduce the previous evaluation. No live model changes.

The runner now supports --residual, holding the existing baseline coefficient at one and learning a correction using only earlier games. This is an experimental evaluation option, not production behavior. Historical source revisions and repeated testing of these same three weeks limit inference; future candidate selection must use later untouched games.
