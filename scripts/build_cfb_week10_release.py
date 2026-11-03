#!/usr/bin/env python3
"""Prospective CFB Week 10 foundation-shadow release; never promote to canonical.

This job must begin and freeze all models before first listed kickoff. An
existing immutable research lock is verified, never recreated from results.
"""
from __future__ import annotations
import csv
import datetime as dt
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from cfb_week8_schedule import discover_games, parse_dt
from cfb_foundation_candidate import build
from lock_research_shadow import build_lock, verify
import cfb_shadow_engine as engine

ET=ZoneInfo('America/New_York')
START=parse_dt('2026-11-03T00:00:00-05:00')
END=parse_dt('2026-11-08T00:00:00-05:00')
TRAIN_START=parse_dt('2026-08-20T00:00:00-04:00')
FIRST_KICKOFF=parse_dt('2026-11-03T19:00:00-05:00')

def stamp(): return dt.datetime.now(dt.timezone.utc)
def iso(x): return x.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
def write(path,obj):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def fmt(x):return f'{float(x):.1f}' if x is not None else '—'
def local(kickoff): return parse_dt(kickoff).astimezone(ET)

def fetch_context(g):
    t=stamp(); kickoff=parse_dt(g['kickoff'])
    if t>=kickoff:return {'sourceGameId':g['sourceGameId'],'status':'AFTER_KICKOFF_NOT_CAPTURED','market':None}
    url=f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={g['sourceGameId']}"
    try:
        j=engine.fetch_json(url)
        # ESPN's summary pickcenter is a secondary public sportsbook reference,
        # not a direct-book execution snapshot or an authorized model input.
        odds=(j.get('pickcenter') or [])
        o=next((z for z in odds if 'draft' in str((z.get('provider') or {}).get('name','')).lower()), odds[0] if odds else None)
        spread=total=None
        if o and o.get('spread') is not None:
            a=abs(float(o['spread']))
            home=(o.get('homeTeamOdds') or {})
            away=(o.get('awayTeamOdds') or {})
            if home.get('favorite') is True:spread=-a
            elif away.get('favorite') is True:spread=a
            else:spread=None
        if o and o.get('overUnder') is not None: total=float(o['overUnder'])
        finished=stamp()
        if finished>=kickoff:return {'sourceGameId':g['sourceGameId'],'status':'AFTER_KICKOFF_NOT_CAPTURED','market':None}
        return {'sourceGameId':g['sourceGameId'],'status':'PREGAME_CONTEXT_CAPTURED','observedAt':iso(finished),'source':url,
                'market':{'spreadHome':spread,'total':total,'source':f"ESPN-carried {((o or {}).get('provider') or {}).get('name','sportsbook')} reference" if o else None,
                'directBookExecutionVerified':False},
                'injuryStatus':'NOT_VERIFIED','refereeStatus':'NOT_VERIFIED',
                'warning':'Context only; no numeric model adjustments'}
    except Exception as exc:
        return {'sourceGameId':g['sourceGameId'],'status':'SOURCE_UNAVAILABLE','market':None,'source':url,'error':str(exc)[:240]}

