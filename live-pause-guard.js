(() => {
  if (!window.CBLiveData) return;

  const originalSummary = window.CBLiveData.fetchSummary.bind(window.CBLiveData);
  window.CBLiveData.fetchSummary = (eventId, options) => {
    if (window.CBLiveData.state.paused) {
      const cached = window.CBLiveData.state.detailCache?.get(String(eventId));
      return Promise.resolve(cached?.data || null);
    }
    return originalSummary(eventId, options);
  };

  function stopMarketTimers() {
    if (window.CBMarketsSportsbooks?.state?.timer) {
      clearTimeout(window.CBMarketsSportsbooks.state.timer);
      window.CBMarketsSportsbooks.state.timer = null;
    }
  }

  document.addEventListener('cb:live-pause', event => {
    if (event.detail?.paused) stopMarketTimers();
  });

  document.addEventListener('visibilitychange', () => {
    if (window.CBLiveData.state.paused) setTimeout(stopMarketTimers, 0);
  });
})();
