#!/usr/bin/env python3
"""Capture official Sagarin Predictor ratings and map them to a CFB weekly slate.

Research benchmark only. The output must never modify a canonical projection.
Sagarin currently presents a self-signed TLS certificate to GitHub-hosted runners.
A narrowly scoped certificate-verification fallback is allowed only for the exact
approved Sagarin URL, and any such capture must pass an independent known-game
crosscheck before it may be saved as a benchmark snapshot.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import ssl
import urllib.error
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
THROUGH_RE = re.compile(
    r"through (?:games|results) of\s+(?P<through>.+?)\s+-\s+Week\s+(?P<week>\d+)",
    re.IGNORECASE,
)

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


def _clean_html(raw: str) -> str:
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    return html_lib.unescape(raw).replace("\r", "")


def _request(url: str, context: ssl.SSLContext | None = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "CBModelBenchmark/1.0"})
    kwargs: dict[str, Any] = {"timeout": 30}
    if context is not None:
        kwargs["context"] = context
    with urllib.request.urlopen(req, **kwargs) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_text(url: str = OFFICIAL_URL) -> tuple[str, dict[str, Any]]:
    if url != OFFICIAL_URL:
        raise ValueError("Live Sagarin fetch is restricted to the approved official URL")
    try:
        raw = _request(url)
        transport = {
            "tlsVerified": True,
            "certificateWorkaroundUsed": False,
            "warning": None,
        }
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if not isinstance(reason, ssl.SSLCertVerificationError):
            raise
        # Narrow exception: exact approved host only. The caller must independently
        # crosscheck known pregame values before accepting output from this path.
        raw = _request(url, ssl._create_unverified_context())
        transport = {
            "tlsVerified": False,
            "certificateWorkaroundUsed": True,
            "warning": "Official Sagarin host presented a certificate that the GitHub runner could not verify; exact-host fallback used and independent known-game crosscheck required.",
        }
    return _clean_html(raw), transport


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


def ratings_through_iso(label: str | None, season: int | None) -> str:
    if not label or not season:
        raise ValueError("Sagarin ratings-through date/season unavailable")
    match = re.search(r"([A-Za-z]+)\s+(\d{1,2})", label)
    if not match:
        raise ValueError(f"Cannot normalize Sagarin ratings-through label: {label}")
    dt = datetime.strptime(f"{int(season)} {match.group(1)} {match.group(2)}", "%Y %B %d")
    return dt.date().isoformat()


def _rating_for(team: str, ratings: dict[str, dict[str, Any]], aliases: dict[str, str]) -> dict[str, Any] | None:
    candidates = [team, canonical_team(team, aliases)]
    for candidate in candidates:
        direct = ratings.get(norm_name(candidate))
        if direct:
            return direct
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
    transport: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ratings, predictor_hfa, source_meta = parse_ratings(text)
    ratings_through = ratings_through_iso(source_meta["ratingsThrough"], schedule.get("season"))
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
                "observedAt": observed_at,
                "ratingsThrough": ratings_through,
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

    source_block = {
        "sourceId": "sagarin-cfb",
        "publisher": "Jeff Sagarin",
        "officialUrl": OFFICIAL_URL,
        "status": "CURRENT",
        "ratingsThrough": ratings_through,
        "ratingsThroughLabel": source_meta["ratingsThrough"],
        "sourceWeek": source_meta["sourceWeek"],
        "predictorHomeAdvantage": predictor_hfa,
        "observedAt": observed_at,
        "transport": transport or {"tlsVerified": None, "certificateWorkaroundUsed": False, "warning": "Source text supplied from a saved capture."},
    }
    return {
        "schemaVersion": 1,
        "league": "cfb",
        "season": schedule.get("season"),
        "week": schedule.get("week"),
        "role": "OFFICIAL_EXTERNAL_BENCHMARK_SNAPSHOT",
        "canonicalInfluence": False,
        "observedAt": observed_at,
        "source": source_block,
        "sources": {"sagarin": source_block},
        "coverage": {
            "scheduleGames": len(games),
            "resolvedGames": resolved,
            "ratio": coverage,
            "unresolvedTeams": sorted(set(unresolved)),
        },
        "games": games,
        "policy": "Official Sagarin benchmark only. These values are independent comparison evidence and cannot change frozen CB projections or canonical grades.",
    }


def _same_matchup(a: dict[str, Any], b: dict[str, Any], aliases: dict[str, str]) -> bool:
    return (
        canonical_team(a.get("awayTeam"), aliases) == canonical_team(b.get("awayTeam"), aliases)
        and canonical_team(a.get("homeTeam"), aliases) == canonical_team(b.get("homeTeam"), aliases)
        and str(a.get("kickoff")) == str(b.get("kickoff"))
    )


def verify_crosscheck(
    snapshot: dict[str, Any],
    reference: dict[str, Any],
    aliases: dict[str, str],
    tolerance: float = 0.15,
) -> dict[str, Any]:
    checks = []
    for ref in reference.get("games", []):
        old = ref.get("sagarin") or {}
        if str(old.get("status", "")).upper() != "CURRENT" or old.get("impliedSpreadHome") is None:
            continue
        matches = [game for game in snapshot.get("games", []) if _same_matchup(game, ref, aliases)]
        if len(matches) != 1:
            raise ValueError(f"Sagarin crosscheck matchup resolution failed for {ref.get('gameId')}: {len(matches)} matches")
        new = matches[0].get("sagarin") or {}
        if str(new.get("status", "")).upper() != "CURRENT":
            raise ValueError(f"Sagarin crosscheck is not CURRENT for {ref.get('gameId')}")
        expected = float(old["impliedSpreadHome"])
        actual = float(new["impliedSpreadHome"])
        delta = actual - expected
        if abs(delta) > tolerance:
            raise ValueError(
                f"Sagarin known-game crosscheck failed for {ref.get('gameId')}: expected {expected}, derived {actual}, delta {delta}"
            )
        checks.append({"referenceGameId": ref.get("gameId"), "expectedSpreadHome": expected, "derivedSpreadHome": actual, "delta": delta})
    if len(checks) < 3:
        raise ValueError(f"Sagarin crosscheck requires >=3 known current games; found {len(checks)}")
    return {"status": "PASS", "games": len(checks), "tolerance": tolerance, "checks": checks}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", default="cfb/pregame/week-08-schedule.json")
    ap.add_argument("--output", default="cfb/benchmarks/week-08-sagarin-full.json")
    ap.add_argument("--source-file", help="Optional saved official Sagarin HTML/text for deterministic replay")
    ap.add_argument("--crosscheck", help="Existing independently captured Sagarin benchmark used to verify live-derived values")
    ap.add_argument("--min-coverage", type=float, default=0.90)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root)
    aliases = load_aliases(root)
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    if args.source_file:
        text = Path(args.source_file).read_text(encoding="utf-8")
        transport = {"tlsVerified": None, "certificateWorkaroundUsed": False, "warning": "Source text supplied from a saved capture."}
    else:
        text, transport = fetch_text()
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    out = build_snapshot(schedule, text, aliases, observed_at, args.min_coverage, transport)

    if args.crosscheck:
        reference = json.loads(Path(args.crosscheck).read_text(encoding="utf-8"))
        out["knownGameCrosscheck"] = verify_crosscheck(out, reference, aliases)
    elif transport.get("tlsVerified") is False:
        raise ValueError("Unverified-TLS Sagarin capture requires --crosscheck against independently captured known games")

    atomic_json(Path(args.output), out)
    print(json.dumps({"source": out["source"], "coverage": out["coverage"], "knownGameCrosscheck": out.get("knownGameCrosscheck"), "output": args.output}, indent=2))


if __name__ == "__main__":
    main()
