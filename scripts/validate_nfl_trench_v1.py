#!/usr/bin/env python3
"""Walk-forward validation for NFL trench / pressure candidates.

Variants:
- pressure: PFR/nflverse pass-protection + pass-rush features
- pressure_continuity: pressure features plus OL snap continuity

Outer folds are identical to the frozen baseline: 2023, 2024, 2025 unseen.
Market lines are benchmark/grading only. Development only / HOLD.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base  # noqa: E402

TRENCH_FILE = Path("nfl_data/historical/team_week_trench_2022_2025.csv")
OUT_DIR = Path("nfl_data/validation")
TARGET_YEARS = [2023, 2024, 2025]
TRENCH_K_GRID = [1.0, 2.0, 4.0, 8.0, 16.0]
VARIANTS = ["pressure", "pressure_continuity"]
KINDS = ["spread", "total"]

PRESSURE = [
    "off_pressure_rate", "off_hurry_rate", "off_hit_rate", "off_sack_rate_pfr",
    "off_blitz_faced_rate", "off_pressure_to_sack",
    "def_pressure_events_per_db", "def_hurry_events_per_db", "def_hit_events_per_db",
    "def_sack_rate_pfr", "def_blitzer_events_per_db", "def_pressure_to_sack",
]
CONTINUITY = [
    "ol_last_top5_overlap", "ol_last3_top5_overlap", "ol_last_top5_avg_snap_pct",
    "ol_last_full_snap_count", "ol_last_half_snap_count", "ol_cumulative_top5_concentration",
    "ol_cumulative_unique_players",
]


def tf(v): return base.to_float(v)


def load_index():
    with TRENCH_FILE.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    idx = {}; leakage = 0
    for r in rows:
        season = int(float(r["season"])); week = int(float(r["target_week"])); team = r["team"]
        if int(float(r.get("max_current_week_used") or 0)) >= week: leakage += 1
        key = (season, week, team)
        if key in idx: raise RuntimeError(f"Duplicate trench snapshot {key}")
        idx[key] = r
    return idx, leakage, len(rows)


def attach(game_rows, idx):
    out = []; missing = []
    for r in game_rows:
        h = idx.get((r["season"], r["week"], r["home_team"]))
        a = idx.get((r["season"], r["week"], r["away_team"]))
        if h is None or a is None:
            missing.append(r["game_id"]); continue
        x = dict(r)
        for side, row in (("home", h), ("away", a)):
            for k, v in row.items():
                if k in {"season", "target_week", "team", "release_state"}: continue
                x[f"{side}_tr_{k}"] = v
        out.append(x)
    if missing:
        raise RuntimeError(f"Missing trench snapshots for {len(missing)} games; first={missing[:5]}")
    return out


def blend_metric(r, side, metric, k):
    games = tf(r.get(f"{side}_tr_games_before")) or 0.0
    cur, prior = tf(r.get(f"{side}_tr_cur_{metric}")), tf(r.get(f"{side}_tr_prior_{metric}"))
    if cur is not None and prior is not None: return (games * cur + k * prior) / (games + k)
    if cur is not None: return cur
    if prior is not None: return prior
    return None


def current_metric(r, side, metric):
    return tf(r.get(f"{side}_tr_cur_{metric}"))


def last3_metric(r, side, metric):
    return tf(r.get(f"{side}_tr_last3_{metric}"))


def pressure_features(r, kind, k):
    h = {m: blend_metric(r, "home", m, k) for m in PRESSURE}
    a = {m: blend_metric(r, "away", m, k) for m in PRESSURE}
    # Matchup constructs deliberately compare offense exposure with opponent defensive disruption.
    hm = None if h["off_pressure_rate"] is None or a["def_pressure_events_per_db"] is None else h["off_pressure_rate"] + a["def_pressure_events_per_db"]
    am = None if a["off_pressure_rate"] is None or h["def_pressure_events_per_db"] is None else a["off_pressure_rate"] + h["def_pressure_events_per_db"]
    if kind == "spread":
        names = [
            "tr_off_pressure_diff", "tr_def_pressure_events_diff", "tr_pressure_matchup_diff",
            "tr_off_hurry_diff", "tr_off_hit_diff", "tr_off_sack_diff", "tr_off_blitz_faced_diff",
            "tr_off_pressure_to_sack_diff", "tr_def_hurry_events_diff", "tr_def_hit_events_diff",
            "tr_def_sack_diff", "tr_def_blitzer_events_diff", "tr_def_pressure_to_sack_diff",
        ]
        vals = [
            base.diff(h["off_pressure_rate"], a["off_pressure_rate"]),
            base.diff(h["def_pressure_events_per_db"], a["def_pressure_events_per_db"]), base.diff(hm, am),
            base.diff(h["off_hurry_rate"], a["off_hurry_rate"]), base.diff(h["off_hit_rate"], a["off_hit_rate"]),
            base.diff(h["off_sack_rate_pfr"], a["off_sack_rate_pfr"]), base.diff(h["off_blitz_faced_rate"], a["off_blitz_faced_rate"]),
            base.diff(h["off_pressure_to_sack"], a["off_pressure_to_sack"]),
            base.diff(h["def_hurry_events_per_db"], a["def_hurry_events_per_db"]), base.diff(h["def_hit_events_per_db"], a["def_hit_events_per_db"]),
            base.diff(h["def_sack_rate_pfr"], a["def_sack_rate_pfr"]), base.diff(h["def_blitzer_events_per_db"], a["def_blitzer_events_per_db"]),
            base.diff(h["def_pressure_to_sack"], a["def_pressure_to_sack"]),
        ]
    else:
        names = [
            "tr_off_pressure_sum", "tr_def_pressure_events_sum", "tr_pressure_matchup_sum",
            "tr_off_hurry_sum", "tr_off_hit_sum", "tr_off_sack_sum", "tr_off_blitz_faced_sum",
            "tr_off_pressure_to_sack_sum", "tr_def_hurry_events_sum", "tr_def_hit_events_sum",
            "tr_def_sack_sum", "tr_def_blitzer_events_sum", "tr_def_pressure_to_sack_sum",
        ]
        vals = [
            base.summ(h["off_pressure_rate"], a["off_pressure_rate"]),
            base.summ(h["def_pressure_events_per_db"], a["def_pressure_events_per_db"]), base.summ(hm, am),
            base.summ(h["off_hurry_rate"], a["off_hurry_rate"]), base.summ(h["off_hit_rate"], a["off_hit_rate"]),
            base.summ(h["off_sack_rate_pfr"], a["off_sack_rate_pfr"]), base.summ(h["off_blitz_faced_rate"], a["off_blitz_faced_rate"]),
            base.summ(h["off_pressure_to_sack"], a["off_pressure_to_sack"]),
            base.summ(h["def_hurry_events_per_db"], a["def_hurry_events_per_db"]), base.summ(h["def_hit_events_per_db"], a["def_hit_events_per_db"]),
            base.summ(h["def_sack_rate_pfr"], a["def_sack_rate_pfr"]), base.summ(h["def_blitzer_events_per_db"], a["def_blitzer_events_per_db"]),
            base.summ(h["def_pressure_to_sack"], a["def_pressure_to_sack"]),
        ]
    return names, vals


def continuity_features(r, kind):
    # Continuity is inherently recent/current; no prior-season blend is imposed.
    hv = {m: current_metric(r, "home", m) for m in CONTINUITY}
    av = {m: current_metric(r, "away", m) for m in CONTINUITY}
    hl = {m: last3_metric(r, "home", m) for m in CONTINUITY}
    al = {m: last3_metric(r, "away", m) for m in CONTINUITY}
    if kind == "spread":
        names = [
            "ol_top5_overlap_diff", "ol_last3_overlap_diff", "ol_top5_avg_pct_diff",
            "ol_full_snap_count_diff", "ol_half_snap_count_diff", "ol_top5_concentration_diff",
            "ol_unique_players_diff", "ol_recent_overlap_diff",
        ]
        vals = [
            base.diff(hv["ol_last_top5_overlap"], av["ol_last_top5_overlap"]),
            base.diff(hv["ol_last3_top5_overlap"], av["ol_last3_top5_overlap"]),
            base.diff(hv["ol_last_top5_avg_snap_pct"], av["ol_last_top5_avg_snap_pct"]),
            base.diff(hv["ol_last_full_snap_count"], av["ol_last_full_snap_count"]),
            base.diff(hv["ol_last_half_snap_count"], av["ol_last_half_snap_count"]),
            base.diff(hv["ol_cumulative_top5_concentration"], av["ol_cumulative_top5_concentration"]),
            base.diff(hv["ol_cumulative_unique_players"], av["ol_cumulative_unique_players"]),
            base.diff(hl["ol_last_top5_overlap"], al["ol_last_top5_overlap"]),
        ]
    else:
        names = [
            "ol_top5_overlap_sum", "ol_last3_overlap_sum", "ol_top5_avg_pct_sum",
            "ol_full_snap_count_sum", "ol_half_snap_count_sum", "ol_top5_concentration_sum",
            "ol_unique_players_sum", "ol_recent_overlap_sum",
        ]
        vals = [
            base.summ(hv["ol_last_top5_overlap"], av["ol_last_top5_overlap"]),
            base.summ(hv["ol_last3_top5_overlap"], av["ol_last3_top5_overlap"]),
            base.summ(hv["ol_last_top5_avg_snap_pct"], av["ol_last_top5_avg_snap_pct"]),
            base.summ(hv["ol_last_full_snap_count"], av["ol_last_full_snap_count"]),
            base.summ(hv["ol_last_half_snap_count"], av["ol_last_half_snap_count"]),
            base.summ(hv["ol_cumulative_top5_concentration"], av["ol_cumulative_top5_concentration"]),
            base.summ(hv["ol_cumulative_unique_players"], av["ol_cumulative_unique_players"]),
            base.summ(hl["ol_last_top5_overlap"], al["ol_last_top5_overlap"]),
        ]
    return names, vals


def augmented_matrix(rows, team_k, trench_k, kind, variant):
    names = None; data = []
    for r in rows:
        bn, bv = (base.spread_features(r, team_k) if kind == "spread" else base.total_features(r, team_k))
        pn, pv = pressure_features(r, kind, trench_k)
        if variant == "pressure_continuity":
            cn, cv = continuity_features(r, kind); n, v = bn + pn + cn, bv + pv + cv
        else:
            n, v = bn + pn, bv + pv
        if names is None: names = n
        data.append([np.nan if x is None else float(x) for x in v])
    return names, np.asarray(data, dtype=float)


def select_params(train_rows, kind, variant):
    fit_rows, val_rows = base.inner_split(train_rows)
    yfit, yval = base.target_array(fit_rows, kind), base.target_array(val_rows, kind)
    candidates = []
    for team_k in base.K_GRID:
        for trench_k in TRENCH_K_GRID:
            names, Xf = augmented_matrix(fit_rows, team_k, trench_k, kind, variant)
            _, Xv = augmented_matrix(val_rows, team_k, trench_k, kind, variant)
            prep = base.fit_preprocessor(Xf); Xfz, Xvz = base.transform(Xf, prep), base.transform(Xv, prep)
            for lam in base.LAMBDA_GRID:
                model = base.ridge_fit(Xfz, yfit, lam); pred = base.predict(model, Xvz)
                candidates.append({"team_k": team_k, "trench_k": trench_k, "lambda": lam, "mae": base.mae(yval, pred), "rmse": base.rmse(yval, pred), "n": len(val_rows)})
    candidates.sort(key=lambda x: (x["mae"], x["rmse"], x["lambda"], x["trench_k"]))
    return candidates[0], candidates[:12]


def fit_aug(train_rows, test_rows, kind, variant, team_k, trench_k, lam):
    names, Xtr = augmented_matrix(train_rows, team_k, trench_k, kind, variant)
    _, Xte = augmented_matrix(test_rows, team_k, trench_k, kind, variant)
    prep = base.fit_preprocessor(Xtr); Xtrz, Xtez = base.transform(Xtr, prep), base.transform(Xte, prep)
    y = base.target_array(train_rows, kind); model = base.ridge_fit(Xtrz, y, lam); pred = base.predict(model, Xtez)
    return pred, {n: float(v) for n, v in zip(names, model[1])}


def metrics(rows, pred, kind):
    y = base.target_array(rows, kind)
    return {"n": len(rows), "mae": round(base.mae(y, pred),4), "rmse": round(base.rmse(y,pred),4), "bias": round(base.bias(y,pred),4), "market_reference_mae": round(base.market_mae(rows,kind),4), "edge_grading": base.grading(rows,pred,kind)}


def aggregate(folds):
    n = sum(f["n"] for f in folds)
    return {"n": n, **{m: round(sum(f[m]*f["n"] for f in folds)/n,4) for m in ["mae","rmse","bias","market_reference_mae"]}}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    idx, leakage, source_rows = load_index()
    if leakage: raise RuntimeError(f"Trench source leakage rows={leakage}")
    rows = attach(base.load_rows(), idx)
    summary = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "source_rows": source_rows, "source_leakage_rows": leakage, "market_policy": "BENCHMARK_ONLY_NOT_MODEL_FEATURE", "variants": {}, "release_state": "HOLD_RESEARCH_ONLY", "website_publish_allowed": False}
    preds_out = []; coef_out = []; baseline_folds = defaultdict(list); variant_folds = defaultdict(list)

    for year in TARGET_YEARS:
        train = [r for r in rows if r["season"] < year]; test = [r for r in rows if r["season"] == year]
        for kind in KINDS:
            best, _ = base.select_params(train, kind)
            bpred, _, _, _, bcoef = base.fit_and_predict(train, test, kind, best["k"], best["lambda"])
            bm = metrics(test, bpred, kind); bm.update({"season": year, "team_k": best["k"], "lambda": best["lambda"]}); baseline_folds[kind].append(bm)
            for n, v in bcoef.items(): coef_out.append({"season":year,"kind":kind,"variant":"baseline","team_k":best["k"],"trench_k":"","lambda":best["lambda"],"feature":n,"standardized_coefficient":round(v,7)})

            for variant in VARIANTS:
                ba, top = select_params(train, kind, variant)
                pred, coef = fit_aug(train, test, kind, variant, ba["team_k"], ba["trench_k"], ba["lambda"])
                m = metrics(test, pred, kind); m.update({"season":year,"team_k":ba["team_k"],"trench_k":ba["trench_k"],"lambda":ba["lambda"],"inner_validation_best_mae":round(ba["mae"],4),"inner_top_candidates":top}); variant_folds[(variant,kind)].append(m)
                for n, v in coef.items(): coef_out.append({"season":year,"kind":kind,"variant":variant,"team_k":ba["team_k"],"trench_k":ba["trench_k"],"lambda":ba["lambda"],"feature":n,"standardized_coefficient":round(v,7)})
                for r, p in zip(test,pred): preds_out.append({"game_id":r["game_id"],"season":r["season"],"week":r["week"],"gameday":r["gameday"],"away_team":r["away_team"],"home_team":r["home_team"],"kind":kind,"variant":variant,"actual":r["home_margin"] if kind=="spread" else r["game_total"],"prediction":round(float(p),5),"market_reference":r["market_home_spread_reference"] if kind=="spread" else r["market_total_reference"],"market_policy":"BENCHMARK_ONLY_NOT_MODEL_FEATURE","release_state":"HOLD_RESEARCH_ONLY"})

    summary["baseline"] = {}
    for kind in KINDS:
        bf = baseline_folds[kind]; bagg = aggregate(bf); summary["baseline"][kind] = {"folds":bf,"aggregate":bagg}
        for variant in VARIANTS:
            vf = variant_folds[(variant,kind)]; agg = aggregate(vf); wins = sum(1 for f,b in zip(vf,bf) if f["mae"] < b["mae"]); delta = round(agg["mae"]-bagg["mae"],4)
            further = delta <= -0.05 and wins >= 2
            summary["variants"].setdefault(variant,{})[kind] = {"folds":vf,"aggregate":agg,"mae_delta_vs_baseline":delta,"seasons_with_lower_mae":wins,"historical_verdict":"EARNED_FURTHER_TESTING" if further else "NO_PROMOTION","production_verdict":"HOLD_RESEARCH_ONLY"}

    ppath=OUT_DIR/"trench_v1_predictions.csv"; cpath=OUT_DIR/"trench_v1_coefficients.csv"; qpath=OUT_DIR/"trench_v1_qa.json"
    with ppath.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(preds_out[0].keys())); w.writeheader(); w.writerows(preds_out)
    with cpath.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(coef_out[0].keys())); w.writeheader(); w.writerows(coef_out)
    qpath.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"qa":str(qpath),"baseline":{k:summary["baseline"][k]["aggregate"] for k in KINDS},"pressure":summary["variants"]["pressure"],"pressure_continuity":summary["variants"]["pressure_continuity"],"release_state":"HOLD_RESEARCH_ONLY"},indent=2))

if __name__ == "__main__": main()
