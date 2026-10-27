from __future__ import annotations
import json, urllib.parse, urllib.request
from datetime import datetime, timezone

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
    dates=sorted({str(g["kickoff"])[:10].replace("-","") for g in projection.get("games",[])})
    out={}
    for d in dates:
        url=BASE[league]+"?"+urllib.parse.urlencode({"dates":d,"limit":1000,**({"groups":80} if league=="cfb" else {})})
        doc=_get(url)
        for e in doc.get("events",[]):
            row=_parse_event(e)
            if row:out[row["sourceGameId"]]=row
    return list(out.values())
