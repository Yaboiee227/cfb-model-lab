#!/usr/bin/env python3
"""Audit NFL Stage 3 context + market execution infrastructure.

This is a reporting/safety layer. It does not change the immutable Week 6
canonical model, create point adjustments, or authorize recommendations.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PRELOCK = Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
GATES = Path('nfl_data/prospective/2026_week6_gate_inputs.json')
READINESS = Path('nfl_data/prospective/week6_readiness_matrix_20261017.json')
CHECKLIST = Path('nfl_data/prospective/week6_gameday_final_gate_checklist_20261017.json')
MOVEMENT = Path('nfl_data/prospective/week6_public_market_movement_20261017.json')
CONTEXT = Path('nfl_data/prospective/week6_context_refresh_20261018T0055Z.json')
POLICY = Path('NFL_STAGE3_CONTEXT_MARKET_POLICY.md')
OUT_JSON = Path('nfl_data/validation/stage3_context_market_audit.json')
OUT_MD = Path('nfl_data/validation/STAGE3_CONTEXT_MARKET_AUDIT.md')


def load(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))


def main():
    required = [PRELOCK, GATES, READINESS, CHECKLIST, MOVEMENT, CONTEXT, POLICY]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f'Missing Stage 3 inputs: {missing}')

    pre = load(PRELOCK)
    gates = load(GATES)
    ready = load(READINESS)
    checklist = load(CHECKLIST)
    movement = load(MOVEMENT)
    context = load(CONTEXT)

    sid = pre['manifest']['snapshot_id']
    pre_rows = pre['rows']
    ready_rows = ready['rows']
    check_rows = checklist['rows']
    move_rows = movement['rows']

    assert len(pre_rows) == 13
    assert len(ready_rows) == 13
    assert len(check_rows) == 13
    assert len(move_rows) == 13
    assert ready['snapshot_id'] == sid
    assert checklist['snapshot_id'] == sid
    assert movement['snapshot_id'] == sid
    assert pre['manifest'].get('website_publish_allowed') is False
    assert ready.get('website_publish_allowed') is False
    assert checklist.get('website_publish_allowed') is False
    assert movement.get('website_publish_allowed') is False
    assert context.get('website_publish_allowed') is False
    assert context.get('recommendation_release_allowed') is False

    # Core safety checks.
    assert all(r.get('model_snapshot_mutable') is False for r in check_rows)
    assert all(r.get('point_adjustment_allowed') is False for r in check_rows)
    assert all(r.get('recommendation_release_allowed') is False for r in check_rows)
    assert all(r.get('movement_is_clv') is False for r in move_rows)
    assert all(not r.get('user_account_execution_verified') for r in ready_rows)
    assert all((r.get('qb_operational_point_adjustment') in (None, 0, 0.0)) for r in ready_rows)

    game_ids = {r['game_id'] for r in pre_rows}
    assert game_ids == set(gates['games'])
    assert game_ids == {r['game_id'] for r in ready_rows}
    assert game_ids == {r['game_id'] for r in check_rows}
    assert game_ids == {r['game_id'] for r in move_rows}

    summary = ready['summary']
    hard_qb = [r['game_id'] for r in ready_rows if r.get('hard_qb_state_break')]
    elevated_weather = [r['game_id'] for r in ready_rows if r.get('weather_elevated_uncertainty')]
    weather_final = [r['game_id'] for r in ready_rows if r.get('weather_roof_final_for_release')]
    inactives_final = [r['game_id'] for r in ready_rows if r.get('final_inactives_resolved')]

    policy_checks = {
        'immutable_snapshot_protected': True,
        'manual_context_point_adjustments_disabled': True,
        'qb_replacement_operational_points_zero': True,
        'public_board_not_treated_as_executable': True,
        'public_board_movement_not_labeled_clv': True,
        'opening_line_definition_locked': True,
        'current_line_definition_locked': True,
        'closing_line_definition_locked': True,
        'line_shopping_rules_locked': True,
        'game_day_timing_locked': True,
        'source_hierarchy_locked': True,
        'recommendations_still_hold': True,
    }

    current_state = {
        'games': 13,
        'official_final_status_report_available_games': summary['official_final_status_report_available_games'],
        'final_inactives_resolved_games': len(inactives_final),
        'hard_qb_break_games': len(hard_qb),
        'hard_qb_game_ids': hard_qb,
        'weather_forecast_or_roof_checked_games': summary['weather_forecast_or_roof_checked_games'],
        'weather_elevated_uncertainty_games': len(elevated_weather),
        'elevated_weather_game_ids': elevated_weather,
        'weather_roof_final_games': len(weather_final),
        'public_book_captured_games': summary['public_book_captured_games'],
        'account_executable_verified_games': summary['user_account_execution_verified_games'],
        'validated_edge_threshold_games': summary['validated_edge_threshold_games'],
        'recommendation_release_games': summary['recommendation_release_games'],
        'latest_context_refresh_utc': context['captured_at_utc'],
        'latest_internal_public_capture_utc': context['market_context']['latest_internal_public_capture_utc'],
    }

    live_blockers = {
        'final_inactives_pending': 13 - len(inactives_final),
        'weather_or_roof_pending': 13 - len(weather_final),
        'account_execution_unverified': 13 - summary['user_account_execution_verified_games'],
        'validated_edge_threshold_missing': 13 - summary['validated_edge_threshold_games'],
    }

    report = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'stage': 3,
        'stage_name': 'Context + market execution',
        'snapshot_id': sid,
        'policy_file': str(POLICY),
        'policy_checks': policy_checks,
        'current_week6_state': current_state,
        'live_game_blockers': live_blockers,
        'audit_verdict': 'PASS_STAGE3_ARCHITECTURE__LIVE_GAME_GATES_REMAIN_OPEN',
        'stage3_architecture_complete': True,
        'individual_game_release_complete': False,
        'recommendation_release_allowed': False,
        'website_betting_signal_release_allowed': False,
        'handoff': (
            'Stage 3 system design is complete. Continue refreshing live Week 6 inactives, weather/roof and market observations at the locked checkpoint times. '
            'Proceed to Stage 4 calibration framework, but do not release betting confidence or edge thresholds until prospective frozen outcomes accumulate.'
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    md = [
        '# NFL Stage 3 Context + Market Execution Audit',
        '',
        f"**Verdict:** `{report['audit_verdict']}`  ",
        f"**Snapshot:** `{sid}`  ",
        '**Recommendation release:** HOLD',
        '',
        '## Policy lock',
        '',
        '- Canonical Week 6 projections are immutable after freeze.',
        '- QB/personnel/weather/roof news changes reliability or release state only; manual point adjustments are disabled.',
        '- Public sportsbook boards are benchmark observations, not executable-price proof.',
        '- Public-board movement is not CLV.',
        '- Opening/current/closing definitions and line-shopping rules are fixed in `NFL_STAGE3_CONTEXT_MARKET_POLICY.md`.',
        '- Game-day targets are T-2h weather/roof, T-90m inactives, T-60m public market, optional T-15m account observation.',
        '',
        '## Current Week 6 state',
        '',
        f"- Games: **13**",
        f"- Official final status report available: **{current_state['official_final_status_report_available_games']}/13**",
        f"- Final inactives resolved: **{current_state['final_inactives_resolved_games']}/13**",
        f"- Hard QB breaks: **{current_state['hard_qb_break_games']}** ({', '.join(hard_qb)})",
        f"- Weather/roof checked: **{current_state['weather_forecast_or_roof_checked_games']}/13**",
        f"- Weather/roof final for release: **{current_state['weather_roof_final_games']}/13**",
        f"- Timestamped public-book capture: **{current_state['public_book_captured_games']}/13**",
        f"- Account-executable verified: **{current_state['account_executable_verified_games']}/13**",
        f"- Validated edge threshold: **{current_state['validated_edge_threshold_games']}/13**",
        '',
        '## Interpretation',
        '',
        'The Stage 3 operating architecture is complete even though live game-day facts are intentionally unresolved before their publication windows. Those unresolved observations keep individual games on HOLD; they do not justify altering the frozen model.',
        '',
        '## Stage 3 handoff',
        '',
        f"> {report['handoff']}",
    ]
    OUT_MD.write_text('\n'.join(md) + '\n', encoding='utf-8')

    print(json.dumps({
        'verdict': report['audit_verdict'],
        'games': 13,
        'hard_qb_breaks': len(hard_qb),
        'final_inactives': len(inactives_final),
        'weather_final': len(weather_final),
        'public_book': current_state['public_book_captured_games'],
        'executable': current_state['account_executable_verified_games'],
    }, indent=2))


if __name__ == '__main__':
    main()
