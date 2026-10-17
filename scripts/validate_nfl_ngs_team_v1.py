#!/usr/bin/env python3
"""Incremental walk-forward validation of leakage-safe team-level NFL NGS features.

Tests passing, rushing, receiving, and combined NGS families separately against
our frozen market-independent baseline. Market prices remain benchmarks only.
"""
from __future__ import annotations
import csv, json, math, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base

INFILE=Path('nfl_data/historical/team_week_ngs_2022_2025.csv')
OUT=Path('nfl_data/validation')
YEARS=[2023,2024,2025]
NGS_K=[1.,2.,4.,8.,16.]
FAMILIES={
 'passing_ngs':[
  'pass_avg_time_to_throw','pass_avg_completed_air_yards','pass_avg_intended_air_yards',
  'pass_avg_air_yards_differential','pass_aggressiveness','pass_avg_air_yards_to_sticks',
  'pass_passer_rating','pass_completion_percentage','pass_expected_completion_percentage',
  'pass_completion_percentage_above_expectation'],
 'rushing_ngs':['rush_efficiency','rush_percent_attempts_gte_eight_defenders','rush_avg_time_to_los','rush_avg_rush_yards','rush_rush_yards_over_expected_per_att','rush_rush_pct_over_expected'],
 'receiving_ngs':['rec_avg_cushion','rec_avg_separation','rec_percent_share_of_intended_air_yards','rec_catch_percentage','rec_avg_yac','rec_avg_expected_yac','rec_avg_yac_above_expectation'],
}
FAMILIES['all_ngs']=FAMILIES['passing_ngs']+FAMILIES['rushing_ngs']+FAMILIES['receiving_ngs']

def tf(v): return base.to_float(v)

def load_index():
 with INFILE.open(encoding='utf-8') as f: rows=list(csv.DictReader(f))
 idx={}; leak=0
 for r in rows:
  key=(int(float(r['season'])),int(float(r['target_week'])),r['team'])
  if key in idx: raise RuntimeError(f'duplicate NGS snapshot {key}')
  max_allowed=int(float(r.get('max_current_week_allowed') or 0))
  # Source builder already asserts strict cutoff; recheck any reported max-week fields.
  for k,v in r.items():
   if k.startswith('cur_') and k.endswith('_max_week_used') and tf(v) is not None and tf(v)>=key[1]: leak+=1
  idx[key]=r
 return idx,leak,len(rows)

def attach(rows,idx):
 out=[]; miss=[]
 for r in rows:
  h=idx.get((r['season'],r['week'],r['home_team'])); a=idx.get((r['season'],r['week'],r['away_team']))
  if h is None or a is None: miss.append(r['game_id']); continue
  x=dict(r)
  for side,row in [('home',h),('away',a)]:
   for k,v in row.items():
    if k not in {'season','target_week','team','release_state'}: x[f'{side}_ngs_{k}']=v
  out.append(x)
 if miss: raise RuntimeError(f'missing NGS snapshots {len(miss)} first={miss[:5]}')
 return out

def blend(r,side,m,k):
 games=tf(r.get(f'{side}_games_before')) or 0.
 cur=tf(r.get(f'{side}_ngs_cur_{m}')); prior=tf(r.get(f'{side}_ngs_prior_{m}'))
 if cur is not None and prior is not None: return (games*cur+k*prior)/(games+k)
 if cur is not None:return cur
 if prior is not None:return prior
 return None

def ngs_features(r,kind,family,k):
 metrics=FAMILIES[family]
 h=[blend(r,'home',m,k) for m in metrics]; a=[blend(r,'away',m,k) for m in metrics]
 suffix='diff' if kind=='spread' else 'sum'
 names=[f'ngs_{m}_{suffix}' for m in metrics]
 vals=[(base.diff(x,y) if kind=='spread' else base.summ(x,y)) for x,y in zip(h,a)]
 return names,vals

def matrix(rows,team_k,ngs_k,kind,family):
 data=[]; names=None
 for r in rows:
  bn,bv=base.spread_features(r,team_k) if kind=='spread' else base.total_features(r,team_k)
  nn,nv=ngs_features(r,kind,family,ngs_k)
  if names is None:names=bn+nn
  data.append([np.nan if x is None else float(x) for x in bv+nv])
 return names,np.asarray(data,float)

def select(train,kind,family):
 fit,val=base.inner_split(train); yf=base.target_array(fit,kind); yv=base.target_array(val,kind); cand=[]
 for tk in base.K_GRID:
  for nk in NGS_K:
   names,Xf=matrix(fit,tk,nk,kind,family); _,Xv=matrix(val,tk,nk,kind,family)
   prep=base.fit_preprocessor(Xf); Xfz=base.transform(Xf,prep); Xvz=base.transform(Xv,prep)
   for lam in base.LAMBDA_GRID:
    model=base.ridge_fit(Xfz,yf,lam); p=base.predict(model,Xvz)
    cand.append({'team_k':tk,'ngs_k':nk,'lambda':lam,'mae':base.mae(yv,p),'rmse':base.rmse(yv,p),'n':len(val)})
 cand.sort(key=lambda x:(x['mae'],x['rmse'],x['lambda'],x['ngs_k']))
 return cand[0],cand[:10]

