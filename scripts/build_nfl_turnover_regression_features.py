#!/usr/bin/env python3
"""Build leakage-safe NFL turnover/luck/regression candidate features.

Uses nflverse weekly team stats and completed schedule results. The layer is
explicitly research-only because turnover margin, fumble recovery and one-score
record are high-variance features that require shrinkage and validation.
"""
from __future__ import annotations

import io
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
TARGETS = [2022, 2023, 2024, 2025]
CURRENT = 2026
TARGET_WEEK = 6
TEAM_URL = "https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{season}.csv"
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
OUT_H = Path("nfl_data/historical/team_week_turnover_regression_2022_2025.csv")
OUT_C = Path("nfl_data/generated/turnover_regression_2026_week6_pregame.csv")
OUT_Q = Path("nfl_data/generated/turnover_regression_build_qa_2026_week6.json")
ALIASES = {"LAR":"LA","STL":"LA","JAC":"JAX","WSH":"WAS","WFT":"WAS","OAK":"LV","SD":"LAC","SDG":"LAC"}
EXPONENT = 2.37
METRICS = [
    "off_int_rate", "off_fumble_loss_rate", "giveaways_per_game",
    "def_int_rate", "def_fumble_recovery_rate", "takeaways_per_game",
    "turnover_margin_per_game", "point_diff_per_game", "win_pct",
    "pythag_win_pct", "win_pct_minus_pythag", "one_score_win_pct",
    "one_score_games_share",
]

def nt(v):
    s=str(v or "").strip().upper(); return ALIASES.get(s,s)

def n(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError,ValueError): return None

def div(a,b): return None if b is None or b==0 else a/b

