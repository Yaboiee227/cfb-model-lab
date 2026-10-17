#!/usr/bin/env python3
"""Frozen nested robustness audit for NFL injury/personnel spread features.

Coverage is the current robust advanced spread candidate. This test freezes the
coverage recipe from 2022, adds injury families without retuning team/coverage
shrinkage in later years, and reports exact-timestamp (2023-24) separately from
lower-quality 2025 final-week injury data.
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
import validate_nfl_injury_personnel_v1 as inj

OUT=Path('nfl_data/validation/injury_personnel_robustness.json');YEARS=[2023,2024,2025];LAMBDAS=[0.1,1.,3.,10.,30.,100.];DRAWS=5000;SEED=20261017
FAMILIES=['weighted_groups','all_injury','offense','defense','overall']

def matrix(rows,team_k,coverage_k,fam):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,team_k);cn,cv=cov.extras(r,'spread','coverage',coverage_k);inn,iv=inj.injury_features(r,'spread',fam);n=bn+cn+inn;v=bv+cv+iv
  if names is None:names=n
  data.append([np.nan if x is None else float(x) for x in v])
 return names,np.asarray(data,float)
def fit(rows,team_k,coverage_k,fam,lam):
 names,X=matrix(rows,team_k,coverage_k,fam);prep=base.fit_preprocessor(X);model=base.ridge_fit(base.transform(X,prep),base.target_array(rows,'spread'),lam);return names,prep,model
def pred(rows,team_k,coverage_k,fam,fitobj):
 names,prep,model=fitobj;_,X=matrix(rows,team_k,coverage_k,fam);p=base.predict(model,base.transform(X,prep));return np.asarray(p,float),{n:float(v) for n,v in zip(names,model[1])}
def select_lambda(rows,team_k,coverage_k,fam):
 fitrows,valrows=base.inner_split(rows);y=base.target_array(valrows,'spread');best=None
 for lam in LAMBDAS:
  fo=fit(fitrows,team_k,coverage_k,fam,lam);p,_=pred(valrows,team_k,coverage_k,fam,fo);r={'lambda':lam,'mae':base.mae(y,p),'rmse':base.rmse(y,p)}
  if best is None or (r['mae'],r['rmse'],r['lambda'])<(best['mae'],best['rmse'],best['lambda']):best=r
 return best
def abs_err(rows,p):return np.abs(base.target_array(rows,'spread')-np.asarray(p,float))
def bootstrap(d):
 rng=np.random.default_rng(SEED);n=len(d);v=np.empty(DRAWS)
 for i in range(DRAWS):v[i]=np.mean(d[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(v,[.025,.975]);return {'mean_improvement':round(float(np.mean(d)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_gt_0':round(float(np.mean(v>0)),4),'draws':DRAWS}
def subset_report(years,tests,ref,cand):
 rows=[];rp=[];cp=[]
 for y in years:rows+=tests[y];rp+=list(ref[y]);cp+=list(cand[y])
 re=abs_err(rows,rp);ce=abs_err(rows,cp);return {'n':len(rows),'reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4),'bootstrap':bootstrap(re-ce)}
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov');ii,quality,nrows=inj.loadidx()
 if nl+cl:raise RuntimeError(f'coverage source leak ngs={nl} cov={cl}')
 rows=inj.attach(cov.attach(base_rows,ci,ni),ii);r22=[r for r in rows if r['season']==2022];c22=[r for r in cov.attach(base_rows,ci,ni) if r['season']==2022]
 cp,_=cov.select(c22,'spread','coverage');team_k=cp['team_k'];coverage_k=cp['feature_k'];coverage_lambda=cp['lambda']
 frozen={fam:select_lambda(r22,team_k,coverage_k,fam) for fam in FAMILIES}
 tests={};coverage_pred={};lookup={r['game_id']:r for r in rows};covrows=cov.attach(base_rows,ci,ni);covlookup={r['game_id']:r for r in covrows}
 for y in YEARS:
  tr=[r for r in covrows if r['season']<y];te=[covlookup[r['game_id']] for r in base_rows if r['season']==y];p,_=cov.fitp(tr,te,'spread','coverage',{'team_k':team_k,'feature_k':coverage_k,'lambda':coverage_lambda});tests[y]=[lookup[r['game_id']] for r in te];coverage_pred[y]=np.asarray(p,float)
 variants={}
 for fam in FAMILIES:
  pp={};folds={};coef_by_year={}
  for y in YEARS:
   tr=[r for r in rows if r['season']<y];te=tests[y];fo=fit(tr,team_k,coverage_k,fam,frozen[fam]['lambda']);p,c=pred(te,team_k,coverage_k,fam,fo);pp[y]=p;coef_by_year[y]=c;re=abs_err(te,coverage_pred[y]);ce=abs_err(te,p);folds[str(y)]={'n':len(te),'coverage_reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta_vs_coverage':round(float(np.mean(ce)-np.mean(re)),4),'market_reference_mae':round(base.market_mae(te,'spread'),4),'report_quality':'EXACT_PREKICKOFF_TIMESTAMP' if y in [2023,2024] else 'FINAL_WEEK_REPORT_NO_REVISION_TIMESTAMP'}
  allrep=subset_report(YEARS,tests,coverage_pred,pp);exact=subset_report([2023,2024],tests,coverage_pred,pp);low=subset_report([2025],tests,coverage_pred,pp)
  injcoef={k:[coef_by_year[y].get(k) for y in YEARS] for k in sorted(set().union(*[set(coef_by_year[y]) for y in YEARS])) if k.startswith('inj_')};eligible=0;stable=0
  for vs in injcoef.values():
   x=[v for v in vs if v is not None and abs(v)>1e-12]
   if len(x)>=2:eligible+=1;stable+=int(all(v>0 for v in x) or all(v<0 for v in x))
  variants[fam]={'frozen_lambda':frozen[fam],'folds':folds,'aggregate_vs_frozen_coverage':allrep,'exact_timestamp_2023_2024':exact,'lower_quality_2025':low,'coefficient_sign_stability':{'eligible_features':eligible,'same_sign_features':stable,'same_sign_share':None if not eligible else round(stable/eligible,4),'coefficients':{k:[None if v is None else round(float(v),6) for v in vs] for k,vs in injcoef.items()}}}
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'Coverage team_k, coverage shrinkage, coverage lambda and injury combined lambda selected from 2022 only; frozen for 2023-2025.','source_rows':nrows,'report_quality_counts':quality,'frozen_coverage':{'team_k':team_k,'feature_k':coverage_k,'lambda':coverage_lambda,'selection_mae':cp['mae']},'variants':variants,'release_state':'HOLD_ROBUSTNESS_ONLY','website_publish_allowed':False};OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({k:{'all':v['aggregate_vs_frozen_coverage'],'exact':v['exact_timestamp_2023_2024'],'2025':v['lower_quality_2025']} for k,v in variants.items()},indent=2))
if __name__=='__main__':main()
