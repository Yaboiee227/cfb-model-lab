#!/usr/bin/env python3
"""Grade the immutable NFL Week-6 prospective snapshot without modifying it.

The grader may be run repeatedly as games complete. Each run creates a new
postgame grading artifact. The original pre-lock snapshot remains untouched.
Schedule reference prices are graded only as frozen benchmark references, not
as verified executable sportsbook prices or ROI observations.
"""
from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT = Path("nfl_data/prospective/week6_prelock_20261017T225656Z.json")
OUT_DIR = Path("nfl_data/prospective/grades")
SCHEDULE_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
SPREAD_ABS_ERROR_BANDS = {"68pct": 12.6803, "80pct": 17.2328, "90pct": 22.4361}
TOTAL_ABS_ERROR_BANDS = {"68pct": 13.1899, "80pct": 16.5569, "90pct": 22.5405}


def f(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def fetch_schedule():
    req = urllib.request.Request(SCHEDULE_URL, headers={"User-Agent": "cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode("utf-8")
    return list(csv.DictReader(text.splitlines()))


def ats_grade(actual_home_margin, home_spread_reference, disagreement):
    if home_spread_reference is None or disagreement is None or abs(disagreement) < 1e-12:
        return "NO_GRADE"
    ats_result = actual_home_margin + home_spread_reference
    if abs(ats_result) < 1e-12:
        return "PUSH"
    return "WIN" if disagreement * ats_result > 0 else "LOSS"


def ou_grade(actual_total, total_reference, disagreement):
    if total_reference is None or disagreement is None or abs(disagreement) < 1e-12:
        return "NO_GRADE"
    ou_result = actual_total - total_reference
    if abs(ou_result) < 1e-12:
        return "PUSH"
    return "WIN" if disagreement * ou_result > 0 else "LOSS"


def band_label(err, bands):
    if err <= bands["68pct"]:
        return "WITHIN_HISTORICAL_68PCT_ABS_ERROR"
    if err <= bands["80pct"]:
        return "BETWEEN_HISTORICAL_68_AND_80PCT"
    if err <= bands["90pct"]:
        return "BETWEEN_HISTORICAL_80_AND_90PCT"
    return "WORSE_THAN_HISTORICAL_90PCT_ABS_ERROR"


def summary(rows):
    if not rows:
        return {"games": 0, "spread_mae": None, "total_mae": None, "spread_reference_record": None, "total_reference_record": None}
    spread_errors = [r["spread_absolute_error"] for r in rows]
    total_errors = [r["total_absolute_error"] for r in rows]
    def rec(key):
        wins = sum(r[key] == "WIN" for r in rows)
        losses = sum(r[key] == "LOSS" for r in rows)
        pushes = sum(r[key] == "PUSH" for r in rows)
        decisions = wins + losses
        return {"wins": wins, "losses": losses, "pushes": pushes, "decisions": decisions, "win_rate": None if not decisions else round(wins / decisions, 4)}
    return {
        "games": len(rows),
        "spread_mae": round(sum(spread_errors) / len(spread_errors), 4),
        "total_mae": round(sum(total_errors) / len(total_errors), 4),
        "spread_reference_record": rec("spread_reference_grade"),
        "total_reference_record": rec("total_reference_grade"),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    manifest = snap["manifest"]
    rows = snap["rows"]
    schedule = {r.get("game_id", ""): r for r in fetch_schedule()}

    graded = []
    pending = []
    for s in rows:
        g = schedule.get(s["game_id"])
        if not g:
            pending.append({"game_id": s["game_id"], "reason": "MISSING_FROM_SCHEDULE_SOURCE"})
            continue
        hs = f(g.get("home_score")); aws = f(g.get("away_score"))
        if hs is None or aws is None:
            pending.append({"game_id": s["game_id"], "reason": "GAME_NOT_COMPLETED"})
            continue
        actual_margin = hs - aws
        actual_total = hs + aws
        pred_margin = f(s["final_research_home_margin"])
        pred_total = f(s["projected_total"])
        sp_ref = f(s["schedule_home_spread_reference"])
        tot_ref = f(s["schedule_total_reference"])
        sp_dis = f(s["spread_disagreement_vs_schedule_reference"])
        tot_dis = f(s["total_disagreement_vs_schedule_reference"])
        spread_err = abs(actual_margin - pred_margin)
        total_err = abs(actual_total - pred_total)
        graded.append({
            "snapshot_id": manifest["snapshot_id"],
            "game_id": s["game_id"],
            "away_team": s["away_team"],
            "home_team": s["home_team"],
            "hard_qb_state_break": bool(s["hard_qb_state_break"]),
            "personnel_state_at_snapshot": s["personnel_state"],
            "actual_home_margin": round(actual_margin, 3),
            "pred_home_margin": pred_margin,
            "spread_absolute_error": round(spread_err, 3),
            "spread_error_band": band_label(spread_err, SPREAD_ABS_ERROR_BANDS),
            "actual_total": round(actual_total, 3),
            "pred_total": pred_total,
            "total_absolute_error": round(total_err, 3),
            "total_error_band": band_label(total_err, TOTAL_ABS_ERROR_BANDS),
            "schedule_home_spread_reference": sp_ref,
            "spread_disagreement_vs_schedule_reference": sp_dis,
            "spread_reference_grade": ats_grade(actual_margin, sp_ref, sp_dis),
            "schedule_total_reference": tot_ref,
            "total_disagreement_vs_schedule_reference": tot_dis,
            "total_reference_grade": ou_grade(actual_total, tot_ref, tot_dis),
            "execution_price_was_verified_at_snapshot": False,
            "roi_grade_allowed": False,
        })

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    hard = [r for r in graded if r["hard_qb_state_break"]]
    normal = [r for r in graded if not r["hard_qb_state_break"]]
    result = {
        "graded_at_utc": now.isoformat(),
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_file": str(SNAPSHOT),
        "completed_games_graded": len(graded),
        "pending_games": pending,
        "all_completed_summary": summary(graded),
        "hard_qb_break_summary": summary(hard),
        "non_hard_qb_break_summary": summary(normal),
        "historical_error_bands": {"spread": SPREAD_ABS_ERROR_BANDS, "total": TOTAL_ABS_ERROR_BANDS},
        "market_grading_policy": "Frozen schedule references only. No verified executable-price or ROI grading is permitted for this snapshot.",
        "promotion_policy": "One prospective week cannot promote a betting threshold. Accumulate timestamped weeks before any release decision.",
        "rows": graded,
        "website_publish_allowed": False,
    }
    json_path = OUT_DIR / f"week6_grade_{stamp}.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if graded:
        csv_path = OUT_DIR / f"week6_grade_{stamp}.csv"
        with csv_path.open("x", newline="", encoding="utf-8") as fobj:
            w = csv.DictWriter(fobj, fieldnames=list(graded[0]))
            w.writeheader(); w.writerows(graded)
    else:
        csv_path = None

    print(json.dumps({
        "snapshot_id": manifest["snapshot_id"],
        "completed_games_graded": len(graded),
        "pending_games": len(pending),
        "json_output": str(json_path),
        "csv_output": None if csv_path is None else str(csv_path),
        "state": "WAITING_FOR_COMPLETED_GAMES" if not graded else "PARTIAL_OR_COMPLETE_GRADE"
    }, indent=2))


if __name__ == "__main__":
    main()
