#!/usr/bin/env python3
"""Build leakage-safe NFL scheme/charting features from nflverse FTN charting.

FTN charting is postgame information. Therefore target-week snapshots use only
charted plays from strictly earlier weeks. 2022 has no 2021 FTN prior and those
early values remain missing rather than being fabricated.
"""
from __future__ import annotations
import json,math
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd

SEASONS=[2022,2023,2024,2025,2026];TARGETS=[2022,2023,2024,2025];CURRENT=2026;TARGET_WEEK=6
FTN='https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_{season}.parquet'
PBP='https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet'
OUT_H=Path('nfl_data/historical/team_week_ftn_charting_2022_2025.csv');OUT_C=Path('nfl_data/generated/ftn_charting_2026_week6_pregame.csv');OUT_Q=Path('nfl_data/generated/ftn_charting_build_qa_2026_week6.json')
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
BINARY=['is_no_huddle','is_motion','is_play_action','is_screen_pass','is_rpo','is_qb_out_of_pocket','is_interception_worthy','is_throw_away','is_catchable_ball','is_contested_ball','is_created_reception','is_drop','is_qb_fault_sack']
NUMERIC=['n_offense_backfield','n_defense_box','n_blitzers','n_pass_rushers']
OFF_METRICS=['no_huddle_rate','motion_rate','play_action_rate','screen_rate','rpo_rate','qb_out_of_pocket_rate','interception_worthy_rate','throwaway_rate','catchable_rate','contested_rate','created_reception_rate','drop_rate','qb_fault_sack_rate','avg_offense_backfield','avg_defense_box_faced','avg_blitzers_faced','avg_pass_rushers_faced']
DEF_METRICS=['def_no_huddle_faced_rate','def_motion_faced_rate','def_play_action_faced_rate','def_screen_faced_rate','def_rpo_faced_rate','def_qb_out_of_pocket_faced_rate','def_interception_worthy_forced_rate','def_throwaway_forced_rate','def_catchable_allowed_rate','def_contested_rate','def_created_reception_allowed_rate','def_drop_rate','def_qb_fault_sack_rate','def_avg_offense_backfield_faced','def_avg_box','def_avg_blitzers','def_avg_pass_rushers']
ALL=OFF_METRICS+DEF_METRICS

def nt(v):
 if v is None or pd.isna(v):return None
 s=str(v).strip().upper()
 if not s or s in {'NAN','NONE','NULL'}:return None
 return ALIASES.get(s,s)
