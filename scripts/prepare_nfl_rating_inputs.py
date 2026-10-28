"""Prepare Week 8 rating inputs using the pinned model's unchanged aggregators.
Run from the pinned NFL source checkout; all paths below are explicit CLI inputs.
"""
import argparse,sys,json,pathlib,hashlib
from datetime import datetime,timezone
import pandas as pd
sys.path.insert(0,str(pathlib.Path.cwd()/'scripts'))
import build_nfl_week6_research_projections as wk
import build_nfl_coverage_features as cov
ap=argparse.ArgumentParser();ap.add_argument('--cache',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--results',type=pathlib.Path,required=True);a=ap.parse_args()
cache=a.cache.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
sources=json.loads((cache/'manifest.json').read_text())
for item in sources:
 assert 'error' not in item
 assert hashlib.sha256((cache/item['file']).read_bytes()).hexdigest()==item['sha256']
wk.TARGET_WEEK=8;wk.CUTOFF_WEEK=7;wk.hist.PBP_URL=cache.as_uri()+'/play_by_play_{season}.csv.gz'
rows,qa,mw,future=wk.build_team_snapshot();assert mw==7 and future==0
cov.URL=str(cache/'advstats_week_def_{season}.parquet')
c25=cov.weekly(cov.load(2025));c26=cov.weekly(cov.load(2026));crows=[cov.snap(2026,8,t,c26,c25) for t in sorted(rows)]
assert len(rows)==len(crows)==32
assert max(r['max_current_week_used'] for r in crows)==7
res=json.loads(a.results.read_text());pbp=pd.read_csv(cache/'play_by_play_2026.csv.gz',usecols=['game_id','week','home_score','away_score']);checks=[];coverage_lag=[]
for g in res['games']:
 d=pbp[pbp.game_id.eq(g['gameId'])];assert len(d)>0,g['gameId']
 assert d.home_score.dropna().iloc[-1]==g['homeScore'],g
 assert d.away_score.dropna().iloc[-1]==g['awayScore'],g
 for t in (g['homeTeam'],g['awayTeam']):
  assert rows[t]['max_current_season_week_used']==7,t
  cw=next(r for r in crows if r['team']==t)['max_current_week_used']
  if cw<7: coverage_lag.append(dict(team=t,latestCoverageWeek=cw,expectedWeek=7))
 checks.append(g['gameId'])
assert len(checks)==14
pd.DataFrame(rows.values()).to_csv(out/'core_inputs.csv',index=False,lineterminator='\n');pd.DataFrame(crows).to_csv(out/'coverage_inputs.csv',index=False,lineterminator='\n')
manifest=dict(asOf=datetime.now(timezone.utc).isoformat(),targetWeek=8,maxSourceWeek=7,coverageLag=coverage_lag,week7FinalsCrossChecked=checks,sources=sources,files={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['core_inputs.csv','coverage_inputs.csv']})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('32 teams, 14 finals verified; source week',mw)
