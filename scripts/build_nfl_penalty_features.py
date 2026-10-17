#!/usr/bin/env python3
"""Build leakage-safe NFL team penalty tendency features from nflverse PBP.

This layer measures team penalty behavior only. It does not assign causal value
to referee crews and does not attempt a counterfactual EPA-lost calculation from
penalty plays. Target snapshots use only weeks strictly before the target week.
"""
from __future__ import annotations
import json,math,re
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

SEASONS=[2021,2022,2023,2024,2025,2026];TARGETS=[2022,2023,2024,2025];CURRENT=2026;TARGET_WEEK=6
PBP='https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet'
OUT_H=Path('nfl_data/historical/team_week_penalties_2022_2025.csv');OUT_C=Path('nfl_data/generated/penalties_2026_week6_pregame.csv');OUT_Q=Path('nfl_data/generated/penalties_build_qa_2026_week6.json')
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
METRICS=['penalties_per_game','penalty_yards_per_game','false_start_per_game','offensive_holding_per_game','dpi_per_game','defensive_holding_per_game','offsides_encroachment_per_game','personal_foul_per_game']

def nt(v):
 s=str(v or '').strip().upper();return ALIASES.get(s,s)
def num(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None
def clean(x):
 x=num(x);return None if x is None else round(x,6)
def bucket(text):
 s=str(text or '').lower()
 if 'false start' in s:return 'false_start'
 if 'offensive holding' in s:return 'offensive_holding'
 if 'pass interference' in s:return 'dpi'
 if 'defensive holding' in s:return 'defensive_holding'
 if 'offside' in s or 'offsides' in s or 'encroachment' in s or 'neutral zone infraction' in s:return 'offsides_encroachment'
 if 'personal foul' in s or 'unnecessary roughness' in s or 'roughing' in s:return 'personal_foul'
 return 'other'
def load(s):
 wanted=['season','week','season_type','game_id','home_team','away_team','penalty','penalty_team','penalty_yards','penalty_type','desc']
 # Read full schema once to tolerate seasons where penalty_type is absent.
 df=pd.read_parquet(PBP.format(season=s));available=set(df.columns);missing_required=[c for c in ['season','week','season_type','game_id','home_team','away_team','penalty','penalty_team','penalty_yards'] if c not in available]
 if missing_required:raise RuntimeError(f'{s} PBP missing penalty columns: {missing_required}')
 df=df[(pd.to_numeric(df['season'],errors='coerce')==s)&(df['season_type'].astype(str).str.upper()=='REG')].copy();df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64');df['home_team']=df['home_team'].map(nt);df['away_team']=df['away_team'].map(nt);df['penalty_team']=df['penalty_team'].map(nt);df['penalty']=pd.to_numeric(df['penalty'],errors='coerce').fillna(0);df['penalty_yards']=pd.to_numeric(df['penalty_yards'],errors='coerce').fillna(0)
 if 'penalty_type' not in df:df['penalty_type']=''
 if 'desc' not in df:df['desc']=''
 df['_ptype']=(df['penalty_type'].fillna('').astype(str)+' '+df['desc'].fillna('').astype(str)).map(bucket)
 return df,sorted(available)
def weekly(df):
 out={};team_games=defaultdict(set)
 for _,r in df.dropna(subset=['week']).iterrows():
  w=int(r['week']);gid=str(r['game_id']);h=nt(r['home_team']);a=nt(r['away_team']);team_games[(h,w)].add(gid);team_games[(a,w)].add(gid)
 # Start every team-week that actually played, so a no-penalty game is a real zero rather than missing.
 for key,gids in team_games.items():out[key]={'games':len(gids),'penalties':0.,'yards':0.,'false_start':0.,'offensive_holding':0.,'dpi':0.,'defensive_holding':0.,'offsides_encroachment':0.,'personal_foul':0.}
 z=df[(df['penalty']==1)&df['penalty_team'].astype(str).ne('')&df['penalty_team'].astype(str).ne('NAN')].copy()
 for _,r in z.dropna(subset=['week']).iterrows():
  key=(nt(r['penalty_team']),int(r['week']))
  if key not in out:continue
  out[key]['penalties']+=1;out[key]['yards']+=max(0.,float(r['penalty_yards'] or 0));b=r['_ptype']
  if b in out[key]:out[key][b]+=1
 return out,len(z)
def agg(wk,team,weeks):
 rs=[wk[(team,w)] for w in weeks if (team,w) in wk]
 if not rs:return {m:None for m in METRICS}
 games=sum(r['games'] for r in rs)
 if games<=0:return {m:None for m in METRICS}
 return {'penalties_per_game':sum(r['penalties'] for r in rs)/games,'penalty_yards_per_game':sum(r['yards'] for r in rs)/games,'false_start_per_game':sum(r['false_start'] for r in rs)/games,'offensive_holding_per_game':sum(r['offensive_holding'] for r in rs)/games,'dpi_per_game':sum(r['dpi'] for r in rs)/games,'defensive_holding_per_game':sum(r['defensive_holding'] for r in rs)/games,'offsides_encroachment_per_game':sum(r['offsides_encroachment'] for r in rs)/games,'personal_foul_per_game':sum(r['personal_foul'] for r in rs)/games}
def snap(s,tw,team,wk,prior):
 weeks=sorted(w for t,w in wk if t==team and w<tw);last3=weeks[-3:];pweeks=sorted(w for t,w in prior if t==team);cur=agg(wk,team,weeks);rec=agg(wk,team,last3);prv=agg(prior,team,pweeks);r={'season':s,'target_week':tw,'team':team,'max_current_week_used':max(weeks) if weeks else 0}
 for m in METRICS:r[f'cur_{m}']=clean(cur[m]);r[f'last3_{m}']=clean(rec[m]);r[f'prior_{m}']=clean(prv[m])
 r['release_state']='HOLD_RESEARCH_ONLY';return r
def main():
 OUT_H.parent.mkdir(parents=True,exist_ok=True);OUT_C.parent.mkdir(parents=True,exist_ok=True);data={};qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'policy':'Team penalty tendencies only; referee causality and penalty EPA counterfactual are not assumed.','seasons':{}}
 for s in SEASONS:
  df,cols=load(s);wk,pen_rows=weekly(df);teams=sorted(set(t for t,_ in wk));data[s]=(wk,teams);qa['seasons'][str(s)]={'reg_pbp_rows':len(df),'penalty_rows_used':pen_rows,'team_weeks':len(wk),'teams':len(teams),'penalty_type_available':'penalty_type' in cols}
 hist=[];leak=0
 for s in TARGETS:
  wk,teams=data[s];pr,pt=data[s-1]
  for tw in range(1,19):
   for team in sorted(set(teams)|set(pt)):
    r=snap(s,tw,team,wk,pr);leak+=int(r['max_current_week_used']>=tw);hist.append(r)
 hdf=pd.DataFrame(hist);hdf.to_csv(OUT_H,index=False);wk,teams=data[CURRENT];pr,pt=data[CURRENT-1];cur=[snap(CURRENT,TARGET_WEEK,t,wk,pr) for t in sorted(set(teams)|set(pt))];cdf=pd.DataFrame(cur);cdf.to_csv(OUT_C,index=False);future=int((cdf['max_current_week_used']>=TARGET_WEEK).sum());qa.update({'historical_rows':len(hdf),'historical_leakage_rows':leak,'current_rows':len(cdf),'current_max_week_used':int(cdf['max_current_week_used'].max()),'current_target_or_future_rows_used':future,'metrics':METRICS})
 if leak or future:raise RuntimeError(f'penalty leakage historical={leak} current={future}')
 OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'historical_rows':len(hdf),'current_rows':len(cdf),'leakage':0},indent=2))
if __name__=='__main__':main()
