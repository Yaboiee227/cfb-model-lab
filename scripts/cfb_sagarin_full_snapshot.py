#!/usr/bin/env python3
"""Capture official Sagarin Predictor ratings and map them to a CFB weekly slate.

Research benchmark only. The output must never modify a canonical projection.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from record_tracker import atomic_json, canonical_team, load_aliases, norm_name

OFFICIAL_URL = "https://sagarin.com/sports/cfsend.htm"
RATING_RE = re.compile(
    r"^\s*(?P<rank>\d+)\s+(?P<team>.+?)\s+(?P<class>A{1,2})\s+=\s+"
    r"(?P<rating>-?\d+(?:\.\d+)?)\s+.*?\|\s+\d+\s+\d+\s+\|\s+"
    r"(?P<predictor>-?\d+(?:\.\d+)?)\s+\d+\s+\|",
    re.MULTILINE,
)
HFA_RE = re.compile(
    r"HOME\s+ADVANTAGE=\[\s*-?\d+(?:\.\d+)?\]\s+\[\s*(?P<predictor>-?\d+(?:\.\d+)?)\]",
    re.IGNORECASE,
)
THROUGH_RE = re.compile(r"through games of\s+(?P<through>.+?)\s+-\s+Week\s+(?P<week>\d+)", re.IGNORECASE)

# Sagarin display names that differ materially from common ESPN names. The normal
# team-alias registry is still applied after this source-specific normalization.
SOURCE_NAME_MAP = {
    "Fla. International": "Florida International",
    "Appalachian State": "App State",
    "Sam Houston State": "Sam Houston",
    "Connecticut": "UConn",
    "Miami-Florida": "Miami",
    "Miami-Ohio": "Miami (OH)",
    "North Carolina State": "NC State",
    "Southern California": "USC",
    "Brigham Young": "BYU",
    "Texas-San Antonio": "UTSA",
    "Louisiana-Lafayette": "Louisiana",
    "Louisiana-Monroe": "UL Monroe",
}


def fetch_text(url: str = OFFICIAL_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "CBModelBenchmark/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8", errors="replace")
    # The source is preformatted HTML. Converting tags to line breaks/spaces makes
    # parsing stable whether the server returns PRE text or lightly marked-up HTML.
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return html_lib.unescape(raw).replace("\r", "")


def parse_ratings(text: str) -> tuple[dict[str, dict[str, Any]], float, dict[str, Any]]:
    hfa_match = HFA_RE.search(text)
    if not hfa_match:
        raise ValueError("Official Sagarin Predictor home advantage not found")
    predictor_hfa = float(hfa_match.group("predictor"))

    through_match = THROUGH_RE.search(text)
    source_meta = {
        "ratingsThrough": through_match.group("through").strip() if through_match else None,
        "sourceWeek": int(through_match.group("week")) if through_match else None,
    }

    ratings: dict[str, dict[str, Any]] = {}
    for match in RATING_RE.finditer(text):
        raw_name = re.sub(r"\s+", " ", match.group("team")).strip()
        mapped_name = SOURCE_NAME_MAP.get(raw_name, raw_name)
        key = norm_name(mapped_name)
        ratings[key] = {
            "sourceName": raw_name,
            "mappedName": mapped_name,
            "rank": int(match.group("rank")),
            "classification": match.group("class"),
            "rating": float(match.group("rating")),
            "predictor": float(match.group("predictor")),
        }
    if len(ratings) < 120:
        raise ValueError(f"Too few Sagarin team ratings parsed: {len(ratings)}")
    return ratings, predictor_hfa, source_meta


def _rating_for(team: str, ratings: dict[str, dict[str, Any]], aliases: dict[str, str]) -> dict[str, Any] | None:
    candidates = [team, canonical_team(team, aliases)]
    for candidate in candidates:
        direct = ratings.get(norm_name(candidate))
        if direct:
            return direct
    # Reverse alias comparison lets source names resolve to the same canonical team.
    target = canonical_team(team, aliases)
    hits = []
    for row in ratings.values():
        if canonical_team(row["mappedName"], aliases) == target:
            hits.append(row)
    return hits[0] if len(hits) == 1 else None


def build_snapshot(
    schedule: dict[str, Any],
    text: str,
    aliases: dict[str, str],
    observed_at: str,
    min_coverage: float = 0.90,
) -> dict[str, Any]:
    ratings, predictor_hfa, source_meta = parse_ratings(text)
    games = []
    unresolved = []

    for game in schedule.get("games", []):
        away = _rating_for(game["awayTeam"], ratings, aliases)
        home = _rating_for(game["homeTeam"], ratings, aliases)
        row = {
            "gameId": game["gameId"],
            "sourceGameId": game.get("sourceGameId"),
            "awayTeam": game["awayTeam"],
            "homeTeam": game["homeTeam"],
            "kickoff": game["kickoff"],
        }
        if not away or not home:
            missing = []
            if not away:
                missing.append(game["awayTeam"])
            if not home:
                missing.append(game["homeTeam"])
            unresolved.extend(missing)
            row["sagarin"] = {"status": "REVIEW", "missingTeams": missing}
        else:
            margin_home = float(home["predictor"]) - float(away["predictor"])
            if not game.get("neutralSite"):
                margin_home += predictor_hfa
            row["sagarin"] = {
                "status": "CURRENT",
                "awayPredictor": away["predictor"],
                "homePredictor": home["predictor"],
                "predictorHomeAdvantage": 0.0 if game.get("neutralSite") else predictor_hfa,
                "impliedHomeMargin": margin_home,
                "impliedSpreadHome": -margin_home,
                "predictorFavorite": game["homeTeam"] if margin_home > 0 else game["awayTeam"] if margin_home < 0 else "PICK",
                "predictorMargin": abs(margin_home),
                "awaySourceName": away["sourceName"],
                "homeSourceName": home["sourceName"],
            }
        games.append(row)

    resolved = sum(g["sagarin"]["status"] == "CURRENT" for g in games)
    coverage = resolved / len(games) if games else 0.0
    if coverage < min_coverage:
        raise ValueError(
            f"Sagarin schedule coverage {coverage:.3f} below required {min_coverage:.3f}; unresolved={sorted(set(unresolved))}"
        )

    return {
        "schemaVersion": 1,
        "league": "cfb",
        "season": schedule.get("season"),
        "week": schedule.get("week"),
        "role": "OFFICIAL_EXTERNAL_BENCHMARK_SNAPSHOT",
        "canonicalInfluence": False,
        "observedAt": observed_at,
        "source": {
            "sourceId": "sagarin-cfb",
            "publisher": "Jeff Sagarin",
            "officialUrl": OFFICIAL_URL,
            "status": "CURRENT",
            "ratingsThrough": source_meta["ratingsThrough"],
            "sourceWeek": source_meta["sourceWeek"],
            "predictorHomeAdvantage": predictor_hfa,
        },
        "coverage": {
            "scheduleGames": len(games),
            "resolvedGames": resolved,
            "ratio": coverage,
            "unresolvedTeams": sorted(set(unresolved)),
        },
        "games": games,
        "policy": "Official Sagarin benchmark only. These values are independent comparison evidence and cannot change frozen CB projections or canonical grades.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", default="cfb/pregame/week-08-schedule.json")
    ap.add_argument("--output", default="cfb/benchmarks/week-08-sagarin-full.json")
    ap.add_argument("--source-file", help="Optional saved official Sagarin HTML/text for deterministic replay")
    ap.add_argument("--min-coverage", type=float, default=0.90)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    text = Path(args.source_file).read_text(encoding="utf-8") if args.source_file else fetch_text()
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    out = build_snapshot(schedule, text, load_aliases(Path(args.root)), observed_at, args.min_coverage)
    atomic_json(Path(args.output), out)
    print(json.dumps({"source": out["source"], "coverage": out["coverage"], "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
