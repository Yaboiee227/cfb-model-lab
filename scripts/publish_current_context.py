#!/usr/bin/env python3
"""Attach current context, descriptive trends and market comparisons; no forecast edits."""

import argparse, csv, gzip, hashlib, html, json, re
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


def norm(s):
    import unicodedata

    n = re.sub(
        "[^a-z0-9]",
        "",
        unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode(),
    )
    aliases = {
        "appalachianstate": "appstate",
        "ucf": "centralflorida",
        "floridast": "floridastate",
        "iowast": "iowastate",
        "oklahomast": "oklahomastate",
        "kansasst": "kansasstate",
        "ohiost": "ohiostate",
        "pennst": "pennstate",
        "michiganst": "michiganstate",
        "arizonast": "arizonastate",
        "mississippist": "mississippistate",
        "ulm": "ulmonroe",
        "latech": "louisianatech",
    }
    return aliases.get(n, n)


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", type=Path, required=True)
    a = ap.parse_args()
    ev = a.evidence
    meta = json.loads((ev / "manifest.json").read_text())
    by = {x["sourceId"]: x for x in meta}
    audit = ROOT / "research/operations/week10-week9-20261107"
    data = json.loads((ROOT / "data/game-readiness.json").read_text())
    checked = datetime.now(timezone.utc).isoformat()
    data["updatedAt"] = checked

    def raw(k):
        return gzip.decompress((ev / by[k]["rawPath"]).read_bytes())

    def doc(k):
        return json.loads(raw(k))

    reports = []
    for conf in ["SEC", "ACC", "B10", "B12", "American"]:
        if conf + "-official-public-report" not in by:
            continue
        for rid, r in doc(conf + "-official-public-report").items():
            if r.get("ReportType") == "Report Pending":
                continue
            if r.get("footer", {}).get("date") not in ["2026-11-06", "2026-11-07"]:
                continue
            reports.append(
                dict(
                    reportId=rid,
                    conference=conf,
                    reportType=r["ReportType"],
                    publishDate=r["publishDate"],
                    postedTime=r["postedTime"],
                    timeZone=r["conferenceTimeZone"],
                    gameDate=r["footer"]["date"],
                    teams=[
                        dict(
                            team=x["teamName"],
                            players=[
                                p
                                for p in x["rows"]
                                if p["status"] != "Available"
                                or p["name"].startswith("QB ")
                            ],
                        )
                        for x in r["games"]
                    ],
                    sourceUrl="https://app.hdintelligence.com/?conf="
                    + conf
                    + "&source="
                    + conf
                    + "&sport=Football&type=report",
                    observedAt=by[conf + "-official-public-report"]["observedAt"],
                )
            )
    for source, conf in [
        ("sunbelt-official-report", "Sun Belt"),
        ("pac12-official-report", "Pac-12"),
    ]:
        for g in doc(source).get("games", []):
            if not g.get("dateISO", "").startswith("2026-11-0"):
                continue
            reports.append(
                dict(
                    reportId=g["gameId"],
                    conference=conf,
                    reportType=g.get("notes", "Designation report"),
                    gameDate=g["dateISO"],
                    publishedAt=g.get("updatedAtUTC"),
                    teams=[
                        dict(
                            team=g[s]["name"],
                            players=[
                                dict(
                                    name=p.get("position", "") + " " + p["name"],
                                    status=p["status"],
                                )
                                for p in g[s].get("players", [])
                            ],
                        )
                        for s in ["away", "home"]
                    ],
                    sourceUrl=by[source]["url"],
                    observedAt=by[source]["observedAt"],
                )
            )
    projections = {
        l: list(
            csv.DictReader(
                (
                    ROOT
                    / (
                        "data/projections.csv"
                        if l == "cfb"
                        else "nfl_data/site/projections.csv"
                    )
                ).open()
            )
        )
        for l in ["cfb", "nfl"]
    }
    nflf = json.loads((ROOT / "nfl/research-projections/week-09.json").read_text())
    nflf = {g["gameId"]: g for g in nflf["games"]}
    cfbrows = projections["cfb"]
    cfbindex = {(norm(r["awayTeam"]), norm(r["homeTeam"])): r for r in cfbrows}
    nflindex = {r["gameId"]: r for r in projections["nfl"]}
    for r in data["games"]:
        if r["contextStatus"] != "PREGAME_CONTEXT_CAPTURED":
            continue
        if r["league"] == "cfb":
            pair = {norm(r["away"]), norm(r["home"])}
            matches = [
                d
                for d in reports
                if {norm(x["team"]) for x in d["teams"]} == pair
                and d["gameDate"] == r["dateET"]
            ]
            r["officialAvailabilityReports"] = matches
            if matches:
                r["injuryStatus"] = (
                    "OFFICIAL_CONFERENCE_REPORT_CAPTURED_RECHECK_FINAL_WINDOW"
                )
                r["qbAlerts"] = [
                    {"team": t["team"], "player": p["name"], "status": p["status"]}
                    for d in matches
                    for t in d["teams"]
                    for p in t["players"]
                    if p["name"].startswith("QB ")
                    and p["status"] not in ["Available", "Exempt"]
                ]
            p = cfbindex.get((norm(r["away"]), norm(r["home"])))
            assert p, (r["away"], r["home"])
        else:
            p = nflindex[r["gameId"]]
        r["projectionGameId"] = p["gameId"]
        r["baselineProjection"] = {
            k: float(p[k])
            for k in [
                "modelSpreadHome",
                "modelTotal",
                "projectedAwayPoints",
                "projectedHomePoints",
            ]
        }
        r["baselineProjection"]["homeWinProbability"] = (
            float(p["homeWinProbability"]) if p.get("homeWinProbability") else None
        )
        market = r.get("marketReference") or {}
        ms = market.get("spreadHome")
        mt = market.get("total")
        r["modelMarketComparison"] = dict(
            spreadGapHome=None if ms is None else ms - float(p["modelSpreadHome"]),
            totalGapOver=None if mt is None else float(p["modelTotal"]) - mt,
            role="CONTEXT_ONLY_NOT_GRADING_LOCK",
        )
        r["contextAlerts"] = []
        if r.get("scheduleConflict") and r.get("gameId") == "2026_09_LV_SF":
            r["scheduleConfirmationSource"] = (
                "https://www.raiders.com/news/how-to-watch-listen-to-and-livestream-raiders-at-49ers"
            )
            r["contextAlerts"].append(
                "KICKOFF_SOURCE_CONFLICT: NFL and Raiders schedules list 4:25 p.m. ET. The original freeze recorded 4:05 p.m. ET."
            )
        if r["league"] == "nfl" and r["gameId"] == "2026_09_ARI_SEA":
            r["contextAlerts"] += [
                "QB_CHANGE_NOT_REPRESENTED_IN_FORECAST: Seattle plans Drew Lock for injured Sam Darnold; Arizona changed to Gardner Minshew.",
                "SEATTLE_PERSONNEL_BREAK: team report lists Charles Cross, Quenton Nelson, Leonard Williams, Uchenna Nwosu and Rashid Shaheed out.",
            ]
            r["qbChange"] = True
            r["contextAlertSource"] = by["seattle-qb-update"]["url"]
        if r.get("qbAlerts"):
            r["contextAlerts"].append(
                "QB_AVAILABILITY_REQUIRES_REVIEW; no validated personnel-point adjustment is applied."
            )
        # Last-five straight-up form is calculated from source final scores before capture.
        r["formTrends"] = []
        summary = doc(f"{r['league']}-game-{r['eventId']}")
        for f in summary.get("lastFiveGames", []):
            teamid = str(f["team"]["id"])
            side = next((s for s, i in r["teamIds"].items() if str(i) == teamid), None)
            if not side:
                continue
            games = [
                g
                for g in f.get("events", [])
                if g.get("gameResult") in ["W", "L", "T"]
                and dt(g["gameDate"]) < dt(r["observedAt"])
                and g["gameDate"].startswith("2026-")
            ]
            games = sorted(games, key=lambda g: dt(g["gameDate"]), reverse=True)[:5]
            if len(games) < 5:
                continue
            wins = sum(g["gameResult"] == "W" for g in games)
            loss = sum(g["gameResult"] == "L" for g in games)
            ties = 5 - wins - loss
            points = (
                side
                if wins > loss
                else ("away" if side == "home" else "home")
                if loss > wins
                else None
            )
            prob = r["baselineProjection"]["homeWinProbability"]
            modelside = (
                None
                if prob is None
                else "home"
                if prob > 50.5
                else "away"
                if prob < 49.5
                else None
            )
            state = (
                "NO_MODEL_LEAN"
                if not modelside or not points
                else "ALIGNS"
                if modelside == points
                else "CONFLICTS"
            )
            r["formTrends"].append(
                dict(
                    team=r[side],
                    record=f"{wins}-{loss}" + (f"-{ties}" if ties else ""),
                    sampleSize=5,
                    trendType="SU_RECENT_FORM",
                    pointsTo=points,
                    alignment=state,
                    sourceUrl=r["sourceUrl"],
                    observedAt=r["observedAt"],
                    eventIds=[g["id"] for g in games],
                    note="Descriptive five-game form only; not an estimated probability or validated feature. Both aligned and conflicting records are retained.",
                )
            )
        # Trim verbose provider presentation metadata; original source bytes are preserved separately.
        r.pop("competitors", None)
        if r.get("nwsWeather"):
            fields = [
                "startTime",
                "endTime",
                "temperature",
                "temperatureUnit",
                "windSpeed",
                "windDirection",
                "probabilityOfPrecipitation",
                "shortForecast",
            ]
            r["nwsWeather"]["periods"] = [
                {k: p.get(k) for k in fields} for p in r["nwsWeather"]["periods"]
            ]
        if r.get("recentPersonnelUpdates"):
            for updates in r["recentPersonnelUpdates"].values():
                for update in updates:
                    update.pop("summary", None)
    dump(audit / "official-cfb-reports.json", reports)
    # Keep old trend file byte-for-byte before switching the active week.
    old = ROOT / "nfl_data/site/nfl-trends.json"
    archive = ROOT / "nfl_data/site/archive/week8-before-week9/nfl-trends.json"
    if not archive.exists():
        archive.write_bytes(old.read_bytes())
    nick = {
        "CIN": "Bengals",
        "ATL": "Falcons",
        "LA": "Rams",
        "WAS": "Commanders",
        "CLE": "Browns",
        "NO": "Saints",
        "DET": "Lions",
        "MIA": "Dolphins",
        "NYJ": "Jets",
        "KC": "Chiefs",
        "DEN": "Broncos",
        "CAR": "Panthers",
        "NYG": "Giants",
        "PHI": "Eagles",
        "DAL": "Cowboys",
        "IND": "Colts",
        "HOU": "Texans",
        "LAC": "Chargers",
        "LV": "Raiders",
        "SF": "49ers",
        "GB": "Packers",
        "NE": "Patriots",
        "ARI": "Cardinals",
        "SEA": "Seahawks",
        "TB": "Buccaneers",
        "CHI": "Bears",
        "BUF": "Bills",
        "MIN": "Vikings",
    }
    nflgames = [g for g in data["games"] if g["league"] == "nfl"]
    trends = []
    rejected = []
    soup = BeautifulSoup(raw("nfl-trends"), "html.parser")
    for card in soup.select("article.matchup-league-trends-card"):
        time = card.find("time")
        title = card.find("h2")
        parts = title.get_text(" ", strip=True).split(" @ ") if title else []
        if not time or len(parts) != 2:
            continue
        # Exact source nickname pair from the accessible link label, plus kickoff identity.
        label = title.find("a").get("aria-label", "")
        matches = [
            g
            for g in nflgames
            if nick[g["away"]] in label
            and nick[g["home"]] in label
            and dt(time["datetime"]) == dt(g["kickoffUTC"])
        ]
        if len(matches) != 1:
            rejected.append(
                dict(matchup=" @ ".join(parts), reason="MATCHUP_OR_KICKOFF_MISMATCH")
            )
            continue
        g = matches[0]
        market = g.get("marketReference") or {}
        spread = market.get("spreadHome")
        favorite = (
            "home"
            if spread is not None and spread < 0
            else "away"
            if spread is not None and spread > 0
            else None
        )
        for li in card.select("li"):
            text = li.get_text(" ", strip=True)
            m = re.search(r"\b(\d+)-(\d+)(?:-(\d+))?\b", text)
            reason = None
            if not m:
                continue
            # Ignore conditions not independently checked in this pass; never label them applicable.
            if any(
                x in text.lower()
                for x in [
                    "after ",
                    "following ",
                    "vs. ",
                    " on grass",
                    " on fieldturf",
                    "in week ",
                    "in november",
                ]
            ):
                reason = "SITUATIONAL_CONDITION_NOT_INDEPENDENTLY_VERIFIED"
            subjectside = next(
                (s for s in ["away", "home"] if nick[g[s]] in text), None
            )
            points = None
            tt = (
                "TOTAL"
                if text.startswith(("Over ", "Under "))
                else "ATS"
                if " ATS " in text
                else None
            )
            if not tt:
                continue
            if tt == "TOTAL":
                points = "over" if text.startswith("Over ") else "under"
            elif text.startswith("Home team"):
                points = "home"
            elif text.startswith(("Favorite", "Underdog")):
                points = (
                    favorite
                    if text.startswith("Favorite")
                    else ("away" if favorite == "home" else "home")
                    if favorite
                    else None
                )
            else:
                points = subjectside
            if (
                "as an underdog" in text
                or "as a home underdog" in text
                or "as a road underdog" in text
            ):
                if not subjectside or not favorite or subjectside == favorite:
                    reason = "CURRENT_UNDERDOG_CONDITION_FALSE_OR_UNKNOWN"
            if (
                "as a favorite" in text
                or "as a road favorite" in text
                or "as a home favorite" in text
            ):
                if not subjectside or not favorite or subjectside != favorite:
                    reason = "CURRENT_FAVORITE_CONDITION_FALSE_OR_UNKNOWN"
            if g.get("neutralSite") and (
                "home games" in text
                or "road games" in text
                or "home underdog" in text
                or "road underdog" in text
                or "home favorite" in text
                or "road favorite" in text
            ):
                reason = "NEUTRAL_SITE_NOT_HOME_OR_ROAD"
            if (
                "home games" in text
                or "home underdog" in text
                or "home favorite" in text
            ) and subjectside != "home":
                reason = "HOME_CONDITION_FALSE"
            if (
                "road games" in text
                or "road underdog" in text
                or "road favorite" in text
            ) and subjectside != "away":
                reason = "ROAD_CONDITION_FALSE"
            if not points:
                reason = "DIRECTION_NOT_RESOLVED"
            if reason:
                rejected.append(
                    dict(gameId=g["gameId"], record=m.group(), reason=reason)
                )
                continue
            n = sum(int(x or 0) for x in m.groups())
            tail = text[m.end() :].strip()
            tail = re.sub(r"^ATS in their |^in ", "", tail).rstrip(".")
            tail = tail.replace("their last", "last")
            subject = g[subjectside] if subjectside else "Matchup"
            summary = (
                f"{subject}: {m.group()} "
                + (
                    "Over"
                    if points == "over"
                    else "Under"
                    if points == "under"
                    else "ATS"
                )
                + "; "
                + tail
            )
            t = dict(
                id=f"2026-w9-context-{len(trends) + 1}",
                gameId=g["gameId"],
                season=2026,
                week=9,
                matchup={"away": g["away"], "home": g["home"]},
                subject="TOTAL"
                if tt == "TOTAL"
                else g[subjectside]
                if subjectside
                else g[points],
                trendType=tt,
                alignmentTarget="total" if tt == "TOTAL" else "spread",
                text=summary[:180],
                pointsTo=points,
                sampleSize=n,
                record=m.group(),
                sourceName="Covers · reported matchup statistics",
                sourceUrl=by["nfl-trends"]["url"],
                observedAt=by["nfl-trends"]["observedAt"],
                tags=[
                    "CONTEXT_ONLY",
                    "SOURCE_REPORTED_NOT_INDEPENDENTLY_RECOMPUTED",
                    "SMALL_SAMPLE",
                    "ROSTER_CHANGE_CAUTION",
                ],
            )
            gap = g["modelMarketComparison"][
                "totalGapOver" if tt == "TOTAL" else "spreadGapHome"
            ]
            band = 1 if tt == "TOTAL" else 0.25
            lean = (
                None
                if gap is None or abs(gap) <= band
                else ("over" if gap > 0 else "under")
                if tt == "TOTAL"
                else ("home" if gap > 0 else "away")
            )
            t["alignment"] = (
                "NO_MODEL_LEAN"
                if lean is None
                else "ALIGNS"
                if lean == points
                else "CONFLICTS"
            )
            trends.append(t)
    td = dict(
        schemaVersion=1,
        season=2026,
        week=9,
        lastUpdated=by["nfl-trends"]["observedAt"],
        status="SOURCE_REVIEWED_CONTEXT_ONLY",
        source={"name": "Covers", "url": by["nfl-trends"]["url"]},
        alignmentConfig={
            "spreadNeutralBand": 0.25,
            "totalNeutralBand": 1,
            "moneylineNeutralBandPct": 0.5,
        },
        coverage={
            "entryCount": len(trends),
            "gamesWithVerifiedEntries": len({t["gameId"] for t in trends}),
            "currentSlateGames": 14,
            "fullScheduledSlateGames": 15,
            "gamesWithResearchProjections": 14,
            "method": "Retain eligible reported trends in both directions. Match exact pair and kickoff; exclude unverified situation predicates, false favorite/home/road predicates and mismatched kickoff.",
        },
        notes="Small descriptive source-reported samples, not validated forecast features. No probability, confidence or numerical adjustment. CFB Covers trend source rejected as stale.",
        trends=trends,
    )
    dump(old, td)
    dump(
        audit / "trend-filter-audit.json",
        {
            "retained": len(trends),
            "excluded": rejected,
            "cfbSourceRejected": "October 10 matchup dates fail current-week identity",
            "aligned": sum(t["alignment"] == "ALIGNS" for t in trends),
            "conflicting": sum(t["alignment"] == "CONFLICTS" for t in trends),
        },
    )
    # Current NFL references are a separate runtime overlay. The original CSV market snapshot is unchanged.
    marketgames = []
    for g in nflgames:
        m = g.get("marketReference") or {}
        p = g["baselineProjection"]
        if m.get("spreadHome") is None or m.get("total") is None:
            continue
        marketgames.append(
            dict(
                gameId=g["gameId"],
                eventId=g["eventId"],
                away=g["away"],
                home=g["home"],
                marketSpreadHome=m["spreadHome"],
                marketTotal=m["total"],
                modelSpreadHome=p["modelSpreadHome"],
                gapHome=m["spreadHome"] - p["modelSpreadHome"],
                marketSource="ESPN / " + str(m["provider"]) + " comparison reference",
                marketObservedAt=g["marketObservedAt"],
                executionVerified=False,
                eligibleForGrading=False,
                source=g["sourceUrl"],
                kickoffUtc=g["kickoffUTC"],
            )
        )
    dump(
        ROOT / "nfl_data/site/market-reference.json",
        dict(
            observedAt=max(g["marketObservedAt"] for g in marketgames),
            provider="DraftKings via ESPN",
            eligibleForGrading=False,
            executionVerified=False,
            games=marketgames,
            note="Current pregame comparison only. Original publication markets and all frozen model values are unchanged.",
        ),
    )
    # Personnel gates explicitly carry known baseline breaks without fabricated points.
    gates = []
    for g in nflgames:
        gates.append(
            dict(
                gameId=g["gameId"],
                source=g.get("contextAlertSource", by["nfl-official-injuries"]["url"]),
                observedAt=g["observedAt"],
                reportType="OFFICIAL_DESIGNATION_REPORT_NOT_FINAL_INACTIVES",
                finalAvailabilityVerified=False,
                qbChange=g.get("qbChange"),
                summary=" ".join(g["contextAlerts"])
                or "Official designations captured; final inactives and starting-lineup verification remain pending.",
                status="HOLD",
                blockers=[
                    "FINAL_AVAILABILITY_UNVERIFIED",
                    "QB_CHANGE_NOT_REPRESENTED_IN_FORECAST"
                    if g.get("qbChange")
                    else "QB_STATE_NOT_FULLY_VERIFIED",
                ],
                personnelAdjusted=False,
                baselineResearchDisplayAllowed=True,
                fullReleaseCertified=False,
            )
        )
    dump(
        ROOT / "nfl_data/site/personnel-gates.json",
        dict(
            league="nfl",
            week=9,
            canonicalInfluence=False,
            updatedAt=checked,
            policy="Official reports are context, not final-inactive clearance. No personnel points are applied.",
            games=gates,
        ),
    )
    cfgpath = ROOT / "nfl_data/site/config.json"
    cfg = json.loads(cfgpath.read_text())
    cfg.update(
        contextLastUpdated=checked, currentContextAudit="data/game-readiness.json"
    )
    dump(cfgpath, cfg)
    # Forecast values, freeze timestamps and original CSV markets stay unchanged.
    csvpath = ROOT / "nfl_data/site/projections.csv"
    rows = list(csv.DictReader(csvpath.open()))
    fields = list(rows[0])
    fixed = [
        "modelSpreadHome",
        "modelTotal",
        "projectedAwayPoints",
        "projectedHomePoints",
        "homeWinProbability",
        "awayWinProbability",
        "projectionFreezeUtc",
        "marketSpreadHome",
        "marketTotal",
        "marketObservedAt",
        "marketSource",
    ]
    before = {r["gameId"]: tuple(r[k] for k in fixed) for r in rows}
    context_byid = {g["gameId"]: g for g in nflgames}
    for r in rows:
        g = context_byid[r["gameId"]]
        r["personnelState"] = "OFFICIAL_DESIGNATIONS_FINAL_INACTIVES_PENDING"
        r["contextObservedAt"] = g["observedAt"]
        r["contextSource"] = "readiness.html"
        r["weatherRoofState"] = g["weatherStatus"] + " / " + g["roofStatus"]
        r["hardQbStateBreak"] = "true" if g.get("qbChange") else ""
        r["rosterChangeState"] = (
            "KNOWN_QB_CHANGES_BASELINE_UNADJUSTED"
            if g.get("qbChange")
            else "CURRENT_DESIGNATIONS_REVIEWED_NOT_FINAL"
        )
        r["rosterAuditSource"] = "readiness.html"
        r["notes"] = (
            r["notes"].split(" Current context review:")[0]
            + " Current context review: "
            + (
                " ".join(g["contextAlerts"])
                or "Official designation reports and referee assignment captured. Final availability and roof remain unverified."
            )
            + " See readiness.html."
        )
        if g.get("gameId") == "2026_09_LV_SF" and g.get("scheduleConfirmationSource"):
            r["kickoffET"] = "4:25 PM"
        if g.get("qbChange"):
            r["releaseBlockers"] = "|".join(
                dict.fromkeys(
                    r["releaseBlockers"].split("|")
                    + ["QB_CHANGE_NOT_REPRESENTED_IN_FORECAST"]
                )
            )
    assert before == {r["gameId"]: tuple(r[k] for k in fixed) for r in rows}
    with csvpath.open("w") as fp:
        w = csv.DictWriter(fp, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    research = json.loads((ROOT / "nfl_data/site/research.json").read_text())
    research["updated"] = checked
    research["categories"][0]["summary"] = (
        "Week 9 context refreshed. Known Seattle/Arizona QB changes are not represented by a validated point adjustment. Official designation reports are not final inactives; all rows remain research HOLD."
    )
    research["categories"][0]["items"] = [
        i
        for i in research["categories"][0]["items"]
        if i.get("title") != "Current game evidence"
    ]
    research["categories"][0]["items"].append(
        dict(
            title="Current game evidence",
            detail="Current injuries, area forecasts, referee assignments, comparisons and trend conditions: readiness.html",
            tag="CONTEXT / HOLD",
        )
    )
    dump(ROOT / "nfl_data/site/research.json", research)
    data["sourceWarnings"] = list(
        dict.fromkeys(
            data["sourceWarnings"]
            + [
                "Mountain West archive PDF checked Friday covers November 2025. Official availability remains unresolved wherever a current matchup report is missing. The American Conference listed its four remaining conference games as Report Pending at capture."
            ]
        )
    )
    dump(ROOT / "data/game-readiness.json", data)
    dump(
        audit / "source-manifest.json",
        [{k: v for k, v in x.items() if k != "rawPath"} for x in meta],
    )
    # Current matchup-level comparisons accompany refreshed research ratings.
    import build_power_rankings as pr

    ratings = {
        l: json.loads((ROOT / f"data/power-rankings/{l}.json").read_text())
        for l in ["cfb", "nfl"]
    }
    for l, d in ratings.items():
        comps = []
        edges = []
        for g in data["games"]:
            if g["league"] != l or dt(g["kickoffUTC"]) <= datetime.now(timezone.utc):
                continue
            m = g.get("marketReference") or {}
            spread = m.get("spreadHome")
            if spread is None:
                continue
            home, away = g["home"], g["away"]
            gap = g["modelMarketComparison"]["spreadGapHome"]
            comps.append(
                dict(
                    gameId=g["projectionGameId"],
                    kickoff=g["kickoffUTC"],
                    homeTeam=home,
                    awayTeam=away,
                    modelSpreadHome=g["baselineProjection"]["modelSpreadHome"],
                    marketSpreadHome=spread,
                    modelMarketGapHome=gap,
                    gapSide=home if gap > 0 else away if gap < 0 else "PUSH",
                    gapMagnitude=abs(gap),
                    marketSource="ESPN / " + str(m["provider"]),
                    marketObservedAt=g["marketObservedAt"],
                    marketRole="CONTEXT_BENCHMARK_ONLY",
                    eligibleForGrading=False,
                )
            )
            edges.append(
                (pr.engine.canonical_school(away), pr.engine.canonical_school(home))
                if l == "cfb"
                else (away, home)
            )
        d["remainingMatchupComparisons"] = comps
        d["marketNationalRatings"] = pr.market_status(
            pr.graph_status({r["team"] for r in d["teams"]}, edges),
            checked,
            "Current ESPN sportsbook references, context only",
        )
        dump(ROOT / f"data/power-rankings/{l}.json", d)
    pr.write_manifest(ratings["cfb"], ratings["nfl"], ROOT / "data/power-rankings")
    # Keep all current evidence accessible, without carrying old Week 8/9 page claims forward.
    e = lambda x: html.escape(str(x))
    htmlout = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Current game evidence | CB Model Projections</title><style>body{background:#0b1423;color:#eef4fa;font:16px/1.6 system-ui;margin:auto;max-width:1100px;padding:24px}a{color:#9bd8ff}article{border:1px solid #41536b;padding:18px;margin:16px 0;border-radius:12px}small{color:#b0c2d6}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;padding:10px 0}strong{color:#ffd18a}nav{display:flex;gap:20px;flex-wrap:wrap}h2{margin-top:40px}</style></head><body><nav><a href="current-matchups.html">Current matchups</a><a href="week-10.html">CFB Week 10</a><a href="index.html?league=nfl">NFL Week 9</a><a href="ratings.html">Power ratings</a></nav><h1>Current-week game evidence</h1>"""
    htmlout += f'<p>Collected {e(checked)}. Frozen model projections are preserved. Injury reports, trends, markets and area forecasts are separate context. <strong>Final availability, roof decisions and pregame rechecks remain HOLD.</strong></p><p><a href="data/game-readiness.json">Full evidence and timestamps</a></p>'
    for l in ["cfb", "nfl"]:
        games = [g for g in data["games"] if g["league"] == l]
        htmlout += f"<h2>{l.upper()} · Week {data['leagues'][l]['week']} · {len(games)} remaining games at collection</h2>"
        for g in games:
            htmlout += f"<article><h3>{e(g['away'])} at {e(g['home'])}</h3><small>{e(g['kickoffUTC'])} · source observed {e(g.get('observedAt', 'unavailable'))}</small><p><strong>Research HOLD.</strong> {e(g['injuryStatus'])}. Final availability unverified.</p>"
            for alert in g.get("contextAlerts", []):
                htmlout += f"<p><strong>{e(alert)}</strong></p>"
            p = g["baselineProjection"]
            m = g.get("marketReference") or {}
            htmlout += f"<p>Frozen model: home spread {p['modelSpreadHome']:+.2f}, total {p['modelTotal']:.2f}. Current reference: spread {e(m.get('spreadHome', '—'))}, total {e(m.get('total', '—'))}. Context only; not a grading lock.</p>"
            htmlout += f"<p>Officials: {e(', '.join(x.get('displayName', '') for x in g.get('officials', [])) or 'Not posted in checked source')}. Weather: {e(g['weatherStatus'])}. Roof: {e(g['roofStatus'])}.</p>"
            if g.get("qbAlerts"):
                htmlout += (
                    "<ul>"
                    + "".join(
                        f"<li>{e(a if isinstance(a, str) else a['team'] + ' ' + a['player'] + ': ' + a['status'])}</li>"
                        for a in g["qbAlerts"]
                    )
                    + "</ul>"
                )
            if g.get("officialAvailabilityReports"):
                htmlout += "<details><summary>Conference availability reports</summary>"
                for report in g["officialAvailabilityReports"]:
                    htmlout += f'<p><a href="{e(report["sourceUrl"])}">{e(report["conference"])} {e(report["reportType"])}</a> · {e(report.get("publishDate") or report.get("publishedAt"))} {e(report.get("postedTime", ""))} {e(report.get("timeZone", ""))}</p>'
                    for team in report["teams"]:
                        htmlout += (
                            f"<p>{e(team['team'])}</p><ul>"
                            + "".join(
                                f"<li>{e(p['name'])} · {e(p['status'])}</li>"
                                for p in team["players"]
                            )
                            + "</ul>"
                        )
                htmlout += "</details>"
            if g.get("officialInjuryReports"):
                htmlout += "<details><summary>NFL injury designations</summary>"
                for side in g["officialInjuryReports"].values():
                    htmlout += (
                        f'<p><a href="{e(side["sourceUrl"])}">{e(side["team"])}</a></p><ul>'
                        + "".join(f"<li>{e(x)}</li>" for x in side["designations"])
                        + "</ul>"
                    )
                    if not side["designations"]:
                        htmlout += "<p>Game designation list pending. Check the team report.</p>"
                htmlout += "</details>"
            if g.get("nwsWeather"):
                weather = g["nwsWeather"]
                htmlout += "<details><summary>Hourly area forecast</summary><ul>"
                for period in weather["periods"]:
                    htmlout += f"<li>{e(period['startTime'])} · {e(period['temperature'])}°{e(period['temperatureUnit'])} · {e(period['windSpeed'])} {e(period['windDirection'])} · {e(period['shortForecast'])}</li>"
                htmlout += f'</ul><p><a href="{e(weather["sourceUrl"])}">NWS forecast</a></p></details>'
            forms = g.get("formTrends", [])
            matched = [t for t in trends if t["gameId"] == g.get("gameId")]
            if forms or matched:
                htmlout += "<details><summary>Form and trend alignment</summary><ul>"
                htmlout += "".join(
                    f"<li>{e(f['team'])} · {e(f['record'])} in last five · {e(f['alignment'].replace('_', ' ').lower())}</li>"
                    for f in forms
                )
                htmlout += "".join(
                    f"<li>{e(t['text'])} · {e(t['alignment'].replace('_', ' ').lower())}</li>"
                    for t in matched
                )
                htmlout += "</ul></details>"
            htmlout += f'<p><a href="{e(g["sourceUrl"])}">Game source</a></p></article>'
    htmlout += (
        "<h2>Source gaps and exclusions</h2>"
        + "".join(f"<p>{e(w)}</p>" for w in data["sourceWarnings"])
        + f"<p>{len(data['excludedStartedGames'])} already-started games excluded from new pregame collection. Their frozen evidence and grading remain separate.</p></body></html>"
    )
    (ROOT / "readiness.html").write_text(htmlout)
    print(
        json.dumps(
            {
                "cfbOfficialGames": sum(
                    bool(g.get("officialAvailabilityReports"))
                    for g in data["games"]
                    if g["league"] == "cfb"
                ),
                "nflReferences": len(marketgames),
                "nflTrends": len(trends),
                "aligns": sum(t["alignment"] == "ALIGNS" for t in trends),
                "conflicts": sum(t["alignment"] == "CONFLICTS" for t in trends),
                "ratingComparisons": {
                    l: len(d["remainingMatchupComparisons"]) for l, d in ratings.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
