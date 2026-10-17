(() => {
  const state={data:null,lastFetch:0};
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(v):String(v??'');
  const fmtPct=p=>Number.isFinite(Number(p))?`${(Number(p)*100).toFixed(1)}%`:'—';
  const fmtMoney=n=>Number.isFinite(Number(n))?Number(n).toLocaleString(undefined,{maximumFractionDigits:0}):'—';
  const same=(a,b)=>window.CBLiveData?.sameTeam?.(a,b)||String(a||'').toLowerCase()===String(b||'').toLowerCase();

  async function load(force=false){
    if(!force&&state.data&&Date.now()-state.lastFetch<45000)return state.data;
    try{
      if(window.CBLiveData?.state.mockMode){const mock=await fetch('data/mock-live.json',{cache:'no-store'}).then(r=>r.json());state.data={generatedAt:mock.generatedAt,games:[{eventId:'MOCK-CFB-001',homeTeam:'Tennessee',awayTeam:'Alabama',kalshi:mock.predictionMarkets?.kalshi||{matched:false},polymarket:mock.predictionMarkets?.polymarket||{matched:false}}]};}
      else state.data=await fetch(`data/markets-prediction.json?ts=${Date.now()}`,{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject(new Error(`prediction snapshot ${r.status}`)));
      state.lastFetch=Date.now();document.dispatchEvent(new CustomEvent('cb:prediction-markets-update',{detail:{data:state.data}}));
    }catch(error){document.dispatchEvent(new CustomEvent('cb:market-error',{detail:{source:'prediction markets',error:String(error?.message||error)}}));state.data=state.data||{generatedAt:null,games:[]};}
    return state.data;
  }
  function matchGame(game){return(state.data?.games||[]).find(row=>String(row.eventId||'')===String(game.eventId)||same(row.homeTeam,game.home.name)&&same(row.awayTeam,game.away.name))||null;}
  function spark(points=[]){const vals=points.map(x=>Number(x.home)).filter(Number.isFinite);if(vals.length<2)return'<span class="market-spark-empty">Collecting snapshots</span>';const min=Math.min(...vals),max=Math.max(...vals),r=max-min||1,pts=vals.map((v,i)=>`${(i/(vals.length-1))*100},${24-((v-min)/r)*20}`).join(' ');return`<svg class="market-spark" viewBox="0 0 100 28" aria-hidden="true"><polyline points="${pts}" fill="none" vector-effect="non-scaling-stroke"/></svg>`;}
  function card(label,row,projection){if(!row?.matched)return`<article class="market-source-card"><div class="market-source-head"><h4>${label}</h4><span>Public market snapshot</span></div><p class="market-source-missing">${esc(row?.error||'No market listed / no reliable game match')}</p></article>`;const model=Number(projection?.homeWinProbability)/100,diff=Number.isFinite(model)&&Number.isFinite(Number(row.homeProbability))?model-Number(row.homeProbability):null;return`<article class="market-source-card"><div class="market-source-head"><h4>${label}</h4><span>${row.updatedAt?new Date(row.updatedAt).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}):'Update time unavailable'}</span></div><div class="market-line-grid"><div><span>${esc(projection?.homeTeam||'Home')} probability</span><strong>${fmtPct(row.homeProbability)}</strong><small>Current market price</small></div><div><span>${esc(projection?.awayTeam||'Away')} probability</span><strong>${fmtPct(row.awayProbability)}</strong><small>Current market price</small></div><div><span>Volume</span><strong>${fmtMoney(row.volume)}</strong><small>When available</small></div><div><span>Liquidity</span><strong>${fmtMoney(row.liquidity)}</strong><small>When available</small></div></div><div class="market-difference"><span>Difference from market</span><strong>${diff===null?'—':`${diff>0?'+':''}${(diff*100).toFixed(1)} pts`}</strong><small>Model home win probability minus current prediction-market probability.</small></div><div class="prediction-history"><span>Probability movement</span>${spark(row.history||[])}</div></article>`;}
  async function loadForGame(game,{force=false}={}){await load(force);const row=matchGame(game);return row?{kalshi:row.kalshi||{matched:false},polymarket:row.polymarket||{matched:false}}:{kalshi:{matched:false},polymarket:{matched:false}};}
  async function renderDetail(container,game,projection){if(!container)return;container.innerHTML='<div class="market-loading">Loading prediction-market snapshot…</div>';const data=await loadForGame(game);container.innerHTML=`<div class="market-detail-grid prediction-market-grid">${card('Kalshi',data.kalshi,projection)}${card('Polymarket',data.polymarket,projection)}</div><p class="market-panel-note">Prediction markets are matched in the scheduled data job using team aliases and market-title keywords. If no confident match exists, the source is shown as unavailable instead of guessed.</p>`;}
  document.addEventListener('cb:live-update',e=>{if(e.detail.games.some(g=>g.state==='in'))load();});
  window.CBMarketsPrediction={state,load,loadForGame,renderDetail,matchGame};
})();
