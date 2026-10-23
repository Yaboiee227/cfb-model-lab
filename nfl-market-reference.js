/* Separate comparison overlay; never changes canonical fields or grading records. */
(() => {
  if (window.CB_ACTIVE_LEAGUE !== 'nfl') return;
  const numeric = x => typeof x === 'number' && Number.isFinite(x);
  async function start() {
    try {
      const response = await fetch('nfl_data/site/market-reference.json', {cache:'no-store'});
      if (!response.ok) throw new Error('Market comparison unavailable');
      const data = await response.json();
      const age = Date.now() - Date.parse(data.observedAt);
      const usable = Number.isFinite(age) && age >= 0 && age <= 24*60*60*1000;
      let attempts=0;
      const apply = () => {
        if (typeof STATE === 'undefined' || !STATE.projections.length) {
          if (++attempts < 100) setTimeout(apply,100);
          return;
        }
        let count=0;
        if (usable) for (const game of STATE.projections) {
          const ref=data.games.find(r=>r.gameId===game.gameId);
          if (!ref || ref.home!==game.homeTeam || ref.away!==game.awayTeam || Date.parse(ref.kickoffUtc)<=Date.now()) continue;
          if (!numeric(ref.marketSpreadHome) || !numeric(ref.marketTotal) || Math.abs(ref.modelSpreadHome-game.modelSpreadHome)>1e-9) continue;
          Object.assign(game,{marketSpreadHome:ref.marketSpreadHome,marketTotal:ref.marketTotal,
            marketSource:ref.marketSource+'; retrieved '+data.observedAt+'; provider update time unavailable; NOT a grading lock',
            marketObservedAt:data.observedAt,executionVerified:false});
          count++;
        }
        const note=document.createElement('p');note.id='nflMarketReferenceNotice';note.className='nfl-policy-note';note.setAttribute('role','status');
        note.textContent=usable ? `${count} upcoming games: DraftKings via ESPN, retrieved ${new Date(data.observedAt).toLocaleString('en-US',{timeZone:'America/New_York'})} ET. Dated comparison, not live execution or a grading lock. Gap = home market spread minus home model spread. Completed games have no current quote.` : 'Market comparison snapshot is unavailable or older than 24 hours. No current market gaps are published.';
        document.getElementById('projectionCount')?.after(note);
        filterProjections();renderHeroMetrics();
      };
      apply();
    } catch(error) { console.warn('NFL market reference:',error.message); }
  }
  document.addEventListener('DOMContentLoaded',start,{once:true});
})();
