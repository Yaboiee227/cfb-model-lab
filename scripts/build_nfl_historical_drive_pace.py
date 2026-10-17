#!/usr/bin/env python3
"""Build leakage-safe NFL drive, possession and pace pregame features.

The target is totals research. Target-week rows use only completed prior weeks.
2021 is context only for safe 2022 prior-season baselines. Outputs remain HOLD.
"""
from __future__ import annotations

import csv, gzip, io, json, math, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CONTEXT_SEASONS=[2021,2022,2023,2024,2025]
TARGET_SEASONS=[2022,2023,2024,2025]
PBP_URL="https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
BASE_GAME=Path("nfl_data/historical/game_pregame_features_2022_2025.csv")
OUT_DIR=Path("nfl_data/historical")
REQUIRED={"season","week","season_type","game_id","play_id","posteam","defteam","play_type","epa","qtr","wp","down","fixed_drive","game_seconds_remaining","posteam_score","posteam_score_post","yardline_100","qb_dropback","rush_attempt","qb_kneel","qb_spike"}


def num(v):
    if v is None:return None
    s=str(v).strip()
    if not s or s.lower() in {"na","nan","none","null"}:return None
    try:
        x=float(s);return x if math.isfinite(x) else None
    except ValueError:return None

def z(v):
    x=num(v);return 0.0 if x is None else x

def flag(v):return z(v)==1.0

def div(a,b):return None if not b else a/b

def rnd(v,n=5):return "" if v is None or not math.isfinite(v) else round(v,n)

def merge(dst,src):
    for k,v in src.items():dst[k]+=v


def metric(a):
    return {
        "points_per_drive":rnd(div(a["points"],a["drives"])),
        "scoring_drive_rate":rnd(div(a["scoring_drives"],a["drives"])),
        "plays_per_drive":rnd(div(a["plays"],a["drives"])),
        "epa_per_drive":rnd(div(a["epa"],a["drives"])),
        "epa_per_drive_play":rnd(div(a["epa"],a["plays"])),
        "start_yardline_100":rnd(div(a["start_yardline_sum"],a["start_yardline_n"])),
        "drives_per_game":rnd(div(a["drives"],a["games"])),
        "neutral_seconds_per_snap":rnd(div(a["neutral_seconds"],a["neutral_intervals"]),3),
        "seconds_per_snap":rnd(div(a["seconds"],a["intervals"]),3),
        "redzone_drive_rate":rnd(div(a["rz_drives"],a["drives"])),
    }


