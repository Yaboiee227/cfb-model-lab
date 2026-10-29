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
