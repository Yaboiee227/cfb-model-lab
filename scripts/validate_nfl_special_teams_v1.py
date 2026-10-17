#!/usr/bin/env python3
"""Walk-forward validation for NFL special-teams candidate families."""
from __future__ import annotations
import csv,json,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
IN=Path('nfl_data/historical/team_week_special_teams_2022_2025.csv');OUT=Path('nfl_data/validation');YEARS=[2023,2024,2025];KGRID=[1.,2.,4.,8.,16.]
FAMILIES={'kicking':['fg_pct','fg_40_49_pct','fg_50_plus_pct','pat_pct'],'punting':['punt_net_avg','punt_inside20_rate','punt_touchback_rate'],'returns':['punt_return_avg','kickoff_return_avg'],'full_special_teams':['fg_pct','fg_40_49_pct','fg_50_plus_pct','pat_pct','punt_net_avg','punt_inside20_rate','punt_touchback_rate','punt_block_rate','punt_return_avg','kickoff_return_avg','special_teams_td_per_game']}
def tf(v):return base.to_float(v)
def loadidx():
 with IN.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
 idx={};leak=0
 for r in rows:
  k=(int(float(r['season'])),int(float(r['target_week'])),r['team']);idx[k]=r
  if tf(r.get('max_current_week_used')) is not None and tf(r['max_current_week_used'])>=k[1]:leak+=1
 return idx,leak,len(rows)
def attach(rows,idx):
 out=[];miss=[]
 for r in rows:
  h=idx.get((r['season'],r['week'],r['home_team']));a=idx.get((r['season'],r['week'],r['away_team']))
  if h is None or a is None:miss.append(r['game_id']);continue
  x=dict(r)
  for side,row in [('home',h),('away',a)]:
   for k,v in row.items():
    if k not in {'season','target_week','team','release_state'}:x[f'{side}_st_{k}']=v
  out.append(x)
 if miss:raise RuntimeError(f'missing ST snapshots {len(miss)} first={miss[:5]}')
 return out
def blend(r,side,m,k):
 games=tf(r.get(f'{side}_games_before')) or 0.;cur=tf(r.get(f'{side}_st_cur_{m}'));prior=tf(r.get(f'{side}_st_prior_{m}'))
 if cur is not None and prior is not None:return (games*cur+k*prior)/(games+k)
 return cur if cur is not None else prior
def feats(r,kind,fam,k):
 ms=FAMILIES[fam];h=[blend(r,'home',m,k) for m in ms];a=[blend(r,'away',m,k) for m in ms];op=base.diff if kind=='spread' else base.summ;suf='diff' if kind=='spread' else 'sum';return [f'st_{m}_{suf}' for m in ms],[op(x,y) for x,y in zip(h,a)]
def matrix(rows,tk,xk,kind,fam):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,tk) if kind=='spread' else base.total_features(r,tk);xn,xv=feats(r,kind,fam,xk)
  if names is None:names=bn+xn
  data.append([np.nan if z is None else float(z) for z in bv+xv])
 return names,np.asarray(data,float)
def select(tr,kind,fam):
 fit,val=base.inner_split(tr);yf=base.target_array(fit,kind);yv=base.target_array(val,kind);cs=[]
 for tk in base.K_GRID:
  for xk in KGRID:
   _,X=matrix(fit,tk,xk,kind,fam);_,Z=matrix(val,tk,xk,kind,fam);prep=base.fit_preprocessor(X);X=base.transform(X,prep);Z=base.transform(Z,prep)
   for lam in base.LAMBDA_GRID:
    mo=base.ridge_fit(X,yf,lam);p=base.predict(mo,Z);cs.append({'team_k':tk,'feature_k':xk,'lambda':lam,'mae':base.mae(yv,p),'rmse':base.rmse(yv,p)})
 cs.sort(key=lambda x:(x['mae'],x['rmse'],x['lambda']));return cs[0],cs[:10]
