#!/usr/bin/env python3
"""Frozen-parameter robustness validation for NFL FTN charting families.

Spread candidates must improve the frozen baseline+coverage reference. Totals
must improve the frozen core totals baseline because coverage is not a validated
totals component. Hyperparameters are selected from 2022 only and frozen for
2023-2025; coefficients refit using prior seasons only.
"""
from __future__ import annotations
import csv,json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix  # canonical aliases
import validate_nfl_coverage_v1 as cov

IN=Path('nfl_data/historical/team_week_ftn_charting_2022_2025.csv');OUT=Path('nfl_data/validation/ftn_charting_robustness.json')
YEARS=[2023,2024,2025];KGRID=[1.,2.,4.,8.,16.];LAMBDAS=[0.1,1.,3.,10.,30.,100.];DRAWS=5000;SEED=20261017
OFF_SCHEME=['no_huddle_rate','motion_rate','play_action_rate','screen_rate','rpo_rate']
DEF_SCHEME=['def_no_huddle_faced_rate','def_motion_faced_rate','def_play_action_faced_rate','def_screen_faced_rate','def_rpo_faced_rate']
OFF_PROCESS=['qb_out_of_pocket_rate','interception_worthy_rate','throwaway_rate','catchable_rate','contested_rate','created_reception_rate','drop_rate','qb_fault_sack_rate']
DEF_PROCESS=['def_qb_out_of_pocket_faced_rate','def_interception_worthy_forced_rate','def_throwaway_forced_rate','def_catchable_allowed_rate','def_contested_rate','def_created_reception_allowed_rate','def_drop_rate','def_qb_fault_sack_rate']
OFF_BOX=['avg_offense_backfield','avg_defense_box_faced','avg_blitzers_faced','avg_pass_rushers_faced']
DEF_BOX=['def_avg_offense_backfield_faced','def_avg_box','def_avg_blitzers','def_avg_pass_rushers']
FAMILIES={'scheme':OFF_SCHEME+DEF_SCHEME,'qb_process':OFF_PROCESS+DEF_PROCESS,'box_pressure':OFF_BOX+DEF_BOX}
FAMILIES['full_charting']=FAMILIES['scheme']+FAMILIES['qb_process']+FAMILIES['box_pressure']

def tf(v):return base.to_float(v)
def loadidx():
 with IN.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
 idx={};leak=0
 for r in rows:
  k=(int(float(r['season'])),int(float(r['target_week'])),r['team']);idx[k]=r
  mw=tf(r.get('max_current_week_used'));leak+=int(mw is not None and mw>=k[1])
 return idx,leak,len(rows)
def attach(rows,idx):
 out=[];miss=[]
 for r in rows:
  h=idx.get((r['season'],r['week'],r['home_team']));a=idx.get((r['season'],r['week'],r['away_team']))
  if h is None or a is None:miss.append(r['game_id']);continue
  x=dict(r)
  for side,row in [('home',h),('away',a)]:
   for k,v in row.items():
    if k not in {'season','target_week','team','release_state'}:x[f'{side}_ftn_{k}']=v
  out.append(x)
 if miss:raise RuntimeError(f'missing FTN snapshots {len(miss)} first={miss[:5]}')
 return out
def blend(r,side,m,k):
 games=tf(r.get(f'{side}_games_before')) or 0.;cur=tf(r.get(f'{side}_ftn_cur_{m}'));prior=tf(r.get(f'{side}_ftn_prior_{m}'))
 if cur is not None and prior is not None:return (games*cur+k*prior)/(games+k)
 return cur if cur is not None else prior
def extras(r,kind,fam,k):
 ms=FAMILIES[fam];h=[blend(r,'home',m,k) for m in ms];a=[blend(r,'away',m,k) for m in ms];op=base.diff if kind=='spread' else base.summ;suf='diff' if kind=='spread' else 'sum'
 return [f'ftn_{m}_{suf}' for m in ms],[op(x,y) for x,y in zip(h,a)]
def matrix(rows,kind,fam,team_k,feature_k,with_cov=False,cov_k=1.0):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,team_k) if kind=='spread' else base.total_features(r,team_k);en,ev=extras(r,kind,fam,feature_k)
  if with_cov:
   cn,cv=cov.extras(r,kind,'coverage',cov_k);n=bn+cn+en;v=bv+cv+ev
  else:n=bn+en;v=bv+ev
  if names is None:names=n
  data.append([np.nan if x is None else float(x) for x in v])
 return names,np.asarray(data,float)
def fit(rows,kind,fam,tk,fk,lam,with_cov=False,cov_k=1.0):
 names,X=matrix(rows,kind,fam,tk,fk,with_cov,cov_k);prep=base.fit_preprocessor(X);model=base.ridge_fit(base.transform(X,prep),base.target_array(rows,kind),lam);return names,prep,model
