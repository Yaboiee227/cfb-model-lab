#!/usr/bin/env python3
"""Walk-forward validation for the NFL opponent-adjusted efficiency layer.

Purpose
-------
Test whether leakage-safe, opponent-adjusted EPA ratings carry forward into
future NFL game margins and ATS decisions before the ratings are allowed into
any production model or website output.

Validation rules
----------------
* A target week's rating snapshot uses only prior regular-season weeks.
* Margin calibration for a game uses only validation rows earlier in time.
* Market spread is used only as an evaluation benchmark / edge threshold, not
  as an input to the independent efficiency rating.
* All outputs remain HOLD / RESEARCH_INPUT_ONLY.

The schedule spread in nflverse is a historical market field and may represent
a consensus/closing-style number rather than the exact timestamped executable
price needed for production validation. That limitation is recorded in QA.
"""

from __future__ import annotations

import csv
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SEASONS = [2022, 2023, 2024, 2025]
EVAL_SEASONS = [2023, 2024, 2025]
MIN_TARGET_WEEK = 4
MAX_TARGET_WEEK = 18
RECENCY_DECAY_PER_WEEK = 0.88
RIDGE_EQUIVALENT_PLAYS = 120.0
MAX_ITERATIONS = 500
CONVERGENCE_TOLERANCE = 1e-10
MIN_CALIBRATION_GAMES = 100
EDGE_THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 4.0]
OUT_DIR = Path("nfl_data/validation")
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"


def team_stats_url(season: int) -> str:
    return (
        "https://github.com/nflverse/nflverse-data/releases/download/"
        f"stats_team/stats_team_week_{season}.csv"
    )


