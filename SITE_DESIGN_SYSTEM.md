# CB Model Projections — Site Design System

## Product idea

CB Model Projections is a football prediction research product, not a sportsbook landing page and not a generic SaaS dashboard. The public interface should feel like an editorial research terminal: expressive enough to have an identity, disciplined enough to scan quickly, and transparent enough to expose model state and evidence boundaries.

The visual direction takes inspiration from the editorial hierarchy and atmosphere of the Kyma and Neiden references supplied for the redesign, while applying the data-density and restraint principles reviewed from Taste Skill. Design Extract is treated as a QA concept/tooling reference rather than a production dependency. React Bits is inspiration only; the site stays static HTML/CSS/vanilla JavaScript for GitHub Pages.

Apple's Human Interface Guidelines are used as an additional review layer for accessibility, adaptability, typography, color, controls, motion, feedback and design craft. They are not used to make the site visually imitate iOS or macOS. See `APPLE_DESIGN_REVIEW.md` for the web-specific translation and `AGENTS.md` for the rules future coding/design agents must follow.

## Non-negotiable model boundaries

The interface must never visually blur these layers:

1. **Canonical** — the explicitly approved production model for that league.
2. **Challenger** — research candidates with zero canonical influence until validated and promoted.
3. **Benchmark** — sportsbooks, external ratings/models, prediction markets and comparison sources.
4. **Context** — timestamped pregame information such as injuries, quarterbacks, weather, travel and coaching.

No visual treatment may imply that a benchmark or contextual input is part of the canonical numerical model unless project evidence and explicit promotion say it is.

## Visual language

- Background: near-black midnight surface with a very low-contrast technical grid.
- Model data: lime.
- Market comparison: cyan.
- Challenger research: soft violet.
- HOLD / uncertainty / contextual gating: amber.
- Red/green are reserved primarily for completed outcomes and explicit error/success states.
- Navigation and containers should recede. Color belongs on information more than on chrome.
- Cards are used only where grouping is meaningful. Tables, status summaries and methodology sequences prefer borders and alignment over floating shadows.
- Large typography is reserved for identity and section hierarchy. Projection tables, timestamps and audit metadata remain compact.
- Important meaning must never depend on color alone; use labels, icons, borders or structure as secondary cues.

## Section rhythm

The main product uses coded section labels as a repeatable identity device:

- 01 · Projections
- 02 · Performance
- 03 · Research
- 04 · Trends (NFL when available)
- 05 · Methodology
- 06 · Glossary
- 07 · Support
- 08 · About

Recap and benchmark pages use the same numbered editorial convention.

## CFB / NFL architecture

CFB and NFL share the presentation system but remain separate predictive products. The league selector changes the underlying site data and language while preserving a common interaction model.

- CFB data routes through the existing `data/` and `cfb/` resources.
- NFL data routes through `nfl_data/site/` via the existing league bootstrap.
- Bookmarks remain league-isolated.
- Model registries and frozen snapshots determine the displayed state; the design layer does not invent production status.

## Interaction rules

- Desktop tables remain the primary dense view; mobile uses readable cards/drawers.
- Filters, priority games, matchup inspection, exports, theme control and research tools remain functional.
- Motion is brief and structural only. No persistent animation competes with data.
- Reduced-motion preferences are respected.
- Mobile navigation collapses instead of forcing a horizontally scrolling header.
- Missing values display honestly as unavailable rather than being inferred.
- Keyboard focus must remain visible and navigation order must be logical.
- Mobile controls should have comfortable touch targets; roughly 44px is the working target where practical.
- Layouts should survive browser zoom, enlarged text and narrow widths without clipping essential content.
- Empty, loading, stale and error states should be explicit rather than appearing as blank or broken surfaces.

## Apple/HIG review layer

Apple's design principles are used as a quality filter, especially where they map cleanly to responsive web design:

- **Purpose** — every screen should have one obvious primary job.
- **Agency** — users can filter, inspect, reset and recover without being trapped in a flow.
- **Responsibility** — model state, uncertainty, provenance and research-only status remain explicit.
- **Familiarity** — common web interaction patterns are preferred over novel controls that need explanation.
- **Flexibility** — the same core information and actions work across screen sizes, input types and larger text.
- **Simplicity** — chrome recedes behind the data.
- **Craft** — spacing, alignment, labels, focus states and motion are deliberate.
- **Delight** — personality comes from the CB research-terminal identity rather than decorative effects that reduce scan speed.

Apple-specific native navigation conventions are not copied mechanically. For a web product, the underlying principle wins over literal platform imitation.

## Page roles

### Main projection app

Answers: **What does the model project this week, what does the market show, and what information should I audit before trusting the comparison?**

### Recap & Validation

Answers: **What actually happened, how was it graded, and what is the current canonical/challenger validation state?**

Poor results remain visible. Current-week ungraded research does not silently enter the completed record.

### Ratings & Benchmarks

Answers: **What outside comparison evidence is available, and how does it differ from the CB canonical layer?**

For CFB, the preserved Sagarin snapshot is explicitly external benchmark evidence. For NFL, the page compares the frozen canonical spread with the public market benchmark and shadow challenger where available.

## Deployment constraint

The redesign must remain compatible with GitHub Pages: no React conversion, no build requirement, and no runtime dependency on the inspiration repositories or the Apple Design Skill. The existing data files, frozen artifacts and production workflows remain the source of truth.
