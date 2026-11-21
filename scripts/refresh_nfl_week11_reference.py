#!/usr/bin/env python3
"""Extract NFL Week 11 comparison quotes from the timestamped ESPN scoreboard.

Only pregame, exact-team, kickoff-matched events are considered; this is never a
betting recommendation or grading lock. ESPN's close field is a display quote,
not a certified closing line. The source retrieval time is not a bookmaker update.
"""
import json, math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def dt(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('timestamp lacks timezone')
    return d.astimezone(timezone.utc)
def build(freeze, feed):
    if freeze['week'] != 11 or freeze['season'] != 2026 or freeze['canonicalInfluence'] is not False or feed['league'] != 'nfl' or feed['week'] != 11:
        raise ValueError('wrong league/week or invalid forecast')
    observed=dt(feed['refreshedAt']); aliases={'WSH':'WAS','LAR':'LA'}
    byid={}
    for e in feed['events']:
        c=e['competitions'][0]; teams={x['homeAway']:aliases.get(x['team']['abbreviation'],x['team']['abbreviation']) for x in c['competitors']}
        key=(teams['away'],teams['home'])
        if key in byid: raise ValueError('duplicate matchup')
        byid[key]=e
    games=[]
    for g in freeze['games']:
        e=byid.get((g['away'],g['home']))
        if not e or e['status']['type']['name']!='STATUS_SCHEDULED': continue
        kickoff=dt(g['kickoffUTC'])
        if abs((dt(e['date'])-kickoff).total_seconds())>300 or observed>=kickoff: continue
        books=[o for o in e['competitions'][0].get('odds',[]) if o.get('provider',{}).get('name','').replace(' ','').lower()=='draftkings']
        if len(books)!=1: continue
        try:
            book=books[0]; p=book['pointSpread']; t=book['total']; home=float(p['home']['close']['line']); away=float(p['away']['close']['line']); over=float(t['over']['close']['line'].lstrip('oO')); under=float(t['under']['close']['line'].lstrip('uU'))
            if not all(math.isfinite(x) for x in (home,away,over,under)) or abs(home+away)>1e-8 or over != under or over<=0: continue
        except (KeyError,TypeError,ValueError): continue
        model=float(g['modelSpreadHome']);games.append({'gameId':g['gameId'],'eventId':e['id'],'away':g['away'],'home':g['home'],'kickoffUtc':g['kickoffUTC'],'marketSpreadHome':home,'marketTotal':over,'modelSpreadHome':model,'gapHome':home-model,'marketSource':'ESPN / DraftKings comparison reference','marketObservedAt':feed['refreshedAt'],'eligibleForGrading':False,'executionVerified':False})
    return {'observedAt':feed['refreshedAt'],'provider':'DraftKings via ESPN','source':'ESPN public NFL scoreboard; retrieval time is not bookmaker update time','eligibleForGrading':False,'executionVerified':False,'games':games,'note':'Scheduled games only. Comparison reference, not a grading lock or certified closing quote.'}
def main():
    freeze=json.loads((ROOT/'nfl/research-projections/week-11.json').read_text());feed=json.loads((ROOT/'nfl_data/site/live-scoreboard.json').read_text());out=build(freeze,feed)
    path=ROOT/'nfl_data/site/market-reference.json';path.write_text(json.dumps(out,indent=2)+'\n');print('Scheduled matched market comparisons:',len(out['games']),'as of',out['observedAt'])
if __name__=='__main__':main()
