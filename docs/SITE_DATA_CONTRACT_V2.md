# CB Model Projections — Site Data Contract v2

## Purpose
Define a normalized, league-aware interface between the CFB/NFL model pipelines and the future CB Model Projections redesign without changing either model's internal feature architecture.

This is a **design/development contract only**. It does not authorize NFL website publication.

## Design rules
1. CFB and NFL share a rendering contract, not a modeling contract.
2. `websitePublishAllowed=false` is a hard guard.
3. A model projection can exist while recommendation state remains `HOLD` or `NOT_VALIDATED`.
4. Market reference, public-book capture, and account-verified executable price are distinct source states.
5. Projection reliability is separate from betting confidence/recommendation evidence.
6. Context-only features must never be rendered as if they carry learned model weight.
7. Historical retrospective grading and prospective locked-snapshot grading remain separate.
8. Alt-line fields may be present while activation state remains `HOLD`.

## Normalized league metadata
```json
{
  "league": "NFL",
  "season": 2026,
  "week": 6,
  "modelVersion": "NFL_RESEARCH_2026_W6",
  "updatedAt": "2026-10-17T23:00:00Z",
  "projectionState": "RESEARCH",
  "recommendationState": "NOT_VALIDATED",
  "prospectiveValidationState": "ACCUMULATING",
  "marketExecutionState": "PUBLIC_CAPTURE_ONLY",
  "websitePublishAllowed": false
}
```

Allowed `projectionState` values:
- `LIVE`
- `RESEARCH`
- `HOLD`

Allowed `recommendationState` values:
- `RELEASED`
- `HOLD`
- `NOT_VALIDATED`

Allowed `prospectiveValidationState` examples:
- `NOT_STARTED`
- `ACCUMULATING`
- `SUFFICIENT_SAMPLE_PENDING_REVIEW`
- `APPROVED`

Allowed `marketExecutionState` examples:
- `REFERENCE_ONLY`
- `PUBLIC_CAPTURE_ONLY`
- `ACCOUNT_VERIFIED`

## Normalized game projection object
```json
{
  "league": "NFL",
  "season": 2026,
  "week": 6,
  "gameId": "2026_06_NYJ_NE",
  "kickoff": "2026-10-18T13:00:00-04:00",
  "awayTeam": "NYJ",
  "homeTeam": "NE",
  "model": {
    "homeMargin": 11.012,
    "homeSpread": -11.012,
    "total": 46.378,
    "awayScore": null,
    "homeScore": null,
    "winProbabilityHome": null,
    "impliedMoneylineHome": null,
    "architecture": "core + defensive coverage + win Elo + margin rating",
    "version": "NFL_RESEARCH_2026_W6"
  },
  "market": {
    "source": "BetMGM",
    "sourceType": "PUBLIC_BOOK_CAPTURE",
    "capturedAt": "2026-10-17T22:59:10Z",
    "homeSpread": -7.0,
    "awaySpread": 7.0,
    "homeSpreadOddsDecimal": 1.88,
    "awaySpreadOddsDecimal": 1.95,
    "total": 43.5,
    "overOddsDecimal": 1.90,
    "underOddsDecimal": 1.93,
    "accountExecutableVerified": false
  },
  "disagreement": {
    "spread": 4.012,
    "total": 2.878,
    "spreadDirection": "HOME_SIDE_OF_BOOK_LINE",
    "totalDirection": "OVER_SIDE_OF_BOOK_TOTAL"
  },
  "reliability": {
    "spreadTier": "C",
    "spreadLabel": "ELEVATED_STATE_UNCERTAINTY",
    "spreadReason": "Major non-QB absences remain",
    "totalTier": "C",
    "totalLabel": "ELEVATED_STATE_UNCERTAINTY",
    "totalReason": "Personnel state is materially unresolved",
    "isBettingConfidence": false
  },
  "uncertainty": {
    "spread68": [-1.168, 24.392],
    "spread80": [-5.400, 29.274],
    "spread90": [-11.185, 34.249],
    "total68": [34.882, 60.811],
    "total80": [31.373, 65.492],
    "total90": [27.585, 71.581]
  },
  "gates": {
    "personnelState": "NO_QB_BREAK_IDENTIFIED_MAJOR_NONQB_ABSENCES",
    "hardQbStateBreak": false,
    "weatherRoofState": "OUTDOOR_FINAL_FORECAST_REFRESH_REQUIRED",
    "weatherRoofFinal": false,
    "executionPriceState": "PUBLIC_CAPTURE_NOT_ACCOUNT_VERIFIED",
    "finalInactivesVerified": false
  },
  "recommendation": {
    "state": "HOLD",
    "reason": "NO_VALIDATED_EDGE_THRESHOLD",
    "historicalThresholdEarned": false,
    "prospectiveThresholdEarned": false,
    "altLineState": "HOLD"
  },
  "audit": {
    "snapshotId": "NFL_2026_W6_PRELOCK_20261017T225656Z",
    "snapshotLocked": true,
    "graded": false,
    "gradeArtifact": null
  },
  "websitePublishAllowed": false
}
```

