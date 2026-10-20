#!/usr/bin/env python3
"""Leakage-safe CFB shadow projection engine.

This is NOT the unrecoverable 0.9J canonical generator. It is a transparent,
market-independent bridge/challenger used while a fully reproducible canonical
engine is rebuilt and validated.

Shadow v8:
  projected margin = frozen structural HFA + strength(home) - strength(away)
  projected total  = scoring baseline + scoring_env(home) + scoring_env(away)

The structural home-field parameter is estimated only from the pre-Week-8
training window used in temporal validation, then frozen while team strengths
and scoring-environment effects are refreshed using all games completed before
`--as-of`.

ESPN team identity uses normalized school/location names rather than volatile
abbreviations. FBS team discovery uses ESPN's conference-filtered web teams
endpoint because the ordinary site `/teams?groups=80` endpoint does not reliably
honor the FBS filter. Individual schedules still come from the site API, are
deduplicated by event ID, and are strictly filtered by kickoff timestamp.

No sportsbook, SP+, Sagarin, RefMetrics, post-kickoff or future-game information
enters the fit.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
ESPN_SITE_TEAMS = f"{ESPN_SITE_BASE}/teams"
ESPN_FBS_TEAMS = "https://site.web.api.espn.com/apis/site/v2/sports/football/college-football/teams"
HFA_SANITY_RANGE = (0.0, 5.5)
DEFAULT_MIN_TEAM_APPEARANCES = 3
MIN_EXPECTED_FBS_TEAMS = 120
MIN_EXPECTED_TRAINING_GAMES = 300

TEAM_ALIASES = {
    "middletennesseestate": "middletennessee",
    "middletennessee": "middletennessee",
    "fiu": "floridainternational",
    "floridainternational": "floridainternational",
    "missouristate": "missouristate",
    "delaware": "delaware",
    "southalabama": "southalabama",
    "marshall": "marshall",
}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def canonical_school(value: str) -> str:
    key = norm(value)
    return TEAM_ALIASES.get(key, key)


def team_key(team: dict[str, Any]) -> str:
    for field in ("location", "shortDisplayName", "displayName", "name"):
        value = team.get(field)
        if value:
            key = canonical_school(str(value))
            if key:
                return key
    raise ValueError(f"ESPN team object has no usable school name: id={team.get('id')}")


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


def extract_team_ids(doc: dict[str, Any]) -> list[str]:
    ids: set[str] = set()
    for sport in doc.get("sports", []):
        for league in sport.get("leagues", []):
            for entry in league.get("teams", []):
                team = entry.get("team") or entry
                if team.get("id") is not None:
                    ids.add(str(team["id"]))
    for entry in doc.get("teams", []):
        team = entry.get("team") or entry
        if team.get("id") is not None:
            ids.add(str(team["id"]))
    return sorted(ids, key=lambda x: (len(x), x))


def _score_value(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("value", value.get("displayValue"))
    return float(value)


def _ingest_events(doc: dict[str, Any], games: dict[str, Game], start: datetime, end: datetime) -> None:
    for event in doc.get("events", []):
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        completed = (((comp.get("status") or {}).get("type") or {}).get("completed"))
        if not completed:
            continue
        try:
            kickoff = parse_dt(comp.get("date") or event.get("date"))
        except Exception:
            continue
        if kickoff < start or kickoff >= end:
            continue
        sides: dict[str, dict[str, Any]] = {}
        for c in comp.get("competitors", []):
            sides[c.get("homeAway")] = c
        if "home" not in sides or "away" not in sides:
            continue
        h, a = sides["home"], sides["away"]
        try:
            hs, aas = _score_value(h["score"]), _score_value(a["score"])
            home_code = team_key(h.get("team") or {})
            away_code = team_key(a.get("team") or {})
        except (KeyError, TypeError, ValueError):
            continue
        if not home_code or not away_code or home_code == away_code:
            continue
        gid = str(event.get("id") or comp.get("id") or "")
        if not gid:
            continue
        games[gid] = Game(gid, kickoff, home_code, away_code, hs, aas, bool(comp.get("neutralSite", False)))


def fetch_completed_games(start: datetime, end: datetime) -> list[Game]:
    team_params = urlencode({"groups": 80, "groupType": "conference", "enable": "groups"})
    team_doc = fetch_json(f"{ESPN_FBS_TEAMS}?{team_params}")
    team_ids = extract_team_ids(team_doc)
    if len(team_ids) < MIN_EXPECTED_FBS_TEAMS:
        raise ValueError(f"ESPN FBS team discovery incomplete: {len(team_ids)} teams < {MIN_EXPECTED_FBS_TEAMS}")
    if len(team_ids) > 180:
        raise ValueError(f"ESPN FBS team discovery implausibly broad: {len(team_ids)} teams > 180")

    games: dict[str, Game] = {}
    failures: list[str] = []

    def load_schedule(team_id: str, season: int) -> tuple[str, int, dict[str, Any]]:
        params = urlencode({"season": season, "seasontype": 2})
        return team_id, season, fetch_json(f"{ESPN_SITE_TEAMS}/{team_id}/schedule?{params}")

    futures = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        for season in range(start.year, end.year + 1):
            for team_id in team_ids:
                futures.append(pool.submit(load_schedule, team_id, season))
        for future in as_completed(futures):
            try:
                _team_id, _season, doc = future.result()
                _ingest_events(doc, games, start, end)
            except Exception as exc:
                failures.append(str(exc))

    ordered = sorted(games.values(), key=lambda g: (g.kickoff, g.game_id))
    if len(ordered) < MIN_EXPECTED_TRAINING_GAMES:
        raise ValueError(
            f"ESPN FBS schedule aggregation incomplete: {len(ordered)} pre-cutoff finals < "
            f"{MIN_EXPECTED_TRAINING_GAMES}; discoveredTeams={len(team_ids)} scheduleFailures={len(failures)}"
        )
    return ordered


def appearance_counts(games: list[Game]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for g in games:
        counts[g.home] += 1
        counts[g.away] += 1
    return counts


def filter_core_games(games: list[Game], min_team_appearances: int = DEFAULT_MIN_TEAM_APPEARANCES) -> list[Game]:
    counts = appearance_counts(games)
    return [g for g in games if counts[g.home] >= min_team_appearances and counts[g.away] >= min_team_appearances]


def team_index(games: list[Game]) -> tuple[list[str], dict[str, int]]:
    teams = sorted({g.home for g in games} | {g.away for g in games})
    return teams, {team: i for i, team in enumerate(teams)}


def recency_weight(game_dt: datetime, as_of: datetime, half_life_days: int | None) -> float:
    if half_life_days is None:
        return 1.0
    age_days = max(0.0, (as_of - game_dt).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


def _ridge_solve(X: np.ndarray, y: np.ndarray, weights: np.ndarray, penalty_diag: np.ndarray) -> np.ndarray:
    W = np.sqrt(weights)
    Xw = X * W[:, None]
    yw = y * W
    return np.linalg.solve(Xw.T @ Xw + np.diag(penalty_diag), Xw.T @ yw)


def fit_model(
    games: list[Game],
    as_of: datetime,
    alpha: float,
    half_life_days: int | None,
    min_team_appearances: int = DEFAULT_MIN_TEAM_APPEARANCES,
    fixed_hfa: float | None = None,
):
    core = filter_core_games(games, min_team_appearances)
    if len(core) < 20:
        raise ValueError("Not enough eligible completed games to fit shadow model")

    teams, idx = team_index(core)
    n = len(teams)
    weights = np.asarray([recency_weight(g.kickoff, as_of, half_life_days) for g in core], dtype=float)

    if fixed_hfa is None:
        X_margin = np.zeros((len(core), 1 + n))
        y_margin = np.zeros(len(core))
        for r, g in enumerate(core):
            X_margin[r, 0] = 0.0 if g.neutral else 1.0
            X_margin[r, 1 + idx[g.home]] = 1.0
            X_margin[r, 1 + idx[g.away]] = -1.0
            y_margin[r] = g.home_score - g.away_score
        margin_penalty = np.full(1 + n, float(alpha))
        beta_margin = _ridge_solve(X_margin, y_margin, weights, margin_penalty)
        hfa = float(beta_margin[0])
        strength = beta_margin[1:]
    else:
        X_margin = np.zeros((len(core), n))
        y_margin = np.zeros(len(core))
        for r, g in enumerate(core):
            X_margin[r, idx[g.home]] = 1.0
            X_margin[r, idx[g.away]] = -1.0
            y_margin[r] = (g.home_score - g.away_score) - (0.0 if g.neutral else float(fixed_hfa))
        strength = _ridge_solve(X_margin, y_margin, weights, np.full(n, float(alpha)))
        hfa = float(fixed_hfa)

    X_total = np.zeros((len(core), 1 + n))
    y_total = np.zeros(len(core))
    for r, g in enumerate(core):
        X_total[r, 0] = 1.0
        X_total[r, 1 + idx[g.home]] = 1.0
        X_total[r, 1 + idx[g.away]] = 1.0
        y_total[r] = g.home_score + g.away_score
    total_penalty = np.full(1 + n, float(alpha))
    total_penalty[0] = 0.0
    beta_total = _ridge_solve(X_total, y_total, weights, total_penalty)

    return {
        "teams": teams,
        "idx": idx,
        "strength": strength,
        "betaTotal": beta_total,
        "homeMarginAdvantage": hfa,
        "homeFieldMode": "FIXED_STRUCTURAL" if fixed_hfa is not None else "LEARNED_IN_WINDOW",
        "alpha": alpha,
        "halfLifeDays": half_life_days,
        "minTeamAppearances": min_team_appearances,
        "eligibleTrainingGames": len(core),
        "rawTrainingGames": len(games),
    }


def predict(model, away: str, home: str, neutral: bool = False) -> dict[str, float]:
    idx = model["idx"]
    if away not in idx or home not in idx:
        missing = [t for t in (away, home) if t not in idx]
        raise ValueError("Team(s) absent from eligible training data: " + ", ".join(missing))

    strength = model["strength"]
    bt = model["betaTotal"]
    margin = (0.0 if neutral else model["homeMarginAdvantage"]) + strength[idx[home]] - strength[idx[away]]
    total = bt[0] + bt[1 + idx[home]] + bt[1 + idx[away]]
    total = max(0.0, float(total))
    margin = float(margin)

    home_pts = max(0.0, (total + margin) / 2.0)
    away_pts = max(0.0, (total - margin) / 2.0)
    total = home_pts + away_pts
    margin = home_pts - away_pts

    return {
        "projectedAwayPoints": away_pts,
        "projectedHomePoints": home_pts,
        "projectedMarginHome": margin,
        "projectedSpreadHome": -margin,
        "projectedTotal": total,
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
        return {"games": 0, "marginMae": None, "totalMae": None, "scoreMae": None, "marginRmse": None, "marginResidualStd": None}
    arr_m = np.asarray(margin_errors)
    arr_t = np.asarray(total_errors)
    arr_s = np.asarray(score_errors)
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
        return 20.0, 35, DEFAULT_MIN_TEAM_APPEARANCES, None, {
            "mode": "FALLBACK_INSUFFICIENT_TEMPORAL_HOLDOUT",
            "trainGames": len(train),
            "validationGames": len(valid),
        }

    candidates = []
    for min_apps in (3, 4):
        for alpha in (2.5, 5.0, 10.0, 20.0, 40.0, 80.0):
            for half_life in (21, 35, 56, None):
                try:
                    train_model = fit_model(train, split, alpha, half_life, min_apps)
                except ValueError:
                    continue
                train_hfa = float(train_model["homeMarginAdvantage"])
                validation_model = fit_model(train, split, alpha, half_life, min_apps, fixed_hfa=train_hfa)
                ev = evaluate(validation_model, valid)
                if int(ev["games"] or 0) < 15:
                    continue
                objective = (float(ev["marginMae"]) + float(ev["totalMae"])) / 2.0
                candidates.append((objective, alpha, half_life, min_apps, train_hfa, ev, train_model["eligibleTrainingGames"]))

    if not candidates:
        return 20.0, 35, DEFAULT_MIN_TEAM_APPEARANCES, None, {"mode": "FALLBACK_NO_VALID_CANDIDATES"}

    candidates.sort(key=lambda x: (x[0], x[1], x[3], 999 if x[2] is None else x[2]))
    objective, alpha, half_life, min_apps, train_hfa, ev, eligible = candidates[0]
    return alpha, half_life, min_apps, train_hfa, {
        "mode": "PRE_WEEK8_TEMPORAL_HOLDOUT",
        "splitAt": iso(split),
        "rawTrainGames": len(train),
        "eligibleTrainGames": eligible,
        "validationGames": len(valid),
        "objective": objective,
        "selectedValidation": ev,
        "selectedStructuralHomeMarginAdvantage": train_hfa,
        "candidateCount": len(candidates),
    }


def matchup_code(name: str) -> str:
    return canonical_school(name)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def run(input_path: Path, output_path: Path, as_of: datetime, start: datetime):
    state = json.loads(input_path.read_text(encoding="utf-8"))
    raw_training = fetch_completed_games(start, as_of)
    alpha, half_life, min_apps, structural_hfa, tuning = tune(raw_training, as_of)

    if structural_hfa is None:
        provisional = fit_model(raw_training, as_of, alpha, half_life, min_apps)
        structural_hfa = float(provisional["homeMarginAdvantage"])
        hfa_source = "FULL_SAMPLE_FALLBACK_PROVISIONAL"
    else:
        hfa_source = "PRE_WEEK8_TRAINING_WINDOW_FROZEN"

    model = fit_model(raw_training, as_of, alpha, half_life, min_apps, fixed_hfa=structural_hfa)

    split = as_of - timedelta(days=14)
    earlier = [g for g in raw_training if g.kickoff < split]
    recent = [g for g in raw_training if g.kickoff >= split]
    if len(earlier) >= 100 and len(recent) >= 20:
        holdout_model = fit_model(earlier, split, alpha, half_life, min_apps, fixed_hfa=structural_hfa)
        holdout_eval = evaluate(holdout_model, recent)
        sigma = holdout_eval.get("marginResidualStd") or 15.0
        sigma_source = "temporal_holdout_margin_residual_std"
    else:
        full_eval = evaluate(model, filter_core_games(raw_training, min_apps))
        sigma = full_eval.get("marginResidualStd") or 15.0
        sigma_source = "in_sample_margin_residual_std_provisional"

    hfa_sane = HFA_SANITY_RANGE[0] <= float(structural_hfa) <= HFA_SANITY_RANGE[1]
    hfa_validated = hfa_source == "PRE_WEEK8_TRAINING_WINDOW_FROZEN"
    raw_counts = appearance_counts(raw_training)
    eligible_counts = appearance_counts(filter_core_games(raw_training, min_apps))

    rows = []
    coverage: dict[str, Any] = {}
    for game in state.get("games", []):
        away_code = matchup_code(game["awayTeam"])
        home_code = matchup_code(game["homeTeam"])
        for display, code in ((game["awayTeam"], away_code), (game["homeTeam"], home_code)):
            coverage[code] = {
                "displayName": display,
                "rawAppearances": int(raw_counts.get(code, 0)),
                "eligibleAppearances": int(eligible_counts.get(code, 0)),
                "inEligibleModel": code in model["idx"],
            }
        try:
            pr = predict(model, away_code, home_code, neutral=False)
            z = pr["projectedMarginHome"] / max(float(sigma), 1e-6)
            pr["homeWinProbability"] = 100.0 * normal_cdf(z)
            pr["projectedWinner"] = game["homeTeam"] if pr["projectedMarginHome"] > 0 else game["awayTeam"]
            ready = hfa_sane and hfa_validated
            status = "SHADOW_READY" if ready else "SHADOW_REVIEW"
            error = None if ready else "structural home-field parameter failed provenance/sanity gate"
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
        "schemaVersion": 8,
        "league": "cfb",
        "season": state.get("season"),
        "week": state.get("week"),
        "modelId": "cfb-rebuild-alpha-shadow-v8",
        "role": "SHADOW_CHALLENGER_ONLY",
        "canonicalInfluence": False,
        "asOf": iso(as_of),
        "trainingWindowStart": iso(start),
        "rawTrainingGames": len(raw_training),
        "eligibleTrainingGames": model["eligibleTrainingGames"],
        "teamIdentity": "normalized ESPN team.location/name with explicit aliases",
        "ingestionMode": "ESPN FBS-only team discovery + team regular-season schedules; dedupe event IDs; hard kickoff cutoff",
        "targetCoverage": coverage,
        "source": {
            "provider": "ESPN public FBS teams + college-football team schedules",
            "marketDataUsed": False,
            "externalRatingsUsed": False,
            "postKickoffDataUsed": False,
        },
        "fit": {
            "description": "separate ridge-shrunk margin and scoring-environment models with structural HFA frozen from pre-Week-8 training",
            "selectedAlpha": alpha,
            "selectedHalfLifeDays": half_life,
            "minTeamAppearances": min_apps,
            "structuralHomeMarginAdvantage": float(structural_hfa),
            "homeFieldSource": hfa_source,
            "homeFieldSanityRange": list(HFA_SANITY_RANGE),
            "homeFieldSanityPass": hfa_sane,
            "homeFieldProvenancePass": hfa_validated,
            "uncertaintyMarginSigma": float(sigma),
            "uncertaintySource": sigma_source,
            "tuning": tuning,
            "fullFitDiagnostics": evaluate(model, filter_core_games(raw_training, min_apps)),
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
        print(json.dumps({
            "modelId": out["modelId"],
            "rawTrainingGames": out["rawTrainingGames"],
            "eligibleTrainingGames": out["eligibleTrainingGames"],
            "structuralHomeMarginAdvantage": out["fit"]["structuralHomeMarginAdvantage"],
            "homeFieldSanityPass": out["fit"]["homeFieldSanityPass"],
            "homeFieldProvenancePass": out["fit"]["homeFieldProvenancePass"],
            "targetCoverage": out["targetCoverage"],
            "games": len(out["games"]),
        }, indent=2))
    except Exception as exc:
        print(f"CFB_SHADOW_ENGINE_ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
