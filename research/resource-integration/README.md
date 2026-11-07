# Current-week resource integration

This extends CB Model Projections. It does not replace either league's architecture or promote a new feature. NFL and CFB remain independent projection models.

## What is kept, added and withheld

Kept: the pinned NFL core/coverage/Elo/margin spread and core-total architecture, FTN50's existing shadow status, CFB foundation research, every existing freeze and all recorded grades. Previously unsuccessful feature tests remain unsuccessful; no additional layer is promoted because another website uses it.

Added: actual-time source capture, hashes and raw-byte retention; current-cycle schedule resolution; NFL diagnostic input snapshots; CFB direct benchmark capture; paired comparison contracts; and separate historical margin/total/probability diagnostics. Unknown QB state is missing, never false. Missing prices are not replaced by prior-week markets.

Withheld: new canonical features, arbitrary injury/weather/referee points, new win probabilities, market locks, confidence inferred from consensus, and any accuracy-improvement claim.

## Current review, November 6 Eastern / November 7 UTC

- Current cycle resolves to CFB Week 10 (62 stored games) and NFL Week 9 (15 scheduled games).
- The published NFL feed is still Week 8. A separately prepared, unpublished Week 9 release has 14 future-game research projections. Jacksonville–Baltimore has already started/completed and receives no reconstructed pregame forecast or grade.
- The exact pinned NFL generator reproduces all 14 saved Week 7 spread and total forecasts with maximum numerical difference 0.0. The current refresh uses only 2026 Weeks 1–8 and full prior-season context; no Week 9 result updates state.
- Current NFL diagnostic capture has 32 teams, offense and defense-allowed rows, with no missing completed prior-week game IDs. These unadjusted diagnostic aggregates are not replacements for the canonical feature definitions.
- Final CFB capture contains 53 Moore and 52 PiRate future-game benchmark observations, with every remaining game covered by at least one. Nine started games are excluded. The unmatched PiRate FIU row remains missing rather than being guessed from a misspelled source name. FEI bytes are retained as possession-scale context; no unvalidated conversion into points is made.
- CFB benchmark observations were captured later than the foundation's original freeze. Origin differences are explicit. They are prospective observations for remaining games, not same-information comparisons or evidence of superiority.
- Website publication was initially blocked by automatic approval review, citing a retained approval requirement. Production feeds were restored locally and a review package was saved. Caleb subsequently explicitly approved the prepared Week 9 research feed and pipeline activation. This approved release preserves every forecast number and frozen timestamp; final context remains unverified.

The preserved capture-time audit reports the then-missing production Week 9 projection and stale published week. The approved release supplies the prepared research feed; future audits evaluate the current repository state. A source-capture success must not conceal that operational gap.

## Commands

The ordinary capture/evaluation path uses Python 3.12's standard library and writes only to a new directory:

```bash
python scripts/capture_projection_resources.py --output /tmp/cb-resource-run --strict
python scripts/evaluate_projection_records.py --output /tmp/cb-resource-run/record-diagnostics.json
python -m pytest tests -q
```

Do not supply an old `--as-of` timestamp: the collector does not accept one. Completed games are not backfilled. A new run directory is required; captures cannot overwrite prior evidence. A missing current CFB schedule fails rather than falling back to last week's schedule. `--strict` saves the manifest first, then returns a nonzero status for missing scope, input, benchmark or projection coverage. Source/parser errors remain visible.

The historical record diagnostic reads the existing stored results and grades. It reports MAE, RMSE, median absolute error, bias, paired market-reference errors, existing W–L–P labels, Brier score, log loss and calibration bins. Groups remain separate by league/season/week/tracking class. It is reused historical diagnosis, not a new blind test. Market timestamps and model-version homogeneity are not certified by those legacy records, and no ROI or closing-price claim is made.

## Optional pinned NFL operational refresh

`refresh_nfl_pinned_research.py` requires a clean checkout at `0721b59b5f461ad590bd348bd655c4963265856c` and a recent capture with matching raw hashes. It also needs numpy, pandas and pyarrow. It verifies archived training/snapshot hashes, uses saved hyperparameters, requires exact spread/total reproduction within 1e-8, and excludes any kickoff crossed during generation.

```bash
python scripts/refresh_nfl_pinned_research.py \
  --source-root /path/to/clean-pinned-checkout \
  --capture /tmp/cb-resource-run \
  --output /tmp/cb-nfl-research-refresh
```

This audited source is season-specific to 2026. It is intentionally not an unattended weekly forecast publisher. A new season needs its own reviewed source and eligibility decisions. Fresh source data does not retroactively establish what was known before historical games.

`publish_nfl_current_research.py` stages an approved weekly research artifact into the existing NFL schema, preserves the prior feed in a write-once archive, and audits exact forecast parity. `publish_current_matchups.py` renders the existing matchup layout from saved league schedules. **Caleb explicitly approved publication of the prepared research release and activation of this evidence pipeline.** Neither obtains final personnel, weather, officials or market evidence.

## Automation and retention

The new `projection-resource-evidence.yml` workflow tests the contracts on pull requests. After merge/activation it captures sources at 10:15 UTC daily or by manual dispatch. It has read-only repository permissions, never pushes forecasts or site changes, uploads all captured raw bytes and diagnostics as an artifact, and reports gaps as a failed check after upload.

GitHub artifact retention is 90 days, not permanent storage. The first capture and release evidence are also preserved in a separate durable source archive for Caleb. Future raw snapshots must be archived before expiry if used as long-term validation evidence. The dated compact manifests/derived snapshots retained here are not a substitute for original source bytes when auditing feature calculations.

## Promotion path

Use the new ledger to accumulate prospective forecasts. Test one candidate family at a time with chronological training/tuning/test periods and paired game eligibility. Do not repeat tuning on the already-inspected historical folds and call the result a fresh holdout. External models, FEI, PiRate, Moore, markets, injuries, weather, refs and trends remain benchmark/context/challenger layers unless a separate evidence review and Caleb's explicit promotion authorize a canonical change.
