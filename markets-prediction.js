(() => {
  const state={cache:new Map(),historyKey:'cb-prediction-market-history'};
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(v):String(v??'');
  const norm=v=>window.CBLiveData?.normalizeName(v)||String(v||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const teamTokens=name=>new Set(norm(name).split(' ').filter(x=>x.length>2));
  const overlap=(text,name)=>{const t=norm(text),tokens=[...teamTokens(name)];return tokens.some(x=>t.includes(x));};
  const fmtPct=p=>Number.isFinite(Number(p))?`${(Number(p)*100).toFixed(1)}%`:'—';
  const fmtMoney=n=>Number.isFinite(Number(n))?Number(n).toLocaleString(undefined,{maximumFractionDigits:0}):'—';
  const nowIso=()=>new Date().toISOString();

  function loadHistory(){try{return JSON.parse(localStorage.getItem(state.historyKey)||'{}')}catch{return{}}}
  function savePoint(source,eventId,homeProb){if(!Number.isFinite(homeProb))return;const all=loadHistory(),key=`${source}:${eventId}`,arr=all[key]||[];arr.push({ts:nowIso(),home:homeProb});all[key]=arr.slice(-80);try{localStorage.setItem(state.historyKey,JSON.stringify(all))}catch{}}
  function history(source,eventId){return loadHistory()[`${source}:${eventId}`]||[]}
  function spark(points=[]){const vals=points.map(x=>Number(x.home)).filter(Number.isFinite);if(vals.length<2)return'<span class="market-spark-empty">Collecting snapshots</span>';const min=Math.min(...vals),max=Math.max(...vals),r=max-min||1,pts=vals.map((v,i)=>`${(i/(vals.length-1))*100},${24-((v-min)/r)*20}`).join(' ');return`<svg class="market-spark" viewBox="0 0 100 28" aria-hidden="true"><polyline points="${pts}" fill="none" vector-effect="non-scaling-stroke"/></svg>`}

  async function mockData(liveGame){const mock=await fetch('data/mock-live.json',{cache:'no-store'}).then(r=>r.json());if(liveGame.eventId!=='MOCK-CFB-001')return{kalshi:{matched:false},polymarket:{matched:false}};return mock.predictionMarkets||{};}

  function pickKalshiMarkets(payload,game){
    const events=payload.events||[];const candidates=[];
    for(const event of events){
      const blob=`${event.title||''} ${event.sub_title||''}`;
      if(!(overlap(blob,game.home.name)&&overlap(blob,game.away.name)))continue;
      for(const market of event.markets||[]){candidates.push({...market,eventTitle:event.title||''});}
    }
    if(!candidates.length)return{matched:false};
    const result={matched:true,updatedAt:nowIso(),homeProbability:null,awayProbability:null,volume:0,liquidity:0,marketTickers:[]};
    for(const m of candidates){
      const blob=`${m.title||''} ${m.subtitle||''} ${m.yes_sub_title||''} ${m.no_sub_title||''} ${m.eventTitle||''}`;
      const bid=Number(m.yes_bid_dollars),ask=Number(m.yes_ask_dollars),last=Number(m.last_price_dollars);
      const p=Number.isFinite(bid)&&Number.isFinite(ask)?(bid+ask)/2:Number.isFinite(last)?last:null;
      if(p===null)continue;
      if(overlap(m.yes_sub_title||m.title,game.home.name))result.homeProbability=p;
      if(overlap(m.yes_sub_title||m.title,game.away.name))result.awayProbability=p;
      result.volume+=Number(m.volume_fp||m.volume||0)||0;result.liquidity+=Number(m.liquidity_dollars||m.liquidity||0)||0;result.marketTickers.push(m.ticker);
    }
    if(result.homeProbability!==null&&result.awayProbability===null)result.awayProbability=1-result.homeProbability;
    if(result.awayProbability!==null&&result.homeProbability===null)result.homeProbability=1-result.awayProbability;
    if(result.homeProbability===null&&result.awayProbability===null)return{matched:false};
    return result;
  }

  async function fetchKalshi(game){
    const url='https://external-api.kalshi.com/trade-api/v2/events?status=open&limit=200&with_nested_markets=true';
    const json=await fetch(url,{cache:'no-store',headers:{Accept:'application/json'}}).then(r=>{if(!r.ok)throw new Error(`Kalshi ${r.status}`);return r.json()});
    return pickKalshiMarkets(json,game);
  }

  function parseJsonArray(value){if(Array.isArray(value))return value;try{return JSON.parse(value)}catch{return[]}}
  function pickPolymarket(markets,game){
    const candidates=(Array.isArray(markets)?markets:markets?.data||[]).filter(m=>{const blob=`${m.question||''} ${m.title||''} ${m.description||''} ${m.slug||''}`;return overlap(blob,game.home.name)&&overlap(blob,game.away.name)});
    if(!candidates.length)return{matched:false};
    let home=null,away=null,volume=0,liquidity=0,tokenIds=[];
    for(const m of candidates){
      const outcomes=parseJsonArray(m.outcomes),prices=parseJsonArray(m.outcomePrices).map(Number),tokens=parseJsonArray(m.clobTokenIds);
      outcomes.forEach((outcome,i)=>{if(overlap(outcome,game.home.name)&&Number.isFinite(prices[i])){home=prices[i];if(tokens[i])tokenIds.push(tokens[i])}if(overlap(outcome,game.away.name)&&Number.isFinite(prices[i])){away=prices[i];if(tokens[i])tokenIds.push(tokens[i])}});
      if(outcomes.length===2&&home===null&&away===null){const yesIndex=outcomes.findIndex(x=>/^yes$/i.test(x));if(yesIndex>=0){const blob=`${m.question||''} ${m.title||''}`;if(overlap(blob,game.home.name)){home=prices[yesIndex];away=1-home}else if(overlap(blob,game.away.name)){away=prices[yesIndex];home=1-away}}}
      volume+=Number(m.volumeNum||m.volume||0)||0;liquidity+=Number(m.liquidityNum||m.liquidity||0)||0;
    }
    if(home===null&&away!==null)home=1-away;if(away===null&&home!==null)away=1-home;
    return home===null&&away===null?{matched:false}:{matched:true,updatedAt:nowIso(),homeProbability:home,awayProbability:away,volume,liquidity,tokenIds};
  }

  async function fetchPolymarket(game){
    const q=encodeURIComponent(`${game.away.name} ${game.home.name}`);
    const urls=[`https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=100&q=${q}`,`https://gamma-api.polymarket.com/markets?closed=false&limit=100`];
    let lastError;
    for(const url of urls){try{const json=await fetch(url,{cache:'no-store',headers:{Accept:'application/json'}}).then(r=>{if(!r.ok)throw new Error(`Polymarket ${r.status}`);return r.json()});const picked=pickPolymarket(json,game);if(picked.matched)return picked;}catch(e){lastError=e}}
    if(lastError)throw lastError;return{matched:false};
  }

  async function loadForGame(game,{force=false}={}){
    const key=String(game.eventId),cached=state.cache.get(key);if(!force&&cached&&Date.now()-cached.ts<60000)return cached.data;
    let data;
    if(window.CBLiveData?.state.mockMode)data=await mockData(game);else{
      const [k,p]=await Promise.allSettled([fetchKalshi(game),fetchPolymarket(game)]);
      data={kalshi:k.status==='fulfilled'?k.value:{matched:false,error:'Data unavailable'},polymarket:p.status==='fulfilled'?p.value:{matched:false,error:'Data unavailable'}};
    }
    if(data.kalshi?.matched){savePoint('kalshi',game.eventId,Number(data.kalshi.homeProbability));data.kalshi.history=history('kalshi',game.eventId)}
    if(data.polymarket?.matched){savePoint('polymarket',game.eventId,Number(data.polymarket.homeProbability));data.polymarket.history=history('polymarket',game.eventId)}
    state.cache.set(key,{ts:Date.now(),data});return data;
  }

  function sourceCard(label,row,projection,eventId,source){
    if(!row?.matched)return`<article class="market-source-card"><div class="market-source-head"><h4>${label}</h4><span>Public market API</span></div><p class="market-source-missing">${esc(row?.error||'No market listed / no reliable game match')}</p></article>`;
    const model=Number(projection?.homeWinProbability)/100,diff=Number.isFinite(model)&&Number.isFinite(Number(row.homeProbability))?model-Number(row.homeProbability):null;
    const hist=row.history||history(source,eventId);
    return`<article class="market-source-card"><div class="market-source-head"><h4>${label}</h4><span>${row.updatedAt?new Date(row.updatedAt).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}):'Update time unavailable'}</span></div><div class="market-line-grid"><div><span>${esc(projection?.homeTeam||'Home')} probability</span><strong>${fmtPct(row.homeProbability)}</strong><small>Current market price</small></div><div><span>${esc(projection?.awayTeam||'Away')} probability</span><strong>${fmtPct(row.awayProbability)}</strong><small>Current market price</small></div><div><span>Volume</span><strong>${fmtMoney(row.volume)}</strong><small>When available</small></div><div><span>Liquidity</span><strong>${fmtMoney(row.liquidity)}</strong><small>When available</small></div></div><div class="market-difference"><span>Difference from market</span><strong>${diff===null?'—':`${diff>0?'+':''}${(diff*100).toFixed(1)} pts`}</strong><small>Model home win probability minus current prediction-market probability.</small></div><div class="prediction-history"><span>Price movement while this site is open</span>${spark(hist)}</div></article>`;
  }

  async function renderDetail(container,game,projection){if(!container)return;container.innerHTML='<div class="market-loading">Loading prediction markets…</div>';const data=await loadForGame(game);container.innerHTML=`<div class="market-detail-grid prediction-market-grid">${sourceCard('Kalshi',data.kalshi,projection,game.eventId,'kalshi')}${sourceCard('Polymarket',data.polymarket,projection,game.eventId,'polymarket')}</div><p class="market-panel-note">Prediction-market matching uses team aliases plus market-title keywords. When a confident match is not found, the site shows “No market listed” rather than guessing.</p>`;}

  window.CBMarketsPrediction={state,loadForGame,renderDetail,fetchKalshi,fetchPolymarket};
})();
