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

  window.CBTeamVisuals = Object.freeze({
    normalize,
    visual,
    abbreviation: autoAbbreviation,
    badgeMarkup,
    teamMarkup,
    matchupMarkup
  });
})();
