#!/usr/bin/env python3
"""Build a development-only Week 6 NFL readiness matrix.

This joins three immutable/prospective evidence layers without altering them:
1) locked pregame model snapshot,
2) current release-gate observations,
3) timestamped public BetMGM web-board capture.

It never converts a disagreement into a recommendation. Account-level price
execution, final inactives/roof/weather, and prospective validation remain gates.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

PRELOCK=Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
GATES=Path('nfl_data/prospective/2026_week6_gate_inputs.json')
CAPTURE=Path('nfl_data/prospective/market_captures/week6_betmgm_web_capture_20261017T225910Z.json')
OUT_JSON=Path('nfl_data/prospective/week6_readiness_matrix_20261017.json')
OUT_CSV=Path('nfl_data/prospective/week6_readiness_matrix_20261017.csv')

RESOLVED_WEATHER_PREFIXES=(
    'INDOOR_FIXED_ROOF',
    'COVERED_VENUE_NO_OUTDOOR_WEATHER_ADJUSTMENT_PLANNED',
)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    pre=load(PRELOCK); gates=load(GATES); cap=load(CAPTURE)
    snap_id=pre['manifest']['snapshot_id']
    cap_rows={r['game_id']:r for r in cap['rows']}
    if len(pre['rows'])!=13 or len(cap_rows)!=13:
        raise RuntimeError(f"Expected 13 games prelock={len(pre['rows'])} capture={len(cap_rows)}")
    if cap.get('games')!=13:
        raise RuntimeError('Direct-book capture game count mismatch')

    rows=[]
    for r in pre['rows']:
        gid=r['game_id']; g=gates['games'].get(gid); c=cap_rows.get(gid)
        if g is None or c is None:
            raise RuntimeError(f'Missing gate/capture for {gid}')
        if c.get('snapshot_id')!=snap_id:
            raise RuntimeError(f'Snapshot mismatch for {gid}')
        weather_state=g['weather_roof_state']
        weather_final=weather_state.startswith(RESOLVED_WEATHER_PREFIXES)
        account_verified=bool(c.get('user_account_execution_verified'))
        no_threshold=not bool(c.get('historical_edge_threshold_earned'))
        hard_qb=bool(r.get('hard_qb_state_break'))
        blockers=['NO_VALIDATED_EDGE_THRESHOLD'] if no_threshold else []
        if hard_qb: blockers.append('HARD_QB_STATE_BREAK')
        if not weather_final: blockers.append('FINAL_WEATHER_OR_ROOF_PENDING')
        if not account_verified: blockers.append('USER_ACCOUNT_EXECUTION_NOT_VERIFIED')
        rows.append({
            'game_id':gid,'away_team':r['away_team'],'home_team':r['home_team'],
            'snapshot_id':snap_id,
            'model_home_margin':float(r['final_research_home_margin']),
            'model_total':float(r['projected_total']),
            'betmgm_home_spread':c['home_spread'],'betmgm_home_spread_decimal_odds':c['home_spread_odds'],
            'spread_disagreement_vs_betmgm':c['spread_disagreement_vs_direct_book'],
            'betmgm_total':c['total'],'betmgm_over_decimal_odds':c['over_odds'],'betmgm_under_decimal_odds':c['under_odds'],
            'total_disagreement_vs_betmgm':c['total_disagreement_vs_direct_book'],
            'personnel_state':g['personnel_state'],'hard_qb_state_break':hard_qb,
            'weather_roof_state':weather_state,'weather_roof_final_for_release':weather_final,
            'public_book_capture_state':'CAPTURED_TIMESTAMPED_PUBLIC_WEB_BOARD',
            'user_account_execution_verified':account_verified,
            'historical_edge_threshold_earned':not no_threshold,
            'release_blockers':'|'.join(blockers),
            'recommendation':'HOLD_NO_VALIDATED_EDGE_THRESHOLD',
            'release_state':'HOLD_PROSPECTIVE_READINESS',
            'website_publish_allowed':False,
        })

    summary={
        'games':len(rows),
        'hard_qb_break_games':sum(r['hard_qb_state_break'] for r in rows),
        'weather_roof_final_games':sum(r['weather_roof_final_for_release'] for r in rows),
        'weather_roof_pending_games':sum(not r['weather_roof_final_for_release'] for r in rows),
        'public_book_captured_games':sum(r['public_book_capture_state'].startswith('CAPTURED') for r in rows),
        'user_account_execution_verified_games':sum(r['user_account_execution_verified'] for r in rows),
        'validated_edge_threshold_games':sum(r['historical_edge_threshold_earned'] for r in rows),
        'recommendation_release_games':0,
    }
    out={
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'snapshot_id':snap_id,
        'capture_created_at_utc':cap['capture_created_at_utc'],
        'capture_policy':cap['capture_policy'],
        'policy':'Readiness matrix only. Does not modify locked projection or create recommendations.',
        'summary':summary,
        'rows':rows,
        'promotion_policy':'Prospective outcomes must be accumulated across timestamped weeks before any betting threshold or alt-line logic can be promoted.',
        'website_publish_allowed':False,
    }
    OUT_JSON.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    with OUT_CSV.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    main()
