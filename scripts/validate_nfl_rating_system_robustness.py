#!/usr/bin/env python3
"""Frozen robustness validation for market-independent NFL rating systems.

Tests two recursively updated pregame rating families against the current robust
spread reference (core baseline + defensive coverage):
- win Elo: binary result update with configurable K, HFA and offseason regression
- margin rating: point-scale residual update with configurable learning rate/HFA

All rating states are updated only after completed prior games. Hyperparameters
and model regularization are selected from 2022 only, then frozen for 2023-2025.
No sportsbook data enter the ratings.
"""
from __future__ import annotations
import io,json,math,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix
import validate_nfl_coverage_v1 as cov

GAMES='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv';OUT=Path('nfl_data/validation/rating_system_robustness.json')
YEARS=[2023,2024,2025];K_ELO=[10.,20.,30.,40.];HFA_ELO=[35.,50.,65.,80.];REGRESS=[0.25,0.5,0.75];K_MARGIN=[0.05,0.10,0.20,0.30];HFA_MARGIN=[1.5,2.0,2.5,3.0];LAMBDAS=[0.1,1.,3.,10.,30.,100.];DRAWS=5000;SEED=20261017
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
VARIANTS=['win_elo','margin_rating','both']

def nt(v):
 s=str(v or '').strip().upper();return ALIASES.get(s,s)
def fetch_games():
 req=urllib.request.Request(GAMES,headers={'User-Agent':'cb-model-projections/1.0'})
 with urllib.request.urlopen(req,timeout=120) as r:df=pd.read_csv(io.BytesIO(r.read()))
 df=df[df['game_type'].astype(str).str.upper().eq('REG')].copy();df['season']=pd.to_numeric(df['season'],errors='coerce').astype('Int64');df['week']=pd.to_numeric(df['week'],errors='coerce').astype('Int64');df['home_team']=df['home_team'].map(nt);df['away_team']=df['away_team'].map(nt);df['home_score']=pd.to_numeric(df['home_score'],errors='coerce');df['away_score']=pd.to_numeric(df['away_score'],errors='coerce');df=df[df['season'].between(2021,2026)].sort_values(['season','week','gameday','gametime','game_id']);return df
def expected(rh,ra,hfa):return 1.0/(1.0+10.0**(-((rh+hfa)-ra)/400.0))
def rating_maps(df,ke,he,reg,km,hm):
 er={};mr={};out={};last_season=None
 for _,g in df.iterrows():
  s=int(g['season']);h=g['home_team'];a=g['away_team']
  if last_season is None:last_season=s
  if s!=last_season:
   for t in list(er):er[t]=1500.0+(er[t]-1500.0)*reg
   for t in list(mr):mr[t]=mr[t]*reg
   last_season=s
  eh=er.get(h,1500.0);ea=er.get(a,1500.0);mh=mr.get(h,0.0);ma=mr.get(a,0.0);out[str(g['game_id'])]={'win_elo_diff':eh-ea,'margin_rating_diff':mh-ma}
  hs,aws=g['home_score'],g['away_score']
  if pd.isna(hs) or pd.isna(aws):continue
  margin=float(hs-aws);actual=1.0 if margin>0 else 0.0 if margin<0 else 0.5;p=expected(eh,ea,he);delta=ke*(actual-p);er[h]=eh+delta;er[a]=ea-delta
  exp_margin=(mh-ma)+hm;resid=margin-exp_margin;md=km*resid;mr[h]=mh+md/2.0;mr[a]=ma-md/2.0
 return out
def attach(rows,rmap):
 out=[];miss=[]
 for r in rows:
  z=rmap.get(r['game_id'])
  if z is None:miss.append(r['game_id']);continue
  x=dict(r);x.update({f'rating_{k}':v for k,v in z.items()});out.append(x)
 if miss:raise RuntimeError(f'missing rating rows {len(miss)} first={miss[:5]}')
 return out
def matrix(rows,variant,team_k,with_cov,cov_k):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,team_k);rn=[];rv=[]
  if variant in {'win_elo','both'}:rn.append('rating_win_elo_diff');rv.append(float(r['rating_win_elo_diff']))
  if variant in {'margin_rating','both'}:rn.append('rating_margin_rating_diff');rv.append(float(r['rating_margin_rating_diff']))
  if with_cov:cn,cv=cov.extras(r,'spread','coverage',cov_k);n=bn+cn+rn;v=bv+cv+rv
  else:n=bn+rn;v=bv+rv
  if names is None:names=n
  data.append([np.nan if x is None else float(x) for x in v])
 return names,np.asarray(data,float)
