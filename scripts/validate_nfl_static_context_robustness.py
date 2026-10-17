#!/usr/bin/env python3
"""Frozen-parameter robustness validation for NFL static travel/venue context.

Observed historical temperature/wind are intentionally excluded. Spread models
must improve frozen baseline+coverage; totals must improve frozen core totals.
"""
from __future__ import annotations
import csv,json,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix
import validate_nfl_coverage_v1 as cov

IN=Path('nfl_data/historical/game_static_context_2022_2025.csv');OUT=Path('nfl_data/validation/static_context_robustness.json')
YEARS=[2023,2024,2025];LAMBDAS=[0.1,1.,3.,10.,30.,100.];DRAWS=5000;SEED=20261017
FAMILIES={'travel_schedule':['away_travel_air_miles','away_time_zone_shift_hours','away_signed_time_zone_shift_hours','div_game','is_thursday','is_monday','is_sunday_night','kickoff_hour_et'],'venue':['surface_grass','surface_artificial','roof_indoor','roof_outdoors','roof_open'],'all_static':['away_travel_air_miles','away_time_zone_shift_hours','away_signed_time_zone_shift_hours','div_game','is_thursday','is_monday','is_sunday_night','kickoff_hour_et','surface_grass','surface_artificial','roof_indoor','roof_outdoors','roof_open']}

def tf(v):return base.to_float(v)
def loadidx():
 with IN.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
 idx={}
 for r in rows:
  x=dict(r);surface=str(r.get('surface_group','')).lower();roof=str(r.get('roof','')).lower();x['surface_grass']=1.0 if surface=='grass' else 0.0 if surface else None;x['surface_artificial']=1.0 if surface=='artificial' else 0.0 if surface else None;x['roof_indoor']=1.0 if roof in {'dome','closed'} else 0.0 if roof else None;x['roof_outdoors']=1.0 if roof=='outdoors' else 0.0 if roof else None;x['roof_open']=1.0 if roof=='open' else 0.0 if roof else None;idx[str(r['game_id'])]=x
 return idx,len(rows)
def attach(rows,idx):
 out=[];miss=[]
 for r in rows:
  s=idx.get(r['game_id'])
  if s is None:miss.append(r['game_id']);continue
  x=dict(r)
  for k,v in s.items():
   if k not in {'game_id','season','week','gameday','away_team','home_team','metadata_state'}:x[f'ctx_{k}']=v
  out.append(x)
 if miss:raise RuntimeError(f'missing static context {len(miss)} first={miss[:5]}')
 return out
def extra(r,kind,fam):
 ms=FAMILIES[fam];vals=[]
 for m in ms:
  v=tf(r.get(f'ctx_{m}'))
  if kind=='total' and m=='away_signed_time_zone_shift_hours' and v is not None:v=abs(v)
  vals.append(v)
 return [f'ctx_{m}' for m in ms],vals
def matrix(rows,kind,fam,tk,with_cov=False,covk=1.0):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,tk) if kind=='spread' else base.total_features(r,tk);en,ev=extra(r,kind,fam)
  if with_cov:cn,cv=cov.extras(r,kind,'coverage',covk);n=bn+cn+en;v=bv+cv+ev
  else:n=bn+en;v=bv+ev
  if names is None:names=n
  data.append([np.nan if x is None else float(x) for x in v])
 return names,np.asarray(data,float)
def fit(rows,kind,fam,tk,lam,with_cov=False,covk=1.0):
 names,X=matrix(rows,kind,fam,tk,with_cov,covk);prep=base.fit_preprocessor(X);model=base.ridge_fit(base.transform(X,prep),base.target_array(rows,kind),lam);return names,prep,model
def pred(rows,kind,fam,tk,fitobj,with_cov=False,covk=1.0):
 names,prep,model=fitobj;_,X=matrix(rows,kind,fam,tk,with_cov,covk);return np.asarray(base.predict(model,base.transform(X,prep)),float)
