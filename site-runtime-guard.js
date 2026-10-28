(() => {
  if (window.__CB_SITE_RUNTIME_GUARD) return;
  window.__CB_SITE_RUNTIME_GUARD = true;

  const BREAKPOINT = 1180;
  const body = document.body;
  const header = document.querySelector('.site-header');
  const toggle = document.getElementById('cbMobileNavToggle');
  const nav = document.getElementById('cbPrimaryNav') || document.querySelector('.primary-nav');
  if (!body || !header || !toggle || !nav) return;

  toggle.setAttribute('aria-haspopup', 'true');

  const isCompact = () => window.innerWidth <= BREAKPOINT;
  const isOpen = () => body.dataset.navOpen === 'true';
  let syncFrame = 0;

  const setAttr = (el, name, value) => {
    if (el.getAttribute(name) !== value) el.setAttribute(name, value);
  };

  function applyA11yState() {
    if (!isCompact()) {
      if (nav.hasAttribute('aria-hidden')) nav.removeAttribute('aria-hidden');
      setAttr(toggle, 'aria-expanded', 'false');
      setAttr(toggle, 'aria-label', 'Open navigation');
      return;
    }
    const open = isOpen();
    setAttr(nav, 'aria-hidden', String(!open));
    setAttr(toggle, 'aria-expanded', String(open));
    setAttr(toggle, 'aria-label', open ? 'Close navigation' : 'Open navigation');
  }

  function scheduleSync() {
    cancelAnimationFrame(syncFrame);
    syncFrame = requestAnimationFrame(applyA11yState);
  }

  function closeNav({ focusToggle = false } = {}) {
    if (isOpen()) body.dataset.navOpen = 'false';
    applyA11yState();
    if (focusToggle && isCompact()) toggle.focus({ preventScroll: true });
  }

  // site-shell.js owns the visual state. This guard keeps accessibility state
  // synchronized even when later CFB-only modules mutate the header DOM.
  toggle.addEventListener('click', scheduleSync);

  nav.addEventListener('click', event => {
    if (!event.target.closest('a')) return;
    requestAnimationFrame(() => closeNav());
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && isCompact() && isOpen()) {
      event.preventDefault();
      closeNav({ focusToggle: true });
    }
  });

  document.addEventListener('pointerdown', event => {
    if (!isCompact() || !isOpen()) return;
    if (header.contains(event.target)) return;
    closeNav();
  }, { passive: true });

  window.addEventListener('hashchange', () => closeNav());

  const stateObserver = new MutationObserver(mutations => {
    if (mutations.some(m =>
      (m.target === body && m.attributeName === 'data-nav-open') ||
      (m.target === nav && m.attributeName === 'aria-hidden') ||
      (m.target === toggle && m.attributeName === 'aria-expanded')
    )) scheduleSync();
  });
  stateObserver.observe(body, { attributes: true, attributeFilter: ['data-nav-open'] });
  stateObserver.observe(nav, { attributes: true, attributeFilter: ['aria-hidden'] });
  stateObserver.observe(toggle, { attributes: true, attributeFilter: ['aria-expanded'] });

  let resizeFrame = 0;
  window.addEventListener('resize', () => {
    cancelAnimationFrame(resizeFrame);
    resizeFrame = requestAnimationFrame(() => {
      if (!isCompact()) body.dataset.navOpen = 'false';
      applyA11yState();
    });
  }, { passive: true });

  applyA11yState();
})();

(() => {
  if (document.querySelector('script[data-cb-foundation]')) return;
  const script = document.createElement('script');
  script.src = 'cb-foundation.js?v=20261028-phase1';
  script.async = false;
  script.dataset.cbFoundation = 'true';
  document.body.appendChild(script);
})();

(() => {
  if (window.__CB_PHASE2_ASSET_LOADER) return;
  window.__CB_PHASE2_ASSET_LOADER = true;

  const version = '20261028-phase2';
  const addCss = href => {
    if (document.querySelector(`link[data-cb-phase2-asset="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${href}?v=${version}`;
    link.dataset.cbPhase2Asset = href;
    document.head.appendChild(link);
  };
  const loadScript = src => new Promise((resolve, reject) => {
    if (document.querySelector(`script[data-cb-phase2-asset="${src}"]`)) return resolve();
    const script = document.createElement('script');
    script.src = `${src}?v=${version}`;
    script.async = false;
    script.dataset.cbPhase2Asset = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.body.appendChild(script);
  });

  addCss('cb-team-visuals.css');
  addCss('cb-game-cards.css');

  window.CB_PHASE2_READY = (async () => {
    await loadScript('assets/teams/team-assets.js');
    await loadScript('cb-team-visuals.js');
    await loadScript('cb-game-cards.js');
  })().catch(error => console.error('CB Phase 2 asset load failed', error));
})();

(() => {
  if (window.__CB_PHASE3_ASSET_LOADER) return;
  window.__CB_PHASE3_ASSET_LOADER = true;

  const version = '20261028-phase3';
  const addCss = href => {
    if (document.querySelector(`link[data-cb-phase3-asset="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${href}?v=${version}`;
    link.dataset.cbPhase3Asset = href;
    document.head.appendChild(link);
  };
  const loadScript = src => new Promise((resolve, reject) => {
    if (document.querySelector(`script[data-cb-phase3-asset="${src}"]`)) return resolve();
    const script = document.createElement('script');
    script.src = `${src}?v=${version}`;
    script.async = false;
    script.dataset.cbPhase3Asset = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.body.appendChild(script);
  });

  addCss('cb-phase3.css');
  window.CB_PHASE3_READY = (async () => {
    if (window.CB_PHASE2_READY) await window.CB_PHASE2_READY;
    await loadScript('cb-phase3.js');
    await loadScript('cb-phase3-link-integrity.js');
  })().catch(error => console.error('CB Phase 3 asset load failed', error));
})();

(() => {
  if (window.__CB_PHASE4_ASSET_LOADER) return;
  window.__CB_PHASE4_ASSET_LOADER = true;

  const version = '20261028-phase4';
  const addCss = href => {
    if (document.querySelector(`link[data-cb-phase4-asset="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `${href}?v=${version}`;
    link.dataset.cbPhase4Asset = href;
    document.head.appendChild(link);
  };
  const loadScript = src => new Promise((resolve, reject) => {
    if (document.querySelector(`script[data-cb-phase4-asset="${src}"]`)) return resolve();
    const script = document.createElement('script');
    script.src = `${src}?v=${version}`;
    script.async = false;
    script.dataset.cbPhase4Asset = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.body.appendChild(script);
  });

  addCss('cb-phase4.css');
  window.CB_PHASE4_READY = (async () => {
    if (window.CB_PHASE3_READY) await window.CB_PHASE3_READY;
    await loadScript('cb-phase4.js');
  })().catch(error => console.error('CB Phase 4 asset load failed', error));
})();
