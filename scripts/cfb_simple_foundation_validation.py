#!/usr/bin/env python3
"""Validate the simple CFB rebuild as a reusable foundation across seasons.

Design
------
1. Build one complete FBS schedule/result universe for 2021-2026.
2. Estimate each season's raw structural HFA separately.
3. For a target season, use only the median HFA from the three *prior* seasons.
4. Select ridge/recency/min-appearance settings using weekly walk-forward on
   2024 only.
5. Lock those settings and evaluate unchanged on 2025 and completed 2026 weeks.
6. Also evaluate the current Week-8 lead-shadow settings for comparison.

No market, SP+, Sagarin, RefMetrics, or future/post-target-week information is
used. Team state resets every season.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids

ALPHAS=(2.5,5.0,10.0,20.0,40.0,80.0)
HALF_LIVES=(21,35,56,None)
MIN_APPS=(3,4)
CURRENT_LEAD={'alpha':5.0,'halfLifeDays':21,'minTeamAppearances':4}
MIN_TRAIN_GAMES=100
MIN_COVERAGE=0.85


def week_start(dt: datetime) -> datetime:
    d=dt.astimezone(timezone.utc)
    base=(d-timedelta(days=d.weekday())).date()
    return datetime(base.year,base.month,base.day,tzinfo=timezone.utc)


def season_bounds(season:int):
    return datetime(season,8,1,tzinfo=timezone.utc),datetime(season+1,1,15,tzinfo=timezone.utc)


def load_seasons(first:int,last:int):
    out={}
    for season in range(first,last+1):
        start,end=season_bounds(season)
        out[season]=engine.fetch_completed_games(start,end)
    return out


def raw_hfa(games,season):
    _,end=season_bounds(season)
    model=engine.fit_model(games,end,alpha=5.0,half_life_days=None,min_team_appearances=4,fixed_hfa=None)
    return {'season':season,'rawGames':len(games),'eligibleGames':int(model['eligibleTrainingGames']),'homeMarginAdvantage':float(model['homeMarginAdvantage'])}


def structural_hfa(target:int,hfa_rows:dict[int,dict[str,Any]]):
    source=[target-3,target-2,target-1]
    vals=[float(hfa_rows[s]['homeMarginAdvantage']) for s in source]
    return float(statistics.median(vals)),source


def score_predictions(preds:list[dict[str,float]], potential:int):
    if not preds:
        return {'games':0,'potentialGames':potential,'coverage':0.0,'marginMae':None,'marginRmse':None,'marginBias':None,'totalMae':None,'totalRmse':None,'totalBias':None,'suAccuracyPct':None}
    me=[p['predMargin']-p['actualMargin'] for p in preds]
    te=[p['predTotal']-p['actualTotal'] for p in preds]
    su=[(p['predMargin']>0)==(p['actualMargin']>0) for p in preds if p['predMargin']!=0 and p['actualMargin']!=0]
    mean=lambda xs:sum(xs)/len(xs)
    return {
        'games':len(preds),'potentialGames':potential,'coverage':len(preds)/potential if potential else 0.0,
        'marginMae':mean([abs(x) for x in me]),'marginRmse':math.sqrt(mean([x*x for x in me])),'marginBias':mean(me),
        'totalMae':mean([abs(x) for x in te]),'totalRmse':math.sqrt(mean([x*x for x in te])),'totalBias':mean(te),
        'suAccuracyPct':100.0*sum(su)/len(su) if su else None,
    }


def evaluate_season(games:list[engine.Game],season:int,hfa:float,params:dict[str,Any]):
    by_week=defaultdict(list)
    for g in games:
        by_week[week_start(g.kickoff)].append(g)
    folds=[];all_preds=[];potential=0
    for ws in sorted(by_week):
        train=[g for g in games if g.kickoff < ws]
        test=by_week[ws]
        if len(train)<MIN_TRAIN_GAMES:
            continue
        try:
            model=engine.fit_model(train,ws,float(params['alpha']),params['halfLifeDays'],int(params['minTeamAppearances']),fixed_hfa=hfa)
        except Exception:
            continue
        preds=[]
        for g in test:
            potential+=1
            try:
                pr=engine.predict(model,g.away,g.home,g.neutral)
            except Exception:
                continue
            preds.append({
                'gameId':g.game_id,'predMargin':float(pr['projectedMarginHome']),'predTotal':float(pr['projectedTotal']),
                'actualMargin':float(g.home_score-g.away_score),'actualTotal':float(g.home_score+g.away_score),
            })
        all_preds.extend(preds)
        folds.append({'weekStart':engine.iso(ws),**score_predictions(preds,len(test))})
    return {'season':season,'structuralHomeMarginAdvantage':hfa,'params':params,'folds':folds,'aggregate':score_predictions(all_preds,potential)}


def choose_on_2024(games,hfa):
    candidates=[]
    for alpha in ALPHAS:
        for half in HALF_LIVES:
            for min_apps in MIN_APPS:
                params={'alpha':alpha,'halfLifeDays':half,'minTeamAppearances':min_apps}
                ev=evaluate_season(games,2024,hfa,params)
                a=ev['aggregate']
                if not a['games'] or a['coverage']<MIN_COVERAGE:
                    continue
                objective=(float(a['marginMae'])+float(a['totalMae']))/2.0
                candidates.append({'objective':objective,'params':params,'metrics':a})
    if not candidates:
        raise RuntimeError('no 2024 development candidate met coverage gate')
    candidates.sort(key=lambda r:(r['objective'],-r['metrics']['coverage'],r['params']['alpha'],999 if r['params']['halfLifeDays'] is None else r['params']['halfLifeDays'],r['params']['minTeamAppearances']))
    return candidates[0],candidates


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--as-of',default='2026-10-20T00:00:00-04:00')
    ap.add_argument('--output',default='cfb/validation/week-08-simple-foundation-validation.json')
    args=ap.parse_args()
    as_of=engine.parse_dt(args.as_of)

    seasons=load_seasons(2021,2026)
    # Strictly trim 2026 to pre-Week8 as-of even though the source itself is completed-games only.
    seasons[2026]=[g for g in seasons[2026] if g.kickoff < as_of]
    hfa_rows={s:raw_hfa(seasons[s],s) for s in range(2021,2026)}
    hfa24,src24=structural_hfa(2024,hfa_rows)
    hfa25,src25=structural_hfa(2025,hfa_rows)
    hfa26,src26=structural_hfa(2026,hfa_rows)

    best,candidates=choose_on_2024(seasons[2024],hfa24)
    locked=best['params']
    dev2024=evaluate_season(seasons[2024],2024,hfa24,locked)
    hold2025=evaluate_season(seasons[2025],2025,hfa25,locked)
    confirm2026=evaluate_season(seasons[2026],2026,hfa26,locked)

    current2024=evaluate_season(seasons[2024],2024,hfa24,CURRENT_LEAD)
    current2025=evaluate_season(seasons[2025],2025,hfa25,CURRENT_LEAD)
    current2026=evaluate_season(seasons[2026],2026,hfa26,CURRENT_LEAD)

    holdout_pass=(
        hold2025['aggregate']['coverage']>=MIN_COVERAGE and confirm2026['aggregate']['coverage']>=MIN_COVERAGE
        and hold2025['aggregate']['marginMae'] is not None and confirm2026['aggregate']['marginMae'] is not None
    )
    # This gate names a foundation candidate only; it does not promote canonical.
    foundation_status='FOUNDATION_CANDIDATE_READY' if holdout_pass else 'FOUNDATION_REVIEW'

    out={
        'schemaVersion':1,'league':'cfb','season':2026,'week':8,
        'role':'SIMPLE_REBUILD_FOUNDATION_VALIDATION','canonicalInfluence':False,'canonicalPromotionAuthorized':False,
        'asOf':engine.iso(as_of),
        'policy':{
            'developmentSeason':2024,'holdoutSeason':2025,'confirmationSeason':2026,
            'hyperparametersLockedAfter2024':True,'teamStateResetEverySeason':True,
            'structuralHfaAlwaysPriorSeasonsOnly':True,'marketDataUsed':False,'externalRatingsUsed':False,'postTargetWeekDataUsed':False,
        },
        'structuralHfaResearch':{
            'rawSeasonEstimates':[hfa_rows[s] for s in sorted(hfa_rows)],
            'for2024':{'value':hfa24,'sourceSeasons':src24},
            'for2025':{'value':hfa25,'sourceSeasons':src25},
            'for2026':{'value':hfa26,'sourceSeasons':src26},
        },
        'developmentSelection':{
            'candidateCount':len(candidates),'selected':best,
            'top10':candidates[:10],
        },
        'lockedDevelopmentCandidate':{
            'params':locked,'development2024':dev2024,'holdout2025':hold2025,'confirmation2026PreWeek8':confirm2026,
            'status':foundation_status,
        },
        'currentLeadShadowSettings':{
            'params':CURRENT_LEAD,'development2024':current2024,'holdout2025':current2025,'confirmation2026PreWeek8':current2026,
            'note':'Current lead settings were originally selected using 2026 pre-Week8 research, so 2024/2025 results are robustness context rather than clean parameter-selection holdouts.'
        },
        'warning':'Foundation validation only. Even a strong 2025/2026 result does not authorize replacing the frozen established CB model without explicit promotion review and prospective Week 8 evidence.'
    }
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({
        'status':foundation_status,'selectedParams':locked,
        'development2024':dev2024['aggregate'],'holdout2025':hold2025['aggregate'],'confirmation2026':confirm2026['aggregate'],
        'currentLead2025':current2025['aggregate'],'currentLead2026':current2026['aggregate'],
    },indent=2))


if __name__=='__main__':
    main()
