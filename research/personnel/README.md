# Personnel scenario challenger — initial implementation

Status: executable scenario engine and paired evaluator; **not a fitted injury
model**, not calibrated, not canonical, and not used by either public baseline.
NFL and CFB requests, player valuations, baseline exposures and probability
calibrations must be independently scoped. Shared arithmetic is not shared
coefficients. No current player value has been invented.

## Run the synthetic example

From the repository root:

    python scripts/personnel_scenarios.py research/personnel/synthetic-request.json --as-of 2026-10-01T12:00:00Z --output /tmp/personnel-example.json
    python -m unittest discover -s tests -p test_personnel_scenarios.py -v

The output path must be new; existing files are never overwritten. The example
uses fictional players and values, and is not an Ohio State or Baltimore forecast.

## Input contract

See synthetic-request.json for the complete shape. Every evidence block requires
league, gameId, source and observedAt. Baseline evidence must identify the saved
forecast. Exposure evidence must explain which quarterback workload shares the
baseline already represents. Availability evidence must identify the applicable
conditional starter/backup scenario. Unknown status does not justify a made-up
probability of playing. Valuation evidence additionally requires a training cutoff
and an explicit methodStatus. Caller-supplied QB values are same-matchup offensive
point contributions at the same expected workload, with low/central/high estimates.
External benchmark valuations must remain labeled benchmark inputs.

The adjustment is the difference between the scenario QB mixture and the baseline
QB mixture. Identical exposure produces exactly zero adjustment and zero
sensitivity width. Scores, home spread (away minus home) and total are recomputed
together. Bounds are conservative sensitivity bounds, not confidence intervals.
No conditional scenarios are blended into a single forecast. Win probability is
withheld unless a separately evidenced, validated normal margin calibration for
that league is supplied; it does not make this personnel model validated.

This first version models one team's QB offensive contribution per request. It
does not yet model opposing defense, pace feedback, simultaneous position-group
losses, or combine two independent team adjustments. Do not chain adjustments by
pretending that a previously adjusted result is an independently frozen baseline.

## Work still required before useful current-player numbers

1. Assemble pregame-sourced starter and replacement identities and baseline QB
   exposure for each target matchup. Preserve unknowns and replacements explicitly.
2. Build separate NFL and CFB valuation estimators from pre-cutoff passing/rushing,
   sacks, turnovers, opponent strength, workload and supporting personnel. Team
   scoring differences alone cannot identify a causal quarterback contribution.
3. Estimate shrinkage and uncertainty for sparse backups using development folds;
   do not borrow NFL coefficients for CFB. Record estimator versions and sources.
4. Evaluate baseline versus adjusted predictions on chronological held-out QB
   changes. Include old absences, new absences, unchanged starters, unknown-input
   coverage, market-relative grading and probability calibration. Report failures.
5. Freeze prospective challenger scenarios before kickoff. Grade them separately
   against the original baseline and saved market. Explicit promotion remains
   required after evidence is reviewed.

## Evaluation

    python scripts/validate_personnel_challenger.py paired-games.json

Rows require league/gameId, predictionSourceSha256, trainingCutoff, frozenAt,
kickoff, resultObservedAt, resultSource, resultStatus=Final, finalHomePoints,
finalAwayPoints, baseline and challenger homePoints/awayPoints. The evaluator
rejects duplicates and invalid chronology and reports paired margin/total MAE by
league. It does not fit coefficients, test significance, or authorize promotion.
Timestamp assertions alone do not establish historical provenance: archives must
be independently checked. No historical or prospective improvement is claimed yet.
