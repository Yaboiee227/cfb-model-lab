"""Offline pinned-model decomposition and fixed-parameter diagnostic comparisons.
Run from the pinned NFL source checkout. No model promotion or live edits.
"""
import sys,json,csv,argparse,hashlib,subprocess
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path.cwd()/'scripts'))
import run_nfl_walk_forward as base
import build_nfl_week6_research_projections as wk
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as fm
ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
spec=json.load(open('nfl_data/validation/final_ftn_qb_process_blend.json'));cp=spec['coverage_params'];rp=fm.RATING
schedule=pd.read_csv('nfl_data/research/week6_failure_20261021/inputs/nflverse_games.csv');schedule.loc[(schedule.season==2026)&(schedule.week>=7),['home_score','away_score']]=np.nan
schedule=schedule[schedule.game_type.eq('REG') & schedule.season.between(2021,2026)].sort_values(['season','week','gameday','gametime','game_id'])
schedule['home_team']=schedule.home_team.map(rat.nt);schedule['away_team']=schedule.away_team.map(rat.nt)
rmap=rat.rating_maps(schedule,rp['elo_k'],rp['elo_hfa'],rp['offseason_regression'],rp['margin_k'],rp['margin_hfa'])
historical=rat.attach(wk.attach_historical_coverage(base.load_rows()),rmap)
snap=Path('nfl_data/prospective/week7/20261021T114427Z');read=lambda p:list(csv.DictReader(p.open()))
live=read(snap/'game_feature_inputs.csv');frozen={r['game_id']:float(r['canonical_home_margin']) for r in read(snap/'paired_projections.csv')};finals={g['gameId']:g['homeScore']-g['awayScore'] for g in json.loads(a.results.read_text())['games']}
original=base.spread_features

def corrected_features(r,k):
 names,values=original(r,k)
 for i,off,de in [(4,'off_pass_epa','def_pass_epa_allowed'),(5,'off_rush_epa','def_rush_epa_allowed')]:
  ho=base.blend(r,'home',off,k);ao=base.blend(r,'away',off,k);hd=base.raw(r,'home',de);ad=base.raw(r,'away',de)
  values[i]=None if any(v is None for v in [ho,ao,hd,ad]) else (ho+ad)-(ao+hd)
 return names,values

def family(name):
 if name.startswith('cov_'):return 'coverage'
 if name=='rating_win_elo_diff':return 'elo'
 if name=='rating_margin_rating_diff':return 'margin_rating'
 if name in ['neutral_site','rest_diff']:return 'venue_rest'
 return 'efficiency'

def matrix(rows,variant):
 base.spread_features=corrected_features if variant=='allowance_sign_candidate' else original
 try:n,x=fm.matrix(rows,cp['team_k'],cp['feature_k'])
 finally:base.spread_features=original
 drop={'without_coverage':'coverage','without_elo':'elo','without_margin_rating':'margin_rating'}.get(variant)
 keep=[i for i,k in enumerate(n) if family(k)!=drop]
 return [n[i] for i in keep],x[:,keep]

def fit_predict(train,test,variant,explain=False):
 names,x=matrix(train,variant);_,xt=matrix(test,variant);prep=base.fit_preprocessor(x);model=base.ridge_fit(base.transform(x,prep),base.target_array(train,'spread'),rp['lambda']);z=base.transform(xt,prep);p=base.predict(model,z)
 return p,(names,z,model,xt) if explain else None

def metrics(actual,p):
 e=np.asarray(p)-np.asarray(actual);return dict(games=len(e),mae=float(np.mean(abs(e))),rmse=float(np.sqrt(np.mean(e**2))),biasHomeMargin=float(np.mean(e)))
variants=['baseline','without_coverage','without_elo','without_margin_rating','allowance_sign_candidate'];folds={};agg={v:[] for v in variants};actual=[]
for year in [2023,2024,2025]:
 train=[r for r in historical if r['season']<year];test=[r for r in historical if r['season']==year];y=base.target_array(test,'spread');folds[str(year)]={};actual.extend(y)
 for v in variants:
  p,_=fit_predict(train,test,v);folds[str(year)][v]=metrics(y,p);agg[v].extend(p)
 print('Completed historical fold',year,flush=True)
p,info=fit_predict(historical,live,'baseline',True);maxdiff=max(abs(float(q)-frozen[r['game_id']]) for r,q in zip(live,p));assert len(live)==14 and maxdiff<1e-8,maxdiff
names,z,model,xt=info;decomp=[]
for i,r in enumerate(live):
 groups={'intercept':float(model[0])}
 for j,n in enumerate(names):groups[family(n)]=groups.get(family(n),0)+float(z[i,j]*model[1][j])
 assert abs(sum(groups.values())-p[i])<1e-8
 decomp.append(dict(gameId=r['game_id'],predictedHomeMargin=float(p[i]),actualHomeMargin=finals[r['game_id']],errorHomeMargin=float(p[i])-finals[r['game_id']],contributions=groups,missingRawFeatures=[n for n,v in zip(names,xt[i]) if not np.isfinite(v)]))
out=dict(canonicalInfluence=False,status='DIAGNOSTIC_ONLY_NO_PROMOTION',historicalFolds=folds,historicalAggregate={v:metrics(actual,p) for v,p in agg.items()},week7ReproductionMaxAbsDiff=maxdiff,week7Contributions=decomp,signCandidate='Only pass/rush matchup features change from offense minus opponent defensive EPA allowed to offense plus allowance. Higher allowance denotes weaker defense. Coefficients are refit with unchanged hyperparameters.',limitations=['Historical 2023-2025 outcomes have been examined previously; not new blind holdouts.','Feature ablations refit remaining coefficients; contribution groups alone do not establish causality.','No personnel-point adjustment evaluated; as-of starter reports require separate evidence.','No production coefficients, predictions or totals are changed.'])
out['sourceCommit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
out['inputHashes']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [snap/'game_feature_inputs.csv',snap/'paired_projections.csv',a.results]}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['historicalAggregate'],indent=2))
