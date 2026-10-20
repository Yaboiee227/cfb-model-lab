#!/usr/bin/env python3
"""Generate prospective Week 8 shadows for validated isolated margin families.

Only families marked marginChallengerEligible by the frozen feature-family
validation file are run. Totals remain the lead simple shadow because no totals
family passed. Historical 2025 rows teach coefficients only; target team state
and target features are built exclusively from 2026 pre-Week-8 information.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cfb_rich_challenger as rich
import cfb_shadow_engine as engine
from cfb_feature_family_validation import FEATURE_FAMILIES, ALPHAS, metrics
from cfb_multiseason_walkforward import build_season_rows, estimate_prior_only_hfa
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids


def choose_alpha(train: list[dict[str,Any]], valid: list[dict[str,Any]], indices: tuple[int,...]):
    candidates=[]
    for alpha in ALPHAS:
        model=rich.ridge_fit(train,indices,'margin',alpha)
        pred=rich.ridge_predict(model,valid)
        ev=metrics(pred,[r['margin'] for r in valid])
        candidates.append({'alpha':alpha,**ev})
    candidates.sort(key=lambda r:(r['mae'],r['rmse'],r['alpha']))
    return candidates[0],candidates


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--state',default='cfb/pregame/week-08-tuesday-effective.json')
    ap.add_argument('--simple',default='cfb/shadow/week-08-tuesday.json')
    ap.add_argument('--validation',default='cfb/validation/week-08-feature-family-validation.json')
    ap.add_argument('--as-of',default='2026-10-20T00:00:00-04:00')
    ap.add_argument('--output',default='cfb/shadow/week-08-tuesday-margin-families.json')
    args=ap.parse_args()

    as_of=engine.parse_dt(args.as_of)
    state=json.loads(Path(args.state).read_text())
    simple=json.loads(Path(args.simple).read_text())
    validation=json.loads(Path(args.validation).read_text())
    eligible=[x['family'] for x in validation['validation']['challengerEligibleFamilies'] if x.get('margin')]
    if not eligible:
        raise RuntimeError('no margin feature family is challenger-eligible')

    hfa26=float(simple['fit']['structuralHomeMarginAdvantage'])
    hfa25,_=estimate_prior_only_hfa((2022,2023,2024),alpha=5.0,min_apps=4)
    rows25,_=build_season_rows(2025,engine.parse_dt('2026-01-15T00:00:00Z'),hfa25)

    games26=engine.fetch_completed_games(engine.parse_dt('2026-08-20T00:00:00Z'),as_of)
    boxes26,failures=rich.fetch_boxes(games26)
    if len(boxes26)/max(1,len(games26)) < rich.MIN_SUMMARY_COVERAGE:
        raise RuntimeError(f'2026 box-score coverage insufficient: {len(boxes26)}/{len(games26)} failures={failures[:5]}')
    rows26,target_snapshot,team_history=rich.build_rows(games26,boxes26,hfa26)
    weeks=sorted({r['weekStart'] for r in rows26})
    if len(weeks)<2:
        raise RuntimeError('not enough 2026 weeks for pre-Week8 alpha selection')
    latest_week=weeks[-1]
    latest_valid=[r for r in rows26 if r['weekStart']==latest_week]
    earlier26=[r for r in rows26 if r['weekStart']!=latest_week]
    selection_train=list(rows25)+earlier26
    all_training=list(rows25)+list(rows26)

    simple_games={g['gameId']:g for g in simple['games']}
    state_games={g['gameId']:g for g in state['games']}
    family_models={}
    for family in eligible:
        indices=(0,)+FEATURE_FAMILIES[family]
        best,candidates=choose_alpha(selection_train,latest_valid,indices)
        final=rich.ridge_fit(all_training,indices,'margin',float(best['alpha']))
        family_models[family]={'indices':indices,'best':best,'candidates':candidates,'model':final}

    outputs=[]
    for gid,gs in state_games.items():
        target=engine.Game(gid,engine.parse_dt(gs['kickoff']),engine.canonical_school(gs['homeTeam']),engine.canonical_school(gs['awayTeam']),0.0,0.0,False)
        x=rich.feature_vector(target,target_snapshot,team_history)
        simple_game=simple_games.get(gid)
        if x is None or simple_game is None:
            outputs.append({'gameId':gid,'status':'FAMILY_SHADOW_REVIEW','error':'target features or simple reference unavailable'})
            continue
        total=float(simple_game['projectedTotal'])
        rows=[]
        for family in eligible:
            fm=family_models[family]
            margin=float(rich.ridge_predict(fm['model'],[{'x':x}])[0])
            home=(total+margin)/2.0;away=(total-margin)/2.0
            home=max(0.0,home);away=max(0.0,away);margin=home-away;adjusted_total=home+away
            sigma=float(fm['best'].get('rmse') or 15.0)
            hwp=100.0*0.5*(1.0+math.erf((margin/max(sigma,1e-6))/math.sqrt(2.0)))
            rows.append({
                'family':family,
                'features':[rich.FEATURE_NAMES[i] for i in FEATURE_FAMILIES[family]],
                'selectedAlpha':fm['best']['alpha'],
                'latestCompletedWeekValidation':{k:v for k,v in fm['best'].items() if k!='alpha'},
                'projectedMarginHome':margin,
                'projectedSpreadHome':-margin,
                'projectedTotal':adjusted_total,
                'projectedAwayPoints':away,
                'projectedHomePoints':home,
                'homeWinProbability':hwp,
                'projectedWinner':gs['homeTeam'] if margin>0 else gs['awayTeam'],
                'canonicalInfluence':False,
            })
        outputs.append({
            'gameId':gid,'awayTeam':gs['awayTeam'],'homeTeam':gs['homeTeam'],'kickoff':gs['kickoff'],
            'status':'PROSPECTIVE_MARGIN_FAMILY_SHADOWS_READY',
            'simpleReference':{
                'projectedMarginHome':float(simple_game['projectedMarginHome']),
                'projectedSpreadHome':float(simple_game['projectedSpreadHome']),
                'projectedTotal':float(simple_game['projectedTotal']),
            },
            'familyShadows':rows,
        })

    out={
        'schemaVersion':1,'league':'cfb','season':2026,'week':8,
        'role':'PROSPECTIVE_ISOLATED_MARGIN_FAMILY_SHADOWS','canonicalInfluence':False,
        'asOf':engine.iso(as_of),
        'eligibleFamilies':eligible,
        'totalPolicy':'No isolated total family passed the validation gate; all family shadows retain the lead simple shadow total.',
        'trainingPolicy':{
            'priorSeasonTeamStateCarryover':False,
            'coefficientHistory':'2025 causal feature rows',
            'currentTeamState':'2026 only',
            'alphaSelectionWeekStart':latest_week,
            'alphaSelectionUsesTargetWeek':False,
            'marketDataUsed':False,'externalRatingsUsed':False,'sameWeekResultLeakage':False,
        },
        'familyModels':{name:{
            'features':[rich.FEATURE_NAMES[i] for i in FEATURE_FAMILIES[name]],
            'indices':list(fm['indices']),
            'selectedAlpha':fm['best']['alpha'],
            'latestCompletedWeekValidation':{k:v for k,v in fm['best'].items() if k!='alpha'},
            'alphaCandidates':fm['candidates'],
        } for name,fm in family_models.items()},
        'games':outputs,
        'warning':'Prospective shadow only. These outputs must be frozen before kickoff and graded after results; they do not replace the canonical CB projection or the lead simple shadow.'
    }
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'families':eligible,'selectionWeek':latest_week,'games':[{'gameId':g['gameId'],'shadows':[{'family':s['family'],'spread':s['projectedSpreadHome'],'total':s['projectedTotal']} for s in g.get('familyShadows',[])]} for g in outputs]},indent=2))


if __name__=='__main__':
    main()
