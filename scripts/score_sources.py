from __future__ import annotations
import json, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE={"nfl":"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard","cfb":"https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"}

def _get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"CBModelRecordTracker/1.0"})
    with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)

def _status(event):
    t=((event.get("status") or {}).get("type") or {})
    name=str(t.get("name","")).upper();desc=str(t.get("description","")).upper()
    if t.get("completed") or name=="STATUS_FINAL" or desc.startswith("FINAL"):return "FINAL"
    if "POSTPON" in name+desc:return "POSTPONED"
    if "CANCEL" in name+desc:return "CANCELLED"
    return "PENDING"

def _parse_event(event):
    comp=(event.get("competitions") or [{}])[0];teams=comp.get("competitors") or []
    home=next((x for x in teams if x.get("homeAway")=="home"),None);away=next((x for x in teams if x.get("homeAway")=="away"),None)
    if not home or not away:return None
    hs=int(float(home.get("score") or 0));as_=int(float(away.get("score") or 0))
    for c,s in ((home,hs),(away,as_)):
        ls=c.get("linescores") or []
        if ls and _status(event)=="FINAL":
            total=round(sum(float(x.get("value", x.get("displayValue")) or 0) for x in ls))
            if total!=s:raise RuntimeError(f"ESPN score/linescore mismatch for event {event.get('id')}")
    period=int((event.get("status") or {}).get("period") or 0)
    return {"sourceGameId":str(event.get("id")),"awayTeam":away.get("team",{}).get("location") or away.get("team",{}).get("displayName") or away.get("team",{}).get("shortDisplayName"),"homeTeam":home.get("team",{}).get("location") or home.get("team",{}).get("displayName") or home.get("team",{}).get("shortDisplayName"),"awayScore":as_,"homeScore":hs,"status":_status(event),"overtime":period>4,"source":"ESPN","sourceUpdatedAt":datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}

def fetch_scores_for_projection(league,projection):
    dates = {str(g['kickoff'])[:10].replace('-', '') for g in projection.get('games', [])}
    for game in projection.get('games', []):
        kickoff = datetime.fromisoformat(str(game['kickoff']).replace('Z', '+00:00'))
        if kickoff.tzinfo is not None:
            dates.add(kickoff.astimezone(ZoneInfo('America/New_York')).strftime('%Y%m%d'))
    dates = sorted(dates)
    out={}
    for d in dates:
        url=BASE[league]+"?"+urllib.parse.urlencode({"dates":d,"limit":1000,**({"groups":80} if league=="cfb" else {})})
        doc=_get(url)
        for e in doc.get("events",[]):
            row=_parse_event(e)
            if row:out[row["sourceGameId"]]=row
    missing = {str(g['sourceGameId']) for g in projection.get('games', [])
               if g.get('sourceGameId') and str(g['sourceGameId']) not in out}

    def fetch_missing(source_id):
        try:
            url = BASE[league].replace('/scoreboard', '/summary')+'?'+urllib.parse.urlencode({'event': source_id})
            header = _get(url)['header']
            if str(header['id']) != source_id:
                return None
            competition = header['competitions'][0]
            return _parse_event(dict(header, status=competition['status']))
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        for row in pool.map(fetch_missing, sorted(missing)):
            if row:
                out[row['sourceGameId']] = row
    return list(out.values())
