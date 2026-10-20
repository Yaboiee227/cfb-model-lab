#!/usr/bin/env python3
"""Leakage-safe CFB box-score efficiency challenger.

This challenger is intentionally separate from the canonical model and from the
simpler scoring shadow. It uses only pregame information and freezes feature
states at the start of each Monday-Sunday football week so a Tuesday result can
never help predict a Saturday game in the same week.

Feature families:
- opponent-adjusted scoring margin/total baseline
- opponent-adjusted yards/play
- pass yards/attempt
- rush yards/attempt
- third-down conversion rate
- turnover rate per play
- first-down rate per play
- penalty yards per play
- play volume
- possession share
- recent scoring-margin form
- rest differential

No market, SP+, Sagarin, RefMetrics, future result, or current-game box score is
used to create a pregame feature vector.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import numpy as np

import cfb_shadow_engine as engine
from run_cfb_shadow_week8 import extract_grouped_team_ids

engine.extract_team_ids = extract_grouped_team_ids

SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={}"
BOX_METRICS = (
    "yardsPerPlay",
    "passYpa",
    "rushYpa",
    "thirdRate",
    "turnoverRate",
    "firstDownRate",
    "penaltyYardsPerPlay",
    "plays",
    "possessionShare",
)
FEATURE_NAMES = (
    "scoreBaseMargin",
    "scoreBaseTotal",
    "yppMatchupDiff",
    "passYpaMatchupDiff",
    "rushYpaMatchupDiff",
    "thirdDownMatchupDiff",
    "turnoverControlDiff",
    "firstDownRateMatchupDiff",
    "penaltyDisciplineDiff",
    "combinedPlayVolume",
    "possessionMatchupDiff",
    "recentMarginDiff",
    "restDaysDiff",
)
MARGIN_BUNDLES = {
    "scoring": (0,),
    "core_efficiency": (0, 2, 3, 4, 5, 6),
    "full_efficiency": (0, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12),
}
TOTAL_BUNDLES = {
    "scoring": (1,),
    "core_efficiency": (1, 2, 3, 4, 5, 6, 9),
    "full_efficiency": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
}
RIDGES = (0.1, 1.0, 10.0, 100.0)
MIN_PRIOR_GAMES = 2
MIN_SUMMARY_COVERAGE = 0.90


def parse_dt(value: str) -> datetime:
    return engine.parse_dt(value)


def week_start(dt: datetime) -> datetime:
    dt = dt.astimezone(timezone.utc)
    day = dt.date() - timedelta(days=dt.weekday())
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def numeric(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value", value.get("displayValue"))
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def pair(value: Any, separator: str) -> tuple[float | None, float | None]:
    try:
        left, right = str(value).split(separator, 1)
    except (ValueError, TypeError):
        return None, None
    return numeric(left), numeric(right)


def possession_minutes(value: Any) -> float | None:
    try:
        minutes, seconds = str(value).split(":", 1)
        return float(minutes) + float(seconds) / 60.0
    except (ValueError, TypeError):
        return None


def normalized_box(statistics: list[dict[str, Any]]) -> dict[str, float | None]:
    values = {row.get("name"): row.get("displayValue", row.get("value")) for row in statistics}
    _completions, pass_attempts = pair(values.get("completionAttempts"), "/")
    third_made, third_attempts = pair(values.get("thirdDownEff"), "-")
    _fourth_made, _fourth_attempts = pair(values.get("fourthDownEff"), "-")
    _penalties, penalty_yards = pair(values.get("totalPenaltiesYards"), "-")
    rush_attempts = numeric(values.get("rushingAttempts"))
    total_yards = numeric(values.get("totalYards"))
    pass_yards = numeric(values.get("netPassingYards"))
    rush_yards = numeric(values.get("rushingYards"))
    turnovers = numeric(values.get("turnovers"))
    first_downs = numeric(values.get("firstDowns"))
    poss = possession_minutes(values.get("possessionTime"))
    plays = None if pass_attempts is None or rush_attempts is None else pass_attempts + rush_attempts
    return {
        "plays": plays,
        "yardsPerPlay": None if not plays or total_yards is None else total_yards / plays,
        "passYpa": None if not pass_attempts or pass_yards is None else pass_yards / pass_attempts,
        "rushYpa": None if not rush_attempts or rush_yards is None else rush_yards / rush_attempts,
        "thirdRate": None if not third_attempts or third_made is None else third_made / third_attempts,
        "turnoverRate": None if not plays or turnovers is None else turnovers / plays,
        "firstDownRate": None if not plays or first_downs is None else first_downs / plays,
        "penaltyYardsPerPlay": None if not plays or penalty_yards is None else penalty_yards / plays,
        "possessionShare": None if poss is None else poss / 60.0,
    }


def fetch_json(url: str, attempts: int = 3, timeout: int = 30) -> dict[str, Any]:
    error = None
    for attempt in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": "CB-Model-Projections/1.0 research"})
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (attempt + 1))
    raise error


def fetch_box_for_game(game: engine.Game) -> tuple[str, dict[str, dict[str, float | None]] | None, str | None]:
    try:
        doc = fetch_json(SUMMARY_URL.format(game.game_id))
        rows = (doc.get("boxscore") or {}).get("teams") or []
        box: dict[str, dict[str, float | None]] = {}
        for row in rows:
            team = row.get("team") or {}
            try:
                key = engine.team_key(team)
            except Exception:
                continue
            box[key] = normalized_box(row.get("statistics") or [])
        if game.home not in box or game.away not in box:
            return game.game_id, None, "missing home/away box rows"
        return game.game_id, box, None
    except Exception as exc:
        return game.game_id, None, str(exc)


def fetch_boxes(games: list[engine.Game]) -> tuple[dict[str, dict[str, dict[str, float | None]]], list[dict[str, str]]]:
    boxes: dict[str, dict[str, dict[str, float | None]]] = {}
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        jobs = {pool.submit(fetch_box_for_game, g): g.game_id for g in games}
        for future in as_completed(jobs):
            gid, box, error = future.result()
            if box is not None:
                boxes[gid] = box
            else:
                failures.append({"gameId": gid, "error": error or "unknown"})
    return boxes, failures


def metric_pair_fit(
    history: list[engine.Game],
    boxes: dict[str, dict[str, dict[str, float | None]]],
    metric: str,
    alpha: float = 10.0,
) -> dict[str, tuple[float, float]]:
    """Fit offense and opponent-defense allowance for one box metric."""
    usable = []
    teams = set()
    for g in history:
        box = boxes.get(g.game_id)
        if not box:
            continue
        hv = box.get(g.home, {}).get(metric)
        av = box.get(g.away, {}).get(metric)
        if hv is None or av is None:
            continue
        usable.append((g, float(hv), float(av)))
        teams.update((g.home, g.away))
    if len(usable) < 30 or len(teams) < 20:
        return {}
    names = sorted(teams)
    idx = {t: i for i, t in enumerate(names)}
    n = len(names)
    X = []
    y = []
    for g, hv, av in usable:
        xh = np.zeros(1 + 2 * n)
        xh[0] = 1.0
        xh[1 + idx[g.home]] = 1.0
        xh[1 + n + idx[g.away]] = 1.0
        X.append(xh); y.append(hv)
        xa = np.zeros(1 + 2 * n)
        xa[0] = 1.0
        xa[1 + idx[g.away]] = 1.0
        xa[1 + n + idx[g.home]] = 1.0
        X.append(xa); y.append(av)
    X = np.vstack(X)
    y = np.asarray(y, dtype=float)
    penalty = np.full(X.shape[1], float(alpha))
    penalty[0] = 0.0
    beta = np.linalg.solve(X.T @ X + np.diag(penalty), X.T @ y)
    intercept = float(beta[0])
    return {
        team: (intercept + float(beta[1 + idx[team]]), float(beta[1 + n + idx[team]]))
        for team in names
    }


def expected_metric(ratings: dict[str, tuple[float, float]], offense: str, defense: str) -> float | None:
    if offense not in ratings or defense not in ratings:
        return None
    # Each tuple already includes the intercept in the offense value. Subtract
    # one baseline intercept proxy by centering defense allowance around its mean.
    offense_level = ratings[offense][0]
    defense_allowance = ratings[defense][1]
    defense_center = float(np.mean([v[1] for v in ratings.values()]))
    return offense_level + (defense_allowance - defense_center)


@dataclass
class TeamGameObs:
    date: datetime
    margin: float


def recent_form(history: list[TeamGameObs], n: int = 3) -> float:
    if not history:
        return 0.0
    rows = history[-n:]
    return float(np.mean([r.margin for r in rows]))


def rest_days(history: list[TeamGameObs], kickoff: datetime) -> float:
    if not history:
        return 7.0
    days = (kickoff - history[-1].date).total_seconds() / 86400.0
    return max(3.0, min(21.0, days))


def build_snapshot(
    history: list[engine.Game],
    boxes: dict[str, dict[str, dict[str, float | None]]],
    as_of: datetime,
    structural_hfa: float,
) -> dict[str, Any]:
    if len(history) < 80:
        return {"score": None, "metrics": {}}
    try:
        score = engine.fit_model(
            history,
            as_of,
            alpha=5.0,
            half_life_days=21,
            min_team_appearances=3,
            fixed_hfa=structural_hfa,
        )
    except Exception:
        score = None
    ratings = {metric: metric_pair_fit(history, boxes, metric, alpha=10.0) for metric in BOX_METRICS}
    return {"score": score, "metrics": ratings}


def feature_vector(
    game: engine.Game,
    snapshot: dict[str, Any],
    team_history: dict[str, list[TeamGameObs]],
) -> list[float] | None:
    score = snapshot.get("score")
    if not score or game.home not in score["idx"] or game.away not in score["idx"]:
        return None
    if len(team_history[game.home]) < MIN_PRIOR_GAMES or len(team_history[game.away]) < MIN_PRIOR_GAMES:
        return None
    base = engine.predict(score, game.away, game.home, game.neutral)
    metrics = snapshot.get("metrics") or {}

    def diff(metric: str, lower_is_better: bool = False) -> float | None:
        rating = metrics.get(metric) or {}
        home = expected_metric(rating, game.home, game.away)
        away = expected_metric(rating, game.away, game.home)
        if home is None or away is None:
            return None
        value = home - away
        return -value if lower_is_better else value

    ypp = diff("yardsPerPlay")
    pass_y = diff("passYpa")
    rush_y = diff("rushYpa")
    third = diff("thirdRate")
    turnover = diff("turnoverRate", lower_is_better=True)
    first = diff("firstDownRate")
    penalty = diff("penaltyYardsPerPlay", lower_is_better=True)
    possession = diff("possessionShare")

    play_ratings = metrics.get("plays") or {}
    hp = expected_metric(play_ratings, game.home, game.away)
    ap = expected_metric(play_ratings, game.away, game.home)
    combined_plays = None if hp is None or ap is None else hp + ap

    values = [
        base["projectedMarginHome"],
        base["projectedTotal"],
        ypp,
        pass_y,
        rush_y,
        third,
        turnover,
        first,
        penalty,
        combined_plays,
        possession,
        recent_form(team_history[game.home]) - recent_form(team_history[game.away]),
        rest_days(team_history[game.home], game.kickoff) - rest_days(team_history[game.away], game.kickoff),
    ]
    if any(v is None or not math.isfinite(float(v)) for v in values):
        return None
    return [float(v) for v in values]


def update_histories(game: engine.Game, team_history: dict[str, list[TeamGameObs]]) -> None:
    margin = game.home_score - game.away_score
    team_history[game.home].append(TeamGameObs(game.kickoff, margin))
    team_history[game.away].append(TeamGameObs(game.kickoff, -margin))


def build_rows(
    games: list[engine.Game],
    boxes: dict[str, dict[str, dict[str, float | None]]],
    structural_hfa: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, list[TeamGameObs]]]:
    by_week: dict[datetime, list[engine.Game]] = defaultdict(list)
    for g in games:
        by_week[week_start(g.kickoff)].append(g)

    history: list[engine.Game] = []
    team_history: dict[str, list[TeamGameObs]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    final_snapshot: dict[str, Any] = {"score": None, "metrics": {}}

    for start in sorted(by_week):
        batch = sorted(by_week[start], key=lambda g: (g.kickoff, g.game_id))
        snapshot = build_snapshot(history, boxes, start, structural_hfa)
        final_snapshot = snapshot
        for g in batch:
            x = feature_vector(g, snapshot, team_history)
            if x is not None:
                rows.append({
                    "gameId": g.game_id,
                    "kickoff": engine.iso(g.kickoff),
                    "weekStart": engine.iso(start),
                    "home": g.home,
                    "away": g.away,
                    "x": x,
                    "margin": g.home_score - g.away_score,
                    "total": g.home_score + g.away_score,
                })
        # Freeze all features for the week before allowing any same-week outcome
        # into future state.
        for g in batch:
            history.append(g)
            update_histories(g, team_history)

    # Week 8 target snapshot uses every completed game from prior weeks.
    target_start = max(by_week) + timedelta(days=7) if by_week else datetime.now(timezone.utc)
    final_snapshot = build_snapshot(history, boxes, target_start, structural_hfa)
    return rows, final_snapshot, team_history


def ridge_fit(rows: list[dict[str, Any]], indices: tuple[int, ...], target: str, alpha: float) -> dict[str, Any]:
    X = np.asarray([[r["x"][i] for i in indices] for r in rows], dtype=float)
    y = np.asarray([r[target] for r in rows], dtype=float)
    mean = X.mean(axis=0)
    scale = X.std(axis=0)
    scale = np.where(scale < 1e-6, 1.0, scale)
    Z = (X - mean) / scale
    design = np.column_stack([np.ones(len(Z)), Z])
    penalty = np.eye(design.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {"indices": list(indices), "mean": mean, "scale": scale, "beta": beta, "alpha": alpha}


def ridge_predict(model: dict[str, Any], rows: list[dict[str, Any]]) -> np.ndarray:
    indices = model["indices"]
    X = np.asarray([[r["x"][i] for i in indices] for r in rows], dtype=float)
    Z = (X - model["mean"]) / model["scale"]
    return np.column_stack([np.ones(len(Z)), Z]) @ model["beta"]


def metrics(pred: np.ndarray, actual: np.ndarray) -> dict[str, float | int]:
    err = pred - actual
    return {
        "games": int(len(actual)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "residualStd": float(np.std(err, ddof=1)) if len(err) > 1 else 15.0,
    }


def choose_model(train: list[dict[str, Any]], valid: list[dict[str, Any]], target: str, bundles: dict[str, tuple[int, ...]]):
    candidates = []
    y = np.asarray([r[target] for r in valid], dtype=float)
    for name, indices in bundles.items():
        for alpha in RIDGES:
            model = ridge_fit(train, indices, target, alpha)
            pred = ridge_predict(model, valid)
            candidates.append({
                "name": name,
                "alpha": alpha,
                "indices": list(indices),
                "validation": metrics(pred, y),
                "model": model,
            })
    candidates.sort(key=lambda row: (row["validation"]["mae"], len(row["indices"]), row["alpha"]))
    return candidates[0], candidates


def serialize_model(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "indices": model["indices"],
        "mean": [float(x) for x in model["mean"]],
        "scale": [float(x) for x in model["scale"]],
        "beta": [float(x) for x in model["beta"]],
        "alpha": model["alpha"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="cfb/pregame/week-08-tuesday-effective.json")
    ap.add_argument("--shadow", default="cfb/shadow/week-08-tuesday.json")
    ap.add_argument("--output", default="cfb/shadow/week-08-tuesday-rich.json")
    ap.add_argument("--as-of", default="2026-10-20T00:00:00-04:00")
    ap.add_argument("--start", default="2026-08-20T00:00:00-04:00")
    args = ap.parse_args()

    as_of = parse_dt(args.as_of)
    start = parse_dt(args.start)
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    shadow = json.loads(Path(args.shadow).read_text(encoding="utf-8"))
    structural_hfa = float(shadow["fit"]["structuralHomeMarginAdvantage"])

    games = engine.fetch_completed_games(start, as_of)
    boxes, failures = fetch_boxes(games)
    coverage = len(boxes) / max(1, len(games))
    if coverage < MIN_SUMMARY_COVERAGE:
        raise RuntimeError(f"ESPN box-score coverage {coverage:.3f} below required {MIN_SUMMARY_COVERAGE:.2f}; failures={failures[:5]}")

    rows, target_snapshot, team_history = build_rows(games, boxes, structural_hfa)
    split = parse_dt("2026-10-06T04:00:00Z")
    train = [r for r in rows if parse_dt(r["kickoff"]) < split]
    valid = [r for r in rows if split <= parse_dt(r["kickoff"]) < as_of]
    if len(train) < 100 or len(valid) < 50:
        raise RuntimeError(f"insufficient causal rich-model rows train={len(train)} valid={len(valid)}")

    best_margin, margin_candidates = choose_model(train, valid, "margin", MARGIN_BUNDLES)
    best_total, total_candidates = choose_model(train, valid, "total", TOTAL_BUNDLES)

    # Refit chosen structures on every causal row available before Week 8.
    margin_final = ridge_fit(rows, tuple(best_margin["indices"]), "margin", float(best_margin["alpha"]))
    total_final = ridge_fit(rows, tuple(best_total["indices"]), "total", float(best_total["alpha"]))

    simple_validation = (shadow.get("fit") or {}).get("tuning", {}).get("selectedValidation") or {}
    simple_margin_mae = simple_validation.get("marginMae")
    simple_total_mae = simple_validation.get("totalMae")
    rich_margin_mae = best_margin["validation"]["mae"]
    rich_total_mae = best_total["validation"]["mae"]
    comparison_pass = (
        simple_margin_mae is not None and simple_total_mae is not None
        and rich_margin_mae <= float(simple_margin_mae) + 0.25
        and rich_total_mae <= float(simple_total_mae) + 0.25
        and (rich_margin_mae <= float(simple_margin_mae) - 0.50 or rich_total_mae <= float(simple_total_mae) - 0.50)
    )

    target_rows = []
    state_games = {g["gameId"]: g for g in state.get("games", [])}
    for gid, game_state in state_games.items():
        target = engine.Game(
            gid,
            parse_dt(game_state["kickoff"]),
            engine.canonical_school(game_state["homeTeam"]),
            engine.canonical_school(game_state["awayTeam"]),
            0.0,
            0.0,
            False,
        )
        x = feature_vector(target, target_snapshot, team_history)
        if x is None:
            target_rows.append({"gameId": gid, "status": "RICH_REVIEW", "error": "target feature vector unavailable"})
            continue
        synthetic = {"x": x}
        margin = float(ridge_predict(margin_final, [synthetic])[0])
        total = max(0.0, float(ridge_predict(total_final, [synthetic])[0]))
        home_points = max(0.0, (total + margin) / 2.0)
        away_points = max(0.0, (total - margin) / 2.0)
        margin = home_points - away_points
        total = home_points + away_points
        sigma = float(best_margin["validation"]["residualStd"])
        hwp = 100.0 * 0.5 * (1.0 + math.erf((margin / max(sigma, 1e-6)) / math.sqrt(2.0)))
        target_rows.append({
            "gameId": gid,
            "awayTeam": game_state["awayTeam"],
            "homeTeam": game_state["homeTeam"],
            "status": "RICH_CHALLENGER_READY" if comparison_pass else "RICH_RESEARCH_ONLY",
            "projectedAwayPoints": away_points,
            "projectedHomePoints": home_points,
            "projectedMarginHome": margin,
            "projectedSpreadHome": -margin,
            "projectedTotal": total,
            "homeWinProbability": hwp,
            "projectedWinner": game_state["homeTeam"] if margin > 0 else game_state["awayTeam"],
            "features": {name: value for name, value in zip(FEATURE_NAMES, x)},
        })

    out = {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "week": 8,
        "modelId": "cfb-boxscore-efficiency-challenger-v1",
        "role": "SHADOW_CHALLENGER_ONLY",
        "canonicalInfluence": False,
        "asOf": engine.iso(as_of),
        "source": {
            "schedule": "ESPN public FBS team schedules",
            "boxscores": "ESPN public college-football summary endpoint",
            "marketDataUsed": False,
            "externalRatingsUsed": False,
            "postKickoffTargetDataUsed": False,
            "sameWeekResultLeakage": False,
        },
        "dataQuality": {
            "trainingGames": len(games),
            "boxscoreGames": len(boxes),
            "boxscoreCoverage": coverage,
            "boxscoreFailures": failures[:20],
            "causalRows": len(rows),
            "trainRows": len(train),
            "validationRows": len(valid),
        },
        "features": list(FEATURE_NAMES),
        "validation": {
            "splitAt": engine.iso(split),
            "marginSelected": {
                "bundle": best_margin["name"],
                "alpha": best_margin["alpha"],
                **best_margin["validation"],
            },
            "totalSelected": {
                "bundle": best_total["name"],
                "alpha": best_total["alpha"],
                **best_total["validation"],
            },
            "simpleShadowReference": {
                "marginMae": simple_margin_mae,
                "totalMae": simple_total_mae,
            },
            "comparisonGatePass": comparison_pass,
            "rule": "Rich challenger must improve at least one MAE by >=0.50 while degrading neither margin nor total MAE by more than 0.25 versus the simple shadow reference. Passing this gate does not promote it to canonical; prospective evidence is still required.",
        },
        "selectedModels": {
            "margin": serialize_model(margin_final),
            "total": serialize_model(total_final),
        },
        "candidateResults": {
            "margin": [{"bundle": c["name"], "alpha": c["alpha"], **c["validation"]} for c in margin_candidates],
            "total": [{"bundle": c["name"], "alpha": c["alpha"], **c["validation"]} for c in total_candidates],
        },
        "games": target_rows,
        "warning": "Research challenger only. Even a validation-gate pass does not authorize canonical use during Week 8 without explicit promotion and prospective evidence."
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "modelId": out["modelId"],
        "coverage": coverage,
        "rows": len(rows),
        "validation": out["validation"],
        "games": [{"gameId": g.get("gameId"), "status": g.get("status"), "spread": g.get("projectedSpreadHome"), "total": g.get("projectedTotal")} for g in target_rows],
    }, indent=2))


if __name__ == "__main__":
    main()
