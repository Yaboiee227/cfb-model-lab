#!/usr/bin/env python3
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data/power-rankings"


def load(name):
    return json.loads((DIR / name).read_text(encoding="utf-8"))


def test_01_cfb_has_all_138_fbs_teams():
    doc = load("cfb.json")
    assert doc["teamCount"] == 138
    assert len(doc["teams"]) == 138
    assert len({r["team"] for r in doc["teams"]}) == 138
    assert all(r["teamName"] and r["teamName"] != r["team"] for r in doc["teams"]), "CFB display-name normalization incomplete"


def test_02_nfl_has_all_32_teams():
    doc = load("nfl.json")
    assert doc["teamCount"] == 32
    assert len(doc["teams"]) == 32
    assert len({r["team"] for r in doc["teams"]}) == 32


def test_03_cb_point_scales_are_zero_mean():
    for name in ("cfb.json", "nfl.json"):
        doc = load(name)
        mean = sum(float(r["cbPoints"]) for r in doc["teams"]) / len(doc["teams"])
        assert abs(mean) < 1e-3, (name, mean)


def test_04_ranks_are_complete_and_monotonic():
    for name in ("cfb.json", "nfl.json"):
        doc = load(name)
        ranks = [int(r["rank"]) for r in doc["teams"]]
        pts = [float(r["cbPoints"]) for r in doc["teams"]]
        assert ranks == list(range(1, len(ranks) + 1))
        assert pts == sorted(pts, reverse=True)


def test_05_market_national_ratings_are_withheld_when_graph_is_disconnected():
    for name in ("cfb.json", "nfl.json"):
        status = load(name)["marketNationalRatings"]
        assert status["graph"]["connected"] is False
        assert status["nationalRatingStatus"] == "WITHHELD_DISCONNECTED_MARKET_GRAPH"
        assert status["graph"]["coveredTeams"] < status["graph"]["teamCount"] or status["graph"]["components"] > 1


def test_06_current_comparisons_match_captured_games_without_overwriting_archive():
    context=json.loads((ROOT / "data/game-readiness.json").read_text())
    for league in ("cfb","nfl"):
        expected={g['projectionGameId'] for g in context['games'] if g['league']==league and (g.get('marketReference') or {}).get('spreadHome') is not None}
        assert {g['gameId'] for g in load(f"{league}.json")['remainingMatchupComparisons']} == expected
    assert len(load("archive/cfb-previous.json")["remainingMatchupComparisons"]) == 54
    assert load("archive/nfl-previous.json")["week"] == 8


def test_07_gap_convention_and_side_label_are_exact():
    for name in ("cfb.json", "nfl.json"):
        for row in load(name)["remainingMatchupComparisons"]:
            expected = float(row["marketSpreadHome"]) - float(row["modelSpreadHome"])
            assert math.isclose(float(row["modelMarketGapHome"]), expected, abs_tol=1e-10)
            side = row["homeTeam"] if expected > 0 else row["awayTeam"] if expected < 0 else "PUSH"
            assert row["gapSide"] == side
            assert math.isclose(float(row["gapMagnitude"]), abs(expected), abs_tol=1e-10)


def test_08_power_rankings_never_promote_or_rewrite_canonical_models():
    cfb = load("cfb.json")
    nfl = load("nfl.json")
    for doc in (cfb, nfl):
        assert doc["canonicalInfluence"] is False
        assert doc["canonicalPromotionAuthorized"] is False
        assert doc["modelRole"] == "RESEARCH_POWER_RATING_ONLY"
    assert cfb["week8FrozenProjectionsRewritten"] is False


def test_09_nfl_extractor_reproduces_all_14_frozen_week7_margins():
    doc = load("nfl.json")
    reg = doc["frozenRegression"]
    assert reg["pass"] is True
    assert reg["games"] == 14
    assert float(reg["maxAbsDiff"]) <= 1e-8
    assert len(reg["rows"]) == 14
    assert max(float(r["absDiff"]) for r in reg["rows"]) <= 1e-8
    assert doc["allPairsNeutralMatchups"] == 32 * 31


def test_10_manifest_hashes_and_snapshot_provenance_match_files():
    manifest = load("manifest.json")
    assert manifest["canonicalInfluence"] is False
    assert manifest["canonicalPromotionAuthorized"] is False
    assert manifest["leagues"]["cfb"]["snapshotAsOf"] == load("cfb.json")["snapshotAsOf"]
    assert load("archive/cfb-previous.json")["snapshotAsOf"] == "2026-10-28T12:45:00Z"
    assert manifest["leagues"]["nfl"]["sourceCommit"] == "0721b59b5f461ad590bd348bd655c4963265856c"
    for name, expected in manifest["files"].items():
        actual = hashlib.sha256((DIR / name).read_bytes()).hexdigest()
        assert actual == expected, name


def test_11_nfl_refresh_sources_and_coverage_lag_are_explicit():
    d = load("nfl.json")
    assert d["week"] == 9 and d["sourceMaxWeek"] == 8
    p = d["refreshProvenance"]
    assert d['currentWeekReproductionMaxAbsDiff'] <= 1e-8
    assert p['targetWeek'] == 9 and p['maxSourceWeek'] == 8
    assert p['coverageLag'] == []
    assert hashlib.sha256((ROOT / p['inputPath']).read_bytes()).hexdigest() == p['inputSha256']
    inputs=json.loads((ROOT / p['inputPath']).read_text())
    assert len(inputs['teamCore']) == len(inputs['teamCoverage']) == 32
    assert max(r['max_current_season_week_used'] for r in inputs['teamCore'].values()) == 8
    assert max(r['max_current_week_used'] for r in inputs['teamCoverage'].values()) == 8
    assert d['inputLimitations']


def test_12_current_comparisons_exclude_completed_kickoffs():
    from datetime import datetime
    for name in ("cfb.json", "nfl.json"):
        d = load(name)
        cutoff = datetime.fromisoformat(d["snapshotAsOf"].replace("Z", "+00:00"))
        assert all(datetime.fromisoformat(g["kickoff"].replace("Z", "+00:00")) > cutoff for g in d["remainingMatchupComparisons"])
    cfb=load("cfb.json");p=ROOT / cfb['provenance']['trainingPath']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == cfb['provenance']['trainingSha256']
    train=json.loads(p.read_text());assert len(train['games'])==cfb['trainingGames']
    assert all(datetime.fromisoformat(g['kickoff']) < datetime.fromisoformat(cfb['snapshotAsOf']) for g in train['games'])
    assert cfb['lockedParameters'] == {'alpha':2.5,'halfLifeDays':56,'minTeamAppearances':4}


def test_13_movement_matches_previous_published_snapshot():
    for league in ("cfb", "nfl"):
        previous = {r["team"]: r["rank"] for r in load(f"archive/{league}-previous.json")["teams"]}
        assert all(r["movement"] == previous[r["team"]] - r["rank"] for r in load(f"{league}.json")["teams"])
