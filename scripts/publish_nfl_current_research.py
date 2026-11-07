#!/usr/bin/env python3
"""Publish a verified pinned research freeze through the existing NFL site schema.

Archive the previous feed before rollover. Do not alter frozen files or results,
carry forward prior-week context/markets, or certify unverified readiness gates.
"""
import argparse
import csv
import io
import json
from pathlib import Path

from personnel_readiness import assess_personnel
from projection_resource_evidence import ET, digest, instant, number

ROOT = Path(__file__).resolve().parents[1]
PIN = "0721b59b5f461ad590bd348bd655c4963265856c"
PROJECTION_FIELDS = ["projectedAwayPoints", "projectedHomePoints", "modelSpreadHome", "modelTotal"]


def rows_for(doc, fields):
    if doc.get("sourceCommit") != PIN or doc.get("canonicalInfluence") is not False:
        raise ValueError("publication requires pinned, noncanonical-influence research")
    parity = doc.get("priorWeekReproduction", {})
    if parity.get("games") != 14 or any(number(parity.get(k)) is None or not 0 <= parity[k] <= 1e-8
            for k in ["spreadMaxAbsDiff", "totalMaxAbsDiff"]):
        raise ValueError("saved forecast reproduction required")
    week = doc["week"]; rows = []; gates = []; seen = set()
    if doc["inputs"]["maxSourceWeek"] >= week:
        raise ValueError("input week leakage")
    for g in doc["games"]:
        gid = g["gameId"]
        if gid in seen or not gid.startswith(f"{doc['season']}_{week:02d}_"):
            raise ValueError("duplicate or wrong-week game")
        seen.add(gid)
        if instant(doc["frozenAt"]) >= instant(g["kickoffUTC"]):
            raise ValueError("freeze must precede kickoff")
        if any(number(g.get(k)) is None for k in PROJECTION_FIELDS):
            raise ValueError("nonfinite projection")
        if abs(g["projectedAwayPoints"]-g["projectedHomePoints"]-g["modelSpreadHome"]) > 1e-8 or abs(g["projectedAwayPoints"]+g["projectedHomePoints"]-g["modelTotal"]) > 1e-8:
            raise ValueError("projection arithmetic mismatch")
        gate = assess_personnel(kickoff=g["kickoffUTC"], observed_at=None, report_game_id=None,
                                game_id=gid, final_availability_verified=False, qb_change=None)
        gates.append({"gameId": gid, "source": None, "observedAt": None, "reportType": "NO_VERIFIED_REPORT",
                      "finalAvailabilityVerified": False, "qbChange": None,
                      "summary": "No current game-specific final personnel evidence supplied.", **gate})
        local = instant(g["kickoffUTC"]).astimezone(ET)
        r = {f: "" for f in fields}
        r.update(league="NFL", season=doc["season"], week=week, date=str(local.date()), kickoffET=local.strftime("%H:%M"),
                 gameId=gid, awayTeam=g["away"], homeTeam=g["home"], awayConference="NFL", homeConference="NFL",
                 executionVerified="false", dataQuality="BASELINE_RESEARCH_CONTEXT_PENDING", signalStrength="UNVALIDATED_RESEARCH",
                 releaseStatus="HOLD_RESEARCH_ONLY", notes=doc["limitations"], spreadReliability="PENDING_FINAL_GATES",
                 totalReliability="PENDING_FINAL_GATES", personnelState="HOLD", weatherRoofState="PENDING_VERIFICATION",
                 finalInactivesResolved="false", releaseBlockers="FINAL_PERSONNEL_PENDING|QB_STATE_UNVERIFIED|FINAL_WEATHER_ROOF_PENDING|OFFICIALS_PENDING|MARKET_LOCK_PENDING|VALIDATION_HOLD",
                 preferredArchitecture="UNCHANGED_CANONICAL_ARCHITECTURE_RESEARCH", winProbabilityState="WITHHELD_UNVALIDATED",
                 websitePublishAllowed="true", projectionFreezeUtc=doc["frozenAt"], marketLockState="UNAVAILABLE_NOT_LOCKED",
                 rosterChangeState="UNVERIFIED_CURRENT_WEEK")
        r.update({k: g[k] for k in PROJECTION_FIELDS}); rows.append(r)
    if not rows:
        raise ValueError("empty research publication")
    return rows, gates


