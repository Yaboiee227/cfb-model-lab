#!/usr/bin/env python3
"""Week 8 runner for the CFB shadow engine.

This adapter does two production-safety jobs around the generic shadow engine:
1. Parse ESPN's FBS-only grouped team response (`groups[*].teams`).
2. Estimate home-field advantage as a slow structural parameter from multiple
   completed prior FBS seasons instead of letting the small 2026 sample absorb
   schedule composition into HFA.

Current 2026 games still determine team-strength and scoring-environment effects.
The historical seasons are used only for the structural HFA estimate.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone

import cfb_shadow_engine as engine


def extract_grouped_team_ids(doc):
    ids = set()
    for sport in doc.get("sports", []):
        for league in sport.get("leagues", []):
            for group in league.get("groups", []):
                for entry in group.get("teams", []):
                    team = entry.get("team") or entry
                    if team.get("id") is not None:
                        ids.add(str(team["id"]))
            for entry in league.get("teams", []):
                team = entry.get("team") or entry
                if team.get("id") is not None:
                    ids.add(str(team["id"]))
    for entry in doc.get("teams", []):
        team = entry.get("team") or entry
        if team.get("id") is not None:
            ids.add(str(team["id"]))
    return sorted(ids, key=lambda x: (len(x), x))


engine.extract_team_ids = extract_grouped_team_ids

_ORIGINAL_TUNE = engine.tune
_ORIGINAL_RUN = engine.run
_HFA_META = {}


def estimate_historical_hfa(alpha: float, min_apps: int):
    """Estimate HFA independently for completed 2023-2025 FBS seasons.

    Each season gets its own team-strength effects so a team's 2023 strength is
    never assumed equal to its 2025 strength. The final structural HFA is the
    median of the season-specific estimates, reducing sensitivity to one season.
    """
    season_rows = []
    for season in (2023, 2024, 2025):
        start = datetime(season, 8, 1, tzinfo=timezone.utc)
        end = datetime(season + 1, 1, 15, tzinfo=timezone.utc)
        games = engine.fetch_completed_games(start, end)
        model = engine.fit_model(
            games,
            end,
            alpha=alpha,
            half_life_days=None,
            min_team_appearances=min_apps,
            fixed_hfa=None,
        )
        hfa = float(model["homeMarginAdvantage"])
        season_rows.append({
            "season": season,
            "rawGames": len(games),
            "eligibleGames": int(model["eligibleTrainingGames"]),
            "homeMarginAdvantage": hfa,
        })

    values = [row["homeMarginAdvantage"] for row in season_rows]
    structural = float(statistics.median(values))
    return structural, season_rows


def tune_with_historical_hfa(games, as_of):
    alpha, half_life, min_apps, _current_hfa, meta = _ORIGINAL_TUNE(games, as_of)
    structural_hfa, season_rows = estimate_historical_hfa(alpha, min_apps)
    global _HFA_META
    _HFA_META = {
        "method": "MEDIAN_OF_COMPLETED_2023_2025_FBS_SEASON_ESTIMATES",
        "seasonEstimates": season_rows,
        "structuralHomeMarginAdvantage": structural_hfa,
    }
    meta = dict(meta)
    meta["structuralHfaMethod"] = _HFA_META["method"]
    meta["historicalHfaSeasons"] = season_rows
    meta["selectedStructuralHomeMarginAdvantage"] = structural_hfa
    return alpha, half_life, min_apps, structural_hfa, meta


engine.tune = tune_with_historical_hfa


def run_with_structural_hfa(*args, **kwargs):
    out = _ORIGINAL_RUN(*args, **kwargs)
    out["modelId"] = "cfb-rebuild-alpha-shadow-v8h"
    out["fit"]["homeFieldSource"] = "MULTI_SEASON_FBS_HISTORICAL_MEDIAN"
    out["fit"]["structuralHomeFieldResearch"] = _HFA_META
    out["fit"]["homeFieldProvenancePass"] = bool(_HFA_META.get("seasonEstimates"))
    # Re-evaluate readiness after the provenance label is made explicit.
    hfa_ok = bool(out["fit"].get("homeFieldSanityPass")) and bool(out["fit"].get("homeFieldProvenancePass"))
    for game in out.get("games", []):
        if game.get("error") and "home-field" not in str(game.get("error")):
            continue
        if game.get("projectedSpreadHome") is not None and hfa_ok:
            game["status"] = "SHADOW_READY"
            game["error"] = None
        elif game.get("projectedSpreadHome") is not None:
            game["status"] = "SHADOW_REVIEW"
            game["error"] = "structural home-field parameter failed provenance/sanity gate"

    output_path = kwargs.get("output_path")
    if output_path is None and len(args) >= 2:
        output_path = args[1]
    if output_path is not None:
        output_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


engine.run = run_with_structural_hfa


if __name__ == "__main__":
    engine.main()