def fit(rows,variant,tk,lam,covk):
 names,X=matrix(rows,variant,tk,True,covk);prep=base.fit_preprocessor(X);model=base.ridge_fit(base.transform(X,prep),base.target_array(rows,'spread'),lam);return names,prep,model
def pred(rows,variant,tk,covk,fo):
 names,prep,model=fo;_,X=matrix(rows,variant,tk,True,covk);return np.asarray(base.predict(model,base.transform(X,prep)),float)
def ae(rows,p):return np.abs(base.target_array(rows,'spread')-np.asarray(p,float))
def boot(d):
 rng=np.random.default_rng(SEED);n=len(d);v=np.empty(DRAWS)
 for i in range(DRAWS):v[i]=np.mean(d[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(v,[.025,.975]);return {'mean_improvement':round(float(np.mean(d)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_gt_0':round(float(np.mean(v>0)),4),'draws':DRAWS}
def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);games=fetch_games();base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov')
 if nl+cl:raise RuntimeError(f'coverage source leak ngs={nl} cov={cl}')
 covrows=cov.attach(base_rows,ci,ni);c22=[r for r in covrows if r['season']==2022];cp,_=cov.select(c22,'spread','coverage')
 # Frozen coverage reference.
 covlookup={r['game_id']:r for r in covrows};tests={};refs={}
 for y in YEARS:
  te=[r for r in covrows if r['season']==y];tr=[r for r in covrows if r['season']<y];p,_=cov.fitp(tr,te,'spread','coverage',{'team_k':cp['team_k'],'feature_k':cp['feature_k'],'lambda':cp['lambda']});tests[y]=te;refs[y]=np.asarray(p,float)
 # Select rating dynamics + model lambda from 2022 only. To limit multiple testing,
 # each variant uses the same compact grids and late-season 2022 validation split.
 selected={}
 for variant in VARIANTS:
  best=None
  for ke in K_ELO:
   for he in HFA_ELO:
    for reg in REGRESS:
     for km in K_MARGIN:
      for hm in HFA_MARGIN:
       if variant=='win_elo' and (km!=K_MARGIN[0] or hm!=HFA_MARGIN[0]):continue
       if variant=='margin_rating' and (ke!=K_ELO[0] or he!=HFA_ELO[0]):continue
       rm=rating_maps(games,ke,he,reg,km,hm);r22=attach(c22,rm);fr,vr=base.inner_split(r22);y=base.target_array(vr,'spread')
       for lam in LAMBDAS:
        fo=fit(fr,variant,cp['team_k'],lam,cp['feature_k']);p=pred(vr,variant,cp['team_k'],cp['feature_k'],fo);rec={'elo_k':ke,'elo_hfa':he,'offseason_regression':reg,'margin_k':km,'margin_hfa':hm,'lambda':lam,'mae':base.mae(y,p),'rmse':base.rmse(y,p)}
        if best is None or (rec['mae'],rec['rmse'],rec['lambda'])<(best['mae'],best['rmse'],best['lambda']):best=rec
  selected[variant]=best
 variants={}
 for variant,par in selected.items():
  rm=rating_maps(games,par['elo_k'],par['elo_hfa'],par['offseason_regression'],par['margin_k'],par['margin_hfa']);rated=attach(covrows,rm);lookup={r['game_id']:r for r in rated};pp={};folds={}
  for y in YEARS:
   tr=[r for r in rated if r['season']<y];te=[lookup[r['game_id']] for r in tests[y]];fo=fit(tr,variant,cp['team_k'],par['lambda'],cp['feature_k']);p=pred(te,variant,cp['team_k'],cp['feature_k'],fo);pp[y]=p;re=ae(te,refs[y]);ce=ae(te,p);folds[str(y)]={'n':len(te),'coverage_reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4)}
  rows=[];rr=[];qq=[]
  for y in YEARS:rows+=tests[y];rr+=list(refs[y]);qq+=list(pp[y])
  re=ae(rows,rr);ce=ae(rows,qq);variants[variant]={'frozen_params':par,'folds':folds,'aggregate':{'n':len(rows),'reference_mae':round(float(np.mean(re)),4),'candidate_mae':round(float(np.mean(ce)),4),'delta':round(float(np.mean(ce)-np.mean(re)),4),'seasons_improved':sum(folds[str(y)]['delta']<0 for y in YEARS),'bootstrap':boot(re-ce)}}
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'Market-independent recursive ratings. Rating dynamics and ridge lambda selected using 2022 only; frozen for 2023-2025. Compared with frozen coverage reference.','frozen_coverage':cp,'variants':variants,'release_state':'HOLD_ROBUSTNESS_ONLY','website_publish_allowed':False};OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({k:v['aggregate'] for k,v in variants.items()},indent=2))
if __name__=='__main__':main()
