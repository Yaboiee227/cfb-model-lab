#!/usr/bin/env python3
"""Validate sequential post-calibration for the final NFL research architecture.

Tests only pre-specified, interpretable corrections:
1) totals bias correction learned from prior out-of-sample seasons only;
2) fixed market/model blend weight selected on 2023 OOS predictions only and
   frozen for 2024-2025.

This is a calibration/benchmark layer, not part of the independent core model.
No recommendation or ROI release is permitted from this script.
"""
from __future__ import annotations
import csv,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np

IN=Path('nfl_data/calibration/final_architecture_oos_predictions_2023_2025.csv')
OUT=Path('nfl_data/calibration/postcalibration_validation.json')
YEARS=[2023,2024,2025];TEST_YEARS=[2024,2025];WGRID=[round(x*0.05,2) for x in range(21)];DRAWS=5000;SEED=20261017

def f(v):
 try:return float(v)
 except:return None

def mae(a,b):return float(np.mean(np.abs(np.asarray(a,float)-np.asarray(b,float))))
def rmse(a,b):return float(np.sqrt(np.mean((np.asarray(a,float)-np.asarray(b,float))**2)))
def boot(ae_ref,ae_cand):
 d=np.asarray(ae_ref,float)-np.asarray(ae_cand,float);rng=np.random.default_rng(SEED);n=len(d);vals=np.empty(DRAWS)
 for i in range(DRAWS):vals[i]=np.mean(d[rng.integers(0,n,size=n)])
 lo,hi=np.quantile(vals,[.025,.975]);return {'mean_improvement':round(float(np.mean(d)),5),'bootstrap_95_ci':[round(float(lo),5),round(float(hi),5)],'probability_gt_0':round(float(np.mean(vals>0)),4),'draws':DRAWS,'seed':SEED}

def load():
 with IN.open(encoding='utf-8') as fh:r=list(csv.DictReader(fh))
 for x in r:x['season']=int(x['season']);x['week']=int(x['week'])
 return r

def fields(r,kind):
 if kind=='spread':
  actual=f(r['actual_home_margin']);model=f(r['pred_home_margin']);line=f(r['market_home_spread_reference']);market=None if line is None else -line
 else:
  actual=f(r['actual_total']);model=f(r['pred_total']);market=f(r['market_total_reference'])
 return actual,model,market

def select_weight(cal,kind):
 best=None
 for w in WGRID:
  y=[];p=[]
  for r in cal:
   a,m,mkt=fields(r,kind)
   if None in (a,m,mkt):continue
   y.append(a);p.append(mkt+w*(m-mkt))
  rec={'weight_on_independent_model':w,'weight_on_market':round(1-w,2),'n':len(y),'mae':mae(y,p),'rmse':rmse(y,p)}
  if best is None or (rec['mae'],rec['rmse'],rec['weight_on_independent_model'])<(best['mae'],best['rmse'],best['weight_on_independent_model']):best=rec
 return best

def main():
 OUT.parent.mkdir(parents=True,exist_ok=True);rows=load();cal=[r for r in rows if r['season']==2023];tests=[r for r in rows if r['season'] in TEST_YEARS]
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'design':'2023 OOS used only for calibration selection; 2024-2025 held out for frozen post-calibration validation. Totals sequential bias correction uses only prior OOS seasons.','market_policy':'Market blend is a separate benchmark/calibration layer; independent core remains market-free.','tests':{},'release_state':'HOLD_POSTCALIBRATION_RESEARCH','website_publish_allowed':False}
 # Frozen market/model blend selected on 2023 only.
 for kind in ['spread','total']:
  sel=select_weight(cal,kind);folds={};all_y=[];all_model=[];all_market=[];all_blend=[]
  for y in TEST_YEARS:
   yy=[];mm=[];mk=[];bb=[]
   for r in rows:
    if r['season']!=y:continue
    a,m,mkt=fields(r,kind)
    if None in (a,m,mkt):continue
    b=mkt+sel['weight_on_independent_model']*(m-mkt);yy.append(a);mm.append(m);mk.append(mkt);bb.append(b)
   folds[str(y)]={'n':len(yy),'independent_model_mae':round(mae(yy,mm),4),'market_reference_mae':round(mae(yy,mk),4),'blend_mae':round(mae(yy,bb),4),'blend_delta_vs_market':round(mae(yy,bb)-mae(yy,mk),4)};all_y+=yy;all_model+=mm;all_market+=mk;all_blend+=bb
  am=np.abs(np.asarray(all_y)-np.asarray(all_market));ab=np.abs(np.asarray(all_y)-np.asarray(all_blend))
  result['tests'][f'{kind}_market_blend']={'selected_on_2023':sel,'folds':folds,'aggregate_2024_2025':{'n':len(all_y),'independent_model_mae':round(mae(all_y,all_model),4),'market_reference_mae':round(mae(all_y,all_market),4),'blend_mae':round(mae(all_y,all_blend),4),'blend_delta_vs_market':round(mae(all_y,all_blend)-mae(all_y,all_market),4),'bootstrap_vs_market':boot(am,ab)},'verdict':'EARNED_FURTHER_TESTING' if boot(am,ab)['bootstrap_95_ci'][0]>0 and sum(folds[str(y)]['blend_delta_vs_market']<0 for y in TEST_YEARS)==2 else 'NO_PROMOTION'}
 # Sequential totals bias correction. 2024 uses 2023 OOS bias; 2025 uses 2023-24 OOS bias.
 folds={};all_y=[];all_raw=[];all_corr=[]
 for y in TEST_YEARS:
  prior=[r for r in rows if r['season']<y];res=[]
  for r in prior:
   a,m,_=fields(r,'total')
   if a is not None and m is not None:res.append(a-m)
  correction=float(np.mean(res));yy=[];rr=[];cc=[]
  for r in rows:
   if r['season']!=y:continue
   a,m,_=fields(r,'total')
   if a is None or m is None:continue
   yy.append(a);rr.append(m);cc.append(m+correction)
  folds[str(y)]={'n':len(yy),'prior_oos_mean_actual_minus_pred_correction':round(correction,4),'raw_mae':round(mae(yy,rr),4),'corrected_mae':round(mae(yy,cc),4),'delta':round(mae(yy,cc)-mae(yy,rr),4)};all_y+=yy;all_raw+=rr;all_corr+=cc
 ar=np.abs(np.asarray(all_y)-np.asarray(all_raw));ac=np.abs(np.asarray(all_y)-np.asarray(all_corr));bs=boot(ar,ac)
 result['tests']['total_sequential_bias_correction']={'folds':folds,'aggregate_2024_2025':{'n':len(all_y),'raw_mae':round(mae(all_y,all_raw),4),'corrected_mae':round(mae(all_y,all_corr),4),'delta':round(mae(all_y,all_corr)-mae(all_y,all_raw),4),'bootstrap':bs},'verdict':'EARNED_RESEARCH_INCLUSION' if bs['bootstrap_95_ci'][0]>0 and sum(folds[str(y)]['delta']<0 for y in TEST_YEARS)==2 else 'NO_PROMOTION'}
 OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