def audit(root=ROOT):
    site = root / "nfl_data/site"; cfg = json.loads((site / "config.json").read_text())
    freeze = root / f"nfl/research-projections/week-{cfg['currentWeek']:02d}.json"
    doc = json.loads(freeze.read_text()); actual = list(csv.DictReader((site / "projections.csv").open()))
    expected, _ = rows_for(doc, list(actual[0]))
    if {r["gameId"] for r in actual} != {r["gameId"] for r in expected} or len(actual) != len(expected):
        raise ValueError("published game identity mismatch")
    by_id = {r["gameId"]: r for r in expected}
    for row in actual:
        r = by_id[row["gameId"]]
        for key in PROJECTION_FIELDS:
            if number(row[key]) != number(r[key]):
                raise ValueError(f"published projection differs: {row['gameId']} {key}")
        if row["projectionFreezeUtc"] != doc["frozenAt"] or row["releaseStatus"] != "HOLD_RESEARCH_ONLY":
            raise ValueError("freeze/release status mismatch")
        if row["homeWinProbability"] or row["awayWinProbability"] or row["hardQbStateBreak"] not in {"", "true"}:
            raise ValueError("unknown QB/probability must remain unavailable")
        if row["hardQbStateBreak"] == "true":
            from datetime import datetime
            gate_doc=json.loads((site / "personnel-gates.json").read_text())
            matches=[g for g in gate_doc['games'] if g['gameId']==row['gameId']]
            if len(matches)!=1:
                raise ValueError("QB break requires unique current-game evidence")
            gate=matches[0]
            observed=datetime.fromisoformat(gate['observedAt'].replace('Z','+00:00'))
            kickoff=datetime.fromisoformat(next(g for g in doc['games'] if g['gameId']==row['gameId'])['kickoffUTC'].replace('Z','+00:00'))
            if not (observed.tzinfo and observed<kickoff and gate.get('qbChange') is True and gate.get('source','').startswith('https://') and gate.get('personnelAdjusted') is False and 'QB_CHANGE_NOT_REPRESENTED_IN_FORECAST' in gate.get('blockers',[])):
                raise ValueError("QB break lacks dated evidence or incorrectly claims adjustment")
        if row["executionVerified"] != "false" or not row["releaseBlockers"]:
            raise ValueError("unsupported clearance")
    if cfg["spreadValidation"] != "HOLD" or cfg["totalValidation"] != "HOLD" or cfg["recommendationReleaseAllowed"] is not False:
        raise ValueError("validation must remain held")
    if cfg["researchProjectionSha256"] != digest(freeze.read_bytes()):
        raise ValueError("frozen artifact hash mismatch")
    return {"week": doc["week"], "games": len(actual), "status": "PASS_RESEARCH_PUBLICATION_ONLY"}


def publish(root, week):
    site = root / "nfl_data/site"; freeze = root / f"nfl/research-projections/week-{week:02d}.json"
    doc = json.loads(freeze.read_text()); cfg = json.loads((site / "config.json").read_text())
    old_week = cfg["currentWeek"]
    if week <= old_week:
        raise ValueError("rollover must advance week; never rewrite an existing weekly freeze")
    with (site / "projections.csv").open() as stream:
        fields = csv.DictReader(stream).fieldnames
    rows, gates = rows_for(doc, fields)
    text = io.StringIO(); writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    cfg.update(currentWeek=week, lastUpdated=doc["frozenAt"], generatedAtUtc=doc["frozenAt"],
               modelVersion=f"NFL Week {week} frozen baseline research", gamesInCurrentSlate=len(rows)+len(doc["excludedAlreadyStartedGameIds"]),
               gamesWithResearchProjections=len(rows), excludedAlreadyStartedGameIds=doc["excludedAlreadyStartedGameIds"],
               publicationStatus=f"{len(rows)} remaining Week {week} games have frozen baseline research; final context unverified; no pregame backfill for completed games",
               finalAuditArtifact=str(freeze.relative_to(root)), researchProjectionSha256=digest(freeze.read_bytes()),
               winProbabilityValidation="HOLD_NOT_GENERATED", completedProspectiveGames=0,
               currentContextAudit="nfl_data/site/personnel-gates.json", contextLastUpdated=None,
               inputCoveragePass=False, predictionAccuracy90PercentClaimed=False,
               spreadValidation="HOLD", totalValidation="HOLD", recommendationReleaseAllowed=False)
    research = {"updated": doc["frozenAt"], "categories": [{"id": "readiness", "label": "Readiness", "short": "Readiness", "status": "HOLD",
        "summary": doc["limitations"], "items": [{"title": f"Week {week} baseline research", "detail": cfg["publicationStatus"], "tag": "RESEARCH HOLD"}]}]}
    documents = {"config.json": json.dumps(cfg, indent=2)+"\n", "projections.csv": text.getvalue(),
                 "research.json": json.dumps(research, indent=2)+"\n",
                 "personnel-gates.json": json.dumps({"league": "nfl", "week": week, "canonicalInfluence": False,
                    "policy": "Unknown current-week personnel remains HOLD; no prior-week context carried forward.", "games": gates}, indent=2)+"\n"}
    archive = site / f"archive/week{old_week}-before-week{week}"
    archive.mkdir(parents=True, exist_ok=False)
    for name in documents:
        with (archive / name).open("xb") as stream:
            stream.write((site / name).read_bytes())
    for name, content in documents.items():
        (site / name).write_text(content)
    return audit(root)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--week", type=int); p.add_argument("--audit", action="store_true"); a = p.parse_args()
    if not a.audit and a.week is None:
        p.error("--week or --audit required")
    print(json.dumps(audit() if a.audit else publish(ROOT, a.week), indent=2))
