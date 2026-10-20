#!/usr/bin/env python3
"""Lock fresh sportsbook observations for frozen CFB research projections.

Each book is locked independently inside a final pre-kickoff window. Existing
book observations are immutable. This is research benchmarking only and never
creates or changes a canonical projection/performance record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lock_research_shadow import verify as verify_research_lock
from record_tracker import atomic_json, canonical_team, load_aliases, norm_name

BOOKS = ("fanduel", "draftkings")


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _candidate_norms(team: str, aliases: dict[str, str]) -> set[str]:
    canonical = canonical_team(team, aliases)
    norms = {norm_name(team), norm_name(canonical)}
    for alias_norm, alias_canonical in aliases.items():
        if alias_canonical == canonical:
            norms.add(alias_norm)
    return {x for x in norms if x}


def team_matches(team: str, market_name: str, aliases: dict[str, str]) -> bool:
    if canonical_team(team, aliases) == canonical_team(market_name, aliases):
        return True
    market_norm = norm_name(market_name)
    for candidate in _candidate_norms(team, aliases):
        if candidate == market_norm:
            return True
        # Odds feeds commonly append mascots to the school name. Prefix matching
        # handles that without broad internal substring matching (Miami vs Miami OH).
        if market_norm.startswith(candidate) or candidate.startswith(market_norm):
            return True
    return False


def match_market_game(game: dict[str, Any], markets: list[dict[str, Any]], aliases: dict[str, str]) -> dict[str, Any] | None:
    kickoff = parse_dt(game["kickoff"])
    hits = []
    for market in markets:
        try:
            market_kickoff = parse_dt(market["commenceTime"])
        except Exception:
            continue
        if abs((market_kickoff - kickoff).total_seconds()) > 5 * 60:
            continue
        if team_matches(game["homeTeam"], market.get("homeTeam", ""), aliases) and team_matches(
            game["awayTeam"], market.get("awayTeam", ""), aliases
        ):
            hits.append(market)
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ValueError(f"ambiguous sportsbook market match for {game.get('gameId')}")
    return None


def make_book_lock(
    game: dict[str, Any],
    book_name: str,
    book: dict[str, Any],
    now: datetime,
    max_observation_age_minutes: float,
) -> dict[str, Any] | None:
    observed_raw = book.get("updatedAt")
    if not observed_raw:
        return None
    observed = parse_dt(observed_raw)
    kickoff = parse_dt(game["kickoff"])
    age_minutes = (now - observed).total_seconds() / 60.0
    if observed >= kickoff or observed > now or age_minutes < 0 or age_minutes > max_observation_age_minutes:
        return None
    spread = (book.get("spread") or {}).get("home")
    total = (book.get("total") or {}).get("point")
    if spread is None or total is None:
        return None
    payload = {
        "book": book_name,
        "marketObservedAt": iso(observed),
        "lockedAt": iso(now),
        "marketSpreadHome": float(spread),
        "marketTotal": float(total),
        "marketMoneylineHome": (book.get("moneyline") or {}).get("home"),
        "marketMoneylineAway": (book.get("moneyline") or {}).get("away"),
        "spreadHomePrice": (book.get("spread") or {}).get("homePrice"),
        "totalOverPrice": (book.get("total") or {}).get("overPrice"),
        "totalUnderPrice": (book.get("total") or {}).get("underPrice"),
    }
    return {**payload, "observationDigest": digest(payload)}


def verify_existing(existing: dict[str, Any], foundation_lock: dict[str, Any]) -> None:
    if existing.get("role") != "IMMUTABLE_PREGAME_MARKET_RESEARCH_LOCK":
        raise ValueError("unexpected market research lock role")
    if existing.get("canonicalInfluence") is not False or existing.get("canonicalRecordMerged") is not False:
        raise ValueError("market research lock must remain non-canonical")
    if existing.get("foundationLockDigest") != foundation_lock.get("lockDigest"):
        raise ValueError("market research lock belongs to a different foundation lock")
    for game in existing.get("games", []):
        for book_name, observation in (game.get("books") or {}).items():
            payload = {k: v for k, v in observation.items() if k != "observationDigest"}
            if observation.get("observationDigest") != digest(payload):
                raise ValueError(f"market observation digest mismatch: {game.get('gameId')} {book_name}")


def merge_market_lock(
    foundation_lock: dict[str, Any],
    market_snapshot: dict[str, Any],
    existing: dict[str, Any] | None,
    aliases: dict[str, str],
    now: datetime,
    lock_window_minutes: float = 30.0,
    max_observation_age_minutes: float = 35.0,
) -> dict[str, Any]:
    verify_research_lock(foundation_lock)
    if existing:
        verify_existing(existing, foundation_lock)
        prior_games = {g["gameId"]: g for g in existing.get("games", [])}
    else:
        prior_games = {}

    market_games = market_snapshot.get("games") or []
    rows = []
    newly_locked = 0
    for game in foundation_lock.get("games", []):
        kickoff = parse_dt(game["kickoff"])
        prior = prior_games.get(game["gameId"], {})
        books = dict(prior.get("books") or {})
        seconds_to_kickoff = (kickoff - now).total_seconds()
        in_window = 0 < seconds_to_kickoff <= lock_window_minutes * 60
        market = match_market_game(game, market_games, aliases) if in_window else None

        if in_window and market is not None:
            for book_name in BOOKS:
                if book_name in books:
                    continue
                raw_book = (market.get("books") or {}).get(book_name)
                if not raw_book:
                    continue
                observation = make_book_lock(game, book_name, raw_book, now, max_observation_age_minutes)
                if observation:
                    books[book_name] = observation
                    newly_locked += 1

        rows.append(
            {
                "gameId": game["gameId"],
                "sourceGameId": game.get("sourceGameId"),
                "awayTeam": game["awayTeam"],
                "homeTeam": game["homeTeam"],
                "kickoff": game["kickoff"],
                "projectionDigest": game["projectionDigest"],
                "books": books,
                "status": "LOCKED" if books else ("MISSED" if now >= kickoff else "PENDING"),
            }
        )

    locked_games = sum(bool(r["books"]) for r in rows)
    locked_book_observations = sum(len(r["books"]) for r in rows)
    return {
        "schemaVersion": 1,
        "league": foundation_lock.get("league"),
        "season": foundation_lock.get("season"),
        "week": foundation_lock.get("week"),
        "role": "IMMUTABLE_PREGAME_MARKET_RESEARCH_LOCK",
        "canonicalInfluence": False,
        "canonicalRecordMerged": False,
        "foundationModelId": foundation_lock.get("modelId"),
        "foundationLockDigest": foundation_lock.get("lockDigest"),
        "provider": market_snapshot.get("provider"),
        "booksTracked": list(BOOKS),
        "lockWindowMinutes": lock_window_minutes,
        "maxObservationAgeMinutes": max_observation_age_minutes,
        "updatedAt": iso(now),
        "counts": {
            "foundationGames": len(rows),
            "gamesWithMarketLock": locked_games,
            "bookObservationsLocked": locked_book_observations,
            "newBookObservationsThisRun": newly_locked,
            "pendingGames": sum(r["status"] == "PENDING" for r in rows),
            "missedGames": sum(r["status"] == "MISSED" for r in rows),
        },
        "games": rows,
        "policy": "Research-only per-book publication-window capture. FanDuel and DraftKings are preserved independently; no consensus or canonical benchmark is inferred. Existing book observations are immutable and post-kickoff reconstruction is prohibited.",
    }


def stable_payload(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if k not in {"updatedAt"} and k != "counts"}


def preserve_updated_at_if_unchanged(new: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if not existing:
        return new
    # Ignore run counters/time when determining whether the durable lock changed.
    if stable_payload(new) == stable_payload(existing):
        new["updatedAt"] = existing.get("updatedAt", new["updatedAt"])
        new["counts"]["newBookObservationsThisRun"] = 0
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundation-lock", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--markets", default="data/markets-sportsbooks.json")
    ap.add_argument("--output", default="cfb/research-market-locks/week-08-foundation-market.json")
    ap.add_argument("--lock-window-minutes", type=float, default=30.0)
    ap.add_argument("--max-observation-age-minutes", type=float, default=35.0)
    ap.add_argument("--now", help="UTC/offset timestamp; tests/replay only. Defaults to current time.")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root)
    foundation = json.loads(Path(args.foundation_lock).read_text(encoding="utf-8"))
    markets = json.loads(Path(args.markets).read_text(encoding="utf-8"))
    output = Path(args.output)
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    now = parse_dt(args.now) if args.now else datetime.now(timezone.utc)
    out = merge_market_lock(
        foundation,
        markets,
        existing,
        load_aliases(root),
        now,
        args.lock_window_minutes,
        args.max_observation_age_minutes,
    )
    out = preserve_updated_at_if_unchanged(out, existing)
    atomic_json(output, out)
    print(json.dumps({"updatedAt": out["updatedAt"], "counts": out["counts"]}, indent=2))


if __name__ == "__main__":
    main()
