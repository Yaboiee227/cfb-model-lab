"""Guard evidence timestamps and known QB breaks separately from frozen forecasts."""

import csv, json, shutil, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from publish_nfl_current_research import audit


def instant(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_current_context_is_pregame_and_never_clears_release():
    d = json.loads((ROOT / "data/game-readiness.json").read_text())
    assert len({(g["league"], g["eventId"]) for g in d["games"]}) == len(d["games"])
    assert d["forecastChanges"] == 0 and d["canonicalInfluence"] is False
    for g in d["games"]:
        assert g["contextStatus"] == "PREGAME_CONTEXT_CAPTURED"
        assert instant(g["observedAt"]) < instant(g["kickoffUTC"])
        assert g["releaseStatus"] == "HOLD" and g["finalAvailabilityVerified"] is False
        if g.get("nwsWeather"):
            w = g["nwsWeather"]
            ps = w["periods"]
            if w["coverageComplete"]:
                assert instant(ps[0]["startTime"]) <= instant(g["kickoffUTC"])
                assert instant(ps[-1]["endTime"]) >= instant(
                    g["kickoffUTC"]
                ) + timedelta(hours=4)
                assert all(
                    instant(a["endTime"]) == instant(b["startTime"])
                    for a, b in zip(ps, ps[1:])
                )
    for g in d["excludedStartedGames"]:
        assert instant(g["kickoffUTC"]) <= instant(d["collectionStartedAt"])


def copied_root(tmp):
    for f in [
        "nfl_data/site/config.json",
        "nfl_data/site/projections.csv",
        "nfl_data/site/personnel-gates.json",
        "nfl/research-projections/week-09.json",
    ]:
        p = tmp / f
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / f, p)
    return tmp


def test_qb_break_requires_actual_current_game_evidence(tmp_path):
    root = copied_root(tmp_path)
    p = root / "nfl_data/site/projections.csv"
    rows = list(csv.DictReader(p.open()))
    fields = list(rows[0])
    rows[0]["hardQbStateBreak"] = "true"
    with p.open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with unittest.TestCase().assertRaisesRegex(ValueError, "QB break lacks"):
        audit(root)


def test_after_kickoff_qb_report_cannot_validate_a_pregame_flag(tmp_path):
    root = copied_root(tmp_path)
    p = root / "nfl_data/site/personnel-gates.json"
    d = json.loads(p.read_text())
    r = next(g for g in d["games"] if g.get("qbChange"))
    r["observedAt"] = "2026-11-09T23:00:00Z"
    p.write_text(json.dumps(d))
    with unittest.TestCase().assertRaisesRegex(ValueError, "QB break lacks"):
        audit(root)


def test_current_qb_break_does_not_change_projection_numbers_or_probabilities():
    assert audit(ROOT)["games"] == 14
    rows = list(csv.DictReader((ROOT / "nfl_data/site/projections.csv").open()))
    flag = [g for g in rows if g["hardQbStateBreak"] == "true"]
    assert [g["gameId"] for g in flag] == ["2026_09_ARI_SEA"]
    assert all(
        not r["qbOperationalPointAdjustment"] and not r["homeWinProbability"]
        for r in rows
    )
