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
        "recap.html",
        "ratings.html",
        "power-rankings.js",
        "power-rankings.css",
    )).lower()
    assert "react-dom" not in combined
    assert "create-react-app" not in combined
    assert "vite" not in combined