def fitp(tr,te,kind,fam,p):
 names,X=matrix(tr,p['team_k'],p['feature_k'],kind,fam);_,Z=matrix(te,p['team_k'],p['feature_k'],kind,fam);prep=base.fit_preprocessor(X);mo=base.ridge_fit(base.transform(X,prep),base.target_array(tr,kind),p['lambda']);pr=base.predict(mo,base.transform(Z,prep));return pr,{n:float(v) for n,v in zip(names,mo[1])}
def met(rows,p,kind):
 y=base.target_array(rows,kind);return {'n':len(rows),'mae':round(base.mae(y,p),4),'rmse':round(base.rmse(y,p),4),'bias':round(base.bias(y,p),4),'market_reference_mae':round(base.market_mae(rows,kind),4),'edge_grading':base.grading(rows,p,kind)}
def agg(fs):
 n=sum(x['n'] for x in fs);return {'n':n,**{m:round(sum(x[m]*x['n'] for x in fs)/n,4) for m in ['mae','rmse','bias','market_reference_mae']}}
def main():
 OUT.mkdir(parents=True,exist_ok=True);idx,leak,nrows=loadidx()
 if leak:raise RuntimeError(f'leak={leak}')
 rows=attach(base.load_rows(),idx);bf=defaultdict(list);vf=defaultdict(list);preds=[];coefs=[];summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_rows':nrows,'source_leakage_rows':leak,'variants':{},'market_policy':'BENCHMARK_ONLY_NOT_MODEL_FEATURE','release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False}
 for yr in YEARS:
  tr=[r for r in rows if r['season']<yr];te=[r for r in rows if r['season']==yr]
  for kind in ['spread','total']:
   bp,_=base.select_params(tr,kind);b,_,_,_,_=base.fit_and_predict(tr,te,kind,bp['k'],bp['lambda']);bm=met(te,b,kind);bm['season']=yr;bf[kind].append(bm)
   for fam in FAMILIES:
    best,top=select(tr,kind,fam);p,c=fitp(tr,te,kind,fam,best);m=met(te,p,kind);m.update({'season':yr,**best,'inner_top_candidates':top});vf[(fam,kind)].append(m)
    for n,v in c.items():coefs.append({'season':yr,'kind':kind,'variant':fam,**{k:best[k] for k in ['team_k','feature_k','lambda']},'feature':n,'standardized_coefficient':round(v,7)})
    for r,pv in zip(te,p):preds.append({'game_id':r['game_id'],'season':yr,'week':r['week'],'kind':kind,'variant':fam,'actual':r['home_margin'] if kind=='spread' else r['game_total'],'prediction':round(float(pv),5),'market_reference':r['market_home_spread_reference'] if kind=='spread' else r['market_total_reference'],'release_state':'HOLD_RESEARCH_ONLY'})
 summary['baseline']={k:{'folds':bf[k],'aggregate':agg(bf[k])} for k in ['spread','total']}
 for fam in FAMILIES:
  summary['variants'][fam]={}
  for kind in ['spread','total']:
   fs=vf[(fam,kind)];a=agg(fs);b=summary['baseline'][kind]['aggregate'];wins=sum(x['mae']<y['mae'] for x,y in zip(fs,bf[kind]));d=round(a['mae']-b['mae'],4);summary['variants'][fam][kind]={'folds':fs,'aggregate':a,'mae_delta_vs_baseline':d,'seasons_with_lower_mae':wins,'historical_verdict':'EARNED_FURTHER_TESTING' if d<=-0.05 and wins>=2 else 'NO_PROMOTION','production_verdict':'HOLD_RESEARCH_ONLY'}
 for fn,rr in [('special_teams_v1_predictions.csv',preds),('special_teams_v1_coefficients.csv',coefs)]:
  with (OUT/fn).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 (OUT/'special_teams_v1_qa.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'verdicts':{f:{k:{'delta':summary['variants'][f][k]['mae_delta_vs_baseline'],'wins':summary['variants'][f][k]['seasons_with_lower_mae'],'verdict':summary['variants'][f][k]['historical_verdict']} for k in ['spread','total']} for f in FAMILIES}},indent=2))
if __name__=='__main__':main()
