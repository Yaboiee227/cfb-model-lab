#!/usr/bin/env python3
"""Calibrate the frozen NFL research architecture on unseen 2023-2025 games.

Spread architecture: core + defensive coverage + win Elo + margin rating.
Total architecture: core only.

All hyperparameters are selected/frozen from 2022 only. Market lines are never
model inputs; they are used only to measure historical edge reliability. This
script produces research calibration/error bands and does not authorize release.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_coverage_v1 as cov
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_rating_system_robustness as rat

OUT = Path("nfl_data/validation/final_architecture_calibration.json")
YEARS = [2023, 2024, 2025]
RATING = {
    "elo_k": 40.0,
    "elo_hfa": 35.0,
    "offseason_regression": 0.25,
    "margin_k": 0.05,
    "margin_hfa": 3.0,
    "lambda": 100.0,
}
EDGE_BINS = [(0,1),(1,2),(2,3),(3,4),(4,5),(5,7),(7,float("inf"))]
EDGE_THRESHOLDS = [1,2,3,4,5,7]


def f(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):
        return None


def wilson(w, n, z=1.959963984540054):
    if n <= 0:
        return [None,None]
    p=w/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [round(center-half,4),round(center+half,4)]


def err_summary(actual, pred):
    y=np.asarray(actual,float); p=np.asarray(pred,float); e=p-y; ae=np.abs(e)
    return {
        "n":int(len(y)),
        "mae":round(float(np.mean(ae)),4),
        "rmse":round(float(np.sqrt(np.mean(e*e))),4),
        "bias_pred_minus_actual":round(float(np.mean(e)),4),
        "absolute_error_quantiles":{
            "p50":round(float(np.quantile(ae,.50)),3),
            "p68":round(float(np.quantile(ae,.68)),3),
            "p80":round(float(np.quantile(ae,.80)),3),
            "p90":round(float(np.quantile(ae,.90)),3),
            "p95":round(float(np.quantile(ae,.95)),3),
        },
    }


def grade_one(edge, result):
    if edge is None or result is None or abs(edge)<1e-12:
        return None
    if abs(result)<1e-12:
        return "P"
    return "W" if edge*result>0 else "L"


def bucket_label(lo,hi):
    return f"{lo:g}-{hi:g}" if math.isfinite(hi) else f">={lo:g}"


def edge_calibration(records, kind):
    rows=[]
    for r in records:
        if kind=="spread":
            line=f(r.get("market_home_spread_reference")); pred=f(r.get("pred_home_margin")); actual=f(r.get("actual_home_margin"))
            if line is None or pred is None or actual is None: continue
            edge=pred+line; result=actual+line
        else:
            line=f(r.get("market_total_reference")); pred=f(r.get("pred_total")); actual=f(r.get("actual_total"))
            if line is None or pred is None or actual is None: continue
            edge=pred-line; result=actual-line
        rows.append((abs(edge),grade_one(edge,result)))

    by_bin={}
    for lo,hi in EDGE_BINS:
        subset=[g for ae,g in rows if ae>=lo and ae<hi and g is not None]
        w=sum(g=="W" for g in subset); l=sum(g=="L" for g in subset); p=sum(g=="P" for g in subset); n=w+l
        by_bin[bucket_label(lo,hi)]={
            "bets_including_pushes":len(subset),"wins":w,"losses":l,"pushes":p,
            "decided":n,"win_rate":None if not n else round(w/n,4),
            "wilson_95_ci":wilson(w,n),
        }
    by_threshold={}
    for t in EDGE_THRESHOLDS:
        subset=[g for ae,g in rows if ae>=t and g is not None]
        w=sum(g=="W" for g in subset); l=sum(g=="L" for g in subset); p=sum(g=="P" for g in subset); n=w+l
        by_threshold[str(t)]={
            "bets_including_pushes":len(subset),"wins":w,"losses":l,"pushes":p,
            "decided":n,"win_rate":None if not n else round(w/n,4),
            "wilson_95_ci":wilson(w,n),
            "beats_52_38pct_point_estimate":False if not n else (w/n)>0.5238,
            "lower_ci_above_50pct":False if not n else wilson(w,n)[0]>0.5,
        }
    return {"edge_bins":by_bin,"edge_thresholds":by_threshold,"note":"Schedule/closing reference lines are benchmark-only. No profitability claim is made without executable odds."}


def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    base_rows=base.load_rows()
    ni,nl,_=ngs.load_index(); ci,cl,_=cov.loadidx(cov.COV,"cov")
    if nl+cl:
        raise RuntimeError(f"source leakage ngs={nl} coverage={cl}")
    covrows=cov.attach(base_rows,ci,ni)
    c22=[r for r in covrows if r["season"]==2022]
    cp,_=cov.select(c22,"spread","coverage")
    b22=[r for r in base_rows if r["season"]==2022]
    tp,_=base.select_params(b22,"total")

    games=rat.fetch_games()
    rmap=rat.rating_maps(games,RATING["elo_k"],RATING["elo_hfa"],RATING["offseason_regression"],RATING["margin_k"],RATING["margin_hfa"])
    rated=rat.attach(covrows,rmap)
    rated_lookup={r["game_id"]:r for r in rated}

    records=[]; folds={}
    for y in YEARS:
        tr_s=[r for r in rated if r["season"]<y]; te_s=[r for r in rated if r["season"]==y]
        fo=rat.fit(tr_s,"both",cp["team_k"],RATING["lambda"],cp["feature_k"])
        ps=rat.pred(te_s,"both",cp["team_k"],cp["feature_k"],fo)

        tr_t=[r for r in base_rows if r["season"]<y]; te_t=[r for r in base_rows if r["season"]==y]
        pt,_,_,_,_=base.fit_and_predict(tr_t,te_t,"total",tp["k"],tp["lambda"])
        tlookup={r["game_id"]:(r,p) for r,p in zip(te_t,pt)}
        if len(te_s)!=len(te_t): raise RuntimeError(f"fold size mismatch {y}")

        spread_actual=[]; spread_pred=[]; total_actual=[]; total_pred=[]
        for r,p_sp in zip(te_s,ps):
            br,p_to=tlookup[r["game_id"]]
            rec={
                "game_id":r["game_id"],"season":y,"week":r["week"],
                "actual_home_margin":float(r["home_margin"]),"pred_home_margin":float(p_sp),
                "actual_total":float(br["game_total"]),"pred_total":float(p_to),
                "market_home_spread_reference":r.get("market_home_spread_reference"),
                "market_total_reference":br.get("market_total_reference"),
            }
            records.append(rec)
            spread_actual.append(rec["actual_home_margin"]); spread_pred.append(rec["pred_home_margin"])
            total_actual.append(rec["actual_total"]); total_pred.append(rec["pred_total"])
        folds[str(y)]={"spread":err_summary(spread_actual,spread_pred),"total":err_summary(total_actual,total_pred)}

    sa=[r["actual_home_margin"] for r in records]; sp=[r["pred_home_margin"] for r in records]
    ta=[r["actual_total"] for r in records]; tpv=[r["pred_total"] for r in records]
    result={
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "architecture":{
            "spread":"frozen core + defensive coverage + win Elo + margin rating",
            "total":"frozen core only",
            "market_policy":"market excluded from fitting/tuning; benchmark/edge grading only",
            "spread_params":{"coverage":cp,"ratings":RATING},
            "total_params":tp,
        },
        "folds":folds,
        "aggregate":{
            "spread":err_summary(sa,sp),"total":err_summary(ta,tpv),
            "spread_edge_calibration":edge_calibration(records,"spread"),
            "total_edge_calibration":edge_calibration(records,"total"),
        },
        "confidence_release_rule":"No confidence tier or alternative line is production-authorized solely from these retrospective bins. Require prospective validation and executable prices.",
        "production_verdict":"HOLD_PROSPECTIVE_VALIDATION_REQUIRED",
        "website_publish_allowed":False,
    }
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"spread":result["aggregate"]["spread"],"total":result["aggregate"]["total"],"spread_edges":result["aggregate"]["spread_edge_calibration"]["edge_thresholds"],"total_edges":result["aggregate"]["total_edge_calibration"]["edge_thresholds"]},indent=2))

if __name__=="__main__":
    main()
