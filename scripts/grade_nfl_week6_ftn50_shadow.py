#!/usr/bin/env python3
"""Grade the frozen Week 6 FTN50 shadow against the canonical model.

The shadow and canonical snapshots are immutable pregame evidence. This grader
can be rerun as games complete, but it never rewrites either snapshot. Results
are research-only and cannot promote the shadow from a single week.
"""
from __future__ import annotations

import csv
import json
import math
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CANONICAL = Path("nfl_data/prospective/week6_prelock_20261017T225656Z.json")
SHADOW = Path("nfl_data/prospective/shadow/week6_ftn50_shadow_20261017T235342Z.json")
PUBLIC_CAPTURE = Path("nfl_data/prospective/market_captures/week6_betmgm_web_capture_20261017T225910Z.json")
OUT_DIR = Path("nfl_data/prospective/shadow_grades")
SCHEDULE_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"


def f(v):
    if v is None:
        return None
    try:
        x = float(str(v).strip())
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def fetch_schedule():
    req = urllib.request.Request(SCHEDULE_URL, headers={"User-Agent": "cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return list(csv.DictReader(r.read().decode("utf-8").splitlines()))


def ats_grade(actual_margin, line, disagreement):
    if line is None or disagreement is None or abs(disagreement) < 1e-12:
        return "NO_GRADE"
    ats = actual_margin + line
    if abs(ats) < 1e-12:
        return "PUSH"
    return "WIN" if disagreement * ats > 0 else "LOSS"


def record(rows, key):
    w = sum(r[key] == "WIN" for r in rows)
    l = sum(r[key] == "LOSS" for r in rows)
    p = sum(r[key] == "PUSH" for r in rows)
    n = sum(r[key] == "NO_GRADE" for r in rows)
    d = w + l
    return {"wins": w, "losses": l, "pushes": p, "no_grades": n, "decisions": d, "win_rate_ex_push": None if not d else round(w / d, 4)}


def summarize(rows):
    if not rows:
        return {
            "games": 0,
            "canonical_spread_mae": None,
            "shadow_spread_mae": None,
            "shadow_minus_canonical_mae": None,
            "shadow_games_lower_absolute_error": 0,
            "canonical_games_lower_absolute_error": 0,
            "ties": 0,
            "shadow_public_book_direction_record": None,
        }
    c = sum(r["canonical_spread_absolute_error"] for r in rows) / len(rows)
    s = sum(r["shadow_spread_absolute_error"] for r in rows) / len(rows)
    return {
        "games": len(rows),
        "canonical_spread_mae": round(c, 4),
        "shadow_spread_mae": round(s, 4),
        "shadow_minus_canonical_mae": round(s - c, 4),
        "shadow_games_lower_absolute_error": sum(r["shadow_spread_absolute_error"] < r["canonical_spread_absolute_error"] for r in rows),
        "canonical_games_lower_absolute_error": sum(r["canonical_spread_absolute_error"] < r["shadow_spread_absolute_error"] for r in rows),
        "ties": sum(abs(r["canonical_spread_absolute_error"] - r["shadow_spread_absolute_error"]) < 1e-12 for r in rows),
        "shadow_public_book_direction_record": record(rows, "shadow_public_book_spread_benchmark_grade"),
        "canonical_public_book_direction_record": record(rows, "canonical_public_book_spread_benchmark_grade"),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    can = json.loads(CANONICAL.read_text(encoding="utf-8"))
    sh = json.loads(SHADOW.read_text(encoding="utf-8"))
    cap = json.loads(PUBLIC_CAPTURE.read_text(encoding="utf-8"))

    canonical_id = can["manifest"]["snapshot_id"]
    shadow_id = sh["manifest"]["shadow_snapshot_id"]
    if sh["manifest"]["canonical_snapshot_id"] != canonical_id:
        raise RuntimeError("shadow/canonical snapshot relationship mismatch")
    if sh["manifest"].get("website_publish_allowed") is not False:
        raise RuntimeError("shadow unexpectedly publishable")

    can_rows = {r["game_id"]: r for r in can["rows"]}
    sh_rows = {r["game_id"]: r for r in sh["rows"]}
    cap_rows = {r["game_id"]: r for r in cap["rows"]}
    if set(can_rows) != set(sh_rows) or set(can_rows) != set(cap_rows):
        raise RuntimeError("canonical/shadow/public-capture game sets differ")

    schedule = {r.get("game_id", ""): r for r in fetch_schedule()}
    graded = []
    pending = []
    for gid in sorted(can_rows):
        c = can_rows[gid]
        s = sh_rows[gid]
        b = cap_rows[gid]
        g = schedule.get(gid)
        if not g:
            pending.append({"game_id": gid, "reason": "MISSING_FROM_SCHEDULE_SOURCE"})
            continue
        hs = f(g.get("home_score")); aws = f(g.get("away_score"))
        if hs is None or aws is None:
            pending.append({"game_id": gid, "reason": "GAME_NOT_COMPLETED"})
            continue

        actual = hs - aws
        cp = f(c["final_research_home_margin"])
        sp = f(s["shadow_50_50_home_margin"])
        line = f(b["home_spread"])
        cdis = None if line is None else cp + line
        sdis = None if line is None else sp + line
        ce = abs(actual - cp); se = abs(actual - sp)
        graded.append({
            "canonical_snapshot_id": canonical_id,
            "shadow_snapshot_id": shadow_id,
            "game_id": gid,
            "away_team": c["away_team"],
            "home_team": c["home_team"],
            "hard_qb_state_break": bool(c["hard_qb_state_break"]),
            "actual_home_margin": round(actual, 3),
            "canonical_home_margin": cp,
            "shadow_home_margin": sp,
            "canonical_spread_absolute_error": round(ce, 3),
            "shadow_spread_absolute_error": round(se, 3),
            "shadow_minus_canonical_absolute_error": round(se - ce, 3),
            "lower_error_model": "SHADOW" if se < ce else ("CANONICAL" if ce < se else "TIE"),
            "public_book": b.get("book"),
            "public_book_capture_created_at_utc": b.get("capture_created_at_utc"),
            "public_book_home_spread": line,
            "canonical_public_book_spread_disagreement": None if cdis is None else round(cdis, 3),
            "shadow_public_book_spread_disagreement": None if sdis is None else round(sdis, 3),
            "canonical_public_book_spread_benchmark_grade": ats_grade(actual, line, cdis),
            "shadow_public_book_spread_benchmark_grade": ats_grade(actual, line, sdis),
            "public_book_price_was_account_executable_verified": bool(b.get("user_account_execution_verified")),
            "roi_grade_allowed": False,
            "promotion_allowed_from_this_week_alone": False,
            "website_publish_allowed": False,
        })

    hard = [r for r in graded if r["hard_qb_state_break"]]
    normal = [r for r in graded if not r["hard_qb_state_break"]]
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    result = {
        "graded_at_utc": now.isoformat(),
        "canonical_snapshot_id": canonical_id,
        "shadow_snapshot_id": shadow_id,
        "canonical_snapshot_file": str(CANONICAL),
        "shadow_snapshot_file": str(SHADOW),
        "completed_games_graded": len(graded),
        "pending_games": pending,
        "all_completed_summary": summarize(graded),
        "hard_qb_break_summary": summarize(hard),
        "non_hard_qb_break_summary": summarize(normal),
        "interpretation_policy": "Prospective head-to-head evidence only. Week 6 alone cannot promote, reject, or retune the shadow architecture.",
        "market_policy": "Public BetMGM capture is a benchmark only and was not verified as account-executable.",
        "promotion_allowed": False,
        "recommendation_release_allowed": False,
        "website_publish_allowed": False,
        "rows": graded,
    }
    jpath = OUT_DIR / f"week6_ftn50_shadow_grade_{stamp}.json"
    jpath.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cpath = None
    if graded:
        cpath = OUT_DIR / f"week6_ftn50_shadow_grade_{stamp}.csv"
        with cpath.open("x", newline="", encoding="utf-8") as fobj:
            writer = csv.DictWriter(fobj, fieldnames=list(graded[0]))
            writer.writeheader(); writer.writerows(graded)

    print(json.dumps({
        "canonical_snapshot_id": canonical_id,
        "shadow_snapshot_id": shadow_id,
        "completed_games_graded": len(graded),
        "pending_games": len(pending),
        "summary": result["all_completed_summary"],
        "json_output": str(jpath),
        "csv_output": None if cpath is None else str(cpath),
        "state": "WAITING_FOR_COMPLETED_GAMES" if not graded else "PARTIAL_OR_COMPLETE_GRADE",
        "website_publish_allowed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
