#!/usr/bin/env python3
"""Build Week-6 NFL projection reliability and empirical uncertainty ranges.

This layer is explicitly NOT betting confidence. It combines:
1) empirical signed OOS error quantiles from the final 2023-2025 architecture;
2) transparent current-state reliability tiers from the immutable pregame gate
   snapshot.

No learned injury/weather point adjustment is applied. Games with confirmed QB
breaks are labeled out-of-distribution because historical injury burden did not
survive robustness validation. No recommendation is created.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

CAL = Path("nfl_data/calibration/final_architecture_calibration.json")
SNAP = Path("nfl_data/prospective/week6_prelock_20261017T225656Z.json")
OUT_DIR = Path("nfl_data/prospective")


def r3(x):
    return round(float(x), 3)


def interval(pred, q, lo_key, hi_key):
    return [r3(float(pred) + float(q[lo_key])), r3(float(pred) + float(q[hi_key]))]


def spread_tier(row):
    state = str(row["personnel_state"])
    if bool(row.get("hard_qb_state_break")):
        return "D — OUT_OF_DISTRIBUTION_QB_BREAK", "Confirmed expected-starter QB break; no validated historical QB injury coefficient."
    if "QB_RETURN_EXPECTED" in state:
        return "C — ELEVATED_STATE_UNCERTAINTY", "Returning QB state is not equivalent to a stable normal-starter state."
    if "MAJOR_NONQB_ABSENCES" in state:
        return "C — ELEVATED_STATE_UNCERTAINTY", "Major non-QB absences remain; historical injury burden did not earn a learned coefficient."
    if state.startswith("MONDAY_"):
        return "C — ELEVATED_STATE_UNCERTAINTY", "Monday final personnel status is unresolved at snapshot time."
    return "B — STANDARD_MODEL_PENDING_FINAL_GATES", "No confirmed QB break, but final inactive verification remains incomplete."


def total_tier(row):
    state = str(row["personnel_state"])
    weather = str(row["weather_roof_state"])
    if bool(row.get("hard_qb_state_break")):
        return "D — OUT_OF_DISTRIBUTION_QB_BREAK", "Confirmed QB break can materially alter scoring distribution; no validated injury total adjustment."
    if "QB_RETURN_EXPECTED" in state or "MAJOR_NONQB_ABSENCES" in state or state.startswith("MONDAY_"):
        return "C — ELEVATED_STATE_UNCERTAINTY", "Personnel state is materially unresolved or non-standard."
    if any(token in weather for token in ["WIND_MONITOR", "ROOF_DECISION_PENDING", "FORECAST_REFRESH_REQUIRED", "MONDAY_FINAL_FORECAST_REQUIRED"]):
        return "C — ELEVATED_ENVIRONMENT_UNCERTAINTY", "Final weather/roof state is unresolved and totals have no validated weather coefficient."
    return "B — STANDARD_MODEL_PENDING_FINAL_GATES", "No confirmed QB break; final inactive/market execution gates remain incomplete."


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cal = json.loads(CAL.read_text(encoding="utf-8"))
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    sq = cal["aggregate"]["spread"]["signed_actual_minus_pred_quantiles"]
    tq = cal["aggregate"]["total"]["signed_actual_minus_pred_quantiles"]
    rows = []
    for s in snap["rows"]:
        pm = float(s["final_research_home_margin"])
        pt = float(s["projected_total"])
        s68 = interval(pm, sq, "0.16", "0.84")
        s80 = interval(pm, sq, "0.1", "0.9")
        s90 = interval(pm, sq, "0.05", "0.95")
        t68 = interval(pt, tq, "0.16", "0.84")
        t80 = interval(pt, tq, "0.1", "0.9")
        t90 = interval(pt, tq, "0.05", "0.95")
        stier, sreason = spread_tier(s)
        ttier, treason = total_tier(s)
        rows.append({
            "snapshot_id": snap["manifest"]["snapshot_id"],
            "game_id": s["game_id"],
            "away_team": s["away_team"],
            "home_team": s["home_team"],
            "pred_home_margin": r3(pm),
            "spread_68_low": s68[0],
            "spread_68_high": s68[1],
            "spread_80_low": s80[0],
            "spread_80_high": s80[1],
            "spread_90_low": s90[0],
            "spread_90_high": s90[1],
            "spread_reliability_tier": stier,
            "spread_reliability_reason": sreason,
            "pred_total": r3(pt),
            "total_68_low": t68[0],
            "total_68_high": t68[1],
            "total_80_low": t80[0],
            "total_80_high": t80[1],
            "total_90_low": t90[0],
            "total_90_high": t90[1],
            "total_reliability_tier": ttier,
            "total_reliability_reason": treason,
            "personnel_state": s["personnel_state"],
            "weather_roof_state": s["weather_roof_state"],
            "state_point_adjustment_applied": False,
            "historical_edge_threshold_earned": False,
            "recommendation": "HOLD_NO_VALIDATED_EDGE_THRESHOLD",
            "website_publish_allowed": False,
        })

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = OUT_DIR / f"week6_projection_reliability_{stamp}.csv"
    json_path = OUT_DIR / f"week6_projection_reliability_{stamp}.json"
    with csv_path.open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": snap["manifest"]["snapshot_id"],
        "games": len(rows),
        "definition": "Projection reliability, not betting confidence. Intervals are empirical OOS signed-error ranges from the final architecture; state tiers are explicit operational gate labels.",
        "spread_oos": cal["aggregate"]["spread"],
        "total_oos": cal["aggregate"]["total"],
        "tier_policy": {
            "A": "Reserved for normal-state game with all final personnel/environment gates verified; none qualify at this snapshot.",
            "B": "No confirmed QB break but final game-day gates are still pending.",
            "C": "Elevated uncertainty from returning QB, major non-QB absences, Monday unresolved status, or unresolved weather/roof condition.",
            "D": "Confirmed expected-starter QB break; projection is out-of-distribution relative to the validated architecture."
        },
        "state_point_adjustment_policy": "None applied. Historical injury and weather coefficients did not earn promotion.",
        "rows": rows,
        "release_state": "HOLD_RELIABILITY_RESEARCH_ONLY",
        "website_publish_allowed": False,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"csv": str(csv_path), "json": str(json_path), "games": len(rows), "state": payload["release_state"]}, indent=2))


if __name__ == "__main__":
    main()