def fitpred(train,test,kind,family,p):
 names,Xtr=matrix(train,p['team_k'],p['ngs_k'],kind,family); _,Xte=matrix(test,p['team_k'],p['ngs_k'],kind,family)
 prep=base.fit_preprocessor(Xtr); Xz=base.transform(Xtr,prep); Xtez=base.transform(Xte,prep)
 model=base.ridge_fit(Xz,base.target_array(train,kind),p['lambda']); pred=base.predict(model,Xtez)
 return pred,{n:float(v) for n,v in zip(names,model[1])}

def met(rows,p,kind):
 y=base.target_array(rows,kind)
 return {'n':len(rows),'mae':round(base.mae(y,p),4),'rmse':round(base.rmse(y,p),4),'bias':round(base.bias(y,p),4),'market_reference_mae':round(base.market_mae(rows,kind),4),'edge_grading':base.grading(rows,p,kind)}

def agg(fs):
 n=sum(x['n'] for x in fs)
 return {'n':n,**{m:round(sum(x[m]*x['n'] for x in fs)/n,4) for m in ['mae','rmse','bias','market_reference_mae']}}

def main():
 OUT.mkdir(parents=True,exist_ok=True); idx,leak,nrows=load_index()
 if leak: raise RuntimeError(f'NGS leakage rows={leak}')
 rows=attach(base.load_rows(),idx); bf=defaultdict(list); vf=defaultdict(list); preds=[]; coefs=[]
 summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_rows':nrows,'source_leakage_rows':leak,'market_policy':'BENCHMARK_ONLY_NOT_MODEL_FEATURE','variants':{},'release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False}
 for yr in YEARS:
  tr=[r for r in rows if r['season']<yr]; te=[r for r in rows if r['season']==yr]
  for kind in ['spread','total']:
   bp,_=base.select_params(tr,kind); bpred,_,_,_,_=base.fit_and_predict(tr,te,kind,bp['k'],bp['lambda']); bm=met(te,bpred,kind); bm['season']=yr; bf[kind].append(bm)
   for fam in FAMILIES:
    best,top=select(tr,kind,fam); p,coef=fitpred(tr,te,kind,fam,best); m=met(te,p,kind); m.update({'season':yr,**best,'inner_top_candidates':top}); vf[(fam,kind)].append(m)
    for name,val in coef.items(): coefs.append({'season':yr,'kind':kind,'variant':fam,'team_k':best['team_k'],'ngs_k':best['ngs_k'],'lambda':best['lambda'],'feature':name,'standardized_coefficient':round(val,7)})
    for r,pv in zip(te,p): preds.append({'game_id':r['game_id'],'season':yr,'week':r['week'],'kind':kind,'variant':fam,'actual':r['home_margin'] if kind=='spread' else r['game_total'],'prediction':round(float(pv),5),'market_reference':r['market_home_spread_reference'] if kind=='spread' else r['market_total_reference'],'release_state':'HOLD_RESEARCH_ONLY'})
 summary['baseline']={k:{'folds':bf[k],'aggregate':agg(bf[k])} for k in ['spread','total']}
 for fam in FAMILIES:
  summary['variants'][fam]={}
  for kind in ['spread','total']:
   fs=vf[(fam,kind)]; a=agg(fs); b=summary['baseline'][kind]['aggregate']; wins=sum(1 for x,y in zip(fs,bf[kind]) if x['mae']<y['mae']); d=round(a['mae']-b['mae'],4); earned=d<=-0.05 and wins>=2
   summary['variants'][fam][kind]={'folds':fs,'aggregate':a,'mae_delta_vs_baseline':d,'seasons_with_lower_mae':wins,'historical_verdict':'EARNED_FURTHER_TESTING' if earned else 'NO_PROMOTION','production_verdict':'HOLD_RESEARCH_ONLY'}
 with (OUT/'ngs_team_v1_predictions.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(preds[0]));w.writeheader();w.writerows(preds)
 with (OUT/'ngs_team_v1_coefficients.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(coefs[0]));w.writeheader();w.writerows(coefs)
 (OUT/'ngs_team_v1_qa.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'baseline':{k:summary['baseline'][k]['aggregate'] for k in ['spread','total']},'verdicts':{fam:{k:{'delta':summary['variants'][fam][k]['mae_delta_vs_baseline'],'wins':summary['variants'][fam][k]['seasons_with_lower_mae'],'verdict':summary['variants'][fam][k]['historical_verdict']} for k in ['spread','total']} for fam in FAMILIES},'release_state':'HOLD_RESEARCH_ONLY'},indent=2))
if __name__=='__main__':main()
