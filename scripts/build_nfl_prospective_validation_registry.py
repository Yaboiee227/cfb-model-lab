#!/usr/bin/env python3
"""Build the canonical multi-week NFL prospective validation registry.

The registry is deliberately research-only. It scans timestamped prospective
postgame grade artifacts, deduplicates repeated grader runs for the same frozen
snapshot, and accumulates only completed games from the strongest available
canonical grade for each snapshot.

No betting threshold, recommendation, ROI claim, CLV claim, or website release
is authorized by this script. Edge buckets are descriptive diagnostics only.
"""
from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

GRADE_DIR = Path("nfl_data/prospective/grades")
READINESS = Path("nfl_data/validation/model_readiness.json")
OUT_DIR = Path("nfl_data/prospective/validation_registry")
OUT_JSON = OUT_DIR / "nfl_prospective_validation_registry.json"
OUT_CSV = OUT_DIR / "nfl_prospective_validation_registry.csv"

SPREAD_GRADE = "public_book_spread_benchmark_grade"
TOTAL_GRADE = "public_book_total_benchmark_grade"

CSV_FIELDS = [
    "season",
    "week",
    "snapshot_id",
    "source_grade_file",
    "game_id",
    "away_team",
    "home_team",
    "pred_home_margin",
    "actual_home_margin",
    "spread_signed_error",
    "spread_absolute_error",
    "public_book_home_spread",
    "public_book_spread_disagreement",
    "spread_edge_bucket",
    "public_book_spread_benchmark_grade",
    "pred_total",
    "actual_total",
    "total_signed_error",
    "total_absolute_error",
    "public_book_total",
    "public_book_total_disagreement",
    "total_edge_bucket",
    "public_book_total_benchmark_grade",
    "hard_qb_state_break",
    "weather_elevated_uncertainty",
    "public_book_price_was_account_executable_verified",
]


def f(value):
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def iso_key(value):
    if not value:
        return ""
    return str(value)


def parse_snapshot_context(snapshot_id: str, source_name: str):
    season = None
    week = None
    m = re.search(r"NFL_(\d{4})_W(\d+)", snapshot_id or "", re.I)
    if m:
        season = int(m.group(1))
        week = int(m.group(2))
    if week is None:
        m = re.search(r"week(\d+)", source_name, re.I)
        if m:
            week = int(m.group(1))
    return season, week


def edge_bucket(value):
    x = f(value)
    if x is None:
        return "UNAVAILABLE"
    x = abs(x)
    if x < 2.0:
        return "0_TO_LT2"
    if x < 4.0:
        return "2_TO_LT4"
    if x < 6.0:
        return "4_TO_LT6"
    return "6_PLUS"


def record(rows, key):
    wins = sum(r.get(key) == "WIN" for r in rows)
    losses = sum(r.get(key) == "LOSS" for r in rows)
    pushes = sum(r.get(key) == "PUSH" for r in rows)
    no_grades = sum(r.get(key) in (None, "NO_GRADE") for r in rows)
    decisions = wins + losses
    return {
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "no_grades": no_grades,
        "decisions": decisions,
        "win_rate_ex_push": None if not decisions else round(wins / decisions, 4),
    }


def mean(values):
    xs = [f(v) for v in values]
    xs = [x for x in xs if x is not None]
    return None if not xs else round(sum(xs) / len(xs), 4)


def error_summary(rows):
    return {
        "games": len(rows),
        "spread_mae": mean(r.get("spread_absolute_error") for r in rows),
        "spread_bias_actual_minus_pred": mean(r.get("spread_signed_error") for r in rows),
        "total_mae": mean(r.get("total_absolute_error") for r in rows),
        "total_bias_actual_minus_pred": mean(r.get("total_signed_error") for r in rows),
        "public_book_spread_direction_record": record(rows, SPREAD_GRADE),
        "public_book_total_direction_record": record(rows, TOTAL_GRADE),
    }


def bucket_summaries(rows, value_key, grade_key, bucket_key):
    order = ["0_TO_LT2", "2_TO_LT4", "4_TO_LT6", "6_PLUS", "UNAVAILABLE"]
    output = []
    for label in order:
        subset = [r for r in rows if r.get(bucket_key) == label]
        if not subset:
            continue
        rec = record(subset, grade_key)
        output.append({
            "bucket": label,
            "games": len(subset),
            "mean_absolute_model_market_disagreement": mean(abs(f(r.get(value_key))) for r in subset if f(r.get(value_key)) is not None),
            "direction_record": rec,
            "research_only": True,
            "threshold_status": "DESCRIPTIVE_ONLY_NOT_VALIDATED_FOR_RELEASE",
        })
    return output


