#!/usr/bin/env python3
"""Leakage-safe CFB shadow projection engine.

This is NOT the unrecoverable 0.9J canonical generator. It is a transparent,
market-independent bridge/challenger used to keep Week 8 production moving while
we rebuild and validate a fully reproducible canonical engine.

Model:
  team score = intercept + offense(team) + defense_allowance(opponent)
               + learned_home_score_advantage (home, non-neutral only)

Team effects are ridge-shrunk toward zero. Hyperparameters are chosen on a
strict temporal holdout that ends before `--as-of`, then the model is refit on
all games completed before `--as-of`. No sportsbook, SP+, Sagarin, RefMetrics,
post-kickoff or future-game information enters the fit.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"

TEAM_ALIASES = {
    "middletennessee": "MTSU",
    "middletennesseestate": "MTSU",
    "fiu": "FIU",
    "floridainternational": "FIU",
    "missouristate": "MOST",
    "delaware": "DEL",
    "southalabama": "USA",
    "marshall": "MRSH",
}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timezone required: {value}")
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Game:
    game_id: str
    kickoff: datetime
    home: str
    away: str
    home_score: float
    away_score: float
    neutral: bool


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "CB-Model-Projections/1.0 research"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_completed_games(start: datetime, end: datetime) -> list[Game]:
    games: dict[str, Game] = {}
    day = start.date()
    while day <= end.date():
        params = urlencode({"dates": day.strftime("%Y%m%d"), "groups": "80", "limit": 1000})
        doc = fetch_json(f"{ESPN_SCOREBOARD}?{params}")
        for event in doc.get("events", []):
            comps = event.get("competitions") or []
            if not comps:
                continue
            comp = comps[0]
            status = (((comp.get("status") or {}).get("type") or {}).get("completed"))
            if not status:
                continue
            kickoff = parse_dt(comp.get("date") or event.get("date"))
            if kickoff >= end:
                continue
            sides: dict[str, dict[str, Any]] = {}
            for c in comp.get("competitors", []):
                sides[c.get("homeAway")] = c
            if "home" not in sides or "away" not in sides:
                continue
            h, a = sides["home"], sides["away"]
            try:
                hs, aas = float(h["score"]), float(a["score"])
            except (KeyError, TypeError, ValueError):
                continue
            home_code = str((h.get("team") or {}).get("abbreviation") or "").upper().strip()
            away_code = str((a.get("team") or {}).get("abbreviation") or "").upper().strip()
            if not home_code or not away_code:
                continue
            gid = str(event.get("id") or comp.get("id"))
            games[gid] = Game(gid, kickoff, home_code, away_code, hs, aas, bool(comp.get("neutralSite", False)))
        day += timedelta(days=1)
    return sorted(games.values(), key=lambda g: (g.kickoff, g.game_id))


def team_index(games: list[Game]) -> tuple[list[str], dict[str, int]]:
    teams = sorted({g.home for g in games} | {g.away for g in games})
    return teams, {team: i for i, team in enumerate(teams)}


def recency_weight(game_dt: datetime, as_of: datetime, half_life_days: int | None) -> float:
    if half_life_days is None:
        return 1.0
    age_days = max(0.0, (as_of - game_dt).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


def fit_model(games: list[Game], as_of: datetime, alpha: float, half_life_days: int | None):
    if len(games) < 20:
        raise ValueError("Not enough completed games to fit shadow model")
    teams, idx = team_index(games)
    n = len(teams)
    p = 2 + 2 * n  # intercept, home-score advantage, offense[n], defense-allowance[n]
    rows, y, weights = [], [], []

    for g in games:
        w = recency_weight(g.kickoff, as_of, half_life_days)
        # Home scoring row.
        xh = np.zeros(p)
        xh[0] = 1.0
        xh[1] = 0.0 if g.neutral else 1.0
        xh[2 + idx[g.home]] = 1.0
        xh[2 + n + idx[g.away]] = 1.0
        rows.append(xh); y.append(g.home_score); weights.append(w)
        # Away scoring row.
        xa = np.zeros(p)
        xa[0] = 1.0
        xa[2 + idx[g.away]] = 1.0
        xa[2 + n + idx[g.home]] = 1.0
        rows.append(xa); y.append(g.away_score); weights.append(w)

    X = np.vstack(rows)
    Y = np.asarray(y, dtype=float)
    W = np.sqrt(np.asarray(weights, dtype=float))
    Xw = X * W[:, None]
    Yw = Y * W

    penalty = np.eye(p) * float(alpha)
    penalty[0, 0] = 0.0   # do not shrink intercept
    penalty[1, 1] = 0.25 * float(alpha)  # lightly regularize learned HFA
    beta = np.linalg.solve(Xw.T @ Xw + penalty, Xw.T @ Yw)
    return {"teams": teams, "idx": idx, "beta": beta, "alpha": alpha, "halfLifeDays": half_life_days}


def predict(model, away: str, home: str, neutral: bool = False) -> dict[str, float]:
    idx, beta, teams = model["idx"], model["beta"], model["teams"]
    if away not in idx or home not in idx:
        missing = [t for t in (away, home) if t not in idx]
        raise ValueError("Team(s) absent from training data: " + ", ".join(missing))
    n = len(teams)
    home_pts = beta[0] + (0.0 if neutral else beta[1]) + beta[2 + idx[home]] + beta[2 + n + idx[away]]
    away_pts = beta[0] + beta[2 + idx[away]] + beta[2 + n + idx[home]]
    home_pts = max(0.0, float(home_pts)); away_pts = max(0.0, float(away_pts))
    return {
        "projectedAwayPoints": away_pts,
        "projectedHomePoints": home_pts,
        "projectedMarginHome": home_pts - away_pts,
        "projectedSpreadHome": -(home_pts - away_pts),
        "projectedTotal": home_pts + away_pts,
    }


def evaluate(model, games: list[Game]) -> dict[str, float | int | None]:
    margin_errors, total_errors, score_errors = [], [], []
    for g in games:
        if g.away not in model["idx"] or g.home not in model["idx"]:
            continue
        pr = predict(model, g.away, g.home, g.neutral)
        actual_margin = g.home_score - g.away_score
        actual_total = g.home_score + g.away_score
        margin_errors.append(pr["projectedMarginHome"] - actual_margin)
        total_errors.append(pr["projectedTotal"] - actual_total)
        score_errors.extend([pr["projectedHomePoints"] - g.home_score, pr["projectedAwayPoints"] - g.away_score])
    if not margin_errors:
        return {"games": 0, "marginMae": None, "totalMae": None, "scoreMae": None, "marginRmse": None}
    arr_m = np.asarray(margin_errors); arr_t = np.asarray(total_errors); arr_s = np.asarray(score_errors)
    return {
        "games": len(margin_errors),
        "marginMae": float(np.mean(np.abs(arr_m))),
        "totalMae": float(np.mean(np.abs(arr_t))),
        "scoreMae": float(np.mean(np.abs(arr_s))),
        "marginRmse": float(np.sqrt(np.mean(arr_m ** 2))),
        "marginResidualStd": float(np.std(arr_m, ddof=1)) if len(arr_m) > 1 else None,
    }


def tune(games: list[Game], as_of: datetime):
    split = as_of - timedelta(days=14)
    train = [g for g in games if g.kickoff < split]
    valid = [g for g in games if split <= g.kickoff < as_of]
    if len(train) < 100 or len(valid) < 20:
        # Fail-safe fixed conservative settings, explicitly surfaced in metadata.
        return 20.0, 35, {"mode": "FALLBACK_INSUFFICIENT_TEMPORAL_HOLDOUT", "trainGames": len(train), "validationGames": len(valid)}

    candidates = []
    for alpha in (5.0, 10.0, 20.0, 40.0):
        for half_life in (21, 35, 56, None):
            model = fit_model(train, split, alpha, half_life)
            ev = evaluate(model, valid)
            if not ev["games"]:
                continue
            objective = (float(ev["marginMae"]) + float(ev["totalMae"])) / 2.0
            candidates.append((objective, alpha, half_life, ev))
    if not candidates:
        return 20.0, 35, {"mode": "FALLBACK_NO_VALID_CANDIDATES"}
    candidates.sort(key=lambda x: (x[0], x[1], 999 if x[2] is None else x[2]))
    objective, alpha, half_life, ev = candidates[0]
    return alpha, half_life, {
        "mode": "PRE_WEEK8_TEMPORAL_HOLDOUT",
        "splitAt": iso(split),
        "trainGames": len(train),
        "validationGames": len(valid),
        "objective": objective,
        "selectedValidation": ev,
        "candidateCount": len(candidates),
    }


def matchup_code(name: str) -> str:
    n = norm(name)
    return TEAM_ALIASES.get(n, str(name).upper())


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def run(input_path: Path, output_path: Path, as_of: datetime, start: datetime):
    state = json.loads(input_path.read_text(encoding="utf-8"))
    training = fetch_completed_games(start, as_of)
    alpha, half_life, tuning = tune(training, as_of)
    model = fit_model(training, as_of, alpha, half_life)

    # Estimate uncertainty from the same temporal holdout when available; otherwise use
    # full-fit residual dispersion and label it provisional.
    split = as_of - timedelta(days=14)
    earlier = [g for g in training if g.kickoff < split]
    recent = [g for g in training if g.kickoff >= split]
    if len(earlier) >= 100 and len(recent) >= 20:
        holdout_model = fit_model(earlier, split, alpha, half_life)
        holdout_eval = evaluate(holdout_model, recent)
        sigma = holdout_eval.get("marginResidualStd") or 15.0
        sigma_source = "temporal_holdout_margin_residual_std"
    else:
        full_eval = evaluate(model, training)
        sigma = full_eval.get("marginResidualStd") or 15.0
        sigma_source = "in_sample_margin_residual_std_provisional"

    rows = []
    for game in state.get("games", []):
        away_code = matchup_code(game["awayTeam"])
        home_code = matchup_code(game["homeTeam"])
        try:
            pr = predict(model, away_code, home_code, neutral=False)
            z = pr["projectedMarginHome"] / max(float(sigma), 1e-6)
            pr["homeWinProbability"] = 100.0 * normal_cdf(z)
            pr["projectedWinner"] = game["homeTeam"] if pr["projectedMarginHome"] > 0 else game["awayTeam"]
            status = "SHADOW_READY"
            error = None
        except Exception as exc:
            pr = {"projectedAwayPoints": None, "projectedHomePoints": None, "projectedMarginHome": None, "projectedSpreadHome": None, "projectedTotal": None, "homeWinProbability": None, "projectedWinner": None}
            status = "SHADOW_REVIEW"
            error = str(exc)
        rows.append({
            "gameId": game["gameId"],
            "awayTeam": game["awayTeam"],
            "homeTeam": game["homeTeam"],
            "kickoff": game["kickoff"],
            "awayModelCode": away_code,
            "homeModelCode": home_code,
            "status": status,
            "error": error,
            **pr,
        })

    out = {
        "schemaVersion": 1,
        "league": "cfb",
        "season": state.get("season"),
        "week": state.get("week"),
        "modelId": "cfb-rebuild-alpha-shadow-v1",
        "role": "SHADOW_CHALLENGER_ONLY",
        "canonicalInfluence": False,
        "asOf": iso(as_of),
        "trainingWindowStart": iso(start),
        "trainingGames": len(training),
        "source": {
            "provider": "ESPN public college-football scoreboard",
            "marketDataUsed": False,
            "externalRatingsUsed": False,
            "postKickoffDataUsed": False,
        },
        "fit": {
            "description": "ridge-shrunk opponent-adjusted team scoring model with learned home scoring advantage",
            "selectedAlpha": alpha,
            "selectedHalfLifeDays": half_life,
            "learnedHomeScoreAdvantage": float(model["beta"][1]),
            "uncertaintyMarginSigma": float(sigma),
            "uncertaintySource": sigma_source,
            "tuning": tuning,
            "fullFitDiagnostics": evaluate(model, training),
        },
        "warning": "This output is not the unrecoverable 0.9J canonical model. It is a transparent shadow bridge and must not replace canonical/frozen projections without explicit validation and promotion.",
        "games": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="cfb/pregame/week-08-tuesday-open.json")
    ap.add_argument("--output", default="cfb/shadow/week-08-tuesday.json")
    ap.add_argument("--as-of", default="2026-10-20T00:00:00-04:00", help="Only completed games strictly before this timestamp are eligible")
    ap.add_argument("--start", default="2026-08-20T00:00:00-04:00")
    args = ap.parse_args()
    try:
        out = run(Path(args.input), Path(args.output), parse_dt(args.as_of), parse_dt(args.start))
        print(json.dumps({"modelId": out["modelId"], "trainingGames": out["trainingGames"], "games": len(out["games"])}, indent=2))
    except Exception as exc:
        print(f"CFB_SHADOW_ENGINE_ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
