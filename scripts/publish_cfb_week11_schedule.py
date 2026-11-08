"""Publish Week 10 grades and the independently checked Week 11 schedule."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from grade_research_shadow import grade
from publish_current_matchups import render
from record_tracker import counts, grade_game, load_aliases, merge_counts

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
LOCK = "cfb/research-locks/week-10-foundation-full.json"
MARKETS = "cfb/pregame/week10-evidence/market-context.json"
SHADOW_GRADE = "cfb/research-results/week-10-foundation-full.json"
SCORES = "cfb/postgame/week-10-final-scores.json"
SCHEDULE = "cfb/pregame/week-11-schedule.json"
KEYS = ("ats", "totals", "straightUp")


def read(path):
    return json.loads((ROOT / path).read_text())


def write(path, doc):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2) + "\n")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def unique(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {key}")
    return result


def grade_week10(scores):
    lock = read(LOCK)
    saved_scores = unique(scores["games"], "sourceGameId")
    frozen = unique(lock["games"], "sourceGameId")
    markets = unique(read(MARKETS)["games"], "sourceGameId")
    if saved_scores.keys() != frozen.keys() or markets.keys() != frozen.keys():
        raise ValueError("Final scores and publication markets must match the frozen slate")
    if any(g.get("status") != "FINAL" for g in saved_scores.values()):
        raise ValueError("Week 10 finals capture is incomplete")
    pub = {r["gameId"]: r for r in csv.DictReader((ROOT / "data/projections.csv").open())}
    shadow = grade(lock, scores["games"], load_aliases(ROOT))
    rows = []
    for gid, game in frozen.items():
        quote = markets[gid]
        source = pub[game["gameId"]]
        market = quote["market"]
        kickoff = datetime.fromisoformat(game["kickoff"])
        if not (
            quote["status"] == "PREGAME_CONTEXT_CAPTURED"
            and datetime.fromisoformat(quote["observedAt"]) < kickoff
            and quote["observedAt"] == source["marketObservedAt"]
            and market["source"] == source["marketSource"]
            and market["spreadHome"] == float(source["marketSpreadHome"])
            and market["total"] == float(source["marketTotal"])
            and game["projectedSpreadHome"] == float(source["modelSpreadHome"])
            and game["projectedTotal"] == float(source["modelTotal"])
        ):
            raise ValueError(f"Publication evidence mismatch for {gid}")
        result = grade_game(
            dict(game, marketSpreadHome=market["spreadHome"], marketTotal=market["total"],
                 marketSource=market["source"], marketObservedAt=quote["observedAt"]),
            saved_scores[gid],
        )
        result["projection"]["homeWinProbability"] = game["homeWinProbability"]
        result["date"] = game["gameDateET"]
        result["sourceGameId"] = gid
        result["projectionDigest"] = game["projectionDigest"]
        result["trackingClass"] = "FROZEN_RESEARCH"
        result["gradeReference"] = SHADOW_GRADE
        rows.append(result)
    assert shadow["status"] == "COMPLETE" and len(rows) == 62
    assert counts(rows, "straightUp")["wins"] == shadow["metrics"]["straightUp"]["wins"]
    note = "Frozen Week 10 foundation research graded against the original pregame ESPN-carried DraftKings references. Research benchmark grades. Execution locks were unverified."
    records = dict(schemaVersion=1, league="cfb", season=2026, week=10, status="COMPLETE",
                   role="PUBLISHED_RESEARCH_RESULTS_COMPATIBILITY", canonicalInfluence=False,
                   sourceLock=LOCK, sourceLockDigest=lock["lockDigest"], sourceMarkets=MARKETS,
                   sourceScores=SCORES, sourceNote=note, games=rows)
    summary = read("cfb/record-summary.json")
    if any(w["season"] == 2026 and w["week"] == 10 for w in summary["weeks"]):
        raise ValueError("Week 10 record already exists")
    weekly = dict(season=2026, week=10, status="COMPLETE", pending=0, review=0,
                  recordType="Frozen research", note=note)
    weekly.update({k: counts(rows, k) for k in KEYS})
    summary["weeks"].append(weekly)
    summary.update(currentWeek=10, generatedAt=stamp(), pending=0, review=0)
    summary["overall"] = {k: merge_counts(*(w[k] for w in summary["weeks"])) for k in KEYS}
    summary["sourceNote"] = "Published-model cumulative display combining historical audited and labeled frozen research weeks. " + note

    csvpath = ROOT / "data/results.csv"
    existing = csvpath.read_bytes()
    fields = next(csv.reader(io.StringIO(existing.decode())))
    if not existing.endswith(b"\n"):
        raise ValueError("Results CSV needs a terminal line ending before append")
    new = io.StringIO(newline="")
    writer = csv.DictWriter(new, fieldnames=fields, lineterminator="\n")
    for r in rows:
        writer.writerow(dict(
            season=2026, week=10, date=r["date"], gameId=r["gameId"], awayTeam=r["awayTeam"],
            homeTeam=r["homeTeam"], awayScore=r["final"]["awayScore"], homeScore=r["final"]["homeScore"],
            modelSpreadHome=r["projection"]["spreadHome"], modelTotal=r["projection"]["total"],
            homeWinProbability=r["projection"]["homeWinProbability"], marketSpreadHome=r["market"]["spreadHome"],
            marketTotal=r["market"]["total"], atsProjection=r["ats"]["pick"], atsResult=r["ats"]["result"],
            totalProjection=r["totals"]["pick"], totalResult=r["totals"]["result"],
            suProjection=r["straightUp"]["pick"], suResult=r["straightUp"]["result"],
            trackingClass=r["trackingClass"], gradeReference=SHADOW_GRADE))
    write(SCORES, scores)
    write(SHADOW_GRADE, shadow)
    write("cfb/results/week-10.json", records)
    write("cfb/record-summary.json", summary)
    csvpath.write_bytes(existing + new.getvalue().encode())
    return weekly


def publish_schedule(capture, results):
    games = capture["games"]
    corroboration = capture["corroboration"]
    if len(unique(games, "sourceGameId")) != corroboration["matchupsMatched"] or len(games) != 67:
        raise ValueError("Week 11 schedule did not reconcile with the independent slate")
    now = datetime.now(timezone.utc)
    entries = []
    for g in games:
        source_time = datetime.fromisoformat(g["kickoff"]).astimezone(ET)
        if source_time <= now or g["status"] != "STATUS_SCHEDULED":
            raise ValueError("Week 11 capture contains a started or non-scheduled event")
        kickoff = source_time if g["kickoffConfirmed"] else None
        time_source = "ESPN and CBS Sports" if kickoff else None
        match = re.match(r"(\d{1,2}:\d{2} [ap]m)", g["corroboratingTimeET"], re.I)
        if kickoff is None and match and source_time.hour == source_time.minute == 0:
            t = datetime.strptime(match[1].upper(), "%I:%M %p").time()
            kickoff = datetime.combine(source_time.date(), t, ET)
            time_source = "CBS Sports schedule. ESPN time pending."
        entries.append(dict(
            g, sourceKickoff=g["kickoff"], kickoff=kickoff.astimezone(timezone.utc).isoformat() if kickoff else None,
            kickoffTimeSource=time_source, kickoffCrossChecked=g["kickoffConfirmed"],
            kickoffConfirmed=kickoff is not None, kickoffET=kickoff.strftime("%-I:%M %p ET") if kickoff else "TBD",
            projectionStatus="Schedule posted. Forecast pending."))
    entries.sort(key=lambda g: (g["gameDateET"], g["kickoff"] is None, g["kickoff"] or "", g["awayTeam"]))
    schedule = dict(schemaVersion=2, league="cfb", season=2026, week=11, role="WEEK_SCHEDULE_STATE",
                    canonicalInfluence=False, dateWindowET=["2026-11-10", "2026-11-14"],
                    observedAt=capture["observedAt"], source="ESPN FBS team schedules",
                    corroboration=corroboration, gameCount=len(entries), games=entries)
    write(SCHEDULE, schedule)
    board = read("data/current-matchups.json")
    board.update(updatedAt=stamp(), projectionStatus="CFB_WEEK_11_SCHEDULE_NFL_RESEARCH")
    board["leagues"]["cfb"] = dict(week=11, coverageStatus="FBS_SCHEDULE_POSTED_FORECASTS_PENDING",
                                   sourceSchedule=SCHEDULE, games=[dict(
        gameId=g["gameId"], eventId=g["sourceGameId"], away=g["awayTeam"], home=g["homeTeam"],
        kickoffUTC=g["kickoff"], dateET=g["gameDateET"], kickoffET=g["gameDateET"] + " · " + g["kickoffET"],
        neutralSite=g["neutralSite"], venue=g["venue"]["name"],
        source="https://www.espn.com/college-football/game/_/gameId/" + g["sourceGameId"],
        projectionStatus=g["projectionStatus"], projectionUrl=None) for g in entries])
    write("data/current-matchups.json", board)
    render(board)
    registry = read("data/model-registry.json")
    registry["cfb"]["activeScheduleWeek"] = 11
    registry["cfb"]["activeScheduleSource"] = SCHEDULE
    write("data/model-registry.json", registry)

    def rec(key):
        r = results[key]
        return f'{r["wins"]}–{r["losses"]}' + (f'–{r["pushes"]}' if r["pushes"] else "")
    result_text = f'Week 10 research grades: {rec("ats")} ATS, {rec("totals")} totals, {rec("straightUp")} SU.'
    e = html.escape
    head = (ROOT / "current-matchups.html").read_text().split("<body>", 1)[0].replace(
        "<title>Current matchups", "<title>CFB Week 11 matchups")
    sections = []
    for day in sorted({g["gameDateET"] for g in entries}):
        cards = []
        for g in (g for g in entries if g["gameDateET"] == day):
            cards.append(f'<article class="game"><div class="time">{e(g["kickoffET"])}</div>'
                         f'<h3>{e(g["awayTeam"])} at {e(g["homeTeam"])}</h3>'
                         f'<p>{e(g["venue"]["name"] or "Venue pending")}</p>'
                         f'<a href="https://www.espn.com/college-football/game/_/gameId/{g["sourceGameId"]}">Game details</a></article>')
        date = datetime.fromisoformat(day).strftime("%A, November %-d")
        sections.append(f'<section><h2>{date} · {len(cards)} games</h2><div class="grid">{"".join(cards)}</div></section>')
    (ROOT / "week-11.html").write_text(
        head + '<body><main><nav aria-label="Page navigation"><a href="index.html">Dashboard</a>'
        '<a href="recap.html">Records</a><a href="week-10.html">Week 10 forecasts</a></nav>'
        f'<h1>CFB Week 11 matchups</h1><p class="note">{len(entries)} FBS matchups · November 10–14, 2026. '
        'Kickoff times are Eastern. Forecasts are pending.</p>'
        f'<p>{e(result_text)} <a href="recap.html">View results</a></p>'
        f'<p><a href="{SCHEDULE}">Schedule evidence</a></p>{"".join(sections)}</main></body></html>\n')
    path = ROOT / "index.html"
    page = path.read_text()
    page, n = re.subn(r'<body><p style="padding:12px">.*?</aside>(?=<aside id="saturday-readiness")',
        '<body><p style="padding:12px"><a href="week-11.html">CFB Week 11 matchups →</a></p>'
        f'<aside id="current-week-matchups" style="padding:18px;text-align:center"><strong>CFB Week 11: {len(entries)} matchups posted.</strong> '
        '<a href="week-11.html">View the schedule</a> · <a href="week-10.html">Week 10 forecast archive</a> · '
        '<a href="index.html?league=nfl">NFL projections</a>'
        f'<p>{e(result_text)} <a href="recap.html">Full record</a></p></aside>', page, count=1)
    assert n == 1
    page, n = re.subn(r'<strong>Week 10 · Canonical HOLD</strong>.*?</p>',
        '<strong>CFB Week 11 schedule posted.</strong> Forecasts are pending. '
        '<a href="week-11.html">Open the Week 11 matchups →</a></p>', page, count=1)
    assert n == 1
    path.write_text(page)
    print(result_text, f'Week 11: {len(entries)} games, {sum(g["kickoff"] is None for g in entries)} kickoff times TBD.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    args = parser.parse_args()
    if (ROOT / "cfb/results/week-10.json").exists():
        raise SystemExit("Week 10 grades already exist. Preserve the published record.")
    score_capture = json.loads(args.scores.read_text())
    schedule_capture = json.loads(args.schedule.read_text())
    publish_schedule(schedule_capture, grade_week10(score_capture))
