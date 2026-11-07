#!/usr/bin/env python3
"""Capture current-game context separately from immutable forecast and market locks.
Requires beautifulsoup4. Raw responses stay in an explicit evidence directory.
"""

import argparse, csv, gzip, hashlib, json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc)


def instant(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n")


def normalized(s):
    return re.sub("[^a-z0-9]", "", s.lower()).replace("hawaii", "hawaii")


def market(o):
    if not o:
        return None
    v = o.get("spread")
    home = o.get("homeTeamOdds") or {}
    away = o.get("awayTeamOdds") or {}
    spread = (
        None
        if v is None
        else -abs(float(v))
        if home.get("favorite")
        else abs(float(v))
        if away.get("favorite")
        else 0.0
        if float(v) == 0
        else None
    )
    return dict(
        spreadHome=spread,
        total=o.get("overUnder"),
        provider=(o.get("provider") or {}).get("name"),
        executionVerified=False,
        eligibleForGrading=False,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, type=Path)
    a = ap.parse_args()
    ev = a.evidence.resolve()
    manifest = json.loads((ev / "manifest.json").read_text())
    by = {x["sourceId"]: x for x in manifest}
    cut = now()

    def raw(key):
        return gzip.decompress((ev / by[key]["rawPath"]).read_bytes())

    def doc(key):
        return json.loads(raw(key))

    def fetch(key, url):
        started = now()
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "CBModelProjections research https://github.com/Yaboiee227/cfb-model-lab"
                    },
                ),
                timeout=22,
            ) as f:
                b = f.read()
            meta = dict(
                sourceId=key,
                url=url,
                requestStartedAt=started.isoformat(),
                observedAt=now().isoformat(),
                sha256=hashlib.sha256(b).hexdigest(),
                rawPath=key + ".gz",
                bytes=len(b),
            )
            (ev / meta["rawPath"]).write_bytes(gzip.compress(b, mtime=0))
            manifest.append(meta)
            by[key] = meta
            return json.loads(b)
        except Exception as e:
            manifest.append(
                dict(sourceId=key, url=url, observedAt=now().isoformat(), error=str(e))
            )
            raise

    # Map NFL games by exact home/away abbreviation in current source schedules.
    alias = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}
    nfl_events = {}
    for k in by:
        if k.startswith("nfl-scoreboard-2026"):
            for e in doc(k).get("events", []):
                c = e["competitions"][0]
                teams = {
                    x["homeAway"]: alias.get(
                        x["team"]["abbreviation"], x["team"]["abbreviation"]
                    )
                    for x in c["competitors"]
                }
                nfl_events[(teams["away"], teams["home"])] = e
    board = json.loads((ROOT / "data/current-matchups.json").read_text())
    jobs = []
    past = []
    for league, slate in board["leagues"].items():
        for g in slate["games"]:
            if instant(g["kickoffUTC"]) <= cut:
                past.append(
                    dict(
                        g,
                        league=league,
                        contextStatus="STARTED_OR_COMPLETED_NOT_RECONSTRUCTED",
                    )
                )
                continue
            if league == "nfl":
                e = nfl_events[(g["away"], g["home"])]
                event = e["id"]
                if instant(e["date"]) != instant(g["kickoffUTC"]):
                    g = {
                        **g,
                        "frozenScheduleKickoffUTC": g["kickoffUTC"],
                        "kickoffUTC": e["date"],
                        "scheduleConflict": True,
                    }
            else:
                event = g["eventId"]
            jobs.append((league, {**g, "eventId": event}))

    def collect(item):
        league, g = item
        sport = "nfl" if league == "nfl" else "college-football"
        key = f"{league}-game-{g['eventId']}"
        url = f"https://site.api.espn.com/apis/site/v2/sports/football/{sport}/summary?event={g['eventId']}"
        row = dict(
            g,
            league=league,
            sourceUrl=url,
            contextStatus="UNAVAILABLE",
            finalAvailabilityVerified=False,
            releaseStatus="HOLD",
            canonicalInfluence=False,
        )
        try:
            d = fetch(key, url)
            meta = by[key]
            c = d["header"]["competitions"][0]
            row.update(observedAt=meta["observedAt"], sourceSha256=meta["sha256"])
            assert str(d["header"]["id"]) == g["eventId"]
            if instant(c["date"]) != instant(g["kickoffUTC"]):
                row.update(
                    scheduleConflict=True,
                    frozenScheduleKickoffUTC=g["kickoffUTC"],
                    kickoffUTC=c["date"],
                )
                g = {**g, "kickoffUTC": c["date"]}
            if (
                instant(meta["observedAt"]) >= instant(g["kickoffUTC"])
                or c["status"]["type"].get("state") != "pre"
            ):
                row["contextStatus"] = "STARTED_DURING_CAPTURE_NOT_USED"
                return row
            info = d.get("gameInfo") or {}
            row.update(
                contextStatus="PREGAME_CONTEXT_CAPTURED",
                venue=info.get("venue") or {},
                officials=info.get("officials") or [],
                weather=info.get("weather"),
                competitors=c["competitors"],
                neutralSite=bool(c.get("neutralSite", g.get("neutralSite", False))),
                teamIds={x["homeAway"]: x["team"]["id"] for x in c["competitors"]},
            )
            odds = d.get("pickcenter") or []
            o = next(
                (
                    x
                    for x in odds
                    if "draft" in str((x.get("provider") or {}).get("name", "")).lower()
                ),
                odds[0] if odds else None,
            )
            row["marketReference"] = market(o)
            row["marketObservedAt"] = meta["observedAt"]
            row["injuryStatus"] = "NO_CURRENT_VERIFIED_REPORT_NOT_CLEARED"
            row["refereeStatus"] = (
                "PUBLISHED_IN_SOURCE"
                if row["officials"]
                else "NOT_POSTED_IN_CHECKED_SOURCE"
            )
            row["weatherStatus"] = (
                "EARLY_ESPN_FORECAST_NOT_FINAL" if row["weather"] else "NOT_AVAILABLE"
            )
            # Postal centroid is explicitly approximate; it is never represented as a stadium observation.
            venue = row["venue"]
            addr = venue.get("address") or {}
            zipcode = addr.get("zipCode")
            country = addr.get("country")
            roof = (
                "INDOOR_SOURCE_FLAG_REQUIRES_ROOF_CONFIRMATION"
                if venue.get("indoor")
                else "OUTDOOR_OR_ROOF_UNVERIFIED"
            )
            row["roofStatus"] = roof
            if zipcode and country in ["USA", "United States"]:
                try:
                    geo = fetch(
                        key + "-postal", f"https://api.zippopotam.us/us/{zipcode}"
                    )
                    place = geo["places"][0]
                    lat, lon = place["latitude"], place["longitude"]
                    p = fetch(
                        key + "-nws-point",
                        f"https://api.weather.gov/points/{lat},{lon}",
                    )
                    u = p["properties"]["forecastHourly"]
                    w = fetch(key + "-nws-hourly", u)["properties"]
                    kick = instant(g["kickoffUTC"])
                    end = kick + timedelta(hours=4)
                    periods = [
                        x
                        for x in w["periods"]
                        if instant(x["startTime"]) < end
                        and instant(x["endTime"]) > kick
                    ]
                    complete = (
                        bool(periods)
                        and instant(periods[0]["startTime"]) <= kick
                        and instant(periods[-1]["endTime"]) >= end
                    )
                    row["nwsWeather"] = dict(
                        sourceUrl=u,
                        issuedAt=w.get("updateTime"),
                        coordinateBasis="Venue postal-code centroid, approximate area forecast; not stadium observation",
                        coordinates=[lat, lon],
                        periods=periods,
                        coverageComplete=complete,
                        finalWindowRefreshRequired=True,
                    )
                    row["weatherStatus"] = (
                        "NWS_EARLY_AREA_FORECAST"
                        if complete
                        else "NWS_INCOMPLETE_WINDOW"
                    )
                except Exception as e:
                    row["weatherError"] = str(e)
            if now() >= instant(g["kickoffUTC"]):
                row["contextStatus"] = "STARTED_DURING_CAPTURE_NOT_USED"
                row.pop("marketReference", None)
        except Exception as e:
            row["error"] = str(e)
        return row

    rows = list(ThreadPoolExecutor(12).map(collect, jobs))
    # Official NFL designation article. Not final inactive lists or a verified starting lineup.
    soup = BeautifulSoup(raw("nfl-official-injuries"), "html.parser")
    reports = {}
    for h in soup.select("h3"):
        ul = h.find_next_sibling("ul")
        if ul:
            reports[h.get_text(" ", strip=True)] = [
                x.get_text(" ", strip=True) for x in ul.select("li")
            ]
    names = {
        "ARI": "CARDINALS",
        "ATL": "FALCONS",
        "BAL": "RAVENS",
        "BUF": "BILLS",
        "CAR": "PANTHERS",
        "CHI": "BEARS",
        "CIN": "BENGALS",
        "CLE": "BROWNS",
        "DAL": "COWBOYS",
        "DEN": "BRONCOS",
        "DET": "LIONS",
        "GB": "PACKERS",
        "HOU": "TEXANS",
        "IND": "COLTS",
        "JAX": "JAGUARS",
        "KC": "CHIEFS",
        "LA": "RAMS",
        "LAC": "CHARGERS",
        "LV": "RAIDERS",
        "MIA": "DOLPHINS",
        "MIN": "VIKINGS",
        "NE": "PATRIOTS",
        "NO": "SAINTS",
        "NYG": "GIANTS",
        "NYJ": "JETS",
        "PHI": "EAGLES",
        "PIT": "STEELERS",
        "SEA": "SEAHAWKS",
        "SF": "49ERS",
        "TB": "BUCCANEERS",
        "TEN": "TITANS",
        "WAS": "COMMANDERS",
    }
    refs = {
        "CIN_ATL": "Craig Wrolstad",
        "DEN_CAR": "Alan Eck",
        "DAL_IND": "Clay Martin",
        "NYJ_KC": "Adrian Hill",
        "DET_MIA": "Land Clark",
        "CLE_NO": "Shawn Hochuli",
        "NYG_PHI": "Bill Vinovich",
        "LA_WAS": "John Hussey",
        "HOU_LAC": "Alex Moore",
        "LV_SF": "Scott Novak",
        "GB_NE": "Alex Kemp",
        "ARI_SEA": "Clete Blakeman",
        "TB_CHI": "Ron Torbert",
        "BUF_MIN": "Carl Cheffers",
    }
    reftext = BeautifulSoup(raw("nfl-officials"), "html.parser").get_text(
        " ", strip=True
    )
    nfl_inj = doc("nfl-injuries")
    nfl_byteam = {str(t["id"]): t for t in nfl_inj["injuries"]}
    officialcfb = []
    for conf in ["SEC", "ACC"]:
        for reportid, r in doc(conf + "-official-public-report").items():
            if r.get("footer", {}).get("date") not in ["2026-11-06", "2026-11-07"]:
                continue
            officialcfb.append(
                dict(
                    reportId=reportid,
                    conference=conf,
                    reportType=r["ReportType"],
                    publishDate=r["publishDate"],
                    postedTime=r["postedTime"],
                    timeZone=r["conferenceTimeZone"],
                    gameDate=r["footer"]["date"],
                    teams=[
                        dict(team=x["teamName"], players=x["rows"]) for x in r["games"]
                    ],
                    sourceUrl="https://app.hdintelligence.com/?conf="
                    + conf
                    + "&source="
                    + conf
                    + "&sport=Football&type=report",
                    observedAt=by[conf + "-official-public-report"]["observedAt"],
                )
            )
    for row in rows:
        if row["contextStatus"] != "PREGAME_CONTEXT_CAPTURED":
            continue
        if row["league"] == "nfl":
            row["officialInjuryReports"] = {
                side: dict(
                    team=row[side],
                    designations=reports.get(names[row[side]], []),
                    reportStatus="OFFICIAL_DESIGNATIONS_NOT_FINAL_INACTIVES"
                    if names[row[side]] in reports
                    else "NO_TEAM_DESIGNATIONS_IN_ARTICLE_YET",
                    sourceUrl=by["nfl-official-injuries"]["url"],
                    observedAt=by["nfl-official-injuries"]["observedAt"],
                )
                for side in ["away", "home"]
            }
            row["injuryStatus"] = "OFFICIAL_DESIGNATIONS_NOT_FINAL_INACTIVES"
            # Secondary updates are filtered to recent dates. Absence never clears a player.
            row["recentPersonnelUpdates"] = {
                side: [
                    dict(
                        player=x["athlete"]["displayName"],
                        position=(x["athlete"].get("position") or {}).get(
                            "abbreviation"
                        ),
                        status=x.get("status"),
                        reportedAt=x.get("date"),
                        summary=x.get("shortComment"),
                    )
                    for x in nfl_byteam.get(row["teamIds"][side], {}).get(
                        "injuries", []
                    )
                    if x.get("date")
                    and cut - timedelta(days=3) <= instant(x["date"]) <= cut
                ]
                for side in ["home", "away"]
            }
            referee = refs.get(row["away"] + "_" + row["home"])
            assert referee in reftext
            row["officials"] = [{"displayName": referee, "position": "Referee"}]
            row["refereeStatus"] = "PUBLISHED_CREW_CHIEF_SUBSTITUTIONS_POSSIBLE"
            row["refereeSource"] = by["nfl-officials"]["url"]
            row["qbAlerts"] = [
                d
                for side in row["officialInjuryReports"].values()
                for d in side["designations"]
                if re.search(r"\bQB\b", d)
            ]
        else:
            # Match BOTH teams and the actual game date; do not attach a report merely by conference.
            comp = {normalized(row["away"]), normalized(row["home"])}
            matches = [
                r
                for r in officialcfb
                if {normalized(t["team"]) for t in r["teams"]} == comp
                and r["gameDate"] == row["dateET"]
            ]
            row["officialAvailabilityReports"] = matches
            if matches:
                row["injuryStatus"] = (
                    "OFFICIAL_CONFERENCE_REPORT_CAPTURED_RECHECK_FINAL_WINDOW"
                )
                row["qbAlerts"] = [
                    {"team": t["team"], "player": x["name"], "status": x["status"]}
                    for r in matches
                    for t in r["teams"]
                    for x in t["players"]
                    if x["name"].startswith("QB ")
                    and x["status"] not in ["Available", "Exempt"]
                ]
    # Full current-game evidence; no completed-game pregame records are manufactured.
    output = dict(
        updatedAt=now().isoformat(),
        collectionStartedAt=cut.isoformat(),
        canonicalInfluence=False,
        forecastChanges=0,
        leagues={
            l: dict(
                week=board["leagues"][l]["week"],
                remainingGames=sum(r["league"] == l for r in rows),
                startedOrPast=sum(r["league"] == l for r in past),
            )
            for l in ["cfb", "nfl"]
        },
        games=rows,
        excludedStartedGames=past,
        sourceWarnings=[
            "ESPN CFB injury feed contains old-season reports; rejected for current clearance.",
            "Covers CFB league trends currently list October 10 games; rejected by kickoff identity.",
            "Covers CFB injuries contain old/opponent-mismatched notes; not used to clear current games.",
            "No official report means unknown, not healthy. Final inactives/availability, roof state and forecasts require kickoff-window rechecks.",
        ],
    )
    dump(ROOT / "data/game-readiness.json", output)
    dump(ev / "manifest.json", manifest)
    compact = [{k: v for k, v in x.items() if k not in ["rawPath"]} for x in manifest]
    dump(
        ROOT / "research/operations/week10-week9-20261107/source-manifest.json", compact
    )
    dump(
        ROOT / "research/operations/week10-week9-20261107/official-cfb-reports.json",
        officialcfb,
    )
    print(
        json.dumps(
            {
                l: {
                    "remaining": sum(r["league"] == l for r in rows),
                    "captured": sum(
                        r["league"] == l
                        and r["contextStatus"] == "PREGAME_CONTEXT_CAPTURED"
                        for r in rows
                    ),
                    "officialReports": sum(
                        r["league"] == l
                        and bool(
                            r.get("officialAvailabilityReports")
                            or r.get("officialInjuryReports")
                        )
                        for r in rows
                    ),
                    "nws": sum(
                        r["league"] == l and bool(r.get("nwsWeather")) for r in rows
                    ),
                }
                for l in ["cfb", "nfl"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
