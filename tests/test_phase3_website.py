from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_phase_three_assets_load_after_phase_two():
    guard = read("site-runtime-guard.js")
    assert "cb-phase3.css" in guard
    assert "cb-phase3.js" in guard
    assert "CB_PHASE3_READY" in guard
    assert guard.index("CB_PHASE2_READY") < guard.index("CB_PHASE3_READY")


def test_phase_three_filters_cover_agreed_dimensions_without_model_mutation():
    script = read("cb-phase3.js")
    for control in ("cbTeamFilter", "weekFilter", "conferenceFilter", "cbConfidenceFilter", "cbBetTypeFilter"):
        assert control in script
    assert "70%+ favorite" in script
    assert "display-only band" in script
    assert "betTypeAvailable" in script
    assert "modelSpreadHome" in script
    assert "marketSpreadHome" in script
    assert "modelTotal" in script
    assert "marketTotal" in script
    assert "canonical" not in script.lower() or "canonical" in read("site-shell.js").lower()


def test_phase_three_team_lens_uses_existing_projection_results_and_rankings_only():
    script = read("cb-phase3.js")
    assert "selectedTeamGames" in script
    assert "teamResultRows" in script
    assert "data/power-rankings/${league}.json" in script
    assert "Open rankings view" in script
    assert "renderTeamLens" in script
    assert "fetch('http" not in script


def test_phase_three_group_rankings_are_descriptive_and_withhold_missing_cfb_group_metadata():
    script = read("cb-phase3.js")
    assert "Model difference" in script
    assert "ATS record" in script
    assert "NFL_DIVISIONS" in script
    assert "conference model-difference rankings are withheld rather than inferred" in script
    assert "atsGroups" in script
    assert "edgeGroups" in script


def test_phase_three_power_replay_uses_only_preserved_snapshots():
    page = read("ratings.html")
    script = read("power-rankings-phase3.js")
    assert 'power-rankings-phase3.css' in page
    assert '<script src="power-rankings-phase3.js"></script>' in page
    assert "archive/${league}-previous.json" in script
    assert "data/power-rankings/${league}.json" in script
    assert "Missing weeks are never reconstructed" in script
    assert "frozen ranking files already present in the repository" in script
    assert "Season scrubber" in script
    assert "Play preserved weeks" in script


def test_phase_three_respects_reduced_motion_and_mobile_layouts():
    filters_css = read("cb-phase3.css")
    replay_css = read("power-rankings-phase3.css")
    replay_js = read("power-rankings-phase3.js")
    assert "prefers-reduced-motion" in filters_css
    assert "prefers-reduced-motion" in replay_css
    assert "max-width:720px" in filters_css
    assert "max-width:760px" in replay_css
    assert "prefersReducedMotion" in replay_js


def test_phase_three_does_not_modify_projection_or_result_schema_files():
    cfb_projection = read("data/projections.csv").splitlines()[0]
    nfl_projection = read("nfl_data/site/projections.csv").splitlines()[0]
    cfb_results = read("data/results.csv").splitlines()[0]
    nfl_results = read("nfl_data/site/results.csv").splitlines()[0]
    assert cfb_projection.startswith("season,week,date,kickoffET,gameId")
    assert nfl_projection.startswith("league,season,week,date,kickoffET,gameId")
    assert "atsResult" in cfb_results and "suResult" in cfb_results
    assert "atsResult" in nfl_results and "suResult" in nfl_results


def test_phase_three_stays_static_no_build_framework():
    combined = "\n".join(read(name) for name in (
        "cb-phase3.js",
        "cb-phase3.css",
        "power-rankings-phase3.js",
        "power-rankings-phase3.css",
        "ratings.html",
    )).lower()
    assert "react-dom" not in combined
    assert "vite" not in combined
    assert "webpack" not in combined
