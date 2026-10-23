# CB NFL and FBS power ratings

This adds a descriptive ranking layer to the established projection models. It
neither replaces the models nor changes any frozen forecast, market lock, grade,
coefficient, feature-promotion decision or release gate.

## What is delivered

- `power-rankings.html`: searchable, sortable, responsive league-specific board.
- `data/power-ratings/cfb.json` and `.csv`: all 138 discovered FBS teams.
- `data/power-ratings/nfl.json` and `.csv`: all 32 NFL teams, including bye teams.
- Dated matchup market gaps, separated from national market ratings.
- Immutable dated output snapshots, hashed inputs, exact NFL freeze reproduction,
  preserved compressed CFB source capture, and offline rebuild/test commands.

CFB is explicitly **foundation research shadow**. NFL is **canonical-derived
research**, using the preserved October 21 pre-Week-7 state. NFL ranks therefore
do not incorporate subsequent games, injuries or news. CFB ratings are a newly
observed October 23 state; they are never relabeled as earlier pregame forecasts.

## Calculation choices

### CFB: extract the existing schedule-adjusted strengths

The existing foundation fits completed-game margins to:

`home margin = frozen structural HFA + home strength - away strength`.

Reuse the existing ridge penalty 2.5, 56-day half-life, minimum four appearances
and structural home-field parameter from the validation artifact. Do not retune.
Use all eligible opponents in the established engine, then center the displayed
strengths across the verified FBS membership. Retain FBS teams on bye weeks.
Fail rather than assign an unsupported team a zero rating.

The new capture contains 138 FBS teams and 517 observed completed games before
capture start. Raw source bytes are stored compressed. Completion is observed
at retrieval, not a claim that the source bytes existed at an earlier cutoff.
The established validation artifact records development, holdout and confirmation
results. This ranking transform does not create new predictive evidence.

### NFL: summarize the actual canonical projection function

The existing canonical model uses efficiency, coverage and recursive Elo/margin
features. Refit exactly as in the preserved snapshot using its hashed historical
inputs and established parameters; reproduce all 14 frozen game margins before
exporting any rankings. The current reproduction error is zero.

Evaluate every pair of the 32 teams at neutral venue and equal rest in both home
label orientations. For teams i and j define:

`M[i,j] = (prediction(i,j) - prediction(j,i)) / 2`.

Then `rating[i] = sum_j M[i,j] / N`, including a zero diagonal. This is the
zero-centered least-squares summary of the complete antisymmetric matchup
matrix. Division by N-1 would incorrectly inflate the point scale. The exported
compression residual measures how much matchup-specific information a single
rating discards. It is essentially zero for this frozen model.

This is a neutral team-strength summary; it does not overwrite game forecasts.
It does not promote FTN50 or copy an external model's weights.

### Independent market estimates

Normalize quotes to home spreads, record book/source/observation/kickoff, reject
nonfinite/missing/future/post-kickoff observations and identity conflicts, retain
one latest quote per game/book, then use the median across books per game.
Archived observations accumulate prospectively. A declared 42-day rolling window
is an initial **benchmark design**, not a validated predictive hyperparameter.

Fit `-home spread - HFA = home market strength - away market strength`, with a
zero-sum constraint and equal game weights. Neutral sites receive no HFA. CFB
uses its frozen structural HFA. NFL's market estimator has an explicit 3-point
benchmark assumption; it is not claimed to equal the canonical model's fitted
home effect. This assumption needs sensitivity testing before relying on future
national market gaps.

**Connectivity is mandatory.** A week's isolated matchups cannot identify a
whole-league ranking. Ridge shrinkage or an external-model prior could create a
number for every team but would make it an assumption-driven blended benchmark.
This implementation leaves national market rank/rating/gap null instead.
The initial saved market graph is disconnected in both leagues.

The initial board still offers useful current comparisons: 49 upcoming CFB games
and 13 upcoming NFL games. CFB gaps use the new research rating difference and
structural venue effect. NFL gaps use the existing frozen game forecast versus
the saved current market reference. Each is explicitly dated. These are
matchup gaps, not national power-rating gaps and not certified execution prices.

## Evidence and limitations

- No claim of new out-of-sample improvement, profitability, or calibrated rank
  confidence. Software integrity is different from predictive validation.
