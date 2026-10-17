#!/usr/bin/env python3
"""Build Week 6 replacement-QB residual-state diagnostics.

This is deliberately NOT a point-adjustment model.

Why:
- The frozen Week 6 architecture already contains Weeks 1-5 team performance, so
  recent replacement-QB snaps are partly embedded in the team-state features.
- Historical QB-room variants did not earn promotion over the frozen baseline.
- A confirmed starter change is therefore a release gate / out-of-distribution
  condition, not permission to add a hand-set "QB points" number.

The script creates an auditable stress diagnostic for confirmed hard QB breaks:
1. Verify the named unavailable primary and expected replacement against the
   pregame QB-room snapshot.
2. If identity lineage fails, fail closed and keep the frozen projection.
3. If observed replacement data exist, report the raw passer EPA/dropback gap
   and a FULL-EXTRAPOLATION stress margin for diagnostic purposes only.
4. Never apply that stress result to the operational projection.

All outputs remain HOLD_RESEARCH_ONLY and website_publish_allowed=False.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SEASON = 2026
WEEK = 6
ROOT = Path("nfl_data")
PROJ = ROOT / "generated/week6_research_projections.csv"
QB_ROOM = ROOT / "generated/qb_room_2026_week6_pregame.csv"
GATES = ROOT / "prospective/2026_week6_gate_inputs.json"
SCENARIO_INPUTS = ROOT / "prospective/2026_week6_qb_scenario_inputs.json"
QA = ROOT / "validation/qb_room_v1_qa.json"
OUT_JSON = ROOT / "prospective/week6_qb_scenario_diagnostics.json"
OUT_CSV = ROOT / "prospective/week6_qb_scenario_diagnostics.csv"


def f(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_csv(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def select_expected_prefix(qb, expected_name):
    """Return the QB-room prefix matching the verified expected starter."""
    for prefix in ("recent", "replacement", "primary"):
        if qb.get(f"{prefix}_player_name") == expected_name:
            return prefix
    return None


def main():
    projections = {r["game_id"]: r for r in load_csv(PROJ)}
    qb_rows = {r["team"]: r for r in load_csv(QB_ROOM)}
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    inputs = json.loads(SCENARIO_INPUTS.read_text(encoding="utf-8"))
    qb_qa = json.loads(QA.read_text(encoding="utf-8"))

    if inputs.get("season") != SEASON or inputs.get("week") != WEEK:
        raise RuntimeError("Scenario input season/week mismatch")

    baseline_spread_mae = f(qb_qa.get("baseline", {}).get("spread", {}).get("aggregate", {}).get("mae"))
    room_spread_mae = f(qb_qa.get("variants", {}).get("room", {}).get("spread", {}).get("aggregate", {}).get("mae"))
    primary_spread_mae = f(qb_qa.get("variants", {}).get("primary", {}).get("spread", {}).get("aggregate", {}).get("mae"))

    rows = []
    for game_id, spec in inputs["games"].items():
        p = projections.get(game_id)
        if p is None:
            raise RuntimeError(f"Missing Week 6 projection for {game_id}")
        gate = gates.get("games", {}).get(game_id, {})
        team = spec["affected_team"]
        side = "home" if p["home_team"] == team else "away" if p["away_team"] == team else None
        if side is None:
            raise RuntimeError(f"Affected team {team} not in {game_id}")

        base_margin = f(p.get("rating_adjusted_home_margin"))
        base_total = f(p.get("pred_total"))
        qb = qb_rows.get(team)
        state = "PASS_OBSERVED_REPLACEMENT_DIAGNOSTIC_ONLY"
        reason = "Verified replacement identity is present in the pregame QB-room snapshot."
        prefix = None

        if "HARD_QB_BREAK" not in str(gate.get("personnel_state", "")):
            state = "FAIL_CLOSED_GATE_NOT_HARD_QB_BREAK"
            reason = "Prospective gate does not identify a hard confirmed QB break."
        elif qb is None:
            state = "FAIL_CLOSED_TEAM_MISSING_QB_ROOM"
            reason = "Affected team is absent from the pregame QB-room snapshot."
        elif qb.get("primary_player_name") != spec["unavailable_primary"]:
            state = "FAIL_CLOSED_PRIMARY_IDENTITY_MISMATCH"
            reason = (
                f"Verified unavailable primary {spec['unavailable_primary']} does not match "
                f"QB-room primary {qb.get('primary_player_name')}."
            )
        else:
            prefix = select_expected_prefix(qb, spec["expected_starter"])
            if prefix is None:
                state = "FAIL_CLOSED_EXPECTED_STARTER_NOT_IN_QB_ROOM"
                reason = (
                    f"Verified expected starter {spec['expected_starter']} is not represented by "
                    "the current primary/recent/replacement QB-room identities."
                )

        row = {
            "game_id": game_id,
            "away_team": p["away_team"],
            "home_team": p["home_team"],
            "affected_team": team,
            "affected_side": side,
            "unavailable_primary": spec["unavailable_primary"],
            "expected_starter": spec["expected_starter"],
            "personnel_state": gate.get("personnel_state", ""),
            "scenario_state": state,
            "scenario_reason": reason,
            "base_home_margin": None if base_margin is None else round(base_margin, 3),
            "base_total": None if base_total is None else round(base_total, 3),
            "primary_pass_epa_per_db": None,
            "expected_starter_pass_epa_per_db": None,
            "raw_expected_minus_primary_epa_per_db": None,
            "expected_starter_observed_dropbacks": None,
            "qb_room_covered_dropbacks_per_source_week": None,
            "full_extrapolation_raw_offensive_epa_swing": None,
            "full_extrapolation_stress_home_margin": None,
            "full_extrapolation_policy": "DIAGNOSTIC_STRESS_ONLY_NOT_A_PROJECTION",
            "current_history_already_contains_replacement_snaps": None,
            "operational_point_adjustment": 0.0,
            "operational_home_margin": None if base_margin is None else round(base_margin, 3),
            "operational_total": None if base_total is None else round(base_total, 3),
            "adjustment_policy": "ZERO_UNTIL_QB_EFFECT_EARNS_HISTORICAL_VALIDATION",
            "recommendation": "HOLD",
            "release_state": "HOLD_RESEARCH_ONLY",
            "website_publish_allowed": False,
        }

        if prefix is not None and qb is not None and base_margin is not None:
            primary_epa = f(qb.get("primary_pass_epa_per_db"))
            expected_epa = f(qb.get(f"{prefix}_pass_epa_per_db"))
            expected_db = f(qb.get(f"{prefix}_dropbacks"))
            primary_db = f(qb.get("primary_dropbacks")) or 0.0
            replacement_db = f(qb.get("replacement_dropbacks")) or 0.0
            source_weeks = f(qb.get("max_current_week_used"))

            row["primary_pass_epa_per_db"] = None if primary_epa is None else round(primary_epa, 6)
            row["expected_starter_pass_epa_per_db"] = None if expected_epa is None else round(expected_epa, 6)
            row["expected_starter_observed_dropbacks"] = None if expected_db is None else round(expected_db, 1)
            row["current_history_already_contains_replacement_snaps"] = bool(expected_db and expected_db > 0)

            # The QB-room coverage figure is a scale diagnostic only. It is NOT
            # an assumed future pass volume and it is intentionally not used by
            # the frozen production architecture.
            covered_per_week = None
            if source_weeks and source_weeks > 0:
                covered_per_week = (primary_db + replacement_db) / source_weeks
                row["qb_room_covered_dropbacks_per_source_week"] = round(covered_per_week, 3)

            if primary_epa is not None and expected_epa is not None:
                gap = expected_epa - primary_epa
                row["raw_expected_minus_primary_epa_per_db"] = round(gap, 6)
                if covered_per_week is not None:
                    raw_swing = gap * covered_per_week
                    # Positive offensive swing benefits the affected team.
                    stress_margin = base_margin + raw_swing if side == "home" else base_margin - raw_swing
                    row["full_extrapolation_raw_offensive_epa_swing"] = round(raw_swing, 3)
                    row["full_extrapolation_stress_home_margin"] = round(stress_margin, 3)

        rows.append(row)

    qa_summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
        "week": WEEK,
        "games": len(rows),
        "pass_observed": sum(r["scenario_state"].startswith("PASS_") for r in rows),
        "fail_closed": sum(r["scenario_state"].startswith("FAIL_CLOSED") for r in rows),
        "qb_validation_baseline_spread_mae": baseline_spread_mae,
        "qb_validation_primary_spread_mae": primary_spread_mae,
        "qb_validation_room_spread_mae": room_spread_mae,
        "qb_validation_interpretation": "QB variants did not earn production promotion; no scenario point adjustment is authorized.",
        "double_count_guard": "Current Weeks 1-5 team state already contains observed replacement snaps where they occurred.",
        "release_state": "HOLD_RESEARCH_ONLY",
        "website_publish_allowed": False,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(qa_summary, indent=2) + "\n", encoding="utf-8")

    fields = list(rows[0])
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({
        "json": str(OUT_JSON),
        "csv": str(OUT_CSV),
        "pass_observed": qa_summary["pass_observed"],
        "fail_closed": qa_summary["fail_closed"],
        "release_state": qa_summary["release_state"],
    }, indent=2))


if __name__ == "__main__":
    main()
