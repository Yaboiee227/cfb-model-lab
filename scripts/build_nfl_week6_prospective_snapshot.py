#!/usr/bin/env python3
"""Create an immutable timestamped Week-6 NFL prospective research snapshot.

This snapshot is for future grading only. It does not create recommendations,
does not publish website data, and does not convert schedule reference prices
into executable prices. Every game remains HOLD because no historical betting
edge threshold has earned release and final game-day gates are incomplete.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

BOARD = Path("nfl_data/generated/week6_research_projections.csv")
GATES = Path("nfl_data/prospective/2026_week6_gate_inputs.json")
READINESS = Path("nfl_data/validation/model_readiness.json")
OUT_DIR = Path("nfl_data/prospective")


def as_bool_hard_break(state: str) -> bool:
    return state.startswith("HARD_QB_BREAK")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with BOARD.open(encoding="utf-8") as f:
        board = list(csv.DictReader(f))
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))

    if readiness.get("production_release_state") != "HOLD_PROSPECTIVE_VALIDATION_REQUIRED":
        raise RuntimeError("Unexpected readiness release state")
    if readiness.get("calibration_registry", {}).get("betting_edge_thresholds", {}).get("spread") != "NONE_EARNED":
        raise RuntimeError("Spread threshold unexpectedly promoted")
    if readiness.get("calibration_registry", {}).get("betting_edge_thresholds", {}).get("total") != "NONE_EARNED":
        raise RuntimeError("Total threshold unexpectedly promoted")
    if readiness.get("website_publish_allowed") is not False:
        raise RuntimeError("Website publication must remain disabled")

    gate_rows = gates.get("games", {})
    board_ids = {r["game_id"] for r in board}
    gate_ids = set(gate_rows)
    if board_ids != gate_ids:
        raise RuntimeError(f"Gate/board game mismatch board_only={sorted(board_ids-gate_ids)} gate_only={sorted(gate_ids-board_ids)}")
    if len(board) != 13:
        raise RuntimeError(f"Expected 13 remaining Week-6 games, got {len(board)}")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"NFL_2026_W6_PRELOCK_{stamp}"
    rows = []
    for r in board:
        g = gate_rows[r["game_id"]]
        personnel_state = g["personnel_state"]
        hard_break = as_bool_hard_break(personnel_state)
        row = {
            "snapshot_id": snapshot_id,
            "snapshot_created_at_utc": now.isoformat(),
            "game_id": r["game_id"],
            "gameday": r["gameday"],
            "gametime": r["gametime"],
            "away_team": r["away_team"],
            "home_team": r["home_team"],
            "coverage_only_home_margin": r["coverage_only_home_margin"],
            "final_research_home_margin": r["rating_adjusted_home_margin"],
            "rating_layer_margin_delta": r["rating_layer_margin_delta"],
            "projected_home_spread": r["projected_home_spread"],
            "projected_total": r["pred_total"],
            "schedule_home_spread_reference": r["schedule_home_spread_reference"],
            "schedule_total_reference": r["schedule_total_reference"],
            "spread_disagreement_vs_schedule_reference": r["spread_edge_vs_schedule_reference"],
            "total_disagreement_vs_schedule_reference": r["total_edge_vs_schedule_reference"],
            "spread_model": r["spread_model"],
            "total_model": r["total_model"],
            "personnel_state": personnel_state,
            "hard_qb_state_break": hard_break,
            "personnel_note": g["personnel_note"],
            "personnel_sources": " | ".join(g.get("personnel_sources", [])),
            "weather_roof_state": g["weather_roof_state"],
            "execution_price_state": g["execution_price_state"],
            "schedule_reference_is_executable_price": False,
            "historical_spread_edge_threshold_earned": False,
            "historical_total_edge_threshold_earned": False,
            "recommendation": "HOLD_NO_VALIDATED_EDGE_THRESHOLD",
            "release_state": "HOLD_PROSPECTIVE_SNAPSHOT",
            "website_publish_allowed": False,
        }
        rows.append(row)

    csv_path = OUT_DIR / f"week6_prelock_{stamp}.csv"
    with csv_path.open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    manifest = {
        "snapshot_id": snapshot_id,
        "snapshot_created_at_utc": now.isoformat(),
        "immutable_snapshot_files": [str(csv_path), str(OUT_DIR / f"week6_prelock_{stamp}.json")],
        "season": 2026,
        "week": 6,
        "games": len(rows),
        "completed_week6_game_excluded": "2026_06_SEA_DEN",
        "source_projection_file": str(BOARD),
        "source_gate_file": str(GATES),
        "source_readiness_file": str(READINESS),
        "spread_architecture": readiness["final_research_architecture"]["spread"]["model"],
        "total_architecture": readiness["final_research_architecture"]["total"]["model"],
        "hard_qb_break_games": [r["game_id"] for r in rows if r["hard_qb_state_break"]],
        "release_policy": "All rows HOLD. No historical side/total edge threshold earned release. Direct executable price, final inactive, roof/weather and prospective validation gates remain required.",
        "postgame_rule": "Do not modify or overwrite this snapshot after creation. Grade it in a separate artifact after games complete.",
        "website_publish_allowed": False,
    }
    json_path = OUT_DIR / f"week6_prelock_{stamp}.json"
    json_path.write_text(json.dumps({"manifest": manifest, "rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "snapshot_id": snapshot_id,
        "csv": str(csv_path),
        "json": str(json_path),
        "games": len(rows),
        "hard_qb_break_games": manifest["hard_qb_break_games"],
        "release_state": "HOLD_PROSPECTIVE_SNAPSHOT"
    }, indent=2))


if __name__ == "__main__":
    main()
