#!/usr/bin/env python3
"""Controlled incremental test for FTN QB-process information.

Separates two effects that were confounded in the first nested test:
1) re-regularizing the canonical final architecture, and
2) adding FTN QB-process features.

Both the no-FTN control lambda and FTN candidate parameters are selected only
from the same 2022 inner validation split. Outer 2023-2025 results are untouched
until evaluation. Research-only; no Week 6 rewrite or website release.
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

OUT = Path("nfl_data/validation/ftn_qb_process_controlled.json")
YEARS = [2023, 2024, 2025]
LAMBDAS = [10.0, 30.0, 100.0, 300.0]
DRAWS = 10000
SEED = 20261017


def ae(rows, pred):
    return np.abs(base.target_array(rows, "spread") - np.asarray(pred, float))


def boot(diff):
    d = np.asarray(diff, float)
    rng = np.random.default_rng(SEED)
    n = len(d)
    draws = np.empty(DRAWS)
    for i in range(DRAWS):
        draws[i] = np.mean(d[rng.integers(0, n, size=n)])
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return {
        "mean_improvement": round(float(np.mean(d)), 5),
        "bootstrap_95_ci": [round(float(lo), 5), round(float(hi), 5)],
        "probability_gt_0": round(float(np.mean(draws > 0)), 4),
        "draws": DRAWS,
    }


def select_control_lambda(rows22, team_k, cov_k):
    train, valid = base.inner_split(rows22)
    y = base.target_array(valid, "spread")
    out = []
    for lam in LAMBDAS:
        fo = qbp.fit(train, team_k, cov_k, lam, None)
        p, _ = qbp.predict(valid, team_k, cov_k, fo, None)
        out.append({"lambda": lam, "mae": base.mae(y, p), "rmse": base.rmse(y, p), "validation_games": len(valid)})
    out.sort(key=lambda x: (x["mae"], x["rmse"], x["lambda"]))
    return out[0], out


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base_rows = base.load_rows()
    ni, nl, _ = ngs.load_index()
    ci, cl, _ = cov.loadidx(cov.COV, "cov")
    fi, fl, _ = ftn.loadidx()
    if nl + cl + fl:
        raise RuntimeError(f"source leakage ngs={nl} coverage={cl} ftn={fl}")

    covrows = cov.attach(base_rows, ci, ni)
    charted = ftn.attach(covrows, fi)
    c22 = [r for r in covrows if r["season"] == 2022]
    cp, _ = cov.select(c22, "spread", "coverage")

    games = rat.fetch_games()
    rmap = rat.rating_maps(
        games,
        qbp.RATING["elo_k"], qbp.RATING["elo_hfa"], qbp.RATING["offseason_regression"],
        qbp.RATING["margin_k"], qbp.RATING["margin_hfa"],
    )
    rows = rat.attach(charted, rmap)
    r22 = [r for r in rows if r["season"] == 2022]

    control, control_grid = select_control_lambda(r22, cp["team_k"], cp["feature_k"])
    candidate, _ = qbp.choose_candidate_2022(r22, cp["team_k"], cp["feature_k"])

    folds = {}
    can_all, ctl_all, cand_all = [], [], []
    for year in YEARS:
        tr = [r for r in rows if r["season"] < year]
        te = [r for r in rows if r["season"] == year]

        can_fit = qbp.fit(tr, cp["team_k"], cp["feature_k"], qbp.RATING["lambda"], None)
        can_p, _ = qbp.predict(te, cp["team_k"], cp["feature_k"], can_fit, None)
        ctl_fit = qbp.fit(tr, cp["team_k"], cp["feature_k"], control["lambda"], None)
        ctl_p, _ = qbp.predict(te, cp["team_k"], cp["feature_k"], ctl_fit, None)
        cand_fit = qbp.fit(tr, cp["team_k"], cp["feature_k"], candidate["lambda"], candidate["feature_k"])
        cand_p, _ = qbp.predict(te, cp["team_k"], cp["feature_k"], cand_fit, candidate["feature_k"])

        ce, te_ctl, fe = ae(te, can_p), ae(te, ctl_p), ae(te, cand_p)
        can_all.extend(ce.tolist()); ctl_all.extend(te_ctl.tolist()); cand_all.extend(fe.tolist())
        folds[str(year)] = {
            "n": len(te),
            "canonical_mae": round(float(np.mean(ce)), 4),
            "tuned_no_ftn_control_mae": round(float(np.mean(te_ctl)), 4),
            "ftn_candidate_mae": round(float(np.mean(fe)), 4),
            "control_minus_canonical_mae": round(float(np.mean(te_ctl) - np.mean(ce)), 4),
            "ftn_minus_control_mae": round(float(np.mean(fe) - np.mean(te_ctl)), 4),
        }

    can = np.asarray(can_all); ctl = np.asarray(ctl_all); cand = np.asarray(cand_all)
    control_boot = boot(can - ctl)
    ftn_boot = boot(ctl - cand)
    control_seasons = sum(folds[str(y)]["control_minus_canonical_mae"] < 0 for y in YEARS)
    ftn_seasons = sum(folds[str(y)]["ftn_minus_control_mae"] < 0 for y in YEARS)
    control_robust = bool(np.mean(ctl) < np.mean(can) and control_seasons >= 2 and control_boot["bootstrap_95_ci"][0] > 0)
    ftn_incremental = bool(np.mean(cand) < np.mean(ctl) and ftn_seasons >= 2 and ftn_boot["bootstrap_95_ci"][0] > 0)

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "design": "Matched 2022-only tuning control: canonical lambda vs re-tuned no-FTN lambda vs FTN QB-process candidate; outer 2023-2025.",
        "canonical_lambda": qbp.RATING["lambda"],
        "selected_no_ftn_control_2022_only": control,
        "control_lambda_grid_2022": control_grid,
        "selected_ftn_candidate_2022_only": candidate,
        "folds": folds,
        "aggregate": {
            "n": len(can),
            "canonical_mae": round(float(np.mean(can)), 4),
            "tuned_no_ftn_control_mae": round(float(np.mean(ctl)), 4),
            "ftn_candidate_mae": round(float(np.mean(cand)), 4),
            "control_minus_canonical_mae": round(float(np.mean(ctl) - np.mean(can)), 4),
            "ftn_minus_control_mae": round(float(np.mean(cand) - np.mean(ctl)), 4),
            "control_seasons_improved": control_seasons,
            "ftn_incremental_seasons_improved": ftn_seasons,
            "canonical_minus_control_bootstrap": control_boot,
            "control_minus_ftn_bootstrap": ftn_boot,
        },
        "regularization_control_robust": control_robust,
        "ftn_incremental_value_robust": ftn_incremental,
        "interpretation": "Credit FTN only for improvement beyond the equally 2022-tuned no-FTN control. Do not credit feature value to a regularization-only gain.",
        "week6_frozen_snapshot_may_be_rewritten": False,
        "production_promotion_allowed": False,
        "website_publish_allowed": False,
        "recommendation_release_allowed": False,
        "release_state": "CONTROLLED_FTN_SHADOW_ELIGIBLE" if ftn_incremental else ("REGULARIZATION_SHADOW_ELIGIBLE" if control_robust else "HOLD_NO_ROBUST_INCREMENT"),
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate":result["aggregate"],"release_state":result["release_state"]}, indent=2))


if __name__ == "__main__":
    main()
