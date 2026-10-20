'use strict';
const esc=value=>String(value??'Not captured').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const et=value=>value?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}).format(new Date(value)):'Not captured';
const fmt=n=>Number.isFinite(Number(n))?Number(n).toFixed(1):'—';
const line=n=>Number.isFinite(Number(n))?`${Number(n)>0?'+':''}${Number(n).toFixed(1)}`:'—';
const range=value=>Array.isArray(value)&&value.length?value.map(esc).join('–'):'Not supplied';
async function get(path){const response=await fetch(path,{cache:'no-store'});if(!response.ok)throw new Error(`Unavailable: ${path}`);return response.json();}
const aliases={
  'delaware blue hens':'Delaware','missouri state bears':'Missouri State','florida international panthers':'Florida International','middle tennessee blue raiders':'Middle Tennessee','marshall thundering herd':'Marshall','south alabama jaguars':'South Alabama','new mexico state aggies':'New Mexico State','sam houston bearkats':'Sam Houston','james madison dukes':'James Madison','appalachian state mountaineers':'App State','liberty flames':'Liberty','kennesaw state owls':'Kennesaw State','east carolina pirates':'East Carolina','memphis tigers':'Memphis'
};
const canon=name=>aliases[String(name||'').toLowerCase()]||String(name||'').replace(/^FIU$/i,'Florida International').replace(/^Appalachian State$/i,'App State');
function marketGame(feed,g){return(feed.games||[]).find(x=>canon(x.homeTeam)===canon(g.homeTeam)&&canon(x.awayTeam)===canon(g.awayTeam));}
function freshestQuotes(feedGame,fallback){if(feedGame?.books){return Object.entries(feedGame.books).map(([book,b])=>({book:book==='fanduel'?'FanDuel':book==='draftkings'?'DraftKings':book,observedAt:b.updatedAt,spreadHome:b.spread?.home,spreadHomePrice:b.spread?.homePrice,total:b.total?.point,overPrice:b.total?.overPrice,underPrice:b.total?.underPrice,moneylineHome:b.moneyline?.home,moneylineAway:b.moneyline?.away}));}return fallback?.observations||[];}
function windowState(kickoff){const ms=new Date(kickoff).getTime()-Date.now(),mins=ms/60000;if(mins<=0)return'KICKOFF/STARTED';if(mins<=30)return'T−30 LOCK WINDOW';if(mins<=60)return'FINAL HOUR';if(mins<=180)return'PREGAME <3H';return'PREP';}
function statusClass(day){return day==='tonight'?'tonight':day==='tomorrow'?'next':'';}
function dayLabel(day){return day==='tonight'?'Tonight':day==='tomorrow'?'Tomorrow':'Thursday';}
function shadowBlock(g){const f=g.frozenFoundationReference||{};if(!Number.isFinite(Number(f.projectedSpreadHome)))return'';return `<div class="shadow"><strong>Frozen research shadow</strong><div>${esc(f.projectedWinner||'—')} · projected score ${fmt(f.projectedAwayPoints)}–${fmt(f.projectedHomePoints)} · home spread ${line(f.projectedSpreadHome)} · total ${fmt(f.projectedTotal)} · home win ${fmt(f.homeWinProbability)}%</div><span class="muted">Immutable prospective research evidence only. Canonical influence: none.</span></div>`;}
function readinessFor(g,audits){return audits.find(a=>a.gameId===g.gameId)||null;}
function renderGame(g,day,audits,locks,marketFeed){
  const p=g.personnel||{},w=g.weather||{},audit=readinessFor(g,audits),feedGame=marketGame(marketFeed,g),quotes=freshestQuotes(feedGame,g.market),lock=locks.games?.find(x=>x.projectionDigest===g.frozenFoundationReference?.projectionDigest),lockBooks=Object.keys(lock?.books||{}).length;
  const lockStart=new Date(new Date(g.kickoff).getTime()-30*60000).toISOString();
  const finalStart=new Date(new Date(g.kickoff).getTime()-60*60000).toISOString();
  const personnelLabel=String(p.status||'Pending').replaceAll('_',' ');
  const weatherLabel=String(w.status||'Pending').replaceAll('_',' ');
  const lockLabel=lockBooks?`${lockBooks} book${lockBooks===1?'':'s'} locked`:`Pending T−30`;
  const quoteHtml=quotes.length?quotes.map(q=>`<li><strong>${esc(q.book||q.source||'Book')}</strong>: home spread ${line(q.spreadHome)}${q.spreadHomePrice!=null?` (${esc(q.spreadHomePrice)})`:''}, total ${fmt(q.total)}${q.moneylineHome!=null?`, ML home ${esc(q.moneylineHome)} / away ${esc(q.moneylineAway)}`:''}. <span class="muted">${esc(et(q.observedAt))}</span></li>`).join(''):'<li>No current timestamped sportsbook quote captured.</li>';
  const qbs=['away','home'].map(side=>{const x=p[side]||{},team=side==='away'?g.awayTeam:g.homeTeam;return `<p><strong>${esc(team)}</strong>: ${esc(x.startingQB||x.mostRecentStartingQB||x.materialStatus||'Starter/usage unresolved')}. <span class="muted">${esc(x.qbEvidenceStatus||x.officialContext||'Final confirmation remains source-dependent.')}</span></p>`;}).join('');
  const evidence=[...(audit?.blockers||[]),...(audit?.warnings||[])];
  const sourceUrls=[...(p.sources||[]),p.officialAvailability?.source,w.sourceUrl].filter(u=>typeof u==='string'&&u.startsWith('https://'));
  return `<article class="game ${statusClass(day)}"><div class="game-head"><div><span class="pill ${day==='tonight'?'live':day==='tomorrow'?'next':''}">${esc(dayLabel(day))} · ${esc(windowState(g.kickoff))}</span><h3>${esc(g.awayTeam)} at ${esc(g.homeTeam)}</h3><div class="kick">Kickoff ${esc(et(g.kickoff))}</div></div></div>
  <div class="status-row"><div><span>Personnel</span><strong>${esc(personnelLabel.length>34?personnelLabel.slice(0,31)+'…':personnelLabel)}</strong></div><div><span>Weather</span><strong>${esc(weatherLabel.includes('FINAL_RECHECK')?'Final recheck pending':'Captured')}</strong></div><div><span>Market lock</span><strong>${esc(lockLabel)}</strong></div></div>
  ${shadowBlock(g)}
  <h4>Quarterback / personnel</h4>${qbs}
  <h4>Weather</h4><p>${range(w.temperatureFRange)} °F · wind ${range(w.windMphRange)} mph · precipitation ${range(w.precipProbabilityPctRange)}%.</p><p class="muted">${esc(w.spatialScope||'Saved pregame weather context')}. Last checked ${esc(et(w.observedAt||w.lastCheckedAt))}. Final-hour recheck is required where marked.</p>
  <h4>Tracked sportsbook context</h4><ul class="market-list">${quoteHtml}</ul><p class="muted">Current quotes are benchmark/context only. Final-hour source review opens ${esc(et(finalStart))}; immutable publication-market lock opens ${esc(et(lockStart))}. Saved lock status: ${esc(lock?.status||'PENDING')}.</p>
  <details><summary>Readiness, blockers &amp; sources</summary>${audit?`<p class="muted">Latest readiness audit: ${esc(et(audit.auditedAt||audit.auditAt))}</p>`:'<p class="muted">Dedicated game-day readiness audit has not run yet; current source state is still preserved.</p>'}<ul>${(evidence.length?evidence:['Final game-day audit remains pending.']).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>${sourceUrls.length?`<h4>Source links</h4><ul>${sourceUrls.map(u=>`<li><a href="${esc(u)}" rel="noopener noreferrer">${esc(new URL(u).hostname)}</a></li>`).join('')}</ul>`:''}</details></article>`;
}
async function render(){
  const [gate,state,tr,wr,locks,markets]=await Promise.all([
    'cfb/projections/week-08-status.json','cfb/pregame/week-08-through-thursday-effective.json','cfb/pregame/week-08-tuesday-readiness.json','cfb/pregame/week-08-wednesday-readiness.json','cfb/research-market-locks/week-08-foundation-market.json','data/markets-sportsbooks.json'
  ].map(get));
  const audits=[...(tr.games||[]),...(wr.games||[])];
  document.querySelector('#release').textContent=`Canonical release: ${gate.status}. ${gate.canonicalProjectionAvailable?'Authorized canonical projection is available.':'No authorized Week 8 canonical projection is available; research/shadow tracking continues prospectively.'}`;
  document.querySelector('#gateShort').textContent=gate.status;
  const tue=(state.games||[]).filter(g=>String(g.gameId).startsWith('2026-10-20-'));
  const wed=(state.games||[]).filter(g=>String(g.gameId).startsWith('2026-10-21-'));
  const thu=(state.games||[]).filter(g=>String(g.gameId).startsWith('2026-10-22-'));
  document.querySelector('#tonightCount').textContent=tue.length;
  document.querySelector('#tomorrowCount').textContent=wed.length;
  document.querySelector('#thursdayCount').textContent=thu.length;
  document.querySelector('#updated').textContent=`Integrated Week 8 state: ${et(state.observedAt)} · tracked sportsbook feed: ${et(markets.generatedAt)} · moneyline feed: ${et(markets.lastMoneylineRefresh)} · each source and immutable lock retains its own timestamp.`;
  document.querySelector('#tonightGames').innerHTML=tue.map(g=>renderGame(g,'tonight',audits,locks,markets)).join('');
  document.querySelector('#tomorrowGames').innerHTML=wed.map(g=>renderGame(g,'tomorrow',audits,locks,markets)).join('');
  document.querySelector('#thursdayGames').innerHTML=thu.map(g=>renderGame(g,'thursday',audits,locks,markets)).join('');
  document.querySelector('#pageClock').textContent=`Week 8 active window · Tue–Thu · page read ${et(new Date().toISOString())}`;
}
render().catch(error=>{document.querySelector('#release').textContent='Status data unavailable — no release clearance inferred.';const u=document.querySelector('#updated');u.textContent=error.message;u.classList.add('error');});
