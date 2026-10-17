#!/usr/bin/env python3
"""Build leakage-safe NFL defensive coverage / tackling features from PFR advanced defense.

Development only. Historical snapshots use target-season weeks strictly before
the target week; 2021 is only a prior for 2022. Current 2026 Week 6 uses Weeks 1-5.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

SEASONS=[2021,2022,2023,2024,2025,2026]
TARGETS=[2022,2023,2024,2025]
CURRENT=2026; TARGET_WEEK=6
URL='https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_def_{season}.parquet'
OUT_H=Path('nfl_data/historical/team_week_coverage_2022_2025.csv')
OUT_C=Path('nfl_data/generated/coverage_2026_week6_pregame.csv')
OUT_Q=Path('nfl_data/generated/coverage_build_qa_2026_week6.json')
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
METRICS=['coverage_completion_pct','coverage_yards_per_target','coverage_td_rate','coverage_int_rate','coverage_passer_rating_allowed','coverage_adot_allowed','coverage_yac_per_completion','coverage_missed_tackle_rate']

def nt(v):
 s=str(v or '').strip().upper(); return ALIASES.get(s,s)

def num(v):
 try:
  x=float(v); return x if math.isfinite(x) else None
 except (TypeError,ValueError): return None

def div(a,b): return None if b is None or b==0 else a/b

def load(season):
 df=pd.read_parquet(URL.format(season=season)); df=df[pd.to_numeric(df['season'],errors='coerce')==season].copy()
 if 'game_type' in df:
  gt=df['game_type'].astype(str).str.upper(); df=df[(gt=='REG')|(gt=='')|(gt=='NAN')]
 df['team']=df['team'].map(nt); df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64')
 needed=['def_targets','def_completions_allowed','def_yards_allowed','def_receiving_td_allowed','def_ints','def_passer_rating_allowed','def_adot','def_yards_after_catch','def_tackles_combined','def_missed_tackles']
 for c in needed:
  if c not in df: df[c]=float('nan')
  df[c]=pd.to_numeric(df[c],errors='coerce')
 return df

def weekly(df):
 out={}
 for (team,week),g in df.dropna(subset=['week']).groupby(['team','week']):
  week=int(week); targets=float(g['def_targets'].fillna(0).sum()); comps=float(g['def_completions_allowed'].fillna(0).sum()); yards=float(g['def_yards_allowed'].fillna(0).sum()); tds=float(g['def_receiving_td_allowed'].fillna(0).sum()); ints=float(g['def_ints'].fillna(0).sum()); yac=float(g['def_yards_after_catch'].fillna(0).sum()); tackles=float(g['def_tackles_combined'].fillna(0).sum()); missed=float(g['def_missed_tackles'].fillna(0).sum())
  def wavg(col):
   z=g[[col,'def_targets']].dropna(); den=float(z['def_targets'].sum()) if len(z) else 0
   return None if den<=0 else float((z[col]*z['def_targets']).sum()/den)
  out[(team,week)]={'targets':targets,'comps':comps,'yards':yards,'tds':tds,'ints':ints,'yac':yac,'tackles':tackles,'missed':missed,'rating_num':None,'adot_num':None,'coverage_passer_rating_allowed':wavg('def_passer_rating_allowed'),'coverage_adot_allowed':wavg('def_adot')}
 return out

def agg(wk,team,weeks):
 rows=[wk[(team,w)] for w in weeks if (team,w) in wk]
 if not rows:return {m:None for m in METRICS}
 sums={k:sum((num(r.get(k)) or 0) for r in rows) for k in ['targets','comps','yards','tds','ints','yac','tackles','missed']}
 def weighted(key):
  vals=[]
  for r in rows:
   v=num(r.get(key)); t=num(r.get('targets'))
   if v is not None and t is not None and t>0:vals.append((v,t))
  den=sum(t for _,t in vals)
  return None if den<=0 else sum(v*t for v,t in vals)/den
 return {
  'coverage_completion_pct':div(sums['comps'],sums['targets']),
  'coverage_yards_per_target':div(sums['yards'],sums['targets']),
  'coverage_td_rate':div(sums['tds'],sums['targets']),
  'coverage_int_rate':div(sums['ints'],sums['targets']),
  'coverage_passer_rating_allowed':weighted('coverage_passer_rating_allowed'),
  'coverage_adot_allowed':weighted('coverage_adot_allowed'),
  'coverage_yac_per_completion':div(sums['yac'],sums['comps']),
  'coverage_missed_tackle_rate':div(sums['missed'],sums['tackles']+sums['missed']),
 }

def clean(x):
 x=num(x); return None if x is None else round(x,6)

def snap(season,tw,team,wk,prior):
 weeks=sorted(w for t,w in wk if t==team and w<tw); last3=weeks[-3:]; pweeks=sorted(w for t,w in prior if t==team)
 cur=agg(wk,team,weeks); rec=agg(wk,team,last3); prv=agg(prior,team,pweeks)
 r={'season':season,'target_week':tw,'team':team,'max_current_week_used':max(weeks) if weeks else 0}
 for m in METRICS:r[f'cur_{m}']=clean(cur[m]);r[f'last3_{m}']=clean(rec[m]);r[f'prior_{m}']=clean(prv[m])
 r['release_state']='HOLD_RESEARCH_ONLY';return r

def main():
 OUT_H.parent.mkdir(parents=True,exist_ok=True); OUT_C.parent.mkdir(parents=True,exist_ok=True)
 data={};qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'seasons':{}}
 for s in SEASONS:
  df=load(s);wk=weekly(df); teams=sorted(set(t for t,_ in wk)); data[s]=(wk,teams);qa['seasons'][str(s)]={'rows':int(len(df)),'team_weeks':len(wk),'teams':len(teams),'max_week':int(df['week'].dropna().max()),'non_null':{m:int(df[c].notna().sum()) for m,c in {'targets':'def_targets','rating':'def_passer_rating_allowed','adot':'def_adot','missed':'def_missed_tackles'}.items()}}
 hist=[];leak=0
 for s in TARGETS:
  wk,teams=data[s];prior,pteams=data[s-1]
  for tw in range(1,19):
   for team in sorted(set(teams)|set(pteams)):
    r=snap(s,tw,team,wk,prior); leak+=int(r['max_current_week_used']>=tw);hist.append(r)
 hdf=pd.DataFrame(hist);hdf.to_csv(OUT_H,index=False)
 wk,teams=data[CURRENT];prior,pteams=data[CURRENT-1];cur=[snap(CURRENT,TARGET_WEEK,t,wk,prior) for t in sorted(set(teams)|set(pteams))];cdf=pd.DataFrame(cur);cdf.to_csv(OUT_C,index=False)
 future=int((cdf['max_current_week_used']>=TARGET_WEEK).sum());qa.update({'historical_rows':len(hdf),'historical_leakage_rows':leak,'current_rows':len(cdf),'current_max_week_used':int(cdf['max_current_week_used'].max()),'current_target_or_future_rows_used':future,'metrics':METRICS,'pregame_rule':'target-season source weeks strictly less than target_week'})
 if leak or future:raise RuntimeError(f'coverage leakage historical={leak} current={future}')
 OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'historical_rows':len(hdf),'current_rows':len(cdf),'leakage':0,'qa':str(OUT_Q)},indent=2))
if __name__=='__main__':main()
