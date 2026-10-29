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

## NFL spread component diagnosis

An offline pinned-source audit reconstructs the canonical efficiency + coverage + Elo + margin-rating architecture and verifies all 14 frozen Week 7 margins. Component contributions sum to each original margin. Removing coverage, Elo or margin ratings and refitting with fixed hyperparameters slightly worsens aggregate MAE across 816 historical games.

A pass/rush allowance-sign hypothesis changes only those matchup definitions from offense minus defensive allowance to offense plus allowance. Higher defensive EPA allowed denotes weaker defense, motivating this alternative; the existing model also has net-efficiency features, so this does not establish that all forecasts have a sign bug. Candidate MAE 10.2447 vs baseline 10.2564: about 0.0117 points better. It improves 2023/2024 but worsens 2025. Too small and unstable to promote. These historical seasons have already been inspected; this is diagnostic reuse, not a blind holdout.

The largest Week 7 misses have no missing raw spread-matrix features, but that does not establish current personnel information. Personnel-event timestamp validation remains outstanding. Contributions from standardized correlated features are not causal player or home-field effects. NFL totals and all frozen projections remain unchanged.

## Personnel integration audit

Saved Week 7 publication evidence includes a confirmed Jackson-to-Huntley switch with an explicitly unadjusted frozen forecast, other starter regime flags, and zero numerical projection changes. The 14-game audit found three archived hard-QB-break flags. This is an integration gap, not proof that personnel changes caused a particular loss.

The reusable personnel gate checks game scope, timezone-aware pregame observation time, final availability and explicit QB state. Unknown is never treated as unchanged. A QB change requires a validated, actually applied adjustment before a personnel-adjusted label is allowed. A personnel-gate pass alone does not certify market, weather, referee or validation gates. The helper and tests are available for pipeline integration; they do not inject numerical adjustments into the canonical predictor.

Week 8 derived personnel gates remain HOLD for all 14 frozen research projections because no dated official availability evidence is supplied to this audit. These are separate diagnostic outputs, not replacements for the frozen predictions or evidence that later reports do not exist. Next requirement: a starter-state/position-group ingestion contract with verified event timestamps, followed by an isolated historically causal adjustment test.

## Personnel gates integrated into publication

`build_nfl_personnel_gates.py` reads explicit current-slate evidence and rejects duplicate/out-of-slate IDs. The main Week 8 publisher now calls it. `apply_nfl_personnel_gates.py` applies context to existing site rows while asserting all projection, freeze, and market fields remain unchanged. Unknown QB state is blank rather than false.

A dated official October 28 NFL injury-designation report was captured for CAR at GB. This is not final inactives or a model-relative starter comparison; all 14 personnel gates remain HOLD. No numerical personnel adjustment or accuracy improvement is claimed. The current helper enforces unvalidated/unapplied adjustments as blocked. A future promotion requires a separate model registry and point-in-time performance evidence.

## QB-change experiment and proxy comparison

Live Week 8 personnel gates were verified after deployment: 14 HOLD rows. Existing prior-only QB-room data is a performance proxy, not a confirmed target-game starter dataset. A new test adds one proxy family at a time to the unchanged current canonical NFL architecture using fixed lambda and chronological 2023-2025 folds. On 816 matched games: baseline MAE 10.2564; primary-quality proxy 10.2544 (roughly -0.0020); room-transition proxy 10.2913 (+0.0349). These are reused historical seasons, not blind evidence; neither result justifies promotion.

The QB event contract now requires starter expectation/source by freeze, confirmation/source before kickoff, replacement prior as-of no later than confirmation, and explicit exclusion of realized target-game starter information. Boundary tests cover invalid timing and missing evidence. The saved Huntley event has pregame confirmation but lacks verified expectation-at-freeze and replacement-prior timestamps, so it is ineligible. No numeric QB-change model was fitted from that event. The timeline contract is ready for valid events; historical source recovery and prospective collection remain necessary.

No model coefficients, frozen predictions or recorded outcomes were changed.
