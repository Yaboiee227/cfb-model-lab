# NFL Week 6 failure analysis and Week 7 paired test

Prepared October 21, 2026. Research only. Canonical V1 unchanged. No feature promoted.

## Verified Week 6 record

All 13 published games remain in the official denominator: **3–10 ATS, 6–6–1 totals, 7–6 straight up**. Every grade was recomputed from the saved projections, market references and final scores and matched the official file. Thursday's game was absent from the original published sample; it is not added retrospectively.

The main-branch results and published projections were copied into the analysis inputs with provenance. Existing development-branch freezes, results, code and historical files were checked against a SHA-256 preservation manifest. No legacy tracked file was changed. The shared CFB system and website were not altered.

| Week 6 measure | Canonical V1 | Frozen FTN50 | Saved market benchmark |
|---|---:|---:|---:|
| Margin MAE | 8.045 | 8.458 | 6.500 |
| Margin RMSE | 8.627 | 9.086 | 7.559 |
| ATS | 3–10 | 3–10 | Not applicable |
| Straight up | 7–6 | 6–7 | Not evaluated here |
| Total MAE | 11.035 | Same canonical totals | 10.423 |

The FTN blend worsened margin MAE by 0.413 points and changed the Chicago–Atlanta winner in the wrong direction. This prospective observation does not erase its earlier historical results. It also provides no justification for promotion.

The market is a saved public Action Network reference observed October 18 at 11:55:09 UTC. It was not an execution-verified wager or consistently near-kickoff quote. No realized ROI, closing-line value or moneyline profitability is inferred.

## What failed, and what is repeatable

1. **Persistent benchmark gap:** across each of 2023, 2024 and 2025, canonical spread and total MAE exceeded the corresponding historical market benchmark. This persists in Week 6. Historical reference lines may be closing lines; they are not timing-equivalent to every research freeze, so this is a benchmark gap rather than proof of a tradable deficiency of a specified size.
2. **Personnel adaptation remains unresolved:** all three pre-identified hard-QB-break games lost ATS. But the other ten still went 3–7, so QB disruption cannot explain the entire failure. These flags were recovered from saved pregame artifacts, not newly reconstructed after the losses. Arbitrary replacement-point penalties remain prohibited.
3. **Directional decisions exceeded demonstrated confidence:** Philadelphia's model–market difference was only 0.121 points and Indianapolis's 0.605. Both lost ATS. The six games with differences of at least three points went 1–5. Neither dropping small edges nor choosing only large edges is validated by this week. All remain in the record.
4. **Home-side concentration was a Week 6 problem, not a proven universal bias:** ten home ATS picks went 2–8; canonical home-margin bias was +4.099 points. Historical signed bias was −0.631, +0.515 and +0.079 across the three seasons. A permanent home penalty is not supported.
5. **Totals vary narrowly, but mechanically widening them is not justified:** Week 6 prediction standard deviation was 2.409 points. Conditional means should vary less than realized outcomes; the difference alone is not evidence of miscalibration. A training-only affine recalibration actually selected slopes below one, not expansion. Historical total underprediction repeats, but simple bias correction did not improve held-out MAE.
6. **Operational completeness and predictive validity are separate:** the saved records still contained unresolved final-inactive and execution gates. A prior 100% input-coverage label cannot certify that those gates were cleared or that the projections had strong betting accuracy.

## Challenger build and testing

The experiment specification was written before running the new candidate evaluations. Week 6 results were used only for diagnosis, never fitting. The 2023 OOS residuals initialize the 2024 test; 2023–24 residuals initialize 2025. Preprocessing/fitting uses earlier seasons only. The same 544 games are evaluated for each candidate. Primary screening uses paired absolute-error differences, improvement in both seasons and season-week cluster bootstrap intervals with Bonferroni adjustment across three candidates.

| Challenger | Canonical MAE | Challenger MAE | Improvement interval | Decision |
|---|---:|---:|---:|---|
| S_BIAS: previous-OOS median margin residual | 10.133 | 10.107 | −0.039 to +0.088 | Inconclusive |
| T_BIAS: previous-OOS median total residual | 10.497 | 10.591 | −0.187 to −0.004 | Failed |
| T_SLOPE: prior-OOS affine total calibration, fixed ridge toward slope 1 | 10.497 | 10.446 | −0.090 to +0.191 | Inconclusive |

Positive improvement means lower challenger MAE. None passes. These seasons were previously used for architecture research, so this is **reused OOS development evidence**, not a new untouched confirmation set. Historical week cutoffs pass; complete historical source-publication/revision archives are not present. Do not describe that limitation as resolved by a week-number check.

