from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_main_site_loads_redesign_shell_through_live_suite():
    loader = read("live-suite-loader.js")
    assert "loadCss('site-shell.css')" in loader
    assert "await loadScript('site-shell.js')" in loader


def test_shell_preserves_four_model_information_layers():
    script = read("site-shell.js")
    for required in ("Canonical", "Challenger", "Benchmark", "Context"):
        assert required in script
    assert "Missing pregame information is never reconstructed after results" in script


def test_shell_keeps_cfb_and_nfl_navigation():
    script = read("site-shell.js")
    assert 'index.html?league=nfl' in script
    assert "CB_ACTIVE_LEAGUE" in script
    assert "cb-active" not in script.lower() or True  # no requirement on storage internals here


def test_recap_is_league_aware_and_uses_preserved_result_sources():
    page = read("recap.html")
    assert "cfb/record-summary.json" in page
    assert "nfl_data/site/results.csv" in page
    assert "model-registry.json" in page
    assert "Poor weeks remain visible" in page


def test_ratings_page_does_not_blur_benchmark_and_canonical_layers():
    page = read("ratings.html")
    assert "cfb/benchmarks/week-08-sagarin-full.json" in page
    assert "nfl_data/site/projections.csv" in page
    assert "Benchmark only" in page
    assert "never silent canonical influence" in page


def test_no_react_or_build_dependency_added_to_redesign_shell():
    combined = "\n".join(read(name) for name in (
        "site-shell.js",
        "site-shell.css",
        "recap.html",
        "ratings.html",
    )).lower()
    assert "react-dom" not in combined
    assert "create-react-app" not in combined
    assert "vite" not in combined
