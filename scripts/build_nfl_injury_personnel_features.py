#!/usr/bin/env python3
"""Build leakage-safe NFL injury/personnel burden features.

2022-2024: injury revisions are timestamped; select latest row strictly before
scheduled kickoff. 2025-2026: source lacks revision timestamp; use the final
week-scoped report and label lower timestamp quality.

Player importance is based only on prior snap share (current season weeks before
target, falling back to prior completed season). No target-game snaps are used.
Development only / HOLD.
"""
from __future__ import annotations
import io,json,math,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

SEASONS=[2021,2022,2023,2024,2025,2026];TARGETS=[2022,2023,2024,2025];CURRENT=2026;TARGET_WEEK=6
INJ='https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.parquet'
SNAP='https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_{season}.parquet'
SCHEDULE='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
OUT_H=Path('nfl_data/historical/team_week_injury_personnel_2022_2025.csv');OUT_C=Path('nfl_data/generated/injury_personnel_2026_week6_pregame.csv');OUT_Q=Path('nfl_data/generated/injury_personnel_build_qa_2026_week6.json')
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
STATUS_WEIGHT={'OUT':1.0,'DOUBTFUL':0.75,'QUESTIONABLE':0.35}
GROUPS=['qb','ol','skill','front7','db','other']
METRICS=['injured_count','out_count','doubtful_count','questionable_count','snap_weighted_burden','known_importance_share','high_snap_severe_count']+[f'{g}_count' for g in GROUPS]+[f'{g}_weighted_burden' for g in GROUPS]

def nt(v):
 s=str(v or '').strip().upper();return ALIASES.get(s,s)
def n(v):
 try:
  x=float(v);return x if math.isfinite(x) else None
 except (TypeError,ValueError):return None
def norm_name(v):
 s=str(v or '').lower();s=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',s);return re.sub(r'[^a-z0-9]','',s)
def group(pos):
 p=str(pos or '').upper().strip()
 if p=='QB':return 'qb'
 if p in {'C','G','OG','LG','RG','T','OT','LT','RT','OL'}:return 'ol'
 if p in {'WR','RB','FB','TE','HB'}:return 'skill'
 if p in {'DL','DE','DT','NT','EDGE','ED','LB','ILB','OLB','MLB'}:return 'front7'
 if p in {'CB','DB','S','SS','FS'}:return 'db'
 return 'other'
