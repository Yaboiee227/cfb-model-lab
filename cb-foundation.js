(() => {
  const q = selector => document.querySelector(selector);
  const qa = selector => [...document.querySelectorAll(selector)];
  const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const systemDark = window.matchMedia?.('(prefers-color-scheme: dark)');

  function setThemeColor(theme) {
    const meta = q('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#202329' : '#F7F7F4');
  }

  function applySystemTheme() {
    if (localStorage.getItem('cb-theme-mode') === 'manual') return;
    const theme = systemDark?.matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    localStorage.removeItem('cb-theme');
    setThemeColor(theme);
  }

  function installThemeBehavior() {
    if (!localStorage.getItem('cb-theme-mode')) {
      localStorage.setItem('cb-theme-mode', 'system');
      localStorage.removeItem('cb-theme');
    }

    if (localStorage.getItem('cb-theme-mode') !== 'manual') applySystemTheme();
    else setThemeColor(document.documentElement.dataset.theme || 'dark');

    systemDark?.addEventListener?.('change', () => {
      if (localStorage.getItem('cb-theme-mode') !== 'manual') applySystemTheme();
    });

    document.addEventListener('click', event => {
      if (!event.target.closest('#themeToggle')) return;
      localStorage.setItem('cb-theme-mode', 'manual');
    }, true);
  }

  function ensureFavicon() {
    let icon = q('link[rel~="icon"]');
    if (!icon) {
      icon = document.createElement('link');
      icon.rel = 'icon';
      document.head.appendChild(icon);
    }
    icon.type = 'image/png';
    icon.href = 'assets/brand/cb-favicon.png';
  }

  function brandHeader() {
    qa('.brand-mark').forEach(mark => {
      mark.textContent = '';
      mark.setAttribute('aria-hidden', 'true');
      mark.dataset.cbBrand = 'true';
    });

    const homeBrand = q('.site-header .brand');
    if (homeBrand) {
      homeBrand.setAttribute('aria-label', 'CB Model Projections home');
      const href = homeBrand.getAttribute('href') || '';
      if (href === '#home') homeBrand.href = '#home';
    }
  }

  function reorderPrimaryNav() {
    const nav = q('.primary-nav');
    if (!nav) return;
    const links = qa('.primary-nav a');
    const score = link => {
      const text = link.textContent.trim().toLowerCase();
      const href = link.getAttribute('href') || '';
      if (text.includes('projection') || href === '#projections') return 10;
      if (text === 'research' || href === '#research') return 20;
      if (text === 'recap') return 30;
      if (text.includes('rating') || text.includes('benchmark')) return 40;
      if (text === 'record' || href === '#record') return 50;
      if (text.includes('methodology') || href === '#methodology') return 60;
      if (text.includes('glossary') || href === '#glossary') return 70;
      if (text.includes('support') || href === '#support') return 80;
      if (text.includes('about') || href === '#about') return 90;
      if (/week\s*\d|archive/.test(text)) return 100;
      return 95;
    };
    links.sort((a, b) => score(a) - score(b)).forEach(link => nav.appendChild(link));
  }

  function leagueTarget(next) {
    const url = new URL(location.href);
    if (next === 'nfl') url.searchParams.set('league', 'nfl');
    else url.searchParams.delete('league');
    url.searchParams.delete('game');
    return url.toString();
  }

  function installLeagueTransitions() {
    document.addEventListener('click', event => {
      const button = event.target.closest('.league-switch button[data-league]');
      const anchor = event.target.closest('.league-switch a');
      if (!button && !anchor) return;

      let target;
      let next;
      if (button) {
        next = button.dataset.league;
        if (!next || next === window.CB_ACTIVE_LEAGUE) return;
        target = leagueTarget(next);
      } else {
        target = anchor.href;
        const parsed = new URL(target);
        next = parsed.searchParams.get('league') === 'nfl' ? 'nfl' : 'cfb';
        const current = new URL(location.href).searchParams.get('league') === 'nfl' ? 'nfl' : 'cfb';
        if (next === current) return;
      }

      event.preventDefault();
      event.stopImmediatePropagation();
      localStorage.setItem('cb-active-league', next);

      if (reducedMotion()) {
        location.href = target;
        return;
      }

      document.documentElement.classList.add('cb-league-transition');
      window.setTimeout(() => { location.href = target; }, 120);
    }, true);
  }

  function installBrandLoader() {
    if (document.readyState === 'complete' || q('#cbBrandLoader')) return;
    let shown = false;
    const loader = document.createElement('div');
    loader.id = 'cbBrandLoader';
    loader.className = 'cb-brand-loader';
    loader.setAttribute('aria-hidden', 'true');

    const showTimer = window.setTimeout(() => {
      if (document.readyState === 'complete') return;
      document.body.appendChild(loader);
      shown = true;
    }, 160);

    const dismiss = () => {
      window.clearTimeout(showTimer);
      if (!shown || !loader.isConnected) return;
      loader.classList.add('cb-loader-out');
      window.setTimeout(() => loader.remove(), reducedMotion() ? 0 : 160);
    };

    window.addEventListener('load', dismiss, { once: true });
    window.setTimeout(dismiss, 1800);
  }

  function markFoundation() {
    document.documentElement.dataset.cbFoundation = 'phase-1';
    document.body.classList.add('cb-foundation');
  }

  function init() {
    markFoundation();
    installThemeBehavior();
    ensureFavicon();
    brandHeader();
    reorderPrimaryNav();
    installLeagueTransitions();
    installBrandLoader();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
