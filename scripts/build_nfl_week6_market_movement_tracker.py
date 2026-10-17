#!/usr/bin/env python3
"""Track Week 6 public sportsbook movement versus the frozen first capture.

This is prospective market-observation infrastructure only. It compares the
first timestamped BetMGM public web-board capture with the most recent capture.
It tracks both headline spread/total movement and displayed decimal-price
movement. It does NOT call the movement CLV because no user-account executable
bet price was verified, and it never creates a recommendation.
"""
from __future__ import annotations

import csv
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

CAPTURE_GLOB = 'nfl_data/prospective/market_captures/week6_betmgm_web_capture_*.json'
OUT_JSON = Path('nfl_data/prospective/week6_public_market_movement_20261017.json')
OUT_CSV = Path('nfl_data/prospective/week6_public_market_movement_20261017.csv')


def load_capture(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def signed_direction(v):
    if v > 0:
        return 'POSITIVE_HOME_OR_OVER_MODEL_DISAGREEMENT'
    if v < 0:
        return 'NEGATIVE_AWAY_OR_UNDER_MODEL_DISAGREEMENT'
    return 'ZERO_DISAGREEMENT'


def num(v):
    return None if v is None else float(v)


def move(latest, baseline):
    if latest is None or baseline is None:
        return None
    return round(float(latest) - float(baseline), 3)


def changed(v):
    return v is not None and abs(v) > 1e-12


def main():
    paths = sorted(glob.glob(CAPTURE_GLOB))
    if not paths:
        raise RuntimeError('No Week 6 BetMGM public web-board captures found')

    captures = [load_capture(p) for p in paths]
    captures.sort(key=lambda d: d['capture_created_at_utc'])
    baseline = captures[0]
    latest = captures[-1]
    snapshot_id = baseline['snapshot_id']

    for c in captures:
        if c.get('snapshot_id') != snapshot_id:
            raise RuntimeError('Market capture snapshot mismatch')
        if c.get('website_publish_allowed') is not False:
            raise RuntimeError('Market capture unexpectedly permits website publication')

    bidx = {r['game_id']: r for r in baseline['rows']}
    lidx = {r['game_id']: r for r in latest['rows']}
    if set(bidx) != set(lidx) or len(bidx) != 13:
        raise RuntimeError('Expected same 13 games in baseline/latest market captures')

    rows = []
    for gid in sorted(bidx):
        b = bidx[gid]
        l = lidx[gid]
        bspread = float(b['home_spread'])
        lspread = float(l['home_spread'])
        btotal = float(b['total'])
        ltotal = float(l['total'])
        bsd = float(b['spread_disagreement_vs_direct_book'])
        lsd = float(l['spread_disagreement_vs_direct_book'])
        btd = float(b['total_disagreement_vs_direct_book'])
        ltd = float(l['total_disagreement_vs_direct_book'])

        baseline_home_price = num(b.get('home_spread_odds'))
        latest_home_price = num(l.get('home_spread_odds'))
        baseline_away_price = num(b.get('away_spread_odds'))
        latest_away_price = num(l.get('away_spread_odds'))
        baseline_over_price = num(b.get('over_odds'))
        latest_over_price = num(l.get('over_odds'))
        baseline_under_price = num(b.get('under_odds'))
        latest_under_price = num(l.get('under_odds'))

        rows.append({
            'game_id': gid,
            'away_team': b['away_team'],
            'home_team': b['home_team'],
            'snapshot_id': snapshot_id,
            'baseline_capture_at_utc': baseline['capture_created_at_utc'],
            'latest_capture_at_utc': latest['capture_created_at_utc'],
            'capture_count_available': len(captures),
            'baseline_home_spread': bspread,
            'latest_home_spread': lspread,
            'home_spread_public_board_move': round(lspread - bspread, 3),
            'baseline_home_spread_decimal_odds': baseline_home_price,
            'latest_home_spread_decimal_odds': latest_home_price,
            'home_spread_decimal_odds_move': move(latest_home_price, baseline_home_price),
            'baseline_away_spread_decimal_odds': baseline_away_price,
            'latest_away_spread_decimal_odds': latest_away_price,
            'away_spread_decimal_odds_move': move(latest_away_price, baseline_away_price),
            'baseline_total': btotal,
            'latest_total': ltotal,
            'total_public_board_move': round(ltotal - btotal, 3),
            'baseline_over_decimal_odds': baseline_over_price,
            'latest_over_decimal_odds': latest_over_price,
            'over_decimal_odds_move': move(latest_over_price, baseline_over_price),
            'baseline_under_decimal_odds': baseline_under_price,
            'latest_under_decimal_odds': latest_under_price,
            'under_decimal_odds_move': move(latest_under_price, baseline_under_price),
            'baseline_model_spread_disagreement': bsd,
            'latest_model_spread_disagreement': lsd,
            'spread_disagreement_change': round(lsd - bsd, 3),
            'spread_disagreement_direction_flipped': (bsd > 0 > lsd) or (bsd < 0 < lsd),
            'baseline_model_total_disagreement': btd,
            'latest_model_total_disagreement': ltd,
            'total_disagreement_change': round(ltd - btd, 3),
            'total_disagreement_direction_flipped': (btd > 0 > ltd) or (btd < 0 < ltd),
            'baseline_spread_disagreement_direction': signed_direction(bsd),
            'latest_spread_disagreement_direction': signed_direction(lsd),
            'baseline_total_disagreement_direction': signed_direction(btd),
            'latest_total_disagreement_direction': signed_direction(ltd),
            'movement_is_clv': False,
            'user_account_execution_verified': bool(l.get('user_account_execution_verified')),
            'recommendation': 'HOLD_NO_VALIDATED_EDGE_THRESHOLD',
            'website_publish_allowed': False,
        })

    summary = {
        'captures': len(captures),
        'games': len(rows),
        'games_with_spread_move': sum(changed(r['home_spread_public_board_move']) for r in rows),
        'games_with_total_move': sum(changed(r['total_public_board_move']) for r in rows),
        'games_with_home_spread_price_move': sum(changed(r['home_spread_decimal_odds_move']) for r in rows),
        'games_with_away_spread_price_move': sum(changed(r['away_spread_decimal_odds_move']) for r in rows),
        'games_with_over_price_move': sum(changed(r['over_decimal_odds_move']) for r in rows),
        'games_with_under_price_move': sum(changed(r['under_decimal_odds_move']) for r in rows),
        'spread_disagreement_direction_flips': sum(r['spread_disagreement_direction_flipped'] for r in rows),
        'total_disagreement_direction_flips': sum(r['total_disagreement_direction_flipped'] for r in rows),
        'account_executable_verified_games_latest_capture': sum(r['user_account_execution_verified'] for r in rows),
        'recommendation_release_games': 0,
    }

    out = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'snapshot_id': snapshot_id,
        'baseline_capture_at_utc': baseline['capture_created_at_utc'],
        'latest_capture_at_utc': latest['capture_created_at_utc'],
        'capture_files': paths,
        'policy': (
            'Public-board movement only, including displayed decimal-price movement. '
            'Do not label as CLV or realized betting value without a verified account-level executable price.'
        ),
        'summary': summary,
        'rows': rows,
        'release_state': 'HOLD_MARKET_OBSERVATION_ONLY',
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
