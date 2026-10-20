#!/usr/bin/env python3
"""Re-test isolated feature families against the locked validated foundation.

The original feature-family study used an earlier score-base configuration.
This study replaces only the causal score snapshot inside the feature builder
with the 2024-selected, 2025-held-out, 2026-confirmed foundation parameters.
All advanced metric construction and leakage controls remain unchanged.

A feature family must prove incremental value over this stronger base before it
remains eligible for prospective Week 8 shadowing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cfb_feature_family_validation as ff
import cfb_rich_challenger as rich
import cfb_shadow_engine as engine
from cfb_multiseason_walkforward import build_season_rows, estimate_prior_only_hfa
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids


def configured_snapshot_factory(params: dict[str, Any]):
    def configured_snapshot(history, boxes, as_of, structural_hfa):
        if len(history) < 80:
            return {"score": None, "metrics": {}}
        try:
            score = engine.fit_model(
                history,
                as_of,
                alpha=float(params["alpha"]),
                half_life_days=params["halfLifeDays"],
                min_team_appearances=int(params["minTeamAppearances"]),
                fixed_hfa=structural_hfa,
            )
        except Exception:
            score = None
        ratings = {metric: rich.metric_pair_fit(history, boxes, metric, alpha=10.0) for metric in rich.BOX_METRICS}
        return {"score": score, "metrics": ratings}
    return configured_snapshot


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--foundation-validation',default='cfb/validation/week-08-simple-foundation-validation.json')
    ap.add_argument('--as-of',default='2026-10-20T00:00:00-04:00')
    ap.add_argument('--output',default='cfb/validation/week-08-foundation-feature-family-validation.json')
    args=ap.parse_args()

    foundation=json.loads(Path(args.foundation_validation).read_text(encoding='utf-8'))
    locked=foundation['lockedDevelopmentCandidate']
    if locked.get('status')!='FOUNDATION_CANDIDATE_READY':
        raise RuntimeError(f"foundation not ready: {locked.get('status')}")
    params=locked['params']
    as_of=engine.parse_dt(args.as_of)

    original_snapshot=rich.build_snapshot
    rich.build_snapshot=configured_snapshot_factory(params)
    try:
        hfa25,hfa25src=estimate_prior_only_hfa((2022,2023,2024),alpha=5.0,min_apps=4)
        hfa26=float(foundation['structuralHfaResearch']['for2026']['value'])
        rows25,meta25=build_season_rows(2025,engine.parse_dt('2026-01-15T00:00:00Z'),hfa25)
        rows26,meta26=build_season_rows(2026,as_of,hfa26)
    finally:
        rich.build_snapshot=original_snapshot

    ev=ff.evaluate(rows25,rows26)
    out={
        'schemaVersion':1,'league':'cfb','season':2026,'week':8,
        'role':'FOUNDATION_INCREMENTAL_FEATURE_FAMILY_RESEARCH','canonicalInfluence':False,
        'asOf':engine.iso(as_of),
        'foundation':{
            'params':params,
            'selection':'2024 development only',
            'holdout2025':locked['holdout2025']['aggregate'],
            'confirmation2026PreWeek8':locked['confirmation2026PreWeek8']['aggregate'],
            'validationSource':args.foundation_validation,
        },
        'policy':{
            'seasonReset':True,'marketDataUsed':False,'externalRatingsUsed':False,
            'sameWeekLeakagePrevented':True,'familyIsolation':True,
            'foundationParamsRetunedForThisStudy':False,
        },
        'hfa':{
            '2025':hfa25,'2025DerivedFrom':[2022,2023,2024],'2025SeasonEstimates':hfa25src,
            '2026':hfa26,'2026DerivedFrom':[2023,2024,2025],
        },
        'dataQuality':{'season2025':meta25,'season2026':meta26},
        'validation':ev,
        'warning':'Incremental research against the validated foundation only. Eligibility allows prospective isolated shadowing, not canonical influence or family stacking.'
    }
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({
        'foundationParams':params,'folds':ev['foldCount'],'games':ev['games'],
        'eligible':ev['challengerEligibleFamilies'],
        'ranking':{k:{'marginDelta':v['marginMaeDeltaVsSimple'],'totalDelta':v['totalMaeDeltaVsSimple'],'marginEligible':v['marginChallengerEligible'],'totalEligible':v['totalChallengerEligible']} for k,v in ev['families'].items()}
    },indent=2))


if __name__=='__main__':
    main()
