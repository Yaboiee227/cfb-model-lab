#!/usr/bin/env python3
"""Walk-forward validation of NFL totals drive/pace candidates.

Compares a drive/pace-only model and a combined football+drive/pace model.
All model inputs are pregame-safe. Historical market totals are excluded from
training/tuning and used only after prediction as a benchmark and research grade.
"""
from __future__ import annotations
import csv, json, math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

DRIVE=Path("nfl_data/historical/game_drive_pace_2022_2025.csv")
BASE=Path("nfl_data/historical/game_pregame_features_2022_2025.csv")
PRIOR_SUMMARY=Path("nfl_data/validation/walk_forward_summary.json")
OUT=Path("nfl_data/validation")
TARGET_YEARS=[2023,2024,2025]
K_GRID=[1.,2.,3.,4.,6.,8.]
LAM_GRID=[.1,1.,3.,10.,30.,100.,300.]
EDGE_THRESHOLDS=[1.,2.,3.,4.,5.]


def f(v):
    try:
        x=float(str(v).strip());return x if math.isfinite(x) else None
    except:return None

def blend(r,side,metric,k,prefix=""):
    g=f(r.get(f"{side}_games_before")) or 0.
    cur=f(r.get(f"{side}_std_{prefix}{metric}"));pr=f(r.get(f"{side}_prior_{prefix}{metric}"))
    if cur is not None and pr is not None:return (g*cur+k*pr)/(g+k)
    return cur if cur is not None else pr

def raw(r,side,key):return f(r.get(f"{side}_{key}"))
def sm(a,b):return None if a is None or b is None else a+b

def load():
    with DRIVE.open(encoding="utf-8") as fh:drive=list(csv.DictReader(fh))
    with BASE.open(encoding="utf-8") as fh:base={r["game_id"]:r for r in csv.DictReader(fh)}
    rows=[]
    for d in drive:
        b=base.get(d["game_id"])
        if not b:continue
        r=dict(d)
        for k,v in b.items():
            if k not in r:r[k]=v
        r["season"]=int(float(r["season"]));r["week"]=int(float(r["week"]));rows.append(r)
    rows.sort(key=lambda r:(r["season"],r["week"],r["gameday"],r["game_id"]))
    return rows

DRIVE_METRICS=[
    "off_points_per_drive","def_points_per_drive_allowed","off_scoring_drive_rate","def_scoring_drive_rate_allowed",
    "off_plays_per_drive","def_plays_per_drive_allowed","off_epa_per_drive","def_epa_per_drive_allowed",
    "off_epa_per_drive_play","def_epa_per_drive_play_allowed","off_drives_per_game","def_drives_per_game_allowed",
    "off_neutral_seconds_per_snap","def_neutral_seconds_per_snap_allowed","off_seconds_per_snap","def_seconds_per_snap_allowed",
    "off_redzone_drive_rate","def_redzone_drive_rate_allowed","off_start_yardline_100","def_start_yardline_100_allowed"
]

def dval(r,side,metric,k):return blend(r,side,metric,k)
def bval(r,side,metric,k):return blend(r,side,metric,k)

def drive_features(r,k):
    h=lambda m:dval(r,"home",m,k);a=lambda m:dval(r,"away",m,k)
    # Match offense with opposing defense, then combine both expected scoring environments.
    h_ppd=sm(h("off_points_per_drive"),a("def_points_per_drive_allowed"));a_ppd=sm(a("off_points_per_drive"),h("def_points_per_drive_allowed"))
    h_scr=sm(h("off_scoring_drive_rate"),a("def_scoring_drive_rate_allowed"));a_scr=sm(a("off_scoring_drive_rate"),h("def_scoring_drive_rate_allowed"))
    h_epd=sm(h("off_epa_per_drive"),a("def_epa_per_drive_allowed"));a_epd=sm(a("off_epa_per_drive"),h("def_epa_per_drive_allowed"))
    h_epp=sm(h("off_epa_per_drive_play"),a("def_epa_per_drive_play_allowed"));a_epp=sm(a("off_epa_per_drive_play"),h("def_epa_per_drive_play_allowed"))
    h_drv=sm(h("off_drives_per_game"),a("def_drives_per_game_allowed"));a_drv=sm(a("off_drives_per_game"),h("def_drives_per_game_allowed"))
    h_pl=sm(h("off_plays_per_drive"),a("def_plays_per_drive_allowed"));a_pl=sm(a("off_plays_per_drive"),h("def_plays_per_drive_allowed"))
    h_npace=sm(h("off_neutral_seconds_per_snap"),a("def_neutral_seconds_per_snap_allowed"));a_npace=sm(a("off_neutral_seconds_per_snap"),h("def_neutral_seconds_per_snap_allowed"))
    h_pace=sm(h("off_seconds_per_snap"),a("def_seconds_per_snap_allowed"));a_pace=sm(a("off_seconds_per_snap"),h("def_seconds_per_snap_allowed"))
    h_rz=sm(h("off_redzone_drive_rate"),a("def_redzone_drive_rate_allowed"));a_rz=sm(a("off_redzone_drive_rate"),h("def_redzone_drive_rate_allowed"))
    h_fp=sm(h("off_start_yardline_100"),a("def_start_yardline_100_allowed"));a_fp=sm(a("off_start_yardline_100"),h("def_start_yardline_100_allowed"))
    hr,ar=f(r.get("home_rest")),f(r.get("away_rest"))
    names=["ppd_context_sum","scoring_drive_context_sum","epa_drive_context_sum","epa_drive_play_context_sum","drive_volume_context_sum","plays_per_drive_context_sum","neutral_seconds_snap_context_sum","seconds_snap_context_sum","redzone_drive_context_sum","start_field_position_context_sum","rest_sum","rest_abs_diff","neutral_site"]
    vals=[sm(h_ppd,a_ppd),sm(h_scr,a_scr),sm(h_epd,a_epd),sm(h_epp,a_epp),sm(h_drv,a_drv),sm(h_pl,a_pl),sm(h_npace,a_npace),sm(h_pace,a_pace),sm(h_rz,a_rz),sm(h_fp,a_fp),sm(hr,ar),None if hr is None or ar is None else abs(hr-ar),f(r.get("neutral_site"))]
    return names,vals

