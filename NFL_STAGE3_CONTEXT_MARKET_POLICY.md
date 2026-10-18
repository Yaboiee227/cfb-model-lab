# NFL Stage 3 — Context + Market Execution Policy

**Stage:** 3 — Context + Market Execution  
**Branch:** `nfl-model-development`  
**Canonical model snapshot policy:** immutable after freeze  
**Recommendation state:** HOLD until Stage 4 is prospectively earned

## Purpose

Stage 3 governs information that becomes important after the canonical spread/total prediction is frozen: starting-quarterback state, injuries/inactives, weather, roof status, schedule/travel context, and sportsbook prices. It is an execution and uncertainty layer, not a license to hand-edit the model.

No Stage 3 observation may retroactively change the frozen Week 6 canonical projection. A future learned coefficient may enter a later model version only after separate timestamp-safe historical validation and prospective review.

## 1. Personnel and quarterback policy

### Source hierarchy

1. Official NFL injury report / transaction report.
2. Official team announcement, depth chart, transaction or coach confirmation.
3. NFL Network or equivalent high-quality reporting when official active/inactive status is not yet posted.
4. Secondary aggregators only as QA, never as the sole hard-gate source when an official source exists.

### State classes

- `NO_QB_BREAK`: expected starter matches the modeled state.
- `QB_RETURN_PENDING`: starter expected back but game-day active status is unresolved.
- `HARD_QB_BREAK`: confirmed or strongly established starter change from the modeled baseline.
- `UNKNOWN_QB_STATE`: unresolved enough that release cannot be trusted.

### Operational rule

- QB/personnel news may change **reliability and release state**.
- QB/personnel news may not add/subtract manual points from the frozen projection.
- Existing replacement-QB scenario diagnostics are research stress tests only and must retain `operational_point_adjustment = 0`.
- Final inactives are a separate game-day gate even when the Friday/Saturday game-status report is complete.

## 2. Weather and roof policy

### Primary sources

- NWS point/hourly forecasts for U.S. outdoor venues.
- Met Office or equivalent official national forecast service for international venues.
- Official stadium/team roof announcement for retractable roofs.
- Venue metadata for fixed/covered roofs.

### Operational rule

- Weather/roof information changes uncertainty/release state unless a separately validated coefficient exists.
- No discretionary wind/rain/temperature points are added to spreads or totals.
- Fixed/covered venues resolve the outdoor-weather gate unless unusual venue conditions are reported.
- Retractable-roof games remain open until the official roof/window decision is known.
- Outdoor/elevated games receive a near-kickoff refresh even if an earlier forecast was benign.

### Game-day target timing

- T-2h: weather/roof refresh.
- Refresh again if the roof or forecast remains materially unresolved.

## 3. Rest, travel and venue context

- Rest differential and neutral-site state already belong to the frozen core architecture where validated.
- Travel distance, time-zone change, surface, divisional status, coaching narratives and similar static context may be tracked descriptively.
- They may not receive a manual point adjustment unless they earn promotion through Stage 1/2-style validation in a future version.

## 4. Market observation definitions

### Public-board price

A price visible on a sportsbook/public web board at a recorded timestamp. It is a **benchmark observation**, not proof that the user could place that wager.

### Executable price

A price observed in the user's available account/market at a known decision timestamp and not blocked by location, account limits, suspension or stale display. Only an explicitly verified executable price may support future execution/CLV claims.

### Opening line

For prospective tracking, the opening line is the earliest timestamped line captured from the defined source set after the market becomes broadly available. A historical schedule/reference line is not automatically treated as a true opener.

### Current line

The most recent timestamped observation available at the time of analysis.

### Closing line

For future prospective CLV research, use one consistently defined close convention. Preferred convention:

- final verified source observation before kickoff, ideally within five minutes of kickoff; or
- a provider-defined closing number if its methodology is documented and used consistently.

Do not mix close definitions across games inside the same CLV statistic.

## 5. Line-shopping policy

