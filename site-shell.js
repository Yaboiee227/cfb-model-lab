(() => {
  const league = window.CB_ACTIVE_LEAGUE === 'nfl' ? 'nfl' : 'cfb';
  const q = selector => document.querySelector(selector);
  const qa = selector => [...document.querySelectorAll(selector)];
  const label = value => String(value || '').replaceAll('_', ' ');
  const leagueQuery = league === 'nfl' ? '?league=nfl' : '';

  document.body.classList.add('site-v2');
  document.body.dataset.navOpen = 'false';

  function updateSharedBrand() {
    const small = q('.brand-copy small');
    if (small) small.textContent = 'Football prediction research';

    document.title = `CB Model Projections | ${league === 'nfl' ? 'NFL' : 'CFB'} Research`;
    const meta = q('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'CB Model Projections: separate CFB and NFL predictive models with frozen projections, market comparison, validation evidence, research context and transparent grading.');
    const og = q('meta[property="og:description"]');
    if (og) og.setAttribute('content', 'Independent CFB and NFL predictive research with separate models, frozen weekly evidence, market comparison and transparent grading.');

    const about = q('#about .about-grid > div:first-child p:last-child');
    if (about) about.textContent = 'CB Model Projections is the shared public interface for separate college football and NFL predictive models. Each league keeps its own architecture, coefficients, frozen projections, validation evidence and grading record while using one consistent research interface.';
  }

  function ensureMobileNav() {
    const header = q('.header-inner');
    const nav = q('.primary-nav');
    if (!header || !nav || q('#cbMobileNavToggle')) return;
    const button = document.createElement('button');
    button.id = 'cbMobileNavToggle';
    button.className = 'cb-mobile-nav-toggle';
    button.type = 'button';
    button.setAttribute('aria-label', 'Open navigation');
    button.setAttribute('aria-controls', 'cbPrimaryNav');
    button.setAttribute('aria-expanded', 'false');
    button.innerHTML = '<span aria-hidden="true"></span>';
    nav.id = 'cbPrimaryNav';
    const leagueSwitch = q('#leagueSwitch');
    header.insertBefore(button, leagueSwitch || q('#themeToggle'));
    button.addEventListener('click', () => {
      const open = document.body.dataset.navOpen !== 'true';
      document.body.dataset.navOpen = String(open);
      button.setAttribute('aria-expanded', String(open));
      button.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });
    nav.addEventListener('click', event => {
      if (!event.target.closest('a')) return;
      document.body.dataset.navOpen = 'false';
      button.setAttribute('aria-expanded', 'false');
      button.setAttribute('aria-label', 'Open navigation');
    });
  }

  function ensurePrimaryNav() {
    const nav = q('.primary-nav');
    if (!nav) return;

    const weekLink = qa('.primary-nav a').find(a => a.getAttribute('href') === 'week-8.html');
    if (weekLink && league === 'nfl') {
      weekLink.href = `recap.html${leagueQuery}`;
      weekLink.textContent = 'Validation';
    }

    const entries = [
      [`recap.html${leagueQuery}`, 'Recap'],
      [`ratings.html${leagueQuery}`, league === 'nfl' ? 'Benchmarks' : 'Ratings']
    ];
    const anchor = qa('.primary-nav a').find(a => a.getAttribute('href') === '#methodology');
    for (const [href, text] of entries.reverse()) {
      if (qa('.primary-nav a').some(a => a.textContent.trim() === text || a.getAttribute('href') === href)) continue;
      const a = document.createElement('a');
      a.href = href;
      a.textContent = text;
      anchor ? nav.insertBefore(a, anchor) : nav.appendChild(a);
    }
  }

  function ensureProductRail() {
    const main = q('main');
    if (!main || q('#cbProductRail')) return;
    const rail = document.createElement('section');
    rail.id = 'cbProductRail';
    rail.className = 'section-shell cb-product-rail';
    rail.setAttribute('aria-label', 'CB Model Projections model navigation');
    rail.innerHTML = `
      <div class="cb-product-rail-inner">
        <div class="cb-product-rail-copy">
          <span class="cb-product-label">Active system</span>
          <span class="cb-product-state" id="cbProductState">Loading preserved model state…</span>
        </div>
        <nav class="cb-product-links" aria-label="Model sections">
          <a href="index.html" ${league === 'cfb' ? 'aria-current="page"' : ''}>CFB</a>
          <a href="index.html?league=nfl" ${league === 'nfl' ? 'aria-current="page"' : ''}>NFL</a>
          <a href="recap.html${leagueQuery}">Recap</a>
          <a href="ratings.html${leagueQuery}">${league === 'nfl' ? 'Benchmarks' : 'Ratings'}</a>
        </nav>
      </div>`;
    main.insertBefore(rail, main.firstChild);
  }

  function ensureLayerStrip() {
    const hero = q('#home');
    const metrics = q('#home .hero-metrics');
    if (!hero || !metrics || q('#cbLayerStrip')) return;
    const wrap = document.createElement('div');
    wrap.id = 'cbLayerStrip';
    wrap.innerHTML = `
      <div class="cb-layer-strip" aria-label="Prediction evidence architecture">
        <article class="cb-layer-card" data-layer="model">
          <span class="cb-layer-kicker">01 · Canonical</span>
          <strong id="cbModelLayerTitle">${league === 'cfb' ? 'CFB canonical model' : 'NFL Canonical V1'}</strong>
          <p id="cbModelLayerCopy">The production model is the only layer allowed to generate canonical projections. Its weekly state is frozen and graded without postgame reconstruction.</p>
          <span class="cb-layer-state" id="cbModelLayerState">Loading state</span>
        </article>
        <article class="cb-layer-card" data-layer="challenger">
          <span class="cb-layer-kicker">02 · Challenger</span>
          <strong>Research candidates</strong>
          <p>Alternative architectures and features can earn evidence prospectively, but they never inherit production status automatically.</p>
          <span class="cb-layer-state" id="cbChallengerState">Shadow only</span>
        </article>
        <article class="cb-layer-card" data-layer="benchmark">
          <span class="cb-layer-kicker">03 · Benchmark</span>
          <strong>Markets + external ratings</strong>
          <p>Sportsbooks, Sagarin, SP+, RefMetrics and prediction markets remain comparison evidence unless separately validated and promoted.</p>
          <span class="cb-layer-state">Reference only</span>
        </article>
        <article class="cb-layer-card" data-layer="context">
          <span class="cb-layer-kicker">04 · Context</span>
          <strong>Pregame information</strong>
          <p>Injuries, quarterbacks, weather, travel, coaching and availability are timestamped and kept distinct from frozen numerical evidence.</p>
          <span class="cb-layer-state">Pregame gated</span>
        </article>
      </div>
      <div class="cb-integrity-note" role="note">
        <strong>Integrity rule</strong>
        <span>Canonical, challenger, benchmark and contextual layers stay separate. Missing pregame information is never reconstructed after results, and completed games never rewrite the frozen projection being graded.</span>
      </div>`;
    metrics.insertAdjacentElement('afterend', wrap);
  }

  function numberSections() {
    const sections = [
      ['projections', '01 · PROJECTIONS'],
      ['record', '02 · PERFORMANCE'],
      ['research', '03 · RESEARCH'],
      ['trends', '04 · TRENDS'],
      ['methodology', '05 · METHODOLOGY'],
      ['glossary', '06 · GLOSSARY'],
      ['support', '07 · SUPPORT'],
      ['about', '08 · ABOUT']
    ];
    sections.forEach(([id, text]) => {
      const section = q(`#${id}`);
      const heading = section?.querySelector(':scope > .section-heading');
      if (!section || !heading) return;
      section.dataset.sectionIndex = text.split(' · ')[0];
      heading.dataset.sectionLabel = text;
    });
  }

  function ensureFooterLinks() {
    const links = q('.footer-links');
    if (!links) return;
    const add = (href, text) => {
      if (qa('.footer-links a').some(a => a.textContent.trim() === text)) return;
      const a = document.createElement('a');
      a.href = href;
      a.textContent = text;
      links.insertBefore(a, links.lastElementChild);
    };
    add(`recap.html${leagueQuery}`, 'Recap');
    add(`ratings.html${leagueQuery}`, league === 'nfl' ? 'Benchmarks' : 'Ratings');
  }

  function updateStaticCopy() {
    const topNote = q('main > .section-shell .hold-note');
    if (topNote && !topNote.closest('#home')) {
      topNote.innerHTML = league === 'cfb'
        ? '<strong>CFB · Week 8 production state</strong> — Canonical publication remains gated. Current pregame research, market locks and frozen evidence are preserved without reconstructing information after results. <a href="week-8.html">Open Week 8 audit →</a>'
        : `<strong>NFL · Week 7 prospective state</strong> — Canonical V1 is frozen weekly. Market differences, reliability and contextual evidence remain research outputs while recommendation thresholds stay on HOLD. <a href="recap.html${leagueQuery}">Open validation recap →</a>`;
    }

    const heroTitle = q('#heroTitle');
    if (heroTitle && league === 'cfb') heroTitle.innerHTML = 'Project the game.<br><span>Preserve the evidence.</span>';
    const heroLede = q('.hero-lede');
    if (heroLede && league === 'cfb') heroLede.textContent = 'Independent FBS projections for score, spread, total and win probability—paired with market comparison, input quality and timestamped pregame context, with every layer kept auditable.';

    const footer = q('#footerDisclaimer');
    if (footer) footer.textContent = 'CB Model Projections is independent research. Projections, market comparisons and model differences are not official wager recommendations. Historical and prospective results are graded honestly, including poor performance. Past performance does not guarantee future results.';
  }

  function installReveal() {
    if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const targets = qa('main > section').filter(section => section.id !== 'cbProductRail');
    targets.forEach(section => section.classList.add('cb-reveal'));
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('cb-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: .05, rootMargin: '0px 0px -8% 0px' });
    targets.forEach(section => observer.observe(section));
  }

  async function hydrateRegistry() {
    try {
      const response = await fetch('data/model-registry.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('registry unavailable');
      const registry = await response.json();
      const state = q('#cbProductState');
      const modelState = q('#cbModelLayerState');
      const challengerState = q('#cbChallengerState');

      if (league === 'cfb') {
        const cfb = registry.cfb || {};
        const canonical = cfb.canonical || {};
        const challenger = cfb.leadResearchChallenger || {};
        if (state) state.textContent = `CFB Week ${cfb.activeWeek || '—'} · canonical ${label(canonical.status || 'HOLD')} · challenger ${label(challenger.tier || 'shadow')}`;
        if (modelState) modelState.textContent = label(canonical.status || 'HOLD');
        if (challengerState) challengerState.textContent = challenger.canonicalInfluence ? 'Canonical influence' : 'Zero canonical influence';
      } else {
        const nfl = registry.nfl || {};
        const canonical = nfl.canonical || {};
        if (state) state.textContent = `NFL Week ${nfl.activeProspectiveWeek || '—'} · ${label(canonical.modelId || 'Canonical V1')} · ${label(canonical.status || 'frozen prospective')}`;
        if (modelState) modelState.textContent = canonical.canonicalChanged ? 'Changed' : 'Frozen prospective';
        if (challengerState) challengerState.textContent = 'Failure analysis / shadow testing only';
      }
    } catch (_) {
      const state = q('#cbProductState');
      if (state) state.textContent = `${league.toUpperCase()} · registry temporarily unavailable · static research interface active`;
    }
  }

  function init() {
    updateSharedBrand();
    ensurePrimaryNav();
    ensureMobileNav();
    ensureProductRail();
    ensureLayerStrip();
    numberSections();
    ensureFooterLinks();
    updateStaticCopy();
    hydrateRegistry();
    installReveal();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
