#!/usr/bin/env python3
"""Publish completed frozen NFL research weeks without retrospective market fills."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from refresh_site_scoreboards import fetch
from score_sources import _parse_event
from sync_published_records import ROOT, sync


def grade(freeze, scoreboard):
    season, week = freeze['season'], freeze['week']
    if freeze['canonicalInfluence'] is not False:
        raise ValueError('Expected frozen research')
    events = {}
    alias = {'WSH': 'WAS', 'LAR': 'LA'}
    for event in scoreboard['events']:
        competition = event['competitions'][0]
        teams = {c['homeAway']: alias.get(c['team']['abbreviation'], c['team']['abbreviation'])
                 for c in competition['competitors']}
        key = f"{season}_{week:02d}_{teams['away']}_{teams['home']}"
        if key in events:
            raise ValueError('Duplicate matchup')
        events[key] = event
    games = []
    for g in freeze['games']:
        event = events.get(g['gameId'])
        if event is None:
            raise ValueError('Missing frozen matchup')
        kickoff = datetime.fromisoformat(g['kickoffUTC'].replace('Z', '+00:00'))
        observed_kickoff = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
        frozen_at = datetime.fromisoformat(freeze['frozenAt'].replace('Z', '+00:00'))
        if kickoff.astimezone(ZoneInfo('America/New_York')).date() != observed_kickoff.astimezone(ZoneInfo('America/New_York')).date() or frozen_at >= min(kickoff, observed_kickoff):
            raise ValueError('Kickoff or prospective freeze mismatch')
        score = _parse_event(event)
        if score['status'] != 'FINAL':
            return None
        home, away = score['homeScore'], score['awayScore']
        spread, total = g['modelSpreadHome'], g['modelTotal']
        pick = g['home'] if spread < 0 else g['away'] if spread > 0 else None
        winner = g['home'] if home > away else g['away'] if away > home else None
        result = 'PUSH' if winner is None else 'REVIEW' if pick is None else 'WIN' if pick == winner else 'LOSS'
        games.append(dict(gameId=g['gameId'], date=kickoff.astimezone(ZoneInfo('America/New_York')).date().isoformat(),
            awayTeam=g['away'], homeTeam=g['home'], status='FINAL',
            final=dict(awayScore=away, homeScore=home, sourceGameId=score['sourceGameId'], source='ESPN'),
            projection=dict(spreadHome=spread, total=total, winner=pick), market={},
            ats=dict(pick=None, result='REVIEW'), totals=dict(pick=None, result='REVIEW'),
            straightUp=dict(pick=pick, result=result),
            errors=dict(margin=-spread-(home-away), total=total-home-away),
            savedKickoff=g['kickoffUTC'], finalSourceKickoff=event['date'],
            exclusionReason='No eligible publication-time market lock archived for this frozen forecast.'))
    if len({g['gameId'] for g in games}) != len(games):
        raise ValueError('Duplicate frozen game')
    return games


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    summary_path = ROOT/'nfl/record-summary.json'
    original_summary = json.loads(summary_path.read_text())
    for path in sorted((ROOT/'nfl/research-projections').glob('week-*.json')):
        freeze = json.loads(path.read_text())
        week = freeze['week']
        # These baseline weeks were published without grading locks. New formats
        # require an explicit market-lock adapter before this policy can expand.
        if week not in (8, 9):
            continue
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?week={week}&seasontype=2&dates={freeze['season']}&limit=100"
        scoreboard = json.loads((args.capture/f'week-{week:02d}-scoreboard.json').read_text()) if args.capture else fetch(url)
        games = grade(freeze, scoreboard)
        if games is None:
            print(f'Week {week} still pending')
            continue
        result_path = ROOT/f'nfl/research-results/week-{week:02d}.json'
        result = dict(league='nfl', season=freeze['season'], week=week,
            role='FROZEN_RESEARCH_RESULTS', canonicalInfluence=False, canonicalRecordMerged=False,
            sourceFreezeSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            scoreSource=url, games=games)
        previous = json.loads(result_path.read_text()) if result_path.exists() else None
        if previous != result:
            result_path.write_text(json.dumps(result, indent=2)+'\n')
        note = f'Week {week} frozen baseline research. All {len(games)} games graded straight up. ATS and totals excluded for missing original market locks.'
        summary = sync('nfl', week, games, note)
        print(week, next(w['straightUp'] for w in summary['weeks'] if w['week'] == week))
    updated_summary = json.loads(summary_path.read_text())
    comparable = lambda doc: {k: v for k, v in doc.items() if k != 'generatedAt'}
    if comparable(original_summary) == comparable(updated_summary):
        updated_summary['generatedAt'] = original_summary['generatedAt']
        summary_path.write_text(json.dumps(updated_summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