## Market source types
Use exact semantics:

### `REFERENCE_ONLY`
Schedule/consensus/reference line retained for comparison. Not proof that the user can bet it.

### `PUBLIC_BOOK_CAPTURE`
Timestamped public sportsbook web-board observation. Better than a generic reference, but still not proof of account-level execution in a specific jurisdiction.

### `ACCOUNT_VERIFIED`
Price actually verified in the user's logged-in sportsbook/account context at the relevant time. Only this state may be described as account-executable.

Never silently upgrade source type based on matching numbers.

## Reliability contract
Allowed tiers:
- `A` — final-state/gate verified normal-state projection
- `B` — standard model; final gates pending
- `C` — elevated state/environment uncertainty
- `D` — out-of-distribution state break

Required fields:
- tier
- human-readable reason
- `isBettingConfidence=false`

The UI must render the phrase **Projection reliability — not betting confidence** anywhere the tier is explained.

## Recommendation contract
A recommendation object is required even when nothing is released.

```json
{
  "state": "HOLD",
  "reason": "NO_VALIDATED_EDGE_THRESHOLD",
  "historicalThresholdEarned": false,
  "prospectiveThresholdEarned": false,
  "altLineState": "HOLD"
}
```

Do not infer `RELEASED` from:
- model/market gap size,
- public-book price availability,
- reliability tier A/B,
- a single good prospective week,
- or a historically positive small sample.

## Feature/research registry object
Each league should expose research-family status separately from game projections.

```json
{
  "family": "defensive_coverage",
  "league": "NFL",
  "spreadUse": "PROMOTED_RESEARCH_LAYER",
  "totalUse": "NO_PROMOTION",
  "displayContext": true,
  "note": "Survived frozen walk-forward robustness for spread only."
}
```

Allowed model-use states:
- `PROMOTED_CORE`
- `PROMOTED_RESEARCH_LAYER`
- `CONTEXT_ONLY`
- `PROSPECTIVE_ONLY`
- `NO_PROMOTION`
- `HOLD_UNAVAILABLE`

This lets the Research Hub show useful matchup context without suggesting every displayed metric is a model coefficient.

## Record/audit contract
Keep three audit channels separate:

### Projection accuracy
Examples:
- spread MAE/RMSE/bias
- total MAE/RMSE/bias
- empirical error quantiles

### Historical market comparison
Examples:
- ATS/OU grading by retrospective disagreement bucket
- market benchmark MAE

Label clearly as retrospective research, not released wagering record.

### Prospective locked-snapshot validation
Examples:
- snapshot ID
- lock timestamp
- number of completed games graded
- spread/total error
- market-reference research record
- hard-QB-break vs normal-state split

Never combine prospective and retrospective samples into one unlabeled win-rate number.

## Alternative-line contract
Keep disabled until validation permits activation.

Inactive example:
```json
{
  "state": "HOLD",
  "reason": "BASE_RECOMMENDATION_THRESHOLD_NOT_VALIDATED",
  "baseLine": null,
  "alternativeLine": null,
  "fairProbability": null,
  "fairPrice": null,
  "bookPrice": null
}
```

Future activation requires its own documented validation and price-comparison semantics.

## CFB legacy migration strategy
Do **not** rewrite the mature CFB model pipeline just to match NFL internals.

Instead add an adapter layer that maps the current CFB files:
- `data/config.json`
- `data/projections.csv`
- `data/results.csv`
- `data/research.json`

into the normalized site object in JavaScript at load time or through a generated normalized CFB export.

Recommended staged migration:
1. Build adapter functions against current CFB data with no visual changes.
2. Build equivalent NFL research adapter against development-only exports.
3. Unit/smoke test both adapters with identical UI components.
4. Redesign components against normalized objects.
5. Keep NFL hidden unless `websitePublishAllowed=true` and final approval is given.
6. Merge only after the existing CFB experience passes regression checks.

## Publication guard
The rendering layer must reject or hide NFL data when:
```text
websitePublishAllowed != true
```

During development, a local/dev preview may override visibility only through an explicit developer flag that cannot ship enabled on `main`.

Do not use the presence of an NFL data file as implicit permission to publish it.

## Current NFL research state encoded by this contract
As of the Week-6 prelock build:
- spread architecture: core + defensive coverage + market-independent win Elo + margin rating
- total architecture: core only
- recommendation threshold: none validated
- alternative-line logic: HOLD
- public BetMGM capture: available for 13/13 remaining games
- account-level execution verification: 0/13
- hard-QB-break games: 3/13
- projection reliability: research-only
- website publication: false

These values describe the current research state and are not permanent schema assumptions.
