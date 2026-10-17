#!/usr/bin/env python3
"""Calibrate uncertainty and benchmark-edge behavior for the final NFL research architecture.

Final research architecture as of Week 6 2026:
- spread: frozen core + defensive coverage + market-independent win Elo + margin rating
- total: frozen core baseline only

All hyperparameters are selected using 2022 only and frozen. Predictions are
strict outer walk-forward for 2023-2025 (816 unseen games). Market lines are
benchmark/reference fields only. No ROI is reported because executable price
and juice are not verified historically.
"""
from __future__ import annotations
import csv,json,math,sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix
import validate_nfl_coverage_v1 as cov
import validate_nfl_rating_system_robustness as rat

OUT=Path('nfl_data/calibration'); YEARS=[2023,2024,2025]
RATING={'elo_hfa':35.0,'elo_k':40.0,'lambda':100.0,'margin_hfa':3.0,'margin_k':0.05,'offseason_regression':0.25}
THRESHOLDS=[0.0,1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0]
EDGE_BUCKETS=[(0,1),(1,2),(2,3),(3,4),(4,5),(5,7),(7,10),(10,999)]
WEEK_BUCKETS={'weeks_1_5':lambda w:1<=w<=5,'weeks_6_12':lambda w:6<=w<=12,'weeks_13_18':lambda w:13<=w<=18}
BREAK_EVEN_110=1.1/2.1

def wilson(w,n,z=1.959963984540054):
 if n<=0:return [None,None]
 p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
 return [round(max(0,c-h),4),round(min(1,c+h),4)]

def summary_error(rows,p,kind):
 y=base.target_array(rows,kind);p=np.asarray(p,float);e=y-p;ae=np.abs(e)
 return {'n':len(rows),'mae':round(float(np.mean(ae)),4),'rmse':round(float(np.sqrt(np.mean(e*e))),4),'bias_pred_minus_actual':round(float(np.mean(p-y)),4),'signed_actual_minus_pred_quantiles':{str(q):round(float(np.quantile(e,q)),4) for q in [0.05,0.10,0.16,0.25,0.50,0.75,0.84,0.90,0.95]},'absolute_error_quantiles':{str(q):round(float(np.quantile(ae,q)),4) for q in [0.50,0.68,0.75,0.80,0.90,0.95]}}

def market_row(r,p,kind):
 if kind=='spread':
  line=base.to_float(r.get('market_home_spread_reference'));actual=float(r['home_margin'])
  if line is None:return None
  edge=float(p)+line;result=actual+line
 else:
  line=base.to_float(r.get('market_total_reference'));actual=float(r['game_total'])
  if line is None:return None
  edge=float(p)-line;result=actual-line
 if abs(result)<1e-12:decision='push'
 elif edge*result>0:decision='win'
 else:decision='loss'
 return {'edge':edge,'abs_edge':abs(edge),'result':result,'decision':decision}

def edge_stats(rows,preds,kind,selector):
 rec=[]
 for r,p in zip(rows,preds):
  z=market_row(r,p,kind)
  if z is not None and selector(z):rec.append((r,z))
 wins=sum(z['decision']=='win' for _,z in rec);losses=sum(z['decision']=='loss' for _,z in rec);pushes=sum(z['decision']=='push' for _,z in rec);n=wins+losses
 wr=None if n==0 else wins/n
 seasons={}
 for y in YEARS:
  rr=[z for r,z in rec if int(r['season'])==y];w=sum(z['decision']=='win' for z in rr);l=sum(z['decision']=='loss' for z in rr);p=sum(z['decision']=='push' for z in rr);d=w+l
  seasons[str(y)]={'n':d+p,'decisions':d,'wins':w,'losses':l,'pushes':p,'win_rate':None if not d else round(w/d,4)}
 return {'n':len(rec),'decisions':n,'wins':wins,'losses':losses,'pushes':pushes,'win_rate':None if wr is None else round(wr,4),'wilson_95':wilson(wins,n),'minus110_break_even':round(BREAK_EVEN_110,4),'seasons':seasons}

