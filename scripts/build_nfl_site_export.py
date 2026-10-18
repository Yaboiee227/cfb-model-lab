#!/usr/bin/env python3
"""Build an NFL site-preview export without touching production CFB site data.

This adapter converts the latest NFL CFB-style research export into a schema
compatible with the existing CB Model Projections presentation layer while
preserving NFL-specific reliability and release-gate fields.

Safety policy:
- writes only under nfl_data/site/
- never edits production data/ files
- never flips website publication to true
- does not invent NFL win probabilities
- canonical projection remains primary; FTN50 stays shadow/challenger
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("nfl_data/research_exports/week6_cfb_style_research_latest.csv")
OUT_DIR = Path("nfl_data/site")
OUT_PROJECTIONS = OUT_DIR / "projections.csv"
OUT_CONFIG = OUT_DIR / "config.json"

SITE_FIELDS = [
    "league",
    "season",
    "week",
    "date",
    "kickoffET",
    "gameId",
    "awayTeam",
    "awayConference",
    "homeTeam",
    "homeConference",
    "projectedAwayPoints",
    "projectedHomePoints",
    "modelSpreadHome",
    "modelTotal",
    "homeWinProbability",
    "awayWinProbability",
    "marketSpreadHome",
    "marketTotal",
    "marketSource",
    "marketObservedAt",
    "executionVerified",
    "dataQuality",
    "signalStrength",
    "releaseStatus",
    "notes",
    "shadowModelSpreadHome",
    "spreadReliability",
    "totalReliability",
    "spread68Low",
    "spread68High",
    "total68Low",
    "total68High",
    "personnelState",
    "hardQbStateBreak",
    "qbExpectedStarter",
    "qbOperationalPointAdjustment",
    "weatherRoofState",
    "weatherElevatedUncertainty",
    "finalInactivesResolved",
    "releaseBlockers",
    "preferredArchitecture",
    "websitePublishAllowed",
]


def f(value):
    if value in (None, ""):
        return None
    return float(value)


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


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing source export: {SOURCE}")

    rows = list(csv.DictReader(SOURCE.open(encoding="utf-8", newline="")))
    if not rows:
        raise SystemExit("NFL research export has no rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

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
            # Intentionally blank until an NFL-specific probability layer is validated.
            "homeWinProbability": "",
            "awayWinProbability": "",
            "marketSpreadHome": src.get("public_book_home_spread") or "",
            "marketTotal": src.get("public_book_total") or "",
            "marketSource": f"{src.get('public_book') or 'Public book'} public benchmark",
            "marketObservedAt": capture,
            "executionVerified": str(b(src.get("user_account_execution_verified"))).lower(),
            # NFL reliability tiers are surfaced separately. Do not fabricate CFB-style data-quality score.
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

    latest_capture = max(capture_times) if capture_times else None
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
        "preferredArchitecture": "CANONICAL_UNTIL_PROSPECTIVE_SHADOW_EVIDENCE_ACCUMULATES",
        "prospectiveState": "WAITING_FOR_FIRST_COMPLETED_PROSPECTIVE_GAMES",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "NFL model output is provided for research and entertainment purposes only. "
            "HOLD projections are not released wagers. Public sportsbook observations are "
            "benchmarks unless account-level execution is verified."
        ),
    }
    OUT_CONFIG.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "source": str(SOURCE),
        "rows": len(site_rows),
        "projections_output": str(OUT_PROJECTIONS),
        "config_output": str(OUT_CONFIG),
        "website_publish_allowed": False,
        "production_data_directory_touched": False,
    }, indent=2))


if __name__ == "__main__":
    main()
