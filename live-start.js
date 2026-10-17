(() => {
  const DISCLAIMER = 'Live scores, stats, and market data are provided by third-party sources and may be delayed, incomplete, or inaccurate. Everything on CB Model Projections is for research and entertainment purposes only and is not betting advice or a recommendation to wager or trade. Must be 21+ (or the legal age in your jurisdiction). Availability of sportsbooks and prediction markets varies by location. If you or someone you know has a gambling problem, call 1-800-GAMBLER.';

  function ensureDisclaimer() {
    const center = document.getElementById('liveCenter');
    if (center && !document.getElementById('liveCenterDisclaimer')) {
      const p = document.createElement('p');
      p.id = 'liveCenterDisclaimer';
      p.className = 'live-center-disclaimer';
      p.textContent = DISCLAIMER;
      center.appendChild(p);
    }
  }

  function ensureGlossary() {
    const grid = document.querySelector('.glossary-grid');
    if (!grid || document.getElementById('liveGlossaryImplied')) return;
    const entries = [
      ['liveGlossaryImplied','Implied probability','The win probability represented by a market price. Sportsbook moneylines include bookmaker margin (vig), so CB Model Projections also shows a normalized no-vig comparison when both sides are available.'],
      ['liveGlossaryMovement','Line movement','A change in a sportsbook spread, total, or moneyline over time. Movement is market context only and does not automatically change the model projection.'],
      ['liveGlossaryPrediction','Prediction market','A market where prices can be interpreted as an implied probability. CB Model Projections displays Kalshi and Polymarket only when a reliable game match is found.']
    ];
    for (const [id,title,text] of entries) {
      const article = document.createElement('article');
      article.id = id;
      article.innerHTML = `<h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p>`;
      grid.appendChild(article);
    }
  }

  function relocateProjectionClickTargets() {
    document.querySelectorAll('#projectionBody tr[data-live-event]').forEach(row => {
      const eventId = row.dataset.liveEvent;
      const cell = row.querySelector('.game-cell');
      if (!cell) return;
      cell.dataset.liveEvent = eventId;
      cell.classList.add('live-clickable');
      delete row.dataset.liveEvent;
      row.classList.remove('live-clickable');
    });
    document.querySelectorAll('#projectionCards .projection-card[data-live-event]').forEach(card => {
      const eventId = card.dataset.liveEvent;
      for (const target of [card.querySelector('.projection-card-head'), card.querySelector('.projection-card-grid')].filter(Boolean)) {
        target.dataset.liveEvent = eventId;
        target.classList.add('live-clickable');
      }
      delete card.dataset.liveEvent;
      card.classList.remove('live-clickable');
    });
  }

  function enhanceKeyboardAccess() {
    document.querySelectorAll('[data-live-event].live-clickable').forEach(el => {
      if (el.dataset.liveKeyboardReady === '1') return;
      el.dataset.liveKeyboardReady = '1';
      el.tabIndex = 0;
      el.setAttribute('role','button');
      el.setAttribute('aria-label', `Open live game detail for ${el.querySelector('.game-matchup, h3')?.textContent?.trim() || el.closest('tr,article')?.querySelector('.game-matchup, h3')?.textContent?.trim() || 'this game'}`);
      el.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        if (event.target.closest('button,a,input,select')) return;
        event.preventDefault();
        window.CBGameDetail?.open(el.dataset.liveEvent);
      });
    });
  }

  function decorate() {
    ensureDisclaimer();
    ensureGlossary();
    relocateProjectionClickTargets();
    enhanceKeyboardAccess();
  }

  document.addEventListener('cb:live-update', () => requestAnimationFrame(decorate));
  document.addEventListener('cb:sportsbooks-update', () => requestAnimationFrame(decorate));

  try {
    window.CBLiveData?.init();
  } catch (error) {
    console.error('CB live suite could not initialize:', error);
  }
  requestAnimationFrame(decorate);
})();
