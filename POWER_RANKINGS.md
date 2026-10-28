# CB Model Projections Power Rankings

## Purpose

The Power Rankings page is a **research-only summary of model state**. It does not replace, modify, blend into, or retroactively alter any frozen CFB or NFL projection.

The rankings answer one narrow question:

> On a neutral field, how many points does the frozen model's team-strength state imply one team is worth relative to league average?

The result is displayed as **CB Points**. Higher is stronger. Both league point scales are centered at zero so `+5.0` means approximately five points stronger than league average on the model-derived power scale, while `-5.0` means approximately five points weaker.

CFB and NFL are generated independently. Their numerical scales must not be compared across leagues.

## CFB methodology

Source architecture: `cfb-rebuild-foundation-v1-shadow`.

The CFB ranking snapshot uses the same validated foundation settings already selected before Week 8:

- alpha: 2.5
- half-life: 56 days
- minimum team appearances: 4
- 2026 structural home-field advantage: preserved from the Week 8 validation artifact
- schedule-adjusted ridge team strengths
- no market, Sagarin, SP+, RefMetrics, prediction-market, injury, weather, or post-cutoff information as model features

The ranking build uses a fixed cutoff of **2026-10-28 12:45:00 UTC / 8:45 AM ET**, after Tuesday’s Week 9 games. Completed games before that cutoff may update the descriptive team-strength snapshot, but those results do **not** change the immutable Week 8 projections that were frozen earlier.

The fitted team-strength coefficients are mean-centered to zero and ranked from highest to lowest.

Expected coverage: **138 FBS teams**.

## NFL methodology

NFL rankings are pinned to the exact pre-Week-7 model source commit:

`0721b59b5f461ad590bd348bd655c5463265856c`

and the frozen snapshot:

`nfl_data/prospective/week7/20261021T114427Z/`

The source architecture is the same frozen spread model used for the Week 7 paired projections:

- efficiency core
- defensive coverage
- win Elo
- margin rating

The ranking extractor first reconstructs the pre-Week-7 rating state with Week 7+ scores blanked. It then fits the frozen model and must reproduce **all 14 frozen Week 7 canonical home-margin projections** to numerical tolerance before any team ranking can publish.

For the October 28 update, efficiency and recursive rating state incorporate all 14 Week 7 finals. Defensive coverage is refreshed from the latest available reports; Dallas and Philadelphia still have Week 6 coverage and are explicitly flagged. Model coefficients and historical training remain unchanged. Input CSVs and source hashes are saved in `data/power-rankings/inputs/nfl-20261027/`.

After that guard passes, the model predicts every ordered neutral-field pairing among the 32 teams (992 ordered matchups). Opposite orientations are symmetrized to remove residual home/away encoding artifacts. A least-squares system then reduces the model's all-pairs matchup surface to a zero-mean team point scale.

Expected coverage: **32 NFL teams**, including bye teams.

This reduction is a research summary of the frozen model; it is not a new predictive coefficient set.

## Market rankings and comparison policy

Market information is a **benchmark/context layer only**.

A national market power ranking is not published unless the timestamped spread graph covers and connects the entire league. The current CFB and NFL market graphs do not satisfy that requirement, so national `Market Rank`, `Market Points`, and team-level `Gap` are intentionally blank and marked **withheld**.

We do not fill those missing national ratings by:

- borrowing an external power rating,
- using postgame lines,
- silently assuming the CB model's home-field advantage is the market's home-field advantage,
- connecting disconnected teams with stale or reconstructed prices,
- or using untimestamped historical information.

Matchup-level spread comparisons remain valid context. Their convention is:

`modelMarketGapHome = marketSpreadHome - modelSpreadHome`

A positive value means the CB model is more favorable to the **home team** than the market line; a negative value means it is more favorable to the **away team**.

October 28 snapshot:

- CFB remaining matchup comparisons: 54
- NFL remaining matchup comparisons: 0 (Week 8 projections and current market pairs pending)

These market values are not canonical model features and are not automatically eligible for grading unless a separate publication-time execution lock says so.

## Integrity gates

`tests/test_power_rankings.py` enforces ten invariants:

1. 138 CFB teams are present.
2. 32 NFL teams are present.
3. Both CB Points scales are zero-mean.
4. Rank order is complete and monotonically consistent with CB Points.
5. Disconnected market graphs force national market ratings to be withheld.
6. Remaining matchup counts are 54 CFB and 0 NFL.
7. Model/market gap arithmetic and side labels use the defined convention exactly.
8. Every ranking artifact explicitly has `canonicalInfluence: false` and `canonicalPromotionAuthorized: false`.
9. The NFL extractor reproduces all 14 frozen Week 7 margins before ranking publication and evaluates all 992 ordered neutral matchups.
10. Snapshot provenance and manifest hashes match the generated artifacts.

The GitHub Actions workflow `.github/workflows/power-rankings-check.yml` validates the committed snapshots on main and pull requests without rewriting frozen data.

## Generated files

- `data/power-rankings/cfb.json`
- `data/power-rankings/cfb.csv`
- `data/power-rankings/nfl.json`
- `data/power-rankings/nfl.csv`
- `data/power-rankings/manifest.json`

The website reads the JSON snapshots from `ratings.html` through `power-rankings.js`.

## Promotion rule

Power rankings are **not a promotion pathway by themselves**. A future ranking-derived feature may become a challenger hypothesis, but it cannot influence the canonical CFB or NFL model without leakage-safe historical testing, walk-forward/out-of-sample validation, prospective frozen-week evidence, and explicit authorization.

## External comparison review — October 28, 2026

Andrew Percival’s [CFB Picker](https://public.tableau.com/app/profile/andrew.percival/viz/CFBPicker/Standings) was reviewed in its public dashboard and Metadata tab. It evaluates prediction systems, while the separate [CFB Metrics Consensus](https://public.tableau.com/app/profile/andrew.percival/viz/CFBMetricsConsensus/Tables) evaluates teams using an ensemble. The dashboard does not permit raw-source exports; no outside dataset or rating has been imported into CB Points.

Useful evaluation practices: compare identical game samples, freeze pregame predictions and line timestamps, report margin MAE and RMSE alongside ATS/straight-up accuracy, and keep closing-line value distinct from outcome accuracy. Compare consensus with its components carefully because they are correlated. These are evaluation criteria, not claims that a new ensemble has been validated or implemented. Injury, referee and weather adjustments are not part of these baseline team ratings.

Movement is prior published rank minus current rank: positive means a climb. The CFB comparison board retains the original frozen Week 9 matchup projections; newly updated descriptive ratings do not retroactively replace those predictions.
