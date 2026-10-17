#!/usr/bin/env python3
"""Build leakage-safe NFL special-teams candidate features from nflverse team stats."""
from __future__ import annotations
import json,math
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

SEASONS=[2021,2022,2023,2024,2025,2026];TARGETS=[2022,2023,2024,2025];CURRENT=2026;TARGET_WEEK=6
URL='https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{season}.csv'
OUT_H=Path('nfl_data/historical/team_week_special_teams_2022_2025.csv');OUT_C=Path('nfl_data/generated/special_teams_2026_week6_pregame.csv');OUT_Q=Path('nfl_data/generated/special_teams_build_qa_2026_week6.json')
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
METRICS=['fg_pct','fg_40_49_pct','fg_50_plus_pct','pat_pct','punt_net_avg','punt_inside20_rate','punt_touchback_rate','punt_block_rate','punt_return_avg','kickoff_return_avg','special_teams_td_per_game']

def nt(v):
 s=str(v or '').strip().upper();return ALIASES.get(s,s)
def n(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None
def div(a,b):return None if b is None or b==0 else a/b
def load(s):
 df=pd.read_csv(URL.format(season=s));df=df[(pd.to_numeric(df['season'],errors='coerce')==s)&(df['season_type'].astype(str).str.upper()=='REG')].copy();df['team']=df['team'].map(nt);df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64')
 cols=['fg_made','fg_att','fg_made_40_49','fg_missed_40_49','fg_made_50_59','fg_missed_50_59','fg_made_60_','fg_missed_60_','pat_made','pat_att','pt_att','pt_blocked','pt_net_yards','pt_inside_20','pt_touchback','punt_returns','punt_return_yards','kickoff_returns','kickoff_return_yards','special_teams_tds']
 for c in cols:
  if c not in df:df[c]=0.0
  df[c]=pd.to_numeric(df[c],errors='coerce').fillna(0.0)
 return df
def weekly(df):
 out={}
 for _,r in df.dropna(subset=['week']).iterrows():
  out[(r['team'],int(r['week']))]={c:float(r[c]) for c in ['fg_made','fg_att','fg_made_40_49','fg_missed_40_49','fg_made_50_59','fg_missed_50_59','fg_made_60_','fg_missed_60_','pat_made','pat_att','pt_att','pt_blocked','pt_net_yards','pt_inside_20','pt_touchback','punt_returns','punt_return_yards','kickoff_returns','kickoff_return_yards','special_teams_tds']}
 return out
def agg(wk,team,weeks):
 rs=[wk[(team,w)] for w in weeks if (team,w) in wk]
 if not rs:return {m:None for m in METRICS}
 def s(k):return sum(r[k] for r in rs)
 fg49=s('fg_made_40_49')+s('fg_missed_40_49');fg50m=s('fg_made_50_59')+s('fg_missed_50_59');fg60=s('fg_made_60_')+s('fg_missed_60_');fg50=fg50m+fg60
 return {'fg_pct':div(s('fg_made'),s('fg_att')),'fg_40_49_pct':div(s('fg_made_40_49'),fg49),'fg_50_plus_pct':div(s('fg_made_50_59')+s('fg_made_60_'),fg50),'pat_pct':div(s('pat_made'),s('pat_att')),'punt_net_avg':div(s('pt_net_yards'),s('pt_att')),'punt_inside20_rate':div(s('pt_inside_20'),s('pt_att')),'punt_touchback_rate':div(s('pt_touchback'),s('pt_att')),'punt_block_rate':div(s('pt_blocked'),s('pt_att')),'punt_return_avg':div(s('punt_return_yards'),s('punt_returns')),'kickoff_return_avg':div(s('kickoff_return_yards'),s('kickoff_returns')),'special_teams_td_per_game':div(s('special_teams_tds'),len(rs))}
def clean(x):
 x=n(x);return None if x is None else round(x,6)
def snap(s,tw,team,wk,prior):
 weeks=sorted(w for t,w in wk if t==team and w<tw);last3=weeks[-3:];pweeks=sorted(w for t,w in prior if t==team);cur=agg(wk,team,weeks);rec=agg(wk,team,last3);prv=agg(prior,team,pweeks);r={'season':s,'target_week':tw,'team':team,'max_current_week_used':max(weeks) if weeks else 0}
 for m in METRICS:r[f'cur_{m}']=clean(cur[m]);r[f'last3_{m}']=clean(rec[m]);r[f'prior_{m}']=clean(prv[m])
 r['release_state']='HOLD_RESEARCH_ONLY';return r
def main():
 OUT_H.parent.mkdir(parents=True,exist_ok=True);OUT_C.parent.mkdir(parents=True,exist_ok=True);data={};qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'seasons':{}}
 for s in SEASONS:
  df=load(s);wk=weekly(df);teams=sorted(set(t for t,_ in wk));data[s]=(wk,teams);qa['seasons'][str(s)]={'rows':len(df),'team_weeks':len(wk),'teams':len(teams)}
 hist=[];leak=0
 for s in TARGETS:
  wk,teams=data[s];pr,pt=data[s-1]
  for tw in range(1,19):
   for team in sorted(set(teams)|set(pt)):
    r=snap(s,tw,team,wk,pr);leak+=int(r['max_current_week_used']>=tw);hist.append(r)
 hdf=pd.DataFrame(hist);hdf.to_csv(OUT_H,index=False);wk,teams=data[CURRENT];pr,pt=data[CURRENT-1];cur=[snap(CURRENT,TARGET_WEEK,t,wk,pr) for t in sorted(set(teams)|set(pt))];cdf=pd.DataFrame(cur);cdf.to_csv(OUT_C,index=False);future=int((cdf['max_current_week_used']>=TARGET_WEEK).sum());qa.update({'historical_rows':len(hdf),'historical_leakage_rows':leak,'current_rows':len(cdf),'current_max_week_used':int(cdf['max_current_week_used'].max()),'current_target_or_future_rows_used':future,'metrics':METRICS,'rare_event_note':'blocks and special-teams TDs are high-variance candidates and require heavy shrinkage/validation.'})
 if leak or future:raise RuntimeError(f'leakage historical={leak} current={future}')
 OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'historical_rows':len(hdf),'current_rows':len(cdf),'leakage':0},indent=2))
if __name__=='__main__':main()
