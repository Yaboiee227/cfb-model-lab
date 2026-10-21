(() => {
  const league = window.CB_ACTIVE_LEAGUE === 'nfl' ? 'nfl' : 'cfb';
  document.body.classList.add('site-v2');

  const q = selector => document.querySelector(selector);
  const label = value => String(value || '').replaceAll('_', ' ');

  function updateSharedBrand() {
    const small = q('.brand-copy small');
    if (small) small.textContent = 'Football prediction research';

    if (league === 'cfb') {
      document.title = 'CB Model Projections | CFB Research';
      const meta = q('meta[name="description"]');
      if (meta) meta.setAttribute('content', 'CB Model Projections: separate college football and NFL predictive research with frozen projections, market comparison, validation, and transparent grading.');
      const og = q('meta[property="og:description"]');
      if (og) og.setAttribute('content', 'Independent CFB and NFL predictive research with separate models, frozen weekly evidence, market comparison and transparent grading.');
    }

    const about = q('#about .about-grid > div:first-child p:last-child');
    if (about) about.textContent = 'CB Model Projections is the shared public interface for separate college football and NFL predictive models. Each league keeps its own architecture, coefficients, frozen projections, validation evidence and record while using one consistent research interface.';
  }

  function ensurePrimaryNav() {
    const nav = q('.primary-nav');
    if (!nav) return;
    const entries = [
      ['recap.html', 'Recap'],
      ['ratings.html', 'Ratings']
    ];
    const anchor = [...nav.querySelectorAll('a')].find(a => a.getAttribute('href') === '#methodology');
    for (const [href, text] of entries.reverse()) {
      if ([...nav.querySelectorAll('a')].some(a => a.getAttribute('href') === href)) continue;
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
    rail.setAttribute('aria-label', 'CB Model Projections product navigation');
    const state = league === 'cfb'
      ? 'CFB Week 8 · canonical publication HOLD · frozen research evidence preserved'
      : 'NFL Week 7 · Canonical V1 frozen prospectively · recommendations remain HOLD';
    rail.innerHTML = `
      <div class="cb-product-rail-inner">
        <div class="cb-product-rail-copy">
          <span class="cb-product-label">CB Model Projections</span>
          <span class="cb-product-state" id="cbProductState">${state}</span>
        </div>
        <nav class="cb-product-links" aria-label="Model sections">
          <a href="index.html" ${league === 'cfb' ? 'aria-current="page"' : ''}>CFB</a>
          <a href="index.html?league=nfl" ${league === 'nfl' ? 'aria-current="page"' : ''}>NFL</a>
          <a href="recap.html">Recap</a>
          <a href="ratings.html">Ratings</a>
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
      <div class="cb-layer-strip" aria-label="Model information layers">
        <article class="cb-layer-card" data-layer="model">
          <span class="cb-layer-kicker">01 · Model</span>
          <strong id="cbModelLayerTitle">${league === 'cfb' ? 'CFB canonical release' : 'NFL Canonical V1'}</strong>
          <p id="cbModelLayerCopy">${league === 'cfb' ? 'Publication remains on HOLD; frozen research outputs are preserved exactly as produced.' : 'The numerical model is frozen prospectively before games and graded after completion.'}</p>
          <span class="cb-layer-state" id="cbModelLayerState">${league === 'cfb' ? 'HOLD' : 'FROZEN'}</span>
        </article>
        <article class="cb-layer-card" data-layer="challenger">
          <span class="cb-layer-kicker">02 · Challenger</span>
          <strong>Research candidates</strong>
          <p>Alternative architectures may be tested historically and prospectively but never inherit production status automatically.</p>
          <span class="cb-layer-state" id="cbChallengerState">Shadow only</span>
        </article>
        <article class="cb-layer-card" data-layer="benchmark">
          <span class="cb-layer-kicker">03 · Benchmarks</span>
          <strong>Market + external ratings</strong>
          <p>Sportsbooks, Sagarin, SP+, RefMetrics and prediction markets are comparison evidence unless separately validated and promoted.</p>
          <span class="cb-layer-state">Reference only</span>
        </article>
        <article class="cb-layer-card" data-layer="context">
          <span class="cb-layer-kicker">04 · Context</span>
          <strong>Pregame information</strong>
          <p>Injuries, quarterbacks, weather, travel, coaching and availability are timestamped and kept distinct from the frozen numerical layer.</p>
          <span class="cb-layer-state">Pregame gated</span>
        </article>
      </div>
      <div class="cb-integrity-note" role="note">
        <strong>Integrity rule</strong>
        <span>Canonical, challenger, benchmark and contextual layers stay separate. Missing pregame information is never reconstructed after results, and completed games never rewrite the frozen projection that is graded.</span>
      </div>`;
    metrics.insertAdjacentElement('afterend', wrap);
  }

  function ensureFooterLinks() {
    const links = q('.footer-links');
    if (!links) return;
    const add = (href, text) => {
      if ([...links.querySelectorAll('a')].some(a => a.getAttribute('href') === href)) return;
      const a = document.createElement('a');
      a.href = href;
      a.textContent = text;
      links.insertBefore(a, links.lastElementChild);
    };
    add('recap.html', 'Recap');
    add('ratings.html', 'Ratings');
  }

  async function hydrateRegistry() {
    try {
      const response = await fetch('data/model-registry.json', { cache: 'no-store' });
      if (!response.ok) return;
      const registry = await response.json();
      if (league === 'cfb') {
        const cfb = registry.cfb || {};
        const canonical = cfb.canonical || {};
        const challenger = cfb.leadResearchChallenger || {};
        const state = q('#cbProductState');
        if (state) state.textContent = `CFB Week ${cfb.activeWeek || '—'} · canonical ${label(canonical.status || 'HOLD')} · research challenger ${label(challenger.tier || 'shadow')}`;
        const modelState = q('#cbModelLayerState');
        if (modelState) modelState.textContent = label(canonical.status || 'HOLD');
        const challengerState = q('#cbChallengerState');
        if (challengerState) challengerState.textContent = challenger.canonicalInfluence ? 'Canonical influence' : 'Zero canonical influence';
      } else {
        const nfl = registry.nfl || {};
        const canonical = nfl.canonical || {};
        const state = q('#cbProductState');
        if (state) state.textContent = `NFL Week ${nfl.activeProspectiveWeek || '—'} · ${label(canonical.modelId || 'Canonical V1')} · ${label(canonical.status || 'frozen prospective')}`;
        const modelState = q('#cbModelLayerState');
        if (modelState) modelState.textContent = canonical.canonicalChanged ? 'Changed' : 'Frozen';
        const challengerState = q('#cbChallengerState');
        if (challengerState) challengerState.textContent = 'Week 6 failure analysis preserved';
      }
    } catch (_) {
      // Static UI remains usable even if the registry is temporarily unavailable.
    }
  }

  function updateActiveCopy() {
    if (league === 'cfb') return;
    const statusNote = q('main > .section-shell .hold-note');
    if (statusNote && statusNote.closest('#home') == null) {
      statusNote.innerHTML = '<strong>NFL · Prospective research</strong> — Canonical V1 is frozen weekly. Market differences, win probability and reliability remain research outputs; recommendation thresholds are still on HOLD.';
    }
  }

  function init() {
    updateSharedBrand();
    ensurePrimaryNav();
    ensureProductRail();
    ensureLayerStrip();
    ensureFooterLinks();
    updateActiveCopy();
    hydrateRegistry();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
