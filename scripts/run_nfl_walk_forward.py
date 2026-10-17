#!/usr/bin/env python3
"""Run market-independent NFL spread and total walk-forward baselines.

Outer validation folds:
- 2023: train on 2022
- 2024: train on 2022-2023
- 2025: train on 2022-2024

Hyperparameters are selected only inside the available training seasons using a
blocked late-season validation slice. Market lines are never model features or
tuning targets; they are retained only for post-prediction benchmarking and
research grading. All outputs remain HOLD / RESEARCH ONLY.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

INFILE = Path("nfl_data/historical/game_pregame_features_2022_2025.csv")
OUT_DIR = Path("nfl_data/validation")
TARGET_YEARS = [2023, 2024, 2025]
K_GRID = [1.0, 2.0, 3.0, 4.0, 6.0, 8.0]
LAMBDA_GRID = [0.1, 1.0, 3.0, 10.0, 30.0, 100.0]
EDGE_THRESHOLDS = [1.0, 2.0, 3.0, 4.0, 5.0]

CORE_BLEND = [
    "off_epa", "def_epa_allowed", "net_epa",
    "off_success", "def_success_allowed", "net_success",
    "off_pass_epa", "off_rush_epa", "off_sack_rate", "def_sack_rate_forced",
]


def to_float(v):
    if v is None: return None
    s = str(v).strip()
    if not s or s.lower() in {"na","nan","none","null"}: return None
    try:
        x = float(s); return x if math.isfinite(x) else None
    except ValueError: return None


def load_rows():
    with INFILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["season"] = int(float(r["season"])); r["week"] = int(float(r["week"]))
    rows.sort(key=lambda r: (r["season"], r["week"], r["gameday"], r["game_id"]))
    return rows


def blend(r, side, metric, k):
    games = to_float(r.get(f"{side}_games_before")) or 0.0
    cur = to_float(r.get(f"{side}_std_{metric}"))
    prior = to_float(r.get(f"{side}_prior_{metric}"))
    if cur is not None and prior is not None:
        return (games * cur + k * prior) / (games + k)
    if cur is not None: return cur
    if prior is not None: return prior
    return None


def raw(r, side, metric):
    return to_float(r.get(f"{side}_std_{metric}"))


def last3(r, side, metric):
    return to_float(r.get(f"{side}_last3_{metric}"))


def diff(a,b): return None if a is None or b is None else a-b

def summ(a,b): return None if a is None or b is None else a+b


def spread_features(r, k):
    h = lambda m: blend(r,"home",m,k)
    a = lambda m: blend(r,"away",m,k)
    hr = lambda m: raw(r,"home",m)
    ar = lambda m: raw(r,"away",m)
    hl = lambda m: last3(r,"home",m)
    al = lambda m: last3(r,"away",m)

    # Matchup residuals are deliberately raw/current where no safe prior-season
    # defensive counterpart exists; missing early-week values are train-median imputed.
    hp = None if h("off_pass_epa") is None or ar("def_pass_epa_allowed") is None else h("off_pass_epa") - ar("def_pass_epa_allowed")
    ap = None if a("off_pass_epa") is None or hr("def_pass_epa_allowed") is None else a("off_pass_epa") - hr("def_pass_epa_allowed")
    hru = None if h("off_rush_epa") is None or ar("def_rush_epa_allowed") is None else h("off_rush_epa") - ar("def_rush_epa_allowed")
    aru = None if a("off_rush_epa") is None or hr("def_rush_epa_allowed") is None else a("off_rush_epa") - hr("def_rush_epa_allowed")
    hxp = None if hr("off_pass20_rate") is None or ar("def_pass20_rate_allowed") is None else hr("off_pass20_rate") - ar("def_pass20_rate_allowed")
    axp = None if ar("off_pass20_rate") is None or hr("def_pass20_rate_allowed") is None else ar("off_pass20_rate") - hr("def_pass20_rate_allowed")
    hxr = None if hr("off_rush10_rate") is None or ar("def_rush10_rate_allowed") is None else hr("off_rush10_rate") - ar("def_rush10_rate_allowed")
    axr = None if ar("off_rush10_rate") is None or hr("def_rush10_rate_allowed") is None else ar("off_rush10_rate") - hr("def_rush10_rate_allowed")
    hsack = None if h("def_sack_rate_forced") is None or a("off_sack_rate") is None else h("def_sack_rate_forced") - a("off_sack_rate")
    asack = None if a("def_sack_rate_forced") is None or h("off_sack_rate") is None else a("def_sack_rate_forced") - h("off_sack_rate")
    rest_h, rest_a = to_float(r.get("home_rest")), to_float(r.get("away_rest"))

    names = [
        "blend_net_epa_diff","blend_net_success_diff","last3_net_epa_diff","last3_net_success_diff",
        "pass_matchup_diff","rush_matchup_diff","explosive_pass_matchup_diff","explosive_rush_matchup_diff",
        "sack_matchup_diff","neutral_ed_pass_rate_diff","rest_diff","neutral_site",
    ]
    vals = [
        diff(h("net_epa"),a("net_epa")), diff(h("net_success"),a("net_success")),
        diff(hl("net_epa"),al("net_epa")), diff(hl("net_success"),al("net_success")),
        diff(hp,ap), diff(hru,aru), diff(hxp,axp), diff(hxr,axr), diff(hsack,asack),
        diff(hr("off_neutral_ed_pass_rate"), ar("off_neutral_ed_pass_rate")),
        diff(rest_h,rest_a), to_float(r.get("neutral_site")),
    ]
    return names, vals


def total_features(r, k):
    h = lambda m: blend(r,"home",m,k)
    a = lambda m: blend(r,"away",m,k)
    hr = lambda m: raw(r,"home",m)
    ar = lambda m: raw(r,"away",m)
    hl = lambda m: last3(r,"home",m)
    al = lambda m: last3(r,"away",m)
    pass_strength_h = None if h("off_pass_epa") is None or ar("def_pass_epa_allowed") is None else h("off_pass_epa") + ar("def_pass_epa_allowed")
    pass_strength_a = None if a("off_pass_epa") is None or hr("def_pass_epa_allowed") is None else a("off_pass_epa") + hr("def_pass_epa_allowed")
    rush_strength_h = None if h("off_rush_epa") is None or ar("def_rush_epa_allowed") is None else h("off_rush_epa") + ar("def_rush_epa_allowed")
    rush_strength_a = None if a("off_rush_epa") is None or hr("def_rush_epa_allowed") is None else a("off_rush_epa") + hr("def_rush_epa_allowed")
    exp_pass_h = None if hr("off_pass20_rate") is None or ar("def_pass20_rate_allowed") is None else hr("off_pass20_rate") + ar("def_pass20_rate_allowed")
    exp_pass_a = None if ar("off_pass20_rate") is None or hr("def_pass20_rate_allowed") is None else ar("off_pass20_rate") + hr("def_pass20_rate_allowed")
    exp_rush_h = None if hr("off_rush10_rate") is None or ar("def_rush10_rate_allowed") is None else hr("off_rush10_rate") + ar("def_rush10_rate_allowed")
    exp_rush_a = None if ar("off_rush10_rate") is None or hr("def_rush10_rate_allowed") is None else ar("off_rush10_rate") + hr("def_rush10_rate_allowed")
    sack_drag_h = None if h("off_sack_rate") is None or a("def_sack_rate_forced") is None else h("off_sack_rate") + a("def_sack_rate_forced")
    sack_drag_a = None if a("off_sack_rate") is None or h("def_sack_rate_forced") is None else a("off_sack_rate") + h("def_sack_rate_forced")
    rest_h, rest_a = to_float(r.get("home_rest")), to_float(r.get("away_rest"))

    names = [
        "blend_off_epa_sum","blend_def_epa_allowed_sum","blend_off_success_sum","blend_def_success_allowed_sum",
        "last3_off_epa_sum","last3_def_epa_allowed_sum","pass_matchup_strength_sum","rush_matchup_strength_sum",
        "explosive_pass_context_sum","explosive_rush_context_sum","sack_context_sum","neutral_ed_pass_rate_sum",
        "rest_sum","rest_abs_diff","neutral_site",
    ]
    vals = [
        summ(h("off_epa"),a("off_epa")), summ(h("def_epa_allowed"),a("def_epa_allowed")),
        summ(h("off_success"),a("off_success")), summ(h("def_success_allowed"),a("def_success_allowed")),
        summ(hl("off_epa"),al("off_epa")), summ(hl("def_epa_allowed"),al("def_epa_allowed")),
        summ(pass_strength_h,pass_strength_a), summ(rush_strength_h,rush_strength_a),
        summ(exp_pass_h,exp_pass_a), summ(exp_rush_h,exp_rush_a), summ(sack_drag_h,sack_drag_a),
        summ(hr("off_neutral_ed_pass_rate"),ar("off_neutral_ed_pass_rate")), summ(rest_h,rest_a),
        None if rest_h is None or rest_a is None else abs(rest_h-rest_a), to_float(r.get("neutral_site")),
    ]
    return names, vals


def matrix(rows, k, kind):
    fn = spread_features if kind == "spread" else total_features
    names = None; data = []
    for r in rows:
        n,v = fn(r,k)
        if names is None: names=n
        data.append([np.nan if x is None else float(x) for x in v])
    return names, np.asarray(data,dtype=float)


def fit_preprocessor(X):
    med = np.nanmedian(X,axis=0)
    med = np.where(np.isfinite(med),med,0.0)
    Xi = np.where(np.isnan(X),med,X)
    mean = Xi.mean(axis=0); std = Xi.std(axis=0)
    std = np.where(std < 1e-9,1.0,std)
    return med,mean,std


def transform(X,prep):
    med,mean,std=prep
    Xi=np.where(np.isnan(X),med,X)
    return (Xi-mean)/std


def ridge_fit(X,y,lam):
    ymean=float(np.mean(y)); yc=y-ymean
    A=X.T@X + lam*np.eye(X.shape[1])
    try: beta=np.linalg.solve(A,X.T@yc)
    except np.linalg.LinAlgError: beta=np.linalg.pinv(A)@(X.T@yc)
    return ymean,beta


def predict(model,X):
    intercept,beta=model
    return intercept + X@beta


def mae(y,p): return float(np.mean(np.abs(y-p)))
def rmse(y,p): return float(np.sqrt(np.mean((y-p)**2)))
def bias(y,p): return float(np.mean(p-y))


def target_array(rows,kind):
    key="home_margin" if kind=="spread" else "game_total"
    return np.asarray([float(r[key]) for r in rows],dtype=float)


def inner_split(train_rows):
    latest=max(r["season"] for r in train_rows)
    val=[r for r in train_rows if r["season"]==latest and r["week"]>=13]
    fit=[r for r in train_rows if not (r["season"]==latest and r["week"]>=13)]
    if len(val)<30 or len(fit)<100:
        # conservative fallback: final four weeks of latest training season
        maxw=max(r["week"] for r in train_rows if r["season"]==latest)
        cut=maxw-3
        val=[r for r in train_rows if r["season"]==latest and r["week"]>=cut]
        fit=[r for r in train_rows if not (r["season"]==latest and r["week"]>=cut)]
    return fit,val


def select_params(train_rows,kind):
    fit_rows,val_rows=inner_split(train_rows)
    yfit=target_array(fit_rows,kind); yval=target_array(val_rows,kind)
    candidates=[]
    for k in K_GRID:
        names,Xfit=matrix(fit_rows,k,kind); _,Xval=matrix(val_rows,k,kind)
        prep=fit_preprocessor(Xfit); Xf=transform(Xfit,prep); Xv=transform(Xval,prep)
        for lam in LAMBDA_GRID:
            model=ridge_fit(Xf,yfit,lam); pred=predict(model,Xv)
            candidates.append({"k":k,"lambda":lam,"mae":mae(yval,pred),"rmse":rmse(yval,pred),"n":len(val_rows)})
    candidates.sort(key=lambda x:(x["mae"],x["rmse"],x["lambda"]))
    return candidates[0],candidates[:10]


def fit_and_predict(train_rows,test_rows,kind,k,lam):
    names,Xtr=matrix(train_rows,k,kind); _,Xte=matrix(test_rows,k,kind)
    prep=fit_preprocessor(Xtr); Xtrz=transform(Xtr,prep); Xtez=transform(Xte,prep)
    ytr=target_array(train_rows,kind); model=ridge_fit(Xtrz,ytr,lam); pred=predict(model,Xtez)
    coefs={name:float(beta) for name,beta in zip(names,model[1])}
    return pred,model,prep,names,coefs


def grading(rows,preds,kind):
    out={}
    for t in EDGE_THRESHOLDS:
        wins=losses=pushes=0
        for r,p in zip(rows,preds):
            if kind=="spread":
                line=to_float(r.get("market_home_spread_reference")); actual=float(r["home_margin"])
                if line is None: continue
                edge=p+line; result=actual+line
            else:
                line=to_float(r.get("market_total_reference")); actual=float(r["game_total"])
                if line is None: continue
                edge=p-line; result=actual-line
            if abs(edge)<t or abs(edge)<1e-12: continue
            if abs(result)<1e-12: pushes+=1
            elif edge*result>0: wins+=1
            else: losses+=1
        decided=wins+losses
        out[str(int(t))]={"n":decided+pushes,"wins":wins,"losses":losses,"pushes":pushes,"win_rate":None if not decided else round(wins/decided,4)}
    return out


def market_mae(rows,kind):
    ys=[]; ps=[]
    for r in rows:
        if kind=="spread":
            q=to_float(r.get("market_home_spread_reference")); y=to_float(r.get("home_margin")); p=None if q is None else -q
        else:
            q=to_float(r.get("market_total_reference")); y=to_float(r.get("game_total")); p=q
        if y is not None and p is not None: ys.append(y); ps.append(p)
    return None if not ys else mae(np.asarray(ys),np.asarray(ps))


def summarize_fold(train_rows,test_rows,preds,kind,params):
    y=target_array(test_rows,kind)
    train_y=target_array(train_rows,kind); naive=np.full_like(y,float(np.mean(train_y)))
    return {
        "train_games":len(train_rows),"test_games":len(test_rows),"k":params["k"],"lambda":params["lambda"],
        "mae":round(mae(y,preds),4),"rmse":round(rmse(y,preds),4),"bias_pred_minus_actual":round(bias(y,preds),4),
        "training_mean_baseline_mae":round(mae(y,naive),4),
        "market_reference_mae":None if (m:=market_mae(test_rows,kind)) is None else round(m,4),
        "research_grading_by_edge":grading(test_rows,preds,kind),
    }


def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    rows=load_rows(); predictions=[]; coeff_rows=[]
    summary={
        "architecture":"season-level outer walk-forward; blocked late-season tuning inside training only",
        "market_policy":"market lines excluded from feature matrix/tuning; benchmark and grading only",
        "release_state":"HOLD","research_only":True,"folds":{},
    }

    for year in TARGET_YEARS:
        train=[r for r in rows if r["season"]<year]
        test=[r for r in rows if r["season"]==year]
        fold={"train_seasons":sorted({r["season"] for r in train}),"test_season":year}
        fold_preds={}
        for kind in ("spread","total"):
            best,top=select_params(train,kind)
            pred,model,prep,names,coefs=fit_and_predict(train,test,kind,best["k"],best["lambda"])
            fold_preds[kind]=pred
            fold[kind]=summarize_fold(train,test,pred,kind,best)
            fold[kind]["inner_top_candidates"]=top
            for n,b in coefs.items():
                coeff_rows.append({"test_season":year,"model":kind,"k":best["k"],"lambda":best["lambda"],"feature":n,"standardized_beta":round(b,6),"release_state":"HOLD"})
            coeff_rows.append({"test_season":year,"model":kind,"k":best["k"],"lambda":best["lambda"],"feature":"INTERCEPT_TARGET_MEAN","standardized_beta":round(model[0],6),"release_state":"HOLD"})
        summary["folds"][str(year)]=fold

        for i,r in enumerate(test):
            ps=float(fold_preds["spread"][i]); pt=float(fold_preds["total"][i])
            qsp=to_float(r.get("market_home_spread_reference")); qtot=to_float(r.get("market_total_reference"))
            predictions.append({
                "game_id":r["game_id"],"season":r["season"],"week":r["week"],"gameday":r["gameday"],
                "away_team":r["away_team"],"home_team":r["home_team"],"actual_home_margin":r["home_margin"],"actual_total":r["game_total"],
                "pred_home_margin":round(ps,4),"pred_total":round(pt,4),
                "market_home_spread_reference":r.get("market_home_spread_reference",""),"market_total_reference":r.get("market_total_reference",""),
                "spread_edge_vs_reference":"" if qsp is None else round(ps+qsp,4),
                "total_edge_vs_reference":"" if qtot is None else round(pt-qtot,4),
                "market_policy":"BENCHMARK_ONLY_NOT_MODEL_FEATURE","release_state":"HOLD_RESEARCH_ONLY",
            })

    # Aggregate all out-of-sample folds.
    for kind,pred_key,target_key in (("spread","pred_home_margin","actual_home_margin"),("total","pred_total","actual_total")):
        y=np.asarray([float(r[target_key]) for r in predictions]); p=np.asarray([float(r[pred_key]) for r in predictions])
        # Training-mean baseline is fold-specific, so aggregate it from stored fold MAEs weighted by fold n.
        fold_items=[summary["folds"][str(y_)][kind] for y_ in TARGET_YEARS]
        total_n=sum(x["test_games"] for x in fold_items)
        weighted_naive=sum(x["training_mean_baseline_mae"]*x["test_games"] for x in fold_items)/total_n
        weighted_market=sum(x["market_reference_mae"]*x["test_games"] for x in fold_items if x["market_reference_mae"] is not None)/sum(x["test_games"] for x in fold_items if x["market_reference_mae"] is not None)
        # Research grading across all OOS predictions.
        fake_rows=[]
        for r in predictions:
            fake_rows.append({
                "home_margin":r["actual_home_margin"],"game_total":r["actual_total"],
                "market_home_spread_reference":r["market_home_spread_reference"],"market_total_reference":r["market_total_reference"],
            })
        summary[f"aggregate_{kind}"]={
            "games":len(predictions),"mae":round(mae(y,p),4),"rmse":round(rmse(y,p),4),"bias_pred_minus_actual":round(bias(y,p),4),
            "weighted_fold_training_mean_baseline_mae":round(weighted_naive,4),"weighted_fold_market_reference_mae":round(weighted_market,4),
            "research_grading_by_edge":grading(fake_rows,p,kind),
        }

    summary["interpretation"]=(
        "This is the first raw-feature NFL baseline, not a released model. Market reference performance is a comparison target, not a model feature. "
        "Opponent adjustment, QB/personnel, pace/drive refinement, weather, executable-price checks, robustness and prospective validation remain required."
    )
    summary["generated_utc"]=datetime.now(timezone.utc).isoformat()

    pred_path=OUT_DIR/"walk_forward_predictions_2023_2025.csv"
    with pred_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(predictions[0])); w.writeheader(); w.writerows(predictions)
    coef_path=OUT_DIR/"walk_forward_coefficients.csv"
    with coef_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(coeff_rows[0])); w.writeheader(); w.writerows(coeff_rows)
    sum_path=OUT_DIR/"walk_forward_summary.json"; sum_path.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2)); print(pred_path); print(coef_path); print(sum_path)

if __name__=="__main__": main()
