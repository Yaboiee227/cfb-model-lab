#!/usr/bin/env python3
"""Build the Week 6 game-day final-gate observation checklist.

This is an operational research checklist, not a betting card. It schedules the
remaining pre-kickoff evidence checks around the immutable Week 6 snapshot:
- final weather / roof state,
- official inactive list,
- fresh public sportsbook board,
- optional user-account executable-price observation.

Nothing in this artifact can alter the frozen model, authorize a point
adjustment, promote an edge threshold, or publish a recommendation.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

PRELOCK = Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
READINESS = Path('nfl_data/prospective/week6_readiness_matrix_20261017.json')
GATES = Path('nfl_data/prospective/2026_week6_gate_inputs.json')
OUT_JSON = Path('nfl_data/prospective/week6_gameday_final_gate_checklist_20261017.json')
OUT_CSV = Path('nfl_data/prospective/week6_gameday_final_gate_checklist_20261017.csv')
ET = ZoneInfo('America/New_York')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def et_iso(dt):
    return dt.astimezone(ET).isoformat()


def observation_priority(row):
    spread = abs(float(row['spread_disagreement_vs_betmgm']))
    total = abs(float(row['total_disagreement_vs_betmgm']))
    if row['hard_qb_state_break']:
        return 'CRITICAL_STATE_VALIDATION'
    if row['weather_elevated_uncertainty']:
        return 'ELEVATED_ENVIRONMENT_VALIDATION'
    if spread >= 4.0 or total >= 5.0:
        return 'HIGH_DISAGREEMENT_OBSERVATION'
    return 'STANDARD_OBSERVATION'


def main():
    pre = load(PRELOCK)
    readiness = load(READINESS)
    gates = load(GATES)
    snap_id = pre['manifest']['snapshot_id']
    ready = {r['game_id']: r for r in readiness['rows']}

    if readiness.get('snapshot_id') != snap_id:
        raise RuntimeError('Readiness snapshot mismatch')
    if readiness.get('website_publish_allowed') is not False:
        raise RuntimeError('Readiness unexpectedly permits website publication')
    if len(pre['rows']) != 13 or len(ready) != 13:
        raise RuntimeError('Expected 13 Week 6 games')

    rows = []
    for p in pre['rows']:
        gid = p['game_id']
        r = ready.get(gid)
        g = gates.get('games', {}).get(gid)
        if r is None or g is None:
            raise RuntimeError(f'Missing readiness/gate row for {gid}')

        kickoff = datetime.fromisoformat(f"{p['gameday']}T{p['gametime']}:00").replace(tzinfo=ET)
        weather_check = kickoff - timedelta(hours=2)
        inactive_check = kickoff - timedelta(minutes=90)
        public_book_check = kickoff - timedelta(hours=1)
        account_check = kickoff - timedelta(minutes=15)

        priority = observation_priority(r)
        unresolved = [x for x in str(r['release_blockers']).split('|') if x]

        rows.append({
            'game_id': gid,
            'away_team': p['away_team'],
            'home_team': p['home_team'],
            'snapshot_id': snap_id,
            'kickoff_et': et_iso(kickoff),
            'weather_roof_recheck_target_et': et_iso(weather_check),
            'official_inactives_check_target_et': et_iso(inactive_check),
            'fresh_public_book_capture_target_et': et_iso(public_book_check),
            'optional_user_account_price_observation_target_et': et_iso(account_check),
            'observation_priority': priority,
            'hard_qb_state_break': bool(r['hard_qb_state_break']),
            'qb_expected_starter': r.get('qb_expected_starter'),
            'qb_profile_source': r.get('qb_profile_source'),
            'qb_operational_point_adjustment': r.get('qb_operational_point_adjustment'),
            'weather_roof_state_now': r['weather_roof_state'],
            'weather_elevated_uncertainty': bool(r['weather_elevated_uncertainty']),
            'final_inactives_state_now': r['final_inactives_state'],
            'betmgm_home_spread_at_frozen_capture': r['betmgm_home_spread'],
            'spread_disagreement_vs_frozen_betmgm': r['spread_disagreement_vs_betmgm'],
            'betmgm_total_at_frozen_capture': r['betmgm_total'],
            'total_disagreement_vs_frozen_betmgm': r['total_disagreement_vs_betmgm'],
            'unresolved_release_blockers_now': '|'.join(unresolved),
            'weather_roof_check_required': not bool(r['weather_roof_final_for_release']),
            'official_inactives_check_required': not bool(r['final_inactives_resolved']),
            'fresh_public_book_capture_required_for_observation': True,
            'user_account_price_observation_optional': True,
            'model_snapshot_mutable': False,
            'point_adjustment_allowed': False,
            'recommendation_release_allowed': False,
            'website_publish_allowed': False,
        })

    rows.sort(key=lambda x: (x['kickoff_et'], x['game_id']))
    summary = {
        'games': len(rows),
        'critical_state_validation_games': sum(r['observation_priority'] == 'CRITICAL_STATE_VALIDATION' for r in rows),
        'elevated_environment_validation_games': sum(r['observation_priority'] == 'ELEVATED_ENVIRONMENT_VALIDATION' for r in rows),
        'high_disagreement_observation_games': sum(r['observation_priority'] == 'HIGH_DISAGREEMENT_OBSERVATION' for r in rows),
        'standard_observation_games': sum(r['observation_priority'] == 'STANDARD_OBSERVATION' for r in rows),
        'weather_roof_rechecks_required': sum(r['weather_roof_check_required'] for r in rows),
        'official_inactives_checks_required': sum(r['official_inactives_check_required'] for r in rows),
        'fresh_public_book_captures_required': len(rows),
        'recommendation_release_games': 0,
    }

    out = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'snapshot_id': snap_id,
        'timezone': 'America/New_York',
        'policy': (
            'Operational observation checklist only. Checkpoint times are target times, not guarantees that official information '
            'will be available exactly then. The frozen model and pregame snapshot cannot be changed.'
        ),
        'check_timing_policy': {
            'weather_roof': 'target two hours before kickoff; refresh again if conditions/roof remain unresolved',
            'official_inactives': 'target 90 minutes before kickoff, consistent with normal NFL inactive timing',
            'fresh_public_book': 'target one hour before kickoff for prospective market comparison',
            'user_account_price': 'optional observation near 15 minutes before kickoff; required before any future executable-price claim',
        },
        'summary': summary,
        'rows': rows,
        'release_state': 'HOLD_OBSERVATION_ONLY',
        'website_publish_allowed': False,
    }

    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    with OUT_CSV.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