def fetch_schedule():
 req=urllib.request.Request(SCHEDULE,headers={'User-Agent':'cb-model-projections/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:return pd.read_csv(io.BytesIO(r.read()))
def kickoff_map(schedule,season):
 df=schedule[(pd.to_numeric(schedule['season'],errors='coerce')==season)&(schedule['game_type'].astype(str).str.upper()=='REG')].copy();out={};missing=0
 for _,r in df.iterrows():
  w=n(r.get('week'));day=str(r.get('gameday','')).strip();tm=str(r.get('gametime','')).strip()
  if w is None or not day:continue
  if not tm or tm.lower()=='nan':missing+=1;continue
  try:
   local=datetime.fromisoformat(f'{day}T{tm}').replace(tzinfo=ZoneInfo('America/New_York'));utc=local.astimezone(timezone.utc)
  except Exception:missing+=1;continue
  for team in [nt(r.get('home_team')),nt(r.get('away_team'))]:out[(team,int(w))]=utc
 return out,missing
def load_snaps(season):
 df=pd.read_parquet(SNAP.format(season=season));df=df[pd.to_numeric(df['season'],errors='coerce')==season].copy();df['team']=df['team'].map(nt);df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64');df['name_key']=df['player'].map(norm_name)
 for c in ['offense_pct','defense_pct']:
  df[c]=pd.to_numeric(df[c],errors='coerce')
  if df[c].dropna().max()>1.5:df[c]/=100.0
 df['snap_importance']=df[['offense_pct','defense_pct']].max(axis=1,skipna=True)
 return df
def load_inj(season):
 df=pd.read_parquet(INJ.format(season=season));df=df[pd.to_numeric(df['season'],errors='coerce')==season].copy()
 if 'season_type' in df.columns:
  st=df['season_type'].astype(str).str.upper();df=df[(st=='REG')|(st=='NAN')|(st=='')]
 elif 'game_type' in df.columns:
  gt=df['game_type'].astype(str).str.upper();df=df[(gt=='REG')|(gt=='NAN')|(gt=='')]
 df['team']=df['team'].map(nt);df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64');df['name_key']=df['full_name'].map(norm_name);df['status']=df['report_status'].astype(str).str.upper().str.strip().replace({'NAN':''})
 if 'date_modified' in df.columns:df['date_modified']=pd.to_datetime(df['date_modified'],utc=True,errors='coerce')
 return df
def snap_importance(snaps,prior_snaps,team,name_key,target_week):
 cur=snaps[(snaps['team']==team)&(snaps['name_key']==name_key)&(snaps['week']<target_week)]['snap_importance'].dropna()
 if len(cur):return float(cur.mean()),'CURRENT_PRIOR_WEEKS'
 prv=prior_snaps[prior_snaps['name_key']==name_key]['snap_importance'].dropna()
 if len(prv):return float(prv.mean()),'PRIOR_SEASON_PLAYER'
 return None,'UNKNOWN'
def weekly_injury_snapshot(df,season,team,week,kickoff):
 x=df[(df['team']==team)&(df['week']==week)].copy()
 if not len(x):return x,'NO_ROWS',0
 conflicts=0
 if 'date_modified' in x.columns and season<=2024:
  if kickoff is None:return x.iloc[0:0].copy(),'MISSING_KICKOFF_FOR_TIMESTAMP_FILTER',0
  x=x[x['date_modified'].notna()&(x['date_modified']<kickoff)].copy()
  if not len(x):return x,'NO_PREKICKOFF_ROWS',0
  x=x.sort_values('date_modified').groupby('name_key',as_index=False).tail(1)
  return x,'EXACT_PREKICKOFF_TIMESTAMP',0
 # 2025+ has no revision timestamp. Prefer a row with a game designation; if conflicting,
 # retain most severe designation and record the conflict for QA.
 rows=[]
 severity={'OUT':3,'DOUBTFUL':2,'QUESTIONABLE':1,'':0}
 for _,g in x.groupby('name_key'):
  statuses=set(s for s in g['status'] if s)
  conflicts+=int(len(statuses)>1)
  g=g.assign(_sev=g['status'].map(severity).fillna(0));rows.append(g.sort_values('_sev').tail(1).drop(columns=['_sev']))
 return pd.concat(rows,ignore_index=True) if rows else x.iloc[0:0].copy(),'FINAL_WEEK_REPORT_NO_REVISION_TIMESTAMP',conflicts
def build_team(season,week,team,inj,snaps,prior_snaps,kickoff):
 rep,quality,conflicts=weekly_injury_snapshot(inj,season,team,week,kickoff);vals={m:0.0 for m in METRICS};known=0;total=0;source_counts={}
 for _,r in rep.iterrows():
  status=str(r.get('status','')).upper();sev=STATUS_WEIGHT.get(status)
  if sev is None:continue
  total+=1;vals['injured_count']+=1;vals[status.lower()+'_count' if status!='QUESTIONABLE' else 'questionable_count']+=1
  imp,src=snap_importance(snaps,prior_snaps,team,r['name_key'],week);source_counts[src]=source_counts.get(src,0)+1;g=group(r.get('position'));vals[f'{g}_count']+=1
  if imp is not None:
   known+=1;weighted=sev*imp;vals['snap_weighted_burden']+=weighted;vals[f'{g}_weighted_burden']+=weighted
   if sev>=0.75 and imp>=0.5:vals['high_snap_severe_count']+=1
 vals['known_importance_share']=None if total==0 else known/total
 return vals,quality,conflicts,source_counts,len(rep)
def clean(x):
 x=n(x);return None if x is None else round(x,6)
def main():
 OUT_H.parent.mkdir(parents=True,exist_ok=True);OUT_C.parent.mkdir(parents=True,exist_ok=True);schedule=fetch_schedule();data={};qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'status_weights_for_research_only':STATUS_WEIGHT,'seasons':{},'timestamp_policy':{'2022_2024':'latest injury revision strictly before scheduled kickoff','2025_2026':'final week-scoped report; no revision timestamp available'}}
 for s in SEASONS:
  snaps=load_snaps(s);inj=load_inj(s);ko,missing=kickoff_map(schedule,s);teams=sorted(set(inj['team'].dropna())|set(snaps['team'].dropna()));data[s]=(snaps,inj,ko,teams);qa['seasons'][str(s)]={'snap_rows':len(snaps),'injury_rows':len(inj),'teams':len(teams),'kickoff_keys':len(ko),'games_missing_exact_gametime':missing,'timestamp_available':'date_modified' in inj.columns,'status_counts':{str(k):int(v) for k,v in inj['status'].value_counts().head(12).items()}}
 hist=[];quality_counts={};conflict_total=0
 for s in TARGETS:
  snaps,inj,ko,teams=data[s];prior=data[s-1][0]
  for week in range(1,19):
   for team in teams:
    vals,q,c,src,report_rows=build_team(s,week,team,inj,snaps,prior,ko.get((team,week)));quality_counts[q]=quality_counts.get(q,0)+1;conflict_total+=c;r={'season':s,'target_week':week,'team':team,'report_quality':q,'report_conflicts':c,'report_rows':report_rows}
    for m in METRICS:r[m]=clean(vals[m])
    r['release_state']='HOLD_RESEARCH_ONLY';hist.append(r)
 hdf=pd.DataFrame(hist);hdf.to_csv(OUT_H,index=False)
 snaps,inj,ko,teams=data[CURRENT];prior=data[CURRENT-1][0];cur=[]
 for team in teams:
  vals,q,c,src,rr=build_team(CURRENT,TARGET_WEEK,team,inj,snaps,prior,ko.get((team,TARGET_WEEK)));r={'season':CURRENT,'target_week':TARGET_WEEK,'team':team,'report_quality':q,'report_conflicts':c,'report_rows':rr};r.update({m:clean(vals[m]) for m in METRICS});r['release_state']='HOLD_RESEARCH_ONLY';cur.append(r)
 cdf=pd.DataFrame(cur);cdf.to_csv(OUT_C,index=False);qa.update({'historical_rows':len(hdf),'current_rows':len(cdf),'quality_counts_historical':quality_counts,'status_conflict_groups_historical':conflict_total,'metrics':METRICS,'importance_rule':'Mean prior offensive/defensive snap percentage, current-season pregame history first, previous completed season fallback; unknown remains unknown.','leakage_rule':'No target-game snap participation is used. 2022-24 injury revisions must predate kickoff.'});OUT_Q.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'historical_rows':len(hdf),'current_rows':len(cdf),'quality':quality_counts},indent=2))
if __name__=='__main__':main()