def process_season(season,qa):
    req=urllib.request.Request(PBP_URL.format(season=season),headers={"User-Agent":"cb-model-projections/1.0"})
    drives={};prev={};games=defaultdict(lambda:defaultdict(set));scanned=0
    with urllib.request.urlopen(req,timeout=180) as resp:
        with gzip.GzipFile(fileobj=resp) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8-sig",newline="") as text:
                reader=csv.DictReader(text);fields=set(reader.fieldnames or [])
                missing=sorted(REQUIRED-fields)
                if missing:raise RuntimeError(f"{season} missing pace/drive columns {missing}")
                has_no_play="no_play" in fields
                for r in reader:
                    scanned+=1
                    if int(z(r.get("season")))!=season or str(r.get("season_type","")).upper()!="REG":continue
                    week=int(z(r.get("week")));posteam=str(r.get("posteam","")).strip();defteam=str(r.get("defteam","")).strip();gid=str(r.get("game_id","")).strip();drv=str(r.get("fixed_drive","")).strip()
                    if week<1 or not posteam or not defteam or not gid or not drv:continue
                    games[posteam][week].add(gid);games[defteam][week].add(gid)
                    key=(week,gid,drv,posteam)
                    d=drives.setdefault(key,{"week":week,"game_id":gid,"posteam":posteam,"defteam":defteam,"plays":0.0,"epa":0.0,"rz":0.0,"start_yardline":None,"start_score":None,"end_score":None,"neutral_seconds":0.0,"neutral_intervals":0.0,"seconds":0.0,"intervals":0.0})
                    pre=num(r.get("posteam_score"));post=num(r.get("posteam_score_post"))
                    if d["start_score"] is None and pre is not None:d["start_score"]=pre
                    if post is not None:d["end_score"]=post
                    pt=str(r.get("play_type","")).strip().lower();nullified=pt=="no_play" or (has_no_play and flag(r.get("no_play")))
                    if nullified or flag(r.get("qb_kneel")) or flag(r.get("qb_spike")):continue
                    drop=flag(r.get("qb_dropback"));rush=flag(r.get("rush_attempt"))
                    if not (pt in {"pass","run"} or drop or rush):continue
                    epa=num(r.get("epa"));clock=num(r.get("game_seconds_remaining"));yl=num(r.get("yardline_100"))
                    if epa is None:continue
                    d["plays"]+=1;d["epa"]+=epa
                    if d["start_yardline"] is None and yl is not None:d["start_yardline"]=yl
                    if yl is not None and yl<=20:d["rz"]=1.0
                    qtr=num(r.get("qtr"));down=num(r.get("down"));wp=num(r.get("wp"))
                    neutral=down in {1.0,2.0} and qtr is not None and qtr<=3 and wp is not None and .20<=wp<=.80
                    pkey=(gid,drv,posteam);prior=prev.get(pkey)
                    if prior and clock is not None and prior["clock"] is not None:
                        delta=prior["clock"]-clock
                        if 5<=delta<=50:
                            d["seconds"]+=delta;d["intervals"]+=1
                            if neutral and prior["neutral"]:
                                d["neutral_seconds"]+=delta;d["neutral_intervals"]+=1
                    if clock is not None:prev[pkey]={"clock":clock,"neutral":neutral}
    weekly_off=defaultdict(lambda:defaultdict(lambda:defaultdict(float)));weekly_def=defaultdict(lambda:defaultdict(lambda:defaultdict(float)));valid_drives=0
    for d in drives.values():
        if d["plays"]<=0:continue
        valid_drives+=1;pts=0.0
        if d["start_score"] is not None and d["end_score"] is not None:pts=max(0.0,d["end_score"]-d["start_score"])
        row={"drives":1.0,"points":pts,"scoring_drives":1.0 if pts>0 else 0.0,"plays":d["plays"],"epa":d["epa"],"rz_drives":d["rz"],"start_yardline_sum":0.0 if d["start_yardline"] is None else d["start_yardline"],"start_yardline_n":0.0 if d["start_yardline"] is None else 1.0,"neutral_seconds":d["neutral_seconds"],"neutral_intervals":d["neutral_intervals"],"seconds":d["seconds"],"intervals":d["intervals"]}
        merge(weekly_off[d["posteam"]][d["week"]],row);merge(weekly_def[d["defteam"]][d["week"]],row)
    for team,wmap in weekly_off.items():
        for week,a in wmap.items():a["games"]=len(games[team][week])
    for team,wmap in weekly_def.items():
        for week,a in wmap.items():a["games"]=len(games[team][week])
    qa[str(season)]={"rows_scanned":scanned,"drive_keys":len(drives),"valid_drives":valid_drives,"offense_teams":len(weekly_off),"defense_teams":len(weekly_def)}
    return weekly_off,weekly_def


def agg(weekly,team,weeks):
    out=defaultdict(float)
    for w in weeks:merge(out,weekly[team].get(w,{}))
    return out


def full_metrics(wo,wd,team):
    weeks=sorted(set(wo[team])|set(wd[team]));o=metric(agg(wo,team,weeks));d=metric(agg(wd,team,weeks))
    out={f"off_{k}":v for k,v in o.items()};out.update({f"def_{k}_allowed":v for k,v in d.items()});return out


