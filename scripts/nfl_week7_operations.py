"""Week 7 append-only sportsbook capture. Never changes model or prior locks."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode

ROOT = Path('nfl_data/prospective/week7')
SNAPSHOT = ROOT/'20261021T114427Z'
TEAM_NAMES = dict(zip('NE CHI PIT NO CIN BAL CLE TEN IND MIN MIA NYJ NYG HOU SF ATL TB CAR DEN ARI GB DET LA LV KC SEA DAL PHI'.split(),
 ['New England Patriots','Chicago Bears','Pittsburgh Steelers','New Orleans Saints','Cincinnati Bengals','Baltimore Ravens','Cleveland Browns','Tennessee Titans','Indianapolis Colts','Minnesota Vikings','Miami Dolphins','New York Jets','New York Giants','Houston Texans','San Francisco 49ers','Atlanta Falcons','Tampa Bay Buccaneers','Carolina Panthers','Denver Broncos','Arizona Cardinals','Green Bay Packers','Detroit Lions','Los Angeles Rams','Las Vegas Raiders','Kansas City Chiefs','Seattle Seahawks','Dallas Cowboys','Philadelphia Eagles']))

def utc(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone required')
    return d.astimezone(timezone.utc)

def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'CBModelProjections research','Accept':'application/json'}),timeout=20) as r:
                return json.load(r),dict(r.headers)
        except Exception:
            if attempt==2: raise RuntimeError('Source request failed; URL omitted to protect credentials') from None
            time.sleep(2**attempt)

def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def verify():
    m=json.loads((SNAPSHOT/'manifest.json').read_text())
    for name,digest in m['files'].items():
        if hashlib.sha256((SNAPSHOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen hash mismatch: '+name)
    with (SNAPSHOT/'paired_projections.csv').open() as f:return list(csv.DictReader(f))

def match_event(row,event):
    _,_,a,h=row['game_id'].split('_')
    return event.get('away_team')==TEAM_NAMES[a] and event.get('home_team')==TEAM_NAMES[h] and utc(event['commence_time'])==utc(row['kickoff_utc'])

def lock_from(row,event,book,now):
    ko=utc(row['kickoff_utc'])
    if not match_event(row,event) or book.get('key') not in ['fanduel','draftkings']:return None
    if not ko-timedelta(minutes=30)<=now<ko:return None
    markets={m['key']:m for m in book.get('markets',[])}
    if not {'spreads','totals'}<=markets.keys():return None
    times=[utc(markets[k].get('last_update') or book['last_update']) for k in ['spreads','totals']]
    if not all(ko-timedelta(minutes=30)<=t<=now and (now-t).total_seconds()<=300 for t in times):return None
    spreads=markets['spreads']['outcomes'];totals=markets['totals']['outcomes']
    home=next((x for x in spreads if x['name']==event['home_team']),None)
    away=next((x for x in spreads if x['name']==event['away_team']),None)
    over=next((x for x in totals if x['name']=='Over'),None);under=next((x for x in totals if x['name']=='Under'),None)
    if not all(x and finite(x.get('point')) and finite(x.get('price')) for x in [home,away,over,under]):return None
    if abs(home['point']+away['point'])>1e-8 or over['point']!=under['point']:return None
    return dict(game_id=row['game_id'],book=book['key'],event_id=event['id'],spread_home=home['point'],total=over['point'],
        source='The Odds API / '+book['key'],observed_at=min(times).isoformat(),captured_at=now.isoformat(),
        market_timestamps={k:markets[k].get('last_update') or book['last_update'] for k in ['spreads','totals']},
        prices={'home':home['price'],'away':away['price'],'over':over['price'],'under':under['price']},
        moneyline=markets.get('h2h'),execution_verified=False,
        policy='First qualifying capture. FanDuel primary, DraftKings fallback at that capture; no best-line selection or replacement.')

def write_new(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(data,f,indent=2)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    rows=verify();now=datetime.now(timezone.utc)
    if args.check:
        print(json.dumps({'freeze_verified':True,'games':len(rows),'now':now.isoformat()}));return
    if not utc('2026-10-22T00:00:00Z')<=now<utc('2026-10-27T01:00:00Z'):
        print('Outside Week 7 capture scope; no requests.');return
    active=[r for r in rows if timedelta(0)<utc(r['kickoff_utc'])-now<=timedelta(minutes=35) and not (ROOT/'locks'/f"{r['game_id']}.json").exists()]
    if not active:
        print('No unlocked NFL game in capture window; no requests.');return
    stamp=now.strftime('%Y%m%dT%H%M%S%fZ');audit={'captured_at':now.isoformat(),'games':[r['game_id'] for r in active],'locks_created':[],'failures':[]}
    key=os.environ.get('ODDS_API_KEY')
    if not key:audit['failures'].append('MISSING_ODDS_API_KEY')
    else:
        # Respect the shared CFB quota; no purchase or paid-plan change.
        old=json.loads(Path('data/markets-sportsbooks.json').read_text()) if Path('data/markets-sportsbooks.json').exists() else {}
        remaining=old.get('quota',{}).get('remaining')
        if remaining is not None and remaining<=30:audit['failures'].append('SHARED_QUOTA_RESERVE_REACHED')
        else:
            params=urlencode({'apiKey':key,'bookmakers':'fanduel,draftkings','markets':'spreads,totals,h2h','oddsFormat':'american','dateFormat':'iso',
                'commenceTimeFrom':now.strftime('%Y-%m-%dT%H:%M:%SZ'),'commenceTimeTo':(now+timedelta(minutes=36)).strftime('%Y-%m-%dT%H:%M:%SZ')})
            try:
                data,headers=fetch('https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?'+params)
                captured=datetime.now(timezone.utc)
                audit['quota_remaining']=headers.get('x-requests-remaining')
                write_new(ROOT/'market_captures'/f'{stamp}.json',{'captured_at':captured.isoformat(),'provider':'The Odds API','sport':'americanfootball_nfl','events':data})
                for row in active:
                    events=[e for e in data if match_event(row,e)]
                    if len(events)!=1:audit['failures'].append(row['game_id']+': EVENT_MISSING_OR_DUPLICATE');continue
                    event=events[0];books={b['key']:b for b in event.get('bookmakers',[])}
                    for book in ['fanduel','draftkings']:
                        lock=lock_from(row,event,books.get(book,{}),captured)
                        if lock:
                            write_new(ROOT/'locks'/f"{row['game_id']}.json",lock);audit['locks_created'].append(row['game_id']);break
                    else:audit['failures'].append(row['game_id']+': NO_FRESH_COMPLETE_IN_WINDOW_QUOTE')
            except Exception as e:audit['failures'].append(type(e).__name__+': '+str(e))
    write_new(ROOT/'operations'/f'market_{stamp}.json',audit)
    print(json.dumps(audit))
    if audit['failures']:raise SystemExit(1)

if __name__=='__main__':main()
