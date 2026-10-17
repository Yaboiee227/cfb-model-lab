#!/usr/bin/env python3
"""Walk-forward validation for defensive coverage and receiver-tracking matchups."""
from __future__ import annotations
import csv,json,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base

COV=Path('nfl_data/historical/team_week_coverage_2022_2025.csv')
NGS=Path('nfl_data/historical/team_week_ngs_2022_2025.csv')
OUT=Path('nfl_data/validation'); YEARS=[2023,2024,2025]; KGRID=[1.,2.,4.,8.,16.]
ALIASES={'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}
COV_MET=['coverage_completion_pct','coverage_yards_per_target','coverage_td_rate','coverage_int_rate','coverage_passer_rating_allowed','coverage_adot_allowed','coverage_yac_per_completion','coverage_missed_tackle_rate']
REC_MET=['rec_avg_separation','rec_catch_percentage','rec_avg_yac','rec_avg_expected_yac','rec_avg_yac_above_expectation','rec_avg_cushion']
VARIANTS=['coverage','coverage_receiving_matchup']

def tf(v):return base.to_float(v)
def nt(t):return ALIASES.get(t,t)
def loadidx(path,prefix):
 with path.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
 idx={};leak=0
 for r in rows:
  s=int(float(r['season']));w=int(float(r['target_week']));t=nt(r['team']); idx[(s,w,t)]=r
  for k,v in r.items():
   if (k=='max_current_week_used' or (k.startswith('cur_') and k.endswith('_max_week_used'))) and tf(v) is not None and tf(v)>=w:leak+=1
 return idx,leak,len(rows)
def attach(rows,cov,ngs):
 out=[];miss=[]
 for r in rows:
  keys=[(r['season'],r['week'],r['home_team']),(r['season'],r['week'],r['away_team'])]
  if any(k not in cov or k not in ngs for k in keys):miss.append(r['game_id']);continue
  x=dict(r)
  for side,k in zip(['home','away'],keys):
   for a,b in cov[k].items():
    if a not in {'season','target_week','team','release_state'}:x[f'{side}_cov_{a}']=b
   for a,b in ngs[k].items():
    if a not in {'season','target_week','team','release_state'}:x[f'{side}_ngs_{a}']=b
  out.append(x)
 if miss:raise RuntimeError(f'missing snapshots {len(miss)} first={miss[:5]}')
 return out
def blend(r,side,src,m,k):
 games=tf(r.get(f'{side}_games_before')) or 0.;cur=tf(r.get(f'{side}_{src}_cur_{m}'));prior=tf(r.get(f'{side}_{src}_prior_{m}'))
 if cur is not None and prior is not None:return (games*cur+k*prior)/(games+k)
 return cur if cur is not None else prior
def extras(r,kind,variant,k):
 h={m:blend(r,'home','cov',m,k) for m in COV_MET};a={m:blend(r,'away','cov',m,k) for m in COV_MET};op=base.diff if kind=='spread' else base.summ;suf='diff' if kind=='spread' else 'sum';names=[f'cov_{m}_{suf}' for m in COV_MET];vals=[op(h[m],a[m]) for m in COV_MET]
 if variant=='coverage_receiving_matchup':
  hr={m:blend(r,'home','ngs',m,k) for m in REC_MET};ar={m:blend(r,'away','ngs',m,k) for m in REC_MET}
  names += [f'rec_{m}_{suf}' for m in REC_MET]; vals += [op(hr[m],ar[m]) for m in REC_MET]
  hm_yac=None if hr['rec_avg_yac_above_expectation'] is None or a['coverage_yac_per_completion'] is None else hr['rec_avg_yac_above_expectation']+a['coverage_yac_per_completion'];am_yac=None if ar['rec_avg_yac_above_expectation'] is None or h['coverage_yac_per_completion'] is None else ar['rec_avg_yac_above_expectation']+h['coverage_yac_per_completion']
  hm_catch=None if hr['rec_catch_percentage'] is None or a['coverage_completion_pct'] is None else hr['rec_catch_percentage']+100*a['coverage_completion_pct'];am_catch=None if ar['rec_catch_percentage'] is None or h['coverage_completion_pct'] is None else ar['rec_catch_percentage']+100*h['coverage_completion_pct']
  hm_sep=None if hr['rec_avg_separation'] is None or a['coverage_yards_per_target'] is None else hr['rec_avg_separation']+a['coverage_yards_per_target'];am_sep=None if ar['rec_avg_separation'] is None or h['coverage_yards_per_target'] is None else ar['rec_avg_separation']+h['coverage_yards_per_target']
  names += [f'matchup_yac_{suf}',f'matchup_catch_{suf}',f'matchup_sep_ypt_{suf}']; vals += [op(hm_yac,am_yac),op(hm_catch,am_catch),op(hm_sep,am_sep)]
 return names,vals
def matrix(rows,tk,xk,kind,var):
 data=[];names=None
 for r in rows:
  bn,bv=base.spread_features(r,tk) if kind=='spread' else base.total_features(r,tk);xn,xv=extras(r,kind,var,xk)
  if names is None:names=bn+xn
  data.append([np.nan if z is None else float(z) for z in bv+xv])
 return names,np.asarray(data,float)
def select(tr,kind,var):
 fit,val=base.inner_split(tr);yf=base.target_array(fit,kind);yv=base.target_array(val,kind);cs=[]
 for tk in base.K_GRID:
  for xk in KGRID:
   n,Xf=matrix(fit,tk,xk,kind,var);_,Xv=matrix(val,tk,xk,kind,var);prep=base.fit_preprocessor(Xf);Xfz=base.transform(Xf,prep);Xvz=base.transform(Xv,prep)
   for lam in base.LAMBDA_GRID:
    mo=base.ridge_fit(Xfz,yf,lam);p=base.predict(mo,Xvz);cs.append({'team_k':tk,'feature_k':xk,'lambda':lam,'mae':base.mae(yv,p),'rmse':base.rmse(yv,p)})
 cs.sort(key=lambda x:(x['mae'],x['rmse'],x['lambda']));return cs[0],cs[:10]
def fitp(tr,te,kind,var,p):
 names,X=matrix(tr,p['team_k'],p['feature_k'],kind,var);_,Z=matrix(te,p['team_k'],p['feature_k'],kind,var);prep=base.fit_preprocessor(X);mo=base.ridge_fit(base.transform(X,prep),base.target_array(tr,kind),p['lambda']);pr=base.predict(mo,base.transform(Z,prep));return pr,{n:float(v) for n,v in zip(names,mo[1])}
def met(rows,p,kind):
 y=base.target_array(rows,kind);return {'n':len(rows),'mae':round(base.mae(y,p),4),'rmse':round(base.rmse(y,p),4),'bias':round(base.bias(y,p),4),'market_reference_mae':round(base.market_mae(rows,kind),4),'edge_grading':base.grading(rows,p,kind)}
def agg(fs):
 n=sum(x['n'] for x in fs);return {'n':n,**{m:round(sum(x[m]*x['n'] for x in fs)/n,4) for m in ['mae','rmse','bias','market_reference_mae']}}
def main():
 OUT.mkdir(parents=True,exist_ok=True);ci,cl,cn=loadidx(COV,'cov');ni,nl,nn=loadidx(NGS,'ngs')
 if cl or nl:raise RuntimeError(f'leak coverage={cl} ngs={nl}')
 rows=attach(base.load_rows(),ci,ni);bf=defaultdict(list);vf=defaultdict(list);preds=[];coefs=[]
 summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'coverage_source_rows':cn,'ngs_source_rows':nn,'source_leakage_rows':cl+nl,'variants':{},'market_policy':'BENCHMARK_ONLY_NOT_MODEL_FEATURE','release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False}
 for yr in YEARS:
  tr=[r for r in rows if r['season']<yr];te=[r for r in rows if r['season']==yr]
  for kind in ['spread','total']:
   bp,_=base.select_params(tr,kind);b,_,_,_,_=base.fit_and_predict(tr,te,kind,bp['k'],bp['lambda']);bm=met(te,b,kind);bm['season']=yr;bf[kind].append(bm)
   for var in VARIANTS:
    best,top=select(tr,kind,var);p,c=fitp(tr,te,kind,var,best);m=met(te,p,kind);m.update({'season':yr,**best,'inner_top_candidates':top});vf[(var,kind)].append(m)
    for n,v in c.items():coefs.append({'season':yr,'kind':kind,'variant':var,**{k:best[k] for k in ['team_k','feature_k','lambda']},'feature':n,'standardized_coefficient':round(v,7)})
    for r,pv in zip(te,p):preds.append({'game_id':r['game_id'],'season':yr,'week':r['week'],'kind':kind,'variant':var,'actual':r['home_margin'] if kind=='spread' else r['game_total'],'prediction':round(float(pv),5),'market_reference':r['market_home_spread_reference'] if kind=='spread' else r['market_total_reference'],'release_state':'HOLD_RESEARCH_ONLY'})
 summary['baseline']={k:{'folds':bf[k],'aggregate':agg(bf[k])} for k in ['spread','total']}
 for var in VARIANTS:
  summary['variants'][var]={}
  for kind in ['spread','total']:
   fs=vf[(var,kind)];a=agg(fs);b=summary['baseline'][kind]['aggregate'];wins=sum(x['mae']<y['mae'] for x,y in zip(fs,bf[kind]));d=round(a['mae']-b['mae'],4);summary['variants'][var][kind]={'folds':fs,'aggregate':a,'mae_delta_vs_baseline':d,'seasons_with_lower_mae':wins,'historical_verdict':'EARNED_FURTHER_TESTING' if d<=-0.05 and wins>=2 else 'NO_PROMOTION','production_verdict':'HOLD_RESEARCH_ONLY'}
 for fn,rowsout in [('coverage_v1_predictions.csv',preds),('coverage_v1_coefficients.csv',coefs)]:
  with (OUT/fn).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rowsout[0]));w.writeheader();w.writerows(rowsout)
 (OUT/'coverage_v1_qa.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'verdicts':{v:{k:{'delta':summary['variants'][v][k]['mae_delta_vs_baseline'],'wins':summary['variants'][v][k]['seasons_with_lower_mae'],'verdict':summary['variants'][v][k]['historical_verdict']} for k in ['spread','total']} for v in VARIANTS}},indent=2))
if __name__=='__main__':main()