- No fabricated historical movement: first snapshot has no rank-change baseline.
- No automatic injury, referee, letdown, travel or motivation point adjustments.
- No invented confidence intervals. Rank uncertainty calibration is future work.
- Missing market connectivity remains a visible data limitation.
- NFL inputs are frozen through Week 6; refreshing the underlying model snapshot
  is separate from rebuilding this board.
- CFB source membership, IDs and names are captured from the conference-grouped
  ESPN response. Schedule aggregation fails if any team request fails after retries.
- National ranks in different leagues are not comparable to one another.

## Research reviewed and decisions

| Primary/reference resource | Decision |
|---|---|
| https://thepowerrank.com/the-top-10-things-to-know-about-the-power-ranks-methods/ | Schedule-adjusted point ratings fit the existing CFB architecture; do not import its performance claims. |
| https://thepowerrank.com/guide-cfb-rankings/ | Separate predictive models from polls; external benchmarks only. |
| https://www.teamrankings.com/about/how-we-rank/ | Joint opponent/location-adjusted ratings; proprietary recipe not copied. |
| https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification | Ridge regularization background; keep existing validated penalty. |
| https://bradleyterry2.r-forge.r-project.org/ | Pairwise probability modeling reference; not substituted for point margins. |
| https://www.nfeloapp.com/about/ | Elo/advanced-metric research reference; retain our existing NFL coefficients. |
| https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/ | Market blending remains unapproved; independent comparison only. |
| https://github.com/kyleaclark/nfl-power-rankings | Inspected fixed weighted composite and Python 2 dependencies; not adopted. |
| https://www.espn.com/college-football/fpi | Benchmark only; live table could not be reliably retrieved in prior review. |
| https://powerrankingsguru.com/nfl/power-rankings | External model/UI comparison only. |
| https://apnews.com/hub/ap-top-25-college-football-poll | Media comparison, never sportsbook-market evidence. |
| https://www.bettoredge.com/post/letdown-and-sandwich-spots-betting | Prospective hypotheses, no automatic points. |
| https://oddsindex.com/guides/situational-betting-spots | Schedule/context hypotheses, unvalidated incremental value. |
| https://escapesf.net/college-football-covers-d2mg.html | Inaccessible/unverified; not used. |
| https://www.ncaa.com/news/football/article/2025-01-22/college-football-rankings-every-poll-explained-how-they-work | Verification wall; not used as inspected evidence. |
| https://masseyratings.com/theory/massey97.pdf | Fetch returned 403; no claim to have reviewed the paper. |

A broad search does not establish a universally best method. The implementation
choice is driven by our existing validated architecture and exact reproduction,
with alternative methods left for controlled challenger tests.

## Reproduce

Requirements: Python 3, numpy; pandas also needed for NFL source export.
From this repository:

```bash
OPENBLAS_NUM_THREADS=1 python scripts/build_power_ratings.py
python -m unittest discover -s tests -p 'test_power_ratings.py' -v
node --check power-rankings.js
```

Refresh CFB inputs only when producing a new current ranking snapshot:

```bash
python scripts/capture_cfb_power_inputs.py
OPENBLAS_NUM_THREADS=1 python scripts/build_power_ratings.py
```

For the NFL matrix, use the same repository at pinned source commit
`0721b59b5f461ad590bd348bd655c4963265856c` in a separate checkout. From that source
checkout run the absolute path to `scripts/export_nfl_power_matrix.py` in this
branch, passing `--output` with the absolute path to
`data/power-ratings/nfl-model-input.json` in this branch. The exporter checks
historical/snapshot hashes and reproduces frozen margins before saving.

The GitHub workflow checks the complete offline build and uploads a review
artifact. It does not publish, mutate model freezes, or fetch new pregame inputs.

## Verification performed

Ten targeted tests cover point-scale recovery, nontransitive matchup residuals,
invalid matrices, disconnected markets, spread signs, neutral sites, invalid or
late quotes, book deduplication, event identity conflicts, full-team coverage,
zero centering and exact NFL frozen-margin reproduction. JavaScript syntax is
checked separately. Browser screenshot verification was attempted locally but
blocked by an unavailable browser binary and failed browser download; no visual
QA success is claimed.
