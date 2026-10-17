#!/usr/bin/env python3
"""Freeze a Week 6 prospective shadow snapshot for the robust FTN 50/50 blend.

This does NOT modify or supersede the canonical Week 6 snapshot. The shadow
spread is a fixed 50/50 blend of:
  A) canonical final spread architecture, and
  B) the 2022-selected FTN QB-process candidate.

The 50/50 weight was fixed before Week 6 outcomes and passed the historical
2023-2025 robustness rule. Totals are copied unchanged from the immutable
canonical snapshot. All rows remain research-only HOLD.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_nfl_walk_forward as base
import validate_nfl_coverage_v1 as cov
import validate_nfl_ftn_charting_robustness as ftn
import validate_nfl_rating_system_robustness as rat
import validate_nfl_final_plus_ftn_qb_process as qbp
import build_nfl_week6_research_projections as wk6

CANONICAL_CSV = Path("nfl_data/prospective/week6_prelock_20261017T225656Z.csv")
CANONICAL_JSON = Path("nfl_data/prospective/week6_prelock_20261017T225656Z.json")
CURRENT_FTN = Path("nfl_data/generated/ftn_charting_2026_week6_pregame.csv")
BLEND_VALIDATION = Path("nfl_data/validation/final_ftn_qb_process_blend.json")
CONTROL_VALIDATION = Path("nfl_data/validation/ftn_qb_process_controlled.json")
OUT_DIR = Path("nfl_data/prospective/shadow")
BLEND_WEIGHT = 0.50


def tf(v):
    return base.to_float(v)


def load_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_current_ftn():
    rows = load_csv(CURRENT_FTN)
    idx = {}
    leak = 0
    for r in rows:
        team = r["team"]
        if team in idx:
            raise RuntimeError(f"duplicate current FTN team {team}")
        mw = tf(r.get("max_current_week_used"))
        leak += int(mw is not None and mw >= 6)
        idx[team] = r
    if len(idx) != 32 or leak:
        raise RuntimeError(f"current FTN QA failed teams={len(idx)} leakage={leak}")
    return idx


def attach_current_ftn(games, idx):
    out = []
    for r in games:
        h = idx.get(r["home_team"])
        a = idx.get(r["away_team"])
        if h is None or a is None:
            raise RuntimeError(f"missing current FTN {r['away_team']}@{r['home_team']}")
        x = dict(r)
        for side, row in (("home", h), ("away", a)):
            for k, v in row.items():
                if k not in {"season", "target_week", "team", "release_state"}:
                    x[f"{side}_ftn_{k}"] = v
        out.append(x)
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    canonical_manifest = json.loads(CANONICAL_JSON.read_text(encoding="utf-8"))["manifest"]
    canonical_rows = load_csv(CANONICAL_CSV)
    canonical = {r["game_id"]: r for r in canonical_rows}
    if canonical_manifest.get("snapshot_id") != "NFL_2026_W6_PRELOCK_20261017T225656Z":
        raise RuntimeError("unexpected canonical snapshot id")
    if len(canonical) != 13:
        raise RuntimeError(f"expected 13 canonical rows, got {len(canonical)}")

    blend_val = json.loads(BLEND_VALIDATION.read_text(encoding="utf-8"))
    control_val = json.loads(CONTROL_VALIDATION.read_text(encoding="utf-8"))
    if not blend_val.get("robust_shadow_blend_earned"):
        raise RuntimeError("historical robust shadow blend was not earned")
    if float(blend_val.get("blend_candidate_weight")) != BLEND_WEIGHT:
        raise RuntimeError("validated blend weight mismatch")
    cand = control_val["selected_ftn_candidate_2022_only"]
    if float(cand["feature_k"]) != 1.0 or float(cand["lambda"]) != 300.0:
        raise RuntimeError(f"unexpected frozen FTN candidate params: {cand}")

    historical = base.load_rows()
    historical_cov = wk6.attach_historical_coverage(historical)
    fi, leak, _ = ftn.loadidx()
    if leak:
        raise RuntimeError(f"historical FTN leakage rows={leak}")
    historical_charted = ftn.attach(historical_cov, fi)

    # Recreate exactly the same current-game state used by the canonical model.
    team_rows, _, max_source_week, future_rows_used = wk6.build_team_snapshot()
    current_cov = wk6.load_current_coverage()
    current_games, completed_excluded = wk6.build_current_games(team_rows, current_cov)
    if max_source_week > 5 or future_rows_used:
        raise RuntimeError(f"current core leakage max_week={max_source_week} future={future_rows_used}")
    if len(current_games) != 13:
        raise RuntimeError(f"expected 13 remaining games, got {len(current_games)}")
    current_charted = attach_current_ftn(current_games, load_current_ftn())

    # Use the canonical frozen rating dynamics.
    rating_spec, rating_params = wk6.load_rating_spec()
    games_df = rat.fetch_games()
    rating_map = rat.rating_maps(
        games_df,
        rating_params["elo_k"],
        rating_params["elo_hfa"],
        rating_params["offseason_regression"],
        rating_params["margin_k"],
        rating_params["margin_hfa"],
    )
    hist_rated = rat.attach(historical_charted, rating_map)
    cur_rated = rat.attach(current_charted, rating_map)

    coverage_params = blend_val["coverage_params"]
    tk = float(coverage_params["team_k"])
    ck = float(coverage_params["feature_k"])

    # Reconstruct canonical final architecture as an audit control.
    canonical_fit = qbp.fit(hist_rated, tk, ck, float(rating_params["lambda"]), None)
    canonical_pred, _ = qbp.predict(cur_rated, tk, ck, canonical_fit, None)

    # Fit the historically validated FTN QB-process candidate on all completed
    # 2022-2025 training games, then predict Week 6 using only Weeks 1-5 state.
    candidate_fit = qbp.fit(hist_rated, tk, ck, float(cand["lambda"]), float(cand["feature_k"]))
    candidate_pred, candidate_coef = qbp.predict(
        cur_rated, tk, ck, candidate_fit, float(cand["feature_k"])
    )

    generated = datetime.now(timezone.utc)
    stamp = generated.strftime("%Y%m%dT%H%M%SZ")
    snapshot_id = f"NFL_2026_W6_FTN50_SHADOW_{stamp}"
    output = []
    max_reconstruction_delta = 0.0
    for game, recon, ftn_pred in zip(cur_rated, canonical_pred, candidate_pred):
        gid = game["game_id"]
        c = canonical.get(gid)
        if c is None:
            raise RuntimeError(f"game absent from canonical snapshot: {gid}")
        frozen_margin = float(c["final_research_home_margin"])
        recon = float(recon)
        ftn_pred = float(ftn_pred)
        recon_delta = abs(recon - frozen_margin)
        max_reconstruction_delta = max(max_reconstruction_delta, recon_delta)
        # The canonical file is rounded to 0.001; a 0.002 tolerance protects
        # against harmless serialization rounding while catching architecture drift.
        if recon_delta > 0.002:
            raise RuntimeError(
                f"canonical reconstruction drift {gid}: frozen={frozen_margin} reconstructed={recon} delta={recon_delta}"
            )
        shadow = (1.0 - BLEND_WEIGHT) * frozen_margin + BLEND_WEIGHT * ftn_pred
        public_line = tf(c.get("schedule_home_spread_reference"))
        output.append({
            "shadow_snapshot_id": snapshot_id,
            "shadow_snapshot_created_at_utc": generated.isoformat(),
            "canonical_snapshot_id": canonical_manifest["snapshot_id"],
            "game_id": gid,
            "gameday": c["gameday"],
            "gametime": c["gametime"],
            "away_team": c["away_team"],
            "home_team": c["home_team"],
            "canonical_home_margin": round(frozen_margin, 3),
            "ftn_qb_process_candidate_home_margin": round(ftn_pred, 3),
            "ftn_candidate_delta_vs_canonical": round(ftn_pred - frozen_margin, 3),
            "shadow_50_50_home_margin": round(shadow, 3),
            "shadow_projected_home_spread": round(-shadow, 3),
            "canonical_projected_total": float(c["projected_total"]),
            "schedule_home_spread_reference": "" if public_line is None else round(public_line, 3),
            "shadow_spread_disagreement_vs_schedule_reference": "" if public_line is None else round(shadow + public_line, 3),
            "hard_qb_state_break": str(c.get("hard_qb_state_break", "")).lower() == "true",
            "spread_architecture": "FIXED_50_50_BLEND_CANONICAL_FINAL_PLUS_FTN_QB_PROCESS",
            "total_architecture": "CANONICAL_FROZEN_CORE_UNCHANGED",
            "historical_shadow_mae": blend_val["aggregate"]["fixed_50_50_blend_mae"],
            "historical_canonical_mae": blend_val["aggregate"]["reference_mae"],
            "historical_bootstrap_ci_reference_minus_shadow": blend_val["aggregate"]["paired_bootstrap_reference_minus_blend"]["bootstrap_95_ci"],
            "recommendation": "HOLD",
            "release_state": "SHADOW_PROSPECTIVE_RESEARCH_ONLY",
            "canonical_model_superseded": False,
            "website_publish_allowed": False,
        })

    if len(output) != 13:
        raise RuntimeError(f"shadow output rows={len(output)}")

    manifest = {
        "shadow_snapshot_id": snapshot_id,
        "shadow_snapshot_created_at_utc": generated.isoformat(),
        "canonical_snapshot_id": canonical_manifest["snapshot_id"],
        "canonical_snapshot_immutable": True,
        "games": len(output),
        "completed_week6_games_excluded": completed_excluded,
        "training_seasons": [2022, 2023, 2024, 2025],
        "current_season_max_week_used": max_source_week,
        "ftn_current_max_week_used": 5,
        "blend_weight_canonical": 0.5,
        "blend_weight_ftn_qb_process": 0.5,
        "blend_weight_selected_from_outer_results": False,
        "candidate_params_selected_2022_only": cand,
        "rating_params": rating_params,
        "rating_stability_verdict": rating_spec.get("stability_verdict"),
        "historical_validation": {
            "canonical_mae": blend_val["aggregate"]["reference_mae"],
            "shadow_blend_mae": blend_val["aggregate"]["fixed_50_50_blend_mae"],
            "mae_improvement": blend_val["aggregate"]["paired_bootstrap_reference_minus_blend"]["mean_improvement"],
            "seasons_improved": blend_val["aggregate"]["seasons_improved"],
            "paired_bootstrap_95_ci": blend_val["aggregate"]["paired_bootstrap_reference_minus_blend"]["bootstrap_95_ci"],
            "probability_improvement_gt_zero": blend_val["aggregate"]["paired_bootstrap_reference_minus_blend"]["probability_gt_0"],
        },
        "matched_regularization_control": {
            "selected_no_ftn_lambda": control_val["selected_no_ftn_control_2022_only"]["lambda"],
            "no_ftn_control_mae": control_val["aggregate"]["tuned_no_ftn_control_mae"],
            "ftn_candidate_mae": control_val["aggregate"]["ftn_candidate_mae"],
        },
        "canonical_reconstruction_max_absolute_delta": round(max_reconstruction_delta, 8),
        "prospective_rule": "Freeze this file before Week 6 outcomes. Grade canonical and shadow separately after games. Do not choose between architectures using partial Week 6 outcomes.",
        "recommendation_release_allowed": False,
        "website_publish_allowed": False,
    }

    jpath = OUT_DIR / f"week6_ftn50_shadow_{stamp}.json"
    cpath = OUT_DIR / f"week6_ftn50_shadow_{stamp}.csv"
    jpath.write_text(json.dumps({"manifest": manifest, "rows": output}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with cpath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(output[0]))
        writer.writeheader(); writer.writerows(output)

    print(json.dumps({
        "shadow_snapshot_id": snapshot_id,
        "json": str(jpath),
        "csv": str(cpath),
        "games": len(output),
        "canonical_reconstruction_max_absolute_delta": round(max_reconstruction_delta, 8),
        "historical_canonical_mae": manifest["historical_validation"]["canonical_mae"],
        "historical_shadow_mae": manifest["historical_validation"]["shadow_blend_mae"],
        "website_publish_allowed": False,
    }, indent=2))


if __name__ == "__main__":
    main()