def select(rows,kind,fam,with_cov=False,covk=1.0):
 fr,vr=base.inner_split(rows);y=base.target_array(vr,kind);cs=[]
 for tk in base.K_GRID:
  for lam in LAMBDAS:
   fo=fit(fr,kind,fam,tk,lam,with_cov,covk);p=pred(vr,kind,fam,tk,fo,with_cov,covk);cs.append({'team_k':tk,'lambda':lam,'mae':base.mae(y,p),'rmse':base.rmse(y,p)})
 cs.sort(key=lambda x:(x['mae'],x['rmse'],x['lambda']));return cs[0]
def ae(rows,p,kind):return np.abs(base.target_array(rows,kind)-np.asarray(p,float))
def boot(d):
 rng=np.random.default_rng(SEED);n=len(d);v=np.empty(DRAWS)
 for i in range(DRAWS):v[i]=np.mean(d[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(v,[.025,.975]);return {'mean_improvement':round(float(np.mean(d)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_gt_0':round(float(np.mean(v>0)),4),'draws':DRAWS}
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);idx,nrows=loadidx();base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov')
 if nl+cl:raise RuntimeError(f'coverage source leak ngs={nl} cov={cl}')
 covrows=cov.attach(base_rows,ci,ni);rows=attach(covrows,idx);r22=[r for r in rows if r['season']==2022];c22=[r for r in covrows if r['season']==2022];b22=[r for r in base_rows if r['season']==2022];cp,_=cov.select(c22,'spread','coverage');tbp,_=base.select_params(b22,'total');frozen={(f,k):select(r22,k,f,k=='spread',cp['feature_k']) for f in FAMILIES for k in ['spread','total']};lookup={r['game_id']:r for r in rows};covlookup={r['game_id']:r for r in covrows};tests={};refs={'spread':{},'total':{}}
 for y in YEARS:
  tebase=[r for r in base_rows if r['season']==y];tests[y]=[lookup[r['game_id']] for r in tebase];ctr=[r for r in covrows if r['season']<y];cte=[covlookup[r['game_id']] for r in tebase];sp,_=cov.fitp(ctr,cte,'spread','coverage',{'team_k':cp['team_k'],'feature_k':cp['feature_k'],'lambda':cp['lambda']});refs['spread'][y]=np.asarray(sp,float);btr=[r for r in base_rows if r['season']<y];tp,_,_,_,_=base.fit_and_predict(btr,tebase,'total',tbp['k'],tbp['lambda']);refs['total'][y]=np.asarray(tp,float)
 variants={}
 for fam in FAMILIES:
  variants[fam]={}
  for kind in ['spread','total']:
   par=frozen[(fam,kind)];pp={};folds={}
   for y in YEARS:
    tr=[r for r in rows if r['season']<y];te=tests[y];fo=fit(tr,kind,fam,par['team_k'],par['lambda'],kind=='spread',cp['feature_k']);p=pred(te,kind,fam,par['team_k'],fo,kind=='spread',cp['feature_k']);pp[y]=p;re=ae(te,refs[kind][y],kind);ce=ae(te,p,kind);folds[str(y)]={'n':len(te),'reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4)}
   allrows=[];rr=[];qq=[]
   for y in YEARS:allrows+=tests[y];rr+=list(refs[kind][y]);qq+=list(pp[y])
   re=ae(allrows,rr,kind);ce=ae(allrows,qq,kind);variants[fam][kind]={'frozen_params':par,'folds':folds,'aggregate':{'n':len(allrows),'reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4),'seasons_improved':sum(folds[str(y)]['delta']<0 for y in YEARS),'bootstrap':boot(re-ce)},'reference':'frozen_coverage' if kind=='spread' else 'frozen_core_total'}
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'Static context hyperparameters selected from 2022 only and frozen for 2023-2025. Historical observed temp/wind excluded.','source_rows':nrows,'variants':variants,'release_state':'HOLD_ROBUSTNESS_ONLY','website_publish_allowed':False};OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({f:{k:v[k]['aggregate'] for k in ['spread','total']} for f,v in variants.items()},indent=2))
if __name__=='__main__':main()