def threshold_verdict(s):
 if s['decisions']<100 or s['win_rate'] is None:return 'INSUFFICIENT_SAMPLE'
 improved=sum(1 for y in YEARS if s['seasons'][str(y)]['decisions']>=20 and (s['seasons'][str(y)]['win_rate'] or 0)>0.5)
 lo=s['wilson_95'][0]
 if s['win_rate']>BREAK_EVEN_110 and lo is not None and lo>0.50 and improved>=2:return 'EARNED_PROSPECTIVE_THRESHOLD_TEST'
 return 'NO_HISTORICAL_RELEASE_EVIDENCE'

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov')
 if nl+cl:raise RuntimeError(f'coverage source leakage ngs={nl} cov={cl}')
 covrows=cov.attach(base_rows,ci,ni);c22=[r for r in covrows if r['season']==2022];cp,_=cov.select(c22,'spread','coverage')
 b22=[r for r in base_rows if r['season']==2022];tp,_=base.select_params(b22,'total')
 games=rat.fetch_games();rmap=rat.rating_maps(games,RATING['elo_k'],RATING['elo_hfa'],RATING['offseason_regression'],RATING['margin_k'],RATING['margin_hfa']);rated=rat.attach(covrows,rmap);rated_lookup={r['game_id']:r for r in rated};base_lookup={r['game_id']:r for r in base_rows}
 predictions=[];folds={}
 for y in YEARS:
  sptr=[r for r in rated if r['season']<y];spte=[r for r in rated if r['season']==y];fo=rat.fit(sptr,'both',cp['team_k'],RATING['lambda'],cp['feature_k']);sp=rat.pred(spte,'both',cp['team_k'],cp['feature_k'],fo)
  tetr=[r for r in base_rows if r['season']==y];tr=[r for r in base_rows if r['season']<y];tot,_,_,_,_=base.fit_and_predict(tr,tetr,'total',tp['k'],tp['lambda'])
  if [r['game_id'] for r in spte]!=[r['game_id'] for r in tetr]:
   sm={r['game_id']:float(p) for r,p in zip(spte,sp)};sp=np.asarray([sm[r['game_id']] for r in tetr],float);spte=[rated_lookup[r['game_id']] for r in tetr]
  folds[str(y)]={'spread':summary_error(spte,sp,'spread'),'total':summary_error(tetr,tot,'total')}
  for r,ps,pt in zip(tetr,sp,tot):
   predictions.append({'game_id':r['game_id'],'season':r['season'],'week':r['week'],'gameday':r['gameday'],'away_team':r['away_team'],'home_team':r['home_team'],'actual_home_margin':r['home_margin'],'pred_home_margin':round(float(ps),6),'spread_error_actual_minus_pred':round(float(r['home_margin'])-float(ps),6),'market_home_spread_reference':r.get('market_home_spread_reference',''),'spread_edge_vs_reference':'' if base.to_float(r.get('market_home_spread_reference')) is None else round(float(ps)+float(r['market_home_spread_reference']),6),'actual_total':r['game_total'],'pred_total':round(float(pt),6),'total_error_actual_minus_pred':round(float(r['game_total'])-float(pt),6),'market_total_reference':r.get('market_total_reference',''),'total_edge_vs_reference':'' if base.to_float(r.get('market_total_reference')) is None else round(float(pt)-float(r['market_total_reference']),6),'market_policy':'BENCHMARK_ONLY_NOT_MODEL_FEATURE','release_state':'HOLD_CALIBRATION_RESEARCH'})
 rows=[base_lookup[p['game_id']] for p in predictions];spp=np.asarray([p['pred_home_margin'] for p in predictions],float);ttp=np.asarray([p['pred_total'] for p in predictions],float)
 result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'architecture':{'spread':'frozen core + defensive coverage + win Elo + margin rating','total':'frozen core only'},'frozen_params':{'coverage':cp,'ratings':RATING,'total':tp},'games':len(rows),'folds':folds,'aggregate':{'spread':summary_error(rows,spp,'spread'),'total':summary_error(rows,ttp,'total')},'week_buckets':{},'edge_thresholds':{},'edge_buckets':{},'market_policy':'Historical schedule/market references are calibration benchmarks only; no executable price or juice assumed, so no ROI is reported.','release_state':'HOLD_CALIBRATION_RESEARCH','website_publish_allowed':False}
 for kind,p in [('spread',spp),('total',ttp)]:
  result['week_buckets'][kind]={}
  for name,fn in WEEK_BUCKETS.items():
   idx=[i for i,r in enumerate(rows) if fn(int(r['week']))];rr=[rows[i] for i in idx];pp=[p[i] for i in idx];result['week_buckets'][kind][name]=summary_error(rr,pp,kind)
  result['edge_thresholds'][kind]={}
  for t in THRESHOLDS:
   s=edge_stats(rows,p,kind,lambda z,t=t:z['abs_edge']>=t);s['historical_verdict']=threshold_verdict(s);result['edge_thresholds'][kind][str(t)]=s
  result['edge_buckets'][kind]={}
  for lo,hi in EDGE_BUCKETS:
   label=f'{lo}_to_{hi}' if hi<999 else f'{lo}_plus';result['edge_buckets'][kind][label]=edge_stats(rows,p,kind,lambda z,lo=lo,hi=hi:z['abs_edge']>=lo and z['abs_edge']<hi)
 with (OUT/'final_architecture_oos_predictions_2023_2025.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(predictions[0]));w.writeheader();w.writerows(predictions)
 (OUT/'final_architecture_calibration.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'aggregate':result['aggregate'],'spread_thresholds':{t:{'n':v['decisions'],'win_rate':v['win_rate'],'wilson':v['wilson_95'],'verdict':v['historical_verdict']} for t,v in result['edge_thresholds']['spread'].items()},'total_thresholds':{t:{'n':v['decisions'],'win_rate':v['win_rate'],'wilson':v['wilson_95'],'verdict':v['historical_verdict']} for t,v in result['edge_thresholds']['total'].items()},'release_state':result['release_state']},indent=2))
if __name__=='__main__':main()
