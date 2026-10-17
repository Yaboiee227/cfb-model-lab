const D = window.CFB_DATA;
Object.assign(D, {
  snapshotTime: "Oct 17, 2026 • 10:46 AM ET",
  modelVersion: "Advanced Calibrated 0.9J - Prospective Qualification + Totals Shadow v1",
  spreadValidation: "HOLD",
  totalValidation: "HOLD",
  openGames: 52,
  releasedBets: 0,
  publicationStatus: "INFO ONLY — NO RELEASED BETS",
  note: "Model projections are informational while validation holds. Computed alternative lines marked unpriced are not executable sportsbook prices."
});
const $ = s => document.querySelector(s);
const fmt = (n,d=1) => n == null || Number.isNaN(Number(n)) ? "—" : Number(n).toFixed(d);
const line = n => n == null ? "—" : (Number(n) > 0 ? "+" : "") + fmt(n,1);
const pct = n => n == null ? "—" : Math.round(Number(n)*100) + "%";
const esc = s => String(s ?? "").replace(/[&<>"']/g, m => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[m]));
const parseTime = t => { const m=t.match(/(\d+):(\d+)\s*(AM|PM)/i); if(!m)return 0; let h=+m[1]%12 + (m[3].toUpperCase()==="PM"?12:0); return h*60 + +m[2]; };
const abs = n => n == null ? -1 : Math.abs(Number(n));
const projectionCount = D.games.filter(g => g.projectedAwayPts != null && g.projectedHomePts != null).length;
const maxSpread = Math.max(...D.games.map(g=>abs(g.spreadEdge)));
const maxTotal = Math.max(...D.games.map(g=>abs(g.totalEdge)));
const avgDQ = D.games.reduce((s,g)=>s+(g.dataQuality||0),0)/D.games.length;

$("#modelVersion").textContent = D.modelVersion;
$("#snapshot").textContent = D.snapshotTime;
$("#pubStatus").textContent = D.publicationStatus;
$("#spreadGate").textContent = D.spreadValidation;
$("#totalGate").textContent = D.totalValidation;
$("#released").textContent = D.releasedBets;
$("#openGames").textContent = D.openGames;
$("#projectionCount").textContent = `${projectionCount}/${D.openGames}`;
$("#avgDQ").textContent = pct(avgDQ);
$("#maxSpread").textContent = fmt(maxSpread);
$("#maxTotal").textContent = fmt(maxTotal);
$("#note").textContent = D.note;

const dateSelect=$("#dateFilter");
[...new Set(D.games.map(g=>g.date))].sort().forEach(d=>{
  const o=document.createElement("option"); o.value=d;
  o.textContent=new Date(d+"T12:00:00").toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"});
  dateSelect.appendChild(o);
});

function marketBlock(title, model, market, edge, alt, threshold){
  const notable = edge != null && Math.abs(edge) >= threshold;
  return `<div class="market">
    <h3>${title}</h3>
    <div class="kv"><span>Model</span><b>${title==="Spread"?line(model):fmt(model)}</b></div>
    <div class="kv"><span>Market</span><b>${title==="Spread"?line(market):fmt(market)}</b></div>
    <div class="kv"><span>Edge</span><b class="edge ${notable?"notable":""}">${title==="Spread"?line(edge):line(edge)}</b></div>
    ${alt ? `<div class="alt"><strong>Computed alt:</strong><br>${esc(alt)}</div>` : ""}
  </div>`;
}
function card(g){
  const projected = g.projectedAwayPts != null && g.projectedHomePts != null;
  const q = Math.max(0,Math.min(100,Math.round((g.dataQuality||0)*100)));
  return `<article class="game">
    <div class="game-top">
      <div class="time">${esc(g.date)} • ${esc(g.kickoffET)} ET</div>
      <div class="badges"><span class="badge hold">${esc(g.releaseStatus)}</span><span class="badge low">${esc(g.signalStrength)}</span></div>
    </div>
    <div class="matchup">
      <div><div class="team">${esc(g.away)}</div><div class="score ${projected?"":"missing"}">${projected?fmt(g.projectedAwayPts):"No baseline"}</div></div>
      <div class="vs">at</div>
      <div><div class="team home">${esc(g.home)}</div><div class="score ${projected?"":"missing"}" style="text-align:right">${projected?fmt(g.projectedHomePts):"No baseline"}</div></div>
    </div>
    <div class="winner">${esc(g.projectedWinner)}</div>
    <div class="markets">
      ${marketBlock("Spread",g.modelSpreadHome,g.marketSpreadHome,g.spreadEdge,g.spreadAlt,3)}
      ${marketBlock("Total",g.modelTotal,g.marketTotal,g.totalEdge,g.totalAlt,4)}
    </div>
    <div class="quality"><span>Data quality</span><div class="meter"><span style="width:${q}%"></span></div><strong>${q}%</strong></div>
    <div class="release"><strong>${esc(g.betCandidate)}</strong><div class="blockers">${esc(g.releaseBlockers)}</div></div>
  </article>`;
}
function render(){
  const term=$("#search").value.trim().toLowerCase();
  const date=$("#dateFilter").value;
  const sort=$("#sort").value;
  const filter=$("#viewFilter").value;
  let rows=D.games.filter(g=>{
    const matches=!term || `${g.away} ${g.home}`.toLowerCase().includes(term);
    const dateOk=!date || g.date===date;
    const notable=abs(g.spreadEdge)>=3 || abs(g.totalEdge)>=4;
    const baseline=g.projectedAwayPts!=null && g.projectedHomePts!=null;
    const viewOk=filter==="all" || (filter==="notable"&&notable) || (filter==="baseline"&&baseline) || (filter==="missing"&&!baseline);
    return matches&&dateOk&&viewOk;
  });
  rows.sort((a,b)=>{
    if(sort==="spread") return abs(b.spreadEdge)-abs(a.spreadEdge);
    if(sort==="total") return abs(b.totalEdge)-abs(a.totalEdge);
    if(sort==="quality") return (b.dataQuality||0)-(a.dataQuality||0);
    return a.date.localeCompare(b.date) || parseTime(a.kickoffET)-parseTime(b.kickoffET);
  });
  $("#count").textContent=`${rows.length} game${rows.length===1?"":"s"}`;
  $("#games").innerHTML=rows.length?rows.map(card).join(""):`<div class="empty">No games match the current filters.</div>`;
}
["search","dateFilter","sort","viewFilter"].forEach(id=>$("#"+id).addEventListener("input",render));
render();
