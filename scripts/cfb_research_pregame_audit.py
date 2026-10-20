#!/usr/bin/env python3
"""Audit full-week CFB research pregame coverage without implying canonical readiness.

The audit is a work queue around an already-frozen research projection. It tracks
context/benchmark/market-capture completeness and kickoff priority, but no field in
this artifact may modify the immutable foundation projection.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lock_research_shadow import verify as verify_research_lock
from record_tracker import atomic_json, canonical_team, load_aliases


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timezone required: {value}")
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def priority_for(kickoff: datetime, as_of: datetime) -> str:
    hours = (kickoff - as_of).total_seconds() / 3600.0
    if hours <= 0:
        return "STARTED_OR_PAST"
    if hours <= 2:
        return "FINAL_WINDOW"
    if hours <= 24:
        return "TODAY"
    if hours <= 48:
        return "NEXT_48H"
    if hours <= 72:
        return "NEXT_72H"
    return "LATER_WEEK"


def same_game(a: dict[str, Any], b: dict[str, Any], aliases: dict[str, str]) -> bool:
    a_source = str(a.get("sourceGameId") or "")
    b_source = str(b.get("sourceGameId") or "")
    if a_source and b_source and a_source == b_source:
        return True
    if str(a.get("kickoff")) != str(b.get("kickoff")):
        return False
    return (
        canonical_team(a.get("awayTeam"), aliases) == canonical_team(b.get("awayTeam"), aliases)
        and canonical_team(a.get("homeTeam"), aliases) == canonical_team(b.get("homeTeam"), aliases)
    )


def unique_match(game: dict[str, Any], rows: list[dict[str, Any]], aliases: dict[str, str], label: str) -> dict[str, Any] | None:
    hits = [row for row in rows if same_game(game, row, aliases)]
    if len(hits) > 1:
        raise ValueError(f"ambiguous {label} match for {game.get('gameId')}")
    return hits[0] if hits else None


def _context_docs(context: Any) -> list[tuple[str, dict[str, Any]]]:
    if not context:
        return []
    if isinstance(context, dict):
        return [(str(context.get("_contextSource") or "inline-context"), context)]
    docs: list[tuple[str, dict[str, Any]]] = []
    for item in context:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict):
            docs.append((str(item[0]), item[1]))
        elif isinstance(item, dict):
            docs.append((str(item.get("_contextSource") or "inline-context"), item))
        else:
            raise ValueError("context entries must be documents or (source, document) pairs")
    return docs


def context_status(game: dict[str, Any], context: Any, aliases: dict[str, str]) -> dict[str, Any]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for source, doc in _context_docs(context):
        match = unique_match(game, doc.get("games") or [], aliases, f"pregame context in {source}")
        if match:
            matches.append((source, match))
    if len(matches) > 1:
        sources = ", ".join(source for source, _ in matches)
        raise ValueError(f"ambiguous pregame context across files for {game.get('gameId')}: {sources}")
    if not matches:
        return {
            "personnel": "NOT_CAPTURED",
            "weather": "NOT_CAPTURED",
            "referee": "NOT_CAPTURED",
            "marketContext": "NOT_CAPTURED",
            "contextSource": None,
        }
    source, match = matches[0]
    personnel = match.get("personnel") or {}
    weather = match.get("weather") or {}
    market = match.get("market") or {}
    refs = ((match.get("benchmarks") or {}).get("refMetrics") or {})
    return {
        "personnel": str(personnel.get("status") or "UNKNOWN").upper(),
        "weather": str(weather.get("status") or "UNKNOWN").upper(),
        "referee": str(refs.get("status") or "UNKNOWN").upper(),
        "marketContext": str(market.get("status") or "UNKNOWN").upper(),
        "contextSource": source,
    }


def market_lock_status(game: dict[str, Any], market_lock: dict[str, Any] | None, aliases: dict[str, str], as_of: datetime) -> dict[str, Any]:
    kickoff = parse_dt(game["kickoff"])
    if not market_lock:
        return {
            "status": "MISSED" if as_of >= kickoff else "PENDING",
            "booksLocked": [],
            "bookCount": 0,
        }
    match = unique_match(game, market_lock.get("games") or [], aliases, "market lock")
    if not match:
        return {
            "status": "MISSED" if as_of >= kickoff else "PENDING",
            "booksLocked": [],
            "bookCount": 0,
        }
    books = sorted((match.get("books") or {}).keys())
    return {
        "status": str(match.get("status") or ("LOCKED" if books else "PENDING")).upper(),
        "booksLocked": books,
        "bookCount": len(books),
    }


def build_audit(
    schedule: dict[str, Any],
    foundation: dict[str, Any],
    sagarin: dict[str, Any],
    aliases: dict[str, str],
    as_of: datetime,
    context: Any = None,
    market_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_research_lock(foundation)
    if foundation.get("canonicalInfluence") is not False or foundation.get("canonicalPromotionAuthorized") is not False:
        raise ValueError("foundation must remain research-only")
    if sagarin.get("canonicalInfluence") is not False:
        raise ValueError("Sagarin benchmark must remain non-canonical")
    source = sagarin.get("source") or {}
    if source.get("sourceId") != "sagarin-cfb":
        raise ValueError("expected official Sagarin CFB snapshot")

    schedule_games = schedule.get("games") or []
    foundation_games = foundation.get("games") or []
    sagarin_games = sagarin.get("games") or []
    out_games: list[dict[str, Any]] = []

    for game in schedule_games:
        kickoff = parse_dt(game["kickoff"])
        priority = priority_for(kickoff, as_of)
        locked = unique_match(game, foundation_games, aliases, "foundation")
        benchmark = unique_match(game, sagarin_games, aliases, "Sagarin")
        ctx = context_status(game, context, aliases)
        market = market_lock_status(game, market_lock, aliases, as_of)

        gaps: list[str] = []
        warnings: list[str] = []
        foundation_status = "LOCKED" if locked and locked.get("projectionDigest") else "MISSING"
        if foundation_status != "LOCKED":
            gaps.append("frozen foundation projection missing")
        sag_status = str(((benchmark or {}).get("sagarin") or {}).get("status") or "MISSING").upper()
        if sag_status != "CURRENT":
            warnings.append(f"official Sagarin benchmark status: {sag_status}")

        personnel = ctx["personnel"]
        weather = ctx["weather"]
        referee = ctx["referee"]
        if personnel == "NOT_CAPTURED":
            gaps.append("personnel context not yet captured")
        elif any(x in personnel for x in ("UNRESOLVED", "MATERIAL_QB", "REFRESH_REQUIRED", "FINAL_RECHECK_REQUIRED", "SOURCE_CONFLICT")):
            gaps.append(f"personnel requires follow-up: {personnel}")
        if weather == "NOT_CAPTURED":
            gaps.append("weather context not yet captured")
        elif any(x in weather for x in ("FINAL_RECHECK_REQUIRED", "REFRESH_REQUIRED", "STALE", "UNKNOWN")):
            gaps.append(f"weather final review pending: {weather}")
        if any(x in referee for x in ("NOT_CAPTURED", "NOT_YET_POSTED", "UNKNOWN", "UNAVAILABLE", "STALE")):
            warnings.append(f"referee assignment status: {referee}; do not guess")
        if market["status"] != "LOCKED":
            if priority in {"FINAL_WINDOW", "STARTED_OR_PAST"}:
                gaps.append(f"immutable final-window market status: {market['status']}")
            else:
                warnings.append("immutable final-window market lock pending")

        if priority == "LATER_WEEK" and ctx["personnel"] == "NOT_CAPTURED":
            urgency = "PLANNED"
        elif priority in {"FINAL_WINDOW", "TODAY"} and gaps:
            urgency = "CRITICAL"
        elif priority in {"NEXT_48H", "NEXT_72H"} and gaps:
            urgency = "HIGH"
        elif gaps:
            urgency = "NORMAL"
        else:
            urgency = "MONITOR"

        out_games.append(
            {
                "gameId": game["gameId"],
                "sourceGameId": game.get("sourceGameId"),
                "awayTeam": game["awayTeam"],
                "homeTeam": game["homeTeam"],
                "kickoff": game["kickoff"],
                "priority": priority,
                "urgency": urgency,
                "foundation": {
                    "status": foundation_status,
                    "projectionDigest": locked.get("projectionDigest") if locked else None,
                },
                "benchmarks": {
                    "sagarin": sag_status,
                    "spPlus": "PENDING_OFFICIAL_CAPTURE",
                },
                "context": ctx,
                "marketLock": market,
                "gaps": gaps,
                "warnings": warnings,
            }
        )

    order = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "PLANNED": 3, "MONITOR": 4}
    queue = sorted(
        [g for g in out_games if g["urgency"] != "MONITOR"],
        key=lambda g: (order[g["urgency"]], parse_dt(g["kickoff"]), g["gameId"]),
    )
    summary = {
        "games": len(out_games),
        "foundationLocked": sum(g["foundation"]["status"] == "LOCKED" for g in out_games),
        "sagarinCurrent": sum(g["benchmarks"]["sagarin"] == "CURRENT" for g in out_games),
        "personnelCaptured": sum(g["context"]["personnel"] != "NOT_CAPTURED" for g in out_games),
        "weatherCaptured": sum(g["context"]["weather"] != "NOT_CAPTURED" for g in out_games),
        "refereeCapturedOrExplicitlyChecked": sum(g["context"]["referee"] != "NOT_CAPTURED" for g in out_games),
        "gamesWithMarketLock": sum(g["marketLock"]["status"] == "LOCKED" for g in out_games),
        "critical": sum(g["urgency"] == "CRITICAL" for g in out_games),
        "high": sum(g["urgency"] == "HIGH" for g in out_games),
    }
    if summary["foundationLocked"] != len(out_games):
        raise ValueError(f"foundation lock coverage incomplete: {summary['foundationLocked']}/{len(out_games)}")
    if summary["sagarinCurrent"] != len(out_games):
        raise ValueError(f"Sagarin coverage incomplete: {summary['sagarinCurrent']}/{len(out_games)}")

    return {
        "schemaVersion": 1,
        "league": "cfb",
        "season": schedule.get("season"),
        "week": schedule.get("week"),
        "role": "FULL_WEEK_RESEARCH_PREGAME_COVERAGE_AUDIT",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "auditedAt": iso(as_of),
        "summary": summary,
        "workQueue": [
            {
                "gameId": g["gameId"],
                "awayTeam": g["awayTeam"],
                "homeTeam": g["homeTeam"],
                "kickoff": g["kickoff"],
                "priority": g["priority"],
                "urgency": g["urgency"],
                "gaps": g["gaps"],
                "warnings": g["warnings"],
            }
            for g in queue
        ],
        "games": out_games,
        "policy": "Operational research audit only. Context gaps prioritize source collection but cannot rewrite the immutable foundation. Official benchmarks and locked markets remain comparison layers only; unknown facts stay unknown.",
    }


def stable_payload(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "auditedAt"}


def preserve_audited_at_if_unchanged(new: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if existing and stable_payload(new) == stable_payload(existing):
        new["auditedAt"] = existing.get("auditedAt", new["auditedAt"])
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", default="cfb/pregame/week-08-schedule.json")
    ap.add_argument("--foundation", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--sagarin", default="cfb/benchmarks/week-08-sagarin-full.json")
    ap.add_argument("--context", dest="contexts", action="append", help="Repeat for each day-specific pregame context file")
    ap.add_argument("--market-lock", default="cfb/research-market-locks/week-08-foundation-market.json")
    ap.add_argument("--output", default="cfb/pregame/week-08-research-coverage.json")
    ap.add_argument("--as-of")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root)
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    foundation = json.loads(Path(args.foundation).read_text(encoding="utf-8"))
    sagarin = json.loads(Path(args.sagarin).read_text(encoding="utf-8"))
    context_names = args.contexts or [
        "cfb/pregame/week-08-tuesday-effective.json",
        "cfb/pregame/week-08-wednesday-effective.json",
    ]
    contexts: list[tuple[str, dict[str, Any]]] = []
    for name in context_names:
        context_path = Path(name)
        if context_path.exists():
            contexts.append((str(context_path), json.loads(context_path.read_text(encoding="utf-8"))))
    market_path = Path(args.market_lock)
    market_lock = json.loads(market_path.read_text(encoding="utf-8")) if market_path.exists() else None
    as_of = parse_dt(args.as_of) if args.as_of else datetime.now(timezone.utc)
    out = build_audit(schedule, foundation, sagarin, load_aliases(root), as_of, contexts, market_lock)

    output = Path(args.output)
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    out = preserve_audited_at_if_unchanged(out, existing)
    atomic_json(output, out)
    print(json.dumps({"auditedAt": out["auditedAt"], "summary": out["summary"], "next": out["workQueue"][:8]}, indent=2))


if __name__ == "__main__":
    main()