Line shopping is allowed only as an execution layer and must preserve exact timestamp/source metadata.

### Spread

- Prefer the best **line** available to the intended side before comparing juice.
- At the same spread number, prefer the better price.
- Do not describe a worse line with cheaper juice as automatically superior without converting the tradeoff explicitly.

### Total

- For an Over, prefer the lower total; at the same total, prefer the better price.
- For an Under, prefer the higher total; at the same total, prefer the better price.

### Moneyline

- Prefer the highest payout / least-negative price for the intended team from an eligible executable source.

### Source eligibility

A line may be used in a future best-price execution claim only when the source is actually available to the user and the price is verified executable. Public web boards can be displayed as market references but must stay labeled public/benchmark.

## 6. Market capture timing

Minimum prospective observation schedule around the frozen model:

- Initial/frozen comparison capture: as soon as the model snapshot is frozen.
- T-60m: fresh public-board capture for every game.
- T-15m: optional account-level executable-price observation when practical.
- Pre-kick close: final market capture for research if infrastructure permits.

Every capture must retain source, timestamp, game ID, spread/total/moneyline where available, and displayed price/odds.

## 7. CLV policy

Public-board movement is **not CLV**.

A future CLV observation requires:

1. a verified decision-time executable price,
2. a consistently defined closing price,
3. the same market/side and normalized line/price representation,
4. immutable timestamps.

Until those conditions are met, report only `market movement`, `model-market disagreement`, or `public-board change`.

## 8. Release blockers

The Stage 3 release layer can block a game for any of the following:

- `HARD_QB_STATE_BREAK`
- `UNKNOWN_QB_STATE`
- `FINAL_INACTIVES_PENDING`
- `FINAL_WEATHER_OR_ROOF_PENDING`
- `PUBLIC_BOOK_PRICE_NOT_CAPTURED`
- `USER_ACCOUNT_EXECUTION_NOT_VERIFIED` (required only for any claim about executable price/CLV)
- `NO_VALIDATED_EDGE_THRESHOLD` (carried into Stage 4)

A blocker may reduce reliability or keep a game on HOLD. It does not authorize a manual numeric adjustment.

## 9. Week 6 known state as of Saturday night

- Official Week 6 injury/game-status reporting is available for the Sunday slate.
- Hard QB breaks include Baltimore (Lamar Jackson out), Philadelphia (Jalen Hurts out; Tanner McKee starter) and Tampa Bay (Baker Mayfield out; Jalon Daniels starter/expected starter state).
- Chicago's Caleb Williams is reported expected to start but remains a game-day active-status confirmation gate.
- Indianapolis roof/window status remains TBD on the official Colts gameday page.
- Final game-day inactives remain unresolved for the Sunday/Monday games until their normal pregame release windows.
- Timestamped public BetMGM web-board observations exist for all 13 remaining Week 6 games, but account-level execution has not been verified.

## 10. Stage 3 completion standard

The **Stage 3 architecture/policy** is complete when:

- source hierarchy is explicit,
- QB/personnel state handling is deterministic,
- weather/roof handling is deterministic,
- market timestamps and open/current/close definitions are explicit,
- line-shopping rules are explicit,
- public-board vs executable-price distinction is explicit,
- game-day check timing is explicit,
- immutable canonical projections are protected.

Individual games can still carry live unresolved gates. Those live gates do not make the Stage 3 system incomplete; they mean that game's release state remains HOLD until the observation arrives.

## Stage 3 handoff

> Context and market execution are a timestamped uncertainty/release layer around an immutable canonical model. Personnel, QB, weather, roof and market observations may change reliability or HOLD status but cannot hand-edit the Week 6 spread/total. Public sportsbook boards are benchmark observations. Executable-price and CLV claims require account-level verification plus a consistent closing convention. Opening/current/closing definitions and line-shopping rules are now fixed. Proceed to Stage 4 to build confidence/release calibration from prospective frozen outcomes without turning historical model-market disagreement into an assumed edge.