def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True);qa={"release_state":"HOLD","context_seasons":CONTEXT_SEASONS,"target_seasons":TARGET_SEASONS};data={}
    for s in CONTEXT_SEASONS:data[s]=process_season(s,qa)
    full={}
    for s,(wo,wd) in data.items():
        teams=sorted(set(wo)|set(wd));full[s]={t:full_metrics(wo,wd,t) for t in teams}
    snaps={};rows=[]
    for s in TARGET_SEASONS:
        wo,wd=data[s];teams=sorted(set(wo)|set(wd));maxw=max(max(m.keys()) for m in list(wo.values())+list(wd.values()))
        for tw in range(1,maxw+1):
            for team in teams:
                prior_weeks=[w for w in sorted(set(wo[team])|set(wd[team])) if w<tw]
                om=metric(agg(wo,team,prior_weeks)) if prior_weeks else {};dm=metric(agg(wd,team,prior_weeks)) if prior_weeks else {}
                rec={"season":s,"target_week":tw,"team":team,"games_before":sum(wo[team][w].get("games",0) for w in prior_weeks),"max_week_used":max(prior_weeks) if prior_weeks else 0}
                for k,v in om.items():rec[f"std_off_{k}"]=v
                for k,v in dm.items():rec[f"std_def_{k}_allowed"]=v
                for k,v in full.get(s-1,{}).get(team,{}).items():rec[f"prior_{k}"]=v
                rec["release_state"]="HISTORICAL_RESEARCH";snaps[(s,tw,team)]=rec;rows.append(rec)
                if rec["max_week_used"]>=tw:raise RuntimeError(f"Leakage {s} W{tw} {team}")
    keys=sorted({k for r in rows for k in r},key=lambda k:(0 if k in ["season","target_week","team","games_before","max_week_used"] else 1,k))
    team_path=OUT_DIR/"team_week_drive_pace_2022_2025.csv"
    with team_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(rows)
    with BASE_GAME.open(encoding="utf-8") as f:base=list(csv.DictReader(f))
    games=[];missing=0
    for r in base:
        s=int(float(r["season"]));tw=int(float(r["week"]));h=snaps.get((s,tw,r["home_team"]));a=snaps.get((s,tw,r["away_team"]))
        if not h or not a:missing+=1;continue
        out={"game_id":r["game_id"],"season":s,"week":tw,"gameday":r["gameday"],"away_team":r["away_team"],"home_team":r["home_team"],"game_total":r["game_total"],"market_total_reference":r["market_total_reference"],"neutral_site":r["neutral_site"],"away_rest":r["away_rest"],"home_rest":r["home_rest"]}
        for side,obj in (("home",h),("away",a)):
            for k,v in obj.items():
                if k not in {"season","target_week","team","release_state"}:out[f"{side}_{k}"]=v
        out["release_state"]="HISTORICAL_RESEARCH";games.append(out)
    game_path=OUT_DIR/"game_drive_pace_2022_2025.csv"
    game_keys=sorted({k for g in games for k in g},key=lambda k:(0 if k in ["game_id","season","week","gameday","away_team","home_team","game_total","market_total_reference","neutral_site","away_rest","home_rest"] else 1,k))
    with game_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=game_keys,extrasaction="ignore");w.writeheader();w.writerows(games)
    qa.update({"team_week_rows":len(rows),"game_rows":len(games),"missing_game_snapshots":missing,"pace_definition":"mean game-clock seconds between consecutive qualifying scrimmage snaps within same fixed_drive, keeping 5-50 second intervals; neutral requires both snaps on early downs Q1-Q3 with 0.20<=wp<=0.80","drive_definition":"fixed_drive with at least one non-nullified non-kneel/spike scrimmage play","points_per_drive_definition":"posteam score change across fixed_drive; nonnegative","anti_leakage":"max_week_used < target_week for every snapshot","generated_utc":datetime.now(timezone.utc).isoformat()})
    (OUT_DIR/"drive_pace_build_qa.json").write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(qa,indent=2));print(team_path);print(game_path)

if __name__=="__main__":main()
