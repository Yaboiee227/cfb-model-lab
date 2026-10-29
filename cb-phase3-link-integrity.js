(() => {
  if (window.__CB_PHASE3_LINK_INTEGRITY) return;
  window.__CB_PHASE3_LINK_INTEGRITY = true;

  const league = String(window.CB_ACTIVE_LEAGUE || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  if (league !== 'nfl') return;

  function syncLinks(root = document) {
    root.querySelectorAll?.('.cb-team-lens-game a[href]').forEach(link => {
      const raw = link.getAttribute('href') || '';
      if (!raw) return;
      const url = new URL(raw, location.href);
      url.searchParams.set('league', 'nfl');
      link.setAttribute('href', `${url.pathname.split('/').pop() || 'index.html'}${url.search}${url.hash}`);
    });
  }

  function attach() {
    const lens = document.getElementById('cbTeamLensBody');
    if (!lens) {
      requestAnimationFrame(attach);
      return;
    }
    syncLinks(lens);
    const observer = new MutationObserver(() => syncLinks(lens));
    observer.observe(lens, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach, { once: true });
  else attach();
})();