def predict(rows,kind,fam,tk,fk,fitobj,with_cov=False,cov_k=1.0):
 names,prep,model=fitobj;_,X=matrix(rows,kind,fam,tk,fk,with_cov,cov_k);p=base.predict(model,base.transform(X,prep));return np.asarray(p,float),{n:float(v) for n,v in zip(names,model[1])}
def select_params(rows,kind,fam,with_cov=False,cov_k=1.0):
 fr,vr=base.inner_split(rows);y=base.target_array(vr,kind);cs=[]
 for tk in base.K_GRID:
  for fk in KGRID:
   for lam in LAMBDAS:
    fo=fit(fr,kind,fam,tk,fk,lam,with_cov,cov_k);p,_=predict(vr,kind,fam,tk,fk,fo,with_cov,cov_k);cs.append({'team_k':tk,'feature_k':fk,'lambda':lam,'mae':base.mae(y,p),'rmse':base.rmse(y,p)})
 cs.sort(key=lambda x:(x['mae'],x['rmse'],x['lambda']));return cs[0]
def ae(rows,p,kind):return np.abs(base.target_array(rows,kind)-np.asarray(p,float))
def boot(d):
 rng=np.random.default_rng(SEED);n=len(d);v=np.empty(DRAWS)
 for i in range(DRAWS):v[i]=np.mean(d[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(v,[.025,.975]);return {'mean_improvement':round(float(np.mean(d)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_gt_0':round(float(np.mean(v>0)),4),'draws':DRAWS}
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);fi,leak,nrows=loadidx();base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov')
 if leak+nl+cl:raise RuntimeError(f'source leakage ftn={leak} ngs={nl} cov={cl}')
 covrows=cov.attach(base_rows,ci,ni);rows=attach(covrows,fi);r22=[r for r in rows if r['season']==2022];c22=[r for r in covrows if r['season']==2022];b22=[r for r in base_rows if r['season']==2022]
 cp,_=cov.select(c22,'spread','coverage');total_bp,_=base.select_params(b22,'total')
 frozen={}
 for fam in FAMILIES:
  frozen[(fam,'spread')]=select_params(r22,'spread',fam,True,cp['feature_k']);frozen[(fam,'total')]=select_params(r22,'total',fam,False,1.0)
 covlookup={r['game_id']:r for r in covrows};lookup={r['game_id']:r for r in rows};refs={'spread':{},'total':{}};tests={}
 for y in YEARS:
  tebase=[r for r in base_rows if r['season']==y];tests[y]=[lookup[r['game_id']] for r in tebase]
  ctr=[r for r in covrows if r['season']<y];cte=[covlookup[r['game_id']] for r in tebase];sp,_=cov.fitp(ctr,cte,'spread','coverage',{'team_k':cp['team_k'],'feature_k':cp['feature_k'],'lambda':cp['lambda']});refs['spread'][y]=np.asarray(sp,float)
  btr=[r for r in base_rows if r['season']<y];tp,_,_,_,_=base.fit_and_predict(btr,tebase,'total',total_bp['k'],total_bp['lambda']);refs['total'][y]=np.asarray(tp,float)
 variants={}
 for fam in FAMILIES:
  variants[fam]={}
  for kind in ['spread','total']:
   par=frozen[(fam,kind)];pp={};folds={};coef={}
   for y in YEARS:
    tr=[r for r in rows if r['season']<y];te=tests[y];fo=fit(tr,kind,fam,par['team_k'],par['feature_k'],par['lambda'],kind=='spread',cp['feature_k']);p,c=predict(te,kind,fam,par['team_k'],par['feature_k'],fo,kind=='spread',cp['feature_k']);pp[y]=p;coef[y]=c;re=ae(te,refs[kind][y],kind);ce=ae(te,p,kind);folds[str(y)]={'n':len(te),'reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4)}
   allrows=[];rr=[];qq=[]
   for y in YEARS:allrows+=tests[y];rr+=list(refs[kind][y]);qq+=list(pp[y])
   re=ae(allrows,rr,kind);ce=ae(allrows,qq,kind);variants[fam][kind]={'frozen_params':par,'folds':folds,'aggregate':{'n':len(allrows),'reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4),'seasons_improved':sum(folds[str(y)]['delta']<0 for y in YEARS),'bootstrap':boot(re-ce)},'reference':'frozen_coverage' if kind=='spread' else 'frozen_core_total'}
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'FTN family hyperparameters selected from 2022 only and frozen for 2023-2025; spread compared with frozen coverage, totals with frozen core baseline.','source_rows':nrows,'source_leakage_rows':leak,'frozen_coverage':cp,'frozen_total_baseline':total_bp,'variants':variants,'release_state':'HOLD_ROBUSTNESS_ONLY','website_publish_allowed':False};OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({f:{k:v[k]['aggregate'] for k in ['spread','total']} for f,v in variants.items()},indent=2))
if __name__=='__main__':main()