def choose_canonical_grade(items):
    """Prefer the grade with the most completed games, then the newest run."""
    return max(
        items,
        key=lambda item: (
            int(item["payload"].get("completed_games_graded", len(item["payload"].get("rows", []))) or 0),
            iso_key(item["payload"].get("graded_at_utc")),
            item["path"].name,
        ),
    )


def load_grades():
    artifacts = []
    for path in sorted(GRADE_DIR.glob("week*_grade_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to load prospective grade artifact {path}: {exc}") from exc
        snapshot_id = payload.get("snapshot_id")
        if not snapshot_id:
            continue
        artifacts.append({"path": path, "payload": payload, "snapshot_id": snapshot_id})
    return artifacts


def historical_reference():
    if not READINESS.exists():
        return None
    d = json.loads(READINESS.read_text(encoding="utf-8"))
    arch = d.get("final_research_architecture", {})
    return {
        "source": str(READINESS),
        "spread_oos_games": arch.get("spread", {}).get("oos_games_2023_2025"),
        "spread_oos_mae": arch.get("spread", {}).get("oos_mae"),
        "total_oos_games": arch.get("total", {}).get("oos_games_2023_2025"),
        "total_oos_mae": arch.get("total", {}).get("oos_mae"),
        "production_release_state": d.get("production_release_state"),
    }


def milestone_state(games, weeks):
    if games == 0:
        return "WAITING_FOR_FIRST_COMPLETED_PROSPECTIVE_GAMES"
    if games < 25 or weeks < 2:
        return "EARLY_PROSPECTIVE_SAMPLE"
    if games < 40 or weeks < 3:
        return "ACCUMULATING_PROJECTION_BETA_EVIDENCE"
    if games < 75 or weeks < 5:
        return "PROJECTION_BETA_REVIEW_ELIGIBLE_RECOMMENDATIONS_LOCKED"
    return "CALIBRATION_REVIEW_ELIGIBLE_NO_AUTOMATIC_PROMOTION"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = load_grades()

    by_snapshot = {}
    for item in artifacts:
        by_snapshot.setdefault(item["snapshot_id"], []).append(item)

    canonical = [choose_canonical_grade(items) for items in by_snapshot.values()]
    canonical.sort(key=lambda item: item["snapshot_id"])

    rows = []
    snapshot_registry = []
    for item in canonical:
        p = item["payload"]
        snapshot_id = item["snapshot_id"]
        season, week = parse_snapshot_context(snapshot_id, item["path"].name)
        grade_rows = p.get("rows", []) or []
        completed = int(p.get("completed_games_graded", len(grade_rows)) or 0)
        if completed != len(grade_rows):
            raise RuntimeError(
                f"Completed-game count mismatch in {item['path']}: metadata={completed}, rows={len(grade_rows)}"
            )
        snapshot_registry.append({
            "snapshot_id": snapshot_id,
            "season": season,
            "week": week,
            "canonical_grade_file": str(item["path"]),
            "graded_at_utc": p.get("graded_at_utc"),
            "completed_games_graded": completed,
            "pending_games": len(p.get("pending_games", []) or []),
            "duplicate_grade_artifacts_seen": len(by_snapshot[snapshot_id]),
        })
        for source in grade_rows:
            row = dict(source)
            row["season"] = season
            row["week"] = week
            row["source_grade_file"] = str(item["path"])
            row["spread_edge_bucket"] = edge_bucket(row.get("public_book_spread_disagreement"))
            row["total_edge_bucket"] = edge_bucket(row.get("public_book_total_disagreement"))
            rows.append(row)

    # A frozen game belongs to exactly one canonical snapshot. Duplicate keys are an audit failure.
    seen = set()
    for row in rows:
        key = (row.get("snapshot_id"), row.get("game_id"))
        if key in seen:
            raise RuntimeError(f"Duplicate canonical prospective game row: {key}")
        seen.add(key)

    weeks = sorted({(r.get("season"), r.get("week")) for r in snapshot_registry if r.get("week") is not None})
    games = len(rows)
    aggregate = error_summary(rows)
    hard_qb = [r for r in rows if bool(r.get("hard_qb_state_break"))]
    normal_qb = [r for r in rows if not bool(r.get("hard_qb_state_break"))]
    elevated_weather = [r for r in rows if bool(r.get("weather_elevated_uncertainty"))]
    executable = [r for r in rows if bool(r.get("public_book_price_was_account_executable_verified"))]

    hist = historical_reference()
    spread_delta = None
    total_delta = None
    if hist and aggregate["spread_mae"] is not None and hist.get("spread_oos_mae") is not None:
        spread_delta = round(aggregate["spread_mae"] - float(hist["spread_oos_mae"]), 4)
    if hist and aggregate["total_mae"] is not None and hist.get("total_oos_mae") is not None:
        total_delta = round(aggregate["total_mae"] - float(hist["total_oos_mae"]), 4)

    health_alerts = []
    if games >= 25:
        if spread_delta is not None and spread_delta > 2.0:
            health_alerts.append("PROSPECTIVE_SPREAD_MAE_MATERIALLY_WORSE_THAN_HISTORICAL_OOS")
        if total_delta is not None and total_delta > 2.0:
            health_alerts.append("PROSPECTIVE_TOTAL_MAE_MATERIALLY_WORSE_THAN_HISTORICAL_OOS")

    state = milestone_state(games, len(weeks))
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "league": "NFL",
        "purpose": "Canonical multi-week prospective audit and calibration evidence registry.",
        "grade_artifacts_seen": len(artifacts),
        "unique_frozen_snapshots": len(canonical),
        "distinct_prospective_weeks_with_snapshot": len(weeks),
        "completed_prospective_games": games,
        "sample_state": state,
        "canonical_snapshot_registry": snapshot_registry,
        "historical_reference": hist,
        "aggregate": aggregate,
        "prospective_vs_historical_oos": {
            "spread_mae_delta": spread_delta,
            "total_mae_delta": total_delta,
            "interpretation_policy": "Do not interpret prospective-vs-historical deltas as stable until the prospective sample is sufficiently large and spans multiple weeks."
        },
        "state_splits": {
            "hard_qb_break": error_summary(hard_qb),
            "non_hard_qb_break": error_summary(normal_qb),
            "elevated_weather": error_summary(elevated_weather),
            "account_executable_price_verified": error_summary(executable),
        },
        "edge_bucket_summaries": {
            "spread": bucket_summaries(rows, "public_book_spread_disagreement", SPREAD_GRADE, "spread_edge_bucket"),
            "total": bucket_summaries(rows, "public_book_total_disagreement", TOTAL_GRADE, "total_edge_bucket"),
        },
        "milestones": {
            "projection_beta_review_eligible": games >= 40 and len(weeks) >= 3,
            "projection_beta_minimum_evidence_rule": ">=40 completed prospective games across >=3 frozen weeks; still requires explicit review.",
            "recommendation_calibration_review_eligible": games >= 75 and len(weeks) >= 5,
            "recommendation_review_minimum_evidence_rule": ">=75 completed prospective games across >=5 frozen weeks; this only permits calibration review, not automatic release.",
            "automatic_threshold_promotion": False,
        },
        "model_health_alerts": health_alerts,
        "policy": {
            "edge_buckets": "Descriptive research only. Larger disagreement is not assumed to mean better betting value.",
            "market_prices": "Public-book captures are benchmarks unless account-level executable verification is explicitly present.",
            "roi": "No ROI claim without verified account-executable pricing and a prospectively frozen recommendation policy.",
            "clv": "No CLV claim from public web-board movement alone.",
            "website": "NFL outputs remain isolated from the live CFB site until explicit release review.",
        },
        "automatic_threshold_promotion_allowed": False,
        "recommendation_release_allowed": False,
        "roi_claims_allowed": False,
        "clv_claims_allowed": False,
        "website_publish_allowed": False,
        "rows": rows,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fobj:
        writer = csv.DictWriter(fobj, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(json.dumps({
        "output_json": str(OUT_JSON),
        "output_csv": str(OUT_CSV),
        "grade_artifacts_seen": len(artifacts),
        "unique_frozen_snapshots": len(canonical),
        "distinct_weeks": len(weeks),
        "completed_games": games,
        "sample_state": state,
        "website_publish_allowed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
