#!/usr/bin/env python3
"""Leakage-safe NFL multifeature market-residual validation v1.

This validator uses the historical pregame PBP feature panel built from only
information available before each game. The historical market is the baseline
forecast; football features predict only a residual adjustment around it.

Anti-overfit/release rules:
- Evaluation seasons are 2023-2025.
- Ridge lambda and actionable edge threshold are chosen BEFORE each evaluation
  season using only earlier-season validation data.
- Each target game is fit using only games from earlier season/weeks.
- Same-week games never train one another.
- If no prior-data threshold clears both break-even win rate and positive ROI,
  the selected policy is NO PLAY for that evaluation season.
- All outputs remain HOLD / RESEARCH_VALIDATION_ONLY.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

INPUT = Path("nfl_data/historical/game_pregame_features_2022_2025.csv")
OUT_DIR = Path("nfl_data/validation")
OUT_CSV = OUT_DIR / "multifeature_residual_v1_walkforward_2023_2025.csv"
OUT_QA = OUT_DIR / "multifeature_residual_v1_qa.json"

EVAL_SEASONS = [2023, 2024, 2025]
LAMBDA_CANDIDATES = [1.0, 3.0, 10.0, 30.0, 100.0, 300.0]
THRESHOLD_CANDIDATES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
MIN_TRAIN_GAMES = 120
MIN_THRESHOLD_GRADED = 35
BREAKEVEN_WIN_RATE_MINUS_110 = 1.1 / 2.1

FEATURE_NAMES = [
    "std_net_epa_diff",
    "std_net_success_diff",
    "std_pass_matchup_diff",
    "std_rush_matchup_diff",
    "std_pass_explosive_matchup_diff",
    "std_rush_explosive_matchup_diff",
    "std_sack_matchup_diff",
    "std_neutral_pass_rate_diff",
    "last3_net_epa_diff",
    "last3_net_success_diff",
    "prior_net_epa_diff",
    "prior_net_success_diff",
    "prior_pass_epa_diff",
    "prior_rush_epa_diff",
    "prior_sack_balance_diff",
    "rest_diff",
    "neutral_site",
]


def f(v):
    try:
        if v is None or str(v).strip() == "": return None
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None


def mean(xs): return None if not xs else sum(xs)/len(xs)

def rmse(errors): return None if not errors else math.sqrt(sum(e*e for e in errors)/len(errors))


def corr(xs,ys):
    if len(xs)!=len(ys) or len(xs)<2: return None
    mx,my=mean(xs),mean(ys)
    dx=[x-mx for x in xs]; dy=[y-my for y in ys]
    den=math.sqrt(sum(x*x for x in dx)*sum(y*y for y in dy))
    return None if not den else sum(a*b for a,b in zip(dx,dy))/den


def val(r,key): return f(r.get(key))


def diff(r,key):
    h=val(r,"home_"+key); a=val(r,"away_"+key)
    return None if h is None or a is None else h-a


def combo4(r,h1,a1,h2,a2):
    vals=[val(r,h1),val(r,a1),val(r,h2),val(r,a2)]
    return None if any(x is None for x in vals) else vals[0]+vals[1]-vals[2]-vals[3]


def feature_vector(r):
    pass_match=combo4(r,"home_std_off_pass_epa","away_std_def_pass_epa_allowed",
                         "away_std_off_pass_epa","home_std_def_pass_epa_allowed")
    rush_match=combo4(r,"home_std_off_rush_epa","away_std_def_rush_epa_allowed",
                         "away_std_off_rush_epa","home_std_def_rush_epa_allowed")
    pass_expl=combo4(r,"home_std_off_pass20_rate","away_std_def_pass20_rate_allowed",
                        "away_std_off_pass20_rate","home_std_def_pass20_rate_allowed")
    rush_expl=combo4(r,"home_std_off_rush10_rate","away_std_def_rush10_rate_allowed",
                        "away_std_off_rush10_rate","home_std_def_rush10_rate_allowed")
    hs=[val(r,"home_std_def_sack_rate_forced"),val(r,"away_std_off_sack_rate"),
        val(r,"away_std_def_sack_rate_forced"),val(r,"home_std_off_sack_rate")]
    sack_match=None if any(x is None for x in hs) else hs[0]+hs[1]-hs[2]-hs[3]
    ps=[val(r,"home_prior_def_sack_rate_forced"),val(r,"home_prior_off_sack_rate"),
        val(r,"away_prior_def_sack_rate_forced"),val(r,"away_prior_off_sack_rate")]
    prior_sack=None if any(x is None for x in ps) else (ps[0]-ps[1])-(ps[2]-ps[3])
    hr=val(r,"home_rest"); ar=val(r,"away_rest")
    rest=None if hr is None or ar is None else hr-ar
    return [
        diff(r,"std_net_epa"), diff(r,"std_net_success"), pass_match, rush_match,
        pass_expl, rush_expl, sack_match, diff(r,"std_off_neutral_ed_pass_rate"),
        diff(r,"last3_net_epa"), diff(r,"last3_net_success"), diff(r,"prior_net_epa"),
        diff(r,"prior_net_success"), diff(r,"prior_off_pass_epa"), diff(r,"prior_off_rush_epa"),
        prior_sack, rest, val(r,"neutral_site"),
    ]


def solve(a,b):
    n=len(b); m=[list(map(float,a[i]))+[float(b[i])] for i in range(n)]
    for c in range(n):
        p=max(range(c,n),key=lambda r:abs(m[r][c]))
        if abs(m[p][c])<1e-12: return None
        m[c],m[p]=m[p],m[c]
        d=m[c][c]; m[c]=[x/d for x in m[c]]
        for r in range(n):
            if r==c: continue
            q=m[r][c]
            if q: m[r]=[rv-q*cv for rv,cv in zip(m[r],m[c])]
    return [m[i][-1] for i in range(n)]


def fit_ridge(rows,lam):
    p=len(FEATURE_NAMES); means=[]; scales=[]
    for j in range(p):
        observed=[r["features"][j] for r in rows if r["features"][j] is not None]
        mu=mean(observed) or 0.0
        var=sum((x-mu)**2 for x in observed)/max(1,len(observed)-1)
        sd=math.sqrt(var) if var>1e-12 else 1.0
        means.append(mu); scales.append(sd)
    X=[]; y=[]
    for r in rows:
        x=[1.0]
        for j,v in enumerate(r["features"]):
            z=means[j] if v is None else v
            x.append((z-means[j])/scales[j])
        X.append(x); y.append(r["actual_residual"])
    k=p+1; xtx=[[0.0]*k for _ in range(k)]; xty=[0.0]*k
    for x,t in zip(X,y):
        for i in range(k):
            xty[i]+=x[i]*t
            for j in range(k): xtx[i][j]+=x[i]*x[j]
    for j in range(1,k): xtx[j][j]+=lam
    beta=solve(xtx,xty)
    return None if beta is None else {"beta":beta,"means":means,"scales":scales,"lambda":lam}


def predict(model,features):
    x=[1.0]
    for j,v in enumerate(features):
        z=model["means"][j] if v is None else v
        x.append((z-model["means"][j])/model["scales"][j])
    return sum(a*b for a,b in zip(model["beta"],x))


def ats(actual_margin,market_margin,edge):
    delta=actual_margin-market_margin
    if abs(delta)<1e-9: return "PUSH"
    return "WIN" if (delta>0)==(edge>0) else "LOSS"


def grade_threshold(preds,threshold):
    picks=[r for r in preds if abs(r["predicted_residual"])>=threshold]
    w=sum(r["ats_result"]=="WIN" for r in picks); l=sum(r["ats_result"]=="LOSS" for r in picks); p=sum(r["ats_result"]=="PUSH" for r in picks)
    graded=w+l; units=w-1.1*l
    return {"bets":len(picks),"wins":w,"losses":l,"pushes":p,"graded":graded,
            "win_rate_ex_push":w/graded if graded else None,"units_at_minus_110":units,
            "roi_at_minus_110":units/graded if graded else None}


def score_model(train,validation,lam):
    if len(train)<MIN_TRAIN_GAMES: return None
    model=fit_ridge(train,lam)
    if model is None: return None
    preds=[]
    for r in validation:
        edge=predict(model,r["features"]); mm=r["market_margin"]
        q=dict(r); q.update({"predicted_residual":edge,"model_margin":mm+edge,"ats_result":ats(r["home_margin"],mm,edge)})
        preds.append(q)
    if not preds: return None
    errors=[r["home_margin"]-r["model_margin"] for r in preds]
    return {"model":model,"preds":preds,"mae":sum(abs(e) for e in errors)/len(errors),"rmse":rmse(errors)}


def tuning_split(rows,eval_season):
    prev=eval_season-1
    if eval_season==2023:
        train=[r for r in rows if r["season"]==2022 and r["week"]<=9]
        valid=[r for r in rows if r["season"]==2022 and r["week"]>=10]
    else:
        train=[r for r in rows if r["season"]<prev]
        valid=[r for r in rows if r["season"]==prev]
    return train,valid


def choose_preseason_settings(rows,eval_season):
    train,valid=tuning_split(rows,eval_season)
    candidates=[]
    for lam in LAMBDA_CANDIDATES:
        s=score_model(train,valid,lam)
        if s is not None: candidates.append((s["mae"],lam,s))
    if not candidates: raise RuntimeError(f"No tuning candidate for {eval_season}")
    _,lam,best=min(candidates,key=lambda x:x[0])

    eligible=[]; all_grades={}
    for t in THRESHOLD_CANDIDATES:
        g=grade_threshold(best["preds"],t); all_grades[str(t)]=g
        if (g["graded"]>=MIN_THRESHOLD_GRADED and g["roi_at_minus_110"] is not None
                and g["roi_at_minus_110"]>0 and g["win_rate_ex_push"] is not None
                and g["win_rate_ex_push"]>BREAKEVEN_WIN_RATE_MINUS_110):
            eligible.append((g["roi_at_minus_110"],t,g))
    if eligible:
        _,threshold,grade=max(eligible,key=lambda x:x[0]); action_state="QUALIFIED"
    else:
        threshold=None; grade={"bets":0,"wins":0,"losses":0,"pushes":0,"graded":0,
                              "win_rate_ex_push":None,"units_at_minus_110":0.0,"roi_at_minus_110":None}
        action_state="NO_PLAY"
    return {
        "lambda":lam,"threshold":threshold,"action_state":action_state,
        "tuning_train_games":len(train),"tuning_validation_games":len(valid),
        "tuning_validation_mae":best["mae"],"threshold_validation_grade":grade,
        "all_threshold_validation_grades":all_grades,
        "lambda_candidates":LAMBDA_CANDIDATES,"threshold_candidates":THRESHOLD_CANDIDATES,
    }


def summarize(rows,selected_only=False):
    use=[r for r in rows if (not selected_only or r["selected_play"])]
    if not use:
        return {"bets":0,"wins":0,"losses":0,"pushes":0,"win_rate_ex_push":None,
                "units_at_minus_110":0.0,"roi_at_minus_110":None} if selected_only else {"games":0}
    if selected_only:
        w=sum(r["ats_result"]=="WIN" for r in use); l=sum(r["ats_result"]=="LOSS" for r in use); p=sum(r["ats_result"]=="PUSH" for r in use)
        graded=w+l; units=w-1.1*l
        return {"bets":len(use),"wins":w,"losses":l,"pushes":p,"win_rate_ex_push":w/graded if graded else None,
                "units_at_minus_110":units,"roi_at_minus_110":units/graded if graded else None}
    market_err=[r["home_margin"]-r["market_margin"] for r in use]
    model_err=[r["home_margin"]-r["model_margin"] for r in use]
    return {"games":len(use),"market_mae":sum(abs(x) for x in market_err)/len(use),"model_mae":sum(abs(x) for x in model_err)/len(use),
            "market_rmse":rmse(market_err),"model_rmse":rmse(model_err),
            "predicted_vs_actual_residual_correlation":corr([r["predicted_residual"] for r in use],[r["actual_residual"] for r in use])}


def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    with INPUT.open(encoding="utf-8",newline="") as fobj: source=list(csv.DictReader(fobj))
    rows=[]
    for r in source:
        season=int(float(r["season"])); week=int(float(r["week"])); hm=f(r.get("home_margin")); line=f(r.get("market_home_spread_reference"))
        if hm is None or line is None: continue
        market_margin=-line
        rows.append({
            "game_id":r.get("game_id",""),"season":season,"week":week,"gameday":r.get("gameday",""),
            "away_team":r.get("away_team",""),"home_team":r.get("home_team",""),
            "home_margin":hm,"market_home_spread":line,"market_margin":market_margin,
            "actual_residual":hm-market_margin,"features":feature_vector(r),
            "home_source_week":int(float(r.get("home_max_current_season_week_used") or 0)),
            "away_source_week":int(float(r.get("away_max_current_season_week_used") or 0)),
        })
    rows.sort(key=lambda r:(r["season"],r["week"],r["gameday"],r["game_id"]))
    if any(r["home_source_week"]>=r["week"] or r["away_source_week"]>=r["week"] for r in rows):
        raise RuntimeError("Leakage guard failed in historical input")

    settings={s:choose_preseason_settings(rows,s) for s in EVAL_SEASONS}
    out=[]
    for season in EVAL_SEASONS:
        cfg=settings[season]; games=[r for r in rows if r["season"]==season]
        for r in games:
            train=[x for x in rows if (x["season"],x["week"])<(season,r["week"])]
            if len(train)<MIN_TRAIN_GAMES: continue
            model=fit_ridge(train,cfg["lambda"])
            if model is None: continue
            edge=predict(model,r["features"]); mm=r["market_margin"]
            selected=(cfg["threshold"] is not None and abs(edge)>=cfg["threshold"])
            q={k:v for k,v in r.items() if k!="features"}
            q.update({"selected_lambda":cfg["lambda"],"selected_threshold":cfg["threshold"],
                      "preseason_action_state":cfg["action_state"],"predicted_residual":edge,
                      "model_margin":mm+edge,"ats_result":ats(r["home_margin"],mm,edge),
                      "selected_play":selected,"prior_training_games":len(train),
                      "release_state":"HOLD","model_use":"RESEARCH_VALIDATION_ONLY"})
            out.append(q)
    if not out: raise RuntimeError("No multifeature validation rows produced")

    with OUT_CSV.open("w",encoding="utf-8",newline="") as fobj:
        w=csv.DictWriter(fobj,fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

    qa={
        "validation_name":"NFL multifeature market-residual walk-forward v1",
        "input":str(INPUT),"features":FEATURE_NAMES,"evaluation_seasons":EVAL_SEASONS,
        "anti_leakage":"all current-season source weeks < target week; same-week games excluded from training",
        "break_even_win_rate_minus_110":BREAKEVEN_WIN_RATE_MINUS_110,
        "preseason_settings":settings,
        "overall_forecast":summarize(out),"overall_selected_ats":summarize(out,True),
        "by_season":{str(s):{"forecast":summarize([r for r in out if r["season"]==s]),
                             "selected_ats":summarize([r for r in out if r["season"]==s],True)} for s in EVAL_SEASONS},
        "release_state":"HOLD","model_use":"RESEARCH_VALIDATION_ONLY",
        "notes":[
            "Historical market spread is the baseline and is not presented as timestamped executable pricing.",
            "Lambda and actionable edge threshold are selected only from data predating each evaluation season.",
            "Threshold selection requires at least 35 graded bets, positive prior-data ROI, and win rate above -110 break-even; otherwise the season is NO PLAY.",
            "Current PBP, last-three form, prior-season priors, rest and neutral-site context are included.",
            "QB identity, injuries, weather, travel distance/time zones, price/vig, line movement and CLV remain separate required layers.",
            "No output authorizes website publication or wager release."
        ],
        "generated_utc":datetime.now(timezone.utc).isoformat(),
    }
    OUT_QA.write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(qa,indent=2)); print(OUT_CSV); print(OUT_QA)

if __name__=="__main__": main()
