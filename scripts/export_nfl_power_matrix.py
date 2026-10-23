"""Export existing NFL canonical neutral matchups from a pinned model checkout.
Run from the source checkout; output is a new artifact, never a freeze rewrite.
"""
import argparse,csv,json,sys,hashlib,subprocess
from pathlib import Path
import numpy as np
import pandas as pd
ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args()
sys.path.insert(0,str(Path('scripts').resolve()))
import run_nfl_walk_forward as base
import validate_nfl_coverage_v1 as cov
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as model
snap=Path('nfl_data/prospective/week7/20261021T114427Z')
manifest=json.loads((snap/'manifest.json').read_text())
read=lambda p:list(csv.DictReader(Path(p).open()))
# Verify exact historical bytes used in the preserved fit.
for p,digest in manifest['source_hashes'].items():
    assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest,p
for name in ['core_inputs.csv','coverage_inputs.csv','game_feature_inputs.csv','paired_projections.csv']:
    assert hashlib.sha256((snap/name).read_bytes()).hexdigest()==manifest['files'][name],name
rows=base.load_rows();ci,leak,_=cov.loadidx(cov.COV,'cov');assert leak==0
hist=[]
for r in rows:
    x=dict(r)
    for side in ['home','away']:
        z=ci[(r['season'],r['week'],r[side+'_team'])]
        x.update({side+'_cov_'+k:v for k,v in z.items() if k not in {'season','target_week','team','release_state'}})
    hist.append(x)
sched=pd.read_csv('nfl_data/research/week6_failure_20261021/inputs/nflverse_games.csv')
sched=sched[sched.game_type.eq('REG')&sched.season.between(2021,2026)].copy()
sched.loc[(sched.season==2026)&(sched.week>=7),['home_score','away_score']]=np.nan
sched=sched.sort_values(['season','week','gameday','gametime','game_id'])
core={r['team']:r for r in read(snap/'core_inputs.csv')};cover={r['team']:r for r in read(snap/'coverage_inputs.csv')};teams=sorted(core);assert len(teams)==32
assert all(int(r['max_current_season_week_used'])<7 for r in core.values())
# Append unplayed synthetic pairings to read rating states for bye teams too.
pairs=[]
for h in teams:
 for away in teams:
    if h!=away:pairs.append(dict(game_id='power_'+h+'_'+away,season=2026,home_team=h,away_team=away,home_score=np.nan,away_score=np.nan))
rp=manifest['rating_params'];rmap=rat.rating_maps(pd.concat([sched,pd.DataFrame(pairs)],ignore_index=True),rp['elo_k'],rp['elo_hfa'],rp['offseason_regression'],rp['margin_k'],rp['margin_hfa'])
par=manifest['coverage_params'];fit=model.fit(rat.attach(hist,rmap),par['team_k'],par['feature_k'],rp['lambda'])
actual=read(snap/'game_feature_inputs.csv');pred,_=model.predict(actual,par['team_k'],par['feature_k'],fit)
frozen=read(snap/'paired_projections.csv');err=max(abs(float(p)-float(z['canonical_home_margin'])) for p,z in zip(pred,frozen));assert err<1e-8,err
synthetic=[]
for p in pairs:
    x={**p,'neutral_site':1,'home_rest':7,'away_rest':7}
    for side,t in [('home',p['home_team']),('away',p['away_team'])]:
        x.update({side+'_'+k:v for k,v in core[t].items()})
        x.update({side+'_cov_'+k:v for k,v in cover[t].items()})
    synthetic.append(x)
pr,_=model.predict(rat.attach(synthetic,rmap),par['team_k'],par['feature_k'],fit)
lookup={(p['home_team'],p['away_team']):float(v) for p,v in zip(pairs,pr)}
m=[[0 if h==away else (lookup[h,away]-lookup[away,h])/2 for away in teams] for h in teams]
out={'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'league':'nfl','modelId':'NFL Canonical v1 — neutral matchup summary','asOf':manifest['created_at_utc'],'sourceWeek':6,'teams':teams,'margins':m,'frozenReproductionMaxError':err,'sourceHashes':manifest['source_hashes'],'method':'Both orientations, equal rest, neutral venue, antisymmetrized; no market features','gamesBefore':{t:int(core[t]['games_before']) for t in teams}}
Path(a.output).write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print('NFL frozen reproduction max error:',err)
