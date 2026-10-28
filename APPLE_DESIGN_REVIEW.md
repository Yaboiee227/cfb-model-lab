# Apple Design Review Layer for CB Model Projections

## Purpose

This file adapts the transferable parts of Apple's Human Interface Guidelines to the CB Model Projections web product.

The goal is **not** to make the site imitate iOS or macOS. The goal is to use Apple's strongest design principles—clarity, adaptability, accessibility, restraint, familiar interaction and craft—to improve the existing football research interface.

Upstream design-review reference:

- Repository: `dickwu/apple-design-skill`
- Integration baseline: commit `ff4ebddf0488598723a82bfdce1afb04de0b1c44`
- Upstream source material points back to Apple's public Human Interface Guidelines.

This is a review standard only. It is not shipped as a website dependency and does not alter model calculations.

## What applies to this website

Because CB Model Projections is a responsive web app rather than a native Apple app, use Apple's design principles and foundation guidance where they translate well to the web:

### 1. Purpose and hierarchy

Every screen needs a clear primary job.

For the main page, that job is to answer:

> What does the model project, what does the market show, and what pregame evidence should be audited before trusting the comparison?

The projection board should remain the dominant working surface. Supporting context should be available without competing with it.

### 2. Adaptability

The same information and core actions must remain available across desktop and mobile. Layout may change, functionality should not disappear simply because the viewport is smaller.

Responsive rules should be based on available space rather than assumptions about a particular device.

Large text must not cause controls, table labels or important status text to overlap or clip. When horizontal layouts become too tight, stack them rather than compressing them into unreadable rows.

### 3. Accessibility

Treat accessibility defects as release-blocking UI issues when they prevent someone from perceiving or operating the interface.

For the web implementation:

- Aim for WCAG AA contrast for normal text and controls.
- Do not use color as the only signal for HOLD, success, loss, model, market or benchmark state.
- Preserve semantic labels for icon-only controls.
- Ensure keyboard focus is visible.
- Keep tab order logical.
- Give interactive controls comfortable hit areas; mobile controls should generally target roughly 44px or more where practical.
- Avoid tiny/light type for essential information.
- Make layouts survive browser zoom and enlarged text.
- Respect `prefers-reduced-motion`.

### 4. Typography

Use type to create hierarchy, not decoration.

- Large display typography is appropriate for product identity and section entry points.
- Dense projection data should use restrained, highly readable type.
- Avoid excessive tracking in body copy or numerical data.
- Use weight, size, spacing and alignment consistently so model values, market values and metadata scan predictably.

### 5. Color and appearance

Color belongs primarily on information rather than chrome.

Preserve CB's semantic system:

- lime = model
- cyan = market/benchmark comparison
- violet = challenger/research
- amber = HOLD/uncertainty/context gating
- green/red = completed positive/negative outcomes and explicit success/error states

Every important state also needs text, iconography, borders or another non-color cue.

Both dark and light appearances should preserve hierarchy and contrast. The site may provide its own appearance control because this is a web product; it should still respect system preference as the default when possible.

### 6. Controls and interaction

Controls should look interactive without overpowering the data.

- Primary actions should be visually distinct but limited in number.
- Filters should use consistent labels and spacing.
- Search should remain easy to find when it materially improves slate navigation.
- Hover, focus, active and disabled states must be visually clear.
- Destructive actions should not be visually confused with navigation or normal filtering.
- Important functions should not require a gesture without an obvious clickable/tappable alternative.

### 7. Lists, tables and dense data

Projection tables and record tables are core product surfaces, not decoration.

- Align related numbers consistently.
- Right-align numerical columns where it improves comparison.
- Keep row separators subtle but visible.
- Avoid visual effects that reduce scan speed.
- Make headers remain understandable during horizontal scrolling.
- Use mobile cards/drawers only when they preserve the same information hierarchy as the desktop table.
- Missing data should display as unavailable/unknown rather than inferred.

### 8. Feedback, loading and empty states

Every asynchronous or data-dependent surface should answer what is happening.

Use explicit states for:

- loading
- no games matching filters
- missing market reference
- unavailable benchmark data
- stale context
- validation HOLD
- data load error

Do not leave blank panels that look broken.

### 9. Motion and materials

Motion should clarify state changes or hierarchy, not advertise itself.

- Avoid persistent or looping animation near projection data.
- Prefer short transitions for navigation, drawers and disclosure.
- Disable nonessential animation for reduced-motion users.
- Blur/translucency may be used sparingly on navigation or floating functional layers; content surfaces should remain stable and readable.

### 10. Writing and labels

Labels should describe what a control or number actually does.

Prefer:

- `Model / market difference` over language that implies guaranteed edge.
- `Research only`, `HOLD`, `Benchmark`, `Context`, and `Frozen` where those are the actual states.
- Explicit timestamps and provenance when freshness matters.

Avoid language that visually upgrades research output into a recommendation or canonical release.

## CB-specific review order

For any substantial redesign, review in this order:

1. Model-integrity boundary failures
2. Accessibility and operability
3. Information hierarchy
4. Responsive behavior
5. Projection-table scan quality
6. Control clarity and filter UX
7. Loading/error/empty states
8. Dark/light appearance
9. Motion and polish
10. Brand expression

## Required screen set

At minimum, verify:

- CFB desktop main page
- CFB mobile main page
- NFL desktop main page
- NFL mobile main page
- Projection board with populated data
- Projection board with filters producing no results
- Matchup inspector/drawer
- Record/performance section
- Research section
- Recap & Validation page
- Ratings & Benchmarks page
- Dark appearance
- Light appearance
- Keyboard-only navigation
- Reduced-motion mode

## What not to do

Do not:

- convert the site to React or another framework just to use an Apple-style component library
- install the Apple Design Skill as a production dependency
- copy Apple's visual identity, branding, product chrome or native components literally
- replace CB's football/research identity with generic glassmorphism
- reduce data density so far that weekly model work becomes slower
- hide poor model results
- merge benchmark or contextual evidence into canonical presentation
- reconstruct missing pregame information after games

## How to use the upstream skill during redesign work

When the upstream skill is available to the working agent, read its `SKILL.md` first, then load only the relevant guideline files for the current task. For CB's main site, the most useful references are typically:

- `accessibility.md`
- `layout.md`
- `typography.md`
- `color.md`
- `dark-mode.md`
- `lists-and-tables.md`
- `buttons.md`
- `search-fields.md`
- `loading.md`
- `feedback.md`
- `motion.md`
- `writing.md`

Use Apple-specific platform rules only when the underlying principle clearly improves the responsive web experience.