The existing FTN50 816-game experiment was also rerun without overwriting its old outputs. It reproduced canonical MAE 10.2564 and FTN50 MAE 10.2016, improvement in all three seasons, and the original paired game-bootstrap interval [0.00985, 0.10082]. This replication is not new independent evidence; its original interval is not the cluster/multiplicity-adjusted screen used above. Week 7 retains FTN50 only as the existing shadow comparator.

**QB_REPLACEMENT_V2** is specified separately: use prior player dropback EPA with partial pooling, incumbent-to-expected-replacement difference and expected snap-share uncertainty. Require timestamped expected-starter evidence before kickoff. The existing audit identifies week-scoped depth proxies in 2022–24, exact depth timestamps in 2025–26, and missing injury `date_modified` in 2025–26. That mismatch prevents a claim of fully audited historical replacement-state coverage. Actual game starters must not be substituted as pregame knowledge. No numeric QB coefficient was fitted or applied in this pass.

## Resource disposition

The current `MODEL_SOURCES.md` and existing `docs/NFL_SOURCE_REGISTRY.md` govern this work. The broader registry is copied into the analysis inputs.

- nflverse/nflfastR PBP, schedule/results, PFR coverage and FTN charting support the existing model replay and prospective feature capture. Current source bytes are timestamped and hashed; derived Week 7 feature matrices are retained.
- Official NFL/team reports provide contextual availability evidence. Initial Patriots–Bears and Eagles context is captured separately, without numeric adjustments or claims of final active confirmation.
- NGS, red-zone/turnover, trench, drive/pace, special-teams, penalty, travel and injury-burden additions retain their existing unpromoted status. This analysis does not silently reopen previously failed features.
- nfelo, Sagarin, FTN/DVOA, Action, Covers, sportsbooks and prediction markets remain benchmark/context or market sources. No external rating or price enters a new canonical coefficient. Uncaptured Week 7 benchmarks remain missing.
- SICScore, PFF/SIS, PFN, RBSDM, SumerSports, NFL Savant, RefMetrics and news sources remain constrained by their documented research/context roles and historical timestamp/access requirements. No unsupported proprietary values or retrospective assignments were invented.
- AI tools, agent frameworks, workflow libraries and interface resources are infrastructure, not predictive variables.

## Week 7 prospective freeze

Snapshot: `nfl_data/prospective/week7/20261021T114427Z/`.

All **14 games** have paired Canonical V1 and FTN50 predictions frozen at **October 21, 7:44:27 AM Eastern**, before the first game. Training remains 2022–25; current statistical features use only 2026 Weeks 1–6. Canonical architecture, regularization, FTN candidate specification and the fixed 50/50 weight are unchanged. FTN50 totals remain identical to canonical totals. No failed new challenger was substituted.

First game: New England at Chicago, Thursday October 22, 8:15 PM Eastern. Initial canonical Chicago margin +1.278 and total 49.149; FTN50 Chicago margin +0.891. These are research forecasts, not released recommendations.

Separate per-game records identify kickoff, approximately T−90 inactive review and the T−30-to-kickoff market-lock window. Thursday's times are 6:45 PM and 7:45–8:15 PM Eastern respectively. Lock capture must finish before kickoff, with a source, actual observation and capture timestamps, line and price where available. The current snapshot does not claim any publication-time lock is already complete.

All games remain HOLD. Final personnel checks, weather/roof capture, executable or clearly labeled benchmark markets and remaining independent benchmark capture are outstanding. This pass is a statistical early-week freeze, not a complete final-window release review. New context cannot overwrite it. If a later prospective prediction version is authorized, create a new separately timestamped snapshot and predeclare which version is primary before its results.

## Reproduction and grading

Run from the research checkout:

```bash
python scripts/analyze_nfl_week6_failure.py
python -m unittest discover -s tests -p test_nfl_research_integrity.py -v
```

The prospective builder accepts a source cache with verified SHA-256 manifest; it never writes Week 6 files. Its inputs and output hashes are included in the Week 7 snapshot. Raw downloaded bytes remain a local cache; persistent derived feature inputs permit prediction inspection. A fresh vendor download is not assumed byte-identical to this capture.

`grade_nfl_paired_snapshot.py` verifies the frozen file hashes, retains all games, accepts sourced final results and optionally timestamp-valid market locks, and writes a new grade artifact. Without a qualifying market lock it records prediction errors/SU and leaves ATS/totals grades unavailable. It rejects late or stale locks. It does not reconstruct prices. This runner is implemented and tested; no new scheduled background execution is claimed.

Promotion remains blocked pending independent historical validation, multiple frozen prospective weeks and explicit user approval. Poor results remain visible.
