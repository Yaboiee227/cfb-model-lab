#!/usr/bin/env python3
"""Walk-forward validation for NFL injury/personnel burden candidates.

Tests injury families against both the frozen core football baseline and the
stronger baseline+coverage candidate. Injury rows are target-week pregame state,
not lagged performance, so no cross-week blending is applied here.
"""
from __future__ import annotations
import csv,json,sys
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_ngs_team_v1 as ngs
import validate_nfl_ngs_team_v1_aliasfix  # canonical NGS aliases
import validate_nfl_coverage_v1 as cov

IN=Path('nfl_data/historical/team_week_injury_personnel_2022_2025.csv');OUT=Path('nfl_data/validation')
YEARS=[2023,2024,2025]
FAMILIES={
 'overall':['injured_count','out_count','doubtful_count','questionable_count','snap_weighted_burden','known_importance_share','high_snap_severe_count'],
 'offense':['qb_count','ol_count','skill_count','qb_weighted_burden','ol_weighted_burden','skill_weighted_burden'],
 'defense':['front7_count','db_count','front7_weighted_burden','db_weighted_burden'],
 'weighted_groups':['qb_weighted_burden','ol_weighted_burden','skill_weighted_burden','front7_weighted_burden','db_weighted_burden','other_weighted_burden'],
}
FAMILIES['all_injury']=FAMILIES['overall']+FAMILIES['weighted_groups']

def tf(v):return base.to_float(v)
def loadidx():
 with IN.open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
 idx={};quality=defaultdict(int)
 for r in rows:
  k=(int(float(r['season'])),int(float(r['target_week'])),r['team']);idx[k]=r;quality[r.get('report_quality','UNKNOWN')]+=1
 return idx,dict(quality),len(rows)
def attach(rows,idx):
 out=[];miss=[]
 for r in rows:
  h=idx.get((r['season'],r['week'],r['home_team']));a=idx.get((r['season'],r['week'],r['away_team']))
  if h is None or a is None:miss.append(r['game_id']);continue
  x=dict(r)
  for side,row in [('home',h),('away',a)]:
   for k,v in row.items():
    if k not in {'season','target_week','team','release_state'}:x[f'{side}_inj_{k}']=v
  out.append(x)
 if miss:raise RuntimeError(f'missing injury snapshots {len(miss)} first={miss[:5]}')
 return out
def injury_features(r,kind,fam):
 ms=FAMILIES[fam];op=base.diff if kind=='spread' else base.summ;suf='diff' if kind=='spread' else 'sum';h=[tf(r.get(f'home_inj_{m}')) for m in ms];a=[tf(r.get(f'away_inj_{m}')) for m in ms]
 return [f'inj_{m}_{suf}' for m in ms],[op(x,y) for x,y in zip(h,a)]
def matrix(rows,team_k,kind,fam,with_coverage=False,coverage_k=1.0):
 names=None;data=[]
 for r in rows:
  bn,bv=base.spread_features(r,team_k) if kind=='spread' else base.total_features(r,team_k)
  en,ev=injury_features(r,kind,fam)
  if with_coverage:
   cn,cv=cov.extras(r,kind,'coverage',coverage_k);n=bn+cn+en;v=bv+cv+ev
  else:n=bn+en;v=bv+ev
  if names is None:names=n
  data.append([np.nan if z is None else float(z) for z in v])
 return names,np.asarray(data,float)
def select(tr,kind,fam,with_coverage=False,coverage_k=1.0):
 fit,val=base.inner_split(tr);yf=base.target_array(fit,kind);yv=base.target_array(val,kind);cs=[]
 for tk in base.K_GRID:
  _,X=matrix(fit,tk,kind,fam,with_coverage,coverage_k);_,Z=matrix(val,tk,kind,fam,with_coverage,coverage_k);prep=base.fit_preprocessor(X);X=base.transform(X,prep);Z=base.transform(Z,prep)
  for lam in base.LAMBDA_GRID:
   mo=base.ridge_fit(X,yf,lam);p=base.predict(mo,Z);cs.append({'team_k':tk,'lambda':lam,'mae':base.mae(yv,p),'rmse':base.rmse(yv,p)})
 cs.sort(key=lambda x:(x['mae'],x['rmse'],x['lambda']));return cs[0],cs[:10]
def fitp(tr,te,kind,fam,p,with_coverage=False,coverage_k=1.0):
 names,X=matrix(tr,p['team_k'],kind,fam,with_coverage,coverage_k);_,Z=matrix(te,p['team_k'],kind,fam,with_coverage,coverage_k);prep=base.fit_preprocessor(X);mo=base.ridge_fit(base.transform(X,prep),base.target_array(tr,kind),p['lambda']);pr=base.predict(mo,base.transform(Z,prep));return pr,{n:float(v) for n,v in zip(names,mo[1])}