def combined_features(r,k):
    n,v=drive_features(r,k)
    h=lambda m:bval(r,"home",m,k);a=lambda m:bval(r,"away",m,k)
    hr=lambda m:raw(r,"home",f"std_{m}");ar=lambda m:raw(r,"away",f"std_{m}")
    # Current-only matchup variables are median-imputed in early weeks.
    ph=None if h("off_pass_epa") is None or ar("def_pass_epa_allowed") is None else h("off_pass_epa")+ar("def_pass_epa_allowed")
    pa=None if a("off_pass_epa") is None or hr("def_pass_epa_allowed") is None else a("off_pass_epa")+hr("def_pass_epa_allowed")
    rh=None if h("off_rush_epa") is None or ar("def_rush_epa_allowed") is None else h("off_rush_epa")+ar("def_rush_epa_allowed")
    ra=None if a("off_rush_epa") is None or hr("def_rush_epa_allowed") is None else a("off_rush_epa")+hr("def_rush_epa_allowed")
    xp_h=None if hr("off_pass20_rate") is None or ar("def_pass20_rate_allowed") is None else hr("off_pass20_rate")+ar("def_pass20_rate_allowed")
    xp_a=None if ar("off_pass20_rate") is None or hr("def_pass20_rate_allowed") is None else ar("off_pass20_rate")+hr("def_pass20_rate_allowed")
    xr_h=None if hr("off_rush10_rate") is None or ar("def_rush10_rate_allowed") is None else hr("off_rush10_rate")+ar("def_rush10_rate_allowed")
    xr_a=None if ar("off_rush10_rate") is None or hr("def_rush10_rate_allowed") is None else ar("off_rush10_rate")+hr("def_rush10_rate_allowed")
    addn=["blend_off_epa_sum","blend_def_epa_allowed_sum","blend_off_success_sum","blend_def_success_allowed_sum","pass_matchup_sum","rush_matchup_sum","explosive_pass_context_sum","explosive_rush_context_sum","neutral_early_down_pass_rate_sum"]
    addv=[sm(h("off_epa"),a("off_epa")),sm(h("def_epa_allowed"),a("def_epa_allowed")),sm(h("off_success"),a("off_success")),sm(h("def_success_allowed"),a("def_success_allowed")),sm(ph,pa),sm(rh,ra),sm(xp_h,xp_a),sm(xr_h,xr_a),sm(hr("off_neutral_ed_pass_rate"),ar("off_neutral_ed_pass_rate"))]
    return n+addn,v+addv

def matrix(rows,k,kind):
    fn=drive_features if kind=="drive" else combined_features;names=None;vals=[]
    for r in rows:
        n,v=fn(r,k);names=n if names is None else names;vals.append([np.nan if x is None else x for x in v])
    return names,np.asarray(vals,float)
def prepfit(X):
    med=np.nanmedian(X,axis=0);med=np.where(np.isfinite(med),med,0.);Xi=np.where(np.isnan(X),med,X);mu=Xi.mean(0);sd=Xi.std(0);sd=np.where(sd<1e-9,1.,sd);return med,mu,sd
def trans(X,p):
    med,mu,sd=p;return (np.where(np.isnan(X),med,X)-mu)/sd
def fitridge(X,y,lam):
    ym=float(y.mean());A=X.T@X+lam*np.eye(X.shape[1]);b=np.linalg.solve(A,X.T@(y-ym));return ym,b
def pred(m,X):return m[0]+X@m[1]
def mae(y,p):return float(np.mean(np.abs(y-p)))
def rmse(y,p):return float(np.sqrt(np.mean((y-p)**2)))

def inner(rows):
    latest=max(r["season"] for r in rows);val=[r for r in rows if r["season"]==latest and r["week"]>=13];tr=[r for r in rows if r not in val]
    return tr,val

