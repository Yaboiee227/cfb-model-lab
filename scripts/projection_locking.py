#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

# Fields that define the published projection position and its grading benchmark.
# External benchmarks/context are frozen with the game for auditability but never
# participate in ATS/Total/SU grading.
IMMUTABLE_GAME_FIELDS = [
    "gameId",
    "sourceGameId",
    "awayTeam",
    "homeTeam",
    "kickoff",
    "projectedSpreadHome",
    "projectedTotal",
    "projectedWinner",
    "marketSpreadHome",
    "marketTotal",
    "marketMoneylineHome",
    "marketMoneylineAway",
    "marketSource",
    "marketObservedAt",
    "benchmarkSnapshot",
    "contextSnapshot",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp must include timezone: {value}")
    return dt.astimezone(timezone.utc)


def immutable_game_payload(game: dict[str, Any]) -> dict[str, Any]:
    return {key: game.get(key) for key in IMMUTABLE_GAME_FIELDS}


def game_digest(game: dict[str, Any]) -> str:
    raw = json.dumps(
        immutable_game_payload(game),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def lock_game(game: dict[str, Any], locked_at: str | None = None) -> dict[str, Any]:
    """Lock one game without freezing later-kickoff games in the same weekly file."""
    if game.get("locked") is True:
        validate_game_lock(game)
        return game

    stamp = locked_at or utcnow_iso()
    kickoff = parse_dt(game["kickoff"])
    lock_dt = parse_dt(stamp)
    if lock_dt > kickoff:
        raise ValueError(f"Cannot lock {game.get('gameId')} after kickoff")

    game["locked"] = True
    game["lockedAt"] = stamp
    game["lockDigest"] = game_digest(game)
    return game


def validate_game_lock(game: dict[str, Any]) -> None:
    if game.get("locked") is not True:
        raise ValueError(f"Game is not locked: {game.get('gameId')}")
    if not game.get("lockedAt"):
        raise ValueError(f"Game missing lockedAt: {game.get('gameId')}")
    if not game.get("lockDigest"):
        raise ValueError(f"Game missing lockDigest: {game.get('gameId')}")
    if game["lockDigest"] != game_digest(game):
        raise ValueError(
            f"LOCK VIOLATION: immutable projection/market/benchmark fields changed for {game.get('gameId')}"
        )
    if parse_dt(game["lockedAt"]) > parse_dt(game["kickoff"]):
        raise ValueError(f"lockedAt is after kickoff for {game.get('gameId')}")


def validate_week_locks(payload: dict[str, Any], require_all: bool = True) -> None:
    games = payload.get("games", [])
    if not games:
        raise ValueError("Projection snapshot has no games")
    unlocked = []
    for game in games:
        if game.get("locked") is True:
            validate_game_lock(game)
        else:
            unlocked.append(game.get("gameId"))
    if require_all and unlocked:
        raise ValueError("Unlocked projection games: " + ", ".join(map(str, unlocked)))


def lock_games_before(
    payload: dict[str, Any],
    cutoff: datetime,
    locked_at: str | None = None,
) -> list[str]:
    """Lock every unlocked game whose kickoff is on/before cutoff."""
    if cutoff.tzinfo is None:
        raise ValueError("cutoff must be timezone-aware")
    cutoff = cutoff.astimezone(timezone.utc)
    locked_ids: list[str] = []
    for game in payload.get("games", []):
        if game.get("locked") is True:
            validate_game_lock(game)
            continue
        if parse_dt(game["kickoff"]) <= cutoff:
            lock_game(game, locked_at=locked_at)
            locked_ids.append(str(game.get("gameId")))
    return locked_ids
