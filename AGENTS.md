# CB Model Projections — Agent Instructions

These instructions apply to all coding/design agents working in this repository.

## Product and model integrity

CB Model Projections contains separate CFB and NFL predictive models. They share infrastructure and the public site, but model architecture, coefficients, frozen evidence, grading and promotion status remain league-specific.

Never change canonical model behavior, frozen projections, historical results, publication-time markets, validation status, feature promotion, or grading logic as part of a visual redesign unless the user explicitly asks for a model change and the project validation rules are satisfied.

Keep these layers visually and logically distinct:

1. Canonical model
2. Challenger/research models
3. External benchmarks/markets
4. Pregame context

Never imply that an outside model, sportsbook, injury note, trend, weather signal or other context is part of the canonical model unless it has been explicitly validated and promoted.

## Site stack

The production site must remain compatible with GitHub Pages.

- Static HTML
- CSS
- Vanilla JavaScript
- Existing JSON/CSV/site data
- Existing GitHub Actions

Do not introduce React, a build step, a framework migration, or a runtime dependency solely for redesign work.

## Design system

Read `SITE_DESIGN_SYSTEM.md` before changing the public UI.

The site should remain a premium football prediction research terminal: editorial enough to have identity, disciplined enough to scan quickly, and transparent enough to expose model state and evidence boundaries.

Kyma and Neiden remain visual inspiration. Taste-style dashboard discipline remains relevant. Apple HIG principles are an additional quality and accessibility review layer, not a mandate to make the site look like an Apple app.

## Apple design review layer

Read `APPLE_DESIGN_REVIEW.md` before substantial UI/UX work.

The upstream reference is `dickwu/apple-design-skill`, pinned for this integration to commit `ff4ebddf0488598723a82bfdce1afb04de0b1c44` (2026-10-28).

For substantial redesign/review tasks, consult the upstream `SKILL.md` plus the relevant HIG references when available. For this web product, prioritize transferable principles and foundations:

- accessibility
- layout and adaptability
- typography
- color and contrast
- dark/light appearance
- lists/tables and dense data presentation
- buttons, search fields and form controls
- feedback/loading/empty/error states
- motion/reduced motion
- writing and labels

Do not mechanically copy native iOS/macOS navigation conventions into the web app when normal web conventions are more appropriate.

## Required UI review questions

Before shipping a visual change, check:

- Does the most important information appear first and scan clearly?
- Is the interface still usable at narrow mobile widths and large text sizes?
- Are interactive controls comfortably tappable/clickable?
- Can keyboard users reach and identify interactive elements?
- Does any meaning depend on color alone?
- Are text/icon contrast and focus states sufficient in both themes?
- Does reduced-motion preference remove nonessential motion?
- Do loading, unavailable, empty and error states remain explicit rather than inferred?
- Do tables/cards preserve the difference between model, market, benchmark and context?
- Did the redesign leave model/data artifacts untouched unless explicitly intended?

## Change discipline

For redesign work:

1. Prefer a dedicated branch.
2. Preserve existing functionality unless replacement behavior is intentional.
3. Keep changes presentation-layer focused.
4. Add or update static integrity tests for important UI contracts.
5. Verify desktop and mobile behavior.
6. Verify both CFB and NFL views.
7. Do not merge stale branches over newer production/model commits.
