(() => {
  const esc = value => typeof escapeHtml === 'function' ? escapeHtml(value) : String(value ?? '');
  const eventId = () => {
    const match = location.hash.match(/^#game=(.+)$/);
    return match ? decodeURIComponent(match[1]) : null;
  };

  async function context() {
    const id = eventId();
    if (!id) return null;
    const game = window.CBLiveData?.getGame(id);
    if (!game) return null;
    const projection = window.CBLiveData?.getProjectionForEvent(id);
    const cached = window.CBLiveData?.state.detailCache?.get(String(id))?.data;
    const summary = cached || await window.CBLiveData?.fetchSummary(id);
    return { id, game, projection, summary };
  }

  function quarterScores(summary, teamId) {
    const comp = summary?.header?.competitions?.[0];
    const team = comp?.competitors?.find(c => String(c.id || c.team?.id) === String(teamId));
    return (team?.linescores || []).map(x => Number.isFinite(Number(x.value)) ? Number(x.value) : Number(x.displayValue || 0));
  }

  async function ensureQuarterTable(panel) {
    const totals = panel.querySelector('.box-score-table');
    if (!totals || panel.querySelector('.quarter-score-table')) return;
    const ctx = await context();
    if (!ctx) return;
    const away = quarterScores(ctx.summary, ctx.game.away.id);
    const home = quarterScores(ctx.summary, ctx.game.home.id);
    if (!away.length && !home.length) return;
    const count = Math.max(away.length, home.length);
    const labels = Array.from({length:count}, (_,i) => i < 4 ? `Q${i+1}` : `OT${i-3}`);
    const table = document.createElement('div');
    table.className = 'quarter-score-table';
    table.innerHTML = `
      <div class="quarter-row quarter-head"><strong>Team</strong>${labels.map(x=>`<span>${x}</span>`).join('')}<strong>Total</strong></div>
      <div class="quarter-row"><strong>${esc(ctx.game.away.name)}</strong>${labels.map((_,i)=>`<span>${away[i] ?? '—'}</span>`).join('')}<strong>${ctx.game.away.score}</strong></div>
      <div class="quarter-row"><strong>${esc(ctx.game.home.name)}</strong>${labels.map((_,i)=>`<span>${home[i] ?? '—'}</span>`).join('')}<strong>${ctx.game.home.score}</strong></div>`;
    totals.insertAdjacentElement('beforebegin', table);
  }

  function elapsedMinutes(game) {
    if (game.state === 'post') return 60;
    if (game.state !== 'in' || !game.period) return 0;
    const [m,s] = String(game.clock || '0:00').split(':').map(Number);
    const remaining = (m || 0) + (s || 0)/60;
    return Math.max(0, Math.min(60, (game.period - 1) * 15 + (15 - remaining)));
  }

  async function correctTotalStatus(panel) {
    const tiles = panel.querySelectorAll('.live-model-status .status-tile');
    if (tiles.length < 3) return;
    const ctx = await context();
    if (!ctx?.projection) return;
    const p = ctx.projection, g = ctx.game;
    const elapsed = elapsedMinutes(g);
    const market = Number(p.marketTotal), model = Number(p.modelTotal);
    const tile = tiles[2];
    if (!elapsed || !Number.isFinite(market) || !Number.isFinite(model)) {
      tile.classList.remove('good','bad'); tile.classList.add('pending');
      return;
    }
    const pace = (g.home.score + g.away.score) / elapsed * 60;
    const modelDirection = model > market ? 'over' : model < market ? 'under' : 'aligned';
    const paceDirection = pace > market ? 'over' : pace < market ? 'under' : 'aligned';
    const good = modelDirection !== 'aligned' && modelDirection === paceDirection;
    const bad = modelDirection !== 'aligned' && paceDirection !== 'aligned' && modelDirection !== paceDirection;
    tile.classList.remove('good','bad','pending');
    tile.classList.add(good ? 'good' : bad ? 'bad' : 'pending');
    const strong = tile.querySelector('strong');
    const small = tile.querySelector('small');
    if (strong) strong.textContent = `${paceDirection === 'aligned' ? 'On market total' : `${paceDirection[0].toUpperCase()+paceDirection.slice(1)} pace`} · ${good ? 'aligns with model' : bad ? 'opposes model' : 'pending'}`;
    if (small) small.textContent = `${pace.toFixed(1)} pace · model ${model.toFixed(1)} vs market ${market.toFixed(1)}`;
  }

  function ensureResearchShortcuts(panel) {
    const overview = panel.querySelector('.detail-context-note');
    if (!overview || panel.querySelector('.detail-research-shortcuts')) return;
    const nav = document.createElement('div');
    nav.className = 'detail-research-shortcuts';
    nav.innerHTML = `<span>Related research</span><a href="#research">Availability</a><a href="#research">Weather</a><a href="#research">Line movement</a>`;
    overview.insertAdjacentElement('afterend', nav);
    nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => window.CBGameDetail?.close(false)));
  }

  async function decorate() {
    const panel = document.getElementById('liveTabPanel');
    if (!panel) return;
    await ensureQuarterTable(panel);
    await correctTotalStatus(panel);
    ensureResearchShortcuts(panel);
  }

  function start() {
    const panel = document.getElementById('liveTabPanel');
    if (!panel) return setTimeout(start,100);
    new MutationObserver(() => setTimeout(decorate,0)).observe(panel,{childList:true,subtree:true});
    document.addEventListener('cb:live-update', () => setTimeout(decorate,0));
    window.addEventListener('hashchange', () => setTimeout(decorate,0));
    decorate();
  }
  start();
})();
