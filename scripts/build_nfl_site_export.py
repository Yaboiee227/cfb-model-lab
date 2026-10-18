#!/usr/bin/env python3
"""Build the NFL data package for the shared CB Model Projections site.

The adapter converts the latest NFL research export into the same presentation
contract used by the existing CFB site while preserving NFL-specific reliability
and release-gate fields. It also derives the NFL record view from the canonical
prospective validation registry and generates an NFL-specific research hub.

Safety policy:
- writes only under nfl_data/site/
- never edits production data/ files
- never flips website publication to true
- does not invent NFL win probabilities
- canonical projection remains primary; FTN50 stays shadow/challenger
- public sportsbook prices remain benchmark context unless execution is verified
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("nfl_data/research_exports/week6_cfb_style_research_latest.csv")
REGISTRY_CSV = Path("nfl_data/prospective/validation_registry/nfl_prospective_validation_registry.csv")
REGISTRY_JSON = Path("nfl_data/prospective/validation_registry/nfl_prospective_validation_registry.json")
READINESS_JSON = Path("nfl_data/validation/model_readiness.json")
OUT_DIR = Path("nfl_data/site")
OUT_PROJECTIONS = OUT_DIR / "projections.csv"
OUT_RESULTS = OUT_DIR / "results.csv"
OUT_RESEARCH = OUT_DIR / "research.json"
OUT_CONFIG = OUT_DIR / "config.json"

SITE_FIELDS = [
    "league", "season", "week", "date", "kickoffET", "gameId",
    "awayTeam", "awayConference", "homeTeam", "homeConference",
    "projectedAwayPoints", "projectedHomePoints", "modelSpreadHome", "modelTotal",
    "homeWinProbability", "awayWinProbability", "marketSpreadHome", "marketTotal",
    "marketSource", "marketObservedAt", "executionVerified", "dataQuality",
    "signalStrength", "releaseStatus", "notes", "shadowModelSpreadHome",
    "spreadReliability", "totalReliability", "spread68Low", "spread68High",
    "total68Low", "total68High", "personnelState", "hardQbStateBreak",
    "qbExpectedStarter", "qbOperationalPointAdjustment", "weatherRoofState",
    "weatherElevatedUncertainty", "finalInactivesResolved", "releaseBlockers",
    "preferredArchitecture", "websitePublishAllowed",
]

RESULT_FIELDS = [
    "season", "week", "date", "gameId", "awayTeam", "homeTeam", "conference",
    "awayScore", "homeScore", "modelSpreadHome", "marketSpreadHome", "modelTotal",
    "marketTotal", "homeWinProbability", "atsProjection", "atsResult",
    "suProjection", "suResult",
]


def f(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def b(value):
    return str(value).strip().lower() == "true"


def reliability_letter(value: str) -> str:
    text = str(value or "").strip()
    return text[:1] if text else ""


def signal_from_reliability(spread: str, total: str) -> str:
    letters = {reliability_letter(spread), reliability_letter(total)}
    if "D" in letters:
        return "OUT_OF_DISTRIBUTION"
    if "C" in letters:
        return "ELEVATED_UNCERTAINTY"
    if "B" in letters:
        return "STANDARD_MODEL"
    return "UNRATED"


def projected_scores(total, home_margin):
    total = f(total)
    margin = f(home_margin)
    if total is None or margin is None:
        return None, None
    home = (total + margin) / 2.0
    away = (total - margin) / 2.0
    return round(away, 3), round(home, 3)


def actual_scores(total, home_margin):
    total = f(total)
    margin = f(home_margin)
    if total is None or margin is None:
        return None, None
    home = (total + margin) / 2.0
    away = (total - margin) / 2.0
    return int(round(away)), int(round(home))


def line_label(team, line):
    line = f(line)
    if line is None:
        return ""
    if abs(line) < 0.05:
        return f"{team} PK"
    return f"{team} {line:+.1f}"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def build_results():
    if not REGISTRY_CSV.exists():
        return []
    rows = list(csv.DictReader(REGISTRY_CSV.open(encoding="utf-8", newline="")))
    out = []
    for row in rows:
        pred_margin = f(row.get("pred_home_margin"))
        actual_margin = f(row.get("actual_home_margin"))
        away_score, home_score = actual_scores(row.get("actual_total"), actual_margin)
        away = row.get("away_team") or ""
        home = row.get("home_team") or ""
        market_home = f(row.get("public_book_home_spread"))
        model_home_spread = None if pred_margin is None else -pred_margin
        if pred_margin is None:
            su_projection = ""
            su_result = ""
        else:
            su_projection = home if pred_margin >= 0 else away
            if actual_margin is None or actual_margin == 0:
                su_result = "PUSH" if actual_margin == 0 else ""
            else:
                actual_winner = home if actual_margin > 0 else away
                su_result = "WIN" if actual_winner == su_projection else "LOSS"
        disagreement = f(row.get("public_book_spread_disagreement"))
        if disagreement is None or market_home is None:
            ats_projection = ""
        elif disagreement > 0:
            ats_projection = line_label(home, market_home)
        elif disagreement < 0:
            ats_projection = line_label(away, -market_home)
        else:
            ats_projection = "ALIGNED"
        out.append({
            "season": row.get("season") or "",
            "week": row.get("week") or "",
            "date": "",
            "gameId": row.get("game_id") or "",
            "awayTeam": away,
            "homeTeam": home,
            "conference": "NFL",
            "awayScore": "" if away_score is None else away_score,
            "homeScore": "" if home_score is None else home_score,
            "modelSpreadHome": "" if model_home_spread is None else round(model_home_spread, 4),
            "marketSpreadHome": row.get("public_book_home_spread") or "",
            "modelTotal": row.get("pred_total") or "",
            "marketTotal": row.get("public_book_total") or "",
            "homeWinProbability": "",
            "atsProjection": ats_projection,
            "atsResult": row.get("public_book_spread_benchmark_grade") or "",
            "suProjection": su_projection,
            "suResult": su_result,
        })
    return out


def build_research(site_rows, registry, readiness, latest_capture):
    hard_qb = sum(b(r.get("hardQbStateBreak")) for r in site_rows)
    elevated_weather = sum(b(r.get("weatherElevatedUncertainty")) for r in site_rows)
    final_inactives = sum(b(r.get("finalInactivesResolved")) for r in site_rows)
    execution = sum(b(r.get("executionVerified")) for r in site_rows)
    roof_pending = sum("ROOF" in str(r.get("weatherRoofState", "")).upper() and "PENDING" in str(r.get("weatherRoofState", "")).upper() for r in site_rows)
    completed = int(registry.get("completed_prospective_games", 0) or 0)
    weeks = int(registry.get("distinct_prospective_weeks_with_snapshot", 0) or 0)
    hist = registry.get("historical_reference") or {}
    spread_mae = hist.get("spread_oos_mae")
    total_mae = hist.get("total_oos_mae")
    architecture = readiness.get("final_research_architecture") or {}

    return {
        "updated": latest_capture or datetime.now(timezone.utc).isoformat(),
        "categories": [
            {
                "id": "availability",
                "label": "Injuries & availability",
                "short": "Availability",
                "status": "Game-day gate",
                "summary": "NFL starter identity, official game status and replacement uncertainty are kept separate from unvalidated point adjustments.",
                "items": [
                    {"title": "Hard QB state breaks", "detail": f"{hard_qb} current matchup(s) are classified as hard starting-QB breaks. They remain reliability/release gates; the operational QB point adjustment remains zero unless historically earned.", "tag": "QB gate"},
                    {"title": "Final inactives", "detail": f"{final_inactives}/{len(site_rows)} games currently have final-inactive resolution. Official inactive lists are required on game day before the contextual gate can fully clear.", "tag": "Inactives"},
                    {"title": "Replacement quality", "detail": "Depth chart, prior NFL performance and personnel context are recorded, but historical injury-burden coefficients were unstable and therefore were not promoted.", "tag": "Model discipline"},
                ],
            },
            {
                "id": "weather",
                "label": "Weather & venue",
                "short": "Weather",
                "status": "Pregame refresh",
                "summary": "Wind, precipitation, temperature and roof state are timestamped context, with elevated uncertainty surfaced rather than converted into arbitrary points.",
                "items": [
                    {"title": "Elevated environment", "detail": f"{elevated_weather} current matchup(s) carry elevated weather uncertainty. Final forecasts are refreshed close to kickoff.", "tag": "Environment"},
                    {"title": "Roof decisions", "detail": f"{roof_pending} current retractable-roof decision(s) remain explicitly pending in the site export.", "tag": "Venue"},
                    {"title": "Historical weather restraint", "detail": "Observed postgame weather is not backfilled as if it were a pregame forecast. Weather remains prospective context until timestamp-safe historical forecast data supports a learned coefficient.", "tag": "Leakage control"},
                ],
            },
            {
                "id": "market",
                "label": "Line movement & market",
                "short": "Market",
                "status": "Benchmark only",
                "summary": "The core NFL projection remains market-independent. Public sportsbook observations are comparison benchmarks, not proof of executable prices.",
                "items": [
                    {"title": "Latest public capture", "detail": f"Latest exported public-book benchmark timestamp: {latest_capture or 'unavailable'}. Market observations remain separate from the frozen model snapshot.", "tag": "Timestamp"},
                    {"title": "Execution verification", "detail": f"{execution}/{len(site_rows)} current games have account-level execution verification. Unverified public-board prices cannot support ROI or CLV claims.", "tag": "Price QA"},
                    {"title": "No market blend", "detail": "Historical market-blend testing favored the market benchmark itself, so no market residual or market-weighted projection was promoted into the independent core.", "tag": "Independence"},
                ],
            },
            {
                "id": "efficiency",
                "label": "Efficiency & model architecture",
                "short": "Efficiency",
                "status": "Frozen V1",
                "summary": "The NFL spread model uses only feature families that survived leakage-safe out-of-sample testing.",
                "items": [
                    {"title": "Canonical spread", "detail": f"Current spread architecture: {architecture.get('spread', {}).get('model', 'frozen core + validated research layers')}. Historical 2023-25 OOS MAE: {spread_mae if spread_mae is not None else '—'}.", "tag": "Canonical"},
                    {"title": "Canonical total", "detail": f"Current total architecture: {architecture.get('total', {}).get('model', 'frozen core')}. Historical 2023-25 OOS MAE: {total_mae if total_mae is not None else '—'}.", "tag": "Totals"},
                    {"title": "Rejected layers stay rejected", "detail": "NGS tracking, trenches, drive/pace, red-zone, turnover, special-teams, penalties, static travel/roof and historical injury-burden candidates were not promoted when robust validation did not support them.", "tag": "OOS discipline"},
                ],
            },
            {
                "id": "validation",
                "label": "Prospective validation",
                "short": "Validation",
                "status": "HOLD",
                "summary": "The model can publish research projections only after prospective evidence accumulates; betting recommendation thresholds require a larger, separate evidence gate.",
                "items": [
                    {"title": "Current prospective sample", "detail": f"{completed} completed prospectively frozen game(s) across {weeks} frozen week(s). The Week 6 snapshot is immutable and will be graded after games finish.", "tag": "Prospective"},
                    {"title": "Projection beta review", "detail": "Review eligibility begins at 40+ completed prospective games across at least 3 frozen weeks; this is not automatic promotion.", "tag": "Milestone"},
                    {"title": "Recommendation calibration", "detail": "PLAY/LEAN/HOLD calibration review begins only at 75+ completed games across at least 5 weeks, and still requires explicit evidence review.", "tag": "Release gate"},
                ],
            },
            {
                "id": "workflow",
                "label": "Weekly production workflow",
                "short": "Workflow",
                "status": "Active",
                "summary": "Each NFL week follows the same frozen-snapshot, game-day-gate, grading and registry process before any website release decision.",
                "items": [
                    {"title": "Pregame freeze", "detail": "Canonical and challenger projections are timestamped before games and are never rewritten after results are known.", "tag": "Integrity"},
                    {"title": "Game-day gates", "detail": "Final inactives, starter confirmation, roof/weather and fresh public-book benchmarks are refreshed separately from the frozen numerical prediction.", "tag": "Operations"},
                    {"title": "Postgame grading", "detail": "Canonical and FTN50 shadow models are graded on the same games, then the multi-week registry updates calibration and model-health diagnostics.", "tag": "Audit"},
                ],
            },
        ],
    }


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing source export: {SOURCE}")

    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8", newline="")))
    if not rows:
        raise SystemExit("NFL research export has no rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY_JSON, {})
    readiness = load_json(READINESS_JSON, {})

    site_rows = []
    capture_times = []
    weeks = set()
    for src in rows:
        away_pts, home_pts = projected_scores(src.get("model_total"), src.get("canonical_home_margin"))
        capture = src.get("public_book_capture_utc") or ""
        if capture:
            capture_times.append(capture)
        game_id = src.get("game_id") or ""
        try:
            week = int(game_id.split("_")[1])
        except Exception:
            week = 6
        weeks.add(week)

        spread_rel = src.get("spread_reliability_tier") or ""
        total_rel = src.get("total_reliability_tier") or ""
        blockers = src.get("release_blockers") or ""
        recommendation = src.get("recommendation") or "HOLD_NO_VALIDATED_EDGE_THRESHOLD"
        website_allowed = b(src.get("website_publish_allowed"))
        notes = (
            f"Spread reliability: {spread_rel}; total reliability: {total_rel}. "
            f"Release blockers: {blockers}. Public-book price is a benchmark unless execution is verified."
        )

        site_rows.append({
            "league": "NFL",
            "season": 2026,
            "week": week,
            "date": src.get("gameday") or "",
            "kickoffET": src.get("gametime_et") or "",
            "gameId": game_id,
            "awayTeam": src.get("away_team") or "",
            "awayConference": "NFL",
            "homeTeam": src.get("home_team") or "",
            "homeConference": "NFL",
            "projectedAwayPoints": away_pts if away_pts is not None else "",
            "projectedHomePoints": home_pts if home_pts is not None else "",
            "modelSpreadHome": src.get("canonical_home_spread") or "",
            "modelTotal": src.get("model_total") or "",
            "homeWinProbability": "",
            "awayWinProbability": "",
            "marketSpreadHome": src.get("public_book_home_spread") or "",
            "marketTotal": src.get("public_book_total") or "",
            "marketSource": f"{src.get('public_book') or 'Public book'} public benchmark",
            "marketObservedAt": capture,
            "executionVerified": str(b(src.get("user_account_execution_verified"))).lower(),
            "dataQuality": "",
            "signalStrength": signal_from_reliability(spread_rel, total_rel),
            "releaseStatus": recommendation,
            "notes": notes,
            "shadowModelSpreadHome": src.get("shadow_home_spread") or "",
            "spreadReliability": spread_rel,
            "totalReliability": total_rel,
            "spread68Low": src.get("spread_68_low") or "",
            "spread68High": src.get("spread_68_high") or "",
            "total68Low": src.get("total_68_low") or "",
            "total68High": src.get("total_68_high") or "",
            "personnelState": src.get("personnel_state") or "",
            "hardQbStateBreak": str(b(src.get("hard_qb_state_break"))).lower(),
            "qbExpectedStarter": src.get("qb_expected_starter") or "",
            "qbOperationalPointAdjustment": src.get("qb_operational_point_adjustment") or "",
            "weatherRoofState": src.get("weather_roof_state") or "",
            "weatherElevatedUncertainty": str(b(src.get("weather_elevated_uncertainty"))).lower(),
            "finalInactivesResolved": str(b(src.get("final_inactives_resolved"))).lower(),
            "releaseBlockers": blockers,
            "preferredArchitecture": src.get("preferred_architecture_for_release") or "CANONICAL",
            "websitePublishAllowed": str(website_allowed).lower(),
        })

    with OUT_PROJECTIONS.open("w", encoding="utf-8", newline="") as fobj:
        writer = csv.DictWriter(fobj, fieldnames=SITE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(site_rows)

    result_rows = build_results()
    with OUT_RESULTS.open("w", encoding="utf-8", newline="") as fobj:
        writer = csv.DictWriter(fobj, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result_rows)

    latest_capture = max(capture_times) if capture_times else None
    research = build_research(site_rows, registry, readiness, latest_capture)
    OUT_RESEARCH.write_text(json.dumps(research, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    config = {
        "siteName": "CB Model Projections",
        "league": "NFL",
        "season": 2026,
        "currentWeek": max(weeks) if weeks else 6,
        "lastUpdated": latest_capture,
        "modelVersion": "NFL Canonical v1 + FTN50 shadow challenger",
        "spreadValidation": "HOLD",
        "totalValidation": "HOLD",
        "publicationStatus": "Research only · no released NFL bets",
        "websitePublishAllowed": False,
        "integrationTarget": "Existing CB Model Projections site",
        "separateNflSite": False,
        "leagueSwitchEnabled": True,
        "preferredArchitecture": "CANONICAL_UNTIL_PROSPECTIVE_SHADOW_EVIDENCE_ACCUMULATES",
        "prospectiveState": registry.get("sample_state", "WAITING_FOR_FIRST_COMPLETED_PROSPECTIVE_GAMES"),
        "completedProspectiveGames": registry.get("completed_prospective_games", 0),
        "prospectiveWeeks": registry.get("distinct_prospective_weeks_with_snapshot", 0),
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "repoUrl": "https://github.com/Yaboiee227/cfb-model-lab",
        "disclaimer": (
            "NFL model output is provided for research and entertainment purposes only. "
            "HOLD projections are not released wagers. Public sportsbook observations are "
            "benchmarks unless account-level execution is verified."
        ),
    }
    OUT_CONFIG.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "source": str(SOURCE),
        "projection_rows": len(site_rows),
        "result_rows": len(result_rows),
        "projections_output": str(OUT_PROJECTIONS),
        "results_output": str(OUT_RESULTS),
        "research_output": str(OUT_RESEARCH),
        "config_output": str(OUT_CONFIG),
        "website_publish_allowed": False,
        "production_data_directory_touched": False,
    }, indent=2))


if __name__ == "__main__":
    main()
