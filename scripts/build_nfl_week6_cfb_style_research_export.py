#!/usr/bin/env python3
"""Build a development-only CFB-style NFL Week 6 model product export.

This file is a presentation/data-contract dry run only. It exposes the frozen
canonical model and the separately frozen FTN50 shadow side-by-side, plus the
same reliability, market and gate context the eventual NFL site should show.
It cannot publish to the live site or create betting recommendations.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

CANON = Path('nfl_data/prospective/week6_prelock_20261017T225656Z.json')
SHADOW = Path('nfl_data/prospective/shadow/week6_ftn50_shadow_20261017T235342Z.json')
REL = Path('nfl_data/prospective/week6_projection_reliability_20261017T230853Z.json')
READY = Path('nfl_data/prospective/week6_readiness_matrix_20261017.json')
MARKET = Path('nfl_data/prospective/market_captures/week6_betmgm_web_capture_20261017T225910Z.json')
OUT = Path('nfl_data/research_exports')


def idx(payload, key='rows'):
    return {r['game_id']: r for r in payload[key]}


def side_from_margin(home_team, away_team, margin):
    if margin > 0:
        return home_team
    if margin < 0:
        return away_team
    return 'PICK'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    can = json.loads(CANON.read_text())
    sh = json.loads(SHADOW.read_text())
    rel = json.loads(REL.read_text())
    ready = json.loads(READY.read_text())
    market = json.loads(MARKET.read_text())

    ci = idx(can)
    si = idx(sh)
    ri = idx(rel)
    rdi = idx(ready)
    mi = idx(market)
    sets = [set(ci), set(si), set(ri), set(rdi), set(mi)]
    if not all(s == sets[0] for s in sets[1:]):
        raise RuntimeError('canonical/shadow/reliability/readiness/market game sets differ')
    if can['manifest']['snapshot_id'] != sh['manifest']['canonical_snapshot_id']:
        raise RuntimeError('shadow does not reference canonical snapshot')
    if any(x.get('website_publish_allowed') is not False for x in [sh['manifest'], ready]):
        raise RuntimeError('source unexpectedly publishable')

    rows = []
    for gid in sorted(ci, key=lambda g: (ci[g]['gameday'], ci[g]['gametime'], g)):
        c, s, r, d, m = ci[gid], si[gid], ri[gid], rdi[gid], mi[gid]
        canonical_margin = float(c['final_research_home_margin'])
        shadow_margin = float(s['shadow_50_50_home_margin'])
        market_home_spread = float(m['home_spread'])
        model_total = float(c['projected_total'])
        market_total = float(m['total'])
        rows.append({
            'game_id': gid,
            'gameday': c['gameday'],
            'gametime_et': c['gametime'],
            'away_team': c['away_team'],
            'home_team': c['home_team'],
            'canonical_model_side': side_from_margin(c['home_team'], c['away_team'], canonical_margin),
            'canonical_home_margin': round(canonical_margin, 3),
            'canonical_home_spread': round(-canonical_margin, 3),
            'shadow_model_side': side_from_margin(c['home_team'], c['away_team'], shadow_margin),
            'shadow_home_margin': round(shadow_margin, 3),
            'shadow_home_spread': round(-shadow_margin, 3),
            'shadow_minus_canonical_home_margin': round(shadow_margin - canonical_margin, 3),
            'model_total': round(model_total, 3),
            'public_book': m['book'],
            'public_book_capture_utc': m['capture_created_at_utc'],
            'public_book_home_spread': market_home_spread,
            'canonical_spread_disagreement_vs_market': round(canonical_margin + market_home_spread, 3),
            'shadow_spread_disagreement_vs_market': round(shadow_margin + market_home_spread, 3),
            'public_book_total': market_total,
            'total_disagreement_vs_market': round(model_total - market_total, 3),
            'spread_reliability_tier': r['spread_reliability_tier'],
            'total_reliability_tier': r['total_reliability_tier'],
            'spread_68_low': r['spread_68_low'],
            'spread_68_high': r['spread_68_high'],
            'total_68_low': r['total_68_low'],
            'total_68_high': r['total_68_high'],
            'personnel_state': d['personnel_state'],
            'hard_qb_state_break': d['hard_qb_state_break'],
            'qb_expected_starter': d['qb_expected_starter'],
            'qb_operational_point_adjustment': d['qb_operational_point_adjustment'],
            'weather_roof_state': d['weather_roof_state'],
            'weather_elevated_uncertainty': d['weather_elevated_uncertainty'],
            'final_inactives_resolved': d['final_inactives_resolved'],
            'user_account_execution_verified': d['user_account_execution_verified'],
            'release_blockers': d['release_blockers'],
            'recommendation': 'HOLD_NO_VALIDATED_EDGE_THRESHOLD',
            'preferred_architecture_for_release': 'CANONICAL_UNTIL_PROSPECTIVE_SHADOW_EVIDENCE_ACCUMULATES',
            'website_publish_allowed': False,
        })

    now = datetime.now(timezone.utc)
    stamp = now.strftime('%Y%m%dT%H%M%SZ')
    payload = {
        'schema_version': 'nfl-cfb-style-research-v2',
        'created_at_utc': now.isoformat(),
        'league': 'NFL',
        'season': 2026,
        'week': 6,
        'canonical_snapshot_id': can['manifest']['snapshot_id'],
        'shadow_snapshot_id': sh['manifest']['shadow_snapshot_id'],
        'display_intent': 'Mirror the CFB model product structure while preserving research-only NFL status.',
        'architecture_policy': {
            'official': 'CANONICAL_FINAL_ARCHITECTURE',
            'shadow': 'FIXED_50_50_CANONICAL_PLUS_FTN_QB_PROCESS',
            'total': 'CANONICAL_CORE_UNCHANGED',
            'do_not_average_or_select_using_week6_outcomes': True,
        },
        'historical_architecture_evidence': {
            'canonical_spread_mae': sh['manifest']['historical_validation']['canonical_mae'],
            'ftn50_shadow_spread_mae': sh['manifest']['historical_validation']['shadow_blend_mae'],
            'ftn50_shadow_mean_improvement': sh['manifest']['historical_validation']['mae_improvement'],
            'ftn50_shadow_bootstrap_95_ci': sh['manifest']['historical_validation']['paired_bootstrap_95_ci'],
        },
        'release_policy': {
            'recommendations_enabled': False,
            'validated_edge_threshold_exists': False,
            'alt_line_logic_enabled': False,
            'website_publish_allowed': False,
            'reason': 'Prospective calibration sample is not yet sufficient.',
        },
        'games': rows,
        'website_publish_allowed': False,
    }
    jpath = OUT / f'week6_cfb_style_research_export_{stamp}.json'
    cpath = OUT / f'week6_cfb_style_research_export_{stamp}.csv'
    jpath.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    with cpath.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(json.dumps({'json': str(jpath), 'csv': str(cpath), 'games': len(rows), 'schema_version': payload['schema_version'], 'website_publish_allowed': False}, indent=2))


if __name__ == '__main__':
    main()
