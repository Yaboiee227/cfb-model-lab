'use strict';
const esc = value => String(value ?? 'Not captured').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const et = value => value ? new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value)) : 'Not captured';
const range = value => Array.isArray(value) ? value.map(esc).join('–') : 'Not supplied';
async function get(path) { const response = await fetch(path, {cache:'no-store'}); if (!response.ok) throw new Error(`Unavailable: ${path}`); return response.json(); }
async function render() {
  const [gate,tue,wed,tr,wr,locks] = await Promise.all([
    'cfb/projections/week-08-status.json','cfb/pregame/week-08-tuesday-effective.json','cfb/pregame/week-08-wednesday-effective.json',
    'cfb/pregame/week-08-tuesday-readiness.json','cfb/pregame/week-08-wednesday-readiness.json','cfb/research-market-locks/week-08-foundation-market.json'
  ].map(get));
  document.querySelector('#release').textContent = `Canonical release: ${gate.status}. ${gate.canonicalProjectionAvailable ? 'See the release gate for authorization.' : 'No authorized Week 8 canonical projection is available.'}`;
  document.querySelector('#updated').textContent = `Tuesday context: ${et(tue.observedAt)} · Wednesday context: ${et(wed.observedAt)} · Each quote and source retains its own timestamp.`;
  document.querySelector('#games').innerHTML = [...tue.games,...wed.games].map(g => {
    const p = g.personnel || {}, w = g.weather || {}, m = g.market || {};
    const audit = [...tr.games,...wr.games].find(a=>a.gameId===g.gameId);
    const lock = locks.games.find(l=>l.projectionDigest===g.frozenFoundationReference?.projectionDigest);
    const lockStart = new Date(new Date(g.kickoff).getTime() - 30*60000).toISOString();
    const availability = ['away','home'].flatMap(side=>(p[side]?.officialAvailability||[]).map(x=>`${side==='away'?g.awayTeam:g.homeTeam}: ${x.name} (${x.position}) — ${x.status}`));
    const quotes = (m.observations||[]).map(q=>`<li><strong>${esc(q.book||q.source)}</strong>: home spread ${esc(q.spreadHome)} (${esc(q.spreadHomePrice)}), total ${esc(q.total)}. <span class="muted">Quote ${esc(et(q.observedAt))}.</span></li>`).join('');
    const books = Object.entries(lock?.books||{});
    return `<article><span class="pill">${esc(gate.status)} · Research context</span><h2>${esc(g.awayTeam)} at ${esc(g.homeTeam)}</h2><p class="muted">Frozen kickoff: ${esc(et(g.kickoff))}</p>
    <h3>Personnel</h3><p>${esc(p.status)}</p>${['away','home'].map(side=>`<p><strong>${esc(side==='away'?g.awayTeam:g.homeTeam)}</strong>: ${esc(p[side]?.startingQB || p[side]?.mostRecentStartingQB || 'Starter unresolved')}. <span class="muted">${esc(p[side]?.qbEvidenceStatus || p[side]?.officialContext || 'Final confirmation pending.')}</span></p>`).join('')}
    ${p.availabilityNote?`<p>${esc(p.availabilityNote)}</p>`:''}
    <h3>Weather</h3><p>${range(w.temperatureFRange)} °F · wind ${range(w.windMphRange)} mph · precipitation ${range(w.precipProbabilityPctRange)}%.</p><p class="muted">${esc(w.spatialScope)}. Checked ${esc(et(w.observedAt))}; source updated ${esc(et(w.sourceLastUpdate))}. Final-window recheck pending unless the audit explicitly clears it. Gusts are not supplied by the hourly API.</p>
    <h3>Markets &amp; locks</h3><ul>${quotes||'<li>No current timestamped book quote captured.</li>'}</ul><p class="muted">Quotes are observations, not execution verification. T−30 lock window opens ${esc(et(lockStart))}. Saved lock state: ${esc(lock?.status || 'Unavailable')}; ${books.length} books captured.</p>
    <details><summary>Readiness &amp; source evidence</summary><p class="muted">Audit ${esc(et(audit?.auditedAt || (tr.games.some(a=>a.gameId===g.gameId)?tr.auditedAt:wr.auditedAt)))}</p><ul>${[...(audit?.blockers||['Readiness audit unavailable']),...(audit?.warnings||[])].map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${availability.length?`<h3>Official availability report</h3><p class="muted">Published ${esc(et(p.officialAvailability?.sourcePublishedAt))}; retrieved ${esc(et(p.officialAvailability?.retrievedAt))}.</p><ul>${availability.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}<h3>Sources</h3><ul>${[...(p.sources||[]),p.officialAvailability?.source,w.sourceUrl].filter(u=>typeof u==='string'&&u.startsWith('https://')).map(u=>`<li><a href="${esc(u)}" rel="noopener noreferrer">${esc(new URL(u).hostname)}</a></li>`).join('')}</ul></details></article>`;
  }).join('');
}
render().catch(error=>{document.querySelector('#release').textContent='Status data unavailable — no release clearance inferred.';document.querySelector('#updated').textContent=error.message;document.querySelector('#updated').classList.add('error');});
