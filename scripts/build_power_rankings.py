#!/usr/bin/env python3
"""Build research-only CB Model Projections team power rankings.

CFB CB Points are the zero-mean team-strength coefficients from the same frozen
validated Week 8 foundation architecture, refit only on games completed before
the October 28 morning cutoff.  These rankings are descriptive
research output only; they do not rewrite the immutable Week 8 projections.

NFL CB Points are produced by build_nfl_power_rankings.py from the exact pinned
pre-Week-7 model snapshot and are passed in as an input artifact.

Market rankings remain a strictly separate benchmark layer.  A league-wide
market rank is withheld unless the timestamped matchup graph covers and connects
every ranked team.  Matchup-level model/market comparisons are still preserved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cfb_shadow_engine as engine  # noqa: E402
from run_cfb_shadow_week8 import extract_grouped_team_ids  # noqa: E402

engine.extract_team_ids = extract_grouped_team_ids

CFB_AS_OF = engine.parse_dt("2026-10-28T12:45:00Z")
CFB_START = engine.parse_dt("2026-08-20T04:00:00Z")
ET = ZoneInfo("America/New_York")
EXPECTED_CFB_TEAMS = 138
EXPECTED_NFL_TEAMS = 32


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(value):
    if value in (None, ""):
        return None
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def kickoff_from_projection(row: dict) -> datetime:
    dt = datetime.strptime(f"{row['date']} {row['kickoffET']}", "%Y-%m-%d %I:%M %p")
    return dt.replace(tzinfo=ET).astimezone(timezone.utc)


def cfb_display_names() -> dict[str, str]:
    params = "groups=80&groupType=conference&enable=groups"
    doc = engine.fetch_json(f"{engine.ESPN_FBS_TEAMS}?{params}")
    out = {}
    entries = []
    for sport in doc.get("sports", []):
        for league in sport.get("leagues", []):
            entries.extend(league.get("teams", []))
            for group in league.get("groups", []):
                entries.extend(group.get("teams", []))
    entries.extend(doc.get("teams", []))
    for entry in entries:
        team = entry.get("team") or entry
        try:
            key = engine.team_key(team)
        except Exception:
            continue
        display = team.get("location") or team.get("shortDisplayName") or team.get("displayName") or key
        out[key] = str(display)
    return out


def graph_status(team_keys: set[str], edges: list[tuple[str, str]]) -> dict:
    adjacency = defaultdict(set)
    covered = set()
    for away, home in edges:
        if away == home:
            continue
        adjacency[away].add(home)
        adjacency[home].add(away)
        covered.add(away)
        covered.add(home)
    if not team_keys:
        return {"connected": False, "teamCount": 0, "coveredTeams": 0, "edgeCount": len(edges), "components": 0}
    seen = set()
    components = 0
    for start in sorted(team_keys):
        if start in seen:
            continue
        components += 1
        q = deque([start])
        seen.add(start)
        while q:
            cur = q.popleft()
            for nxt in adjacency.get(cur, ()):
                if nxt in team_keys and nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
    return {
        "connected": components == 1 and covered >= team_keys,
        "teamCount": len(team_keys),
        "coveredTeams": len(covered & team_keys),
        "edgeCount": len(edges),
        "components": components,
        "minimumEdgesForConnectivity": max(0, len(team_keys) - 1),
    }


def market_status(graph: dict, observed_at: str | None, source: str) -> dict:
    if not graph["connected"]:
        reason = (
            f"Withheld: timestamped spread graph is not league-wide connected "
            f"({graph['coveredTeams']}/{graph['teamCount']} teams, {graph['edgeCount']} edges, "
            f"{graph['components']} components)."
        )
        return {
            "nationalRatingStatus": "WITHHELD_DISCONNECTED_MARKET_GRAPH",
            "reason": reason,
            "observedAt": observed_at,
            "source": source,
            "graph": graph,
        }
    # We deliberately do not silently borrow the CB model's HFA to manufacture a
    # supposedly independent market rating.  A validated market-HFA policy would
    # be required before connected-graph point estimates could publish.
    return {
        "nationalRatingStatus": "WITHHELD_MARKET_HFA_POLICY_NOT_VALIDATED",
        "reason": "Graph is connected, but no independently validated market-HFA normalization is authorized.",
        "observedAt": observed_at,
        "source": source,
        "graph": graph,
    }


def build_cfb(output_dir: Path):
    validation_path = ROOT / "cfb/validation/week-08-simple-foundation-validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    locked = validation["lockedDevelopmentCandidate"]
    if locked.get("status") != "FOUNDATION_CANDIDATE_READY":
        raise RuntimeError(f"CFB foundation not ready: {locked.get('status')}")
    params = locked["params"]
    hfa = float(validation["structuralHfaResearch"]["for2026"]["value"])

    completed = engine.fetch_completed_games(CFB_START, CFB_AS_OF)
    model = engine.fit_model(
        completed,
        CFB_AS_OF,
        alpha=float(params["alpha"]),
        half_life_days=params["halfLifeDays"],
        min_team_appearances=int(params["minTeamAppearances"]),
        fixed_hfa=hfa,
    )
    teams = list(model["teams"])
    if len(teams) != EXPECTED_CFB_TEAMS:
        raise RuntimeError(f"Expected {EXPECTED_CFB_TEAMS} CFB teams in frozen foundation fit, got {len(teams)}")
    strength = {team: float(model["strength"][model["idx"][team]]) for team in teams}
    mean_strength = sum(strength.values()) / len(strength)
    points = {team: strength[team] - mean_strength for team in teams}
    displays = cfb_display_names()

    projection_path = ROOT / "data/projections.csv"
    remaining = []
    edges = []
    observed = []
    for row in read_csv(projection_path):
        if kickoff_from_projection(row) <= CFB_AS_OF:
            continue
        model_spread = as_float(row.get("modelSpreadHome"))
        market_spread = as_float(row.get("marketSpreadHome"))
        if model_spread is None or market_spread is None:
            continue
        away_code = engine.canonical_school(row["awayTeam"])
        home_code = engine.canonical_school(row["homeTeam"])
        gap = market_spread - model_spread
        remaining.append({
            "gameId": row["gameId"],
            "kickoff": kickoff_from_projection(row).isoformat().replace("+00:00", "Z"),
            "awayTeam": row["awayTeam"],
            "homeTeam": row["homeTeam"],
            "modelSpreadHome": model_spread,
            "marketSpreadHome": market_spread,
            "modelMarketGapHome": gap,
            "gapSide": row["homeTeam"] if gap > 0 else row["awayTeam"] if gap < 0 else "PUSH",
            "gapMagnitude": abs(gap),
            "marketSource": row.get("marketSource") or None,
            "marketObservedAt": row.get("marketObservedAt") or None,
            "marketRole": "CONTEXT_BENCHMARK_ONLY",
        })
        edges.append((away_code, home_code))
        if row.get("marketObservedAt"):
            observed.append(row["marketObservedAt"])
    if len(remaining) != 54:
        raise RuntimeError(f"Expected 54 remaining CFB market comparisons at fixed cutoff, got {len(remaining)}")

    graph = graph_status(set(teams), edges)
    market = market_status(
        graph,
        max(observed) if observed else None,
        "FanDuel/DraftKings tracked context from data/projections.csv",
    )

    ranked = sorted(teams, key=lambda t: (-points[t], displays.get(t, t)))
    previous_path = output_dir / "archive/cfb-previous.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {"teams": []}
    old_ranks = {r["team"]: r["rank"] for r in previous["teams"]}
    rows = []
    for rank, team in enumerate(ranked, 1):
        rows.append({
            "rank": rank,
            "team": team,
            "teamName": displays.get(team, team),
            "cbPoints": round(points[team], 4),
            "movement": old_ranks.get(team, rank) - rank,
            "marketRank": None,
            "marketPoints": None,
            "marketGap": None,
            "evidenceStatus": "UPDATED_FOUNDATION_STRENGTH_EXTRACT",
        })

    out = {
        "schemaVersion": 1,
        "league": "cfb",
        "season": 2026,
        "week": 9,
        "snapshotAsOf": engine.iso(CFB_AS_OF),
        "trainingWindowStart": engine.iso(CFB_START),
        "modelId": "cfb-rebuild-foundation-v1-shadow",
        "modelRole": "RESEARCH_POWER_RATING_ONLY",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "week8FrozenProjectionsRewritten": False,
        "method": "Zero-mean schedule-adjusted team-strength coefficients from the frozen validated Week 8 foundation architecture, refit only on completed games before the October 28 morning cutoff.",
        "lockedParameters": params,
        "structuralHomeMarginAdvantage": hfa,
        "trainingGames": len(completed),
        "eligibleTrainingGames": int(model["eligibleTrainingGames"]),
        "teamCount": len(rows),
        "cbPointsMean": sum(r["cbPoints"] for r in rows) / len(rows),
        "marketNationalRatings": market,
        "remainingMatchupComparisons": remaining,
        "teams": rows,
        "provenance": {
            "validationPath": str(validation_path.relative_to(ROOT)),
            "validationSha256": sha256(validation_path),
            "projectionContextPath": str(projection_path.relative_to(ROOT)),
            "projectionContextSha256": sha256(projection_path),
        },
    }
    (output_dir / "cfb.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "cfb.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    return out


def enrich_nfl(nfl_model_path: Path, output_dir: Path):
    out = json.loads(nfl_model_path.read_text(encoding="utf-8"))
    if out.get("teamCount") != EXPECTED_NFL_TEAMS:
        raise RuntimeError(f"Expected {EXPECTED_NFL_TEAMS} NFL teams, got {out.get('teamCount')}")
    if not out.get("frozenRegression", {}).get("pass"):
        raise RuntimeError("NFL frozen-regression guard did not pass")

    market_path = ROOT / "nfl_data/site/market-reference.json"
    market_doc = json.loads(market_path.read_text(encoding="utf-8"))
    comparisons = []
    edges = []
    for game in market_doc.get("games", []):
        kickoff = engine.parse_dt(game["kickoffUtc"]) if game.get("kickoffUtc") else None
        if kickoff is None or kickoff <= engine.parse_dt(out["snapshotAsOf"]):
            continue
        model_spread = as_float(game.get("modelSpreadHome"))
        market_spread = as_float(game.get("marketSpreadHome"))
        if model_spread is None or market_spread is None:
            continue
        gap = market_spread - model_spread
        comparisons.append({
            "gameId": game.get("gameId"),
            "kickoff": game.get("kickoffUtc"),
            "awayTeam": game.get("away"),
            "homeTeam": game.get("home"),
            "modelSpreadHome": model_spread,
            "marketSpreadHome": market_spread,
            "modelMarketGapHome": gap,
            "gapSide": game.get("home") if gap > 0 else game.get("away") if gap < 0 else "PUSH",
            "gapMagnitude": abs(gap),
            "marketSource": game.get("marketSource") or market_doc.get("provider"),
            "marketObservedAt": game.get("marketObservedAt") or market_doc.get("observedAt"),
            "marketRole": "CONTEXT_BENCHMARK_ONLY",
            "eligibleForGrading": False,
        })
        edges.append((str(game.get("away")), str(game.get("home"))))

    team_keys = {str(row["team"]) for row in out["teams"]}
    graph = graph_status(team_keys, edges)
    out["marketNationalRatings"] = market_status(graph, market_doc.get("observedAt"), market_doc.get("provider", "NFL market reference"))
    out["remainingMatchupComparisons"] = comparisons
    if not comparisons:
        out["marketNationalRatings"]["reason"] = "Current Week 8 matchup comparisons await fresh market snapshots and matching projections; completed Week 7 lines are archived."
    out["marketReferenceProvenance"] = {
        "path": str(market_path.relative_to(ROOT)),
        "sha256": sha256(market_path),
        "eligibleForGrading": False,
        "executionVerified": False,
    }
    out["canonicalInfluence"] = False
    out["canonicalPromotionAuthorized"] = False
    (output_dir / "nfl.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    with (output_dir / "nfl.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out["teams"][0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(out["teams"])
    return out


def write_manifest(cfb: dict, nfl: dict, output_dir: Path):
    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "role": "RESEARCH_POWER_RANKINGS_ONLY",
        "canonicalInfluence": False,
        "canonicalPromotionAuthorized": False,
        "leagues": {
            "cfb": {
                "teamCount": cfb["teamCount"],
                "snapshotAsOf": cfb["snapshotAsOf"],
                "marketNationalRatingStatus": cfb["marketNationalRatings"]["nationalRatingStatus"],
                "matchupComparisons": len(cfb["remainingMatchupComparisons"]),
            },
            "nfl": {
                "teamCount": nfl["teamCount"],
                "snapshotAsOf": nfl["snapshotAsOf"],
                "sourceCommit": nfl["sourceCommit"],
                "marketNationalRatingStatus": nfl["marketNationalRatings"]["nationalRatingStatus"],
                "matchupComparisons": len(nfl["remainingMatchupComparisons"]),
                "frozenRegressionPass": nfl["frozenRegression"]["pass"],
            },
        },
        "files": {},
    }
    for name in ("cfb.json", "cfb.csv", "nfl.json", "nfl.csv"):
        manifest["files"][name] = sha256(output_dir / name)
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nfl-model", required=True)
    ap.add_argument("--output-dir", default="data/power-rankings")
    args = ap.parse_args()
    outdir = ROOT / args.output_dir
    outdir.mkdir(parents=True, exist_ok=True)
    cfb = build_cfb(outdir)
    nfl = enrich_nfl(Path(args.nfl_model), outdir)
    manifest = write_manifest(cfb, nfl, outdir)
    print(json.dumps({
        "cfb": {"teams":cfb["teamCount"],"top10":[[r["rank"],r["teamName"],r["cbPoints"]] for r in cfb["teams"][:10]],"market":cfb["marketNationalRatings"]["nationalRatingStatus"]},
        "nfl": {"teams":nfl["teamCount"],"top10":[[r["rank"],r["teamName"],r["cbPoints"]] for r in nfl["teams"][:10]],"market":nfl["marketNationalRatings"]["nationalRatingStatus"]},
        "manifest": manifest,
    }, indent=2))


if __name__ == "__main__":
    main()
