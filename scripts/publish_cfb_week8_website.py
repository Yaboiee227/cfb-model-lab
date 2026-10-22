#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / 'cfb/research-locks/week-08-foundation-full.json'
SCHEDULE = ROOT / 'cfb/pregame/week-08-schedule.json'
MARKETS = ROOT / 'data/markets-sportsbooks.json'
OUTPUT = ROOT / 'data/projections.csv'
CONFIG = ROOT / 'data/config.json'
ET = ZoneInfo('America/New_York')
FIELDS = ['season','week','date','kickoffET','gameId','awayTeam','awayConference','homeTeam','homeConference','projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal','homeWinProbability','awayWinProbability','marketSpreadHome','marketTotal','marketSource','marketObservedAt','executionVerified','dataQuality','signalStrength','releaseStatus','notes']
ALIASES = {
    'appalachianstate':'appstate','appalachianstatemountaineers':'appstate',
    'floridainternationalpanthers':'floridainternational','fiupanthers':'floridainternational',
    'newmexicostateaggies':'newmexicostate','samhoustonbearkats':'samhouston',
    'massachusettsminutemen':'massachusetts','umassminutemen':'massachusetts',
    'uconnhuskies':'uconn','connecticuthuskies':'uconn',
    'miamiflhurricanes':'miami','miamiohredhawks':'miamioh',
    'hawaiirainbowwarriors':'hawaii','hawaiiwarriors':'hawaii'
}

def norm(value):
    n = re.sub(r'[^a-z0-9]', '', str(value or '').lower())
    return ALIASES.get(n, n)

def team_match(a, b):
    x, y = norm(a), norm(b)
    return bool(x and y) and (x == y or (min(len(x), len(y)) >= 5 and (x.startswith(y) or y.startswith(x))))

def market_for(game, markets):
    kickoff = datetime.fromisoformat(game['kickoff'].replace('Z', '+00:00'))
    for row in markets.get('games', []):
        try:
            market_kickoff = datetime.fromisoformat(row['commenceTime'].replace('Z', '+00:00'))
        except Exception:
            continue
        if abs((market_kickoff - kickoff).total_seconds()) > 300:
            continue
        if team_match(game['homeTeam'], row.get('homeTeam')) and team_match(game['awayTeam'], row.get('awayTeam')):
            return row
    return None

def book_context(market):
    if not market:
        return '', '', '', ''
    for key, label in [('draftkings', 'DraftKings tracked context'), ('fanduel', 'FanDuel tracked context')]:
        book = (market.get('books') or {}).get(key)
        if not book:
            continue
        spread = (book.get('spread') or {}).get('home')
        total = (book.get('total') or {}).get('point')
        if spread is not None and total is not None:
            return spread, total, label, book.get('updatedAt') or ''
    return '', '', '', ''

def kickoff_et(iso):
    dt = datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(ET)
    return dt.strftime('%-I:%M %p'), dt.strftime('%Y-%m-%d')

def main():
    foundation = json.loads(FOUNDATION.read_text(encoding='utf-8'))
    schedule = json.loads(SCHEDULE.read_text(encoding='utf-8'))
    markets = json.loads(MARKETS.read_text(encoding='utf-8'))
    assert foundation['role'] == 'IMMUTABLE_PROSPECTIVE_RESEARCH_SHADOW_LOCK'
    assert foundation['canonicalInfluence'] is False
    assert foundation['canonicalPromotionAuthorized'] is False
    assert len(foundation['games']) == 56

    schedule_by_teams = {
        (norm(g['awayTeam']), norm(g['homeTeam']), g['kickoff']): g
        for g in schedule.get('games', [])
    }
    rows = []
    for game in sorted(foundation['games'], key=lambda x: x['kickoff']):
        kickoff, date = kickoff_et(game['kickoff'])
        market = market_for(game, markets)
        spread, total, source, observed = book_context(market)
        sched = schedule_by_teams.get((norm(game['awayTeam']), norm(game['homeTeam']), game['kickoff']), {})
        hp = float(game['homeWinProbability'])
        rows.append({
            'season': foundation['season'], 'week': foundation['week'], 'date': date,
            'kickoffET': kickoff, 'gameId': sched.get('gameId') or game['gameId'],
            'awayTeam': game['awayTeam'], 'awayConference': '',
            'homeTeam': game['homeTeam'], 'homeConference': '',
            'projectedAwayPoints': f"{game['projectedAwayPoints']:.8f}",
            'projectedHomePoints': f"{game['projectedHomePoints']:.8f}",
            'modelSpreadHome': f"{game['projectedSpreadHome']:.8f}",
            'modelTotal': f"{game['projectedTotal']:.8f}",
            'homeWinProbability': f'{hp:.8f}', 'awayWinProbability': f'{100-hp:.8f}',
            'marketSpreadHome': spread, 'marketTotal': total,
            'marketSource': source, 'marketObservedAt': observed,
            'executionVerified': 'false',
            'dataQuality': '',
            'signalStrength': 'RESEARCH SHADOW',
            'releaseStatus': 'RESEARCH SHADOW - CANONICAL HOLD',
            'notes': f"Immutable Week 8 foundation digest {game['projectionDigest']}; market/context layers are non-canonical; final-window publication locks remain separate."
        })

    with OUTPUT.open('w', newline='', encoding='utf-8') as fp:
        writer = csv.DictWriter(fp, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    stamp = markets.get('generatedAt') or foundation['lockedAt']
    updated = datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(ET)
    cfg.update({
        'season': 2026,
        'currentWeek': 8,
        'lastUpdated': updated.strftime('%B %-d, %Y · %-I:%M %p ET'),
        'modelVersion': 'CFB rebuild foundation v1 · Week 8 prospective research shadow',
        'spreadValidation': 'HOLD',
        'totalValidation': 'HOLD',
        'publicationStatus': 'Week 8 full-slate research shadow · canonical release on HOLD'
    })
    CONFIG.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')

    assert len(rows) == 56
    print(json.dumps({
        'rows': len(rows),
        'output': str(OUTPUT.relative_to(ROOT)),
        'marketSnapshot': markets.get('generatedAt'),
        'foundationDigest': foundation.get('lockDigest'),
        'canonicalInfluence': False
    }, indent=2))

if __name__ == '__main__':
    main()
