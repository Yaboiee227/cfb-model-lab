#!/usr/bin/env python3
"""Compare a frozen CFB research projection with an official benchmark snapshot.

Descriptive research only. This module never changes model projections, creates
recommendations, or writes to the canonical performance ledger.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lock_research_shadow import verify as verify_research_lock
from record_tracker import canonical_team, load_aliases


def sign_label(margin_home: float, home: str, away: str) -> str:
    if margin_home > 0:
        return home
    if margin_home < 0:
        return away
    return "PICK"


def disagreement_bucket(abs_points: float) -> str:
    if abs_points < 2.0:
        return "LT_2"
    if abs_points < 5.0:
        return "2_TO_LT_5"
    if abs_points < 10.0:
        return "5_TO_LT_10"
    return "GE_10"


def _same_teams(a: dict[str, Any], b: dict[str, Any], aliases: dict[str, str]) -> bool:
    return (
        canonical_team(a.get("awayTeam"), aliases) == canonical_team(b.get("awayTeam"), aliases)
        and canonical_team(a.get("homeTeam"), aliases) == canonical_team(b.get("homeTeam"), aliases)
    )


def match_benchmark(
    game: dict[str, Any],
    benchmark_games: list[dict[str, Any]],
    aliases: dict[str, str],
) -> dict[str, Any] | None:
    source_id = str(game.get("sourceGameId") or "")
    if source_id:
        hits = [b for b in benchmark_games if str(b.get("sourceGameId") or "") == source_id]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError(f"duplicate benchmark sourceGameId: {source_id}")

    game_id = str(game.get("gameId") or "")
    if game_id:
        hits = [b for b in benchmark_games if str(b.get("gameId") or "") == game_id]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError(f"duplicate benchmark gameId: {game_id}")

    hits = [
        b
        for b in benchmark_games
        if str(b.get("kickoff")) == str(game.get("kickoff")) and _same_teams(game, b, aliases)
    ]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise ValueError(f"ambiguous benchmark team/kickoff match for {game_id}")
    return None


def build_comparison(
    lock: dict[str, Any],
    benchmark: dict[str, Any],
    aliases: dict[str, str],
) -> dict[str, Any]:
    verify_research_lock(lock)
    if lock.get("canonicalInfluence") is not False or lock.get("canonicalPromotionAuthorized") is not False:
        raise ValueError("foundation lock must remain non-canonical")
    if benchmark.get("canonicalInfluence") is not False:
        raise ValueError("benchmark snapshot must have canonicalInfluence=false")
    source = benchmark.get("source") or (benchmark.get("sources") or {}).get("sagarin") or {}
    if source.get("sourceId") != "sagarin-cfb":
        raise ValueError("comparison requires approved Sagarin CFB snapshot")

    benchmark_games = benchmark.get("games") or []
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []
    abs_values: list[float] = []
    signed_values: list[float] = []
    winner_agreements = 0
    winner_graded = 0
    bucket_counts = {"LT_2": 0, "2_TO_LT_5": 0, "5_TO_LT_10": 0, "GE_10": 0}

    for game in lock.get("games", []):
        b = match_benchmark(game, benchmark_games, aliases)
        if b is None:
            unresolved.append(game["gameId"])
            rows.append(
                {
                    "gameId": game["gameId"],
                    "sourceGameId": game.get("sourceGameId"),
                    "awayTeam": game["awayTeam"],
                    "homeTeam": game["homeTeam"],
                    "kickoff": game["kickoff"],
                    "status": "REVIEW",
                    "reviewReason": "No benchmark match; no guess made",
                }
            )
            continue
        sag = b.get("sagarin") or {}
        if str(sag.get("status", "")).upper() != "CURRENT" or sag.get("impliedHomeMargin") is None:
            unresolved.append(game["gameId"])
            rows.append(
                {
                    "gameId": game["gameId"],
                    "sourceGameId": game.get("sourceGameId"),
                    "awayTeam": game["awayTeam"],
                    "homeTeam": game["homeTeam"],
                    "kickoff": game["kickoff"],
                    "status": "REVIEW",
                    "reviewReason": f"Sagarin observation status is {sag.get('status')}",
                }
            )
            continue

        cb_margin = float(game["projectedMarginHome"])
        sag_margin = float(sag["impliedHomeMargin"])
        delta = cb_margin - sag_margin
        abs_delta = abs(delta)
        bucket = disagreement_bucket(abs_delta)
        cb_winner = sign_label(cb_margin, game["homeTeam"], game["awayTeam"])
        sag_winner = sign_label(sag_margin, game["homeTeam"], game["awayTeam"])
        agreement = cb_winner == sag_winner
        winner_graded += 1
        winner_agreements += int(agreement)
        bucket_counts[bucket] += 1
        abs_values.append(abs_delta)
        signed_values.append(delta)

        rows.append(
            {
                "gameId": game["gameId"],
                "sourceGameId": game.get("sourceGameId") or b.get("sourceGameId"),
                "awayTeam": game["awayTeam"],
                "homeTeam": game["homeTeam"],
                "kickoff": game["kickoff"],
                "status": "COMPARED",
                "foundation": {
                    "projectedHomeMargin": cb_margin,
                    "projectedSpreadHome": float(game["projectedSpreadHome"]),
                    "projectedWinner": game["projectedWinner"],
                    "homeWinProbability": float(game["homeWinProbability"]),
                    "projectionDigest": game["projectionDigest"],
                },
                "sagarin": {
                    "impliedHomeMargin": sag_margin,
                    "impliedSpreadHome": float(sag["impliedSpreadHome"]),
                    "predictorFavorite": sag.get("predictorFavorite"),
                    "observedAt": sag.get("observedAt"),
                    "ratingsThrough": sag.get("ratingsThrough"),
                },
                "comparison": {
                    "cbMinusSagarinHomeMargin": delta,
                    "absoluteDisagreement": abs_delta,
                    "disagreementBucket": bucket,
                    "directionalWinnerAgreement": agreement,
                },
            }
        )

    compared = len(abs_values)
    total = len(lock.get("games", []))
    rows_sorted = sorted(
        (r for r in rows if r.get("status") == "COMPARED"),
        key=lambda r: r["comparison"]["absoluteDisagreement"],
        reverse=True,
    )
    return {
        "schemaVersion": 1,
        "league": lock.get("league"),
        "season": lock.get("season"),
        "week": lock.get("week"),
        "role": "FROZEN_MODEL_VS_OFFICIAL_BENCHMARK_COMPARISON",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "foundation": {
            "modelId": lock.get("modelId"),
            "lockDigest": lock.get("lockDigest"),
            "lockedAt": lock.get("lockedAt"),
            "sourceAsOf": lock.get("sourceAsOf"),
        },
        "benchmark": {
            "sourceId": source.get("sourceId"),
            "publisher": source.get("publisher"),
            "officialUrl": source.get("officialUrl"),
            "observedAt": source.get("observedAt") or benchmark.get("observedAt"),
            "ratingsThrough": source.get("ratingsThrough"),
            "sourceWeek": source.get("sourceWeek"),
        },
        "coverage": {
            "foundationGames": total,
            "comparedGames": compared,
            "ratio": compared / total if total else 0.0,
            "reviewGames": unresolved,
        },
        "aggregate": {
            "meanSignedCbMinusSagarinHomeMargin": statistics.fmean(signed_values) if signed_values else None,
            "meanAbsoluteDisagreement": statistics.fmean(abs_values) if abs_values else None,
            "medianAbsoluteDisagreement": statistics.median(abs_values) if abs_values else None,
            "maxAbsoluteDisagreement": max(abs_values) if abs_values else None,
            "directionalWinnerAgreement": {
                "agree": winner_agreements,
                "graded": winner_graded,
                "pct": (100.0 * winner_agreements / winner_graded) if winner_graded else None,
            },
            "disagreementBuckets": bucket_counts,
        },
        "largestDisagreements": [
            {
                "gameId": r["gameId"],
                "awayTeam": r["awayTeam"],
                "homeTeam": r["homeTeam"],
                "cbHomeMargin": r["foundation"]["projectedHomeMargin"],
                "sagarinHomeMargin": r["sagarin"]["impliedHomeMargin"],
                "absoluteDisagreement": r["comparison"]["absoluteDisagreement"],
                "directionalWinnerAgreement": r["comparison"]["directionalWinnerAgreement"],
            }
            for r in rows_sorted[:10]
        ],
        "games": rows,
        "policy": "Descriptive benchmark comparison only. Disagreement is a research difference, not a recommendation or manual adjustment. Sagarin cannot alter the frozen foundation or canonical projection without separate leakage-safe promotion evidence and explicit review.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundation-lock", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--benchmark", default="cfb/benchmarks/week-08-sagarin-full.json")
    ap.add_argument("--output", default="cfb/validation/week-08-foundation-vs-sagarin.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    lock = json.loads(Path(args.foundation_lock).read_text(encoding="utf-8"))
    benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    out = build_comparison(lock, benchmark, load_aliases(root))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": out["coverage"], "aggregate": out["aggregate"], "largestDisagreements": out["largestDisagreements"]}, indent=2))


if __name__ == "__main__":
    main()
