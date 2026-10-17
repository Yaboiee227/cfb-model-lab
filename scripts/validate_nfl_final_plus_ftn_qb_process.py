#!/usr/bin/env python3
"""Nested robustness test: final NFL spread architecture + FTN QB-process layer.

Reference is the current final spread architecture:
core + defensive coverage + win Elo + margin rating.

The only new family is FTN QB-process charting. Its shrinkage and the augmented
ridge lambda are selected from 2022 only, then frozen for 2023-2025. This is a
research-only shadow test and cannot rewrite the frozen Week 6 snapshot.
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
import validate_nfl_ngs_team_v1_aliasfix  # noqa: F401 - installs canonical aliases
import validate_nfl_coverage_v1 as cov
import validate_nfl_ftn_charting_robustness as ftn
import validate_nfl_rating_system_robustness as rat

OUT = Path("nfl_data/validation/final_plus_ftn_qb_process.json")
YEARS = [2023, 2024, 2025]
FEATURE_K_GRID = [1.0, 2.0, 4.0, 8.0, 16.0]
LAMBDA_GRID = [10.0, 30.0, 100.0, 300.0]
DRAWS = 10000
SEED = 20261017

# Canonical frozen final-architecture rating dynamics from
# validate_nfl_final_architecture_calibration.py. Keep these synchronized.
RATING = {
    "elo_k": 40.0,
    "elo_hfa": 35.0,
    "offseason_regression": 0.25,
    "margin_k": 0.05,
    "margin_hfa": 3.0,
    "lambda": 100.0,
}


def matrix(rows, team_k, cov_k, ftn_k=None):
    names = None
    data = []
    for r in rows:
        bn, bv = base.spread_features(r, team_k)
        cn, cv = cov.extras(r, "spread", "coverage", cov_k)
        rn = ["rating_win_elo_diff", "rating_margin_rating_diff"]
        rv = [float(r["rating_win_elo_diff"]), float(r["rating_margin_rating_diff"])]
        n = bn + cn + rn
        v = bv + cv + rv
        if ftn_k is not None:
            en, ev = ftn.extras(r, "spread", "qb_process", ftn_k)
            n += en
            v += ev
        if names is None:
            names = n
        data.append([np.nan if x is None else float(x) for x in v])
    return names, np.asarray(data, dtype=float)


def fit(rows, team_k, cov_k, lam, ftn_k=None):
    names, x = matrix(rows, team_k, cov_k, ftn_k)
    prep = base.fit_preprocessor(x)
    model = base.ridge_fit(base.transform(x, prep), base.target_array(rows, "spread"), lam)
    return names, prep, model


def predict(rows, team_k, cov_k, fitobj, ftn_k=None):
    names, prep, model = fitobj
    _, x = matrix(rows, team_k, cov_k, ftn_k)
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
    }


def choose_candidate_2022(rows22, team_k, cov_k):
    train, valid = base.inner_split(rows22)
    y = base.target_array(valid, "spread")
    candidates = []
    for fk in FEATURE_K_GRID:
        for lam in LAMBDA_GRID:
            fo = fit(train, team_k, cov_k, lam, fk)
            p, _ = predict(valid, team_k, cov_k, fo, fk)
            candidates.append({
                "feature_k": fk,
                "lambda": lam,
                "mae": base.mae(y, p),
                "rmse": base.rmse(y, p),
                "validation_games": len(valid),
            })
    candidates.sort(key=lambda x: (x["mae"], x["rmse"], x["lambda"], x["feature_k"]))
    return candidates[0], candidates[:8]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base_rows = base.load_rows()
    ngs_idx, ngs_leak, _ = ngs.load_index()
    cov_idx, cov_leak, _ = cov.loadidx(cov.COV, "cov")
    ftn_idx, ftn_leak, ftn_rows = ftn.loadidx()
    if ngs_leak + cov_leak + ftn_leak:
        raise RuntimeError(f"source leakage ngs={ngs_leak} coverage={cov_leak} ftn={ftn_leak}")

    cov_rows = cov.attach(base_rows, cov_idx, ngs_idx)
    rows = ftn.attach(cov_rows, ftn_idx)
    cov22 = [r for r in cov_rows if r["season"] == 2022]
    cov_params, _ = cov.select(cov22, "spread", "coverage")

    games = rat.fetch_games()
    rating_map = rat.rating_maps(
        games,
        RATING["elo_k"],
        RATING["elo_hfa"],
        RATING["offseason_regression"],
        RATING["margin_k"],
        RATING["margin_hfa"],
    )
    rated = rat.attach(rows, rating_map)
    rows22 = [r for r in rated if r["season"] == 2022]

    selected, top = choose_candidate_2022(
        rows22, cov_params["team_k"], cov_params["feature_k"]
    )

    folds = {}
    all_ref_err = []
    all_cand_err = []
    new_feature_coefficients = {}
    for year in YEARS:
        train = [r for r in rated if r["season"] < year]
        test = [r for r in rated if r["season"] == year]

        ref_fit = fit(
            train,
            cov_params["team_k"],
            cov_params["feature_k"],
            RATING["lambda"],
            None,
        )
        ref_pred, _ = predict(
            test, cov_params["team_k"], cov_params["feature_k"], ref_fit, None
        )

        cand_fit = fit(
            train,
            cov_params["team_k"],
            cov_params["feature_k"],
            selected["lambda"],
            selected["feature_k"],
        )
        cand_pred, coef = predict(
            test,
            cov_params["team_k"],
            cov_params["feature_k"],
            cand_fit,
            selected["feature_k"],
        )

        re = abs_error(test, ref_pred)
        ce = abs_error(test, cand_pred)
        all_ref_err.extend(re.tolist())
        all_cand_err.extend(ce.tolist())
        new_feature_coefficients[str(year)] = {
            k: round(v, 6) for k, v in coef.items() if k.startswith("ftn_")
        }
        folds[str(year)] = {
            "n": len(test),
            "reference_final_architecture_mae": round(float(np.mean(re)), 4),
            "candidate_mae": round(float(np.mean(ce)), 4),
            "candidate_minus_reference_mae": round(float(np.mean(ce) - np.mean(re)), 4),
        }

    ref = np.asarray(all_ref_err)
    cand = np.asarray(all_cand_err)
    paired = ref - cand
    boot = bootstrap(paired)
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
        "design": "Nested test of FTN QB-process features on top of the frozen final spread architecture. New-family hyperparameters selected from 2022 only; outer evaluation 2023-2025.",
        "reference_architecture": "core + defensive coverage + market-independent win Elo + margin rating",
        "reference_rating_params": RATING,
        "coverage_params": cov_params,
        "selected_candidate_params_2022_only": selected,
        "top_2022_candidates": top,
        "source_ftn_rows": ftn_rows,
        "source_leakage_rows": ftn_leak,
        "folds": folds,
        "aggregate": {
            "n": len(cand),
            "reference_mae": round(float(np.mean(ref)), 4),
            "candidate_mae": round(float(np.mean(cand)), 4),
            "candidate_minus_reference_mae": round(float(np.mean(cand) - np.mean(ref)), 4),
            "seasons_improved": seasons_improved,
            "paired_bootstrap_reference_minus_candidate": boot,
        },
        "new_feature_coefficients_by_test_season": new_feature_coefficients,
        "promotion_rule": "Candidate must improve aggregate MAE, improve at least 2 of 3 seasons, and have paired-bootstrap 95% CI for reference-minus-candidate entirely above zero.",
        "historical_promotion_earned": promoted,
        "week6_frozen_snapshot_may_be_rewritten": False,
        "release_state": "SHADOW_CANDIDATE_ELIGIBLE" if promoted else "HOLD_NO_INCREMENTAL_PROMOTION",
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