def met(rows,p,kind):
 y=base.target_array(rows,kind);return {'n':len(rows),'mae':round(base.mae(y,p),4),'rmse':round(base.rmse(y,p),4),'bias':round(base.bias(y,p),4),'market_reference_mae':round(base.market_mae(rows,kind),4)}
def agg(fs):
 n=sum(x['n'] for x in fs);return {'n':n,**{m:round(sum(x[m]*x['n'] for x in fs)/n,4) for m in ['mae','rmse','bias','market_reference_mae']}}
def main():
 OUT.mkdir(parents=True,exist_ok=True);ii,quality,nrows=loadidx();base_rows=base.load_rows();ni,nl,_=ngs.load_index();ci,cl,_=cov.loadidx(cov.COV,'cov')
 if nl+cl:raise RuntimeError(f'coverage source leak ngs={nl} cov={cl}')
 rows=attach(cov.attach(base_rows,ci,ni),ii);bf=defaultdict(list);cf=defaultdict(list);vf=defaultdict(list);preds=[];coefs=[]
 summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_rows':nrows,'report_quality_counts':quality,'variants':{},'market_policy':'BENCHMARK_ONLY_NOT_MODEL_FEATURE','release_state':'HOLD_RESEARCH_ONLY','website_publish_allowed':False,'quality_note':'2025 final-week injury reports lack revision timestamps; 2023-24 validation folds use exact pre-kickoff revisions.'}
 for yr in YEARS:
  tr=[r for r in rows if r['season']<yr];te=[r for r in rows if r['season']==yr]
  for kind in ['spread','total']:
   bp,_=base.select_params(tr,kind);b,_,_,_,_=base.fit_and_predict(tr,te,kind,bp['k'],bp['lambda']);bm=met(te,b,kind);bm['season']=yr;bf[kind].append(bm)
   # Coverage reference itself, tuned under the same available training data.
   cp,_=cov.select(tr,kind,'coverage');c,c_coef=cov.fitp(tr,te,kind,'coverage',cp);cm=met(te,c,kind);cm.update({'season':yr,**cp});cf[kind].append(cm)
   for fam in FAMILIES:
    for ref,withcov,ck in [('baseline',False,1.0),('coverage',True,cp['feature_k'])]:
     best,top=select(tr,kind,fam,withcov,ck);p,cfs=fitp(tr,te,kind,fam,best,withcov,ck);m=met(te,p,kind);m.update({'season':yr,**best,'inner_top_candidates':top});vf[(fam,kind,ref)].append(m)
     for n,v in cfs.items():coefs.append({'season':yr,'kind':kind,'variant':fam,'reference':ref,'feature':n,'standardized_coefficient':round(v,7),'team_k':best['team_k'],'lambda':best['lambda']})
     for r,pv in zip(te,p):preds.append({'game_id':r['game_id'],'season':yr,'week':r['week'],'kind':kind,'variant':fam,'reference':ref,'actual':r['home_margin'] if kind=='spread' else r['game_total'],'prediction':round(float(pv),5),'release_state':'HOLD_RESEARCH_ONLY'})
 summary['baseline']={k:{'folds':bf[k],'aggregate':agg(bf[k])} for k in ['spread','total']};summary['coverage_reference']={k:{'folds':cf[k],'aggregate':agg(cf[k])} for k in ['spread','total']}
 for fam in FAMILIES:
  summary['variants'][fam]={}
  for kind in ['spread','total']:
   summary['variants'][fam][kind]={}
   for ref,refs in [('baseline',bf[kind]),('coverage',cf[kind])]:
    fs=vf[(fam,kind,ref)];a=agg(fs);b=agg(refs);wins=sum(x['mae']<y['mae'] for x,y in zip(fs,refs));d=round(a['mae']-b['mae'],4);summary['variants'][fam][kind][f'vs_{ref}']={'folds':fs,'aggregate':a,'mae_delta_vs_reference':d,'seasons_with_lower_mae':wins,'historical_verdict':'EARNED_FURTHER_TESTING' if d<=-0.05 and wins>=2 else 'NO_PROMOTION','production_verdict':'HOLD_RESEARCH_ONLY'}
 for fn,rr in [('injury_personnel_v1_predictions.csv',preds),('injury_personnel_v1_coefficients.csv',coefs)]:
  with (OUT/fn).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 (OUT/'injury_personnel_v1_qa.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'verdicts':{fam:{kind:{ref:summary['variants'][fam][kind][ref]['mae_delta_vs_reference'] for ref in ['vs_baseline','vs_coverage']} for kind in ['spread','total']} for fam in FAMILIES}},indent=2))
if __name__=='__main__':main()
