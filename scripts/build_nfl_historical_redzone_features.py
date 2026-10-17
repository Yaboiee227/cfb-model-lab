#!/usr/bin/env python3
"""Build leakage-safe NFL red-zone efficiency snapshots.

Historical target seasons 2022-2025 use only weeks strictly before each target
week plus the immediately prior regular season. A 2026 Week 6 snapshot is also
built from Weeks 1-5 plus 2025. Outputs are research-only.
"""
from __future__ import annotations

import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
TARGET_SEASONS = [2022, 2023, 2024, 2025]
CURRENT_SEASON = 2026
CURRENT_TARGET_WEEK = 6
PBP = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
OUT_H = Path("nfl_data/historical/team_week_redzone_2022_2025.csv")
OUT_C = Path("nfl_data/generated/redzone_2026_week6_pregame.csv")
OUT_Q = Path("nfl_data/generated/redzone_build_qa_2026_week6.json")
ALIASES = {"LAR":"LA","STL":"LA","JAC":"JAX","WSH":"WAS","WFT":"WAS","OAK":"LV","SD":"LAC","SDG":"LAC"}
METRICS = [
    "off_rz_epa_per_play",
    "off_rz_success_rate",
    "def_rz_epa_per_play_allowed",
    "def_rz_success_rate_allowed",
]


def nt(v):
    if v is None or pd.isna(v):
        return None
    s = str(v).strip().upper()
    if not s or s in {"NAN", "NONE", "NULL"}:
        return None
    return ALIASES.get(s, s)


def clean(v):
    if v is None or pd.isna(v):
        return None
    x = float(v)
    return round(x, 6) if math.isfinite(x) else None


