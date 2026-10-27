#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/results.csv'
SUMMARY = ROOT / 'cfb/record-summary.json'
OUT_DIR = ROOT / 'cfb/results'


def fnum(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def inum(value):
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding='utf-8'))
    season = int(summary.get('season', 2026))
    week = int(summary['currentWeek'])
    rows = list(csv.DictReader(SOURCE.open(encoding='utf-8')))
    rows = [r for r in rows if int(r.get('season') or 0) == season and int(r.get('week') or 0) == week]
    if not rows:
        raise SystemExit(f'No audited rows found for {season} Week {week}')

    expected = int(((summary.get('weeks') or [{}])[-1].get('ats') or {}).get('graded') or 0)
    if expected and sum(r.get('atsResult') in ('WIN','LOSS','PUSH') for r in rows) != expected:
        raise SystemExit(f'Audited row count mismatch: CSV={len(rows)} summary ATS graded={expected}')

    games = []
    for r in rows:
        away_score, home_score = inum(r.get('awayScore')), inum(r.get('homeScore'))
        final = None
        status = 'PENDING'
        if away_score is not None and home_score is not None:
            status = 'FINAL'
            final = {
                'awayScore': away_score,
                'homeScore': home_score,
                'marginHome': home_score - away_score,
                'total': home_score + away_score,
            }
        games.append({
            'gameId': r.get('gameId'),
            'date': r.get('date'),
            'awayTeam': r.get('awayTeam'),
            'homeTeam': r.get('homeTeam'),
            'conference': r.get('conference'),
            'status': status,
            'final': final,
            'projection': {
                'spreadHome': fnum(r.get('modelSpreadHome')),
                'total': fnum(r.get('modelTotal')),
                'homeWinProbability': fnum(r.get('homeWinProbability')),
                'winner': r.get('suProjection') or None,
            },
            'market': {
                'spreadHome': fnum(r.get('marketSpreadHome')),
                'total': fnum(r.get('marketTotal')),
                'moneylineHome': None,
                'moneylineAway': None,
            },
            'ats': {'pick': r.get('atsProjection') or None, 'result': (r.get('atsResult') or 'NO_PICK').upper()},
            'totals': {'pick': r.get('totalProjection') or None, 'result': (r.get('totalResult') or 'NO_PICK').upper()},
            'straightUp': {'pick': r.get('suProjection') or None, 'result': (r.get('suResult') or 'NO_PICK').upper()},
            'trackingClass': r.get('trackingClass') or None,
            'gradeReference': r.get('gradeReference') or None,
        })

    payload = {
        'schemaVersion': 1,
        'league': 'cfb',
        'season': season,
        'week': week,
        'role': 'AUDITED_SITE_RESULTS_COMPATIBILITY',
        'canonicalInfluence': False,
        'source': 'data/results.csv',
        'sourcePolicy': 'Mechanical export of already-audited published result rows. Never reconstructs missing pregame information and never changes a grade.',
        'games': games,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f'week-{week:02d}.json'
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
    previous = out.read_text(encoding='utf-8') if out.exists() else ''
    if previous != rendered:
        out.write_text(rendered, encoding='utf-8')
    print(json.dumps({'output': str(out.relative_to(ROOT)), 'games': len(games), 'week': week}, indent=2))


if __name__ == '__main__':
    main()
