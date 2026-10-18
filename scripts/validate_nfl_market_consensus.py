#!/usr/bin/env python3
"""Walk-forward validation for a separately labeled market-informed consensus layer.

The independent canonical model remains unchanged. This script tests whether a
simple predeclared convex blend of canonical projection and historical market
reference improves raw prediction error on later unseen seasons.

Weight selection is time ordered:
- 2024 test chooses weight using 2023 only.
- 2025 test chooses weight using 2023-2024 only.
- 2026 deployment weight is chosen from all 2023-2025 OOS history.

No recommendation/edge calibration is performed here.
"""
from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

SRC=Path('nfl_data/calibration/final_architecture_oos_predictions_2023_2025.csv')
OUT=Path('nfl_data/validation/market_consensus_walkforward.json')
OUT_MD=Path('nfl_data/validation/MARKET_CONSENSUS_WALKFORWARD.md')
WEIGHTS=[i/10 for i in range(11)]


def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None


def mae(vals): return sum(abs(a-p) for a,p in vals)/len(vals)
def rmse(vals): return math.sqrt(sum((a-p)**2 for a,p in vals)/len(vals))


def load():
    with SRC.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
    out=[]
    for r in rows:
        ah=num(r['actual_home_margin']); cm=num(r['pred_home_margin']); hs=num(r['market_home_spread_reference'])
        at=num(r['actual_total']); ct=num(r['pred_total']); mt=num(r['market_total_reference'])
        if None in (ah,cm,hs,at,ct,mt): continue
        out.append({'season':int(r['season']),'actual_margin':ah,'canonical_margin':cm,'market_margin':-hs,'actual_total':at,'canonical_total':ct,'market_total':mt})
    return out


def metric(rows,target,model_key,market_key,w):
    vals=[(r[target], w*r[model_key]+(1-w)*r[market_key]) for r in rows]
    return {'n':len(vals),'mae':mae(vals),'rmse':rmse(vals)}


def best_weight(train,target,model_key,market_key):
    scored=[]
    for w in WEIGHTS:
        m=metric(train,target,model_key,market_key,w)
        scored.append((m['mae'],m['rmse'],abs(w-0.5),w,m))
    scored.sort()
    return scored[0][3],scored[0][4]


def bootstrap_improvement(rows,target,baseline_key,blend_key,n=5000,seed=227):
    rng=random.Random(seed); diffs=[]; N=len(rows)
    per=[abs(r[target]-r[baseline_key])-abs(r[target]-r[blend_key]) for r in rows]
    for _ in range(n):
        diffs.append(sum(per[rng.randrange(N)] for __ in range(N))/N)
    diffs.sort()
    return {'mean':sum(per)/N,'ci95_low':diffs[int(.025*n)],'ci95_high':diffs[int(.975*n)-1]}


def run_side(rows,side):
    if side=='spread': target='actual_margin'; model='canonical_margin'; market='market_margin'
    else: target='actual_total'; model='canonical_total'; market='market_total'
    folds=[]
    for test,train_seasons in [(2024,[2023]),(2025,[2023,2024])]:
        train=[r for r in rows if r['season'] in train_seasons]; test_rows=[r for r in rows if r['season']==test]
        w,_=best_weight(train,target,model,market)
        blend_key=f'{side}_blend'
        eval_rows=[]
        for r in test_rows:
            q=dict(r);q[blend_key]=w*r[model]+(1-w)*r[market];eval_rows.append(q)
        b=metric(test_rows,target,model,model,1.0); m=metric(test_rows,target,market,market,1.0); c=metric(eval_rows,target,blend_key,blend_key,1.0)
        folds.append({'test_season':test,'training_seasons':train_seasons,'canonical_weight':w,'market_weight':1-w,'canonical':b,'market':m,'consensus':c,'improvement_vs_canonical_mae':b['mae']-c['mae'],'improvement_vs_market_mae':m['mae']-c['mae']})
    deploy_w,train_metric=best_weight(rows,target,model,market)
    eval_rows=[]
    for r in rows:
        q=dict(r);q[f'{side}_blend']=deploy_w*r[model]+(1-deploy_w)*r[market];eval_rows.append(q)
    canonical=metric(rows,target,model,model,1.0); market_m=metric(rows,target,market,market,1.0); consensus=metric(eval_rows,target,f'{side}_blend',f'{side}_blend',1.0)
    boot_can=bootstrap_improvement(eval_rows,target,model,f'{side}_blend',seed=227 if side=='spread' else 228)
    boot_mkt=bootstrap_improvement(eval_rows,target,market,f'{side}_blend',seed=327 if side=='spread' else 328)
    robust=(all(f['improvement_vs_canonical_mae']>0 and f['improvement_vs_market_mae']>=0 for f in folds)
            and 0.0<deploy_w<1.0 and boot_can['ci95_low']>0 and boot_mkt['ci95_low']>=0)
    return {'folds':folds,'deployment_2026_canonical_weight':deploy_w,'deployment_2026_market_weight':1-deploy_w,'all_2023_2025':{'canonical':canonical,'market':market_m,'consensus_at_deployment_weight':consensus},'paired_bootstrap_improvement_vs_canonical':boot_can,'paired_bootstrap_improvement_vs_market':boot_mkt,'robust_research_display_candidate':robust}


def main():
    rows=load()
    if len(rows)<800: raise RuntimeError(f'Expected roughly 816 complete rows, got {len(rows)}')
    spread=run_side(rows,'spread'); total=run_side(rows,'total')
    payload={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'rows':len(rows),'weight_grid':WEIGHTS,'policy':'Independent canonical remains unchanged. Consensus is market-informed and cannot be labeled independent, edge, recommendation or execution price.','spread':spread,'total':total,'recommendation_release_allowed':False}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    lines=['# NFL Market-Informed Consensus Walk-Forward Validation','',f"Rows: **{len(rows)}**",'','This tests a separate forecast layer only. It does not change the independent canonical model or authorize betting recommendations.','']
    for name,res in [('Spread',spread),('Total',total)]:
        lines += [f'## {name}','',f"2026 candidate weights: **{res['deployment_2026_canonical_weight']:.1f} canonical / {res['deployment_2026_market_weight']:.1f} market**",f"Robust research-display candidate: **{res['robust_research_display_candidate']}**",'', '| Test season | Canonical weight | Canonical MAE | Market MAE | Consensus MAE |','|---|---:|---:|---:|---:|']
        for f in res['folds']:
            lines.append(f"| {f['test_season']} | {f['canonical_weight']:.1f} | {f['canonical']['mae']:.4f} | {f['market']['mae']:.4f} | {f['consensus']['mae']:.4f} |")
        lines += ['',f"All-history canonical MAE: **{res['all_2023_2025']['canonical']['mae']:.4f}**",f"All-history market MAE: **{res['all_2023_2025']['market']['mae']:.4f}**",f"All-history consensus MAE at 2026 deployment weight: **{res['all_2023_2025']['consensus_at_deployment_weight']['mae']:.4f}**",'']
    OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'spread':spread['robust_research_display_candidate'],'spread_weight':spread['deployment_2026_canonical_weight'],'total':total['robust_research_display_candidate'],'total_weight':total['deployment_2026_canonical_weight']},indent=2))


if __name__=='__main__': main()
