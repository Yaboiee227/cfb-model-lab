#!/usr/bin/env python3
"""Build Week 6 NFL rest/travel context for CFB-equivalent readiness scoring.

This is a context artifact only. It does not alter frozen model projections.
Rest is computed from nflverse regular-season schedule dates strictly before the
Week 6 target game. Travel metadata comes from the already-audited static
context artifact. Neutral/international games are explicitly represented rather
than assigned invented travel mileage.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

SCHEDULE_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
STATIC = Path('nfl_data/generated/static_context_2026_week6.csv')
OUT_JSON = Path('nfl_data/generated/week6_schedule_context_2026.json')
OUT_CSV = Path('nfl_data/generated/week6_schedule_context_2026.csv')
SEASON = 2026
WEEK = 6
ALIASES = {'LAR':'LA','STL':'LA','JAC':'JAX','WSH':'WAS','WFT':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}


def nt(v):
    s = str(v or '').strip().upper()
    return ALIASES.get(s, s)


def fetch_schedule():
    req = urllib.request.Request(SCHEDULE_URL, headers={'User-Agent':'cb-model-projections/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode('utf-8'))))


def parse_day(v):
    return date.fromisoformat(str(v))


def main():
    if not STATIC.exists():
        raise RuntimeError(f'Missing static context: {STATIC}')
    static_rows = list(csv.DictReader(STATIC.open(encoding='utf-8', newline='')))
    static_by_game = {r['game_id']: r for r in static_rows}
    schedule = [r for r in fetch_schedule() if str(r.get('game_type','')).upper() == 'REG' and int(float(r.get('season') or 0)) == SEASON]
    target = [r for r in schedule if int(float(r.get('week') or 0)) == WEEK]
    prior = [r for r in schedule if int(float(r.get('week') or 0)) < WEEK]

    prior_days = {}
    for r in prior:
        d = parse_day(r['gameday'])
        for t in (nt(r.get('away_team')), nt(r.get('home_team'))):
            if not t:
                continue
            prior_days.setdefault(t, []).append(d)

    rows = []
    for g in target:
        gid = str(g.get('game_id'))
        if gid not in static_by_game:
            raise RuntimeError(f'Missing static context for {gid}')
        s = static_by_game[gid]
        game_day = parse_day(g['gameday'])
        away, home = nt(g.get('away_team')), nt(g.get('home_team'))
        def rest(team):
            days = [d for d in prior_days.get(team, []) if d < game_day]
            if not days:
                return None
            return (game_day - max(days)).days
        away_rest = rest(away)
        home_rest = rest(home)
        neutral = str(s.get('neutral_site','0')) == '1'
        travel_ready = bool(s.get('game_stadium')) and (neutral or str(s.get('away_travel_air_miles','')).strip() != '')
        rest_ready = away_rest is not None and home_rest is not None
        rows.append({
            'game_id': gid,
            'away_team': away,
            'home_team': home,
            'gameday': str(g['gameday']),
            'away_rest_days': away_rest,
            'home_rest_days': home_rest,
            'rest_diff_away_minus_home': None if away_rest is None or home_rest is None else away_rest-home_rest,
            'neutral_site': int(neutral),
            'away_travel_air_miles': s.get('away_travel_air_miles') or None,
            'away_time_zone_shift_hours': s.get('away_time_zone_shift_hours') or None,
            'away_signed_time_zone_shift_hours': s.get('away_signed_time_zone_shift_hours') or None,
            'stadium': s.get('game_stadium'),
            'travel_context_ready': travel_ready,
            'rest_context_ready': rest_ready,
            'travel_rest_layer_ready': travel_ready and rest_ready,
            'neutral_travel_note': 'NEUTRAL_SITE_DESTINATION_EXPLICIT_MILEAGE_NOT_INVENTED' if neutral else None,
        })

    week6_rows = [r for r in rows if r['game_id'] != '2026_06_SEA_DEN']
    if len(week6_rows) != 13:
        raise RuntimeError(f'Expected 13 remaining Week 6 games, got {len(week6_rows)}')
    summary = {
        'games': len(week6_rows),
        'travel_ready_games': sum(bool(r['travel_context_ready']) for r in week6_rows),
        'rest_ready_games': sum(bool(r['rest_context_ready']) for r in week6_rows),
        'travel_rest_ready_games': sum(bool(r['travel_rest_layer_ready']) for r in week6_rows),
    }
    payload = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': SCHEDULE_URL,
        'policy': 'Context only; no frozen numeric projection is modified.',
        'summary': summary,
        'rows': week6_rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    with OUT_CSV.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(week6_rows[0].keys()))
        w.writeheader(); w.writerows(week6_rows)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