def tune(rows,kind):
    tr,va=inner(rows);yv=np.asarray([float(r["game_total"]) for r in va]);cand=[]
    for k in K_GRID:
        names,X=matrix(tr,k,kind);_,V=matrix(va,k,kind);pp=prepfit(X);X=trans(X,pp);V=trans(V,pp);yt=np.asarray([float(r["game_total"]) for r in tr])
        for lam in LAM_GRID:
            m=fitridge(X,yt,lam);p=pred(m,V);cand.append({"k":k,"lambda":lam,"mae":mae(yv,p),"rmse":rmse(yv,p),"validation_games":len(va)})
    cand.sort(key=lambda x:(x["mae"],x["rmse"]));return cand[0],cand[:8]
def fit_predict(tr,te,kind,k,lam):
    names,X=matrix(tr,k,kind);_,T=matrix(te,k,kind);pp=prepfit(X);X=trans(X,pp);T=trans(T,pp);y=np.asarray([float(r["game_total"]) for r in tr]);m=fitridge(X,y,lam);return pred(m,T),names,m

def grade(rows,preds):
    out={}
    for t in EDGE_THRESHOLDS:
        w=l=push=0
        for r,p in zip(rows,preds):
            line=f(r.get("market_total_reference"));actual=f(r.get("game_total"))
            if line is None or actual is None:continue
            e=p-line;res=actual-line
            if abs(e)<t:continue
            if abs(res)<1e-12:push+=1
            elif e*res>0:w+=1
            else:l+=1
        d=w+l;out[str(int(t))]={"n":d+push,"wins":w,"losses":l,"pushes":push,"win_rate":None if not d else round(w/d,4)}
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True);rows=load();summary={"validation_name":"NFL totals drive/pace walk-forward v1","market_policy":"benchmark only; never model input","release_state":"HOLD","models":{}}
    all_predictions=[];coef=[]
    for kind in ["drive","combined"]:
        model_sum={"folds":{}};kind_preds=[]
        for year in TARGET_YEARS:
            tr=[r for r in rows if r["season"]<year];te=[r for r in rows if r["season"]==year];best,top=tune(tr,kind);p,names,m=fit_predict(tr,te,kind,best["k"],best["lambda"]);y=np.asarray([float(r["game_total"]) for r in te]);market=np.asarray([float(r["market_total_reference"]) for r in te]);mean=np.full_like(y,np.mean([float(r["game_total"]) for r in tr]))
            model_sum["folds"][str(year)]={"train_games":len(tr),"test_games":len(te),"k":best["k"],"lambda":best["lambda"],"mae":round(mae(y,p),4),"rmse":round(rmse(y,p),4),"training_mean_mae":round(mae(y,mean),4),"market_reference_mae":round(mae(y,market),4),"research_ou_by_edge":grade(te,p),"inner_top_candidates":top}
            for nm,b in zip(names,m[1]):coef.append({"model":kind,"test_season":year,"feature":nm,"standardized_beta":round(float(b),6),"k":best["k"],"lambda":best["lambda"],"release_state":"HOLD"})
            for r,pp in zip(te,p):kind_preds.append((r,float(pp)))
        yy=np.asarray([float(r["game_total"]) for r,_ in kind_preds]);pp=np.asarray([p for _,p in kind_preds]);mm=np.asarray([float(r["market_total_reference"]) for r,_ in kind_preds])
        model_sum["aggregate"]={"games":len(kind_preds),"mae":round(mae(yy,pp),4),"rmse":round(rmse(yy,pp),4),"market_reference_mae":round(mae(yy,mm),4),"research_ou_by_edge":grade([r for r,_ in kind_preds],pp)}
        summary["models"][kind]=model_sum
        for r,pv in kind_preds:all_predictions.append({"model":kind,"game_id":r["game_id"],"season":r["season"],"week":r["week"],"away_team":r["away_team"],"home_team":r["home_team"],"actual_total":r["game_total"],"pred_total":round(pv,4),"market_total_reference":r["market_total_reference"],"edge_vs_reference":round(pv-float(r["market_total_reference"]),4),"release_state":"HOLD_RESEARCH_ONLY"})
    if PRIOR_SUMMARY.exists():
        prior=json.loads(PRIOR_SUMMARY.read_text());summary["prior_raw_total_baseline"]={"mae":prior.get("aggregate_total",{}).get("mae"),"rmse":prior.get("aggregate_total",{}).get("rmse"),"market_reference_mae":prior.get("aggregate_total",{}).get("weighted_fold_market_reference_mae")}
    summary["decision"]="NO PROMOTION: compare candidates, then require robustness and frozen prospective validation before production use."
    summary["generated_utc"]=datetime.now(timezone.utc).isoformat()
    (OUT/"totals_drive_pace_v1_qa.json").write_text(json.dumps(summary,indent=2)+"\n")
    with (OUT/"totals_drive_pace_v1_predictions.csv").open("w",newline="") as fh:w=csv.DictWriter(fh,fieldnames=list(all_predictions[0]));w.writeheader();w.writerows(all_predictions)
    with (OUT/"totals_drive_pace_v1_coefficients.csv").open("w",newline="") as fh:w=csv.DictWriter(fh,fieldnames=list(coef[0]));w.writeheader();w.writerows(coef)
    print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