def main():
    cutoff=stamp()
    if cutoff>=FIRST_KICKOFF:raise SystemExit('Cannot initiate full-week prospective freeze after first Week 10 kickoff. Fail closed.')
    games=discover_games(START,END)
    ids={g['sourceGameId'] for g in games}
    assert {'401866453','401866454'} <= ids, 'Tuesday event ID coverage incomplete'
    if not (50<=len(games)<=70):raise SystemExit(f'FBS schedule coverage insufficient: {len(games)}')
    s={'schemaVersion':2,'league':'cfb','season':2026,'week':10,'role':'WEEK_SCHEDULE_STATE','canonicalInfluence':False,
       'dateWindowET':['2026-11-03','2026-11-07'],'observedAt':iso(stamp()),
       'source':'ESPN public FBS team schedules, deduplicated by event ID','gameCount':len(games),'games':games}
    write('cfb/pregame/week-10-schedule.json',s)

    # Only data that existed before cutoff can inform the validated shadow.
    model=build(ROOT/'cfb/pregame/week-10-schedule.json',ROOT/'cfb/validation/week-08-simple-foundation-validation.json',cutoff,TRAIN_START)
    assert model['lockedParameters']=={'alpha':2.5,'halfLifeDays':56,'minTeamAppearances':4}
    assert model['canonicalInfluence'] is False and model['canonicalPromotionAuthorized'] is False
    assert len(model['games'])==len(games)
    ready=[g for g in model['games'] if g['status']=='FOUNDATION_SHADOW_READY']
    if len(ready)<len(games):raise SystemExit(f'All-game model readiness failed: {len(ready)} ready of {len(games)}. Fail closed.')
    lockpath=ROOT/'cfb/research-locks/week-10-foundation-full.json'
    if lockpath.exists():
        lock=read('cfb/research-locks/week-10-foundation-full.json');verify(lock)
        raise SystemExit('Week 10 lock already exists: refusing to regenerate or overwrite')
    locked_at=stamp()
    if any(parse_dt(g['kickoff'])<=locked_at for g in ready):raise SystemExit('First kickoff passed before freeze. Fail closed.')
    lock=build_lock(model,locked_at);verify(lock)
    assert len(lock['games'])==len(games)
    write('cfb/shadow/week-10-foundation-full.json',model)
    write('cfb/research-locks/week-10-foundation-full.json',lock)

    context={}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures={ex.submit(fetch_context,g):g for g in games}
        for fut in as_completed(futures):
            g=futures[fut]
            try: context[g['sourceGameId']]=fut.result()
            except Exception as e: context[g['sourceGameId']]={'status':'SOURCE_UNAVAILABLE','market':None,'error':str(e)[:200]}
    write('cfb/pregame/week10-evidence/market-context.json',{
        'role':'CURRENT_PUBLIC_MARKET_CONTEXT_NOT_EXECUTION_LOCK','observedAt':iso(stamp()),
        'canonicalInfluence':False,'games':[context[g['sourceGameId']] for g in games],
        'note':'Missing/unverified data remain missing; observations after kickoff are excluded.'})

    byid={g['sourceGameId']:g for g in lock['games']}
    oldpath=ROOT/'data/projections.csv'
    with oldpath.open(encoding='utf-8',newline='') as fp:
        old=list(csv.DictReader(fp));fields=list(old[0].keys())
    assert old and {int(r['week']) for r in old}=={9},'Unexpected current CFB feed: refuse to overwrite'
    archive=ROOT/'data/archive/week-09-projections.csv'
    if archive.exists():raise SystemExit('Prior Week 9 archive already exists; investigate before overwrite')
    archive.write_bytes(oldpath.read_bytes())
    records=[];cards=[]
    for g in games:
        proj=byid[g['sourceGameId']];ctx=context[g['sourceGameId']];m=ctx.get('market') or {}
        spread=m.get('spreadHome');total=m.get('total');t=local(g['kickoff'])
        markettime=ctx.get('observedAt') if ctx.get('status')=='PREGAME_CONTEXT_CAPTURED' else ''
        note='Prospectively frozen validated foundation SHADOW; canonical HOLD. Market is a secondary ESPN public reference, not direct execution; injuries, officials and final weather not verified; no numeric adjustments. See Week 10 market context.'
        records.append(dict(season=2026,week=10,date=t.date().isoformat(),kickoffET=t.strftime('%-I:%M %p'),gameId=g['gameId'],
                awayTeam=g['awayTeam'],awayConference='',homeTeam=g['homeTeam'],homeConference='',
                projectedAwayPoints=proj['projectedAwayPoints'],projectedHomePoints=proj['projectedHomePoints'],
                modelSpreadHome=proj['projectedSpreadHome'],modelTotal=proj['projectedTotal'],
                homeWinProbability=proj['homeWinProbability'],awayWinProbability=100-proj['homeWinProbability'],
                marketSpreadHome=spread if spread is not None else '',marketTotal=total if total is not None else '',
                marketSource=m.get('source') or '',marketObservedAt=markettime,executionVerified='false',dataQuality='PREGAME_CONTEXT_UNVERIFIED',
                signalStrength='RESEARCH SHADOW',releaseStatus='RESEARCH SHADOW - CANONICAL HOLD',notes=note))
        gap=(spread-proj['projectedSpreadHome']) if spread is not None else None
        totalgap=(proj['projectedTotal']-total) if total is not None else None
        game=html.escape(f"{g['awayTeam']} at {g['homeTeam']}")
        cards.append(f'<article class="game"><small>{html.escape(t.strftime("%a %b %d · %-I:%M %p ET"))}</small><h2>{game}</h2>'
          f'<p class="projected">{proj["projectedAwayPoints"]:.1f} – {proj["projectedHomePoints"]:.1f}</p>'
          f'<p>Model: home spread {proj["projectedSpreadHome"]:+.1f} · total {proj["projectedTotal"]:.1f} · home win {proj["homeWinProbability"]:.1f}%</p>'
          f'<p>Market reference: home spread {fmt(spread)} · total {fmt(total)}</p>'
          f'<p>Spread gap (market − model): {fmt(gap)} · Total gap (model − market): {fmt(totalgap)}</p>'
          f'<small>Market observed: {html.escape(markettime or "unavailable")} · Research only · Final context pending</small></article>')
    with oldpath.open('w',newline='',encoding='utf-8') as fp:
        writer=csv.DictWriter(fp,fieldnames=fields);writer.writeheader();writer.writerows(records)
    cfg=read('data/config.json')
    cfg.update(currentWeek=10,lastUpdated=iso(stamp()),modelVersion='CFB foundation v1 · Week 10 prospective shadow',
        spreadValidation='HOLD',totalValidation='HOLD',
        publicationStatus=f'{len(records)} Week 10 prospectively frozen research projections · canonical HOLD · final personnel/officiating/weather gates unresolved',
        currentContextAudit='cfb/pregame/week10-evidence/market-context.json',contextLastUpdated=iso(stamp()))
    write('data/config.json',cfg)
    source='cfb/research-locks/week-10-foundation-full.json'
    def render_page():
        return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CFB Week 10 Projections | CB Model</title><style>body{font:16px/1.6 system-ui,sans-serif;background:#0b1423;color:#edf4fa;margin:0}main{max-width:1160px;margin:auto;padding:clamp(14px,3vw,30px)}a{color:#9bd8ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:14px}.game{min-width:0;overflow-wrap:anywhere;padding:20px;background:#17263b;border:1px solid #34465c;border-radius:12px}.game h2{font-size:1.15rem;line-height:1.4}.projected{font-size:1.75rem;font-weight:700;color:#a8e6ce}small{font-size:.8rem;overflow-wrap:anywhere}.notice{padding:18px;background:#332e20;border-radius:12px}.inline{display:flex;gap:1rem;flex-wrap:wrap}nav{margin-bottom:20px}</style></head><body><main><nav class="inline"><a href="index.html?league=cfb">CFB dashboard</a><a href="week-9.html">Week 9 archive</a><a href="index.html?league=nfl">NFL</a><a href="index.html?league=cfb#record">Records</a></nav><h1>CFB Week 10 projections</h1><p>'+str(len(records))+' FBS games · November 3–7, 2026 · Times Eastern · frozen '+html.escape(lock['lockedAt'])+'</p><p class="notice"><strong>Validated foundation SHADOW, canonical HOLD.</strong> Forecasts were frozen prior to the first kickoff and never incorporate target-game results. Markets are dated secondary public references only, not direct-book execution locks. Injury, availability, weather and officials are not cleared. Blank market numbers indicate unavailable references, not 0. No wagers are recommended. Records remain independently graded from saved original snapshots.</p><p>Source: <a href="'+source+'">immutable projection lock</a> · <a href="cfb/pregame/week10-evidence/market-context.json">timestamped market context</a> · <a href="cfb/pregame/week-10-schedule.json">FBS schedule</a></p><div class="grid">'+''.join(cards)+'</div></main></body></html>'
    (ROOT/'week-10.html').write_text(render_page(),encoding='utf-8')
    # Preserve archived Week 9 records and NFL feeds; switch only CFB live controls.
    idx=ROOT/'index.html';raw=idx.read_text(encoding='utf-8')
    replacement='<aside id="current-week-matchups" style="padding:18px;text-align:center"><strong>CFB Week 10: '+str(len(records))+' prospective research projections available.</strong> <a href="week-10.html">Full Week 10 model, market gaps and readiness</a> · <a href="week-9.html">Week 9 archive</a> · <a href="index.html?league=nfl">NFL projections</a><p>Canonical HOLD. Market references are not execution locks. Previous week: 27–28–1 ATS, 23–33 totals, 36–20 SU.</p></aside>'
    raw,n=re.subn(r'<aside id="current-week-matchups".*?</aside>',lambda _:replacement,raw,count=1,flags=re.S)
    assert n==1, 'Homepage current-week banner not found'
    raw=raw.replace('<a href="tonight.html">Tonight: current projections, availability, weather and reported officials →</a>', '<a href="week-10.html">CFB Week 10: current projections and market references →</a>')
    raw=raw.replace('<strong>Week 9 · Canonical HOLD</strong> — Week 9 frozen research projections and market references are available. <a href="week-9.html">View game readiness, current context and lock windows →</a>',
        '<strong>Week 10 · Canonical HOLD</strong> — Frozen prospective research projections are published; final personnel, officiating and weather gates remain unresolved. <a href="week-10.html">View current week projections and market references →</a>')
    idx.write_text(raw,encoding='utf-8')
    mx=read('data/current-matchups.json')
    mx['updatedAt']=iso(stamp());mx['projectionStatus']='CFB_WEEK10_RESEARCH_PUBLISHED_NFL_SEPARATE'
    mx['leagues']['cfb']={'week':10,'coverageStatus':'FULL_FBS_PROSPECTIVE_SHADOW_RESEARCH', 'games':[
        dict(eventId=g['sourceGameId'],away=g['awayTeam'],home=g['homeTeam'],kickoffUTC=g['kickoff'],
             dateET=local(g['kickoff']).date().isoformat(),kickoffET=local(g['kickoff']).strftime('%a %b %d · %I:%M %p EST'),
             neutralSite=g['neutralSite'],venue=(g.get('venue') or {}).get('name'),
             source=f'https://www.espn.com/college-football/game/_/gameId/{g["sourceGameId"]}',
             projectionStatus='Frozen foundation research; canonical HOLD',projectionUrl='week-10.html') for g in games]}
    write('data/current-matchups.json',mx)
    print(json.dumps({'status':'WEEK10_SHADOW_PUBLISHED','games':len(records),'lock':lock['lockedAt'],
        'referenceMarkets':sum(bool(x.get('market') and x['market'].get('spreadHome') is not None) for x in context.values()),
        'canonicalInfluence':False,'modelAsOf':model['asOf'],'firstGame':games[0]['gameId']},indent=2))
if __name__=='__main__':main()