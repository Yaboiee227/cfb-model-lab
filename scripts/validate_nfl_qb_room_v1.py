#!/usr/bin/env python3
"""Walk-forward test of leakage-safe QB primary/room features.

This script compares the existing market-independent team baseline with two QB
variants on identical outer folds:
  2023 <- train 2022
  2024 <- train 2022-2023
  2025 <- train 2022-2024

QB rate features are shrunk toward neutral using a pseudo-dropback parameter
selected only inside each training fold. The target game's realized starter is
never used. Market spread/total are benchmark/grading fields only.

Development only; all outputs remain HOLD / RESEARCH ONLY.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Import the frozen baseline feature/fit machinery from the same scripts folder.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base  # noqa: E402

QB_FILE = Path("nfl_data/historical/team_week_qb_room_2022_2025.csv")
OUT_DIR = Path("nfl_data/validation")
TARGET_YEARS = [2023, 2024, 2025]
QB_K_GRID = [20.0, 50.0, 100.0, 200.0]
VARIANTS = ["primary", "room"]
KINDS = ["spread", "total"]


def tf(v):
    return base.to_float(v)


def load_qb_index():
    with QB_FILE.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    idx = {}
    leakage = 0
    for r in rows:
        season = int(float(r["season"])); week = int(float(r["target_week"])); team = r["team"]
        if int(float(r.get("max_current_week_used") or 0)) >= week:
            leakage += 1
        key = (season, week, team)
        if key in idx:
            raise RuntimeError(f"Duplicate QB snapshot key {key}")
        idx[key] = r
    return idx, leakage, len(rows)


def attach_qb(game_rows, qb_idx):
    out = []
    missing = []
    for r in game_rows:
        season, week = r["season"], r["week"]
        hkey = (season, week, r["home_team"])
        akey = (season, week, r["away_team"])
        if hkey not in qb_idx or akey not in qb_idx:
            missing.append((r["game_id"], hkey, akey))
            continue
        x = dict(r)
        for side, qrow in (("home", qb_idx[hkey]), ("away", qb_idx[akey])):
            for key, value in qrow.items():
                if key in {"season", "target_week", "team", "release_state"}:
                    continue
                x[f"{side}_qb_{key}"] = value
        out.append(x)
    if missing:
        raise RuntimeError(f"Missing QB snapshots for {len(missing)} games; first={missing[:3]}")
    return out


def shrink_zero(value, sample, k):
    v, n = tf(value), tf(sample)
    if v is None or n is None or n <= 0:
        return None
    return v * n / (n + k)


def qval(r, side, prefix, metric):
    return r.get(f"{side}_qb_{prefix}{metric}")


def qshrunk(r, side, prefix, metric, sample_metric, k):
    return shrink_zero(
        qval(r, side, prefix, metric),
        qval(r, side, prefix, sample_metric),
        k,
    )


def bool_num(v):
    return 1.0 if str(v).strip().lower() == "true" else 0.0


def primary_features(r, kind, qbk):
    def m(side, metric, sample="dropbacks"):
        return qshrunk(r, side, "recent_", metric, sample, qbk)
    def rush(side):
        # Rushing opportunity is smaller than dropback opportunity; use a lighter
        # but fixed shrink constant to avoid adding another tuned dimension.
        return qshrunk(r, side, "recent_", "rush_epa_per_carry", "rush_carries", 20.0)
    def ngs(side):
        return qshrunk(r, side, "recent_", "ngs_cpoe", "ngs_attempts_cpoe", qbk)
    def logdb(side):
        n = tf(qval(r, side, "recent_", "dropbacks"))
        return None if n is None else math.log1p(max(0.0, n))
    def prior_proxy(side):
        return 1.0 if str(r.get(f"{side}_qb_primary_proxy_source", "")).startswith("PRIOR_SEASON") else 0.0
    def switch(side):
        return bool_num(r.get(f"{side}_qb_recent_primary_differs_from_cumulative"))

    hepa, aepa = m("home", "pass_epa_per_db"), m("away", "pass_epa_per_db")
    hcpoe, acpoe = m("home", "cpoe", "attempts"), m("away", "cpoe", "attempts")
    hngs, angs = ngs("home"), ngs("away")
    hrush, arush = rush("home"), rush("away")
    hdb, adb = logdb("home"), logdb("away")
    hsw, asw = switch("home"), switch("away")
    hprior, aprior = prior_proxy("home"), prior_proxy("away")

    if kind == "spread":
        names = [
            "qb_recent_epa_db_diff", "qb_recent_cpoe_diff", "qb_recent_ngs_cpoe_diff",
            "qb_recent_rush_epa_carry_diff", "qb_log_dropbacks_diff", "qb_log_dropbacks_sum",
            "qb_recent_switch_diff", "qb_prior_proxy_diff",
        ]
        vals = [
            base.diff(hepa, aepa), base.diff(hcpoe, acpoe), base.diff(hngs, angs),
            base.diff(hrush, arush), base.diff(hdb, adb), base.summ(hdb, adb),
            hsw - asw, hprior - aprior,
        ]
    else:
        names = [
            "qb_recent_epa_db_sum", "qb_recent_cpoe_sum", "qb_recent_ngs_cpoe_sum",
            "qb_recent_rush_epa_carry_sum", "qb_log_dropbacks_sum", "qb_log_dropbacks_absdiff",
            "qb_recent_switch_sum", "qb_prior_proxy_sum",
        ]
        vals = [
            base.summ(hepa, aepa), base.summ(hcpoe, acpoe), base.summ(hngs, angs),
            base.summ(hrush, arush), base.summ(hdb, adb),
            None if hdb is None or adb is None else abs(hdb - adb),
            hsw + asw, hprior + aprior,
        ]
    return names, vals


def room_features(r, kind, qbk):
    pnames, pvals = primary_features(r, kind, qbk)

    def rep(side, metric, sample="dropbacks"):
        return qshrunk(r, side, "replacement_", metric, sample, qbk)
    def prim(side, metric, sample="dropbacks"):
        return qshrunk(r, side, "recent_", metric, sample, qbk)
    def rep_missing(side):
        return 1.0 if str(r.get(f"{side}_qb_replacement_proxy_source", "")) == "LEAGUE_REPLACEMENT_NEEDED" else 0.0
    def rep_prior(side):
        return 1.0 if str(r.get(f"{side}_qb_replacement_proxy_source", "")).startswith("PRIOR_SEASON") else 0.0

    hp, ap = prim("home", "pass_epa_per_db"), prim("away", "pass_epa_per_db")
    hr, ar = rep("home", "pass_epa_per_db"), rep("away", "pass_epa_per_db")
    hpc, apc = prim("home", "cpoe", "attempts"), prim("away", "cpoe", "attempts")
    hrc, arc = rep("home", "cpoe", "attempts"), rep("away", "cpoe", "attempts")
    hdelta = None if hp is None or hr is None else hp - hr
    adelta = None if ap is None or ar is None else ap - ar
    hcpoed = None if hpc is None or hrc is None else hpc - hrc
    acpoed = None if apc is None or arc is None else apc - arc
    hm, am = rep_missing("home"), rep_missing("away")
    hpr, apr = rep_prior("home"), rep_prior("away")

    if kind == "spread":
        names = pnames + [
            "qb_room_epa_delta_diff", "qb_room_cpoe_delta_diff", "qb_replacement_epa_diff",
            "qb_replacement_missing_diff", "qb_replacement_prior_proxy_diff",
        ]
        vals = pvals + [
            base.diff(hdelta, adelta), base.diff(hcpoed, acpoed), base.diff(hr, ar),
            hm - am, hpr - apr,
        ]
    else:
        names = pnames + [
            "qb_room_epa_delta_sum", "qb_room_cpoe_delta_sum", "qb_replacement_epa_sum",
            "qb_replacement_missing_sum", "qb_replacement_prior_proxy_sum",
        ]
        vals = pvals + [
            base.summ(hdelta, adelta), base.summ(hcpoed, acpoed), base.summ(hr, ar),
            hm + am, hpr + apr,
        ]
    return names, vals


def augmented_matrix(rows, team_k, qb_k, kind, variant):
    qb_fn = primary_features if variant == "primary" else room_features
    names = None
    data = []
    for r in rows:
        bn, bv = (base.spread_features(r, team_k) if kind == "spread" else base.total_features(r, team_k))
        qn, qv = qb_fn(r, kind, qb_k)
        if names is None:
            names = bn + qn
        data.append([np.nan if x is None else float(x) for x in (bv + qv)])
    return names, np.asarray(data, dtype=float)


def select_augmented_params(train_rows, kind, variant):
    fit_rows, val_rows = base.inner_split(train_rows)
    yfit = base.target_array(fit_rows, kind)
    yval = base.target_array(val_rows, kind)
    candidates = []
    for team_k in base.K_GRID:
        for qb_k in QB_K_GRID:
            names, Xfit = augmented_matrix(fit_rows, team_k, qb_k, kind, variant)
            _, Xval = augmented_matrix(val_rows, team_k, qb_k, kind, variant)
            prep = base.fit_preprocessor(Xfit)
            Xf, Xv = base.transform(Xfit, prep), base.transform(Xval, prep)
            for lam in base.LAMBDA_GRID:
                model = base.ridge_fit(Xf, yfit, lam)
                pred = base.predict(model, Xv)
                candidates.append({
                    "team_k": team_k,
                    "qb_k": qb_k,
                    "lambda": lam,
                    "mae": base.mae(yval, pred),
                    "rmse": base.rmse(yval, pred),
                    "n": len(val_rows),
                })
    candidates.sort(key=lambda x: (x["mae"], x["rmse"], x["lambda"], x["qb_k"]))
    return candidates[0], candidates[:12]


def fit_augmented(train_rows, test_rows, kind, variant, team_k, qb_k, lam):
    names, Xtr = augmented_matrix(train_rows, team_k, qb_k, kind, variant)
    _, Xte = augmented_matrix(test_rows, team_k, qb_k, kind, variant)
    prep = base.fit_preprocessor(Xtr)
    Xtrz, Xtez = base.transform(Xtr, prep), base.transform(Xte, prep)
    ytr = base.target_array(train_rows, kind)
    model = base.ridge_fit(Xtrz, ytr, lam)
    pred = base.predict(model, Xtez)
    coefs = {n: float(v) for n, v in zip(names, model[1])}
    return pred, coefs


def metrics(rows, pred, kind):
    y = base.target_array(rows, kind)
    return {
        "n": len(rows),
        "mae": round(base.mae(y, pred), 4),
        "rmse": round(base.rmse(y, pred), 4),
        "bias": round(base.bias(y, pred), 4),
        "market_reference_mae": round(base.market_mae(rows, kind), 4),
        "edge_grading": base.grading(rows, pred, kind),
    }


def weighted_aggregate(folds):
    total_n = sum(x["n"] for x in folds)
    out = {"n": total_n}
    for metric in ["mae", "rmse", "bias", "market_reference_mae"]:
        out[metric] = round(sum(x[metric] * x["n"] for x in folds) / total_n, 4)
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    qb_idx, qb_leakage, qb_rows = load_qb_index()
    if qb_leakage:
        raise RuntimeError(f"QB source leakage detected in {qb_leakage} snapshots")
    rows = attach_qb(base.load_rows(), qb_idx)

    all_predictions = []
    coef_rows = []
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "qb_source_rows": qb_rows,
        "qb_source_leakage_rows": qb_leakage,
        "market_policy": "BENCHMARK_ONLY_NOT_MODEL_FEATURE",
        "realized_target_game_starter_used": False,
        "variants": {},
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
    }

    fold_metrics = defaultdict(lambda: defaultdict(list))
    baseline_fold_metrics = defaultdict(list)

    for test_year in TARGET_YEARS:
        train_rows = [r for r in rows if r["season"] < test_year]
        test_rows = [r for r in rows if r["season"] == test_year]
        if not train_rows or not test_rows:
            raise RuntimeError(f"Bad outer fold for {test_year}")

        # Reproduce the team-only baseline on the exact same attached game rows.
        for kind in KINDS:
            best, _ = base.select_params(train_rows, kind)
            bpred, _, _, _, bcoefs = base.fit_and_predict(
                train_rows, test_rows, kind, best["k"], best["lambda"]
            )
            bm = metrics(test_rows, bpred, kind)
            bm.update({"season": test_year, "team_k": best["k"], "lambda": best["lambda"]})
            baseline_fold_metrics[kind].append(bm)
            for name, value in bcoefs.items():
                coef_rows.append({
                    "season": test_year, "kind": kind, "variant": "baseline",
                    "team_k": best["k"], "qb_k": "", "lambda": best["lambda"],
                    "feature": name, "standardized_coefficient": round(value, 7),
                })

            for variant in VARIANTS:
                best_aug, top = select_augmented_params(train_rows, kind, variant)
                pred, coefs = fit_augmented(
                    train_rows, test_rows, kind, variant,
                    best_aug["team_k"], best_aug["qb_k"], best_aug["lambda"],
                )
                m = metrics(test_rows, pred, kind)
                m.update({
                    "season": test_year,
                    "team_k": best_aug["team_k"],
                    "qb_k": best_aug["qb_k"],
                    "lambda": best_aug["lambda"],
                    "inner_validation_best_mae": round(best_aug["mae"], 4),
                    "inner_top_candidates": top,
                })
                fold_metrics[(variant, kind)]["folds"].append(m)
                for name, value in coefs.items():
                    coef_rows.append({
                        "season": test_year, "kind": kind, "variant": variant,
                        "team_k": best_aug["team_k"], "qb_k": best_aug["qb_k"],
                        "lambda": best_aug["lambda"], "feature": name,
                        "standardized_coefficient": round(value, 7),
                    })

                for r, p in zip(test_rows, pred):
                    all_predictions.append({
                        "game_id": r["game_id"], "season": r["season"], "week": r["week"],
                        "gameday": r["gameday"], "away_team": r["away_team"], "home_team": r["home_team"],
                        "kind": kind, "variant": variant,
                        "actual": r["home_margin"] if kind == "spread" else r["game_total"],
                        "prediction": round(float(p), 5),
                        "market_reference": r["market_home_spread_reference"] if kind == "spread" else r["market_total_reference"],
                        "market_policy": "BENCHMARK_ONLY_NOT_MODEL_FEATURE",
                        "release_state": "HOLD_RESEARCH_ONLY",
                    })

    # Build aggregate comparisons and conservative research verdicts.
    for kind in KINDS:
        bfolds = baseline_fold_metrics[kind]
        bagg = weighted_aggregate(bfolds)
        summary.setdefault("baseline", {})[kind] = {"folds": bfolds, "aggregate": bagg}
        for variant in VARIANTS:
            folds = fold_metrics[(variant, kind)]["folds"]
            agg = weighted_aggregate(folds)
            season_wins = sum(1 for f, b in zip(folds, bfolds) if f["mae"] < b["mae"])
            delta = round(agg["mae"] - bagg["mae"], 4)
            # This only earns *further testing*, never production promotion.
            further = delta <= -0.05 and season_wins >= 2
            summary["variants"].setdefault(variant, {})[kind] = {
                "folds": folds,
                "aggregate": agg,
                "mae_delta_vs_baseline": delta,
                "seasons_with_lower_mae": season_wins,
                "historical_verdict": "EARNED_FURTHER_TESTING" if further else "NO_PROMOTION",
                "production_verdict": "HOLD_RESEARCH_ONLY",
            }

    pred_path = OUT_DIR / "qb_room_v1_predictions.csv"
    coef_path = OUT_DIR / "qb_room_v1_coefficients.csv"
    qa_path = OUT_DIR / "qb_room_v1_qa.json"

    with pred_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_predictions[0].keys()))
        writer.writeheader(); writer.writerows(all_predictions)
    with coef_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(coef_rows[0].keys()))
        writer.writeheader(); writer.writerows(coef_rows)
    with qa_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(json.dumps({
        "qa": str(qa_path),
        "predictions": str(pred_path),
        "coefficients": str(coef_path),
        "baseline_spread_mae": summary["baseline"]["spread"]["aggregate"]["mae"],
        "baseline_total_mae": summary["baseline"]["total"]["aggregate"]["mae"],
        "primary_spread": summary["variants"]["primary"]["spread"],
        "room_spread": summary["variants"]["room"]["spread"],
        "primary_total": summary["variants"]["primary"]["total"],
        "room_total": summary["variants"]["room"]["total"],
        "release_state": "HOLD_RESEARCH_ONLY",
    }, indent=2))


if __name__ == "__main__":
    main()
