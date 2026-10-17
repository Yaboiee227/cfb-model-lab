#!/usr/bin/env python3
"""Grade the immutable NFL Week-6 prospective snapshot without modifying it.

The grader may be run repeatedly as games complete. Each run creates a new
postgame grading artifact. The original pre-lock model snapshot, timestamped
public-book capture and readiness matrix remain untouched.

Two market references are graded:
1. schedule reference captured with the immutable model snapshot;
2. timestamped BetMGM public web-board capture.

The BetMGM capture is a benchmark only. It was not verified as executable in the
user's logged-in account, so ROI, CLV-to-execution and realized betting-return
claims remain prohibited.
"""
from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT = Path("nfl_data/prospective/week6_prelock_20261017T225656Z.json")
PUBLIC_CAPTURE = Path("nfl_data/prospective/market_captures/week6_betmgm_web_capture_20261017T225910Z.json")
READINESS = Path("nfl_data/prospective/week6_readiness_matrix_20261017.json")
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
    """Grade the model-disagreement side versus a frozen home spread.

    home_spread_reference is the sportsbook home spread (e.g. -3). A positive
    disagreement means the model prefers the home side relative to that line.
    """
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


def record(rows, key):
    wins = sum(r[key] == "WIN" for r in rows)
    losses = sum(r[key] == "LOSS" for r in rows)
    pushes = sum(r[key] == "PUSH" for r in rows)
    no_grades = sum(r[key] == "NO_GRADE" for r in rows)
    decisions = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "no_grades": no_grades,
        "decisions": decisions,
        "win_rate": None if not decisions else round(wins / decisions, 4),
    }