def fetch_schedule():
    req=urllib.request.Request(SCHEDULE_URL,headers={"User-Agent":"cb-model-projections/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return pd.read_csv(io.BytesIO(r.read()))

def load_team(season):
    df=pd.read_csv(TEAM_URL.format(season=season))
    df=df[(pd.to_numeric(df['season'],errors='coerce')==season)&(df['season_type'].astype(str).str.upper()=='REG')].copy()
    df['team']=df['team'].map(nt);df['opponent_team']=df['opponent_team'].map(nt);df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64')
    numeric=['attempts','passing_interceptions','fumbles_total','fumbles_lost_total','def_interceptions','fumble_recovery_opp']
    for c in numeric:
        if c not in df: df[c]=0.0
        df[c]=pd.to_numeric(df[c],errors='coerce').fillna(0.0)
    return df

def schedule_team_weeks(schedule,season):
    sdf=schedule[(pd.to_numeric(schedule['season'],errors='coerce')==season)&(schedule['game_type'].astype(str).str.upper()=='REG')].copy()
    out={}
    for _,r in sdf.iterrows():
        hs=n(r.get('home_score'));aws=n(r.get('away_score'));week=n(r.get('week'))
        if hs is None or aws is None or week is None: continue
        h,a=nt(r.get('home_team')),nt(r.get('away_team'));w=int(week)
        out[(h,w)]={'pf':hs,'pa':aws,'margin':hs-aws,'win':1.0 if hs>aws else 0.5 if hs==aws else 0.0}
        out[(a,w)]={'pf':aws,'pa':hs,'margin':aws-hs,'win':1.0 if aws>hs else 0.5 if hs==aws else 0.0}
    return out

def weekly_rows(df,sched):
    by={(r['team'],int(r['week'])):r for _,r in df.dropna(subset=['week']).iterrows()}
    out={}
    for key,r in by.items():
        team,week=key;opp=nt(r['opponent_team']);opp_row=by.get((opp,week));game=sched.get(key)
        opp_attempts=None if opp_row is None else float(opp_row['attempts'])
        opp_fumbles=None if opp_row is None else float(opp_row['fumbles_total'])
        giveaways=float(r['passing_interceptions']+r['fumbles_lost_total'])
        takeaways=float(r['def_interceptions']+r['fumble_recovery_opp'])
        out[key]={
            'attempts':float(r['attempts']),'ints_thrown':float(r['passing_interceptions']),
            'fumbles':float(r['fumbles_total']),'fumbles_lost':float(r['fumbles_lost_total']),
            'opp_attempts':opp_attempts,'def_ints':float(r['def_interceptions']),
            'opp_fumbles':opp_fumbles,'fumbles_recovered':float(r['fumble_recovery_opp']),
            'giveaways':giveaways,'takeaways':takeaways,
            'pf':None if game is None else game['pf'],'pa':None if game is None else game['pa'],
            'margin':None if game is None else game['margin'],'win':None if game is None else game['win'],
        }
    return out

def agg(wk,team,weeks):
    rows=[wk[(team,w)] for w in weeks if (team,w) in wk]
    if not rows:return {m:None for m in METRICS}
    def s(k):return sum((n(r.get(k)) or 0) for r in rows)
    games=len(rows);attempts=s('attempts');opp_attempts=s('opp_attempts');fumbles=s('fumbles');opp_fumbles=s('opp_fumbles')
    pf,pa=s('pf'),s('pa');wins=s('win');one=[r for r in rows if n(r.get('margin')) is not None and abs(r['margin'])<=8]
    one_wins=sum((n(r.get('win')) or 0) for r in one)
    pyth=None
    if pf>0 or pa>0:
        den=(pf**EXPONENT)+(pa**EXPONENT);pyth=None if den<=0 else (pf**EXPONENT)/den
    winpct=div(wins,games)
    return {
        'off_int_rate':div(s('ints_thrown'),attempts),'off_fumble_loss_rate':div(s('fumbles_lost'),fumbles),
        'giveaways_per_game':div(s('giveaways'),games),'def_int_rate':div(s('def_ints'),opp_attempts),
        'def_fumble_recovery_rate':div(s('fumbles_recovered'),opp_fumbles),'takeaways_per_game':div(s('takeaways'),games),
        'turnover_margin_per_game':div(s('takeaways')-s('giveaways'),games),'point_diff_per_game':div(pf-pa,games),
        'win_pct':winpct,'pythag_win_pct':pyth,'win_pct_minus_pythag':None if winpct is None or pyth is None else winpct-pyth,
        'one_score_win_pct':div(one_wins,len(one)),'one_score_games_share':div(len(one),games),
    }

def clean(x):
    x=n(x);return None if x is None else round(x,6)

def snap(season,tw,team,wk,prior):
    weeks=sorted(w for t,w in wk if t==team and w<tw);last3=weeks[-3:];pweeks=sorted(w for t,w in prior if t==team)
    cur=agg(wk,team,weeks);rec=agg(wk,team,last3);prv=agg(prior,team,pweeks)
    r={'season':season,'target_week':tw,'team':team,'max_current_week_used':max(weeks) if weeks else 0}
    for m in METRICS:r[f'cur_{m}']=clean(cur[m]);r[f'last3_{m}']=clean(rec[m]);r[f'prior_{m}']=clean(prv[m])
    r['release_state']='HOLD_RESEARCH_ONLY';return r

def main():
    OUT_H.parent.mkdir(parents=True,exist_ok=True);OUT_C.parent.mkdir(parents=True,exist_ok=True)
    sched=fetch_schedule();data={};qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'pythagorean_exponent_candidate':EXPONENT,'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'seasons':{}}
    for s in SEASONS:
        df=load_team(s);sw=schedule_team_weeks(sched,s);wk=weekly_rows(df,sw);teams=sorted(set(t for t,_ in wk));data[s]=(wk,teams)
        qa['seasons'][str(s)]={'team_stat_rows':int(len(df)),'completed_schedule_team_weeks':len(sw),'feature_team_weeks':len(wk),'teams':len(teams)}
    hist=[];leak=0
    for s in TARGETS:
        wk,teams=data[s];pr,pt=data[s-1]
        for tw in range(1,19):
            for team in sorted(set(teams)|set(pt)):
                r=snap(s,tw,team,wk,pr);leak+=int(r['max_current_week_used']>=tw);hist.append(r)
    hdf=pd.DataFrame(hist);hdf.to_csv(OUT_H,index=False)
    wk,teams=data[CURRENT];pr,pt=data[CURRENT-1];cur=[snap(CURRENT,TARGET_WEEK,t,wk,pr) for t in sorted(set(teams)|set(pt))];cdf=pd.DataFrame(cur);cdf.to_csv(OUT_C,index=False)
    future=int((cdf['max_current_week_used']>=TARGET_WEEK).sum());qa.update({'historical_rows':len(hdf),'historical_leakage_rows':leak,'current_rows':len(cdf),'current_max_week_used':int(cdf['max_current_week_used'].max()),'current_target_or_future_rows_used':future,'metrics':METRICS,'high_variance_note':'Turnover margin, fumble recovery, one-score record and win-vs-Pythagorean are regression candidates, not assumed persistent skill.'})
    if leak or future:raise RuntimeError(f'leakage historical={leak} current={future}')
    OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'historical_rows':len(hdf),'current_rows':len(cdf),'leakage':0},indent=2))
if __name__=='__main__':main()
