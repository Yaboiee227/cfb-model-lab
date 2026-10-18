#!/usr/bin/env python3
"""Validate the static NFL trends data before GitHub Pages publication.

No third-party content is fetched. This validates the manually maintained
nfl_data/site/nfl-trends.json against the current NFL projections package.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

TRENDS = Path('nfl_data/site/nfl-trends.json')
PROJECTIONS = Path('nfl_data/site/projections.csv')
CONFIG = Path('nfl_data/site/config.json')
RESULTS = Path('nfl_data/site/nfl-trend-results.json')
VALID_TYPES = {'ATS', 'SU', 'TOTAL', 'SITUATIONAL'}
VALID_POINTS = {'home', 'away', 'over', 'under', 'none'}
VALID_TARGETS = {'spread', 'moneyline', 'total', 'none'}
EXPECTED_TARGET = {'ATS': 'spread', 'SU': 'moneyline', 'TOTAL': 'total'}
NFL_TEAMS = {
    'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB',
    'HOU','IND','JAX','KC','LV','LAC','LA','MIA','MIN','NE','NO','NYG','NYJ',
    'PHI','PIT','SEA','SF','TB','TEN','WAS'
}
TEAM_ALIASES = {'JAC':'JAX','LAR':'LA','WSH':'WAS','OAK':'LV','SD':'LAC','SDG':'LAC'}


def fail(msg, errors):
    errors.append(msg)


def valid_url(value):
    try:
        p = urlparse(str(value))
        return p.scheme in {'http', 'https'} and bool(p.netloc)
    except Exception:
        return False


def parse_iso(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise SystemExit(f'Could not parse {path}: {exc}')


def load_projection_rows():
    with PROJECTIONS.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def validate():
    errors, warnings = [], []
    for path in (TRENDS, PROJECTIONS, CONFIG, RESULTS):
        if not path.exists():
            fail(f'Missing required file: {path}', errors)
    if errors:
        return errors, warnings

    data = load_json(TRENDS)
    config = load_json(CONFIG)
    result_data = load_json(RESULTS)
    rows = load_projection_rows()
    games = {r['gameId']: r for r in rows}

    if data.get('schemaVersion') != 1:
        fail('schemaVersion must be 1', errors)
    if not isinstance(data.get('season'), int):
        fail('season must be an integer', errors)
    if not isinstance(data.get('week'), int) or not 1 <= data['week'] <= 25:
        fail('week must be an integer from 1 to 25', errors)
    if not parse_iso(data.get('lastUpdated')):
        fail('lastUpdated must be a valid ISO-8601 timestamp', errors)

    source = data.get('source') or {}
    if not str(source.get('name') or '').strip():
        fail('source.name is required', errors)
    if not valid_url(source.get('url')):
        fail('source.url must be an http(s) URL', errors)

    cfg = data.get('alignmentConfig') or {}
    for key, upper in [('spreadNeutralBand', 3), ('totalNeutralBand', 5), ('moneylineNeutralBandPct', 10)]:
        val = cfg.get(key)
        if not isinstance(val, (int, float)) or not 0 <= val <= upper:
            fail(f'alignmentConfig.{key} must be numeric between 0 and {upper}', errors)

    current_week = config.get('currentWeek')
    if current_week is not None and int(data.get('week') or -1) != int(current_week):
        warnings.append(f'Trends file is Week {data.get("week")}; site currentWeek is {current_week}. It will be treated as archived/stale.')

    ids = set()
    trends = data.get('trends')
    if not isinstance(trends, list):
        fail('trends must be an array', errors)
        trends = []

    for i, trend in enumerate(trends):
        p = f'trends[{i}]'
        if not isinstance(trend, dict):
            fail(f'{p} must be an object', errors)
            continue
        tid = str(trend.get('id') or '').strip()
        if not tid:
            fail(f'{p}.id is required', errors)
        elif tid in ids:
            fail(f'{p}.id duplicates {tid}', errors)
        ids.add(tid)

        gid = str(trend.get('gameId') or '').strip()
        game = games.get(gid)
        if game is None:
            fail(f'{p}.gameId {gid!r} does not match nfl_data/site/projections.csv', errors)
            continue

        try:
            season, week = int(trend.get('season')), int(trend.get('week'))
        except Exception:
            fail(f'{p}.season and week must be integers', errors)
            continue
        if season != int(game['season']) or week != int(game['week']):
            fail(f'{p} season/week {season}/{week} does not match game {game["season"]}/{game["week"]}', errors)
        if season != data.get('season') or week != data.get('week'):
            fail(f'{p} season/week must match file-level season/week', errors)

        matchup = trend.get('matchup') or {}
        away = str(matchup.get('away') or '').upper()
        home = str(matchup.get('home') or '').upper()
        if away != game['awayTeam'] or home != game['homeTeam']:
            fail(f'{p}.matchup must be {game["awayTeam"]} at {game["homeTeam"]}', errors)
        if away in TEAM_ALIASES or home in TEAM_ALIASES:
            fail(f'{p}.matchup uses an alias; use canonical team codes (e.g. JAX, LA, WAS, LAC)', errors)
        if away not in NFL_TEAMS or home not in NFL_TEAMS:
            fail(f'{p}.matchup contains an unknown NFL team code', errors)

        subject = str(trend.get('subject') or '').upper()
        if subject in TEAM_ALIASES:
            fail(f'{p}.subject {subject} is an alias; use {TEAM_ALIASES[subject]}', errors)
        if subject != 'TOTAL' and subject not in {away, home}:
            fail(f'{p}.subject must be {away}, {home}, or TOTAL', errors)

        ttype = str(trend.get('trendType') or '').upper()
        target = str(trend.get('alignmentTarget') or '').lower()
        points = str(trend.get('pointsTo') or '').lower()
        if ttype not in VALID_TYPES:
            fail(f'{p}.trendType must be one of {sorted(VALID_TYPES)}', errors)
        if target not in VALID_TARGETS:
            fail(f'{p}.alignmentTarget must be one of {sorted(VALID_TARGETS)}', errors)
        if points not in VALID_POINTS:
            fail(f'{p}.pointsTo must be one of {sorted(VALID_POINTS)}', errors)
        if ttype in EXPECTED_TARGET and target != EXPECTED_TARGET[ttype]:
            fail(f'{p} {ttype} trends must use alignmentTarget={EXPECTED_TARGET[ttype]}', errors)
        if ttype == 'SITUATIONAL' and target == 'none' and points != 'none':
            fail(f'{p} situational alignmentTarget=none requires pointsTo=none', errors)
        if target == 'total' and points not in {'over','under','none'}:
            fail(f'{p} total alignment requires pointsTo over/under/none', errors)
        if target in {'spread','moneyline'} and points not in {'home','away','none'}:
            fail(f'{p} side alignment requires pointsTo home/away/none', errors)

        text = str(trend.get('text') or '').strip()
        if len(text) < 5 or len(text) > 180:
            fail(f'{p}.text must be 5-180 characters', errors)
        if '\n' in text:
            fail(f'{p}.text must be one short line', errors)

        sample = trend.get('sampleSize')
        if not isinstance(sample, int) or sample < 1:
            fail(f'{p}.sampleSize must be a positive integer', errors)
        record = str(trend.get('record') or '').strip()
        if not record or len(record) > 50:
            fail(f'{p}.record is required and must be <= 50 characters', errors)
        if sample and record and not re.search(r'\d', record):
            warnings.append(f'{p}.record contains no number; verify the record was entered correctly.')

        if not str(trend.get('sourceName') or '').strip():
            fail(f'{p}.sourceName is required', errors)
        if not valid_url(trend.get('sourceUrl')):
            fail(f'{p}.sourceUrl must be an http(s) URL', errors)
        tags = trend.get('tags', [])
        if tags is not None and (not isinstance(tags, list) or any(not isinstance(x, str) or not x.strip() for x in tags)):
            fail(f'{p}.tags must be an array of non-empty strings', errors)

    if not isinstance(result_data.get('results'), list):
        fail('nfl-trend-results.json results must be an array', errors)
    else:
        for i, row in enumerate(result_data['results']):
            p = f'results[{i}]'
            if row.get('trendId') not in ids:
                warnings.append(f'{p}.trendId {row.get("trendId")!r} is not present in the current trends file; this is valid only for archived-week results.')
            if row.get('outcome') not in {'win','loss','push','void','pending'}:
                fail(f'{p}.outcome must be win/loss/push/void/pending', errors)

    return errors, warnings


def main():
    errors, warnings = validate()
    for w in warnings:
        print(f'WARNING: {w}')
    if errors:
        for e in errors:
            print(f'ERROR: {e}', file=sys.stderr)
        print(f'NFL trends validation FAILED: {len(errors)} error(s), {len(warnings)} warning(s).', file=sys.stderr)
        raise SystemExit(1)
    print(f'NFL trends validation PASSED: {len(warnings)} warning(s).')


if __name__ == '__main__':
    main()
