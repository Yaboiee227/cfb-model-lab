(() => {
  const params = new URL(location.href).searchParams;
  const league = params.get('league') === 'nfl' ? 'nfl' : 'cfb';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = value => Number.isFinite(Number(value)) ? Number(value) : null;
  const points = value => number(value) === null ? '—' : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}`;
  const rank = value => number(value) === null ? '—' : `#${Number(value)}`;
  const dateLabel = value => {
    if (!value) return '—';
    const d = new Date(value);
    return Number.isFinite(d.getTime()) ? d.toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}) : value;
  };

  let doc = null;
  let rows = [];

  function links() {
    const suffix = league === 'nfl' ? '?league=nfl' : '';
    $('homeLink').href = `index.html${suffix}`;
    $('projectionLink').href = `index.html${suffix}#projections`;
    $('recapLink').href = `recap.html${suffix}`;
    $('cfbSwitch').classList.toggle('active', league === 'cfb');
    $('nflSwitch').classList.toggle('active', league === 'nfl');
    $('kicker').textContent = `CB POWER RATINGS · ${league.toUpperCase()}`;
    document.title = `${league.toUpperCase()} Power Rankings · CB Model Projections`;
  }

  function marketBadge() {
    const status = doc?.marketNationalRatings?.nationalRatingStatus || 'UNKNOWN';
    const withheld = status.startsWith('WITHHELD');
    const text = withheld ? 'Withheld' : status.replaceAll('_',' ');
    return `<span class="status ${withheld ? 'hold' : 'good'}">${esc(text)}</span>`;
  }

  function renderRows() {
    const query = $('search').value.trim().toLowerCase();
    const filtered = rows.filter(r => `${r.teamName} ${r.team}`.toLowerCase().includes(query));
    $('ratingsBody').innerHTML = filtered.map(r => `
      <tr>
        <td class="rank-cell">${rank(r.rank)}</td>
        <td><strong>${esc(r.teamName)}</strong><span class="team-code">${esc(r.team)}</span></td>
        <td class="num model">${points(r.cbPoints)}</td>
        <td class="num market">${rank(r.marketRank)}</td>
        <td class="num market">${points(r.marketPoints)}</td>
        <td class="num context">${points(r.marketGap)}</td>
        <td><span class="movement ${r.movement === 'NEW' ? 'new' : ''}">${esc(r.movement || '—')}</span></td>
        <td><span class="status">${esc(String(r.evidenceStatus || 'research').replaceAll('_',' '))}</span></td>
      </tr>`).join('');
    $('count').textContent = `${filtered.length} of ${rows.length} teams`;
  }

  function renderMatchups() {
    const games = [...(doc.remainingMatchupComparisons || [])].sort((a,b) => Number(b.gapMagnitude || 0) - Number(a.gapMagnitude || 0));
    $('matchupCount').textContent = `${games.length} current comparisons`;
    $('matchupsBody').innerHTML = games.map(g => `
      <tr>
        <td><strong>${esc(g.awayTeam)}</strong><span class="muted"> @ </span><strong>${esc(g.homeTeam)}</strong><small class="kickoff">${esc(dateLabel(g.kickoff))}</small></td>
        <td class="num model">${points(g.modelSpreadHome)}</td>
        <td class="num market">${points(g.marketSpreadHome)}</td>
        <td class="num context">${points(g.modelMarketGapHome)}</td>
        <td><strong>${esc(g.gapSide)}</strong><small class="kickoff">${Number(g.gapMagnitude || 0).toFixed(1)} pts</small></td>
        <td><span class="status">Context only</span></td>
      </tr>`).join('');
  }

  function renderMeta() {
    const top = rows[0];
    $('metric1').textContent = rows.length;
    $('metric1Sub').textContent = league === 'cfb' ? 'FBS teams ranked' : 'NFL teams ranked';
    $('metric2').textContent = top ? top.teamName : '—';
    $('metric2Sub').textContent = top ? `${points(top.cbPoints)} CB points` : 'top team';
    $('metric3').textContent = dateLabel(doc.snapshotAsOf);
    $('metric3Sub').textContent = league === 'cfb' ? 'Friday pregame cutoff' : 'frozen pre-Week-7 state';
    $('metric4').innerHTML = marketBadge();
    $('metric4Sub').textContent = 'national market rank';

    const market = doc.marketNationalRatings || {};
    $('marketNotice').innerHTML = `<strong>${esc((market.nationalRatingStatus || '').replaceAll('_',' '))}.</strong> ${esc(market.reason || '')}`;
    $('systemState').innerHTML = `<strong>${league.toUpperCase()} · ${rows.length} teams</strong> · research-only point scale · zero canonical influence`;
    $('sourceMeta').textContent = league === 'cfb'
      ? `CFB snapshot ${doc.snapshotAsOf}; model ${doc.modelId}; ${doc.trainingGames} completed games inside the fixed training window. Week 8 frozen projections were not rewritten.`
      : `NFL snapshot ${doc.snapshotAsOf}; pinned source commit ${String(doc.sourceCommit || '').slice(0,12)}; frozen Week 7 regression ${doc.frozenRegression?.pass ? 'PASS' : 'FAIL'} across ${doc.frozenRegression?.games || 0} games.`;
    $('methodText').textContent = doc.method || 'Research-only model-derived team point rating.';
  }

  async function init() {
    links();
    try {
      const response = await fetch(`data/power-rankings/${league}.json`, {cache:'no-store'});
      if (!response.ok) throw new Error(`power ranking snapshot unavailable (${response.status})`);
      doc = await response.json();
      rows = doc.teams || [];
      if (!rows.length) throw new Error('power ranking snapshot contains no teams');
      renderMeta();
      renderRows();
      renderMatchups();
      $('search').addEventListener('input', renderRows);
    } catch (err) {
      $('ratingsBody').innerHTML = `<tr><td colspan="8" class="error">Unable to load power rankings: ${esc(err.message)}</td></tr>`;
      $('matchupsBody').innerHTML = `<tr><td colspan="6" class="error">Matchup comparison unavailable until the ranking snapshot passes validation.</td></tr>`;
      $('count').textContent = 'Load error';
      $('matchupCount').textContent = 'Load error';
      $('systemState').innerHTML = '<strong>Power rankings unavailable</strong> · validation output missing';
      $('sourceMeta').textContent = `Power rankings load error: ${err.message}`;
    }
  }

  init();
})();
