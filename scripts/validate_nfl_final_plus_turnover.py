#!/usr/bin/env python3
"""Nested robustness test: final NFL spread architecture + turnover/regression.

Reference is the canonical final spread architecture:
core + defensive coverage + market-independent win Elo + margin rating.

The only added family is the pre-existing `full_turnover_regression` family.
Its shrinkage and augmented ridge lambda are selected from 2022 only, then
frozen for outer 2023-2025 evaluation. This is research-only and cannot rewrite
the immutable Week 6 canonical or FTN shadow snapshots.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix  # noqa: F401
import validate_nfl_coverage_v1 as cov
import validate_nfl_turnover_regression_v1 as tov
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as final_arch

OUT = Path("nfl_data/validation/final_plus_turnover.json")
YEARS = [2023, 2024, 2025]
FAMILY = "full_turnover_regression"
FEATURE_K_GRID = [1.0, 2.0, 4.0, 8.0, 16.0]
LAMBDA_GRID = [10.0, 30.0, 100.0, 300.0]
DRAWS = 10000
SEED = 20261017


def matrix(rows, team_k, cov_k, turnover_k=None):
    names = None
    data = []
    for r in rows:
        bn, bv = base.spread_features(r, team_k)
        cn, cv = cov.extras(r, "spread", "coverage", cov_k)
        rn = ["rating_win_elo_diff", "rating_margin_rating_diff"]
        rv = [float(r["rating_win_elo_diff"]), float(r["rating_margin_rating_diff"])]
        n = bn + cn + rn
        v = bv + cv + rv
        if turnover_k is not None:
            tn, tv = tov.features(r, "spread", FAMILY, turnover_k)
            n += tn
            v += tv
        if names is None:
            names = n
        data.append([np.nan if x is None else float(x) for x in v])
    return names, np.asarray(data, dtype=float)


def fit(rows, team_k, cov_k, lam, turnover_k=None):
    names, x = matrix(rows, team_k, cov_k, turnover_k)
    prep = base.fit_preprocessor(x)
    model = base.ridge_fit(base.transform(x, prep), base.target_array(rows, "spread"), lam)
    return names, prep, model


def predict(rows, team_k, cov_k, fitobj, turnover_k=None):
    names, prep, model = fitobj
    _, x = matrix(rows, team_k, cov_k, turnover_k)
    p = np.asarray(base.predict(model, base.transform(x, prep)), dtype=float)
    coefs = {n: float(v) for n, v in zip(names, model[1])}
    return p, coefs


def abs_error(rows, preds):
    return np.abs(base.target_array(rows, "spread") - np.asarray(preds, dtype=float))


def bootstrap(improvements):
    d = np.asarray(improvements, dtype=float)
    rng = np.random.default_rng(SEED)
    n = len(d)
    draws = np.empty(DRAWS)
    for i in range(DRAWS):
        draws[i] = float(np.mean(d[rng.integers(0, n, size=n)]))
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "mean_improvement": round(float(np.mean(d)), 5),
        "bootstrap_95_ci": [round(float(lo), 5), round(float(hi), 5)],
        "probability_gt_0": round(float(np.mean(draws > 0)), 4),
        "draws": DRAWS,
        "seed": SEED,
    }


def select_candidate_2022(rows22, team_k, cov_k):
    train, valid = base.inner_split(rows22)
    y = base.target_array(valid, "spread")
    candidates = []
    for tk in FEATURE_K_GRID:
        for lam in LAMBDA_GRID:
            fo = fit(train, team_k, cov_k, lam, tk)
            p, _ = predict(valid, team_k, cov_k, fo, tk)
            candidates.append({
                "turnover_feature_k": tk,
                "lambda": lam,
                "mae": base.mae(y, p),
                "rmse": base.rmse(y, p),
                "validation_games": len(valid),
            })
    candidates.sort(key=lambda x: (x["mae"], x["rmse"], x["lambda"], x["turnover_feature_k"]))
    return candidates[0], candidates[:8]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    base_rows = base.load_rows()
    ngs_idx, ngs_leak, _ = ngs.load_index()
    cov_idx, cov_leak, _ = cov.loadidx(cov.COV, "cov")
    turnover_idx, turnover_leak, turnover_rows = tov.loadidx()
    if ngs_leak + cov_leak + turnover_leak:
        raise RuntimeError(
            f"source leakage ngs={ngs_leak} coverage={cov_leak} turnover={turnover_leak}"
        )

    coverage_rows = cov.attach(base_rows, cov_idx, ngs_idx)
    rows = tov.attach(coverage_rows, turnover_idx)

    # Freeze the exact canonical coverage shrinkage using the established 2022-only selection.
    cov22 = [r for r in coverage_rows if r["season"] == 2022]
    coverage_params, _ = cov.select(cov22, "spread", "coverage")

    games = rat.fetch_games()
    rating_map = rat.rating_maps(
        games,
        final_arch.RATING["elo_k"],
        final_arch.RATING["elo_hfa"],
        final_arch.RATING["offseason_regression"],
        final_arch.RATING["margin_k"],
        final_arch.RATING["margin_hfa"],
    )
    rated = rat.attach(rows, rating_map)
    rows22 = [r for r in rated if r["season"] == 2022]

    selected, top = select_candidate_2022(
        rows22, coverage_params["team_k"], coverage_params["feature_k"]
    )

    folds = {}
    ref_all = []
    cand_all = []
    turnover_coefficients = {}
    for year in YEARS:
        train = [r for r in rated if r["season"] < year]
        test = [r for r in rated if r["season"] == year]

        ref_fit = fit(
            train,
            coverage_params["team_k"],
            coverage_params["feature_k"],
            final_arch.RATING["lambda"],
            None,
        )
        ref_pred, _ = predict(
            test,
            coverage_params["team_k"],
            coverage_params["feature_k"],
            ref_fit,
            None,
        )

        cand_fit = fit(
            train,
            coverage_params["team_k"],
            coverage_params["feature_k"],
            selected["lambda"],
            selected["turnover_feature_k"],
        )
        cand_pred, coef = predict(
            test,
            coverage_params["team_k"],
            coverage_params["feature_k"],
            cand_fit,
            selected["turnover_feature_k"],
        )

        re = abs_error(test, ref_pred)
        ce = abs_error(test, cand_pred)
        ref_all.extend(re.tolist())
        cand_all.extend(ce.tolist())
        turnover_coefficients[str(year)] = {
            k: round(v, 6) for k, v in coef.items() if k.startswith("to_")
        }
        folds[str(year)] = {
            "n": len(test),
            "reference_final_architecture_mae": round(float(np.mean(re)), 4),
            "candidate_mae": round(float(np.mean(ce)), 4),
            "candidate_minus_reference_mae": round(float(np.mean(ce) - np.mean(re)), 4),
        }

    ref = np.asarray(ref_all)
    cand = np.asarray(cand_all)
    boot = bootstrap(ref - cand)
    seasons_improved = sum(
        folds[str(y)]["candidate_minus_reference_mae"] < 0 for y in YEARS
    )
    promoted = bool(
        np.mean(cand) < np.mean(ref)
        and seasons_improved >= 2
        and boot["bootstrap_95_ci"][0] > 0
    )

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "design": "Nested incremental test of the pre-existing full turnover/regression family on top of the canonical final spread architecture. Candidate shrinkage/lambda selected from 2022 only; outer evaluation 2023-2025.",
        "family": FAMILY,
        "reference_architecture": "core + defensive coverage + market-independent win Elo + margin rating",
        "reference_rating_params": final_arch.RATING,
        "coverage_params": coverage_params,
        "source_turnover_rows": turnover_rows,
        "source_leakage_rows": turnover_leak,
        "selected_candidate_params_2022_only": selected,
        "top_2022_candidates": top,
        "folds": folds,
        "aggregate": {
            "n": len(cand),
            "reference_mae": round(float(np.mean(ref)), 4),
            "candidate_mae": round(float(np.mean(cand)), 4),
            "candidate_minus_reference_mae": round(float(np.mean(cand) - np.mean(ref)), 4),
            "seasons_improved": seasons_improved,
            "paired_bootstrap_reference_minus_candidate": boot,
        },
        "turnover_feature_coefficients_by_test_season": turnover_coefficients,
        "promotion_rule": "Candidate must improve aggregate MAE, improve at least 2 of 3 outer seasons, and have paired-bootstrap 95% CI for reference-minus-candidate entirely above zero.",
        "historical_promotion_earned": promoted,
        "week6_canonical_snapshot_may_be_rewritten": False,
        "week6_ftn_shadow_snapshot_may_be_rewritten": False,
        "production_promotion_allowed": False,
        "release_state": "ROBUST_SHADOW_CANDIDATE_ELIGIBLE" if promoted else "HOLD_NO_INCREMENTAL_PROMOTION",
        "website_publish_allowed": False,
        "recommendation_release_allowed": False,
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "selected": selected,
        "aggregate": result["aggregate"],
        "historical_promotion_earned": promoted,
        "release_state": result["release_state"],
    }, indent=2))


if __name__ == "__main__":
    main()
