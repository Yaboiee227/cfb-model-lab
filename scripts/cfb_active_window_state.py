#!/usr/bin/env python3
"""Build one leakage-safe active-window CFB state from day-specific pregame states.

This is an operational integration artifact only. It preserves the immutable
prospective research foundation and keeps contextual/benchmark inputs separate.
It cannot authorize canonical promotion.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cfb_research_pregame_audit import same_game
from lock_research_shadow import verify as verify_research_lock
from record_tracker import atomic_json, load_aliases


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timezone required: {value}")
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def source_observed_at(doc: dict[str, Any]) -> str | None:
    direct = doc.get("observedAt")
    if direct:
        return str(direct)
    overlays = ((doc.get("effectiveState") or {}).get("appliedOverlays") or [])
    observed = [str(x.get("observedAt")) for x in overlays if x.get("observedAt")]
    if observed:
        return max(observed, key=parse_dt)
    return None


def unique_context_match(
    scope_game: dict[str, Any],
    contexts: list[tuple[str, dict[str, Any]]],
    aliases: dict[str, str],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    hits: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for source, doc in contexts:
        for game in doc.get("games") or []:
            if same_game(scope_game, game, aliases):
                hits.append((source, doc, game))
    if len(hits) != 1:
        raise ValueError(f"expected exactly one context match for {scope_game.get('gameId')}; got {len(hits)}")
    return hits[0]


def foundation_by_digest(foundation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for game in foundation.get("games") or []:
        digest = str(game.get("projectionDigest") or "")
        if not digest:
            raise ValueError(f"foundation game missing digest: {game.get('gameId')}")
        if digest in out:
            raise ValueError(f"duplicate foundation digest: {digest}")
        out[digest] = game
    return out


def latest_market_observation(market: dict[str, Any]) -> dict[str, Any] | None:
    observations = market.get("observations") or []
    if not observations:
        return None
    def key(row: dict[str, Any]) -> datetime:
        value = row.get("observedAt")
        return parse_dt(value) if value else datetime.min.replace(tzinfo=timezone.utc)
    return max(observations, key=key)


def research_market_comparison(
    foundation_game: dict[str, Any],
    context_game: dict[str, Any],
) -> dict[str, Any] | None:
    market = context_game.get("market") or {}
    obs = latest_market_observation(market)
    if not obs:
        return None
    projected_spread_home = foundation_game.get("projectedSpreadHome")
    market_spread_home = obs.get("spreadHome")
    projected_total = foundation_game.get("projectedTotal")
    market_total = obs.get("total")
    if projected_spread_home is None or market_spread_home is None:
        spread = None
    else:
        diff = float(market_spread_home) - float(projected_spread_home)
        spread = {
            "side": context_game.get("homeTeam") if diff > 0 else context_game.get("awayTeam") if diff < 0 else "NONE",
            "foundationSpreadHome": float(projected_spread_home),
            "marketSpreadHome": float(market_spread_home),
            "differencePoints": abs(diff),
        }
    if projected_total is None or market_total is None:
        total = None
    else:
        diff_total = float(projected_total) - float(market_total)
        total = {
            "direction": "OVER" if diff_total > 0 else "UNDER" if diff_total < 0 else "NONE",
            "foundationTotal": float(projected_total),
            "marketTotal": float(market_total),
            "differencePoints": abs(diff_total),
        }
    return {
        "status": "BENCHMARK_ONLY_NOT_CANONICAL_EDGE",
        "marketObservedAt": obs.get("observedAt"),
        "book": obs.get("book"),
        "spread": spread,
        "total": total,
        "canonicalInfluence": False,
    }


def build_state(
    scope: dict[str, Any],
    foundation: dict[str, Any],
    contexts: list[tuple[str, dict[str, Any]]],
    aliases: dict[str, str],
) -> dict[str, Any]:
    verify_research_lock(foundation)
    if foundation.get("canonicalInfluence") is not False or foundation.get("canonicalPromotionAuthorized") is not False:
        raise ValueError("foundation must remain research-only")
    if scope.get("canonicalInfluence") is not False or scope.get("canonicalPromotionAuthorized") is not False:
        raise ValueError("active scope must remain non-canonical")

    f_by_digest = foundation_by_digest(foundation)
    out_games: list[dict[str, Any]] = []
    source_times: list[datetime] = []

    for source, doc in contexts:
        observed = source_observed_at(doc)
        if observed:
            source_times.append(parse_dt(observed))

    for scope_game in scope.get("games") or []:
        digest = str(scope_game.get("foundationDigest") or "")
        frozen = f_by_digest.get(digest)
        if not frozen:
            raise ValueError(f"foundation digest not found for {scope_game.get('gameId')}: {digest}")
        source, doc, context_game = unique_context_match(scope_game, contexts, aliases)
        context_observed = source_observed_at(doc)

        ref = {
            "role": foundation.get("role"),
            "canonicalInfluence": False,
            "modelId": foundation.get("modelId"),
            "projectedAwayPoints": frozen.get("projectedAwayPoints"),
            "projectedHomePoints": frozen.get("projectedHomePoints"),
            "projectedMarginHome": frozen.get("projectedMarginHome"),
            "projectedSpreadHome": frozen.get("projectedSpreadHome"),
            "projectedTotal": frozen.get("projectedTotal"),
            "homeWinProbability": frozen.get("homeWinProbability"),
            "projectedWinner": frozen.get("projectedWinner"),
            "projectionDigest": frozen.get("projectionDigest"),
            "source": scope.get("frozenFoundation"),
        }

        row: dict[str, Any] = {
            "gameId": scope_game.get("gameId"),
            "sourceGameId": scope_game.get("sourceGameId"),
            "gameDateET": scope_game.get("gameDateET"),
            "awayTeam": scope_game.get("awayTeam"),
            "homeTeam": scope_game.get("homeTeam"),
            "kickoff": scope_game.get("kickoff"),
            "contextSource": source,
            "contextObservedAt": context_observed,
            "frozenFoundationReference": ref,
        }
        for key in (
            "personnel",
            "weather",
            "travelRest",
            "market",
            "benchmarks",
            "officialContext",
            "turnoverContext",
            "audit",
        ):
            if key in context_game:
                row[key] = deepcopy(context_game[key])

        comparison = research_market_comparison(frozen, context_game)
        if comparison:
            row["researchMarketComparison"] = comparison
        out_games.append(row)

    expected = int(scope.get("includedGameCount") or len(scope.get("games") or []))
    if len(out_games) != expected:
        raise ValueError(f"active-window coverage incomplete: {len(out_games)}/{expected}")
    if len({g.get("sourceGameId") for g in out_games}) != len(out_games):
        raise ValueError("duplicate sourceGameId in active window")
    if any((g.get("frozenFoundationReference") or {}).get("canonicalInfluence") is not False for g in out_games):
        raise ValueError("foundation reference boundary violated")

    observed_at = iso(max(source_times)) if source_times else scope.get("activatedAt")
    return {
        "schemaVersion": 2,
        "league": "cfb",
        "season": scope.get("season"),
        "week": scope.get("week"),
        "role": "ACTIVE_WINDOW_INTEGRATED_EFFECTIVE_STATE",
        "status": "OPEN_EFFECTIVE_THROUGH_THURSDAY",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "observedAt": observed_at,
        "dateWindowET": scope.get("dateWindowET"),
        "activeScope": "cfb/pregame/week-08-active-through-thursday.json",
        "sourceSchedule": scope.get("sourceSchedule"),
        "frozenFoundation": scope.get("frozenFoundation"),
        "sourceRegistry": scope.get("sourceRegistry"),
        "sourceStates": [source for source, _ in contexts],
        "policy": "Pregame-only integrated working state. Frozen research projections remain immutable and non-canonical. External markets, personnel, weather and benchmarks remain context/challenger evidence unless separately validated and explicitly promoted. Unknown stays unknown.",
        "games": out_games,
        "pauseBoundary": deepcopy(scope.get("pauseBoundary")),
    }


def stable_payload(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k != "observedAt"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="cfb/pregame/week-08-active-through-thursday.json")
    ap.add_argument("--foundation", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--context", dest="contexts", action="append", required=True)
    ap.add_argument("--output", default="cfb/pregame/week-08-through-thursday-effective.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root)
    scope = json.loads(Path(args.scope).read_text(encoding="utf-8"))
    foundation = json.loads(Path(args.foundation).read_text(encoding="utf-8"))
    contexts = [(name, json.loads(Path(name).read_text(encoding="utf-8"))) for name in args.contexts]
    out = build_state(scope, foundation, contexts, load_aliases(root))

    output = Path(args.output)
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    if existing and stable_payload(out) == stable_payload(existing):
        out["observedAt"] = existing.get("observedAt", out["observedAt"])
    atomic_json(output, out)
    print(json.dumps({
        "observedAt": out["observedAt"],
        "games": len(out["games"]),
        "pauseBoundary": out.get("pauseBoundary"),
        "contexts": out["sourceStates"],
    }, indent=2))


if __name__ == "__main__":
    main()
