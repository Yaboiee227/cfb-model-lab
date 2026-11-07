#!/usr/bin/env python3
"""Refresh descriptive power ratings without modifying frozen game forecasts."""

import argparse, csv, dataclasses, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "0721b59b5f461ad590bd348bd655c4963265856c"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--schedule", type=Path, required=True)
    a = ap.parse_args()
    source = a.source_root.resolve()
    schedule_path = a.schedule.resolve()
    out = ROOT / "data/power-rankings"
    asof = datetime.now(timezone.utc)
    assert (
        subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        == PIN
    )
    assert not subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain"], text=True
    ).strip()
    previous = {l: json.loads((out / f"{l}.json").read_text()) for l in ["cfb", "nfl"]}
    for l in previous:
        archive = out / "archive" / asof.strftime("%Y%m%dT%H%M%SZ") / f"{l}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes((out / f"{l}.json").read_bytes())
        (out / f"archive/{l}-previous.json").write_bytes(
            (out / f"{l}.json").read_bytes()
        )
    # CFB uses the exact locked foundation spec, with completed games at a new current cutoff.
    import build_power_rankings as pr

    engine = pr.engine
    lock = json.loads(
        (ROOT / "cfb/research-locks/week-10-foundation-full.json").read_text()
    )
    params = lock["lockedParameters"]
    hfa = lock["structuralHomeMarginAdvantage"]
    original_fetch = engine.fetch_json
    raw_sources = []

    def recorded_fetch(url):
        d = original_fetch(url)
        raw_sources.append(
            {
                "url": url,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "payload": d,
            }
        )
        return d

    engine.fetch_json = recorded_fetch
    completed = engine.fetch_completed_games(pr.CFB_START, asof)
    assert all(g.kickoff < asof for g in completed)
    model = engine.fit_model(
        completed,
        asof,
        alpha=params["alpha"],
        half_life_days=params["halfLifeDays"],
        min_team_appearances=params["minTeamAppearances"],
        fixed_hfa=hfa,
    )
    assert len(model["teams"]) == 138
    strength = {t: float(model["strength"][model["idx"][t]]) for t in model["teams"]}
    mean = sum(strength.values()) / len(strength)
    oldnames = {r["team"]: r["teamName"] for r in previous["cfb"]["teams"]}
    oldranks = {r["team"]: r["rank"] for r in previous["cfb"]["teams"]}
    teams = [
        dict(
            rank=i,
            team=t,
            teamName=oldnames[t],
            cbPoints=round(strength[t] - mean, 4),
            movement=oldranks[t] - i,
            marketRank=None,
            marketPoints=None,
            marketGap=None,
            evidenceStatus="CURRENT_COMPLETED_GAME_FOUNDATION_STRENGTH",
        )
        for i, t in enumerate(sorted(strength, key=lambda t: -(strength[t] - mean)), 1)
    ]
    trainpath = (
        ROOT / "research/operations/week10-week9-20261107/cfb-rating-training.json"
    )
    write(
        trainpath,
        {
            "asOf": asof.isoformat(),
            "games": [
                {**dataclasses.asdict(g), "kickoff": g.kickoff.isoformat()}
                for g in completed
            ],
        },
    )
    cfb = {
        **previous["cfb"],
        "week": 10,
        "snapshotAsOf": asof.isoformat(),
        "method": "Current zero-mean foundation team strengths, using unchanged locked parameters and only completed games before the stated cutoff. These descriptive ratings do not rewrite frozen Week 10 forecasts.",
        "trainingGames": len(completed),
        "eligibleTrainingGames": model["eligibleTrainingGames"],
        "teams": teams,
        "cbPointsMean": sum(r["cbPoints"] for r in teams) / 138,
        "previousSnapshotAsOf": previous["cfb"]["snapshotAsOf"],
        "provenance": {
            "trainingPath": str(trainpath.relative_to(ROOT)),
            "trainingSha256": sha(trainpath),
            "freezePath": "cfb/research-locks/week-10-foundation-full.json",
            "freezeSha256": sha(
                ROOT / "cfb/research-locks/week-10-foundation-full.json"
            ),
        },
        "remainingMatchupComparisons": [],
    }
    # Preserve actual retrieval payloads separately from the compact training rows.
    import gzip

    rawpath = (
        ROOT
        / "research/operations/week10-week9-20261107/cfb-rating-source-responses.json.gz"
    )
    rawpath.write_bytes(gzip.compress(json.dumps(raw_sources).encode(), mtime=0))
    cfb["provenance"]["rawResponsesSha256"] = sha(rawpath)
    # NFL reuses the same captured Week 9 inputs as the published baseline.
    os.chdir(source)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source / "scripts"))
    import numpy as np, pandas as pd
    import run_nfl_walk_forward as base, build_nfl_week6_research_projections as wk, validate_nfl_rating_system_robustness as rat, validate_nfl_final_plus_ftn_qb_process as final
    import importlib.util

    specmod = importlib.util.spec_from_file_location(
        "rating_extract", ROOT / "scripts/build_nfl_power_rankings.py"
    )
    extract = importlib.util.module_from_spec(specmod)
    specmod.loader.exec_module(extract)
    snap = source / "nfl_data/prospective/week7/20261021T114427Z"
    spec = json.loads((snap / "manifest.json").read_text())
    cp, rp = spec["coverage_params"], spec["rating_params"]
    for name, h in spec["source_hashes"].items():
        assert sha(source / name) == h
    for name, h in spec["files"].items():
        assert sha(snap / name) == h
    schedule = pd.read_csv(
        source / "nfl_data/research/week6_failure_20261021/inputs/nflverse_games.csv"
    )
    _, _, cut = extract.rating_state_through_week6(schedule, rp)
    historical = base.load_rows()
    rated = rat.attach(
        wk.attach_historical_coverage(historical),
        rat.rating_maps(
            cut,
            rp["elo_k"],
            rp["elo_hfa"],
            rp["offseason_regression"],
            rp["margin_k"],
            rp["margin_hfa"],
        ),
    )
    fit = final.fit(rated, cp["team_k"], cp["feature_k"], rp["lambda"])
    f = extract.read_csv(snap / "game_feature_inputs.csv")
    targets = {
        r["game_id"]: float(r["canonical_home_margin"])
        for r in extract.read_csv(snap / "paired_projections.csv")
    }
    pred, _ = final.predict(f, cp["team_k"], cp["feature_k"], fit)
    diff = max(abs(float(v) - targets[r["game_id"]]) for r, v in zip(f, pred))
    assert diff < 1e-8 and len(f) == 14
    ip = ROOT / "nfl_data/prospective/week9/20261107T002937Z/model-inputs.json"
    inp = json.loads(ip.read_text())
    fr = json.loads((ROOT / "nfl/research-projections/week-09.json").read_text())
    assert (
        hashlib.sha256(ip.read_bytes()).hexdigest()
        == "fce9db8030656b4535099f956ef36dae3e07ca18c9a417694630fbe1c3e08075"
    )
    elo, margin, _ = extract.rating_state_through_week6(
        pd.read_csv(schedule_path), rp, target_week=9
    )
    core, cov = inp["teamCore"], inp["teamCoverage"]
    keys = sorted(core)
    pairs = [(h, a) for h in keys for a in keys if h != a]
    synthetic = [extract.synthetic_row(h, a, core, cov, elo, margin) for h, a in pairs]
    pred, _ = final.predict(synthetic, cp["team_k"], cp["feature_k"], fit)
    points, residual = extract.solve_team_points(
        keys, {p: float(v) for p, v in zip(pairs, pred)}
    )
    # The refreshed game-feature rows must still reproduce the published Week 9 spread.
    gp, _ = final.predict(inp["gameFeatures"], cp["team_k"], cp["feature_k"], fit)
    byid = {g["gameId"]: g for g in fr["games"]}
    parity = max(
        abs(-float(v) - byid[r["game_id"]]["modelSpreadHome"])
        for r, v in zip(inp["gameFeatures"], gp)
    )
    assert parity < 1e-8
    oldranks = {r["team"]: r["rank"] for r in previous["nfl"]["teams"]}
    teams = [
        dict(
            rank=i,
            team=t,
            teamName=extract.TEAM_NAMES[t],
            cbPoints=round(points[t], 4),
            movement=oldranks[t] - i,
            marketRank=None,
            marketPoints=None,
            marketGap=None,
            evidenceStatus="UPDATED_THROUGH_WEEK8_BASELINE_CONTEXT_UNADJUSTED",
        )
        for i, t in enumerate(sorted(keys, key=lambda t: -points[t]), 1)
    ]
    nfl = {
        **previous["nfl"],
        "week": 9,
        "snapshotAsOf": asof.isoformat(),
        "sourceMaxWeek": 8,
        "teams": teams,
        "method": "Unchanged canonical spread architecture with Week 9 team inputs through Week 8; 992 neutral orientations summarized as zero-mean point ratings. Injuries, transactions, officials and weather are unadjusted context.",
        "pointScaleFitResidualRmse": residual,
        "previousSnapshotAsOf": previous["nfl"]["snapshotAsOf"],
        "frozenRegression": {
            "games": 14,
            "pass": True,
            "maxAbsDiff": diff,
            "rows": [
                dict(gameId=r["game_id"], absDiff=abs(float(v) - targets[r["game_id"]]))
                for r, v in zip(
                    f, final.predict(f, cp["team_k"], cp["feature_k"], fit)[0]
                )
            ],
        },
        "currentWeekReproductionMaxAbsDiff": parity,
        "refreshProvenance": {
            "inputPath": str(ip.relative_to(ROOT)),
            "inputSha256": sha(ip),
            "sourceScheduleSha256": sha(schedule_path),
            "targetWeek": 9,
            "maxSourceWeek": 8,
            "coverageLag": fr["inputs"]["coverageLag"],
            "projectionFrozenAt": fr["frozenAt"],
        },
        "inputLimitations": "Baseline ratings do not include current injuries, QB changes or trade effects.",
        "remainingMatchupComparisons": [],
    }
    for l, d in [("cfb", cfb), ("nfl", nfl)]:
        d["marketNationalRatings"] = pr.market_status(
            pr.graph_status({r["team"] for r in d["teams"]}, []),
            None,
            "Current context comparisons updated separately",
        )
        write(out / f"{l}.json", d)
        with (out / f"{l}.csv").open("w") as fp:
            w = csv.DictWriter(fp, fieldnames=list(d["teams"][0]), lineterminator="\n")
            w.writeheader()
            w.writerows(d["teams"])
    pr.write_manifest(cfb, nfl, out)
    print(
        json.dumps(
            {
                "cfbTeams": 138,
                "cfbTrainingGames": len(completed),
                "nflTeams": 32,
                "nflOldParity": diff,
                "nflCurrentParity": parity,
            }
        )
    )


if __name__ == "__main__":
    main()
