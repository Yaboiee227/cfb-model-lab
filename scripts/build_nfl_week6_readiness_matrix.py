#!/usr/bin/env python3
"""Build a development-only Week 6 NFL readiness matrix.

This joins four prospective evidence layers without altering the locked model:
1) immutable pregame model snapshot,
2) current release-gate observations,
3) timestamped public BetMGM web-board capture,
4) replacement-QB scenario diagnostics.

It never converts disagreement or QB stress diagnostics into a recommendation.
Final inactives, final outdoor weather/roof decisions, account-level executable
price verification, and prospective validation remain release gates.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

PRELOCK = Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
GATES = Path('nfl_data/prospective/2026_week6_gate_inputs.json')
CAPTURE = Path('nfl_data/prospective/market_captures/week6_betmgm_web_capture_20261017T225910Z.json')
QB_DIAG = Path('nfl_data/prospective/week6_qb_scenario_diagnostics.json')
OUT_JSON = Path('nfl_data/prospective/week6_readiness_matrix_20261017.json')
OUT_CSV = Path('nfl_data/prospective/week6_readiness_matrix_20261017.csv')

RESOLVED_WEATHER_PREFIXES = (
    'INDOOR_FIXED_ROOF',
    'COVERED_VENUE_NO_OUTDOOR_WEATHER_ADJUSTMENT_PLANNED',
)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def bool_starts(value, prefix):
    return str(value or '').startswith(prefix)


def main():
    pre = load(PRELOCK)
    gates = load(GATES)
    cap = load(CAPTURE)
    qb_diag = load(QB_DIAG)

    snap_id = pre['manifest']['snapshot_id']
    cap_rows = {r['game_id']: r for r in cap['rows']}
    qb_rows = {r['game_id']: r for r in qb_diag.get('rows', [])}

    if len(pre['rows']) != 13 or len(cap_rows) != 13:
        raise RuntimeError(f"Expected 13 games prelock={len(pre['rows'])} capture={len(cap_rows)}")
    if cap.get('games') != 13:
        raise RuntimeError('Direct-book capture game count mismatch')
    if qb_diag.get('release_state') != 'HOLD_RESEARCH_ONLY':
        raise RuntimeError('QB scenario layer is not research-only')
    if qb_diag.get('website_publish_allowed') is not False:
        raise RuntimeError('QB scenario layer unexpectedly permits website publication')

    rows = []
    for r in pre['rows']:
        gid = r['game_id']
        g = gates['games'].get(gid)
        c = cap_rows.get(gid)
        if g is None or c is None:
            raise RuntimeError(f'Missing gate/capture for {gid}')
        if c.get('snapshot_id') != snap_id:
            raise RuntimeError(f'Snapshot mismatch for {gid}')

        weather_state = g['weather_roof_state']
        weather_final = weather_state.startswith(RESOLVED_WEATHER_PREFIXES)
        weather_checked = (
            'FORECAST_CHECKED' in weather_state
            or weather_final
            or 'TBD_OFFICIAL' in weather_state
            or 'ROOF_DECISION_PENDING' in weather_state
        )
        elevated_weather = ('ELEVATED_WIND' in weather_state or 'MODERATE_WIND' in weather_state)

        inactive_state = g.get('final_inactives_state', 'UNKNOWN')
        final_inactives_resolved = bool_starts(inactive_state, 'FINAL_')
        final_status_report_available = 'FINAL_STATUS_REPORT_AVAILABLE' in g.get('personnel_state', '')

        account_verified = bool(c.get('user_account_execution_verified'))
        public_book_captured = bool_starts(g.get('execution_price_state'), 'PUBLIC_BOOK_CAPTURED')
        no_threshold = not bool(c.get('historical_edge_threshold_earned'))
        hard_qb = bool(r.get('hard_qb_state_break'))

        q = qb_rows.get(gid)
        qb_profile_resolved = bool(q and str(q.get('scenario_state', '')).startswith('PASS_'))
        qb_operational_adjustment = None if q is None else q.get('operational_point_adjustment')
        if q is not None and qb_operational_adjustment != 0.0:
            raise RuntimeError(f'QB diagnostic attempted operational adjustment for {gid}: {qb_operational_adjustment}')

        blockers = ['NO_VALIDATED_EDGE_THRESHOLD'] if no_threshold else []
        if hard_qb:
            blockers.append('HARD_QB_STATE_BREAK')
        if not final_inactives_resolved:
            blockers.append('FINAL_INACTIVES_PENDING')
        if not weather_final:
            blockers.append('FINAL_WEATHER_OR_ROOF_PENDING')
        if not public_book_captured:
            blockers.append('PUBLIC_BOOK_PRICE_NOT_CAPTURED')
        if not account_verified:
            blockers.append('USER_ACCOUNT_EXECUTION_NOT_VERIFIED')

        rows.append({
            'game_id': gid,
            'away_team': r['away_team'],
            'home_team': r['home_team'],
            'snapshot_id': snap_id,
            'model_home_margin': float(r['final_research_home_margin']),
            'model_total': float(r['projected_total']),
            'betmgm_home_spread': c['home_spread'],
            'betmgm_home_spread_decimal_odds': c['home_spread_odds'],
            'spread_disagreement_vs_betmgm': c['spread_disagreement_vs_direct_book'],
            'betmgm_total': c['total'],
            'betmgm_over_decimal_odds': c['over_odds'],
            'betmgm_under_decimal_odds': c['under_odds'],
            'total_disagreement_vs_betmgm': c['total_disagreement_vs_direct_book'],
            'personnel_state': g['personnel_state'],
            'official_final_status_report_available': final_status_report_available,
            'final_inactives_state': inactive_state,
            'final_inactives_resolved': final_inactives_resolved,
            'hard_qb_state_break': hard_qb,
            'qb_scenario_profile_resolved': qb_profile_resolved,
            'qb_scenario_state': None if q is None else q.get('scenario_state'),
            'qb_expected_starter': None if q is None else q.get('expected_starter'),
            'qb_profile_source': None if q is None else q.get('expected_starter_profile_source'),
            'qb_full_extrapolation_stress_home_margin': None if q is None else q.get('full_extrapolation_stress_home_margin'),
            'qb_operational_point_adjustment': qb_operational_adjustment,
            'qb_scenario_release_state': None if q is None else q.get('release_state'),
            'weather_roof_state': weather_state,
            'weather_forecast_or_roof_status_checked': weather_checked,
            'weather_elevated_uncertainty': elevated_weather,
            'weather_roof_final_for_release': weather_final,
            'public_book_capture_state': 'CAPTURED_TIMESTAMPED_PUBLIC_WEB_BOARD' if public_book_captured else 'NOT_CAPTURED',
            'execution_price_state': g.get('execution_price_state'),
            'user_account_execution_verified': account_verified,
            'historical_edge_threshold_earned': not no_threshold,
            'release_blockers': '|'.join(blockers),
            'recommendation': 'HOLD_NO_VALIDATED_EDGE_THRESHOLD',
            'release_state': 'HOLD_PROSPECTIVE_READINESS',
            'website_publish_allowed': False,
        })

    summary = {
        'games': len(rows),
        'official_final_status_report_available_games': sum(r['official_final_status_report_available'] for r in rows),
        'final_inactives_resolved_games': sum(r['final_inactives_resolved'] for r in rows),
        'hard_qb_break_games': sum(r['hard_qb_state_break'] for r in rows),
        'qb_scenario_profile_resolved_games': sum(r['qb_scenario_profile_resolved'] for r in rows),
        'qb_operational_adjustment_games': sum((r['qb_operational_point_adjustment'] or 0) != 0 for r in rows),
        'weather_forecast_or_roof_checked_games': sum(r['weather_forecast_or_roof_status_checked'] for r in rows),
        'weather_elevated_uncertainty_games': sum(r['weather_elevated_uncertainty'] for r in rows),
        'weather_roof_final_games': sum(r['weather_roof_final_for_release'] for r in rows),
        'weather_roof_pending_games': sum(not r['weather_roof_final_for_release'] for r in rows),
        'public_book_captured_games': sum(r['public_book_capture_state'].startswith('CAPTURED') for r in rows),
        'user_account_execution_verified_games': sum(r['user_account_execution_verified'] for r in rows),
        'validated_edge_threshold_games': sum(r['historical_edge_threshold_earned'] for r in rows),
        'recommendation_release_games': 0,
    }

    out = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'snapshot_id': snap_id,
        'capture_created_at_utc': cap['capture_created_at_utc'],
        'capture_policy': cap['capture_policy'],
        'gate_checked_at_utc': gates.get('checked_at_utc'),
        'qb_diagnostic_created_at_utc': qb_diag.get('created_at_utc'),
        'policy': 'Readiness matrix only. Does not modify locked projection or create recommendations.',
        'summary': summary,
        'rows': rows,
        'promotion_policy': 'Prospective outcomes must be accumulated across timestamped weeks before any betting threshold or alt-line logic can be promoted.',
        'website_publish_allowed': False,
    }

    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    with OUT_CSV.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
