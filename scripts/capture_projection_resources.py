#!/usr/bin/env python3
"""Capture current-week NFL inputs and CFB benchmarks outside production.

This extends existing nflverse ingestion with provenance and scope checks. It
does not introduce another canonical input family or refit a model. The output
directory must not exist. Collection time is always the actual system clock.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from statistics import mean

from projection_resource_evidence import (ET, cfb_slate, compare_forecasts, cycle, digest,
    instant, nfl_slate, number, save_new, team_key, validate_observation)

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"
PIRATE_URL = "https://piratings.wordpress.com/"
FEI_URL = "https://bcftoys.com/{season}-fei"
MOORE_URL = "https://sonnymoorepowerratings.com/col-foot.htm"


def clock():
    return datetime.now(timezone.utc)


def retrieve(url, out, label, max_bytes=80_000_000):
    started = clock()
    request = urllib.request.Request(url, headers={"User-Agent": "CBModelProjections-Research/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("source exceeds size limit")
        completed = clock()
        location = urlsplit(response.url)
        metadata = {"sourceId": label, "url": url, "responseUrl": urlunsplit((location.scheme, location.netloc, location.path, "", "")),
                    "retrievalStartedAt": started.isoformat(), "observedAt": completed.isoformat(),
                    "sha256": digest(raw), "bytes": len(raw),
                    "httpLastModified": response.headers.get("Last-Modified"),
                    "availabilityPolicy": "First usable at completed retrieval; HTTP dates do not certify historical availability."}
    path = out / "raw" / (label + (".csv.gz" if url.endswith("csv.gz") else ".source"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    metadata["rawPath"] = str(path.relative_to(out))
    return raw, metadata


class Tables(HTMLParser):
    """Read public HTML tables and nearby headings, without executing scripts."""
    def __init__(self):
        super().__init__(); self.tables = []; self.headings = []; self.text = []
        self.heading = None; self.heading_text = []; self.table = None; self.row = None; self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3"}:
            self.heading = tag; self.heading_text = []
        if tag == "table" and self.table is None:
            self.table = {"headings": self.headings[-20:].copy(), "rows": []}
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self.heading:
            self.heading_text.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == self.heading:
            self.headings.append(" ".join(" ".join(self.heading_text).split())); self.heading = None
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split())); self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row); self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table); self.table = None


def pirate_margins(html, slate, aliases, now):
    parser = Tables(); parser.feed(html)
    start, _ = cycle(now)
    eligible = []
    for table in parser.tables:
        rows = table["rows"]
        if not rows or [x.lower() for x in rows[0][:3]] != ["home", "visitor", "pirate"]:
            continue
        titles = [h for h in table["headings"] if "PiRate Ratings" in h and "For Week" in h]
        if not titles or "College Football For Week" not in titles[-1]:
            continue
        title = titles[-1]
        date_match = re.search(r"([A-Za-z]+)\s+(\d+)(?:[-–]\d+)?,?\s+(\d{4})", title)
        if not date_match:
            continue
        title_date = datetime.strptime(" ".join(date_match.groups()), "%B %d %Y").date()
        # Validate dates, not the publisher's week number; no stale matchup reuse.
        if not start <= title_date < start + timedelta(days=7):
            continue
        eligible.append(rows[1:])
    if len(eligible) != 1:
        raise ValueError("no unique current-cycle PiRate CFB margin table")
    pairs = {}
    for cells in eligible[0]:
        if len(cells) < 3 or number(cells[2]) is None:
            continue
        key = (team_key(cells[0], aliases), team_key(cells[1], aliases))
        if key in pairs:
            raise ValueError("duplicate PiRate matchup")
        pairs[key] = number(cells[2])
    return {g["gameId"]: pairs[(team_key(g["homeTeam"], aliases), team_key(g["awayTeam"], aliases))]
            for g in slate["games"] if (team_key(g["homeTeam"], aliases), team_key(g["awayTeam"], aliases)) in pairs}


def moore_margins(html, slate, aliases, now):
    parser = Tables(); parser.feed(html)
    text = " ".join(parser.text)
    match = re.search(r"Compiled:\s*\d\d:\d\d:\d\d\s+on\s+(\d\d-\d\d-\d{4})", text)
    if not match:
        raise ValueError("Moore compile date unavailable")
    compiled = datetime.strptime(match[1], "%m-%d-%Y").date()
    if not 0 <= (now.astimezone(ET).date() - compiled).days <= 8:
        raise ValueError("Moore rating date stale or future")
    ratings = {}
    pattern = r"\b\d+\s+([A-Z][A-Z .&'()-]+?)\s+\d+\s+\d+\s+\d+\s+[-\d.]+\s+([-\d.]+)"
    for name, value in re.findall(pattern, text):
        key = team_key(name.strip(), aliases)
        if key in ratings and ratings[key] != float(value):
            raise ValueError("duplicate Moore team")
        ratings[key] = float(value)
    if len(ratings) < 100:
        raise ValueError("Moore parser coverage failed")
    return {g["gameId"]: ratings[team_key(g["homeTeam"], aliases)] - ratings[team_key(g["awayTeam"], aliases)]
            + (0 if g["neutralSite"] else 4.0)
            for g in slate["games"] if all(team_key(g[k], aliases) in ratings for k in ["homeTeam", "awayTeam"])}


def nfl_features(raw, schedule_rows, slate, observed_at):
    """Prior-week, unadjusted diagnostic aggregates; NOT canonical replacements.

    Retain only regular-season valid EPA pass/rush plays, excluding kneels,
    spikes, no-plays and overtime. Success is EPA > 0, not first-down rate.
    """
    season, week = slate["season"], slate["week"]
    complete = {r["game_id"]: r for r in schedule_rows if r.get("season") == str(season)
                and r.get("game_type") == "REG" and int(r["week"]) < week
                and number(r.get("home_score")) is not None and number(r.get("away_score")) is not None
                and r.get("gameday", "9999") < observed_at[:10]}
    required = {"game_id", "play_id", "season", "week", "season_type", "posteam", "defteam", "epa",
                "pass", "rush", "qb_kneel", "qb_spike", "play_type", "qtr"}
    reader = csv.DictReader(io.StringIO(gzip.decompress(raw).decode("utf-8-sig")))
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("PBP schema missing required fields: " + str(sorted(required - set(reader.fieldnames or []))))
    groups = defaultdict(list); seen = set(); used = set(); rejected = Counter()
    for r in reader:
        if r["game_id"] not in complete:
            rejected["not_completed_prior_week"] += 1; continue
        schedule = complete[r["game_id"]]
        if r["season"] != str(season) or number(r["week"]) != number(schedule["week"]) or r["season_type"] != "REG":
            raise ValueError("PBP schedule identity mismatch")
        if r["posteam"] not in {schedule["home_team"], schedule["away_team"]}:
            rejected["not_offensive_play"] += 1; continue
        if r["defteam"] not in {schedule["home_team"], schedule["away_team"]} or r["defteam"] == r["posteam"]:
            raise ValueError("PBP team identity mismatch")
        qtr = number(r["qtr"])
        if (qtr is None or not 1 <= qtr <= 4 or number(r["qb_kneel"]) == 1 or number(r["qb_spike"]) == 1
                or r["play_type"] == "no_play" or not (number(r["pass"]) == 1 or number(r["rush"]) == 1) or number(r["epa"]) is None):
            rejected["excluded_play_type_or_missing_epa"] += 1; continue
        key = (r["game_id"], r["play_id"])
        if not r["play_id"] or key in seen:
            raise ValueError("duplicate/missing PBP play identity")
        seen.add(key); used.add(r["game_id"])
        value = number(r["epa"])
        groups[(r["posteam"], "offense")].append((value, number(r["pass"]) == 1, r["game_id"], int(r["week"])))
        groups[(r["defteam"], "defenseAllowed")].append((value, number(r["pass"]) == 1, r["game_id"], int(r["week"])))
    features = []
    for (team, unit), plays in sorted(groups.items()):
        features.append({"team": team, "unit": unit, "plays": len(plays), "games": len({p[2] for p in plays}),
                         "epaPerPlay": mean(p[0] for p in plays), "successRate": mean(p[0] > 0 for p in plays),
                         "passEpaPerPlay": mean(p[0] for p in plays if p[1]) if any(p[1] for p in plays) else None,
                         "rushEpaPerPlay": mean(p[0] for p in plays if not p[1]) if any(not p[1] for p in plays) else None,
                         "maxSourceWeek": max(p[3] for p in plays)})
    if not features:
        raise ValueError("no usable prior-week PBP")
    missing_games = sorted(set(complete) - used)
    return {"season": season, "targetWeek": week, "canonicalInfluence": False, "role": "diagnostic_input_snapshot", "features": features,
            "definitionVersion": "regulation-pass-rush-epa-v1", "sourceObservedAt": observed_at,
            "eligibleFutureGameIds": [g["gameId"] for g in slate["games"] if instant(g["kickoff"]) > instant(observed_at)],
            "historicalPregameAvailabilityCertified": False, "opponentAdjusted": False,
            "status": "INCOMPLETE" if missing_games else "CAPTURED_RESEARCH_ONLY",
            "missingPriorGameIds": missing_games, "rejectedPlayCounts": dict(rejected)}


def load_freezes(root, league, slate):
    week = slate["week"]
    path = root / (f"cfb/research-locks/week-{week:02d}-foundation-full.json" if league == "cfb"
                   else f"nfl/research-projections/week-{week:02d}.json")
    if not path.exists():
        return [], {"status": "MISSING_CURRENT_WEEK_PROJECTIONS", "expectedPath": str(path.relative_to(root))}
    doc = json.loads(path.read_text())
    if doc.get("league", "").lower() != league or doc.get("season") != slate["season"] or doc.get("week") != week:
        raise ValueError("projection artifact scope mismatch")
    if league == "cfb":
        from lock_research_shadow import verify
        verify(doc)
    rows = []
    for g in doc["games"]:
        if league == "cfb":
            rows.append({"gameId": g["gameId"], "homeTeam": g["homeTeam"], "awayTeam": g["awayTeam"],
                         "kickoff": g["kickoff"], "frozenAt": doc["lockedAt"],
                         "homeMargin": -float(g["projectedSpreadHome"]), "total": g["projectedTotal"]})
        else:
            rows.append({"gameId": g["gameId"], "homeTeam": g["home"], "awayTeam": g["away"],
                         "kickoff": g["kickoffUTC"], "frozenAt": doc["frozenAt"],
                         "homeMargin": -float(g["modelSpreadHome"]), "total": g["modelTotal"]})
    expected = {g["gameId"] for g in slate["games"]}
    actual = {g["gameId"] for g in rows}
    if len(actual) != len(rows) or actual - expected:
        raise ValueError("duplicate/out-of-slate projection")
    future_ids = {g["gameId"] for g in slate["games"] if instant(g["kickoff"]) > clock()}
    status = "COVERED" if expected == actual else "REMAINING_COVERED" if future_ids <= actual else "INCOMPLETE"
    return rows, {"status": status, "projectionCount": len(rows),
                  "missingGameIds": sorted(expected - actual), "sourcePath": str(path.relative_to(root)),
                  "sourceSha256": digest(path.read_bytes())}


def run(root, out, include_pbp=True):
    out.mkdir(parents=True, exist_ok=False)
    report = {"schemaVersion": 1, "startedAt": clock().isoformat(), "canonicalInfluence": False,
              "promotionAuthorized": False, "productionFilesModified": False, "sources": [], "errors": [], "leagues": {}}
    aliases = json.loads((root / "data/team-aliases.json").read_text())
    schedule = None
    try:
        raw, source = retrieve(SCHEDULE_URL, out, "nflverse-schedule")
        report["sources"].append(source)
        schedule = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        slate = nfl_slate(schedule, clock()); forecasts, coverage = load_freezes(root, "nfl", slate)
        cfg = json.loads((root / "nfl_data/site/config.json").read_text())
        report["leagues"]["nfl"] = {**slate, "projectionCoverage": coverage, "publishedWeek": cfg["currentWeek"],
            "publishedWeekMatches": cfg["currentWeek"] == slate["week"],
            "alreadyStartedGameIds": [g["gameId"] for g in slate["games"] if instant(g["kickoff"]) <= clock()]}
        if include_pbp:
            raw, source = retrieve(PBP_URL.format(season=slate["season"]), out, "nflverse-pbp")
            report["sources"].append(source)
            features = nfl_features(raw, schedule, slate, source["observedAt"])
            features["sourceSha256"] = source["sha256"]
            save_new(out / "nfl-inputs.json", features)
            report["leagues"]["nfl"]["inputCaptureStatus"] = features["status"]
        else:
            report["leagues"]["nfl"]["inputCaptureStatus"] = "SKIPPED"
    except Exception as exc:
        report["errors"].append({"stage": "nfl", "error": str(exc)})
    try:
        slate = cfb_slate(root, clock()); forecasts, coverage = load_freezes(root, "cfb", slate)
        report["leagues"]["cfb"] = {**slate, "projectionCoverage": coverage, "benchmarkCoverage": {},
            "alreadyStartedGameIds": [g["gameId"] for g in slate["games"] if instant(g["kickoff"]) <= clock()]}
        observations = []
        for name, url, parser, conversion in [
            ("pirate-cfb", PIRATE_URL, pirate_margins, "Publisher direct PiRate home margin; Mean/Bias not extra independent votes."),
            ("moore-cfb", MOORE_URL, moore_margins, "home PR minus away PR plus publisher 4-point HFA; zero at neutral sites.")]:
            try:
                raw, source = retrieve(url, out, name)
                report["sources"].append(source)
                margins = parser(raw.decode("utf-8", errors="replace"), slate, aliases, clock())
                collected = clock().isoformat(); skipped = []; captured = []
                for game in slate["games"]:
                    if instant(game["kickoff"]) <= instant(collected):
                        skipped.append({"gameId": game["gameId"], "reason": "already_started_no_backfill"}); continue
                    if game["gameId"] not in margins:
                        skipped.append({"gameId": game["gameId"], "reason": "source_match_missing"}); continue
                    obs = {**game, "league": "cfb", "sourceId": name, "family": name, "role": "external_benchmark",
                           "vintage": "game_week", "canonicalInfluence": False, "homeMargin": margins[game["gameId"]],
                           "total": None, "sourceObservedAt": source["observedAt"], "collectedAt": collected,
                           "sourceUrl": url, "sourceSha256": source["sha256"], "conversion": conversion}
                    validate_observation(obs, game); observations.append(obs); captured.append(game["gameId"])
                report["leagues"]["cfb"]["benchmarkCoverage"][name] = {"captured": len(captured), "skipped": skipped}
            except Exception as exc:
                report["errors"].append({"stage": name, "error": str(exc)})
        # FEI is possession-scale data: retain the source, never invent a point conversion.
        try:
            _, source = retrieve(FEI_URL.format(season=slate["season"]), out, "fei-cfb")
            source["role"] = "rating_context_only_no_unvalidated_points_conversion"
            report["sources"].append(source)
        except Exception as exc:
            report["errors"].append({"stage": "fei-cfb", "error": str(exc)})
        save_new(out / "cfb-benchmarks.json", {"canonicalInfluence": False, "observations": observations})
        save_new(out / "cfb-comparison.json", compare_forecasts("cfb", slate["games"], forecasts, observations))
        future_ids = {g["gameId"] for g in slate["games"] if instant(g["kickoff"]) > clock()}
        report["leagues"]["cfb"]["missingFutureBenchmarkGameIds"] = sorted(future_ids - {o["gameId"] for o in observations})
    except Exception as exc:
        report["errors"].append({"stage": "cfb", "error": str(exc)})
    report["completedAt"] = clock().isoformat()
    blockers = [f"{league}: {d['projectionCoverage']['status']}" for league, d in report["leagues"].items()
                if d["projectionCoverage"]["status"] not in {"COVERED", "REMAINING_COVERED"}]
    if len(report["leagues"]) != 2:
        blockers.append("missing current league scope")
    if report["errors"]:
        blockers.append("source/parse errors; see errors")
    nfl = report["leagues"].get("nfl", {})
    if nfl and not nfl.get("publishedWeekMatches"):
        blockers.append("NFL published feed week differs from current schedule week")
    if nfl.get("inputCaptureStatus") != "CAPTURED_RESEARCH_ONLY":
        blockers.append("NFL diagnostic input capture incomplete or skipped")
    if report["leagues"].get("cfb", {}).get("missingFutureBenchmarkGameIds"):
        blockers.append("CFB future games missing benchmark coverage")
    report["status"] = "CAPTURED_WITH_GAPS" if blockers else "RESEARCH_CAPTURE_COMPLETE"
    report["blockers"] = blockers
    report["readinessCertified"] = False
    report["policy"] = "Source capture only. No injury/inactive/weather/referee clearance, new projection, market lock, or model promotion. Revised source bytes do not prove historical availability."
    save_new(out / "manifest.json", report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True, help="new immutable capture directory")
    ap.add_argument("--skip-pbp", action="store_true", help="schedule/benchmark audit only")
    ap.add_argument("--strict", action="store_true", help="nonzero status for gaps, after saving evidence")
    args = ap.parse_args()
    # Capture may never target a protected production tree.
    out = args.output.resolve()
    if out == ROOT or any(out.is_relative_to(ROOT / name) for name in ["data", "cfb", "nfl", "nfl_data", "scripts", "tests", ".github"]):
        ap.error("output must be outside production/model directories")
    report = run(ROOT, out, not args.skip_pbp)
    print(json.dumps({"status": report["status"], "blockers": report["blockers"], "output": str(out)}, indent=2))
    if args.strict and report["status"] != "RESEARCH_CAPTURE_COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
