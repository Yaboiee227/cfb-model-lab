#!/usr/bin/env python3
"""Nested frozen-parameter validation of robust NFL spread candidate families.

Tests whether individually robust coverage, turnover outcomes, punting and return
features remain incrementally useful when combined. All family shrinkage and the
ridge penalty are selected using 2022 only, then frozen for 2023-2025.
"""
from __future__ import annotations
import json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix  # canonical alias patch
import validate_nfl_coverage_v1 as cov
import validate_nfl_turnover_regression_v1 as tov
import validate_nfl_special_teams_v1 as st

OUT=Path('nfl_data/validation/advanced_spread_combined.json');YEARS=[2023,2024,2025];LAMBDAS=[0.1,1.,3.,10.,30.,100.];DRAWS=5000;SEED=20261017
SPECS=[('coverage',['coverage']),('coverage_turnover',['coverage','turnover']),('coverage_turnover_punting',['coverage','turnover','punting']),('coverage_turnover_punting_returns',['coverage','turnover','punting','returns'])]

def attach_all():
 base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov');ti,tl,_=tov.loadidx();si,sl,_=st.loadidx()
 if nl+cl+tl+sl:raise RuntimeError(f'leak source counts ngs={nl} cov={cl} to={tl} st={sl}')
 rows=cov.attach(base_rows,ci,ni);rows=tov.attach(rows,ti);rows=st.attach(rows,si)
 if len(rows)!=len(base_rows):raise RuntimeError('incomplete combined attachment')
 return base_rows,rows
def extra(r,families,ks):
 names=[];vals=[]
 if 'coverage' in families:
  n,v=cov.extras(r,'spread','coverage',ks['coverage']);names+=n;vals+=v
 if 'turnover' in families:
  n,v=tov.features(r,'spread','turnover_outcomes',ks['turnover']);names+=n;vals+=v
 if 'punting' in families:
  n,v=st.feats(r,'spread','punting',ks['punting']);names+=n;vals+=v
 if 'returns' in families:
  n,v=st.feats(r,'spread','returns',ks['returns']);names+=n;vals+=v
 return names,vals
def matrix(rows,team_k,families,ks):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,team_k);en,ev=extra(r,families,ks)
  if names is None:names=bn+en
  data.append([np.nan if x is None else float(x) for x in bv+ev])
 return names,np.asarray(data,float)
def fit(rows,team_k,families,ks,lam):
 names,X=matrix(rows,team_k,families,ks);prep=base.fit_preprocessor(X);Xz=base.transform(X,prep);model=base.ridge_fit(Xz,base.target_array(rows,'spread'),lam);return names,prep,model
def predict(rows,team_k,families,ks,fitobj):
 names,prep,model=fitobj;_,X=matrix(rows,team_k,families,ks);return base.predict(model,base.transform(X,prep)),{n:float(v) for n,v in zip(names,model[1])}
def select_lambda(rows,team_k,families,ks):
 fitrows,valrows=base.inner_split(rows);yv=base.target_array(valrows,'spread');best=None
 for lam in LAMBDAS:
  fo=fit(fitrows,team_k,families,ks,lam);p,_=predict(valrows,team_k,families,ks,fo);rec={'lambda':lam,'mae':base.mae(yv,p),'rmse':base.rmse(yv,p)}
  if best is None or (rec['mae'],rec['rmse'],rec['lambda'])<(best['mae'],best['rmse'],best['lambda']):best=rec
 return best
def abs_err(rows,p):return np.abs(base.target_array(rows,'spread')-np.asarray(p,float))
def bootstrap(diff):
 rng=np.random.default_rng(SEED);n=len(diff);v=np.empty(DRAWS)
 for i in range(DRAWS):v[i]=np.mean(diff[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(v,[.025,.975]);return {'mean_improvement':round(float(np.mean(diff)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_gt_0':round(float(np.mean(v>0)),4),'draws':DRAWS}
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);base_rows,rows=attach_all();b22=[r for r in base_rows if r['season']==2022];r22=[r for r in rows if r['season']==2022];bp,_=base.select_params(b22,'spread');team_k=bp['k']
 # Freeze each family shrinkage using only 2022.
 cp,_=cov.select(r22,'spread','coverage');tp,_=tov.select(r22,'spread','turnover_outcomes');pp,_=st.select(r22,'spread','punting');rp,_=st.select(r22,'spread','returns');ks={'coverage':cp['feature_k'],'turnover':tp['feature_k'],'punting':pp['feature_k'],'returns':rp['feature_k']}
 frozen={};
 for name,fams in SPECS:frozen[name]=select_lambda(r22,team_k,fams,ks)
 tests={};basepred={};market={}
 for y in YEARS:
  tr=[r for r in base_rows if r['season']<y];te=[r for r in base_rows if r['season']==y];p,_,_,_,_=base.fit_and_predict(tr,te,'spread',team_k,bp['lambda']);tests[y]=te;basepred[y]=np.asarray(p,float);market[y]=base.market_mae(te,'spread')
 lookup={r['game_id']:r for r in rows};variants={};prev_all=None
 for name,fams in SPECS:
  fold={};allrows=[];allp=[];allb=[];coef_by_year={}
  for y in YEARS:
   tr=[r for r in rows if r['season']<y];te=[lookup[r['game_id']] for r in tests[y]];fo=fit(tr,team_k,fams,ks,frozen[name]['lambda']);p,c=predict(te,team_k,fams,ks,fo);p=np.asarray(p,float);coef_by_year[y]=c;be=abs_err(te,basepred[y]);ce=abs_err(te,p);fold[str(y)]={'n':len(te),'baseline_mae':round(float(np.mean(be)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta_vs_baseline':round(float(np.mean(ce)-np.mean(be)),4),'market_reference_mae':round(market[y],4)};allrows+=te;allp+=list(p);allb+=list(basepred[y])
  be=abs_err(allrows,allb);ce=abs_err(allrows,allp);agg={'n':len(allrows),'baseline_mae':round(float(np.mean(be)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta_vs_baseline':round(float(np.mean(ce)-np.mean(be)),4),'market_reference_mae':round(base.market_mae(allrows,'spread'),4),'seasons_better_than_baseline':sum(fold[str(y)]['delta_vs_baseline']<0 for y in YEARS),'bootstrap_vs_baseline':bootstrap(be-ce)}
  if prev_all is not None:
   pe=abs_err(allrows,prev_all);agg['delta_vs_previous_nested_spec']=round(float(np.mean(ce)-np.mean(pe)),4);agg['bootstrap_vs_previous_nested_spec']=bootstrap(pe-ce)
  variants[name]={'families':fams,'frozen_lambda':frozen[name],'folds':fold,'aggregate':agg};prev_all=np.asarray(allp,float)
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'Family shrinkage and ridge lambda selected from 2022 only; frozen for 2023-2025. Coefficients refit using prior seasons only.','frozen_baseline':{'team_k':team_k,'lambda':bp['lambda'],'selection_mae':bp['mae']},'family_shrinkage':ks,'variants':variants,'release_state':'HOLD_COMBINED_VALIDATION','website_publish_allowed':False};OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({k:v['aggregate'] for k,v in variants.items()},indent=2))
if __name__=='__main__':main()
