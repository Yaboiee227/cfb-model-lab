#!/usr/bin/env python3
"""Generate Week 8 projections from the cleanly validated CFB foundation settings.

The parameter set is read from the 2024-development -> 2025-holdout -> 2026-
confirmation validation artifact. The generator does not retune on Week 8 and
never reads market, SP+, Sagarin, RefMetrics, or target-game results.

This remains a prospective FOUNDATION SHADOW. It is not the unrecoverable 0.9J
model and it is not canonical until an explicit promotion decision is made.
Stable source game IDs are preserved when supplied by the schedule state so
postgame research grading can match finals without name guessing.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def identity_fields(game):
    out={}
    for key in ('sourceGameId','gameDateET','neutralSite'):
        if key in game and game.get(key) is not None:
            out[key]=game[key]
    return out


def build(state_path: Path, validation_path: Path, as_of, start):
    state=json.loads(state_path.read_text(encoding='utf-8'))
    validation=json.loads(validation_path.read_text(encoding='utf-8'))
    locked=validation['lockedDevelopmentCandidate']
    if locked.get('status')!='FOUNDATION_CANDIDATE_READY':
        raise RuntimeError(f"foundation validation not ready: {locked.get('status')}")
    params=locked['params']
    hfa=float(validation['structuralHfaResearch']['for2026']['value'])
    confirm=locked['confirmation2026PreWeek8']['aggregate']
    sigma=float(confirm['marginRmse'])

    games=engine.fetch_completed_games(start,as_of)
    model=engine.fit_model(
        games,as_of,
        alpha=float(params['alpha']),
        half_life_days=params['halfLifeDays'],
        min_team_appearances=int(params['minTeamAppearances']),
        fixed_hfa=hfa,
    )

    rows=[]
    for g in state.get('games',[]):
        away=engine.canonical_school(g['awayTeam'])
        home=engine.canonical_school(g['homeTeam'])
        identity=identity_fields(g)
        try:
            pr=engine.predict(model,away,home,bool(g.get('neutralSite',False)))
            margin=float(pr['projectedMarginHome'])
            hwp=100.0*normal_cdf(margin/max(sigma,1e-9))
            rows.append({
                'gameId':g['gameId'],**identity,
                'awayTeam':g['awayTeam'],'homeTeam':g['homeTeam'],'kickoff':g['kickoff'],
                'status':'FOUNDATION_SHADOW_READY',
                **pr,
                'homeWinProbability':hwp,
                'projectedWinner':g['homeTeam'] if margin>0 else g['awayTeam'],
            })
        except Exception as exc:
            rows.append({
                'gameId':g['gameId'],**identity,
                'awayTeam':g['awayTeam'],'homeTeam':g['homeTeam'],'kickoff':g['kickoff'],
                'status':'FOUNDATION_SHADOW_REVIEW','error':str(exc)
            })

    return {
        'schemaVersion':2,'league':'cfb','season':state.get('season'),'week':state.get('week'),
        'modelId':'cfb-rebuild-foundation-v1-shadow',
        'role':'VALIDATED_FOUNDATION_PROSPECTIVE_SHADOW','canonicalInfluence':False,'canonicalPromotionAuthorized':False,
        'asOf':engine.iso(as_of),'trainingWindowStart':engine.iso(start),
        'trainingGames':len(games),'eligibleTrainingGames':int(model['eligibleTrainingGames']),
        'lockedParameters':params,
        'structuralHomeMarginAdvantage':hfa,
        'parameterSelection':{
            'developmentSeason':2024,'holdoutSeason':2025,'confirmationSeason':2026,
            'hyperparametersRetunedForWeek8':False,
            'validationSource':str(validation_path),
            'holdout2025':locked['holdout2025']['aggregate'],
            'confirmation2026PreWeek8':confirm,
        },
        'uncertainty':{'marginSigma':sigma,'source':'2026 pre-Week8 confirmation margin RMSE'},
        'source':{
            'provider':'ESPN public FBS teams + team schedules',
            'marketDataUsed':False,'externalRatingsUsed':False,'postKickoffDataUsed':False,
        },
        'games':rows,
        'warning':'Validated foundation prospective shadow only. This is not 0.9J and does not become canonical without explicit promotion review.'
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--state',default='cfb/pregame/week-08-tuesday-effective.json')
    ap.add_argument('--validation',default='cfb/validation/week-08-simple-foundation-validation.json')
    ap.add_argument('--as-of',default='2026-10-20T00:00:00-04:00')
    ap.add_argument('--start',default='2026-08-20T00:00:00-04:00')
    ap.add_argument('--output',default='cfb/shadow/week-08-tuesday-foundation.json')
    args=ap.parse_args()
    out=build(Path(args.state),Path(args.validation),engine.parse_dt(args.as_of),engine.parse_dt(args.start))
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({
        'modelId':out['modelId'],'lockedParameters':out['lockedParameters'],
        'holdout2025':out['parameterSelection']['holdout2025'],
        'confirmation2026':out['parameterSelection']['confirmation2026PreWeek8'],
        'games':[{k:g.get(k) for k in ('gameId','sourceGameId','projectedSpreadHome','projectedTotal','homeWinProbability','status')} for g in out['games']]
    },indent=2))


if __name__=='__main__':
    main()
