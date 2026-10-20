#!/usr/bin/env python3
"""Discover the full Oct. 20-24, 2026 FBS-vs-FBS slate from ESPN team schedules.

This is schedule metadata only. It does not use scores, markets, ratings, or
post-kickoff information. Team schedules are aggregated from ESPN's FBS-only
team universe and deduplicated by ESPN event ID. Human-facing game IDs use the
Eastern game date so evening kickoffs do not roll into the next UTC date.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import extract_grouped_team_ids

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
ESPN_FBS_TEAMS = "https://site.web.api.espn.com/apis/site/v2/sports/football/college-football/teams"
EASTERN = ZoneInfo("America/New_York")
MIN_EXPECTED_GAMES = 50
MAX_EXPECTED_GAMES = 65


def parse_dt(value: str) -> datetime:
    return engine.parse_dt(value)


def eastern_game_date(dt: datetime) -> str:
    return dt.astimezone(EASTERN).date().isoformat()


def team_display(team: dict[str, Any]) -> str:
    for key in ("location", "shortDisplayName", "displayName", "name", "abbreviation"):
        if team.get(key):
            return str(team[key]).strip()
    raise ValueError(f"team lacks display name: {team}")


def discover_fbs_ids() -> list[str]:
    params=urlencode({"groups":80,"groupType":"conference","enable":"groups"})
    doc=engine.fetch_json(f"{ESPN_FBS_TEAMS}?{params}")
    ids=extract_grouped_team_ids(doc)
    if not (120 <= len(ids) <= 180):
        raise RuntimeError(f"implausible FBS team universe: {len(ids)}")
    return ids


def discover_games(start: datetime, end: datetime, season: int=2026) -> list[dict[str, Any]]:
    fbs_ids=discover_fbs_ids()
    fbs_set=set(fbs_ids)
    events: dict[str, dict[str, Any]]={}
    failures=[]

    def load(team_id: str):
        params=urlencode({"season":season,"seasontype":2})
        return team_id,engine.fetch_json(f"{ESPN_SITE_BASE}/teams/{team_id}/schedule?{params}")

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures=[pool.submit(load,tid) for tid in fbs_ids]
        for fut in as_completed(futures):
            try:
                _tid,doc=fut.result()
            except Exception as exc:
                failures.append(str(exc));continue
            for event in doc.get("events",[]):
                comps=event.get("competitions") or []
                if not comps: continue
                comp=comps[0]
                try:
                    kickoff=parse_dt(comp.get("date") or event.get("date"))
                except Exception:
                    continue
                if not (start <= kickoff < end):
                    continue
                sides={c.get("homeAway"):c for c in comp.get("competitors",[]) if c.get("homeAway") in {"home","away"}}
                if "home" not in sides or "away" not in sides: continue
                h,a=sides["home"],sides["away"]
                ht=h.get("team") or {};at=a.get("team") or {}
                hid=str(ht.get("id") or "");aid=str(at.get("id") or "")
                if hid not in fbs_set or aid not in fbs_set:
                    continue
                gid=str(event.get("id") or comp.get("id") or "")
                if not gid: continue
                venue=comp.get("venue") or {}
                address=venue.get("address") or {}
                away=team_display(at);home=team_display(ht)
                game_date=eastern_game_date(kickoff)
                events[gid]={
                    "gameId": f"{game_date}-{engine.canonical_school(away).upper()}-{engine.canonical_school(home).upper()}",
                    "sourceGameId": gid,
                    "gameDateET": game_date,
                    "awayTeam": away,
                    "homeTeam": home,
                    "awayTeamId": aid,
                    "homeTeamId": hid,
                    "kickoff": engine.iso(kickoff),
                    "neutralSite": bool(comp.get("neutralSite",False)),
                    "venue": {
                        "name": venue.get("fullName"),
                        "city": address.get("city"),
                        "state": address.get("state"),
                    },
                    "status": (((comp.get("status") or {}).get("type") or {}).get("name")),
                }

    games=sorted(events.values(),key=lambda g:(g["kickoff"],g["awayTeam"],g["homeTeam"]))
    if len(games) < MIN_EXPECTED_GAMES or len(games) > MAX_EXPECTED_GAMES:
        raise RuntimeError(f"Week 8 FBS schedule coverage failed: {len(games)} games outside [{MIN_EXPECTED_GAMES},{MAX_EXPECTED_GAMES}], scheduleFailures={len(failures)}")
    return games


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--start',default='2026-10-20T00:00:00-04:00')
    ap.add_argument('--end',default='2026-10-25T00:00:00-04:00')
    ap.add_argument('--output',default='cfb/pregame/week-08-schedule.json')
    args=ap.parse_args()
    start=parse_dt(args.start);end=parse_dt(args.end)
    games=discover_games(start,end)
    out={
        "schemaVersion":2,"league":"cfb","season":2026,"week":8,
        "role":"WEEK_SCHEDULE_STATE","canonicalInfluence":False,
        "dateWindowET":["2026-10-20","2026-10-24"],
        "gameIdDateConvention":"America/New_York game date",
        "observedAt":engine.iso(datetime.now(timezone.utc)),
        "source":"ESPN public FBS grouped team universe + 2026 regular-season team schedules",
        "gameCount":len(games),"games":games,
    }
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    by_day={}
    for g in games:
        day=g['gameDateET']
        by_day[day]=by_day.get(day,0)+1
    print(json.dumps({"gameCount":len(games),"byEasternGameDate":by_day,"first":games[:3],"last":games[-3:]},indent=2))


if __name__=='__main__':
    main()
