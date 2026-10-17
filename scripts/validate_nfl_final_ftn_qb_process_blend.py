#!/usr/bin/env python3
"""Conservative shadow blend test for the NFL spread architecture.

The blend is fixed a priori at 50% canonical final spread architecture and 50%
FTN-QB-process candidate. No outer-fold result is used to choose the blend
weight. Candidate hyperparameters remain selected on 2022 only. Evaluation is
strictly 2023-2025 and research-only.
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
import validate_nfl_ftn_charting_robustness as ftn
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as qbp

OUT = Path("nfl_data/validation/final_ftn_qb_process_blend.json")
YEARS = [2023, 2024, 2025]
BLEND_CANDIDATE_WEIGHT = 0.50
DRAWS = 10000
SEED = 20261017


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


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base_rows = base.load_rows()
    ngs_idx, ngs_leak, _ = ngs.load_index()
    cov_idx, cov_leak, _ = cov.loadidx(cov.COV, "cov")
    ftn_idx, ftn_leak, _ = ftn.loadidx()
    if ngs_leak + cov_leak + ftn_leak:
        raise RuntimeError(f"source leakage ngs={ngs_leak} coverage={cov_leak} ftn={ftn_leak}")

    cov_rows = cov.attach(base_rows, cov_idx, ngs_idx)
    charted = ftn.attach(cov_rows, ftn_idx)
    cov22 = [r for r in cov_rows if r["season"] == 2022]
    cov_params, _ = cov.select(cov22, "spread", "coverage")

    games = rat.fetch_games()
    rating_map = rat.rating_maps(
        games,
        qbp.RATING["elo_k"],
        qbp.RATING["elo_hfa"],
        qbp.RATING["offseason_regression"],
        qbp.RATING["margin_k"],
        qbp.RATING["margin_hfa"],
    )
    rated = rat.attach(charted, rating_map)
    rows22 = [r for r in rated if r["season"] == 2022]
    selected, _ = qbp.choose_candidate_2022(
        rows22, cov_params["team_k"], cov_params["feature_k"]
    )

    folds = {}
    ref_all = []
    cand_all = []
    blend_all = []
    for year in YEARS:
        train = [r for r in rated if r["season"] < year]
        test = [r for r in rated if r["season"] == year]

        ref_fit = qbp.fit(
            train, cov_params["team_k"], cov_params["feature_k"], qbp.RATING["lambda"], None
        )
        ref_pred, _ = qbp.predict(
            test, cov_params["team_k"], cov_params["feature_k"], ref_fit, None
        )
        cand_fit = qbp.fit(
            train,
            cov_params["team_k"],
            cov_params["feature_k"],
            selected["lambda"],
            selected["feature_k"],
        )
        cand_pred, _ = qbp.predict(
            test,
            cov_params["team_k"],
            cov_params["feature_k"],
            cand_fit,
            selected["feature_k"],
        )
        blend_pred = (1.0 - BLEND_CANDIDATE_WEIGHT) * ref_pred + BLEND_CANDIDATE_WEIGHT * cand_pred

        re = abs_error(test, ref_pred)
        ce = abs_error(test, cand_pred)
        be = abs_error(test, blend_pred)
        ref_all.extend(re.tolist())
        cand_all.extend(ce.tolist())
        blend_all.extend(be.tolist())
        folds[str(year)] = {
            "n": len(test),
            "reference_mae": round(float(np.mean(re)), 4),
            "candidate_mae": round(float(np.mean(ce)), 4),
            "fixed_50_50_blend_mae": round(float(np.mean(be)), 4),
            "blend_minus_reference_mae": round(float(np.mean(be) - np.mean(re)), 4),
        }

    ref = np.asarray(ref_all)
    cand = np.asarray(cand_all)
    blend = np.asarray(blend_all)
    boot = bootstrap(ref - blend)
    seasons_improved = sum(folds[str(y)]["blend_minus_reference_mae"] < 0 for y in YEARS)
    robust = bool(
        float(np.mean(blend)) < float(np.mean(ref))
        and seasons_improved >= 2
        and boot["bootstrap_95_ci"][0] > 0
    )

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "design": "Fixed 50/50 prediction blend: canonical final spread architecture + 2022-selected FTN QB-process candidate; outer evaluation 2023-2025.",
        "blend_candidate_weight": BLEND_CANDIDATE_WEIGHT,
        "blend_weight_selected_from_outer_results": False,
        "reference_architecture": "core + defensive coverage + market-independent win Elo + margin rating",
        "reference_rating_params": qbp.RATING,
        "coverage_params": cov_params,
        "candidate_params_selected_2022_only": selected,
        "folds": folds,
        "aggregate": {
            "n": len(ref),
            "reference_mae": round(float(np.mean(ref)), 4),
            "unblended_candidate_mae": round(float(np.mean(cand)), 4),
            "fixed_50_50_blend_mae": round(float(np.mean(blend)), 4),
            "blend_minus_reference_mae": round(float(np.mean(blend) - np.mean(ref)), 4),
            "seasons_improved": seasons_improved,
            "paired_bootstrap_reference_minus_blend": boot,
        },
        "robust_shadow_blend_earned": robust,
        "promotion_rule": "Fixed blend must improve aggregate MAE, improve at least 2 of 3 outer seasons, and have paired-bootstrap 95% CI for reference-minus-blend entirely above zero.",
        "production_promotion_allowed": False,
        "reason_production_remains_locked": "Even a robust historical shadow blend requires prospective validation before replacing the frozen canonical architecture.",
        "week6_frozen_snapshot_may_be_rewritten": False,
        "release_state": "ROBUST_SHADOW_BLEND_ELIGIBLE" if robust else "HOLD_BLEND_NOT_ROBUST",
        "website_publish_allowed": False,
        "recommendation_release_allowed": False,
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": result["aggregate"], "release_state": result["release_state"]}, indent=2))


if __name__ == "__main__":
    main()