def fetch_csv(url: str, timeout: int = 120) -> tuple[list[dict[str, str]], list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "cb-model-projections/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    return list(reader), list(reader.fieldnames or [])


def num(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def z(value: str | None) -> float:
    x = num(value)
    return 0.0 if x is None else x


def safe_div(a: float, b: float) -> float | None:
    return None if not b else a / b


def mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = mean(xs), mean(ys)
    if mx is None or my is None:
        return None
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return None if den == 0 else sum(a * b for a, b in zip(dx, dy)) / den


def ols_intercept_slope(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx, my = mean(xs), mean(ys)
    if mx is None or my is None:
        return None
    var = sum((x - mx) ** 2 for x in xs)
    if var <= 0:
        return None
    beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
    alpha = my - beta * mx
    return alpha, beta


def weighted_mean(items: list[tuple[float, float]]) -> float | None:
    den = sum(w for _, w in items)
    return None if den <= 0 else sum(v * w for v, w in items) / den


def build_snapshot(rows: list[dict[str, str]], season: int, target_week: int) -> dict[str, dict[str, float]]:
    cutoff = target_week - 1
    obs = []
    teams = set()

    for r in rows:
        if int(z(r.get("season"))) != season:
            continue
        if str(r.get("season_type", "")).upper().strip() != "REG":
            continue
        week = int(z(r.get("week")))
        if not 1 <= week <= cutoff:
            continue
        team = str(r.get("team", "")).strip()
        opp = str(r.get("opponent_team", "")).strip()
        if not team or not opp or team == opp:
            continue
        attempts = z(r.get("attempts"))
        sacks = z(r.get("sacks_suffered"))
        carries = z(r.get("carries"))
        plays = attempts + sacks + carries
        if plays <= 0:
            continue
        total_epa = z(r.get("passing_epa")) + z(r.get("rushing_epa"))
        epp = total_epa / plays
        recency = RECENCY_DECAY_PER_WEEK ** (cutoff - week)
        weight = plays * recency
        obs.append((team, opp, epp, weight))
        teams.update((team, opp))

    if len(teams) != 32 or not obs:
        return {}

    league_mean = weighted_mean([(epp, w) for _, _, epp, w in obs])
    if league_mean is None:
        return {}

    by_off = defaultdict(list)
    by_def = defaultdict(list)
    for team, opp, epp, w in obs:
        y = epp - league_mean
        by_off[team].append((opp, y, w))
        by_def[opp].append((team, y, w))

    off = {t: 0.0 for t in teams}
    deff = {t: 0.0 for t in teams}
    converged = False

    for _ in range(MAX_ITERATIONS):
        next_off = {}
        for t in teams:
            rows_t = by_off[t]
            den = RIDGE_EQUIVALENT_PLAYS + sum(w for _, _, w in rows_t)
            next_off[t] = sum(w * (y + deff[opp]) for opp, y, w in rows_t) / den if den else 0.0

        next_def = {}
        for t in teams:
            rows_t = by_def[t]
            den = RIDGE_EQUIVALENT_PLAYS + sum(w for _, _, w in rows_t)
            next_def[t] = sum(w * (next_off[o] - y) for o, y, w in rows_t) / den if den else 0.0

        delta = max(
            max(abs(next_off[t] - off[t]) for t in teams),
            max(abs(next_def[t] - deff[t]) for t in teams),
        )
        off, deff = next_off, next_def
        if delta <= CONVERGENCE_TOLERANCE:
            converged = True
            break

    if not converged:
        raise RuntimeError(f"Ratings failed to converge for {season} Week {target_week}")

    return {
        t: {
            "off": off[t],
            "def": deff[t],
            "net": off[t] + deff[t],
            "league_mean": league_mean,
        }
        for t in teams
    }


def settled_game(r: dict[str, str]) -> bool:
    hs = num(r.get("home_score"))
    aws = num(r.get("away_score"))
    return hs is not None and aws is not None


def ats_outcome(actual_margin: float, spread_line: float, pick_home: bool) -> str:
    # nflverse convention: positive spread_line means home team favored by that amount.
    delta = actual_margin - spread_line
    if abs(delta) < 1e-9:
        return "PUSH"
    home_covered = delta > 0
    won = home_covered if pick_home else not home_covered
    return "WIN" if won else "LOSS"


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    scored = [r for r in rows if r.get("model_margin") is not None]
    if not scored:
        return {"games": 0}

    actual = [float(r["actual_margin"]) for r in scored]
    model = [float(r["model_margin"]) for r in scored]
    market_rows = [r for r in scored if r.get("spread_line") is not None]

    summary: dict[str, object] = {
        "games": len(scored),
        "model_mae": sum(abs(a - p) for a, p in zip(actual, model)) / len(scored),
        "model_rmse": math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, model)) / len(scored)),
        "model_actual_correlation": correlation(model, actual),
    }

    if market_rows:
        summary["market_games"] = len(market_rows)
        summary["market_mae"] = sum(
            abs(float(r["actual_margin"]) - float(r["spread_line"])) for r in market_rows
        ) / len(market_rows)
        summary["market_actual_correlation"] = correlation(
            [float(r["spread_line"]) for r in market_rows],
            [float(r["actual_margin"]) for r in market_rows],
        )

        ats = {}
        for threshold in EDGE_THRESHOLDS:
            picks = [r for r in market_rows if abs(float(r["edge_points"])) >= threshold]
            wins = sum(r["ats_result"] == "WIN" for r in picks)
            losses = sum(r["ats_result"] == "LOSS" for r in picks)
            pushes = sum(r["ats_result"] == "PUSH" for r in picks)
            graded = wins + losses
            units = wins - 1.1 * losses
            ats[str(threshold)] = {
                "bets": len(picks),
                "wins": wins,
                "losses": losses,
                "pushes": pushes,
                "win_rate_ex_push": (wins / graded) if graded else None,
                "units_at_minus_110": units,
                "roi_at_minus_110": (units / graded) if graded else None,
            }
        summary["ats_by_edge_threshold"] = ats

    return summary


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    schedule, schedule_fields = fetch_csv(SCHEDULE_URL)
    required_schedule = {"season", "week", "game_type", "home_team", "away_team", "home_score", "away_score", "spread_line"}
    missing_schedule = sorted(required_schedule - set(schedule_fields))
    if missing_schedule:
        raise RuntimeError(f"Schedule source missing fields: {missing_schedule}")

    stats_by_season = {}
    source_fields = {}
    for season in SEASONS:
        rows, fields = fetch_csv(team_stats_url(season))
        required_stats = {
            "season", "week", "season_type", "team", "opponent_team",
            "attempts", "sacks_suffered", "passing_epa", "carries", "rushing_epa",
        }
        missing = sorted(required_stats - set(fields))
        if missing:
            raise RuntimeError(f"{season} team stats missing fields: {missing}")
        stats_by_season[season] = rows
        source_fields[season] = len(fields)

    # Build one leakage-safe rating snapshot for each historical target week.
    snapshots = {}
    for season in SEASONS:
        for week in range(MIN_TARGET_WEEK, MAX_TARGET_WEEK + 1):
            snap = build_snapshot(stats_by_season[season], season, week)
            if snap:
                snapshots[(season, week)] = snap

    candidates = []
    for r in schedule:
        season = int(z(r.get("season")))
        week = int(z(r.get("week")))
        if season not in EVAL_SEASONS:
            continue
        if str(r.get("game_type", "")).upper().strip() != "REG":
            continue
        if not MIN_TARGET_WEEK <= week <= MAX_TARGET_WEEK:
            continue
        if not settled_game(r):
            continue
        snap = snapshots.get((season, week))
        home = str(r.get("home_team", "")).strip()
        away = str(r.get("away_team", "")).strip()
        if not snap or home not in snap or away not in snap:
            continue

        hs = float(num(r.get("home_score")) or 0.0)
        aws = float(num(r.get("away_score")) or 0.0)
        actual_margin = hs - aws
        spread = num(r.get("spread_line"))
        total_line = num(r.get("total_line"))
        net_diff = snap[home]["net"] - snap[away]["net"]
        candidates.append({
            "season": season,
            "week": week,
            "gameday": str(r.get("gameday", "")),
            "game_id": str(r.get("game_id", "")),
            "home_team": home,
            "away_team": away,
            "home_net_rating": snap[home]["net"],
            "away_net_rating": snap[away]["net"],
            "net_rating_diff": net_diff,
            "actual_margin": actual_margin,
            "spread_line": spread,
            "total_line": total_line,
        })

    candidates.sort(key=lambda r: (int(r["season"]), int(r["week"]), str(r["gameday"]), str(r["game_id"])))

    validated = []
    for row in candidates:
        prior = [
            r for r in candidates
            if (int(r["season"]), int(r["week"])) < (int(row["season"]), int(row["week"]))
        ]
        if len(prior) < MIN_CALIBRATION_GAMES:
            continue
        fit = ols_intercept_slope(
            [float(r["net_rating_diff"]) for r in prior],
            [float(r["actual_margin"]) for r in prior],
        )
        if fit is None:
            continue
        alpha, beta = fit
        model_margin = alpha + beta * float(row["net_rating_diff"])
        spread = row.get("spread_line")
        edge = None if spread is None else model_margin - float(spread)
        pick_home = None if edge is None else edge > 0
        result = None
        if edge is not None and pick_home is not None:
            result = ats_outcome(float(row["actual_margin"]), float(spread), pick_home)

        out = dict(row)
        out.update({
            "calibration_games_before": len(prior),
            "calibration_intercept": alpha,
            "calibration_beta": beta,
            "model_margin": model_margin,
            "edge_points": edge,
            "pick_side": (str(row["home_team"]) if pick_home else str(row["away_team"])) if pick_home is not None else "",
            "ats_result": result,
            "release_state": "HOLD",
            "model_use": "RESEARCH_VALIDATION_ONLY",
        })
        validated.append(out)

    if not validated:
        raise RuntimeError("No walk-forward validation rows were produced")

    out_csv = OUT_DIR / "opponent_adjusted_walkforward_2023_2025.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(validated[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(validated)

    by_season = {}
    for season in EVAL_SEASONS:
        rows_s = [r for r in validated if int(r["season"]) == season]
        by_season[str(season)] = summarize(rows_s)

    qa = {
        "validation_name": "NFL opponent-adjusted EPA walk-forward v1",
        "source_seasons": SEASONS,
        "evaluation_seasons": EVAL_SEASONS,
        "target_weeks": [MIN_TARGET_WEEK, MAX_TARGET_WEEK],
        "snapshots_built": len(snapshots),
        "candidate_games": len(candidates),
        "validated_games": len(validated),
        "minimum_prior_calibration_games": MIN_CALIBRATION_GAMES,
        "parameters": {
            "recency_decay_per_week": RECENCY_DECAY_PER_WEEK,
            "ridge_equivalent_plays": RIDGE_EQUIVALENT_PLAYS,
            "edge_thresholds": EDGE_THRESHOLDS,
        },
        "overall": summarize(validated),
        "by_season": by_season,
        "release_state": "HOLD",
        "model_use": "RESEARCH_VALIDATION_ONLY",
        "market_line_limitation": (
            "nflverse spread_line is suitable for historical benchmark testing but is not treated as a guaranteed "
            "timestamped executable sportsbook price. Production release requires timestamped line/price capture and CLV QA."
        ),
        "notes": [
            "Every weekly rating snapshot uses only weeks before the target game week.",
            "Margin calibration for each game uses only earlier season/week validation rows.",
            "Market spread is excluded from rating construction and margin calibration; it is used only for benchmark/edge grading.",
            "ATS ROI assumes -110 pricing solely for a common-denominator research check; executable-price validation remains required.",
            "Totals, moneyline, alt lines, injuries, weather, rest/travel, QB changes, and personnel are not validated by this script.",
            "Passing this structural test does not authorize public release or website publication."
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    qa_path = OUT_DIR / "opponent_adjusted_walkforward_qa.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(qa, indent=2))
    print(f"Wrote {out_csv}")
    print(f"Wrote {qa_path}")


if __name__ == "__main__":
    main()
