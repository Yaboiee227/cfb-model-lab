#!/usr/bin/env python3
"""Grade frozen CB-vs-Sagarin pregame disagreement against final scores.

This is research evaluation only. It reads the pregame comparison artifact and
never refreshes either projection after kickoff.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lock_research_shadow import verify as verify_research_lock
from record_tracker import atomic_json, load_aliases, match_score
from score_sources import fetch_scores_for_projection
from cfb_grading_scope import scoped_digests, score_request, row_digest


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rmse(values: list[float]) -> float | None:
    return math.sqrt(sum(x * x for x in values) / len(values)) if values else None


def sign(margin: float) -> int:
    return 1 if margin > 0 else -1 if margin < 0 else 0


def verify_pregame_comparison(lock: dict[str, Any], comparison: dict[str, Any]) -> None:
    verify_research_lock(lock)
    if comparison.get("role") != "FROZEN_MODEL_VS_OFFICIAL_BENCHMARK_COMPARISON":
        raise ValueError("unexpected comparison role")
    if comparison.get("canonicalInfluence") is not False or comparison.get("canonicalPromotionAuthorized") is not False:
        raise ValueError("comparison must remain non-canonical")
    if comparison.get("foundation", {}).get("lockDigest") != lock.get("lockDigest"):
        raise ValueError("comparison does not belong to supplied foundation lock")

    lock_by_digest = {g["projectionDigest"]: g for g in lock.get("games", [])}
    for row in comparison.get("games", []):
        if row.get("status") != "COMPARED":
            continue
        digest = (row.get("foundation") or {}).get("projectionDigest")
        locked = lock_by_digest.get(digest)
        if not locked:
            raise ValueError(f"comparison projection digest not present in lock: {row.get('gameId')}")
        if abs(float(row["foundation"]["projectedHomeMargin"]) - float(locked["projectedMarginHome"])) > 1e-9:
            raise ValueError(f"comparison CB margin changed after lock: {row.get('gameId')}")
        observed = (row.get("sagarin") or {}).get("observedAt")
        if not observed:
            raise ValueError(f"comparison missing Sagarin observedAt: {row.get('gameId')}")
        obs_dt = datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
        kickoff_dt = datetime.fromisoformat(str(row["kickoff"]).replace("Z", "+00:00"))
        if obs_dt >= kickoff_dt:
            raise ValueError(f"Sagarin comparison observation is not pregame: {row.get('gameId')}")


def _metric_block(errors: list[float]) -> dict[str, Any]:
    return {
        "games": len(errors),
        "mae": mean([abs(x) for x in errors]),
        "rmse": rmse(errors),
        "bias": mean(errors),
    }


def _su_block(correct: int, wrong: int) -> dict[str, Any]:
    graded = correct + wrong
    return {
        "correct": correct,
        "wrong": wrong,
        "graded": graded,
        "accuracyPct": (100.0 * correct / graded) if graded else None,
    }


def grade(
    lock: dict[str, Any],
    comparison: dict[str, Any],
    scores: list[dict[str, Any]],
    aliases: dict[str, str],
    scope=None,
) -> dict[str, Any]:
    verify_pregame_comparison(lock, comparison)
    rows: list[dict[str, Any]] = []
    cb_errors: list[float] = []
    sag_errors: list[float] = []
    cb_su_correct = cb_su_wrong = 0
    sag_su_correct = sag_su_wrong = 0
    closer = {"CB": 0, "SAGARIN": 0, "TIE": 0}
    buckets: dict[str, dict[str, Any]] = {}
    directional_disagreement = {
        "games": 0,
        "cbCloser": 0,
        "sagarinCloser": 0,
        "ties": 0,
        "cbSuCorrect": 0,
        "sagarinSuCorrect": 0,
    }

    allowed = scoped_digests(scope, lock)
    for row in comparison.get("games", []):
        if allowed is not None and row_digest(row) not in allowed:
            continue
        if row.get("status") != "COMPARED":
            rows.append({**row, "postgameStatus": "REVIEW", "postgameReviewReason": "Pregame comparison was not complete"})
            continue
        score = match_score(row, scores, aliases)
        if score is None:
            rows.append({**row, "postgameStatus": "REVIEW", "postgameReviewReason": "No final-score match; no guess made"})
            continue
        status = str(score.get("status", "")).upper()
        if status in {"CANCELLED", "CANCELED", "POSTPONED", "VOID"}:
            rows.append({**row, "postgameStatus": "VOID"})
            continue
        if status != "FINAL":
            rows.append({**row, "postgameStatus": "PENDING"})
            continue

        away_score = int(score["awayScore"])
        home_score = int(score["homeScore"])
        actual_margin = float(home_score - away_score)
        cb_margin = float(row["foundation"]["projectedHomeMargin"])
        sag_margin = float(row["sagarin"]["impliedHomeMargin"])
        cb_error = cb_margin - actual_margin
        sag_error = sag_margin - actual_margin
        cb_abs = abs(cb_error)
        sag_abs = abs(sag_error)
        if abs(cb_abs - sag_abs) <= 1e-9:
            who = "TIE"
        elif cb_abs < sag_abs:
            who = "CB"
        else:
            who = "SAGARIN"
        closer[who] += 1
        cb_errors.append(cb_error)
        sag_errors.append(sag_error)

        actual_sign = sign(actual_margin)
        cb_sign = sign(cb_margin)
        sag_sign = sign(sag_margin)
        if actual_sign != 0:
            if cb_sign == actual_sign:
                cb_su_correct += 1
            else:
                cb_su_wrong += 1
            if sag_sign == actual_sign:
                sag_su_correct += 1
            else:
                sag_su_wrong += 1

        bucket = row["comparison"]["disagreementBucket"]
        b = buckets.setdefault(
            bucket,
            {
                "games": 0,
                "cbErrors": [],
                "sagarinErrors": [],
                "cbCloser": 0,
                "sagarinCloser": 0,
                "ties": 0,
            },
        )
        b["games"] += 1
        b["cbErrors"].append(cb_error)
        b["sagarinErrors"].append(sag_error)
        if who == "CB":
            b["cbCloser"] += 1
        elif who == "SAGARIN":
            b["sagarinCloser"] += 1
        else:
            b["ties"] += 1

        if row["comparison"]["directionalWinnerAgreement"] is False:
            directional_disagreement["games"] += 1
            if who == "CB":
                directional_disagreement["cbCloser"] += 1
            elif who == "SAGARIN":
                directional_disagreement["sagarinCloser"] += 1
            else:
                directional_disagreement["ties"] += 1
            if actual_sign != 0:
                directional_disagreement["cbSuCorrect"] += int(cb_sign == actual_sign)
                directional_disagreement["sagarinSuCorrect"] += int(sag_sign == actual_sign)

        rows.append(
            {
                **row,
                "postgameStatus": "FINAL",
                "final": {
                    "awayScore": away_score,
                    "homeScore": home_score,
                    "homeMargin": actual_margin,
                    "overtime": bool(score.get("overtime", False)),
                    "source": score.get("source", "ESPN"),
                },
                "postgameComparison": {
                    "cbMarginError": cb_error,
                    "cbAbsoluteMarginError": cb_abs,
                    "sagarinMarginError": sag_error,
                    "sagarinAbsoluteMarginError": sag_abs,
                    "closerToFinalMargin": who,
                    "cbStraightUpCorrect": None if actual_sign == 0 else cb_sign == actual_sign,
                    "sagarinStraightUpCorrect": None if actual_sign == 0 else sag_sign == actual_sign,
                },
            }
        )

    bucket_summary: dict[str, Any] = {}
    for name in ("LT_2", "2_TO_LT_5", "5_TO_LT_10", "GE_10"):
        b = buckets.get(name, {"games": 0, "cbErrors": [], "sagarinErrors": [], "cbCloser": 0, "sagarinCloser": 0, "ties": 0})
        bucket_summary[name] = {
            "games": b["games"],
            "cbMargin": _metric_block(b["cbErrors"]),
            "sagarinMargin": _metric_block(b["sagarinErrors"]),
            "closer": {"CB": b["cbCloser"], "SAGARIN": b["sagarinCloser"], "TIE": b["ties"]},
        }

    final_count = sum(r.get("postgameStatus") == "FINAL" for r in rows)
    pending_count = sum(r.get("postgameStatus") == "PENDING" for r in rows)
    review_count = sum(r.get("postgameStatus") == "REVIEW" for r in rows)
    void_count = sum(r.get("postgameStatus") == "VOID" for r in rows)
    return {
        "schemaVersion": 1,
        "league": comparison.get("league"),
        "season": comparison.get("season"),
        "week": comparison.get("week"),
        "role": "POSTGAME_FROZEN_MODEL_VS_OFFICIAL_BENCHMARK_EVALUATION",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "canonicalRecordMerged": False,
        "gradedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "foundation": comparison["foundation"],
        "benchmark": comparison["benchmark"],
        "pregameComparisonCreatedAt": comparison.get("createdAt"),
        "status": "COMPLETE" if final_count + void_count == len(rows) and review_count == 0 else "IN_PROGRESS",
        "counts": {"games": len(rows), "final": final_count, "pending": pending_count, "review": review_count, "void": void_count},
        "aggregate": {
            "cbMargin": _metric_block(cb_errors),
            "sagarinMargin": _metric_block(sag_errors),
            "closerToFinalMargin": closer,
            "cbStraightUp": _su_block(cb_su_correct, cb_su_wrong),
            "sagarinStraightUp": _su_block(sag_su_correct, sag_su_wrong),
            "directionalDisagreementGames": directional_disagreement,
            "byPregameDisagreementBucket": bucket_summary,
        },
        "games": rows,
        "policy": "Postgame research evaluation of pregame-frozen values only. Final scores may grade the frozen CB and Sagarin margins but may never rewrite either pregame value or enter the established canonical record automatically.",
    }


def stable_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k != "gradedAt"}


def preserve_graded_at_if_unchanged(new: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    if existing and stable_payload(existing) == stable_payload(new):
        new["gradedAt"] = existing.get("gradedAt", new["gradedAt"])
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foundation-lock", default="cfb/research-locks/week-08-foundation-full.json")
    ap.add_argument("--comparison", default="cfb/validation/week-08-foundation-vs-sagarin.json")
    ap.add_argument("--scores")
    ap.add_argument("--scope", help="Active processing scope; excludes paused games from score requests and grades")
    ap.add_argument("--output", default="cfb/validation/week-08-foundation-vs-sagarin-results.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root)
    lock = json.loads(Path(args.foundation_lock).read_text(encoding="utf-8"))
    comparison = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    scope = json.loads(Path(args.scope).read_text()) if args.scope else None
    allowed = scoped_digests(scope, lock)
    if args.scores:
        scores = json.loads(Path(args.scores).read_text(encoding="utf-8")).get("games", [])
    else:
        scores = fetch_scores_for_projection("cfb", score_request(comparison, allowed))
    out = grade(lock, comparison, scores, load_aliases(root), scope=scope)
    if scope is not None:
        out["activeScope"] = args.scope
        out["pauseBeforeGameDateET"] = scope["pauseBoundary"]["beforeGameDateET"]
    output = Path(args.output)
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    out = preserve_graded_at_if_unchanged(out, existing)
    atomic_json(output, out)
    print(json.dumps({"status": out["status"], "counts": out["counts"], "aggregate": out["aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