def num(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None
def clean(x):
 x=num(x);return None if x is None else round(x,6)
def load_season(s):
 f=pd.read_parquet(FTN.format(season=s));p=pd.read_parquet(PBP.format(season=s),columns=['game_id','play_id','season','week','season_type','posteam','defteam'])
 p=p[(pd.to_numeric(p['season'],errors='coerce')==s)&(p['season_type'].astype(str).str.upper()=='REG')].copy();p['posteam']=p['posteam'].map(nt);p['defteam']=p['defteam'].map(nt)
 f=f[pd.to_numeric(f['season'],errors='coerce')==s].copy()
 f['_gid']=f['nflverse_game_id'].astype(str);f['_pid']=pd.to_numeric(f['nflverse_play_id'],errors='coerce').astype('Int64');p['_gid']=p['game_id'].astype(str);p['_pid']=pd.to_numeric(p['play_id'],errors='coerce').astype('Int64')
 # PBP is authoritative for week and possession/defense team identity. Rename
 # those fields before merging so similarly named FTN metadata cannot shadow them.
 pjoin=p[['_gid','_pid','week','posteam','defteam']].rename(columns={'week':'pbp_week','posteam':'pbp_posteam','defteam':'pbp_defteam'})
 j=f.merge(pjoin,how='left',on=['_gid','_pid'],validate='many_to_one')
 j['week']=pd.to_numeric(j['pbp_week'],errors='coerce').astype('Int64');j['posteam']=j['pbp_posteam'].map(nt);j['defteam']=j['pbp_defteam'].map(nt)
 for c in BINARY:
  if c not in j:j[c]=float('nan')
  if j[c].dtype==bool:j[c]=j[c].astype(float)
  else:j[c]=pd.to_numeric(j[c],errors='coerce')
 for c in NUMERIC:
  if c not in j:j[c]=float('nan')
  j[c]=pd.to_numeric(j[c],errors='coerce')
 return f,p,j
def aggregate_rows(g,prefix=''):
 if not len(g):return {m:None for m in (OFF_METRICS if not prefix else DEF_METRICS)}
 def mean(c):
  x=g[c].dropna();return None if x.empty else float(x.mean())
 vals=[mean(c) for c in BINARY]+[mean(c) for c in NUMERIC]
 names=OFF_METRICS if not prefix else DEF_METRICS
 return dict(zip(names,vals))
def weekly(j):
 off={};deff={}
 z=j.dropna(subset=['week','posteam','defteam']).copy()
 for (team,w),g in z.groupby(['posteam','week']):off[(team,int(w))]=aggregate_rows(g)
 for (team,w),g in z.groupby(['defteam','week']):deff[(team,int(w))]=aggregate_rows(g,prefix='def')
 return off,deff
def agg_weekly(d,team,weeks,metrics):
 rs=[d[(team,w)] for w in weeks if (team,w) in d]
 if not rs:return {m:None for m in metrics}
 out={}
 for m in metrics:
  vals=[num(r.get(m)) for r in rs];vals=[v for v in vals if v is not None];out[m]=None if not vals else sum(vals)/len(vals)
 return out
def snap(s,tw,team,off,deff,prior_off,prior_def):
 weeks=sorted(set(w for t,w in off if t==team)|set(w for t,w in deff if t==team));weeks=[w for w in weeks if w<tw];last3=weeks[-3:]
 pweeks=sorted(set(w for t,w in prior_off if t==team)|set(w for t,w in prior_def if t==team)) if prior_off is not None else []
 cur={**agg_weekly(off,team,weeks,OFF_METRICS),**agg_weekly(deff,team,weeks,DEF_METRICS)};rec={**agg_weekly(off,team,last3,OFF_METRICS),**agg_weekly(deff,team,last3,DEF_METRICS)}
 if prior_off is None:prv={m:None for m in ALL}
 else:prv={**agg_weekly(prior_off,team,pweeks,OFF_METRICS),**agg_weekly(prior_def,team,pweeks,DEF_METRICS)}
 r={'season':s,'target_week':tw,'team':team,'max_current_week_used':max(weeks) if weeks else 0}
 for m in ALL:r[f'cur_{m}']=clean(cur[m]);r[f'last3_{m}']=clean(rec[m]);r[f'prior_{m}']=clean(prv[m])
 r['release_state']='HOLD_RESEARCH_ONLY';return r
def main():
 OUT_H.parent.mkdir(parents=True,exist_ok=True);OUT_C.parent.mkdir(parents=True,exist_ok=True);data={};qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'postgame_shift_rule':'Target week uses FTN charting only from weeks strictly before target_week.','join_authority':'PBP supplies canonical week/posteam/defteam; FTN supplies charting labels only.','seasons':{}}
 for s in SEASONS:
  f,p,j=load_season(s);off,deff=weekly(j);teams=sorted(set(t for t,_ in off)|set(t for t,_ in deff));data[s]=(off,deff,teams);joined=int(j['posteam'].notna().sum());qa['seasons'][str(s)]={'ftn_rows':len(f),'reg_pbp_rows':len(p),'joined_rows':len(j),'joined_with_team':joined,'join_rate':round(joined/len(j),6) if len(j) else None,'team_weeks_offense':len(off),'team_weeks_defense':len(deff),'teams':len(teams),'max_joined_week':int(j['week'].dropna().max()) if j['week'].notna().any() else None}
 hist=[];leak=0
 for s in TARGETS:
  off,deff,teams=data[s];prior=data.get(s-1)
  if prior is None:po,pd_,pt=None,None,[]
  else:po,pd_,pt=prior
  for tw in range(1,19):
   for team in sorted(set(teams)|set(pt)):
    r=snap(s,tw,team,off,deff,po,pd_);leak+=int(r['max_current_week_used']>=tw);hist.append(r)
 hdf=pd.DataFrame(hist);hdf.to_csv(OUT_H,index=False)
 off,deff,teams=data[CURRENT];po,pd_,pt=data[CURRENT-1];cur=[snap(CURRENT,TARGET_WEEK,t,off,deff,po,pd_) for t in sorted(set(teams)|set(pt))];cdf=pd.DataFrame(cur);cdf.to_csv(OUT_C,index=False);future=int((cdf['max_current_week_used']>=TARGET_WEEK).sum());qa.update({'historical_rows':len(hdf),'historical_leakage_rows':leak,'current_rows':len(cdf),'current_max_week_used':int(cdf['max_current_week_used'].max()),'current_target_or_future_rows_used':future,'metrics':ALL})
 if leak or future:raise RuntimeError(f'FTN leakage historical={leak} current={future}')
 OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'historical_rows':len(hdf),'current_rows':len(cdf),'leakage':0,'qa':str(OUT_Q)},indent=2))
if __name__=='__main__':main()
