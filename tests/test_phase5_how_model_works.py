from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_phase_five_adds_content_only_model_guide():
    html = read("how-it-works.html")
    assert "How the Model Works" in html
    assert "how-it-works.css" in html
    assert "<script" not in html.lower()
    for section_id in ("overview", "inputs", "production", "reading", "grading", "validation"):
        assert f'id="{section_id}"' in html


def test_guide_preserves_separate_cfb_and_nfl_architectures():
    html = read("how-it-works.html")
    assert "two predictive systems" in html
    assert "do not share coefficients, feature weights, or a single model formula" in html
    assert "CFB and NFL use separate architectures and coefficients" in html


def test_guide_defines_public_spread_and_total_differences_exactly():
    html = read("how-it-works.html")
    assert "marketSpreadHome − modelSpreadHome" in html
    assert "modelTotal − marketTotal" in html
    assert "A negative value means the model makes the home team the favorite" in html
    assert "They are not ATS cover probabilities" in html


def test_guide_does_not_overstate_edge_or_confidence():
    html = read("how-it-works.html")
    assert "Difference is not the same as edge" in html
    assert "readiness metadata, not certainty" in html.lower()
    assert "should not be read as a guaranteed probability of covering a spread" in html
    assert "treat it as a research model/market difference" in html
    assert "A large model/market difference does not override a HOLD" in html


def test_guide_describes_honest_final_only_grading():
    html = read("how-it-works.html")
    required = (
        "Games remain pending until the result is Final",
        "saved publication-time market spread",
        "saved publication-time market total",
        "Saved moneyline data is reference metadata and does not change the SU grade",
        "Poor weeks remain visible",
        "not silently reconstructed after the game",
    )
    for phrase in required:
        assert phrase in html


def test_guide_preserves_promotion_and_integrity_rules():
    html = read("how-it-works.html")
    required = (
        "leakage-safe historical testing",
        "out-of-sample or walk-forward validation",
        "prospective frozen-week evidence",
        "explicit approval",
        "No postgame reconstruction",
        "No retroactive coefficient changes",
        "No external benchmark silently becoming canonical",
    )
    for phrase in required:
        assert phrase in html


def test_shared_navigation_exposes_guide_without_model_logic_changes():
    shell = read("site-shell.js")
    assert "how-it-works.html" in shell
    assert "How it works" in shell
    assert "modelSpreadHome =" not in shell
    assert "marketSpreadHome =" not in shell
    assert "coefficient" not in shell.lower()


def test_phase_five_css_has_mobile_and_reduced_motion_guards():
    css = read("how-it-works.css")
    assert "@media(max-width:760px)" in css
    assert "overflow:auto" in css
    assert "@media(prefers-reduced-motion:reduce)" in css
