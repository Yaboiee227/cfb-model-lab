#!/usr/bin/env python3
"""Build the resumed Week 8 CFB pregame scope from saved schedule + frozen foundation.

Operational only: this does not change any projection. It supersedes the earlier
Tue-Thu pause after explicit user direction to process the entire remaining Week
8 slate. Completed Tuesday games are preserved but excluded from the resumed
pregame scope; Wednesday through Saturday games are included.

The schedule's public gameId uses the America/New_York game date while some
frozen foundation IDs were formed from the UTC kickoff date. Therefore the
cross-artifact integrity join is teams + exact kickoff, with the frozen digest
carried forward as the immutable projection identity.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm_team(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def identity(game: dict) -> tuple[str, str, str]:
    return (
        norm_team(game.get("awayTeam", "")),
        norm_team(game.get("homeTeam", "")),
        str(game.get("kickoff", "")),
    )


def build(schedule: dict, foundation: dict, start_date: str = "2026-10-21") -> dict:
    if schedule.get("week") != 8 or foundation.get("week") != 8:
        raise ValueError("expected Week 8 inputs")
    if foundation.get("canonicalInfluence") is not False:
        raise ValueError("foundation must remain non-canonical")

    frozen: dict[tuple[str, str, str], dict] = {}
    for row in foundation.get("games", []):
        key = identity(row)
        if key in frozen:
            raise ValueError(f"duplicate foundation matchup identity: {key}")
        frozen[key] = row

    rows = []
    for game in schedule.get("games", []):
        if str(game.get("gameDateET")) < start_date:
            continue
        key = identity(game)
        match = frozen.get(key)
        if not match:
            raise ValueError(f"schedule game missing from foundation by teams+kickoff: {game.get('gameId')} {key}")
        digest = match.get("projectionDigest")
        if not digest:
            raise ValueError(f"foundation game missing digest: {match.get('gameId')}")
        rows.append({
            "gameId": game["gameId"],
            "foundationGameId": match.get("gameId"),
            "sourceGameId": game.get("sourceGameId"),
            "gameDateET": game["gameDateET"],
            "awayTeam": game["awayTeam"],
            "homeTeam": game["homeTeam"],
            "kickoff": game["kickoff"],
            "foundationDigest": digest,
        })

    rows.sort(key=lambda g: (g["kickoff"], g["gameId"]))
    if len(rows) != 53:
        raise ValueError(f"expected 53 remaining Week 8 games from Oct 21-24; got {len(rows)}")
    if len({g["foundationDigest"] for g in rows}) != len(rows):
        raise ValueError("duplicate foundation digest in full-week scope")

    return {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "week": 8,
        "role": "ACTIVE_PREGAME_PROCESSING_SCOPE",
        "status": "ACTIVE_REMAINING_FULL_WEEK",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "activatedAt": iso_now(),
        "timezone": "America/New_York",
        "sourceSchedule": "cfb/pregame/week-08-schedule.json",
        "frozenFoundation": "cfb/research-locks/week-08-foundation-full.json",
        "sourceRegistry": "MODEL_SOURCES.md",
        "supersedesScope": "cfb/pregame/week-08-active-through-thursday.json",
        "dateWindowET": ["2026-10-21", "2026-10-24"],
        "includedGameCount": len(rows),
        "processingRules": {
            "collectBroadlyPromoteNarrowly": True,
            "pregameOnly": True,
            "preserveSourceTimestamps": True,
            "preserveFrozenProjectionDigests": True,
            "externalBenchmarksAreNonCanonical": True,
            "marketsCannotRewriteFoundation": True,
            "unknownStaysUnknown": True,
            "fridayProcessingAuthorized": True,
            "saturdayProcessingAuthorized": True,
            "gradingDeferredUntilWeekComplete": True,
            "resumeAuthorizedByUser": True,
        },
        "layerPolicy": {
            "canonical": "No canonical architecture/coefficient change during Week 8 without leakage-safe validation and explicit promotion.",
            "researchFoundation": "The existing frozen Week 8 foundation remains immutable and supplies the central research projection.",
            "challenger": "Only leakage-safe validated challengers may earn prospective shadow status; rejected challengers remain evidence only.",
            "benchmark": "Markets, SP+, Sagarin, external computer models and prediction markets are comparison/context unless separately validated and promoted.",
            "context": "Personnel, weather, travel/rest, coaching/news and trends are timestamped pregame context; no invented manual point adjustments."
        },
        "games": rows,
        "pauseBoundary": None,
        "gradingPolicy": "Do not use Week 8 outcomes to tune or alter any remaining Week 8 projection. Grade the full frozen week after completion."
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", default="cfb/pregame/week-08-schedule.json")
    ap.add_argument("--foundation", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--output", default="cfb/pregame/week-08-active-full-week.json")
    ap.add_argument("--start-date", default="2026-10-21")
    args = ap.parse_args()
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    foundation = json.loads(Path(args.foundation).read_text(encoding="utf-8"))
    out = build(schedule, foundation, args.start_date)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"games": len(out["games"]), "dateWindowET": out["dateWindowET"], "status": out["status"]}, indent=2))


if __name__ == "__main__":
    main()
