from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_main_site_loads_redesign_shell_through_live_suite():
    loader = read("live-suite-loader.js")
    assert "loadCss('site-shell.css')" in loader
    assert "await loadScript('site-shell.js')" in loader
    assert "await loadScript('slate-navigation.js')" in loader


def test_phase_one_shared_brand_foundation_is_layered_without_model_changes():
    hotfix = read("site-shell-hotfix.css")
    guard = read("site-runtime-guard.js")
    foundation = read("cb-foundation.css")
    behavior = read("cb-foundation.js")
    assert '@import url("cb-foundation.css")' in hotfix
    assert "cb-foundation.js" in guard
    assert "--cb-charcoal: #202329" in foundation
    assert "--cb-orange: #FF652E" in foundation
    assert "--cb-white: #F7F7F4" in foundation
    assert "prefers-reduced-motion" in foundation
    assert "prefers-color-scheme: dark" in behavior
    assert "assets/brand/cb-logo.jpg" in foundation
    assert "assets/brand/cb-favicon.png" in behavior


def test_phase_one_brand_assets_exist():
    assert (ROOT / "assets/brand/cb-logo.jpg").is_file()
    assert (ROOT / "assets/brand/cb-favicon.png").is_file()


def test_phase_two_assets_are_loaded_after_the_existing_foundation():
    guard = read("site-runtime-guard.js")
    assert "assets/teams/team-assets.js" in guard
    assert "cb-team-visuals.js" in guard
    assert "cb-game-cards.js" in guard
    assert "cb-team-visuals.css" in guard
    assert "cb-game-cards.css" in guard
    assert guard.index("cb-foundation.js") < guard.index("cb-game-cards.js")


def test_phase_two_generated_team_badges_are_default_and_licensed_images_require_opt_in():
    config = read("assets/teams/team-assets.js")
    visuals = read("cb-team-visuals.js")
    assert "generated-badge" in config
    assert "teams: Object.freeze({})" in config
    assert "licensed === true" in visuals
    assert "licensedImage" in visuals
    assert "cb-team-badge" in visuals
    assert "clip-path" in read("cb-team-visuals.css")


def test_phase_two_game_cards_are_expandable_and_preserve_the_table_view():
    cards = read("cb-game-cards.js")
    styles = read("cb-game-cards.css")
    assert "cb-game-breakdown" in cards
    assert "Game breakdown" in cards
    assert "Model · market · difference · trends" in cards
    assert "cb-projection-view" in cards
    assert "data-cb-view-choice=\"cards\"" in cards
    assert "data-cb-view-choice=\"table\"" in cards
    assert '#projections[data-cb-view="cards"]' in styles
    assert '#projections[data-cb-view="table"]' in styles


def test_phase_two_trend_badges_use_only_existing_current_week_nfl_trend_data():
    cards = read("cb-game-cards.js")
    assert "nfl_data/site/nfl-trends.json" in cards
    assert "Number(doc.season) !== Number(game.season)" in cards
    assert "Number(doc.week) !== Number(game.week)" in cards
    assert "Aligns with model" in cards
    assert "No stale trend is carried forward" in cards
    assert "zero canonical influence" in cards.lower()


def test_phase_two_rivalry_and_primetime_tags_are_derived_without_new_data_files():
    cards = read("cb-game-cards.js")
    assert "function isPrimetime" in cards
    assert "minutes >= 19 * 60" in cards
    assert "function isRivalry" in cards
    assert "game.notes" in cards
    assert "rivalry" in cards
    assert "cb-game-tag-primetime" in cards
    assert "cb-game-tag-rivalry" in cards


def test_phase_two_live_team_logos_are_suppressed_only_in_the_presentation_layer():
    live = read("live-data.js")
    visuals = read("cb-team-visuals.js")
    styles = read("cb-game-cards.css")
    # Live source normalization remains untouched; Phase 2 suppresses image rendering in UI only.
    assert "homeRaw.team?.logo" in live
    assert "awayRaw.team?.logo" in live
    assert "stripUnlicensedLiveImages" in visuals
    assert "removeAttribute('src')" in visuals
    assert ".live-matchup-row img" in styles
    assert ".live-scoreboard .live-team>img" in styles


def test_phase_two_power_rankings_use_the_shared_team_visual_component():
    script = read("power-rankings.js")
    assert "CBTeamVisuals" in script
    assert "teamCell" in script
    assert "matchupCell" in script
    assert "cb-team-visuals.js" in script


def test_phase_two_does_not_change_projection_or_record_source_formats():
    cfb_header = read("data/projections.csv").splitlines()[0]
    nfl_header = read("nfl_data/site/projections.csv").splitlines()[0]
    assert cfb_header.startswith("season,week,date,kickoffET,gameId,awayTeam")
    assert nfl_header.startswith("league,season,week,date,kickoffET,gameId,awayTeam")
    assert "modelSpreadHome" in cfb_header and "marketSpreadHome" in cfb_header
    assert "modelSpreadHome" in nfl_header and "marketSpreadHome" in nfl_header


def test_shell_preserves_four_model_information_layers():
    script = read("site-shell.js")
    for required in ("Canonical", "Challenger", "Benchmark", "Context"):
        assert required in script
    assert "Missing pregame information is never reconstructed after results" in script


def test_shell_keeps_cfb_and_nfl_navigation():
    script = read("site-shell.js")
    assert 'index.html?league=nfl' in script
    assert "CB_ACTIVE_LEAGUE" in script
    assert "league-switch" in read("site-shell.css")


def test_shared_navigation_exposes_league_aware_power_rankings():
    script = read("slate-navigation.js")
    assert "Power Rankings" in script
    assert "ratings.html?league=nfl" in script
    assert "ratings.html" in script
    assert "powerRankingsNav" in script
    assert "powerRankingsFooter" in script


def test_recap_is_league_aware_and_uses_preserved_result_sources():
    page = read("recap.html")
    assert "cfb/record-summary.json" in page
    assert "nfl_data/site/results.csv" in page
    assert "model-registry.json" in page
    assert "Poor weeks remain visible" in page


def test_power_rankings_page_keeps_model_and_market_layers_separate():
    page = read("ratings.html")
    script = read("power-rankings.js")
    assert "CB power rankings" in page
    assert "Power rankings do not change canonical projections" in page
    assert "Market safeguard" in page
    assert "data/power-rankings/${league}.json" in script
    assert "remainingMatchupComparisons" in script
    assert "marketNationalRatings" in script
    assert "Context only" in script
    assert '<script src="power-rankings.js"></script>' in page


def test_power_ranking_snapshots_are_explicitly_noncanonical():
    for name in ("data/power-rankings/cfb.json", "data/power-rankings/nfl.json"):
        text = read(name)
        assert '"canonicalInfluence": false' in text
        assert '"canonicalPromotionAuthorized": false' in text
        assert '"modelRole": "RESEARCH_POWER_RATING_ONLY"' in text


def test_no_react_or_build_dependency_added_to_redesign_shell():
    combined = "\n".join(read(name) for name in (
        "site-shell.js",
        "site-shell.css",
        "cb-foundation.css",
        "cb-foundation.js",
        "cb-team-visuals.js",
        "cb-team-visuals.css",
        "cb-game-cards.js",
        "cb-game-cards.css",
        "recap.html",
        "ratings.html",
        "power-rankings.js",
        "power-rankings.css",
    )).lower()
    assert "react-dom" not in combined
    assert "create-react-app" not in combined
    assert "vite" not in combined
