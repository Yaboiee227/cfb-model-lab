from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_phase_four_assets_load_after_phase_three():
    guard = read("site-runtime-guard.js")
    assert "cb-phase4.css" in guard
    assert "cb-phase4.js" in guard
    assert "CB_PHASE4_READY" in guard
    assert guard.index("CB_PHASE3_READY") < guard.index("CB_PHASE4_READY")


def test_phase_four_is_presentation_only_and_has_no_new_network_source():
    script = read("cb-phase4.js")
    lowered = script.lower()
    assert "typeof state" in lowered
    assert "fetch(" not in lowered
    assert "xmlhttprequest" not in lowered
    assert "websocket" not in lowered
    assert "eventsource" not in lowered
    assert "sportsbook" not in lowered
    assert "canonical" not in lowered
    assert "coefficient" not in lowered


def test_slate_pulse_uses_existing_projection_and_result_rows():
    script = read("cb-phase4.js")
    assert "appState()?.projections" in script
    assert "appState()?.results" in script
    assert "modelSpreadHome" in script
    assert "marketSpreadHome" in script
    assert "atsResult" in script
    assert "totalResult" in script
    assert "suResult" in script
    assert "Existing site data · no live API" in script
    assert "Model diff" in script
    assert "Recent grade" in script


def test_record_counter_animation_covers_all_v2_grade_cards_and_preserves_final_text():
    script = read("cb-phase4.js")
    assert "#recordTrackerV2 .rt-cards .record-card > strong" in script
    assert "const finalText = element.textContent.trim()" in script
    assert "element.textContent = finalText" in script
    assert "parseRecord" in script
    assert "recordText" in script


def test_phase_four_respects_reduced_motion_and_keeps_ticker_accessible():
    script = read("cb-phase4.js")
    css = read("cb-phase4.css")
    assert "prefers-reduced-motion: reduce" in script
    assert "@media (prefers-reduced-motion:reduce)" in css
    assert "aria-hidden=\"true\"" in script
    assert "aria-live=\"off\"" in script
    assert "animation-play-state:paused" in css


def test_phase_four_motion_stays_subtle_and_touch_safe():
    css = read("cb-phase4.css")
    assert "@media (hover:hover) and (pointer:fine)" in css
    assert "translateY(-2px)" in css
    assert "scale(.995)" in css
    assert ".cb-phase4-reveal" in css
    assert ".cb-phase4-visible" in css


def test_phase_four_does_not_modify_model_or_result_sources_by_design():
    script = read("cb-phase4.js")
    forbidden_assignments = (
        "STATE.projections =",
        "STATE.results =",
        "modelSpreadHome =",
        "marketSpreadHome =",
        "atsResult =",
        "totalResult =",
        "suResult =",
    )
    for token in forbidden_assignments:
        assert token not in script