def summary(rows):
    if not rows:
        return {
            "games": 0,
            "spread_mae": None,
            "total_mae": None,
            "schedule_spread_reference_record": None,
            "schedule_total_reference_record": None,
            "public_book_spread_benchmark_record": None,
            "public_book_total_benchmark_record": None,
        }
    spread_errors = [r["spread_absolute_error"] for r in rows]
    total_errors = [r["total_absolute_error"] for r in rows]
    return {
        "games": len(rows),
        "spread_mae": round(sum(spread_errors) / len(spread_errors), 4),
        "total_mae": round(sum(total_errors) / len(total_errors), 4),
        "schedule_spread_reference_record": record(rows, "schedule_spread_reference_grade"),
        "schedule_total_reference_record": record(rows, "schedule_total_reference_grade"),
        "public_book_spread_benchmark_record": record(rows, "public_book_spread_benchmark_grade"),
        "public_book_total_benchmark_record": record(rows, "public_book_total_benchmark_grade"),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    capture = json.loads(PUBLIC_CAPTURE.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))

    manifest = snap["manifest"]
    snapshot_id = manifest["snapshot_id"]
    rows = snap["rows"]
    cap_rows = {r["game_id"]: r for r in capture["rows"]}
    ready_rows = {r["game_id"]: r for r in readiness["rows"]}

    if readiness.get("snapshot_id") != snapshot_id:
        raise RuntimeError("Readiness matrix snapshot mismatch")
    if any(r.get("snapshot_id") != snapshot_id for r in capture["rows"]):
        raise RuntimeError("Public-book capture snapshot mismatch")
    if capture.get("games") != len(rows):
        raise RuntimeError("Public-book capture game count mismatch")
    if readiness.get("website_publish_allowed") is not False:
        raise RuntimeError("Readiness matrix unexpectedly permits website publication")

    schedule = {r.get("game_id", ""): r for r in fetch_schedule()}

    graded = []
    pending = []
    for s in rows:
        gid = s["game_id"]
        g = schedule.get(gid)
        c = cap_rows.get(gid)
        rd = ready_rows.get(gid)
        if c is None or rd is None:
            raise RuntimeError(f"Missing frozen capture/readiness row for {gid}")
        if not g:
            pending.append({"game_id": gid, "reason": "MISSING_FROM_SCHEDULE_SOURCE"})
            continue

        hs = f(g.get("home_score"))
        aws = f(g.get("away_score"))
        if hs is None or aws is None:
            pending.append({"game_id": gid, "reason": "GAME_NOT_COMPLETED"})
            continue

        actual_margin = hs - aws
        actual_total = hs + aws
        pred_margin = f(s["final_research_home_margin"])
        pred_total = f(s["projected_total"])

        schedule_spread = f(s["schedule_home_spread_reference"])
        schedule_total = f(s["schedule_total_reference"])
        schedule_spread_disagreement = f(s["spread_disagreement_vs_schedule_reference"])
        schedule_total_disagreement = f(s["total_disagreement_vs_schedule_reference"])

        public_spread = f(c["home_spread"])
        public_total = f(c["total"])
        public_spread_disagreement = f(c["spread_disagreement_vs_direct_book"])
        public_total_disagreement = f(c["total_disagreement_vs_direct_book"])

        spread_err = abs(actual_margin - pred_margin)
        total_err = abs(actual_total - pred_total)

        graded.append({
            "snapshot_id": snapshot_id,
            "game_id": gid,
            "away_team": s["away_team"],
            "home_team": s["home_team"],
            "hard_qb_state_break": bool(s["hard_qb_state_break"]),
            "personnel_state_at_snapshot": s["personnel_state"],
            "readiness_release_blockers": rd["release_blockers"],
            "qb_scenario_state": rd.get("qb_scenario_state"),
            "qb_expected_starter": rd.get("qb_expected_starter"),
            "qb_profile_source": rd.get("qb_profile_source"),
            "qb_operational_point_adjustment": rd.get("qb_operational_point_adjustment"),
            "weather_roof_state": rd.get("weather_roof_state"),
            "weather_elevated_uncertainty": bool(rd.get("weather_elevated_uncertainty")),
            "actual_home_margin": round(actual_margin, 3),
            "pred_home_margin": pred_margin,
            "spread_signed_error": round(actual_margin - pred_margin, 3),
            "spread_absolute_error": round(spread_err, 3),
            "spread_error_band": band_label(spread_err, SPREAD_ABS_ERROR_BANDS),
            "actual_total": round(actual_total, 3),
            "pred_total": pred_total,
            "total_signed_error": round(actual_total - pred_total, 3),
            "total_absolute_error": round(total_err, 3),
            "total_error_band": band_label(total_err, TOTAL_ABS_ERROR_BANDS),
            "schedule_home_spread_reference": schedule_spread,
            "schedule_spread_disagreement": schedule_spread_disagreement,
            "schedule_spread_reference_grade": ats_grade(actual_margin, schedule_spread, schedule_spread_disagreement),
            "schedule_total_reference": schedule_total,
            "schedule_total_disagreement": schedule_total_disagreement,
            "schedule_total_reference_grade": ou_grade(actual_total, schedule_total, schedule_total_disagreement),
            "public_book": c.get("book"),
            "public_book_capture_created_at_utc": c.get("capture_created_at_utc"),
            "public_book_home_spread": public_spread,
            "public_book_home_spread_decimal_odds": f(c.get("home_spread_odds")),
            "public_book_spread_disagreement": public_spread_disagreement,
            "public_book_spread_benchmark_grade": ats_grade(actual_margin, public_spread, public_spread_disagreement),
            "public_book_total": public_total,
            "public_book_over_decimal_odds": f(c.get("over_odds")),
            "public_book_under_decimal_odds": f(c.get("under_odds")),
            "public_book_total_disagreement": public_total_disagreement,
            "public_book_total_benchmark_grade": ou_grade(actual_total, public_total, public_total_disagreement),
            "public_book_price_was_account_executable_verified": bool(c.get("user_account_execution_verified")),
            "roi_grade_allowed": False,
            "release_recommendation_at_snapshot": rd.get("recommendation"),
            "website_publish_allowed": False,
        })

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    hard = [r for r in graded if r["hard_qb_state_break"]]
    normal = [r for r in graded if not r["hard_qb_state_break"]]
    elevated_weather = [r for r in graded if r["weather_elevated_uncertainty"]]

    result = {
        "graded_at_utc": now.isoformat(),
        "snapshot_id": snapshot_id,
        "snapshot_file": str(SNAPSHOT),
        "public_book_capture_file": str(PUBLIC_CAPTURE),
        "public_book_capture_created_at_utc": capture.get("capture_created_at_utc"),
        "readiness_file": str(READINESS),
        "completed_games_graded": len(graded),
        "pending_games": pending,
        "all_completed_summary": summary(graded),
        "hard_qb_break_summary": summary(hard),
        "non_hard_qb_break_summary": summary(normal),
        "elevated_weather_summary": summary(elevated_weather),
        "historical_error_bands": {"spread": SPREAD_ABS_ERROR_BANDS, "total": TOTAL_ABS_ERROR_BANDS},
        "schedule_reference_policy": "Frozen schedule references are benchmark observations only.",
        "public_book_benchmark_policy": "Frozen timestamped BetMGM public web-board prices are benchmark observations only. They are not proof of executable prices in the user's account.",
        "roi_policy": "ROI grading is disabled because account-level executable prices were not verified at the frozen capture time.",
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
            w.writeheader()
            w.writerows(graded)
    else:
        csv_path = None

    print(json.dumps({
        "snapshot_id": snapshot_id,
        "completed_games_graded": len(graded),
        "pending_games": len(pending),
        "public_book_benchmark_loaded_games": len(cap_rows),
        "readiness_loaded_games": len(ready_rows),
        "json_output": str(json_path),
        "csv_output": None if csv_path is None else str(csv_path),
        "state": "WAITING_FOR_COMPLETED_GAMES" if not graded else "PARTIAL_OR_COMPLETE_GRADE",
        "website_publish_allowed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
