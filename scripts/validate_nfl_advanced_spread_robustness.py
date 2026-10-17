#!/usr/bin/env python3
"""Robustness audit for promising NFL advanced spread features.

Harder validation than v1:
- hyperparameters are selected ONCE using only 2022 training data;
- those shrinkage/regularization values are frozen for 2023-2025;
- coefficients may refit using only seasons available before each test season;
- reports paired error deltas, week buckets, season stability, coefficient signs,
  and a fixed-seed paired bootstrap confidence interval.

Development only. No production promotion and no website publication.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix  # patches ngs canonical aliases + metadata collision
import validate_nfl_coverage_v1 as cov

OUT = Path("nfl_data/validation/advanced_spread_robustness.json")
TARGET_YEARS = [2023, 2024, 2025]
WEEK_BUCKETS = {
    "weeks_1_5": lambda w: 1 <= w <= 5,
    "weeks_6_12": lambda w: 6 <= w <= 12,
    "weeks_13_18": lambda w: 13 <= w <= 18,
}
BOOTSTRAP_DRAWS = 5000
RNG_SEED = 20261017


def mae(y, p):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(p, float))))


def paired_bootstrap_improvement(y, base_pred, cand_pred):
    y = np.asarray(y, float)
    b = np.abs(y - np.asarray(base_pred, float))
    c = np.abs(y - np.asarray(cand_pred, float))
    diff = b - c  # positive = candidate improves absolute error
    rng = np.random.default_rng(RNG_SEED)
    n = len(diff)
    means = np.empty(BOOTSTRAP_DRAWS, dtype=float)
    for i in range(BOOTSTRAP_DRAWS):
        idx = rng.integers(0, n, size=n)
        means[i] = float(np.mean(diff[idx]))
    lo, hi = np.quantile(means, [0.025, 0.975])
    return {
        "mean_absolute_error_improvement": round(float(np.mean(diff)), 5),
        "bootstrap_95_ci": [round(float(lo), 5), round(float(hi), 5)],
        "probability_improvement_gt_0": round(float(np.mean(means > 0)), 4),
        "draws": BOOTSTRAP_DRAWS,
        "seed": RNG_SEED,
    }


def basic_metrics(rows, pred):
    y = np.asarray([float(r["home_margin"]) for r in rows], dtype=float)
    p = np.asarray(pred, dtype=float)
    return {
        "n": len(rows),
        "mae": round(base.mae(y, p), 4),
        "rmse": round(base.rmse(y, p), 4),
        "bias": round(base.bias(y, p), 4),
    }


def bucket_metrics(rows, base_pred, cand_pred):
    out = {}
    for name, fn in WEEK_BUCKETS.items():
        idx = [i for i, r in enumerate(rows) if fn(int(r["week"]))]
        if not idx:
            out[name] = {"n": 0}
            continue
        y = [float(rows[i]["home_margin"]) for i in idx]
        bp = [float(base_pred[i]) for i in idx]
        cp = [float(cand_pred[i]) for i in idx]
        bmae, cmae = mae(y, bp), mae(y, cp)
        out[name] = {
            "n": len(idx),
            "baseline_mae": round(bmae, 4),
            "candidate_mae": round(cmae, 4),
            "candidate_delta_vs_baseline": round(cmae - bmae, 4),
        }
    return out


def advanced_sign_summary(coef_by_year, prefix):
    features = sorted({k for _, c in coef_by_year.items() for k in c if k.startswith(prefix)})
    out = {}
    stable_count = 0
    eligible = 0
    for feature in features:
        vals = [coef_by_year[y].get(feature) for y in TARGET_YEARS]
        vals = [v for v in vals if v is not None and math.isfinite(v)]
        signs = [1 if v > 0 else -1 if v < 0 else 0 for v in vals]
        nz = [s for s in signs if s != 0]
        stable = len(nz) >= 2 and (all(s > 0 for s in nz) or all(s < 0 for s in nz))
        if len(nz) >= 2:
            eligible += 1
            stable_count += int(stable)
        out[feature] = {
            "coefficients": [round(float(v), 6) for v in vals],
            "same_nonzero_sign_across_available_folds": stable,
        }
    return {
        "features": out,
        "eligible_features": eligible,
        "same_sign_features": stable_count,
        "same_sign_share": None if eligible == 0 else round(stable_count / eligible, 4),
    }


def combine_all(test_rows_by_year, preds_by_year):
    rows, preds = [], []
    for y in TARGET_YEARS:
        rows.extend(test_rows_by_year[y])
        preds.extend(preds_by_year[y])
    return rows, np.asarray(preds, float)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base_rows = base.load_rows()

    ngs_idx, ngs_leak, ngs_source_rows = ngs.load_index()
    cov_idx, cov_leak, cov_source_rows = cov.loadidx(cov.COV, "cov")
    if ngs_leak or cov_leak:
        raise RuntimeError(f"Source leakage: ngs={ngs_leak}, coverage={cov_leak}")

    ngs_rows = ngs.attach(base_rows, ngs_idx)
    cov_rows = cov.attach(base_rows, cov_idx, ngs_idx)
    if len(ngs_rows) != len(base_rows) or len(cov_rows) != len(base_rows):
        raise RuntimeError("Advanced robustness requires complete game attachment")

    train_2022_base = [r for r in base_rows if r["season"] == 2022]
    train_2022_ngs = [r for r in ngs_rows if r["season"] == 2022]
    train_2022_cov = [r for r in cov_rows if r["season"] == 2022]

    frozen_base, base_candidates = base.select_params(train_2022_base, "spread")
    frozen = {
        "baseline": {
            "team_k": frozen_base["k"],
            "lambda": frozen_base["lambda"],
            "selection_mae": frozen_base["mae"],
        }
    }
    for family in ["passing_ngs", "rushing_ngs", "receiving_ngs", "all_ngs"]:
        best, _ = ngs.select(train_2022_ngs, "spread", family)
        frozen[family] = {
            "team_k": best["team_k"], "ngs_k": best["ngs_k"],
            "lambda": best["lambda"], "selection_mae": best["mae"],
            "inner_validation_n": best.get("inner_validation_n"),
        }
    for variant in ["coverage", "coverage_receiving_matchup"]:
        best, _ = cov.select(train_2022_cov, "spread", variant)
        frozen[variant] = {
            "team_k": best["team_k"], "feature_k": best["feature_k"],
            "lambda": best["lambda"], "selection_mae": best["mae"],
        }

    test_rows_by_year = {}
    base_pred_by_year = {}
    base_metrics_by_year = {}
    market_mae_by_year = {}
    for year in TARGET_YEARS:
        tr = [r for r in base_rows if r["season"] < year]
        te = [r for r in base_rows if r["season"] == year]
        p, _, _, _, _ = base.fit_and_predict(
            tr, te, "spread", frozen_base["k"], frozen_base["lambda"]
        )
        test_rows_by_year[year] = te
        base_pred_by_year[year] = np.asarray(p, float)
        base_metrics_by_year[year] = basic_metrics(te, p)
        market_mae_by_year[year] = round(base.market_mae(te, "spread"), 4)

    variants = {}
    ngs_lookup = {r["game_id"]: r for r in ngs_rows}
    cov_lookup = {r["game_id"]: r for r in cov_rows}

    for family in ["passing_ngs", "rushing_ngs", "receiving_ngs", "all_ngs"]:
        params = frozen[family]
        preds_by_year, coefs_by_year, folds = {}, {}, {}
        for year in TARGET_YEARS:
            tr = [r for r in ngs_rows if r["season"] < year]
            te = [ngs_lookup[r["game_id"]] for r in test_rows_by_year[year]]
            p, coef = ngs.fitpred(tr, te, "spread", family, params)
            p = np.asarray(p, float)
            preds_by_year[year] = p; coefs_by_year[year] = coef
            bm = base_metrics_by_year[year]; cm = basic_metrics(te, p)
            folds[str(year)] = {
                **cm,
                "baseline_mae": bm["mae"],
                "mae_delta_vs_frozen_baseline": round(cm["mae"] - bm["mae"], 4),
                "market_reference_mae": market_mae_by_year[year],
                "week_buckets": bucket_metrics(te, base_pred_by_year[year], p),
            }
        all_rows, all_p = combine_all(test_rows_by_year, preds_by_year)
        _, all_bp = combine_all(test_rows_by_year, base_pred_by_year)
        y = np.asarray([float(r["home_margin"]) for r in all_rows], float)
        cand_mae, bmae = mae(y, all_p), mae(y, all_bp)
        seasons_better = sum(folds[str(y_)]["mae_delta_vs_frozen_baseline"] < 0 for y_ in TARGET_YEARS)
        bucket_deltas = []
        for bname in WEEK_BUCKETS:
            vals = [folds[str(y_)]["week_buckets"][bname] for y_ in TARGET_YEARS]
            n = sum(v.get("n",0) for v in vals)
            if n:
                delta = sum(v["candidate_delta_vs_baseline"] * v["n"] for v in vals) / n
                bucket_deltas.append((bname, round(delta,4), n))
        variants[family] = {
            "frozen_params": params,
            "folds": folds,
            "aggregate": {
                "n": len(all_rows), "baseline_mae": round(bmae,4),
                "candidate_mae": round(cand_mae,4),
                "mae_delta_vs_frozen_baseline": round(cand_mae-bmae,4),
                "market_reference_mae": round(base.market_mae(all_rows,"spread"),4),
                "seasons_with_lower_mae": seasons_better,
                "week_bucket_weighted_deltas": {k:{"delta":d,"n":n} for k,d,n in bucket_deltas},
                "week_buckets_improved": sum(d < 0 for _,d,_ in bucket_deltas),
                "paired_bootstrap": paired_bootstrap_improvement(y, all_bp, all_p),
            },
            "advanced_coefficient_sign_stability": advanced_sign_summary(coefs_by_year, "ngs_"),
        }

    for variant in ["coverage", "coverage_receiving_matchup"]:
        params = frozen[variant]
        preds_by_year, coefs_by_year, folds = {}, {}, {}
        for year in TARGET_YEARS:
            tr = [r for r in cov_rows if r["season"] < year]
            te = [cov_lookup[r["game_id"]] for r in test_rows_by_year[year]]
            p, coef = cov.fitp(tr, te, "spread", variant, params)
            p = np.asarray(p, float)
            preds_by_year[year] = p; coefs_by_year[year] = coef
            bm = base_metrics_by_year[year]; cm = basic_metrics(te, p)
            folds[str(year)] = {
                **cm,
                "baseline_mae": bm["mae"],
                "mae_delta_vs_frozen_baseline": round(cm["mae"] - bm["mae"], 4),
                "market_reference_mae": market_mae_by_year[year],
                "week_buckets": bucket_metrics(te, base_pred_by_year[year], p),
            }
        all_rows, all_p = combine_all(test_rows_by_year, preds_by_year)
        _, all_bp = combine_all(test_rows_by_year, base_pred_by_year)
        y = np.asarray([float(r["home_margin"]) for r in all_rows], float)
        cand_mae, bmae = mae(y, all_p), mae(y, all_bp)
        seasons_better = sum(folds[str(y_)]["mae_delta_vs_frozen_baseline"] < 0 for y_ in TARGET_YEARS)
        bucket_deltas=[]
        for bname in WEEK_BUCKETS:
            vals=[folds[str(y_)]["week_buckets"][bname] for y_ in TARGET_YEARS]
            n=sum(v.get("n",0) for v in vals)
            if n:
                delta=sum(v["candidate_delta_vs_baseline"]*v["n"] for v in vals)/n
                bucket_deltas.append((bname,round(delta,4),n))
        variants[variant]={
            "frozen_params":params,"folds":folds,
            "aggregate":{
                "n":len(all_rows),"baseline_mae":round(bmae,4),"candidate_mae":round(cand_mae,4),
                "mae_delta_vs_frozen_baseline":round(cand_mae-bmae,4),"market_reference_mae":round(base.market_mae(all_rows,"spread"),4),
                "seasons_with_lower_mae":seasons_better,
                "week_bucket_weighted_deltas":{k:{"delta":d,"n":n} for k,d,n in bucket_deltas},
                "week_buckets_improved":sum(d<0 for _,d,_ in bucket_deltas),
                "paired_bootstrap":paired_bootstrap_improvement(y,all_bp,all_p),
            },
            "advanced_coefficient_sign_stability":advanced_sign_summary(coefs_by_year,"cov_")
        }

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "design": "Hyperparameters selected once from 2022 only; frozen for 2023-2025. Coefficients refit only on prior seasons.",
        "source_leakage_rows": ngs_leak + cov_leak,
        "ngs_source_rows": ngs_source_rows,
        "coverage_source_rows": cov_source_rows,
        "frozen_hyperparameters": frozen,
        "frozen_baseline_by_year": base_metrics_by_year,
        "variants": variants,
        "release_state": "HOLD_ROBUSTNESS_ONLY",
        "website_publish_allowed": False,
        "promotion_rule": "No automatic promotion. Robustness, coefficient stability, multiple-testing risk and prospective validation must be reviewed together.",
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "variants": {k: v["aggregate"] for k,v in variants.items()},
        "release_state": result["release_state"],
    }, indent=2))

if __name__ == "__main__":
    main()
