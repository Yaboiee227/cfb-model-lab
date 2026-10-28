(() => {
  if (window.CBTeamVisuals) return;

  const config = window.CB_TEAM_ASSETS || { teams: {} };
  const teamConfig = config.teams || {};
  const palette = [
    '#315C8A', '#4A6D7C', '#6A4C93', '#2F7D63', '#8A5A44', '#7A4E76',
    '#8B5E34', '#38686A', '#586F7C', '#765D69', '#3D5A80', '#5F6F52'
  ];

  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const normalize = value => String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();

  function entryFor(teamName) {
    if (!teamName) return null;
    if (teamConfig[teamName]) return teamConfig[teamName];
    const key = normalize(teamName);
    return Object.entries(teamConfig).find(([name]) => normalize(name) === key)?.[1] || null;
  }

  function hash(value) {
    let h = 2166136261;
    const text = String(value || 'TEAM');
    for (let i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function autoAbbreviation(teamName, supplied) {
    const provided = String(supplied || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (provided && provided.length <= 5) return provided;

    const raw = String(teamName || '').trim();
    const compact = raw.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (/^[A-Z0-9]{2,5}$/.test(compact) && raw.split(/\s+/).length === 1) return compact;

    const words = raw
      .replace(/&/g, ' and ')
      .split(/[^A-Za-z0-9]+/)
      .filter(Boolean)
      .filter(word => !/^(the|university|college|of|and)$/i.test(word));

    if (!words.length) return 'CB';
    if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
    if (words.length === 2) {
      const first = words[0];
      const second = words[1];
      if (/^state$/i.test(second)) return `${first[0] || ''}ST`.toUpperCase();
      return `${first.slice(0, 2)}${second[0] || ''}`.slice(0, 4).toUpperCase();
    }
    return words.map(word => word[0]).join('').slice(0, 4).toUpperCase();
  }

  function hexRgb(hex) {
    const clean = String(hex || '').replace('#', '');
    if (!/^[0-9a-f]{6}$/i.test(clean)) return null;
    return [0, 2, 4].map(i => parseInt(clean.slice(i, i + 2), 16));
  }

  function luminance(hex) {
    const rgb = hexRgb(hex);
    if (!rgb) return 0;
    const channels = rgb.map(value => {
      const v = value / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
  }

  function accentFor(teamName, configured) {
    const candidate = String(configured || '').trim();
    if (/^#[0-9a-f]{6}$/i.test(candidate)) return candidate;
    return palette[hash(normalize(teamName)) % palette.length];
  }

  function visual(teamName, options = {}) {
    const cfg = entryFor(teamName) || {};
    const abbreviation = autoAbbreviation(teamName, options.abbr || cfg.abbreviation);
    const accent = accentFor(teamName, options.accent || cfg.accent);
    const ink = luminance(accent) > 0.42 ? '#202329' : '#F7F7F4';
    const licensedImage = cfg.licensed === true && typeof cfg.licensedImage === 'string' && cfg.licensedImage.trim()
      ? cfg.licensedImage.trim()
      : null;
    return {
      teamName: String(teamName || ''),
      abbreviation,
      accent,
      ink,
      licensedImage
    };
  }

  function badgeMarkup(teamName, options = {}) {
    const v = visual(teamName, options);
    const size = ['xs', 'sm', 'md', 'lg'].includes(options.size) ? options.size : 'md';
    const title = options.title || `${v.teamName || v.abbreviation} team badge`;
    if (v.licensedImage && options.allowLicensedImage !== false) {
      return `<span class="cb-team-badge cb-team-badge-${size} cb-team-badge-image" aria-hidden="true" title="${esc(title)}"><img src="${esc(v.licensedImage)}" alt="" loading="lazy"></span>`;
    }
    return `<span class="cb-team-badge cb-team-badge-${size}" aria-hidden="true" title="${esc(title)}" style="--team-accent:${esc(v.accent)};--team-ink:${esc(v.ink)}"><span>${esc(v.abbreviation)}</span></span>`;
  }

  function teamMarkup(teamName, options = {}) {
    const v = visual(teamName, options);
    const name = options.displayName || teamName || v.abbreviation;
    const detail = options.detail ? `<small>${esc(options.detail)}</small>` : '';
    return `<span class="cb-team-lockup ${options.compact ? 'cb-team-lockup-compact' : ''}">${badgeMarkup(teamName, options)}<span class="cb-team-lockup-copy"><strong>${esc(name)}</strong>${detail}</span></span>`;
  }

  function matchupMarkup(awayTeam, homeTeam, options = {}) {
    return `<span class="cb-matchup-lockup">${teamMarkup(awayTeam, {
      abbr: options.awayAbbr,
      size: options.size || 'sm',
      compact: true
    })}<span class="cb-matchup-at" aria-hidden="true">@</span>${teamMarkup(homeTeam, {
      abbr: options.homeAbbr,
      size: options.size || 'sm',
      compact: true
    })}</span>`;
  }

  function cleanRenderedTeamName(value) {
    return String(value || '').replace(/^◆\s*/, '').trim();
  }

  function siteState() {
    try { return typeof STATE !== 'undefined' ? STATE : null; }
    catch (_) { return null; }
  }

  function projectionById(id) {
    return siteState()?.projections?.find(game => String(game.gameId) === String(id)) || null;
  }

  function stripUnlicensedLiveImages(root = document) {
    root.querySelectorAll?.('.live-matchup-row img, .live-scoreboard .live-team > img').forEach(img => {
      img.removeAttribute('src');
      img.removeAttribute('srcset');
      img.removeAttribute('sizes');
      img.setAttribute('aria-hidden', 'true');
    });
  }

  function decorateProjectionTable() {
    document.querySelectorAll('#projectionBody tr[id^="game-"]').forEach(row => {
      const cell = row.querySelector('.game-matchup');
      if (!cell || cell.dataset.cbTeamVisual === 'true') return;
      const game = projectionById(row.id.replace(/^game-/, ''));
      if (!game) return;
      cell.dataset.cbTeamVisual = 'true';
      cell.classList.add('cb-table-matchup');
      cell.innerHTML = matchupMarkup(game.awayTeam, game.homeTeam, {
        awayAbbr: String(window.CB_ACTIVE_LEAGUE || '').toLowerCase() === 'nfl' ? game.awayTeam : null,
        homeAbbr: String(window.CB_ACTIVE_LEAGUE || '').toLowerCase() === 'nfl' ? game.homeTeam : null,
        size: 'xs'
      });
    });
  }

  function decorateTopSignals() {
    document.querySelectorAll('.top-signal-card').forEach(card => {
      if (card.dataset.cbTeamVisual === 'true') return;
      const gameId = card.querySelector('[data-inspect-game]')?.dataset.inspectGame;
      const game = projectionById(gameId);
      const heading = card.querySelector('h3');
      if (!game || !heading) return;
      card.dataset.cbTeamVisual = 'true';
      heading.classList.add('cb-top-signal-matchup');
      heading.innerHTML = matchupMarkup(game.awayTeam, game.homeTeam, {
        awayAbbr: String(window.CB_ACTIVE_LEAGUE || '').toLowerCase() === 'nfl' ? game.awayTeam : null,
        homeAbbr: String(window.CB_ACTIVE_LEAGUE || '').toLowerCase() === 'nfl' ? game.homeTeam : null,
        size: 'xs'
      });
    });
  }

  function decorateLiveSurfaces() {
    stripUnlicensedLiveImages();
    document.querySelectorAll('.live-matchup-row > div').forEach(row => {
      if (row.querySelector(':scope > .cb-team-badge')) return;
      const nameNode = [...row.children].find(node => node.tagName === 'SPAN' && !node.classList.contains('cb-team-badge'));
      const teamName = cleanRenderedTeamName(nameNode?.textContent);
      if (!teamName) return;
      row.insertAdjacentHTML('afterbegin', badgeMarkup(teamName, { size: 'sm' }));
    });

    document.querySelectorAll('.live-scoreboard .live-team').forEach(team => {
      if (team.querySelector(':scope > .cb-team-badge')) return;
      const nameNode = team.querySelector('div > span');
      const teamName = cleanRenderedTeamName(nameNode?.textContent);
      if (!teamName) return;
      const badge = document.createElement('span');
      badge.innerHTML = badgeMarkup(teamName, { size: 'lg' });
      const node = badge.firstElementChild;
      if (!node) return;
      const copy = team.querySelector(':scope > div');
      if (team.classList.contains('home')) team.appendChild(node);
      else team.insertBefore(node, copy || team.firstChild);
    });
  }

  function decoratePowerRankings() {
    document.querySelectorAll('#ratingsBody tr').forEach(row => {
      const cell = row.children[1];
      if (!cell || cell.dataset.cbTeamVisual === 'true') return;
      if (cell.querySelector('.cb-ranking-team')) {
        cell.dataset.cbTeamVisual = 'true';
        return;
      }
      const name = cell.querySelector('strong')?.textContent?.trim();
      const code = cell.querySelector('.team-code')?.textContent?.trim();
      if (!name) return;
      cell.dataset.cbTeamVisual = 'true';
      cell.classList.add('cb-ranking-team-cell');
      const strong = cell.querySelector('strong');
      const teamCode = cell.querySelector('.team-code');
      const wrapper = document.createElement('span');
      wrapper.className = 'cb-ranking-team';
      wrapper.innerHTML = badgeMarkup(name, { abbr: code, size: 'sm' });
      const copy = document.createElement('span');
      copy.className = 'cb-ranking-team-copy';
      if (strong) copy.appendChild(strong);
      if (teamCode) copy.appendChild(teamCode);
      wrapper.appendChild(copy);
      cell.appendChild(wrapper);
    });

    document.querySelectorAll('#matchupsBody tr').forEach(row => {
      const cell = row.children[0];
      if (!cell || cell.dataset.cbTeamVisual === 'true') return;
      if (cell.querySelector('.cb-matchup-lockup')) {
        cell.dataset.cbTeamVisual = 'true';
        return;
      }
      const teams = [...cell.querySelectorAll('strong')];
      if (teams.length < 2) return;
      const away = teams[0].textContent.trim();
      const home = teams[1].textContent.trim();
      const kickoff = cell.querySelector('.kickoff')?.outerHTML || '';
      cell.dataset.cbTeamVisual = 'true';
      cell.innerHTML = matchupMarkup(away, home, { size: 'xs' }) + kickoff;
    });
  }

  function decorateTickerItems() {
    document.querySelectorAll('[data-cb-ticker-away][data-cb-ticker-home]').forEach(item => {
      if (item.dataset.cbTeamVisual === 'true') return;
      const away = item.dataset.cbTickerAway;
      const home = item.dataset.cbTickerHome;
      const target = item.querySelector('[data-cb-ticker-matchup]') || item;
      item.dataset.cbTeamVisual = 'true';
      target.innerHTML = matchupMarkup(away, home, { size: 'xs' });
    });
  }

  function decorateAll() {
    decorateProjectionTable();
    decorateTopSignals();
    decorateLiveSurfaces();
    decoratePowerRankings();
    decorateTickerItems();
  }

  window.CBTeamVisuals = Object.freeze({
    normalize,
    visual,
    abbreviation: autoAbbreviation,
    badgeMarkup,
    teamMarkup,
    matchupMarkup,
    decorateAll
  });

  let frame = 0;
  const schedule = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(decorateAll);
  };

  const start = () => {
    decorateAll();
    if (!document.body) return;
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
