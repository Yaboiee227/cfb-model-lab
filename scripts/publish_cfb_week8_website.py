#!/usr/bin/env python3
from __future__ import annotations
import csv,json,re
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOUNDATION=ROOT/'cfb/research-locks/week-08-foundation-full.json'
SCHEDULE=ROOT/'cfb/pregame/week-08-schedule.json'
MARKETS=ROOT/'data/markets-sportsbooks.json'
OUTPUT=ROOT/'data/projections.csv'
FIELDS=['season','week','date','kickoffET','gameId','awayTeam','awayConference','homeTeam','homeConference','projectedAwayPoints','projectedHomePoints','modelSpreadHome','modelTotal','homeWinProbability','awayWinProbability','marketSpreadHome','marketTotal','marketSource','marketObservedAt','executionVerified','dataQuality','signalStrength','releaseStatus','notes']
ALIASES={'appalachianstate':'appstate','appalachianstatemountaineers':'appstate','floridainternationalpanthers':'floridainternational','fiupanthers':'floridainternational','newmexicostateaggies':'newmexicostate','samhoustonbearkats':'samhouston','massachusettsminutemen':'massachusetts','uconnhuskies':'uconn','miamiflhurricanes':'miami','miamiohredhawks':'miamioh'}
def norm(x):
    n=re.sub(r'[^a-z0-9]','',str(x).lower())
    return ALIASES.get(n,n)
def team_match(a,b):
    x,y=norm(a),norm(b)
    return x==y or (min(len(x),len(y))>=5 and (x.startswith(y) or y.startswith(x)))
def market_for(game, markets):
    ko=datetime.fromisoformat(game['kickoff'].replace('Z','+00:00'))
    for m in markets.get('games',[]):
        try: mk=datetime.fromisoformat(m['commenceTime'].replace('Z','+00:00'))
        except Exception: continue
        if abs((mk-ko).total_seconds())>300: continue
        if team_match(game['homeTeam'],m.get('homeTeam','')) and team_match(game['awayTeam'],m.get('awayTeam','')): return m
    return None
def book_context(m):
    if not m:return ('','','','','')
    for key,label in [('draftkings','DraftKings tracked context'),('fanduel','FanDuel tracked context')]:
        b=(m.get('books') or {}).get(key)
        if not b:continue
        spread=(b.get('spread') or {}).get('home'); total=(b.get('total') or {}).get('point'); observed=b.get('updatedAt') or ''
        if spread is not None and total is not None:return (spread,total,label,observed,key)
    return ('','','','','')
def kickoff_et(iso):
    from zoneinfo import ZoneInfo
    dt=datetime.fromisoformat(iso.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
    return dt.strftime('%-I:%M %p'),dt.strftime('%Y-%m-%d')
def main():
    f=json.loads(FOUNDATION.read_text()); s=json.loads(SCHEDULE.read_text()); markets=json.loads(MARKETS.read_text())
    schedule_by_teams={(norm(g['awayTeam']),norm(g['homeTeam']),g['kickoff']):g for g in s.get('games',[])}
    rows=[]
    for g in sorted(f['games'],key=lambda x:x['kickoff']):
        kickoff,date=kickoff_et(g['kickoff']); m=market_for(g,markets); spread,total,source,observed,_=book_context(m)
        sched=schedule_by_teams.get((norm(g['awayTeam']),norm(g['homeTeam']),g['kickoff']),{})
        rows.append({'season':f['season'],'week':f['week'],'date':date,'kickoffET':kickoff,'gameId':sched.get('gameId') or g['gameId'],'awayTeam':g['awayTeam'],'awayConference':'','homeTeam':g['homeTeam'],'homeConference':'','projectedAwayPoints':f"{g['projectedAwayPoints']:.8f}",'projectedHomePoints':f"{g['projectedHomePoints']:.8f}",'modelSpreadHome':f"{g['projectedSpreadHome']:.8f}",'modelTotal':f"{g['projectedTotal']:.8f}",'homeWinProbability':f"{g['homeWinProbability']:.8f}",'awayWinProbability':f"{100-g['homeWinProbability']:.8f}",'marketSpreadHome':spread,'marketTotal':total,'marketSource':source,'marketObservedAt':observed,'executionVerified':'false','dataQuality':'0.80','signalStrength':'SHADOW','releaseStatus':'RESEARCH SHADOW - CANONICAL HOLD','notes':'Immutable Week 8 foundation projection; market/context layers are non-canonical; final-window checks and publication locks remain separate.'})
    with OUTPUT.open('w',newline='',encoding='utf-8') as fp:
        w=csv.DictWriter(fp,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    assert len(rows)==56,len(rows)
    print(json.dumps({'rows':len(rows),'output':str(OUTPUT.relative_to(ROOT)),'foundationDigest':f.get('lockDigest')},indent=2))
if __name__=='__main__':main()
