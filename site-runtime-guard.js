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

  function applyA11yState() {
    if (!isCompact()) {
      nav.removeAttribute('aria-hidden');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Open navigation');
      return;
    }
    const open = isOpen();
    nav.setAttribute('aria-hidden', String(!open));
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  }

  function closeNav({ focusToggle = false } = {}) {
    if (isOpen()) body.dataset.navOpen = 'false';
    applyA11yState();
    if (focusToggle && isCompact()) toggle.focus({ preventScroll: true });
  }

  // site-shell.js owns the primary toggle behavior. Run after that listener so
  // ARIA and background-scroll state always match the visual menu state.
  toggle.addEventListener('click', () => requestAnimationFrame(applyA11yState));

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
