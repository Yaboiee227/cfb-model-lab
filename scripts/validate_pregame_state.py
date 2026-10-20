#!/usr/bin/env python3
"""Audit a CFB/NFL pregame state for game-level freeze readiness.

The auditor is intentionally conservative. It distinguishes true freeze blockers
from contextual warnings so missing SP+, late referee assignments, or minor
weather disagreement cannot be mistaken for permission to rewrite or delay a
canonical projection indefinitely.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timezone required: {value}")
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def audit_game(game: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    kickoff = parse_dt(game["kickoff"])
    minutes_to_kick = (kickoff - as_of).total_seconds() / 60.0
    if minutes_to_kick <= 0:
        blockers.append("audit timestamp is at/after kickoff; pregame canonical state may not be created or revised")

    projection = game.get("canonicalProjection") or {}
    required_projection = (
        "projectedSpreadHome",
        "projectedTotal",
        "projectedWinner",
        "homeWinProbability",
    )
    missing_projection = [k for k in required_projection if projection.get(k) is None]
    if missing_projection:
        blockers.append("canonical projection incomplete: " + ", ".join(missing_projection))
    if "SHADOW" in _upper(projection.get("status")):
        blockers.append("shadow/challenger output cannot stand in for the canonical projection")

    market = game.get("market") or {}
    market_status = _upper(market.get("status"))
    lock_ready_market_states = {"PUBLICATION_READY", "LOCK_READY", "LOCKED"}
    if market_status not in lock_ready_market_states:
        blockers.append("publication-time market is not lock-ready")

    observations = market.get("observations") or []
    valid_market_times: list[datetime] = []
    if not observations:
        blockers.append("no pregame market observation preserved")
    for obs in observations:
        source = obs.get("source")
        observed_at = obs.get("observedAt")
        if not source or not observed_at:
            blockers.append("market observation missing source or timestamp")
            continue
        try:
            obs_dt = parse_dt(observed_at)
        except Exception:
            blockers.append("market observation has invalid timestamp")
            continue
        if obs_dt >= kickoff:
            blockers.append("market observation is at/after kickoff")
        else:
            valid_market_times.append(obs_dt)

    if valid_market_times:
        latest_market = max(valid_market_times)
        age_minutes = max(0.0, (as_of - latest_market).total_seconds() / 60.0)
        if 0 < minutes_to_kick <= 90 and age_minutes > 90:
            blockers.append(f"latest market observation is {age_minutes:.0f} minutes old inside the final 90-minute window")
        elif age_minutes > 180:
            warnings.append(f"latest market observation is {age_minutes:.0f} minutes old")

    personnel = game.get("personnel") or {}
    personnel_status = _upper(personnel.get("status"))
    home_qb = _upper((personnel.get("home") or {}).get("startingQB"))
    away_qb = _upper((personnel.get("away") or {}).get("startingQB"))

    if "MATERIAL_QB" in personnel_status:
        if not home_qb or home_qb.startswith("UNRESOLVED"):
            blockers.append("material home starting-QB state unresolved")
        if away_qb.startswith("UNRESOLVED"):
            blockers.append("material away starting-QB state unresolved")
    if 0 < minutes_to_kick <= 90 and (personnel_status in {"REFRESH_REQUIRED", "UNKNOWN", "PARTIAL"} or "FINAL_RECHECK_REQUIRED" in personnel_status):
        blockers.append("personnel state still requires refresh inside final 90-minute window")
    elif (personnel_status in {"REFRESH_REQUIRED", "UNKNOWN", "PARTIAL"} or "FINAL_RECHECK_REQUIRED" in personnel_status):
        warnings.append("personnel refresh still required before final audit")

    weather = game.get("weather") or {}
    weather_status = _upper(weather.get("status"))
    if 0 < minutes_to_kick <= 90 and any(x in weather_status for x in ("REFRESH", "FINAL_RECHECK_REQUIRED", "STALE", "UNKNOWN")):
        blockers.append("material weather state is not current inside final 90-minute window")
    elif any(x in weather_status for x in ("DISAGREEMENT", "REFRESH", "FINAL_RECHECK_REQUIRED", "STALE", "UNKNOWN")):
        warnings.append(f"weather context needs review: {weather_status or 'UNKNOWN'}")

    benchmarks = game.get("benchmarks") or {}
    sp = benchmarks.get("spPlus") or {}
    sag = benchmarks.get("sagarin") or {}
    refs = benchmarks.get("refMetrics") or {}

    sp_status = _upper(sp.get("status"))
    sag_status = _upper(sag.get("status"))
    ref_status = _upper(refs.get("status"))

    if "PENDING" in sp_status or "UNAVAILABLE" in sp_status:
        warnings.append("official SP+ not currently captured; benchmark gap only, not a canonical freeze blocker")
    if sag_status and not any(x in sag_status for x in ("CURRENT", "LOCKED")):
        warnings.append(f"Sagarin freshness requires review: {sag_status}")
    if any(x in ref_status for x in ("NOT_YET_POSTED", "UNAVAILABLE", "PARTIAL", "UNKNOWN", "STALE")):
        warnings.append("RefMetrics crew assignment not fully available; record status, do not guess, and do not block canonical freeze by itself")

    audit = game.get("audit") or {}
    one_hour = audit.get("oneHourRefreshAt") or game.get("oneHourRefreshAt")
    if 0 < minutes_to_kick <= 90:
        if not one_hour:
            blockers.append("final one-hour pregame refresh has not been timestamped")
        else:
            try:
                refresh_dt = parse_dt(one_hour)
                if refresh_dt >= kickoff:
                    blockers.append("one-hour refresh timestamp is at/after kickoff")
                elif (as_of - refresh_dt).total_seconds() / 60.0 > 90:
                    blockers.append("one-hour refresh is too old for final freeze")
            except Exception:
                blockers.append("one-hour refresh timestamp is invalid")

    if not blockers:
        info.append("game is structurally eligible for freeze; lock mechanism must still enforce immutable fields")

    return {
        "gameId": game.get("gameId"),
        "awayTeam": game.get("awayTeam"),
        "homeTeam": game.get("homeTeam"),
        "kickoff": game.get("kickoff"),
        "minutesToKickoff": round(minutes_to_kick, 1),
        "readyToFreeze": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "info": info,
    }


def audit_state(doc: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    games = [audit_game(g, as_of) for g in doc.get("games", [])]
    return {
        "schemaVersion": 1,
        "league": doc.get("league"),
        "season": doc.get("season"),
        "week": doc.get("week"),
        "auditedAt": iso(as_of),
        "games": games,
        "summary": {
            "games": len(games),
            "ready": sum(1 for g in games if g["readyToFreeze"]),
            "blocked": sum(1 for g in games if not g["readyToFreeze"]),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--as-of", default=None, help="ISO timestamp; defaults to now UTC")
    ap.add_argument("--output", default=None)
    ap.add_argument("--strict", action="store_true", help="exit non-zero when any game is blocked")
    args = ap.parse_args()

    path = Path(args.path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    as_of = parse_dt(args.as_of) if args.as_of else datetime.now(timezone.utc)
    result = audit_state(doc, as_of)

    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    if args.strict and result["summary"]["blocked"]:
        sys.exit(2)


if __name__ == "__main__":
    main()

