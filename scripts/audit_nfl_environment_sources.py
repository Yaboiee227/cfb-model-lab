#!/usr/bin/env python3
"""Audit historical/current NFL schedule context and environment source coverage.
Development-only. This script does not build production features.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

SEASONS=list(range(2021,2027))
URL='https://github.com/nflverse/nfldata/raw/master/data/games.csv'
OUT=Path('nfl_data/generated/environment_source_audit_2021_2026.json')
CANDIDATES=['game_id','season','week','game_type','gameday','gametime','weekday','away_team','home_team','location','result','total','overtime','old_game_id','gsis','nfl_detail_id','pfr','pff','espn','away_rest','home_rest','away_moneyline','home_moneyline','spread_line','away_spread_odds','home_spread_odds','total_line','under_odds','over_odds','div_game','roof','surface','temp','wind','away_qb_id','home_qb_id','away_coach','home_coach','referee','stadium_id','stadium']

def finite_count(s):
 x=pd.to_numeric(s,errors='coerce'); return int(x.notna().sum())

def main():
 OUT.parent.mkdir(parents=True,exist_ok=True)
 df=pd.read_csv(URL,low_memory=False)
 cols=list(df.columns)
 qa={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_url':URL,'columns':cols,'candidate_columns_present':[c for c in CANDIDATES if c in cols],'seasons':{},'release_state':'HOLD_AUDIT_ONLY','website_publish_allowed':False}
 for season in SEASONS:
  x=df[(pd.to_numeric(df.get('season'),errors='coerce')==season)&(df.get('game_type').astype(str).str.upper()=='REG')].copy()
  s={'rows':int(len(x)),'completed_rows':int(pd.to_numeric(x.get('home_score'),errors='coerce').notna().sum()) if 'home_score' in x else None}
  for c in ['away_rest','home_rest','temp','wind']:
   if c in x:s[f'{c}_non_null']=finite_count(x[c])
  for c in ['roof','surface','location','stadium','stadium_id','referee','weekday','gametime','div_game']:
   if c in x:
    vals=x[c].dropna().astype(str).str.strip();s[f'{c}_non_null']=int(vals.ne('').sum());s[f'{c}_unique_sample']=sorted(vals[vals.ne('')].unique().tolist())[:25]
  qa['seasons'][str(season)]=s
 OUT.write_text(json.dumps(qa,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'output':str(OUT),'seasons':qa['seasons'],'release_state':qa['release_state']},indent=2))
if __name__=='__main__':main()
