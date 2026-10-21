# CB Model Projections — Site Design System

## Product idea

CB Model Projections is a football prediction research product, not a sportsbook landing page and not a generic SaaS dashboard. The public interface should feel like an editorial research terminal: expressive enough to have an identity, disciplined enough to scan quickly, and transparent enough to expose model state and evidence boundaries.

The visual direction takes inspiration from the editorial hierarchy and atmosphere of the Kyma and Neiden references supplied for the redesign, while applying the data-density and restraint principles reviewed from Taste Skill. Design Extract is treated as a QA concept/tooling reference rather than a production dependency. React Bits is inspiration only; the site stays static HTML/CSS/vanilla JavaScript for GitHub Pages.

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

The redesign must remain compatible with GitHub Pages: no React conversion, no build requirement, and no runtime dependency on the inspiration repositories. The existing data files, frozen artifacts and production workflows remain the source of truth.
