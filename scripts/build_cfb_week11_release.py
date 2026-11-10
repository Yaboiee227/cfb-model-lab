#!/usr/bin/env python3
"""Freeze and publish Week 11 through the existing foundation research model."""
import csv
import dataclasses
import gzip
import hashlib
import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import cfb_shadow_engine as engine
from build_cfb_week10_release import ROOT, TRAIN_START, build, build_lock, discover_games, iso, local, parse_dt, read, stamp, verify, write
from publish_current_matchups import render
from refresh_current_readiness import market


def main():
    cutoff = stamp()
    first = parse_dt('2026-11-10T19:00:00-05:00')
    if cutoff >= first:
        raise ValueError('Full-week freeze requires capture before first kickoff')
    lock_path = ROOT/'cfb/research-locks/week-11-foundation-full.json'
    if lock_path.exists():
        raise ValueError('Existing Week 11 freeze must be preserved')
    evidence = ROOT/'cfb/pregame/week11-evidence'
    evidence.mkdir(exist_ok=False)
    raw_dir = ROOT.parent/'cfb-week11-raw-sources'
    raw_dir.mkdir(exist_ok=True)
    sources = []
    original_fetch = engine.fetch_json

    def recorded_fetch(url, **kwargs):
        doc = original_fetch(url, **kwargs)
        raw = json.dumps(doc, sort_keys=True, separators=(',', ':')).encode()
        sha = hashlib.sha256(raw).hexdigest()
        (raw_dir/(sha+'.json.gz')).write_bytes(gzip.compress(raw, mtime=0))
        sources.append(dict(url=url, observedAt=iso(stamp()), normalizedJsonSha256=sha))
        return doc

    engine.fetch_json = recorded_fetch
    games = discover_games(parse_dt('2026-11-10T00:00:00-05:00'), parse_dt('2026-11-15T00:00:00-05:00'), max_games=70)
    previous = read('cfb/pregame/week-11-schedule.json')
    if {g['sourceGameId'] for g in games} != {g['sourceGameId'] for g in previous['games']}:
        raise ValueError('Schedule changed. Reconcile coverage before freezing')
    schedule = dict(previous, observedAt=iso(stamp()), games=games, gameCount=len(games))
    write('cfb/pregame/week-11-schedule.json', schedule)
    completed_fetch = engine.fetch_completed_games

    def recorded_completed(start, end):
        completed = completed_fetch(start, end)
        rows = []
        for game in completed:
            row = dataclasses.asdict(game)
            rows.append({k:iso(v) if hasattr(v, 'tzinfo') else v for k,v in row.items()})
        write('cfb/pregame/week11-evidence/training-games.json', dict(asOf=iso(end), games=rows))
        return completed

    engine.fetch_completed_games = recorded_completed
    model = build(ROOT/'cfb/pregame/week-11-schedule.json', ROOT/'cfb/validation/week-08-simple-foundation-validation.json', cutoff, TRAIN_START)
    if len(model['games']) != len(games) or any(g['status'] != 'FOUNDATION_SHADOW_READY' for g in model['games']):
        raise ValueError('Incomplete forecast coverage')
    if model['lockedParameters'] != {'alpha':2.5, 'halfLifeDays':56, 'minTeamAppearances':4}:
        raise ValueError('Unexpected model parameters')
    locked_at = stamp()
    if locked_at >= first:
        raise ValueError('First kickoff passed before freeze')
    lock = build_lock(model, locked_at)
    verify(lock)
    write('cfb/shadow/week-11-foundation-full.json', model)
    write('cfb/research-locks/week-11-foundation-full.json', lock)

    def context(g):
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={g['sourceGameId']}"
        try:
            doc = engine.fetch_json(url)
            observed = stamp()
            comp = doc['header']['competitions'][0]
            if str(doc['header']['id']) != g['sourceGameId'] or parse_dt(comp['date']) != parse_dt(g['kickoff']) or comp['status']['type']['state'] != 'pre' or observed >= parse_dt(g['kickoff']):
                raise ValueError('Source game, kickoff or pregame status mismatch')
            info = doc.get('gameInfo') or {}
            odds = doc.get('pickcenter') or []
            quote = next((o for o in odds if 'draft' in (o.get('provider') or {}).get('name','').lower()), None)
            return dict(gameId=g['gameId'], sourceGameId=g['sourceGameId'], source=url, observedAt=iso(observed),
                kickoffUTC=g['kickoff'], status='PREGAME_CONTEXT_CAPTURED', market=market(quote),
                venue=info.get('venue'), weather=info.get('weather'), officials=info.get('officials') or [],
                sourceInjuries=doc.get('injuries') or [], finalAvailabilityVerified=False,
                releaseStatus='HOLD', blockers=['FINAL_AVAILABILITY_UNVERIFIED','FINAL_WEATHER_PENDING','VALIDATION_HOLD'])
        except Exception as exc:
            return dict(gameId=g['gameId'],sourceGameId=g['sourceGameId'], source=url,status='SOURCE_UNAVAILABLE',error=str(exc),market=None,releaseStatus='HOLD')

    with ThreadPoolExecutor(12) as pool:
        contexts = list(pool.map(context, games))
    write('cfb/pregame/week11-evidence/game-context.json', dict(observedAt=iso(stamp()), canonicalInfluence=False, games=contexts))
    write('cfb/pregame/week11-evidence/source-manifest.json', dict(sources=sources))
    path = ROOT/'data/projections.csv'
    with path.open() as stream:
        old = list(csv.DictReader(stream))
    if {int(g['week']) for g in old} != {10}:
        raise ValueError('Unexpected current week')
    archive = ROOT/'data/archive/week-10-projections.csv'
    if archive.exists():
        raise ValueError('Week 10 archive already exists')
    archive.write_bytes(path.read_bytes())
    rows = []
    cards = []
    forecasts = {g['sourceGameId']:g for g in lock['games']}
    for g, ctx in zip(games, contexts):
        p = forecasts[g['sourceGameId']]
        m = ctx.get('market') or {}
        t = local(g['kickoff'])
        row = {key:'' for key in old[0]}
        row.update(season=2026,week=11,date=str(t.date()),kickoffET=t.strftime('%-I:%M %p'),gameId=g['gameId'],awayTeam=g['awayTeam'],homeTeam=g['homeTeam'],
            projectedAwayPoints=p['projectedAwayPoints'],projectedHomePoints=p['projectedHomePoints'],modelSpreadHome=p['projectedSpreadHome'],modelTotal=p['projectedTotal'],
            homeWinProbability=p['homeWinProbability'],awayWinProbability=100-p['homeWinProbability'],marketSpreadHome=m.get('spreadHome') if m.get('spreadHome') is not None else '',marketTotal=m.get('total') if m.get('total') is not None else '',
            marketSource='ESPN-carried DraftKings reference' if m else '',marketObservedAt=ctx.get('observedAt',''),executionVerified='false',dataQuality='PREGAME_CONTEXT_UNVERIFIED',signalStrength='RESEARCH SHADOW',releaseStatus='RESEARCH SHADOW - CANONICAL HOLD',
            notes='Frozen foundation research. Final availability, weather and officiating require game-specific review. See Week 11 context evidence.')
        rows.append(row)
        gap = m['spreadHome']-p['projectedSpreadHome'] if m.get('spreadHome') is not None else None
        cards.append('<article class="game"><small>'+html.escape(t.strftime('%a %b %d · %-I:%M %p ET'))+'</small><h2>'+html.escape(g['awayTeam']+' at '+g['homeTeam'])+'</h2>'+f'<p class="projected">{p["projectedAwayPoints"]:.1f} – {p["projectedHomePoints"]:.1f}</p><p>Model home spread {p["projectedSpreadHome"]:+.1f} · Total {p["projectedTotal"]:.1f}</p><p>Market home spread {m.get("spreadHome", "Unavailable")} · Total {m.get("total", "Unavailable")}</p><p>Spread gap {gap if gap is not None else "Unavailable"}</p><small>Research HOLD · Final context pending</small></article>')
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(old[0]),lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    cfg = read('data/config.json')
    cfg.update(currentWeek=11,lastUpdated=iso(stamp()),modelVersion='CFB foundation v1 · Week 11 prospective shadow',publicationStatus=f'{len(games)} Week 11 frozen research forecasts. Final context pending. Canonical HOLD.',currentContextAudit='cfb/pregame/week11-evidence/game-context.json',contextLastUpdated=iso(stamp()))
    write('data/config.json',cfg)
    page = (ROOT/'week-10.html').read_text().replace('Week 10','Week 11').replace('week-10','week-11').replace('week10','week11').replace('November 3–7','November 10–14')
    page = re.sub(r'<div class="grid">.*?</div></main>',lambda m:'<div class="grid">'+''.join(cards)+'</div></main>',page,flags=re.S)
    page = re.sub(r'frozen [^<]+</p>', 'frozen '+html.escape(lock['lockedAt'])+'</p>',page,count=1)
    page = page.replace('market-context.json','game-context.json')
    page = re.sub(r'<h1>CFB Week 11 projections</h1><p>.*?</p>', '<h1>CFB Week 11 projections</h1><p>'+str(len(games))+' FBS games · November 10–14, 2026 · Times Eastern · frozen '+html.escape(lock['lockedAt'])+'</p>', page, count=1)
    page = page.replace('Week 9 archive','Week 10 archive').replace('href="week-9.html"','href="week-10.html"')
    (ROOT/'week-11.html').write_text(page)
    board = read('data/current-matchups.json')
    board['updatedAt'] = iso(stamp())
    board['leagues']['cfb'].update(coverageStatus='FULL_FBS_PROSPECTIVE_SHADOW_RESEARCH')
    for g in board['leagues']['cfb']['games']:
        g.update(projectionStatus='Frozen foundation research. Final context HOLD.',projectionUrl='week-11.html')
    write('data/current-matchups.json',board)
    render(board)
    index = ROOT/'index.html'
    text = index.read_text().replace('CFB Week 10','CFB Week 11').replace('href="week-10.html"','href="week-11.html"')
    text = text.replace('CFB Week 11: 67 matchups posted.','CFB Week 11: 67 frozen research forecasts available.').replace('View the schedule','View Week 11 forecasts and market gaps')
    index.write_text(text)
    print(json.dumps(dict(games=len(games),frozenAt=lock['lockedAt'],modelAsOf=model['asOf'],trainingGames=model['trainingGames'],markets=sum(bool(c.get('market')) for c in contexts),errors=sum(c['status']=='SOURCE_UNAVAILABLE' for c in contexts))))


if __name__ == '__main__':
    main()
