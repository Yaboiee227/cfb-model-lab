(() => {
  const state = { data:null, lastFetch:0, timer:null, previous:new Map() };
  const BOOKS = ['fanduel','draftkings'];
  const bookLabel = key => key === 'fanduel' ? 'FanDuel' : 'DraftKings';
  const esc = v => typeof escapeHtml === 'function' ? escapeHtml(v) : String(v ?? '').replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[m]));
  const moneylineProb = ml => {
    const n = Number(ml); if (!Number.isFinite(n)) return null;
    return n < 0 ? (-n)/((-n)+100) : 100/(n+100);
  };
  const pctText = p => Number.isFinite(p) ? `${(p*100).toFixed(1)}%` : '—';
  const lineText = n => Number.isFinite(Number(n)) ? `${Number(n)>0?'+':''}${Number(n).toFixed(1)}` : '—';
  const mlText = n => Number.isFinite(Number(n)) ? `${Number(n)>0?'+':''}${Number(n)}` : '—';

  async function load(force=false) {
    if (!force && state.data && Date.now()-state.lastFetch < 45000) return state.data;
    try {
      if (window.CBLiveData?.state.mockMode) {
        const mock = await fetch('data/mock-live.json',{cache:'no-store'}).then(r=>r.json());
        state.data = mock.sportsbooks || {generatedAt:null,games:[]};
      } else {
        state.data = await fetch(`data/markets-sportsbooks.json?ts=${Date.now()}`,{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject(new Error(`sportsbook snapshot ${r.status}`)));
      }
      state.lastFetch = Date.now();
      document.dispatchEvent(new CustomEvent('cb:sportsbooks-update',{detail:{data:state.data}}));
    } catch (error) {
      document.dispatchEvent(new CustomEvent('cb:market-error',{detail:{source:'sportsbooks',error:String(error?.message||error)}}));
      state.data = state.data || {generatedAt:null,games:[]};
    }
    return state.data;
  }

  function matchGame(liveGame) {
    const games = state.data?.games || [];
    return games.find(row => window.CBLiveData?.sameTeam(row.homeTeam,liveGame.home.name) && window.CBLiveData?.sameTeam(row.awayTeam,liveGame.away.name)) || null;
  }

  function noVig(book) {
    const h = moneylineProb(book?.moneyline?.home), a = moneylineProb(book?.moneyline?.away);
    if (h===null || a===null || h+a===0) return {home:null,away:null,vig:null};
    return { home:h/(h+a), away:a/(h+a), vig:h+a-1 };
  }

  function spark(history=[], key='spreadHome') {
    const vals = history.map(p=>Number(p[key])).filter(Number.isFinite);
    if (vals.length < 2) return '<span class="market-spark-empty">—</span>';
    const min=Math.min(...vals),max=Math.max(...vals),range=max-min||1;
    const pts=vals.map((v,i)=>`${(i/(vals.length-1))*100},${24-((v-min)/range)*20}`).join(' ');
    return `<svg class="market-spark" viewBox="0 0 100 28" aria-hidden="true"><polyline points="${pts}" fill="none" vector-effect="non-scaling-stroke"/></svg>`;
  }

  function currentSummary(book) {
    if (!book) return 'No market listed';
    const spread = Number.isFinite(Number(book.spread?.home)) ? `Home ${lineText(book.spread.home)}` : 'Spread —';
    const total = Number.isFinite(Number(book.total?.point)) ? `O/U ${Number(book.total.point).toFixed(1)}` : 'O/U —';
    return `${spread} · ${total}`;
  }

  function renderCompact(liveGame) {
    const row = matchGame(liveGame);
    if (!row) return '<span class="market-source-missing">Sportsbooks: no current market file match</span>';
    return `<div class="compact-market-grid">${BOOKS.map(key=>{
      const book=row.books?.[key];
      return `<div><span>${bookLabel(key)}</span><strong>${esc(currentSummary(book))}</strong><small>${book?.updatedAt?`Updated ${esc(formatTime(book.updatedAt))}`:'No market listed'}</small></div>`;
    }).join('')}</div>`;
  }

  function formatTime(value) {
    if (!value) return '—';
    const d=new Date(value); return Number.isNaN(d.getTime())?String(value):d.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
  }

  function modelDiff(projection, book) {
    const nv=noVig(book);
    const model=Number(projection?.homeWinProbability)/100;
    return Number.isFinite(model) && nv.home!==null ? model-nv.home : null;
  }

  function renderDetail(container, liveGame, projection) {
    const row=matchGame(liveGame);
    if (!container) return;
    if (!row) {
      container.innerHTML='<div class="market-unavailable"><strong>FanDuel / DraftKings</strong><span>No market listed or no game match in the latest sportsbook snapshot.</span></div>';
      return;
    }
    container.innerHTML=`<div class="market-detail-grid">${BOOKS.map(key=>{
      const book=row.books?.[key];
      if (!book) return `<article class="market-source-card"><h4>${bookLabel(key)}</h4><p class="market-source-missing">No market listed</p></article>`;
      const nv=noVig(book), diff=modelDiff(projection,book);
      const open=book.opening||{};
      return `<article class="market-source-card">
        <div class="market-source-head"><h4>${bookLabel(key)}</h4><span>${book.updatedAt?`Updated ${esc(formatTime(book.updatedAt))}`:'Update time unavailable'}</span></div>
        <div class="market-line-grid">
          <div><span>Spread</span><strong>${lineText(book.spread?.home)} home</strong><small>Open ${lineText(open.spread?.home)}</small></div>
          <div><span>Total</span><strong>${Number.isFinite(Number(book.total?.point))?Number(book.total.point).toFixed(1):'—'}</strong><small>Open ${Number.isFinite(Number(open.total?.point))?Number(open.total.point).toFixed(1):'—'}</small></div>
          <div><span>Moneyline</span><strong>${mlText(book.moneyline?.home)} / ${mlText(book.moneyline?.away)}</strong><small>Home / Away</small></div>
          <div><span>No-vig home probability</span><strong>${pctText(nv.home)}</strong><small>Raw vig ${(Number.isFinite(nv.vig)?nv.vig*100:0).toFixed(1)}%</small></div>
        </div>
        <div class="market-difference"><span>Difference from market</span><strong>${diff===null?'—':`${diff>0?'+':''}${(diff*100).toFixed(1)} pts`}</strong><small>Model home win probability minus no-vig ${bookLabel(key)} home probability.</small></div>
        <div class="market-history-row"><div><span>Spread movement</span>${spark(book.history,'spreadHome')}</div><div><span>Total movement</span>${spark(book.history,'total')}</div></div>
      </article>`;
    }).join('')}</div>`;
  }

  function changedKeys(liveGame) {
    const row=matchGame(liveGame); if (!row) return [];
    const changed=[];
    for (const key of BOOKS) {
      const book=row.books?.[key]; if (!book) continue;
      const sig=JSON.stringify([book.spread?.home,book.total?.point,book.moneyline?.home,book.moneyline?.away]);
      const cacheKey=`${liveGame.eventId}:${key}`;
      const prev=state.previous.get(cacheKey); if (prev && prev!==sig) changed.push(key);
      state.previous.set(cacheKey,sig);
    }
    return changed;
  }

  function schedule() {
    clearTimeout(state.timer);
    if (document.hidden) return;
    const live=window.CBLiveData?.state.games?.some(g=>g.state==='in');
    if (live) state.timer=setTimeout(async()=>{await load(true);schedule();},60000);
  }
  document.addEventListener('cb:live-update', async event=>{ if (event.detail.games.some(g=>g.state==='in')) await load(); schedule(); });
  document.addEventListener('visibilitychange',()=>{clearTimeout(state.timer);if(!document.hidden){load(true);schedule();}});

  window.CBMarketsSportsbooks={state,load,matchGame,noVig,renderCompact,renderDetail,changedKeys,moneylineProb};
})();
