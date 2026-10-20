#!/usr/bin/env python3
"""Leakage-safe isolated feature-family validation for the CFB rebuild.

The simple rebuild score/margin estimates remain the baseline. Candidate
families add one logically related set of pregame features at a time. For every
unseen 2026 week, ridge strength is selected only on the immediately preceding
2026 week using 2025 + earlier-2026 training rows, then refit and evaluated on
the unseen week.

This is a research/ablation tool. A family can become *challenger eligible* but
never canonical from this script alone.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import cfb_rich_challenger as rich
import cfb_shadow_engine as engine
from cfb_multiseason_walkforward import build_season_rows, estimate_prior_only_hfa
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids

ALPHAS = (0.1, 1.0, 10.0, 100.0)

# Feature order from cfb_rich_challenger.FEATURE_NAMES.
# Index 0 = simple margin base, index 1 = simple total base.
FEATURE_FAMILIES = {
    "efficiency": (2, 3, 4),                       # YPP, pass YPA, rush YPA
    "drive_control": (5, 6, 7),                   # 3D, turnover control, first-down rate
    "discipline": (8,),                            # penalty yards/play discipline
    "tempo_possession": (9, 10),                  # combined play volume, possession matchup
    "recent_rest": (11, 12),                      # recent margin, rest differential
}

MIN_PRIOR_ROWS = 150
MIN_VALID_ROWS = 10
MIN_TEST_ROWS = 10


def metrics(pred, actual):
    p=np.asarray(pred,dtype=float); y=np.asarray(actual,dtype=float)
    if len(y)==0:
        return {"games":0,"mae":None,"rmse":None,"bias":None}
    e=p-y
    return {"games":int(len(y)),"mae":float(np.mean(np.abs(e))),"rmse":float(np.sqrt(np.mean(e**2))),"bias":float(np.mean(e))}


def fit_candidate(rows: list[dict[str, Any]], indices: tuple[int,...], target: str, alpha: float):
    return rich.ridge_fit(rows, indices, target, alpha)


def choose_alpha(train: list[dict[str,Any]], valid: list[dict[str,Any]], indices: tuple[int,...], target: str):
    best=None
    for alpha in ALPHAS:
        model=fit_candidate(train,indices,target,alpha)
        pred=rich.ridge_predict(model,valid)
        ev=metrics(pred,[r[target] for r in valid])
        cand=(float(ev['mae']),float(ev['rmse']),alpha,ev)
        if best is None or cand[:3] < best[:3]:
            best=cand
    return best


def family_indices(target: str, family: str) -> tuple[int,...]:
    base=0 if target=='margin' else 1
    return (base,)+FEATURE_FAMILIES[family]


def evaluate(prior_rows: list[dict[str,Any]], current_rows: list[dict[str,Any]]) -> dict[str,Any]:
    by_week=defaultdict(list)
    for r in current_rows:
        by_week[r['weekStart']].append(r)
    weeks=sorted(by_week)

    families={name:{"margin":[],"total":[],"folds":[]} for name in FEATURE_FAMILIES}
    baseline={"marginPred":[],"totalPred":[],"marginActual":[],"totalActual":[],"folds":[]}

    for idx in range(1,len(weeks)):
        test_week=weeks[idx]; prev_week=weeks[idx-1]
        earlier=set(weeks[:idx])
        earlier_current=[r for r in current_rows if r['weekStart'] in earlier]
        all_training=list(prior_rows)+earlier_current
        inner_valid=list(by_week[prev_week])
        valid_ids={id(r) for r in inner_valid}
        inner_train=[r for r in all_training if id(r) not in valid_ids]
        test=list(by_week[test_week])
        if len(inner_train)<MIN_PRIOR_ROWS or len(inner_valid)<MIN_VALID_ROWS or len(test)<MIN_TEST_ROWS:
            continue

        actual_m=[float(r['margin']) for r in test]
        actual_t=[float(r['total']) for r in test]
        base_m=[float(r['x'][0]) for r in test]
        base_t=[float(r['x'][1]) for r in test]
        baseline['marginPred']+=base_m; baseline['totalPred']+=base_t
        baseline['marginActual']+=actual_m; baseline['totalActual']+=actual_t
        baseline['folds'].append({
            'testWeekStart':test_week,
            'margin':metrics(base_m,actual_m),
            'total':metrics(base_t,actual_t),
        })

        for name in FEATURE_FAMILIES:
            im=family_indices('margin',name); it=family_indices('total',name)
            bm=choose_alpha(inner_train,inner_valid,im,'margin')
            bt=choose_alpha(inner_train,inner_valid,it,'total')
            mm=fit_candidate(all_training,im,'margin',float(bm[2]))
            mt=fit_candidate(all_training,it,'total',float(bt[2]))
            pm=[float(x) for x in rich.ridge_predict(mm,test)]
            pt=[float(x) for x in rich.ridge_predict(mt,test)]
            families[name]['margin']+=pm; families[name]['total']+=pt
            families[name]['folds'].append({
                'testWeekStart':test_week,
                'selectedMarginAlpha':bm[2],
                'selectedTotalAlpha':bt[2],
                'margin':metrics(pm,actual_m),
                'total':metrics(pt,actual_t),
            })

    base_m=metrics(baseline['marginPred'],baseline['marginActual'])
    base_t=metrics(baseline['totalPred'],baseline['totalActual'])
    results={}
    for name,data in families.items():
        fm=metrics(data['margin'],baseline['marginActual'])
        ft=metrics(data['total'],baseline['totalActual'])
        md=float(fm['mae'])-float(base_m['mae']) if fm['mae'] is not None else None
        td=float(ft['mae'])-float(base_t['mae']) if ft['mae'] is not None else None
        margin_fold_deltas=[]; total_fold_deltas=[]
        for bfold,ffold in zip(baseline['folds'],data['folds']):
            margin_fold_deltas.append(float(ffold['margin']['mae'])-float(bfold['margin']['mae']))
            total_fold_deltas.append(float(ffold['total']['mae'])-float(bfold['total']['mae']))
        results[name]={
            'features':[rich.FEATURE_NAMES[i] for i in FEATURE_FAMILIES[name]],
            'margin':fm,'total':ft,
            'marginMaeDeltaVsSimple':md,
            'totalMaeDeltaVsSimple':td,
            'marginFoldDeltas':margin_fold_deltas,
            'totalFoldDeltas':total_fold_deltas,
            'marginImprovedFolds':sum(x<0 for x in margin_fold_deltas),
            'totalImprovedFolds':sum(x<0 for x in total_fold_deltas),
            'folds':data['folds'],
        }

    # Research gate per target: >=0.50 aggregate MAE improvement, improves >=2/3
    # folds, and no unseen fold degrades by more than 0.75.
    eligible=[]
    for name,r in results.items():
        margin_ok=(
            r['marginMaeDeltaVsSimple'] is not None and r['marginMaeDeltaVsSimple']<=-0.50
            and r['marginImprovedFolds']>=2
            and max(r['marginFoldDeltas'],default=99)<=0.75
        )
        total_ok=(
            r['totalMaeDeltaVsSimple'] is not None and r['totalMaeDeltaVsSimple']<=-0.50
            and r['totalImprovedFolds']>=2
            and max(r['totalFoldDeltas'],default=99)<=0.75
        )
        r['marginChallengerEligible']=margin_ok
        r['totalChallengerEligible']=total_ok
        if margin_ok or total_ok:
            eligible.append({'family':name,'margin':margin_ok,'total':total_ok})

    return {
        'foldCount':len(baseline['folds']),
        'games':len(baseline['marginActual']),
        'simpleBaseline':{'margin':base_m,'total':base_t,'folds':baseline['folds']},
        'families':results,
        'challengerEligibleFamilies':eligible,
        'gateRule':'Per target: improve aggregate MAE by >=0.50, improve at least 2 unseen folds, and no unseen fold may degrade by >0.75. Eligibility means isolated shadow research only, never canonical promotion.',
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--as-of',default='2026-10-20T00:00:00-04:00')
    ap.add_argument('--shadow',default='cfb/shadow/week-08-tuesday.json')
    ap.add_argument('--output',default='cfb/validation/week-08-feature-family-validation.json')
    args=ap.parse_args()
    as_of=engine.parse_dt(args.as_of)
    shadow=json.loads(Path(args.shadow).read_text())
    hfa26=float(shadow['fit']['structuralHomeMarginAdvantage'])
    hfa25,hfa25src=estimate_prior_only_hfa((2022,2023,2024),alpha=5.0,min_apps=4)
    rows25,meta25=build_season_rows(2025,engine.parse_dt('2026-01-15T00:00:00Z'),hfa25)
    rows26,meta26=build_season_rows(2026,as_of,hfa26)
    ev=evaluate(rows25,rows26)
    out={
        'schemaVersion':1,'league':'cfb','season':2026,'week':8,
        'role':'ISOLATED_FEATURE_FAMILY_RESEARCH','canonicalInfluence':False,
        'asOf':engine.iso(as_of),
        'policy':{'seasonReset':True,'marketDataUsed':False,'externalRatingsUsed':False,'sameWeekLeakagePrevented':True,'familyIsolation':True},
        'hfa':{'2025':hfa25,'2025DerivedFrom':[2022,2023,2024],'2025SeasonEstimates':hfa25src,'2026':hfa26},
        'dataQuality':{'season2025':meta25,'season2026':meta26},
        'validation':ev,
        'warning':'Research only. Any eligible family must still be prospectively shadowed on frozen Week 8+ games before explicit canonical promotion review.'
    }
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'folds':ev['foldCount'],'games':ev['games'],'eligible':ev['challengerEligibleFamilies'],'ranking':{k:{'marginDelta':v['marginMaeDeltaVsSimple'],'totalDelta':v['totalMaeDeltaVsSimple']} for k,v in ev['families'].items()}},indent=2))


if __name__=='__main__':
    main()
