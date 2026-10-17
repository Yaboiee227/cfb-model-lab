#!/usr/bin/env python3
"""Frozen-parameter robustness audit for NFL special-teams spread candidates."""
from __future__ import annotations
import json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_special_teams_v1 as st
OUT=Path('nfl_data/validation/special_teams_robustness.json');YEARS=[2023,2024,2025];DRAWS=5000;SEED=20261017
BUCKETS={'weeks_1_5':lambda w:1<=w<=5,'weeks_6_12':lambda w:6<=w<=12,'weeks_13_18':lambda w:13<=w<=18}
def err(rows,p):return np.abs(np.asarray([float(r['home_margin']) for r in rows])-np.asarray(p,float))
def boot(d):
 rng=np.random.default_rng(SEED);n=len(d);v=np.empty(DRAWS)
 for i in range(DRAWS):v[i]=np.mean(d[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(v,[.025,.975]);return {'mean_absolute_error_improvement':round(float(np.mean(d)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_improvement_gt_0':round(float(np.mean(v>0)),4),'draws':DRAWS,'seed':SEED}
def met(rows,p):
 y=np.asarray([float(r['home_margin']) for r in rows]);p=np.asarray(p,float);return {'n':len(rows),'mae':round(base.mae(y,p),4),'rmse':round(base.rmse(y,p),4),'bias':round(base.bias(y,p),4)}
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);idx,leak,nrows=st.loadidx()
 if leak:raise RuntimeError(f'leak={leak}')
 rows=st.attach(base.load_rows(),idx);base_rows=base.load_rows();tr22=[r for r in rows if r['season']==2022];b22=[r for r in base_rows if r['season']==2022];bp,_=base.select_params(b22,'spread');frozen={}
 for fam in st.FAMILIES:p,_=st.select(tr22,'spread',fam);frozen[fam]=p
 tests={};bpred={};bmet={}
 for y in YEARS:
  tr=[r for r in base_rows if r['season']<y];te=[r for r in base_rows if r['season']==y];p,_,_,_,_=base.fit_and_predict(tr,te,'spread',bp['k'],bp['lambda']);tests[y]=te;bpred[y]=np.asarray(p,float);bmet[y]=met(te,p)
 lookup={r['game_id']:r for r in rows};variants={}
 for fam,par in frozen.items():
  pp={};folds={};coef={}
  for y in YEARS:
   tr=[r for r in rows if r['season']<y];te=[lookup[r['game_id']] for r in tests[y]];p,c=st.fitp(tr,te,'spread',fam,par);p=np.asarray(p,float);pp[y]=p;cm=met(te,p);folds[str(y)]={**cm,'baseline_mae':bmet[y]['mae'],'mae_delta_vs_frozen_baseline':round(cm['mae']-bmet[y]['mae'],4),'market_reference_mae':round(base.market_mae(te,'spread'),4),'week_buckets':{}}
   for bn,fn in BUCKETS.items():
    ix=[i for i,r in enumerate(te) if fn(int(r['week']))];be=err([te[i] for i in ix],[bpred[y][i] for i in ix]);ce=err([te[i] for i in ix],[p[i] for i in ix]);folds[str(y)]['week_buckets'][bn]={'n':len(ix),'delta':round(float(np.mean(ce)-np.mean(be)),4)}
   for k,v in c.items():
    if k.startswith('st_'):coef.setdefault(k,[]).append(float(v))
  allrows=[];allb=[];allp=[]
  for y in YEARS:allrows.extend(tests[y]);allb.extend(bpred[y]);allp.extend(pp[y])
  be=err(allrows,allb);ce=err(allrows,allp);buckets={}
  for bn in BUCKETS:
   vs=[folds[str(y)]['week_buckets'][bn] for y in YEARS];nn=sum(v['n'] for v in vs);buckets[bn]={'n':nn,'delta':round(sum(v['delta']*v['n'] for v in vs)/nn,4)}
  stable=sum(1 for vs in coef.values() if len(vs)>=2 and (all(x>0 for x in vs) or all(x<0 for x in vs)))
  variants[fam]={'frozen_params':par,'folds':folds,'aggregate':{'n':len(allrows),'baseline_mae':round(float(np.mean(be)),4),'candidate_mae':round(float(np.mean(ce)),4),'mae_delta_vs_frozen_baseline':round(float(np.mean(ce)-np.mean(be)),4),'market_reference_mae':round(base.market_mae(allrows,'spread'),4),'seasons_with_lower_mae':sum(folds[str(y)]['mae_delta_vs_frozen_baseline']<0 for y in YEARS),'week_bucket_weighted_deltas':buckets,'week_buckets_improved':sum(v['delta']<0 for v in buckets.values()),'paired_bootstrap':boot(be-ce)},'advanced_coefficient_sign_stability':{'eligible_features':len(coef),'same_sign_features':stable,'same_sign_share':None if not coef else round(stable/len(coef),4),'coefficients':{k:[round(x,6) for x in v] for k,v in coef.items()}}}
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'Hyperparameters selected once from 2022 and frozen for 2023-2025.','source_rows':nrows,'source_leakage_rows':leak,'frozen_baseline':{'team_k':bp['k'],'lambda':bp['lambda'],'selection_mae':bp['mae']},'variants':variants,'release_state':'HOLD_ROBUSTNESS_ONLY','website_publish_allowed':False};OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({k:v['aggregate'] for k,v in variants.items()},indent=2))
if __name__=='__main__':main()
