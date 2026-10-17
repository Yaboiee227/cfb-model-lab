#!/usr/bin/env python3
"""Stability audit for the frozen coverage + recursive NFL rating spread model.

Uses the already-selected 2022-only frozen rating specification and checks
2023-2025 early/mid/late season performance plus rating coefficient sign
stability. Development only; no website publication.
"""
from __future__ import annotations
import json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix
import validate_nfl_coverage_v1 as cov
import validate_nfl_rating_system_robustness as rat

OUT=Path('nfl_data/validation/rating_system_stability.json')
YEARS=[2023,2024,2025]
PARAMS={'elo_hfa':35.0,'elo_k':40.0,'lambda':100.0,'margin_hfa':3.0,'margin_k':0.05,'offseason_regression':0.25}
BUCKETS={'weeks_1_5':lambda w:1<=w<=5,'weeks_6_12':lambda w:6<=w<=12,'weeks_13_18':lambda w:13<=w<=18}

def met(rows,p):
 y=base.target_array(rows,'spread');p=np.asarray(p,float)
 return {'n':len(rows),'mae':round(base.mae(y,p),4),'rmse':round(base.rmse(y,p),4),'bias':round(base.bias(y,p),4)}
def fit_rating(train,test,cp,rm):
 rated=rat.attach(train+test,rm);lookup={r['game_id']:r for r in rated};tr=[lookup[r['game_id']] for r in train];te=[lookup[r['game_id']] for r in test]
 fo=rat.fit(tr,'both',cp['team_k'],PARAMS['lambda'],cp['feature_k']);p=rat.pred(te,'both',cp['team_k'],cp['feature_k'],fo)
 names,prep,model=fo;coefs={n:float(v) for n,v in zip(names,model[1])}
 return p,coefs

def main():
 OUT.parent.mkdir(parents=True,exist_ok=True)
 games=rat.fetch_games();base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov')
 if nl+cl:raise RuntimeError(f'coverage source leak ngs={nl} cov={cl}')
 rows=cov.attach(base_rows,ci,ni);cp,_=cov.select([r for r in rows if r['season']==2022],'spread','coverage')
 rm=rat.rating_maps(games,PARAMS['elo_k'],PARAMS['elo_hfa'],PARAMS['offseason_regression'],PARAMS['margin_k'],PARAMS['margin_hfa'])
 folds={};rating_coef={};all_bucket={k:{'n':0,'ref_abs':0.0,'cand_abs':0.0} for k in BUCKETS}
 for y in YEARS:
  tr=[r for r in rows if r['season']<y];te=[r for r in rows if r['season']==y]
  ref,_=cov.fitp(tr,te,'spread','coverage',{'team_k':cp['team_k'],'feature_k':cp['feature_k'],'lambda':cp['lambda']})
  p,c=fit_rating(tr,te,cp,rm);rating_coef[str(y)]={k:round(v,7) for k,v in c.items() if k.startswith('rating_')}
  fm={'reference':met(te,ref),'candidate':met(te,p),'delta':round(met(te,p)['mae']-met(te,ref)['mae'],4),'buckets':{}}
  yy=base.target_array(te,'spread');ref=np.asarray(ref,float);p=np.asarray(p,float)
  for name,fn in BUCKETS.items():
   idx=[i for i,r in enumerate(te) if fn(int(r['week']))];ya=yy[idx];ra=ref[idx];pa=p[idx]
   rma=float(np.mean(np.abs(ya-ra)));cma=float(np.mean(np.abs(ya-pa)));fm['buckets'][name]={'n':len(idx),'reference_mae':round(rma,4),'candidate_mae':round(cma,4),'delta':round(cma-rma,4)}
   all_bucket[name]['n']+=len(idx);all_bucket[name]['ref_abs']+=rma*len(idx);all_bucket[name]['cand_abs']+=cma*len(idx)
  folds[str(y)]=fm
 bucket_summary={}
 for name,z in all_bucket.items():
  r=z['ref_abs']/z['n'];c=z['cand_abs']/z['n'];bucket_summary[name]={'n':z['n'],'reference_mae':round(r,4),'candidate_mae':round(c,4),'delta':round(c-r,4)}
 signs={}
 for feat in ['rating_win_elo_diff','rating_margin_rating_diff']:
  vals=[rating_coef[str(y)].get(feat) for y in YEARS];nz=[v for v in vals if v is not None and abs(v)>1e-12];ok=len(nz)==3 and (all(v>0 for v in nz) or all(v<0 for v in nz));signs[feat]={'coefficients':vals,'same_nonzero_sign_all_folds':ok}
 passes=sum(v['delta']<0 for v in bucket_summary.values())>=2 and all(v['same_nonzero_sign_all_folds'] for v in signs.values()) and sum(folds[str(y)]['delta']<0 for y in YEARS)==3
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_coverage':cp,'frozen_rating_params':PARAMS,'folds':folds,'week_bucket_summary':bucket_summary,'rating_coefficient_sign_stability':signs,'stability_verdict':'EARNED_WEEK6_RESEARCH_INCLUSION' if passes else 'HOLD_NO_INCLUSION','production_verdict':'HOLD_PROSPECTIVE_VALIDATION_REQUIRED','website_publish_allowed':False}
 OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