def fetch_parquet(season):
    url = PBP.format(season=season)
    req = urllib.request.Request(url, headers={"User-Agent":"cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    cols = [
        "season","week","season_type","game_id","posteam","defteam","play_type",
        "epa","success","yardline_100","qb_dropback","rush_attempt","qb_kneel","qb_spike",
    ]
    return pd.read_parquet(io.BytesIO(raw), columns=cols)


def season_weekly(season):
    df = fetch_parquet(season)
    df = df[(pd.to_numeric(df["season"], errors="coerce") == season) & (df["season_type"].astype(str).str.upper() == "REG")].copy()
    df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")
    df["posteam"] = df["posteam"].map(nt)
    df["defteam"] = df["defteam"].map(nt)
    df["epa"] = pd.to_numeric(df["epa"], errors="coerce")
    df["success"] = pd.to_numeric(df["success"], errors="coerce")
    df["yardline_100"] = pd.to_numeric(df["yardline_100"], errors="coerce")
    for c in ["qb_dropback","rush_attempt","qb_kneel","qb_spike"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    ptype = df["play_type"].astype(str).str.lower()
    core = (
        (ptype.isin(["pass","run"]) | df["qb_dropback"].eq(1) | df["rush_attempt"].eq(1))
        & ~ptype.eq("no_play")
        & ~df["qb_kneel"].eq(1)
        & ~df["qb_spike"].eq(1)
        & df["epa"].notna()
        & df["yardline_100"].le(20)
        & df["posteam"].notna()
        & df["defteam"].notna()
        & df["week"].notna()
    )
    rz = df[core].copy()
    off = defaultdict(dict)
    deff = defaultdict(dict)
    for (team, week), g in rz.groupby(["posteam","week"]):
        succ = g["success"].dropna()
        off[(team, int(week))] = {
            "plays": int(len(g)),
            "epa_sum": float(g["epa"].sum()),
            "success_sum": float(succ.sum()) if len(succ) else 0.0,
            "success_n": int(len(succ)),
        }
    for (team, week), g in rz.groupby(["defteam","week"]):
        succ = g["success"].dropna()
        deff[(team, int(week))] = {
            "plays": int(len(g)),
            "epa_sum": float(g["epa"].sum()),
            "success_sum": float(succ.sum()) if len(succ) else 0.0,
            "success_n": int(len(succ)),
        }
    teams = sorted(set(t for t, _ in off) | set(t for t, _ in deff))
    return off, deff, teams, len(df), len(rz)


def aggregate(store, team, weeks):
    rows = [store[(team, w)] for w in weeks if (team, w) in store]
    plays = sum(r["plays"] for r in rows)
    epa_sum = sum(r["epa_sum"] for r in rows)
    success_sum = sum(r["success_sum"] for r in rows)
    success_n = sum(r["success_n"] for r in rows)
    return {
        "plays": plays,
        "epa_per_play": None if plays == 0 else epa_sum / plays,
        "success_rate": None if success_n == 0 else success_sum / success_n,
    }


def snapshot(season, target_week, team, off, deff, prior_off, prior_def):
    cur_weeks = sorted({w for t, w in off if t == team} | {w for t, w in deff if t == team})
    cur_weeks = [w for w in cur_weeks if w < target_week]
    prior_weeks = [] if prior_off is None else sorted({w for t, w in prior_off if t == team} | {w for t, w in prior_def if t == team})
    co = aggregate(off, team, cur_weeks)
    cd = aggregate(deff, team, cur_weeks)
    if prior_off is None:
        po = {"plays":0,"epa_per_play":None,"success_rate":None}
        pd_ = {"plays":0,"epa_per_play":None,"success_rate":None}
    else:
        po = aggregate(prior_off, team, prior_weeks)
        pd_ = aggregate(prior_def, team, prior_weeks)
    return {
        "season": season,
        "target_week": target_week,
        "team": team,
        "max_current_week_used": max(cur_weeks) if cur_weeks else 0,
        "cur_off_rz_plays": co["plays"],
        "cur_off_rz_epa_per_play": clean(co["epa_per_play"]),
        "cur_off_rz_success_rate": clean(co["success_rate"]),
        "cur_def_rz_plays": cd["plays"],
        "cur_def_rz_epa_per_play_allowed": clean(cd["epa_per_play"]),
        "cur_def_rz_success_rate_allowed": clean(cd["success_rate"]),
        "prior_off_rz_plays": po["plays"],
        "prior_off_rz_epa_per_play": clean(po["epa_per_play"]),
        "prior_off_rz_success_rate": clean(po["success_rate"]),
        "prior_def_rz_plays": pd_["plays"],
        "prior_def_rz_epa_per_play_allowed": clean(pd_["epa_per_play"]),
        "prior_def_rz_success_rate_allowed": clean(pd_["success_rate"]),
        "release_state": "HOLD_RESEARCH_ONLY",
    }


def main():
    OUT_H.parent.mkdir(parents=True, exist_ok=True)
    OUT_C.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    qa = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_template": PBP,
        "definition": "Red zone = offensive scrimmage play with yardline_100 <= 20; nullified plays, kneels, spikes excluded.",
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
        "seasons": {},
    }
    for season in SEASONS:
        off, deff, teams, rows, rzrows = season_weekly(season)
        data[season] = (off, deff, teams)
        qa["seasons"][str(season)] = {
            "regular_season_rows": rows,
            "redzone_core_plays": rzrows,
            "off_team_weeks": len(off),
            "def_team_weeks": len(deff),
            "teams": len(teams),
        }

    hist = []
    leakage = 0
    for season in TARGET_SEASONS:
        off, deff, teams = data[season]
        po, pd_, pteams = data[season - 1]
        universe = sorted(set(teams) | set(pteams))
        for tw in range(1, 19):
            for team in universe:
                r = snapshot(season, tw, team, off, deff, po, pd_)
                leakage += int(r["max_current_week_used"] >= tw)
                hist.append(r)
    hdf = pd.DataFrame(hist)
    hdf.to_csv(OUT_H, index=False)

    off, deff, teams = data[CURRENT_SEASON]
    po, pd_, pteams = data[CURRENT_SEASON - 1]
    cur = [snapshot(CURRENT_SEASON, CURRENT_TARGET_WEEK, t, off, deff, po, pd_) for t in sorted(set(teams) | set(pteams))]
    cdf = pd.DataFrame(cur)
    cdf.to_csv(OUT_C, index=False)
    future = int((pd.to_numeric(cdf["max_current_week_used"], errors="coerce") >= CURRENT_TARGET_WEEK).sum())
    if leakage or future:
        raise RuntimeError(f"red-zone leakage historical={leakage} current={future}")

    qa.update({
        "historical_rows": len(hdf),
        "historical_leakage_rows": leakage,
        "current_rows": len(cdf),
        "current_max_week_used": int(cdf["max_current_week_used"].max()),
        "current_target_or_future_rows_used": future,
    })
    OUT_Q.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"historical_rows":len(hdf),"current_rows":len(cdf),"leakage":0,"qa":str(OUT_Q)}, indent=2))


if __name__ == "__main__":
    main()
