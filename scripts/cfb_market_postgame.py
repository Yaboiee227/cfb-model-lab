#!/usr/bin/env python3
"""Evaluate frozen CFB research projections against locked pregame book markets."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cfb_market_research_lock import verify_existing as verify_market_lock
from lock_research_shadow import verify as verify_research_lock
from record_tracker import atomic_json, load_aliases, match_score
from score_sources import fetch_scores_for_projection

EPS = 1e-9


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rmse(values: list[float]) -> float | None:
    return math.sqrt(sum(x * x for x in values) / len(values)) if values else None


def metric_block(errors: list[float]) -> dict[str, Any]:
    return {
        "games": len(errors),
        "mae": mean([abs(x) for x in errors]),
        "rmse": rmse(errors),
        "bias": mean(errors),
    }


def grade_direction(position_diff: float, result_diff: float) -> str:
    if abs(position_diff) <= EPS:
        return "NO_POSITION"
    if abs(result_diff) <= EPS:
        return "PUSH"
    same_direction = (position_diff > 0 and result_diff > 0) or (position_diff < 0 and result_diff < 0)
    return "WIN" if same_direction else "LOSS"


def position_label(diff: float, positive: str, negative: str) -> str:
    if diff > EPS:
        return positive
    if diff < -EPS:
        return negative
    return "NO_POSITION"


def closer_label(model_abs: float, benchmark_abs: float) -> str:
    if abs(model_abs - benchmark_abs) <= EPS:
        return "TIE"
    return "CB" if model_abs < benchmark_abs else "MARKET"


def verify_inputs(foundation: dict[str, Any], market_lock: dict[str, Any]) -> None:
    verify_research_lock(foundation)
    verify_market_lock(market_lock, foundation)
    if market_lock.get("foundationLockDigest") != foundation.get("lockDigest"):
        raise ValueError("market lock does not belong to foundation lock")


def _record() -> dict[str, int]:
    return {"wins": 0, "losses": 0, "pushes": 0, "noPosition": 0}


def _apply_record(record: dict[str, int], result: str) -> None:
    if result == "WIN":
        record["wins"] += 1
    elif result == "LOSS":
        record["losses"] += 1
    elif result == "PUSH":
        record["pushes"] += 1
    elif result == "NO_POSITION":
        record["noPosition"] += 1


def grade(
    foundation: dict[str, Any],
    market_lock: dict[str, Any],
    scores: list[dict[str, Any]],
    aliases: dict[str, str],
) -> dict[str, Any]:
    verify_inputs(foundation, market_lock)
    foundation_by_digest = {g["projectionDigest"]: g for g in foundation.get("games", [])}
    book_acc: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    def acc(book: str) -> dict[str, Any]:
        if book not in book_acc:
            book_acc[book] = {
                "modelMarginErrors": [],
                "marketMarginErrors": [],
                "modelTotalErrors": [],
                "marketTotalErrors": [],
                "ats": _record(),
                "totals": _record(),
                "marginCloser": {"CB": 0, "MARKET": 0, "TIE": 0},
                "totalCloser": {"CB": 0, "MARKET": 0, "TIE": 0},
                "suCorrect": 0,
                "suWrong": 0,
            }
        return book_acc[book]

    for market_game in market_lock.get("games", []):
        locked_projection = foundation_by_digest.get(market_game.get("projectionDigest"))
        if not locked_projection:
            raise ValueError(f"market row projection digest missing from foundation: {market_game.get('gameId')}")
        books = market_game.get("books") or {}
        base = {
            "gameId": market_game["gameId"],
            "sourceGameId": market_game.get("sourceGameId"),
            "awayTeam": market_game["awayTeam"],
            "homeTeam": market_game["homeTeam"],
            "kickoff": market_game["kickoff"],
            "projectionDigest": market_game["projectionDigest"],
        }
        if not books:
            rows.append({**base, "status": "NO_LOCKED_MARKET", "books": {}})
            continue
        score = match_score(market_game, scores, aliases)
        if score is None:
            rows.append({**base, "status": "REVIEW", "reviewReason": "No score match; no guess made", "books": {}})
            continue
        score_status = str(score.get("status", "")).upper()
        if score_status in {"CANCELLED", "CANCELED", "POSTPONED", "VOID"}:
            rows.append({**base, "status": "VOID", "books": {}})
            continue
        if score_status != "FINAL":
            rows.append({**base, "status": "PENDING", "books": {}})
            continue

        away_score = int(score["awayScore"])
        home_score = int(score["homeScore"])
        actual_margin = float(home_score - away_score)
        actual_total = float(home_score + away_score)
        model_margin = float(locked_projection["projectedMarginHome"])
        model_total = float(locked_projection["projectedTotal"])
        actual_sign = 1 if actual_margin > 0 else -1 if actual_margin < 0 else 0
        model_sign = 1 if model_margin > 0 else -1 if model_margin < 0 else 0
        book_rows: dict[str, Any] = {}

        for book_name, observation in books.items():
            market_spread_home = float(observation["marketSpreadHome"])
            market_margin = -market_spread_home
            market_total = float(observation["marketTotal"])
            model_margin_error = model_margin - actual_margin
            market_margin_error = market_margin - actual_margin
            model_total_error = model_total - actual_total
            market_total_error = market_total - actual_total

            spread_position_diff = model_margin - market_margin
            actual_spread_result_diff = actual_margin - market_margin
            ats_result = grade_direction(spread_position_diff, actual_spread_result_diff)
            ats_position = position_label(spread_position_diff, "HOME", "AWAY")

            total_position_diff = model_total - market_total
            actual_total_result_diff = actual_total - market_total
            total_result = grade_direction(total_position_diff, actual_total_result_diff)
            total_position = position_label(total_position_diff, "OVER", "UNDER")

            margin_closer = closer_label(abs(model_margin_error), abs(market_margin_error))
            total_closer = closer_label(abs(model_total_error), abs(market_total_error))
            a = acc(book_name)
            a["modelMarginErrors"].append(model_margin_error)
            a["marketMarginErrors"].append(market_margin_error)
            a["modelTotalErrors"].append(model_total_error)
            a["marketTotalErrors"].append(market_total_error)
            _apply_record(a["ats"], ats_result)
            _apply_record(a["totals"], total_result)
            a["marginCloser"][margin_closer] += 1
            a["totalCloser"][total_closer] += 1
            if actual_sign != 0:
                if model_sign == actual_sign:
                    a["suCorrect"] += 1
                else:
                    a["suWrong"] += 1

            book_rows[book_name] = {
                "marketObservedAt": observation["marketObservedAt"],
                "marketSpreadHome": market_spread_home,
                "marketImpliedHomeMargin": market_margin,
                "marketTotal": market_total,
                "marketMoneylineHome": observation.get("marketMoneylineHome"),
                "marketMoneylineAway": observation.get("marketMoneylineAway"),
                "modelVsMarket": {
                    "homeMarginDifference": spread_position_diff,
                    "totalDifference": total_position_diff,
                    "spreadPosition": ats_position,
                    "spreadResult": ats_result,
                    "totalPosition": total_position,
                    "totalResult": total_result,
                },
                "accuracy": {
                    "cbMarginError": model_margin_error,
                    "marketMarginError": market_margin_error,
                    "closerMarginForecast": margin_closer,
                    "cbTotalError": model_total_error,
                    "marketTotalError": market_total_error,
                    "closerTotalForecast": total_closer,
                },
            }

        rows.append(
            {
                **base,
                "status": "FINAL",
                "final": {
                    "awayScore": away_score,
                    "homeScore": home_score,
                    "homeMargin": actual_margin,
                    "total": actual_total,
                    "overtime": bool(score.get("overtime", False)),
                    "source": score.get("source", "ESPN"),
                },
                "foundation": {
                    "projectedHomeMargin": model_margin,
                    "projectedTotal": model_total,
                    "projectedWinner": locked_projection["projectedWinner"],
                },
                "books": book_rows,
            }
        )

    book_summary: dict[str, Any] = {}
    for book in market_lock.get("booksTracked", []):
        a = book_acc.get(book, acc(book))
        su_graded = a["suCorrect"] + a["suWrong"]
        book_summary[book] = {
            "games": len(a["modelMarginErrors"]),
            "cbMargin": metric_block(a["modelMarginErrors"]),
            "marketMargin": metric_block(a["marketMarginErrors"]),
            "cbMinusMarketMarginMae": (
                metric_block(a["modelMarginErrors"])["mae"] - metric_block(a["marketMarginErrors"])["mae"]
                if a["modelMarginErrors"] else None
            ),
            "cbTotal": metric_block(a["modelTotalErrors"]),
            "marketTotal": metric_block(a["marketTotalErrors"]),
            "cbMinusMarketTotalMae": (
                metric_block(a["modelTotalErrors"])["mae"] - metric_block(a["marketTotalErrors"])["mae"]
                if a["modelTotalErrors"] else None
            ),
            "spreadPositionRecord": a["ats"],
            "totalPositionRecord": a["totals"],
            "closerMarginForecast": a["marginCloser"],
            "closerTotalForecast": a["totalCloser"],
            "straightUp": {
                "correct": a["suCorrect"],
                "wrong": a["suWrong"],
                "graded": su_graded,
                "accuracyPct": (100.0 * a["suCorrect"] / su_graded) if su_graded else None,
            },
        }

    final_count = sum(r["status"] == "FINAL" for r in rows)
    pending_count = sum(r["status"] == "PENDING" for r in rows)
    review_count = sum(r["status"] == "REVIEW" for r in rows)
    void_count = sum(r["status"] == "VOID" for r in rows)
    no_market_count = sum(r["status"] == "NO_LOCKED_MARKET" for r in rows)
    return {
        "schemaVersion": 1,
        "league": foundation.get("league"),
        "season": foundation.get("season"),
        "week": foundation.get("week"),
        "role": "POSTGAME_FROZEN_MODEL_VS_LOCKED_MARKET_RESEARCH_EVALUATION",
        "canonicalInfluence": False,
        "canonicalRecordMerged": False,
        "foundationModelId": foundation.get("modelId"),
        "foundationLockDigest": foundation.get("lockDigest"),
        "marketLockUpdatedAt": market_lock.get("updatedAt"),
        "gradedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "COMPLETE" if final_count + void_count + no_market_count == len(rows) and review_count == 0 else "IN_PROGRESS",
        "counts": {
            "games": len(rows),
            "final": final_count,
            "pending": pending_count,
            "review": review_count,
            "void": void_count,
            "noLockedMarket": no_market_count,
        },
        "books": book_summary,
        "games": rows,
        "policy": "Research-only evaluation using immutable pregame book observations. Market differences describe positions relative to each locked book and are not recommendations. Results remain separate from the established canonical performance ledger.",
    }


def stable_payload(value: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in value.items() if k != "gradedAt"}


def preserve_graded_at_if_unchanged(new: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if existing and stable_payload(new) == stable_payload(existing):
        new["gradedAt"] = existing.get("gradedAt", new["gradedAt"])
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundation-lock", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--market-lock", default="cfb/research-market-locks/week-08-foundation-market.json")
    ap.add_argument("--scores")
    ap.add_argument("--output", default="cfb/validation/week-08-foundation-vs-markets-results.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    foundation = json.loads(Path(args.foundation_lock).read_text(encoding="utf-8"))
    market_lock = json.loads(Path(args.market_lock).read_text(encoding="utf-8"))
    if args.scores:
        scores = json.loads(Path(args.scores).read_text(encoding="utf-8")).get("games", [])
    else:
        scores = fetch_scores_for_projection("cfb", market_lock)
    out = grade(foundation, market_lock, scores, load_aliases(root))
    output = Path(args.output)
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    out = preserve_graded_at_if_unchanged(out, existing)
    atomic_json(output, out)
    print(json.dumps({"status": out["status"], "counts": out["counts"], "books": out["books"]}, indent=2))


if __name__ == "__main__":
    main()
