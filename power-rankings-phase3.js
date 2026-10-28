(() => {
  if (window.__CB_PHASE3_POWER_REPLAY) return;
  window.__CB_PHASE3_POWER_REPLAY = true;

  const params = new URL(location.href).searchParams;
  const league = params.get('league') === 'nfl' ? 'nfl' : 'cfb';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const normalize = value => String(value || '').toLowerCase().replace(/[^a-z0-9]/g,'');
  const num = value => value === '' || value == null || !Number.isFinite(Number(value)) ? null : Number(value);
  const fmt = value => num(value) === null ? '—' : `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}`;
  const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;

  let snapshots = [];
  let index = 0;
  let timer = null;

  function teamVisual(row) {
    const visual = window.CBTeamVisuals;
    if (!visual) return `<span class="replay-team-copy"><strong>${esc(row.teamName)}</strong><small>${esc(row.team || '')}</small></span>`;
    return `${visual.badgeMarkup(row.teamName,{abbr:row.team,size:'xs'})}<span class="replay-team-copy"><strong>${esc(row.teamName)}</strong><small>${esc(row.team || '')}</small></span>`;
  }

  async function fetchJson(path) {
    try {
      const response = await fetch(path,{cache:'no-store'});
      if (!response.ok) return null;
      return await response.json();
    } catch (_) { return null; }
  }

  async function loadSnapshots() {
    const [previous,current] = await Promise.all([
      fetchJson(`data/power-rankings/archive/${league}-previous.json`),
      fetchJson(`data/power-rankings/${league}.json`)
    ]);
    const seen = new Set();
    snapshots = [previous,current].filter(Boolean).filter(snapshot => {
      const key = `${snapshot.season}-${snapshot.week}-${snapshot.snapshotAsOf || ''}`;
      if (seen.has(key) || !Array.isArray(snapshot.teams) || !snapshot.teams.length) return false;
      seen.add(key);
      return true;
    }).sort((a,b) => Number(a.week || 0)-Number(b.week || 0) || String(a.snapshotAsOf || '').localeCompare(String(b.snapshotAsOf || '')));
    index = Math.max(0,snapshots.length-1);
  }

  function installSection() {
    if (document.getElementById('replay')) return;
    const ratings = document.getElementById('ratings');
    if (!ratings) return;
    const section = document.createElement('section');
    section.className = 'section';
    section.id = 'replay';
    section.setAttribute('aria-labelledby','replayTitle');
    section.innerHTML = `
      <div class="section-head" data-index="02 · SEASON REPLAY"><h2 id="replayTitle">Power rankings season replay</h2><p>Replay only the ranking snapshots that were actually preserved. Missing weeks are never reconstructed after the fact.</p></div>
      <div class="replay-shell">
        <div class="replay-controls">
          <button type="button" class="replay-play" id="replayPlay" aria-pressed="false">▶ Play preserved weeks</button>
          <div class="replay-range-wrap"><label for="replayRange">Season scrubber</label><input id="replayRange" type="range" min="0" max="0" step="1" value="0"><div class="replay-range-meta"><span id="replayFirst">—</span><span id="replayLast">—</span></div></div>
          <div class="replay-team-wrap"><label for="replayTeam">Team focus</label><select id="replayTeam"><option value="">Top board</option></select></div>
        </div>
        <div class="replay-status"><span id="replaySnapshot"><strong>Loading preserved snapshots…</strong></span><span id="replayCoverage">—</span></div>
        <div class="replay-board" id="replayBoard" aria-live="polite"></div>
      </div>
      <p class="replay-integrity"><strong>Integrity rule:</strong> the scrubber can only move through frozen ranking files already present in the repository. A visually complete season history is not manufactured from current rankings or movement fields.</p>`;
    ratings.insertAdjacentElement('afterend',section);

    const nav = document.querySelector('.page-nav');
    if (nav && !nav.querySelector('a[href="#replay"]')) {
      const market = nav.querySelector('a[href="#comparisons"]');
      const link = document.createElement('a');
      link.href = '#replay';
      link.textContent = 'Season replay';
      nav.insertBefore(link,market || null);
    }
  }

  function teamOptions() {
    const select = document.getElementById('replayTeam');
    if (!select || !snapshots.length) return;
    const teams = new Map();
    snapshots.forEach(snapshot => (snapshot.teams || []).forEach(row => {
      const key = normalize(row.teamName || row.team);
      if (key && !teams.has(key)) teams.set(key,{key,label:row.teamName || row.team});
    }));
    select.innerHTML = '<option value="">Top board</option>' + [...teams.values()].sort((a,b)=>a.label.localeCompare(b.label)).map(team => `<option value="${esc(team.key)}">${esc(team.label)}</option>`).join('');
    const requested = params.get('team');
    if (requested) {
      const key = normalize(requested);
      if ([...select.options].some(option => option.value === key)) select.value = key;
    }
  }

  function movementMarkup(row) {
    const move = row.movement;
    if (typeof move === 'number') {
      if (move > 0) return {className:'up',value:`+${move}`,label:'positions'};
      if (move < 0) return {className:'down',value:String(move),label:'positions'};
      return {className:'',value:'0',label:'positions'};
    }
    return {className:move === 'NEW' ? 'up' : '',value:move || '—',label:'movement'};
  }

  function rowsForSnapshot(snapshot) {
    const focus = document.getElementById('replayTeam')?.value || '';
    const sorted = [...(snapshot.teams || [])].sort((a,b)=>Number(a.rank || 999)-Number(b.rank || 999));
    const limit = league === 'cfb' ? 25 : 32;
    const visible = sorted.slice(0,limit);
    if (focus) {
      const focused = sorted.find(row => normalize(row.teamName || row.team) === focus);
      if (focused && !visible.includes(focused)) visible.push(focused);
    }
    return visible;
  }

  function animateBoard(nextHtmlRows) {
    const board = document.getElementById('replayBoard');
    if (!board) return;
    const oldRects = new Map([...board.querySelectorAll('.replay-row')].map(row => [row.dataset.team,row.getBoundingClientRect()]));
    board.innerHTML = nextHtmlRows;
    if (prefersReducedMotion) return;
    const nextRows = [...board.querySelectorAll('.replay-row')];
    nextRows.forEach(row => {
      const old = oldRects.get(row.dataset.team);
      if (!old) { row.style.opacity='0';return; }
      const current = row.getBoundingClientRect();
      row.style.transition='none';
      row.style.transform=`translateY(${old.top-current.top}px)`;
    });
    requestAnimationFrame(() => requestAnimationFrame(() => nextRows.forEach(row => {
      row.style.transition='';
      row.style.transform='';
      row.style.opacity='';
    })));
  }

  function render() {
    const snapshot = snapshots[index];
    const board = document.getElementById('replayBoard');
    if (!snapshot || !board) {
      if (board) board.innerHTML = '<div class="replay-empty">No preserved ranking snapshots are available.</div>';
      return;
    }
    const focus = document.getElementById('replayTeam')?.value || '';
    const rows = rowsForSnapshot(snapshot);
    const html = rows.map(row => {
      const key = normalize(row.teamName || row.team);
      const move = movementMarkup(row);
      return `<div class="replay-row${focus && key === focus ? ' is-focus' : ''}" data-team="${esc(key)}">
        <div class="replay-rank">#${esc(row.rank)}</div>
        <div class="replay-team">${teamVisual(row)}</div>
        <div class="replay-points"><strong>${fmt(row.cbPoints)}</strong><small>CB points</small></div>
        <div class="replay-move ${move.className}"><strong>${esc(move.value)}</strong><small>${esc(move.label)}</small></div>
      </div>`;
    }).join('');
    animateBoard(html || '<div class="replay-empty">This preserved snapshot contains no ranking rows.</div>');

    const asOf = snapshot.snapshotAsOf ? new Date(snapshot.snapshotAsOf) : null;
    const asOfText = asOf && Number.isFinite(asOf.getTime()) ? asOf.toLocaleString([],{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}) : (snapshot.snapshotAsOf || 'time unavailable');
    document.getElementById('replaySnapshot').innerHTML = `<strong>${esc(snapshot.season)} · Week ${esc(snapshot.week)}</strong> · ${esc(asOfText)}`;
    document.getElementById('replayCoverage').textContent = `${snapshot.teams.length} teams · preserved snapshot ${index+1} of ${snapshots.length}`;
    const range = document.getElementById('replayRange');
    range.value = String(index);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    const button = document.getElementById('replayPlay');
    if (button) { button.setAttribute('aria-pressed','false');button.textContent='▶ Play preserved weeks'; }
  }

  function play() {
    if (snapshots.length < 2) return;
    if (timer) { stop();return; }
    const button = document.getElementById('replayPlay');
    if (button) { button.setAttribute('aria-pressed','true');button.textContent='Ⅱ Pause replay'; }
    timer = setInterval(() => {
      index = (index + 1) % snapshots.length;
      render();
    }, prefersReducedMotion ? 1500 : 1050);
  }

  function bind() {
    const range = document.getElementById('replayRange');
    const button = document.getElementById('replayPlay');
    const team = document.getElementById('replayTeam');
    if (!range || !button || !team) return;
    range.min='0'; range.max=String(Math.max(0,snapshots.length-1)); range.step='1'; range.value=String(index);
    const label = snapshot => snapshot ? `W${snapshot.week}` : '—';
    document.getElementById('replayFirst').textContent = label(snapshots[0]);
    document.getElementById('replayLast').textContent = label(snapshots.at(-1));
    button.disabled = snapshots.length < 2;
    if (snapshots.length < 2) button.textContent='One preserved snapshot';
    range.addEventListener('input',() => { stop();index=Number(range.value);render(); });
    button.addEventListener('click',play);
    team.addEventListener('change',render);
    document.addEventListener('visibilitychange',() => { if (document.hidden) stop(); });
  }

  async function init() {
    installSection();
    await loadSnapshots();
    teamOptions();
    bind();
    render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',() => init().catch(console.error),{once:true});
  else init().catch(console.error);
})();
