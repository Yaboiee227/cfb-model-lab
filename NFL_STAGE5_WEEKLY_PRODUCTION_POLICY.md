# NFL Stage 5 — Weekly Production / Audit / Tracking Policy

**Stage:** 5 — Weekly Production / Audit / Tracking  
**Current model state:** research/HOLD  
**Goal:** make every weekly forecast reproducible, immutable, gradeable, and safe to feed into future Stage 4 calibration.

## 1. Weekly evidence chain

Every NFL week follows this order:

1. **Build source data** using the canonical NFL ingestion pipelines.
2. **Run model QA** and stop on missing/corrupt critical inputs.
3. **Generate canonical projections** for the eligible slate.
4. **Freeze an immutable prospective snapshot** with a unique snapshot ID and UTC timestamp.
5. **Freeze any challenger/shadow snapshot** with an explicit parent canonical snapshot ID.
6. **Capture context**: QB/personnel, injuries, weather/roof, rest/static context.
7. **Capture market observations** with source and timestamp; preserve public-board vs executable distinction.
8. **Run game-day gates** without altering the frozen canonical numeric projection.
9. **Grade completed games** into new timestamped postgame artifacts.
10. **Grade challengers on the same games** as the canonical model.
11. **Rebuild the multi-week prospective registry**, deduplicating repeated grader runs.
12. **Refresh validation/site research exports** from the verified artifacts.

The sequence may be rerun when new context or completed results arrive, but the frozen prediction snapshots themselves are not rewritten.

## 2. Snapshot contract

Each canonical weekly snapshot must contain or resolve to:

- league, season and week,
- unique snapshot ID,
- created/frozen timestamp,
- model architecture/version,
- game ID, away/home teams and kickoff,
- canonical home margin / site-facing spread,
- model total,
- projected score derivatives,
- validation/reliability metadata available at freeze,
- schedule/market benchmark fields available at freeze,
- release state,
- website/recommendation permissions.

### Immutability

- A frozen snapshot is append-only evidence.
- Post-freeze context belongs in separate artifacts.
- Postgame results belong in separate grading artifacts.
- A corrected model run requires a new snapshot/version and a documented reason; it may not overwrite the original evidence.

## 3. Challenger contract

A challenger/shadow model must:

- identify its parent canonical snapshot,
- cover the same game IDs for head-to-head evaluation,
- be frozen before outcomes are known,
- remain explicitly non-canonical until promotion review,
- never replace the canonical model based on a single week.

Current Week 6 challenger: FTN50.

## 4. Market/context contract

- Every market capture retains book/source, timestamp, line and displayed price when available.
- Public-board data remain benchmark-only unless account execution is explicitly verified.
- Context refreshes may update release/reliability fields, not canonical model points.
- Final inactives, weather/roof and market observations are timestamped game-day evidence.

## 5. Result ingestion and grading

- Results may enter the system only after a game has a completed final score from the defined schedule/results source.
- A grader may be rerun as additional games complete.
- Every rerun creates a new timestamped grade artifact.
- Graders may not modify the original prediction or market snapshot.
- Pending games remain pending; missing results must not be guessed or silently filled.
- ROI grading is disabled when the recorded line was not verified executable.

## 6. Registry and duplicate protection

The prospective registry is the canonical multi-week evidence table.

For each frozen snapshot:

- repeated grade artifacts are grouped by snapshot ID,
- the canonical grade is the artifact with the greatest number of completed games, then newest timestamp,
- completed-game metadata must equal the number of grade rows,
- a `(snapshot_id, game_id)` pair may appear only once in the canonical registry,
- repeated grader runs therefore do not double-count games.

The registry may calculate descriptive model-market buckets, but automatic threshold promotion remains prohibited.

## 7. Failure behavior

The pipeline fails closed.

- Missing critical model input -> do not freeze a new canonical snapshot.
- Snapshot/capture game-set mismatch -> audit failure.
- Snapshot-ID mismatch -> audit failure.
- Missing result source -> leave game pending or fail the grading job; never infer a score.
- Missing final context -> retain HOLD/reliability blocker.
- Missing executable price -> prohibit ROI/CLV/execution claims.
- Failed website/export validation -> keep prior verified research artifact; do not publish a partially generated replacement.

Stale data must never be silently represented as current. Any intentionally retained prior observation must carry its original timestamp.

## 8. Weekly QA minimums

Before a weekly snapshot is accepted:

- expected game IDs are unique,
- league/season/week are correct,
- canonical model fields are finite for every included game,
- snapshot ID and timestamp are present,
- model version/architecture is identified,
- market fields are labeled benchmark vs executable,
- release permissions are explicit,
- no CFB rows/data paths are mixed into NFL artifacts.

Before a weekly grade is accepted:

- grader points to the exact frozen snapshot,
- completed games have final scores,
- pending games are preserved,
- market benchmark is the frozen/timestamped comparison source,
- canonical/shadow comparison uses the same game IDs,
- recommendation/ROI/CLV permissions have not been silently promoted.

## 9. Multi-week model health

After every grading refresh, rebuild the registry and track:

- prospective spread MAE/bias,
- prospective total MAE/bias,
- market-benchmark directional records,
- hard-QB and weather splits,
- executable-price-verified subset,
- canonical vs challenger head-to-head performance,
- model-market disagreement buckets,
- completed games and distinct frozen weeks,
- Stage 4 milestone eligibility.

If prospective MAE materially deteriorates versus historical OOS after enough observations accumulate, raise a model-health alert; do not automatically retune midstream.

## 10. Website/export contract

The website is downstream of Stage 5 evidence.

- Website/export scripts must read verified frozen/context artifacts; they are not allowed to become a second modeling engine.
- `website_publish_allowed` and recommendation permissions must be enforced rather than inferred from visual styling.
- Research projections may be prepared for the NFL preview while betting-signal release remains false.
- Production CFB data/site remains protected until an explicit integration decision.

## 11. Week 6 state

Week 6 is the first canonical prospective sample under this governance model.

- Canonical snapshot: frozen and immutable.
- FTN50 shadow: frozen and linked to canonical.
- Context/market layers: captured and game-day refresh schedule defined.
- Canonical grader: can rerun as games finish without rewriting the snapshot.
- FTN50 grader: same-game head-to-head comparison.
- Prospective registry: deduplication and milestone logic active.
- Completed prospective games at the current checkpoint: zero; this is expected before the Sunday slate.

## Stage 5 completion standard

Stage 5 infrastructure is complete when the freeze, context, market, grade, challenger and registry chain is present and CI verifies the contracts above. Weekly operation remains ongoing by definition; completion of the infrastructure does not mean the future prospective sample has already accumulated.

## Stage 5 handoff

> Weekly production infrastructure is considered complete once CI proves the immutable snapshot, same-game challenger, timestamped market/context, postgame grading and deduplicated registry contracts. Continue running those workflows as games complete. Proceed to Stage 6 website integration using the verified research exports and strict Stage 4 release permissions; the site may present research projections without inventing betting recommendations.
