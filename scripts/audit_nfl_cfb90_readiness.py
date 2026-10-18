#!/usr/bin/env python3
"""Audit Week 6 NFL projections against the CFB eight-layer readiness standard.

The CFB standard is input completeness, not prediction accuracy or betting-edge
validation. Eight equally weighted layers are scored at 12.5% each:
1 Base stats, 2 Opponent adjustment, 3 Advanced efficiency,
4 Injuries/personnel, 5 Weather, 6 Market, 7 Travel/rest, 8 Depth chart.
Because scores move in 12.5-point increments, a nominal 90% minimum requires
8/8 layers = 100% coverage.

This audit NEVER changes the frozen projection and NEVER converts readiness into
PLAY/LEAN/recommendation release. Late inactives, weather/roof finality,
execution verification and prospective calibration remain separate gates.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

PRELOCK = Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
BASE = Path('nfl_data/generated/team_efficiency_2026_week6_pregame.csv')
OPP = Path('nfl_data/generated/opponent_adjusted_2026_week6_pregame.csv')
PBP = Path('nfl_data/generated/pbp_features_2026_week6_pregame.csv')
COVERAGE = Path('nfl_data/generated/coverage_2026_week6_pregame.csv')
INJ = Path('nfl_data/generated/injury_personnel_2026_week6_pregame.csv')
QB = Path('nfl_data/generated/qb_room_2026_week6_pregame.csv')
PROJ_QA = Path('nfl_data/generated/week6_research_projections_qa.json')
DEPTH_QA = Path('nfl_data/generated/depth_injury_audit_2022_2026.json')
READINESS = Path('nfl_data/prospective/week6_readiness_matrix_20261017.json')
SCHED = Path('nfl_data/generated/week6_schedule_context_2026.json')
OUT_JSON = Path('nfl_data/validation/cfb90_readiness_week6.json')
OUT_CSV = Path('nfl_data/validation/cfb90_readiness_week6.csv')
OUT_MD = Path('nfl_data/validation/CFB90_READINESS_WEEK6.md')
LAYER_NAMES = [
    'base_stats','opponent_adjustment','advanced_efficiency','injuries_personnel',
    'weather','market','travel_rest','depth_chart'
]


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def team_index(path):
    return {str(r.get('team','')).strip().upper(): r for r in read_csv(path)}


def present(row, *fields):
    return row is not None and all(str(row.get(f,'')).strip() not in ('', 'nan', 'None') for f in fields)


def main():
    required = [PRELOCK,BASE,OPP,PBP,COVERAGE,INJ,QB,PROJ_QA,DEPTH_QA,READINESS,SCHED]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError(f'Missing readiness inputs: {missing}')

    pre = load_json(PRELOCK)
    proj_qa = load_json(PROJ_QA)
    depth_qa = load_json(DEPTH_QA)
    readiness = load_json(READINESS)
    sched = load_json(SCHED)

    base = team_index(BASE); opp = team_index(OPP); pbp = team_index(PBP)
    coverage = team_index(COVERAGE); inj = team_index(INJ); qb = team_index(QB)
    ready_by_game = {r['game_id']: r for r in readiness['rows']}
    sched_by_game = {r['game_id']: r for r in sched['rows']}

    depth2026 = depth_qa.get('depth',{}).get('2026',{})
    depth_global_ready = (
        depth2026.get('pregame_safety_class') == 'EXACT_TIMESTAMP_FILTERABLE'
        and float(depth2026.get('pregame_snapshot_coverage_rate',0)) >= 0.999
        and float(depth2026.get('qb2_coverage_rate',0)) >= 0.999
    )
    advanced_global_ready = (
        int(proj_qa.get('current_team_rows',0)) == 32
        and int(proj_qa.get('current_target_or_future_rows_used',1)) == 0
        and int(proj_qa.get('max_current_source_week_used',99)) <= 5
    )

    rows=[]
    for game in pre['rows']:
        gid = game['game_id']; away = game['away_team']; home = game['home_team']
        rdy = ready_by_game.get(gid); sch = sched_by_game.get(gid)
        if rdy is None or sch is None:
            raise RuntimeError(f'Missing readiness/schedule context for {gid}')

        b1,b2 = base.get(away),base.get(home)
        o1,o2 = opp.get(away),opp.get(home)
        p1,p2 = pbp.get(away),pbp.get(home)
        c1,c2 = coverage.get(away),coverage.get(home)
        i1,i2 = inj.get(away),inj.get(home)
        q1,q2 = qb.get(away),qb.get(home)

        layers = {
            'base_stats': present(b1,'games','off_epa_per_play_proxy','def_epa_per_play_allowed_proxy') and present(b2,'games','off_epa_per_play_proxy','def_epa_per_play_allowed_proxy') and int(float(b1['data_through_week'])) <= 5 and int(float(b2['data_through_week'])) <= 5,
            'opponent_adjustment': present(o1,'adj_off_epa_per_play_above_average','adj_def_epa_prevention_per_play_above_average','reliability_proxy') and present(o2,'adj_off_epa_per_play_above_average','adj_def_epa_prevention_per_play_above_average','reliability_proxy'),
            'advanced_efficiency': advanced_global_ready and p1 is not None and p2 is not None and c1 is not None and c2 is not None,
            'injuries_personnel': i1 is not None and i2 is not None and bool(rdy.get('official_final_status_report_available')),
            'weather': bool(rdy.get('weather_forecast_or_roof_status_checked')),
            'market': str(rdy.get('public_book_capture_state','')).startswith('CAPTURED_TIMESTAMPED') and rdy.get('betmgm_home_spread') is not None and rdy.get('betmgm_total') is not None,
            'travel_rest': bool(sch.get('travel_rest_layer_ready')),
            'depth_chart': depth_global_ready and q1 is not None and q2 is not None,
        }
        passed = sum(bool(v) for v in layers.values())
        score = passed * 12.5
        cfb90_pass = score >= 90.0
        if cfb90_pass and passed != 8:
            raise RuntimeError('Discrete 8-layer scoring should require 8/8 for >=90%')

        freshness=[]
        if not rdy.get('final_inactives_resolved'): freshness.append('FINAL_INACTIVES_PENDING')
        if not rdy.get('weather_roof_final_for_release'): freshness.append('FINAL_WEATHER_OR_ROOF_PENDING')
        if not rdy.get('user_account_execution_verified'): freshness.append('USER_ACCOUNT_EXECUTION_NOT_VERIFIED')
        if rdy.get('hard_qb_state_break'): freshness.append('HARD_QB_STATE_BREAK')
        if not rdy.get('historical_edge_threshold_earned'): freshness.append('NO_VALIDATED_EDGE_THRESHOLD')

        row={
            'game_id':gid,'away_team':away,'home_team':home,
            **{f'{k}_ready':bool(layers[k]) for k in LAYER_NAMES},
            'layers_passed':passed,'layers_total':8,'input_coverage_pct':score,
            'cfb90_input_coverage_pass':cfb90_pass,
            'freshness_release_blockers':'|'.join(freshness),
            'hard_qb_state_break':bool(rdy.get('hard_qb_state_break')),
            'final_inactives_resolved':bool(rdy.get('final_inactives_resolved')),
            'weather_roof_final_for_release':bool(rdy.get('weather_roof_final_for_release')),
            'execution_verified':bool(rdy.get('user_account_execution_verified')),
            'recommendation':'HOLD_NO_VALIDATED_EDGE_THRESHOLD',
        }
        rows.append(row)

    summary={
        'games':len(rows),
        'games_at_100_pct_input_coverage':sum(r['input_coverage_pct']==100.0 for r in rows),
        'games_meeting_cfb90_input_standard':sum(r['cfb90_input_coverage_pass'] for r in rows),
        'slate_cfb90_pass_rate_pct':round(100*sum(r['cfb90_input_coverage_pass'] for r in rows)/len(rows),2),
        'average_input_coverage_pct':round(sum(r['input_coverage_pct'] for r in rows)/len(rows),2),
        'layer_pass_counts':{k:sum(r[f'{k}_ready'] for r in rows) for k in LAYER_NAMES},
        'final_inactives_resolved_games':sum(r['final_inactives_resolved'] for r in rows),
        'weather_roof_final_games':sum(r['weather_roof_final_for_release'] for r in rows),
        'execution_verified_games':sum(r['execution_verified'] for r in rows),
        'recommendation_release_games':0,
    }
    payload={
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'standard':'CFB eight-layer input completeness standard',
        'nominal_minimum_pct':90,
        'effective_required_layers':'8/8 because each layer is worth 12.5 percentage points',
        'important_interpretation':'Input coverage is not prediction accuracy, cover probability, betting confidence or release authorization.',
        'summary':summary,'rows':rows,
        'release_policy':'CFB90 input pass does not override prospective calibration, final inactive/weather gates, hard-QB uncertainty, or execution verification.',
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    with OUT_CSV.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)

    lines=[
        '# NFL Week 6 — CFB 90% Readiness Audit','',
        f"**Games meeting the CFB input standard:** {summary['games_meeting_cfb90_input_standard']}/{summary['games']} ({summary['slate_cfb90_pass_rate_pct']:.1f}%)  ",
        f"**Average input coverage:** {summary['average_input_coverage_pct']:.1f}%  ",
        '**Recommendation release:** HOLD','',
        'The CFB 90% rule is an input-completeness gate, not a prediction hit-rate target. With eight equal 12.5% layers, a 90% minimum requires all eight layers.','',
        '| Game | Coverage | Base | Opp adj | Advanced | Personnel | Weather | Market | Travel/rest | Depth |','|---|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|'
    ]
    for r in rows:
        checks=['✓' if r[f'{k}_ready'] else '✗' for k in LAYER_NAMES]
        lines.append(f"| {r['away_team']}@{r['home_team']} | {r['input_coverage_pct']:.1f}% | "+' | '.join(checks)+' |')
    lines += ['', '## Separate release/freshness gates','',
              f"- Final inactives resolved: **{summary['final_inactives_resolved_games']}/{summary['games']}**",
              f"- Final weather/roof resolved: **{summary['weather_roof_final_games']}/{summary['games']}**",
              f"- Account-level execution verified: **{summary['execution_verified_games']}/{summary['games']}**",
              '- Betting recommendations remain **HOLD** until prospective calibration and explicit release review are earned.']
    OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
