#!/usr/bin/env python3
"""Build leakage-safe NFL historical pregame features for walk-forward research.

Target seasons: 2022-2025. 2021 is loaded only as a prior-season baseline for
2022 Week 1/early-season shrinkage research. Every target-week snapshot uses
current-season data from weeks strictly BEFORE the target week.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CONTEXT_SEASONS = [2021, 2022, 2023, 2024, 2025]
TARGET_SEASONS = [2022, 2023, 2024, 2025]
OUT_DIR = Path("nfl_data/historical")
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"

REQUIRED = {
    "season","week","season_type","game_id","posteam","defteam","play_type",
    "epa","success","yards_gained","down","qtr","wp","qb_dropback","rush_attempt",
    "sack","qb_kneel","qb_spike"
}


def num(v):
    if v is None: return None
    s = str(v).strip()
    if not s or s.lower() in {"na","nan","none","null"}: return None
    try:
        x = float(s); return x if math.isfinite(x) else None
    except ValueError: return None


def z(v):
    x = num(v); return 0.0 if x is None else x


def flag(v): return z(v) == 1.0

def div(a,b): return None if not b else a/b

def rnd(v,n=5): return "" if v is None or not math.isfinite(v) else round(v,n)


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent":"cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode("utf-8-sig")


def fetch_schedule():
    return list(csv.DictReader(io.StringIO(fetch_text(SCHEDULE_URL))))


def add_play(bucket, epa, success, yards, dropback, rush, sack, neutral_ed):
    bucket["plays"] += 1; bucket["epa"] += epa
    if success is not None:
        bucket["success"] += success; bucket["success_n"] += 1
    if dropback:
        bucket["dropbacks"] += 1; bucket["pass_epa"] += epa
        if yards is not None and yards >= 20: bucket["pass20"] += 1
        if sack: bucket["sacks"] += 1
    if rush:
        bucket["rushes"] += 1; bucket["rush_epa"] += epa
        if yards is not None and yards >= 10: bucket["rush10"] += 1
    if neutral_ed is not None:
        bucket["neutral_ed"] += 1
        if dropback: bucket["neutral_ed_pass"] += 1


def merge(dst, src):
    for k,v in src.items(): dst[k] += v


def metrics(off, deff):
    oe, de = div(off["epa"],off["plays"]), div(deff["epa"],deff["plays"])
    os, ds = div(off["success"],off["success_n"]), div(deff["success"],deff["success_n"])
    return {
        "off_epa": rnd(oe), "def_epa_allowed": rnd(de),
        "net_epa": rnd((oe or 0)-(de or 0)) if oe is not None and de is not None else "",
        "off_success": rnd(os), "def_success_allowed": rnd(ds),
        "net_success": rnd((os or 0)-(ds or 0)) if os is not None and ds is not None else "",
        "off_pass_epa": rnd(div(off["pass_epa"],off["dropbacks"])),
        "def_pass_epa_allowed": rnd(div(deff["pass_epa"],deff["dropbacks"])),
        "off_rush_epa": rnd(div(off["rush_epa"],off["rushes"])),
        "def_rush_epa_allowed": rnd(div(deff["rush_epa"],deff["rushes"])),
        "off_pass20_rate": rnd(div(off["pass20"],off["dropbacks"])),
        "def_pass20_rate_allowed": rnd(div(deff["pass20"],deff["dropbacks"])),
        "off_rush10_rate": rnd(div(off["rush10"],off["rushes"])),
        "def_rush10_rate_allowed": rnd(div(deff["rush10"],deff["rushes"])),
        "off_sack_rate": rnd(div(off["sacks"],off["dropbacks"])),
        "def_sack_rate_forced": rnd(div(deff["sacks"],deff["dropbacks"])),
        "off_neutral_ed_pass_rate": rnd(div(off["neutral_ed_pass"],off["neutral_ed"])),
        "def_neutral_ed_pass_rate_faced": rnd(div(deff["neutral_ed_pass"],deff["neutral_ed"])),
    }


def process_season(season, qa):
    url = PBP_URL.format(season=season)
    req = urllib.request.Request(url, headers={"User-Agent":"cb-model-projections/1.0"})
    weekly_off = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    weekly_def = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    games = defaultdict(lambda: defaultdict(set))
    rows = 0; used = 0; fields_seen = None
    with urllib.request.urlopen(req, timeout=180) as resp:
        with gzip.GzipFile(fileobj=resp) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text); fields_seen = set(reader.fieldnames or [])
                missing = sorted(REQUIRED-fields_seen)
                if missing: raise RuntimeError(f"{season} PBP missing columns: {missing}")
                has_no_play = "no_play" in fields_seen
                for r in reader:
                    rows += 1
                    if int(z(r.get("season"))) != season or str(r.get("season_type","")).upper() != "REG": continue
                    week = int(z(r.get("week"))); posteam=str(r.get("posteam","")).strip(); defteam=str(r.get("defteam","")).strip()
                    if week < 1 or not posteam or not defteam: continue
                    play_type=str(r.get("play_type","")).strip().lower()
                    if play_type=="no_play" or (has_no_play and flag(r.get("no_play"))) or flag(r.get("qb_kneel")) or flag(r.get("qb_spike")): continue
                    dropback=flag(r.get("qb_dropback")); rush=flag(r.get("rush_attempt"))
                    if not (play_type in {"pass","run"} or dropback or rush): continue
                    epa=num(r.get("epa")); success=num(r.get("success")); yards=num(r.get("yards_gained"))
                    if epa is None: continue
                    down,qtr,wp=num(r.get("down")),num(r.get("qtr")),num(r.get("wp"))
                    neutral = True if down in {1.0,2.0} and qtr is not None and qtr<=3 and wp is not None and .20<=wp<=.80 else None
                    add_play(weekly_off[posteam][week],epa,success,yards,dropback,rush,flag(r.get("sack")),neutral)
                    add_play(weekly_def[defteam][week],epa,success,yards,dropback,rush,flag(r.get("sack")),neutral)
                    gid=str(r.get("game_id","")).strip(); games[posteam][week].add(gid); games[defteam][week].add(gid)
                    used += 1
    qa[str(season)]={"rows_scanned":rows,"plays_used":used,"teams":len(set(weekly_off)|set(weekly_def)),"no_play_column":has_no_play}
    return weekly_off, weekly_def, games


def aggregate_weeks(weekly, team, weeks):
    out=defaultdict(float)
    for w in weeks: merge(out, weekly[team].get(w,{}))
    return out


def season_full(weekly_off,weekly_def,team):
    weeks=sorted(set(weekly_off[team])|set(weekly_def[team]))
    return metrics(aggregate_weeks(weekly_off,team,weeks),aggregate_weeks(weekly_def,team,weeks))


def main():
    OUT_DIR.mkdir(parents=True,exist_ok=True)
    qa={"target_seasons":TARGET_SEASONS,"context_seasons":CONTEXT_SEASONS,"release_state":"HOLD"}
    data={}
    for season in CONTEXT_SEASONS:
        wo,wd,g=process_season(season,qa); data[season]=(wo,wd,g)

    prior_full={}
    for season in CONTEXT_SEASONS:
        wo,wd,_=data[season]; teams=sorted(set(wo)|set(wd))
        prior_full[season]={t:season_full(wo,wd,t) for t in teams}

    snapshots={}
    snapshot_rows=[]
    max_source_week_used=0
    for season in TARGET_SEASONS:
        wo,wd,g=data[season]; teams=sorted(set(wo)|set(wd))
        max_week=max(max(x.keys()) for x in list(wo.values())+list(wd.values()))
        for target_week in range(1,max_week+1):
            for team in teams:
                prior_weeks=[w for w in sorted(set(wo[team])|set(wd[team])) if w<target_week]
                curr_off=aggregate_weeks(wo,team,prior_weeks); curr_def=aggregate_weeks(wd,team,prior_weeks)
                cur=metrics(curr_off,curr_def) if prior_weeks else {k:"" for k in metrics(defaultdict(float),defaultdict(float))}
                played_weeks=[w for w in prior_weeks if g[team].get(w)]
                last3=played_weeks[-3:]
                rec=metrics(aggregate_weeks(wo,team,last3),aggregate_weeks(wd,team,last3)) if last3 else {k:"" for k in cur}
                prior=prior_full.get(season-1,{}).get(team,{})
                games_before=sum(len(g[team].get(w,set())) for w in prior_weeks)
                source_week=max(prior_weeks) if prior_weeks else 0
                max_source_week_used=max(max_source_week_used,source_week)
                row={"season":season,"target_week":target_week,"team":team,"games_before":games_before,"max_current_season_week_used":source_week}
                row.update({f"std_{k}":v for k,v in cur.items()})
                row.update({f"last3_{k}":v for k,v in rec.items() if k in {"off_epa","def_epa_allowed","net_epa","off_success","def_success_allowed","net_success"}})
                row.update({f"prior_{k}":v for k,v in prior.items() if k in {"off_epa","def_epa_allowed","net_epa","off_success","def_success_allowed","net_success","off_pass_epa","off_rush_epa","off_sack_rate","def_sack_rate_forced"}})
                row["release_state"]="HISTORICAL_RESEARCH"
                snapshots[(season,target_week,team)]=row; snapshot_rows.append(row)
                if source_week>=target_week: raise RuntimeError(f"Leakage detected {season} W{target_week} {team}: used W{source_week}")

    snap_path=OUT_DIR/"team_week_pregame_features_2022_2025.csv"
    keys=list(snapshot_rows[0])
    with snap_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); w.writerows(snapshot_rows)

    schedule=fetch_schedule(); games_out=[]; missing=0
    for r in schedule:
        season=int(z(r.get("season"))); week=int(z(r.get("week")))
        if season not in TARGET_SEASONS or str(r.get("game_type","")).upper()!="REG": continue
        home=str(r.get("home_team","")).strip(); away=str(r.get("away_team","")).strip()
        hs,aws=num(r.get("home_score")),num(r.get("away_score"))
        if not home or not away or hs is None or aws is None: continue
        h=snapshots.get((season,week,home)); a=snapshots.get((season,week,away))
        if not h or not a: missing+=1; continue
        out={
            "game_id":r.get("game_id",""),"season":season,"week":week,"gameday":r.get("gameday",""),
            "away_team":away,"home_team":home,"neutral_site":1 if str(r.get("location","")).lower()=="neutral" else 0,
            "away_rest":r.get("away_rest",""),"home_rest":r.get("home_rest",""),
            "home_margin":rnd(hs-aws,1),"game_total":rnd(hs+aws,1),
            "market_home_spread_reference":rnd(-num(r.get("spread_line")),2) if num(r.get("spread_line")) is not None else "",
            "market_total_reference":rnd(num(r.get("total_line")),2),
            "market_reference_policy":"BENCHMARK_ONLY_NOT_MODEL_FEATURE",
        }
        feature_names=[k for k in h if k not in {"season","target_week","team","release_state"}]
        for k in feature_names:
            out[f"home_{k}"]=h[k]; out[f"away_{k}"]=a[k]
        out["release_state"]="HISTORICAL_RESEARCH"
        games_out.append(out)

    game_path=OUT_DIR/"game_pregame_features_2022_2025.csv"
    with game_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(games_out[0])); w.writeheader(); w.writerows(games_out)

    qa.update({
        "team_week_rows":len(snapshot_rows),"historical_games":len(games_out),"missing_game_snapshots":missing,
        "max_source_week_used_any_snapshot":max_source_week_used,
        "leakage_rule":"max_current_season_week_used must be < target_week for every row",
        "prior_season_rule":"prior_* features use only the completed immediately preceding regular season",
        "market_rule":"schedule spread/total retained only as historical benchmark; never model input",
        "files":[str(snap_path),str(game_path)],"generated_utc":datetime.now(timezone.utc).isoformat(),
    })
    qa_path=OUT_DIR/"historical_build_qa.json"; qa_path.write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(qa,indent=2)); print(snap_path); print(game_path)

if __name__=="__main__": main()
