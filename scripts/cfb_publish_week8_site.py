#!/usr/bin/env python3
"""Publish the immutable Week 8 CFB research-shadow board to the static site.

This script never recomputes projections. It reads the immutable prospective
foundation lock and only joins timestamped sportsbook context for display.
Canonical/challenger/benchmark boundaries remain explicit.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "cfb/research-locks/week-08-foundation-full.json"
MARKETS = ROOT / "data/markets-sportsbooks.json"
ALIASES = ROOT / "data/team-aliases.json"
PROJECTIONS_OUT = ROOT / "data/projections.csv"
CONFIG_OUT = ROOT / "data/config.json"
ET = ZoneInfo("America/New_York")

FIELDS = [
    "season","week","date","kickoffET","gameId","awayTeam","awayConference",
    "homeTeam","homeConference","projectedAwayPoints","projectedHomePoints",
    "modelSpreadHome","modelTotal","homeWinProbability","awayWinProbability",
    "marketSpreadHome","marketTotal","marketSource","marketObservedAt",
    "executionVerified","dataQuality","signalStrength","releaseStatus","notes",
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def alias_groups(alias_map: dict[str, list[str]]):
    groups = []
    for canonical, values in alias_map.items():
        variants = {clean(canonical), *(clean(v) for v in values)}
        groups.append((clean(canonical), {v for v in variants if v}))
    return groups


def team_key(name: str, groups) -> str:
    n = clean(name)
    for canonical, variants in groups:
        if n in variants:
            return canonical
        if any(len(v) >= 5 and (n.startswith(v + " ") or v.startswith(n + " ")) for v in variants):
            return canonical
    return n


def same_team(a: str, b: str, groups) -> bool:
    ka, kb = team_key(a, groups), team_key(b, groups)
    if ka == kb:
        return True
    return len(ka) >= 5 and len(kb) >= 5 and (ka.startswith(kb + " ") or kb.startswith(ka + " "))


def market_for(game: dict, feed: dict, groups):
    kickoff = datetime.fromisoformat(game["kickoff"].replace("Z", "+00:00"))
    candidates = []
    for row in feed.get("games", []):
        if not same_team(game["awayTeam"], row.get("awayTeam", ""), groups):
            continue
        if not same_team(game["homeTeam"], row.get("homeTeam", ""), groups):
            continue
        try:
            mk = datetime.fromisoformat(row["commenceTime"].replace("Z", "+00:00"))
            if abs((mk - kickoff).total_seconds()) > 4 * 3600:
                continue
        except Exception:
            pass
        candidates.append(row)
    if not candidates:
        return None, None
    row = candidates[0]
    books = row.get("books", {})
    for key, label in (("draftkings", "DraftKings tracked context"), ("fanduel", "FanDuel tracked context")):
        book = books.get(key)
        if book:
            return book, label
    return None, None


def csv_text(foundation: dict, feed: dict, aliases: dict) -> str:
    groups = alias_groups(aliases)
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    for game in foundation["games"]:
        kickoff = datetime.fromisoformat(game["kickoff"].replace("Z", "+00:00")).astimezone(ET)
        book, market_label = market_for(game, feed, groups)
        spread = book.get("spread", {}) if book else {}
        total = book.get("total", {}) if book else {}
        observed = book.get("updatedAt", "") if book else ""
        hp = float(game["homeWinProbability"])
        writer.writerow({
            "season": foundation["season"],
            "week": foundation["week"],
            "date": kickoff.date().isoformat(),
            "kickoffET": kickoff.strftime("%-I:%M %p"),
            "gameId": game["gameId"],
            "awayTeam": game["awayTeam"],
            "awayConference": "",
            "homeTeam": game["homeTeam"],
            "homeConference": "",
            "projectedAwayPoints": f'{float(game["projectedAwayPoints"]):.8f}',
            "projectedHomePoints": f'{float(game["projectedHomePoints"]):.8f}',
            "modelSpreadHome": f'{float(game["projectedSpreadHome"]):.8f}',
            "modelTotal": f'{float(game["projectedTotal"]):.8f}',
            "homeWinProbability": f"{hp:.8f}",
            "awayWinProbability": f"{100.0-hp:.8f}",
            "marketSpreadHome": spread.get("home", ""),
            "marketTotal": total.get("point", ""),
            "marketSource": market_label or "",
            "marketObservedAt": observed,
            "executionVerified": "false",
            "dataQuality": "",
            "signalStrength": "RESEARCH SHADOW",
            "releaseStatus": "HOLD · PROSPECTIVE RESEARCH SHADOW",
            "notes": f'Immutable foundation digest {game["projectionDigest"]}; market is benchmark/context only',
        })
    return out.getvalue()


def config_json(foundation: dict, feed: dict) -> str:
    stamp = feed.get("generatedAt") or foundation["lockedAt"]
    dt = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(ET)
    cfg = {
        "siteName": "CB Model Projections",
        "season": foundation["season"],
        "currentWeek": foundation["week"],
        "lastUpdated": dt.strftime("%B %-d, %Y · %-I:%M %p ET"),
        "modelVersion": "CFB rebuild foundation v1 · Week 8 prospective research shadow",
        "spreadValidation": "HOLD",
        "totalValidation": "HOLD",
        "publicationStatus": "Week 8 full-slate research shadow · canonical release on HOLD",
        "venmoUrl": "https://venmo.com/u/Kaleb_InThe_Cut",
        "repoUrl": "https://github.com/Yaboiee227/cfb-model-lab",
        "disclaimer": "All content on CB Model Projections is model-generated and provided for research and entertainment purposes only. It is not betting advice and not an official wager recommendation. Past performance does not guarantee future results. Must be 21+ (or the legal age in your jurisdiction). If you or someone you know has a gambling problem, call 1-800-GAMBLER.",
    }
    return json.dumps(cfg, indent=2) + "\n"


def main() -> None:
    foundation, feed, aliases = load(FOUNDATION), load(MARKETS), load(ALIASES)
    assert foundation["role"] == "IMMUTABLE_PROSPECTIVE_RESEARCH_SHADOW_LOCK"
    assert foundation["canonicalInfluence"] is False
    assert foundation["canonicalPromotionAuthorized"] is False
    assert len(foundation["games"]) == 56, len(foundation["games"])
    PROJECTIONS_OUT.write_text(csv_text(foundation, feed, aliases), encoding="utf-8")
    CONFIG_OUT.write_text(config_json(foundation, feed), encoding="utf-8")
    print(json.dumps({
        "gamesPublished": 56,
        "foundationLockDigest": foundation.get("lockDigest"),
        "marketSnapshot": feed.get("generatedAt"),
        "canonicalInfluence": False,
    }, indent=2))


if __name__ == "__main__":
    main()
