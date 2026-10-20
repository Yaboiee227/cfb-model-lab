#!/usr/bin/env python3
"""Grade immutable prospective research shadows without touching canonical records."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lock_research_shadow import verify
from record_tracker import atomic_json, load_aliases, match_score
from score_sources import fetch_scores_for_projection


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rmse(values: list[float]) -> float | None:
    return math.sqrt(sum(x * x for x in values) / len(values)) if values else None


def stable_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k != "gradedAt"}


def preserve_graded_at_if_unchanged(new: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if not existing:
        return new
    if existing.get("sourceLockDigest") != new.get("sourceLockDigest"):
        raise ValueError("research result source lock digest changed")
    if stable_payload(existing) == stable_payload(new):
        new["gradedAt"] = existing.get("gradedAt", new["gradedAt"])
    return new


def grade(lock: dict[str, Any], scores: list[dict[str, Any]], aliases: dict[str, str]) -> dict[str, Any]:
    verify(lock)
    rows: list[dict[str, Any]] = []
    margin_errors: list[float] = []
    total_errors: list[float] = []
    brier_terms: list[float] = []
    su_wins = 0
    su_losses = 0

    for game in lock.get("games", []):
        score = match_score(game, scores, aliases)
        base = {
            "gameId": game["gameId"],
            "awayTeam": game["awayTeam"],
            "homeTeam": game["homeTeam"],
            "kickoff": game["kickoff"],
            "projectionDigest": game["projectionDigest"],
            "projection": {
                "awayPoints": game["projectedAwayPoints"],
                "homePoints": game["projectedHomePoints"],
                "marginHome": game["projectedMarginHome"],
                "spreadHome": game["projectedSpreadHome"],
                "total": game["projectedTotal"],
                "homeWinProbability": game["homeWinProbability"],
                "winner": game["projectedWinner"],
            },
        }
        if score is None:
            rows.append({**base, "status": "REVIEW", "reviewReason": "No score source match; no guess made"})
            continue

        status = str(score.get("status", "")).upper()
        if status in {"CANCELLED", "CANCELED", "POSTPONED", "VOID"}:
            rows.append({**base, "status": "VOID", "final": None})
            continue
        if status != "FINAL":
            rows.append({**base, "status": "PENDING", "final": None})
            continue

        away_score = int(score["awayScore"])
        home_score = int(score["homeScore"])
        actual_margin = home_score - away_score
        actual_total = home_score + away_score
        margin_error = float(game["projectedMarginHome"]) - actual_margin
        total_error = float(game["projectedTotal"]) - actual_total
        margin_errors.append(margin_error)
        total_errors.append(total_error)

        if home_score == away_score:
            su_result = "TIE"
        else:
            actual_winner = game["homeTeam"] if home_score > away_score else game["awayTeam"]
            su_result = "WIN" if game["projectedWinner"] == actual_winner else "LOSS"
            if su_result == "WIN":
                su_wins += 1
            else:
                su_losses += 1
            actual_home = 1.0 if home_score > away_score else 0.0
            p_home = float(game["homeWinProbability"]) / 100.0
            brier_terms.append((p_home - actual_home) ** 2)

        rows.append(
            {
                **base,
                "status": "FINAL",
                "final": {
                    "awayScore": away_score,
                    "homeScore": home_score,
                    "marginHome": actual_margin,
                    "total": actual_total,
                    "overtime": bool(score.get("overtime", False)),
                    "source": score.get("source", "ESPN"),
                },
                "errors": {
                    "margin": margin_error,
                    "absoluteMargin": abs(margin_error),
                    "total": total_error,
                    "absoluteTotal": abs(total_error),
                },
                "straightUp": {"result": su_result},
            }
        )

    final_count = sum(row["status"] == "FINAL" for row in rows)
    pending_count = sum(row["status"] == "PENDING" for row in rows)
    review_count = sum(row["status"] == "REVIEW" for row in rows)
    void_count = sum(row["status"] == "VOID" for row in rows)
    su_graded = su_wins + su_losses

    return {
        "schemaVersion": 1,
        "league": lock.get("league"),
        "season": lock.get("season"),
        "week": lock.get("week"),
        "role": "PROSPECTIVE_RESEARCH_SHADOW_RESULTS",
        "canonicalInfluence": False,
        "canonicalRecordMerged": False,
        "modelId": lock.get("modelId"),
        "sourceLockDigest": lock.get("lockDigest"),
        "sourceLockedAt": lock.get("lockedAt"),
        "gradedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "COMPLETE" if final_count + void_count == len(rows) and review_count == 0 else "IN_PROGRESS",
        "counts": {
            "games": len(rows),
            "final": final_count,
            "pending": pending_count,
            "review": review_count,
            "void": void_count,
        },
        "metrics": {
            "margin": {
                "games": len(margin_errors),
                "mae": mean([abs(x) for x in margin_errors]),
                "rmse": rmse(margin_errors),
                "bias": mean(margin_errors),
            },
            "total": {
                "games": len(total_errors),
                "mae": mean([abs(x) for x in total_errors]),
                "rmse": rmse(total_errors),
                "bias": mean(total_errors),
            },
            "straightUp": {
                "wins": su_wins,
                "losses": su_losses,
                "graded": su_graded,
                "accuracyPct": (100.0 * su_wins / su_graded) if su_graded else None,
            },
            "winProbability": {
                "games": len(brier_terms),
                "brierScore": mean(brier_terms),
            },
        },
        "games": rows,
        "policy": "Research-only prospective performance. Never merge these results into the established canonical record or use postgame outcomes to rewrite the frozen projections.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("lock")
    ap.add_argument("--scores")
    ap.add_argument("--output", required=True)
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root)
    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    if args.scores:
        scores = json.loads(Path(args.scores).read_text(encoding="utf-8")).get("games", [])
    else:
        scores = fetch_scores_for_projection(str(lock.get("league")), lock)
    out = grade(lock, scores, load_aliases(root))
    output_path = Path(args.output)
    existing = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else None
    out = preserve_graded_at_if_unchanged(out, existing)
    atomic_json(output_path, out)
    print(
        json.dumps(
            {
                "modelId": out["modelId"],
                "status": out["status"],
                "counts": out["counts"],
                "metrics": out["metrics"],
                "canonicalRecordMerged": out["canonicalRecordMerged"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
