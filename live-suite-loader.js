(() => {
  const league = () => String(window.CB_ACTIVE_LEAGUE || 'cfb').toLowerCase() === 'nfl' ? 'nfl' : 'cfb';
  const ASSET_VERSION = '20261022-current-week-projections-1';
  const versioned = src => `${src}${src.includes('?') ? '&' : '?'}v=${encodeURIComponent(ASSET_VERSION)}`;

  const loadCss = href => {
    if (document.querySelector(`link[data-cb-live-asset="${href}"]`)) return;
    const link=document.createElement('link');link.rel='stylesheet';link.href=versioned(href);link.dataset.cbLiveSuite='true';link.dataset.cbLiveAsset=href;document.head.appendChild(link);
  };
  const loadScript = src => new Promise((resolve,reject)=>{
    if (document.querySelector(`script[data-cb-live-asset="${src}"]`)) return resolve();
    const script=document.createElement('script');script.src=versioned(src);script.async=false;script.dataset.cbLiveSuite='true';script.dataset.cbLiveAsset=src;script.onload=resolve;script.onerror=()=>reject(new Error(`Could not load ${src}`));document.body.appendChild(script);
  });

  function setText(selector, value) {
    const el=document.querySelector(selector);
    if (el && el.textContent !== value) el.textContent=value;
  }

  function syncCfbWeek8Status(){
    if(league()!=='cfb')return;
    const banner=document.querySelector('main > .section-shell > .hold-note');
    if(banner) banner.innerHTML='<strong>CFB · Week 8 active production · Canonical HOLD</strong> — Pregame research, market locks, provenance and frozen evidence are updated through the current production state without reconstructing information after results. <a href="week-8.html">Open Week 8 readiness →</a>';
    setText('.hero-kicker-row .eyebrow','FBS MODEL • WEEK 8 COMMAND CENTER');
    setText('.hero-kicker-row .research-chip','Week 8 · Research shadow');
    const projectionTitle=document.getElementById('projectionsTitle');
    if(projectionTitle) projectionTitle.textContent='Week 8 research projection board';
    const projectionIntro=document.querySelector('#projections .section-heading p:not(.eyebrow)');
    if(projectionIntro) projectionIntro.textContent='The active Week 8 board shows prospectively preserved research projections with current market comparison, data readiness and pregame context. Canonical publication remains gated, and completed games never rewrite the frozen evidence.';
  }

  function legacyResultCounts(key){
    let rows=[];
    try { rows=(typeof STATE!=='undefined' && Array.isArray(STATE.results)) ? STATE.results : []; } catch(_){ rows=[]; }
    let wins=0,losses=0,pushes=0;
    rows.forEach(row=>{
      const value=String(row?.[key]||'').toUpperCase();
      if(value==='WIN')wins++;else if(value==='LOSS')losses++;else if(value==='PUSH')pushes++;
    });
    const decisions=wins+losses;
    return {wins,losses,pushes,pct:decisions?wins/decisions*100:null};
  }

  function syncLegacyFallback(){
    const grid=document.querySelector('#record > .record-grid');
    if(!grid || document.getElementById('recordTrackerV2')?.parentElement?.classList.contains('record-v2-active')) return;
    const cards=[...grid.querySelectorAll(':scope > .record-card')];
    if(cards.length<3)return;
    const totals=legacyResultCounts('totalResult');
    const card=cards[2];
    const label=card.querySelector('.record-card-head span');
    const small=card.querySelector('.record-card-head small');
    const strong=card.querySelector(':scope > strong');
    const sub=card.querySelector('.record-sub');
    if(label)label.textContent='Totals';
    if(small)small.textContent='Over / under';
    if(strong){strong.removeAttribute('id');strong.textContent=`${totals.wins}-${totals.losses}${totals.pushes?`-${totals.pushes}`:''}`;}
    if(sub)sub.innerHTML=`<span>${totals.pct===null?'—':`${totals.pct.toFixed(1)}%`}</span> win rate${totals.pushes?` <span>•</span> ${totals.pushes} push${totals.pushes===1?'':'es'}`:''}`;
  }

  function syncSharedCopy(){
    syncCfbWeek8Status();
    setText('#recordTitle','Projection performance');
    const recordIntro=document.querySelector('#record .section-heading p:not(.eyebrow)');
    if(recordIntro) recordIntro.textContent='Tracks model projection positions against the market spread and total saved when the projection was published. ATS, Totals and Straight Up are graded separately. This is not a wager ledger.';

    const ruleItems=[...document.querySelectorAll('.projection-rules .rule-item')];
    const marketRule=ruleItems.find(x=>x.querySelector('strong')?.textContent?.trim()==='Market');
    if(marketRule?.querySelector('small')) marketRule.querySelector('small').textContent='Current comparison; publication snapshot is locked for grading';
    const validationRule=ruleItems.find(x=>x.querySelector('strong')?.textContent?.trim()==='Validation');
    if(validationRule?.querySelector('small')) validationRule.querySelector('small').textContent='Research and publication state stay separate';

    const sort=document.getElementById('sortFilter');
    if(sort){
      const spread=[...sort.options].find(o=>o.value==='spreadgap');
      const total=[...sort.options].find(o=>o.value==='totalgap');
      if(spread) spread.textContent='Spread difference';
      if(total) total.textContent='Total difference';
    }
    const headers=document.querySelectorAll('.projection-table thead th');
    if(headers.length>=5) headers[4].textContent='Spread difference';

    const glossary=[...document.querySelectorAll('.glossary-grid article')];
    const byTitle=title=>glossary.find(x=>x.querySelector('h3')?.textContent?.trim()===title);
    const ats=byTitle('ATS');
    if(ats?.querySelector('p')) ats.querySelector('p').textContent='Against the spread. The model/market difference identifies the projection side, then the final score is graded against the market spread saved when the projection was published.';
    const total=byTitle('Total');
    if(total?.querySelector('p')) total.querySelector('p').textContent='The model total is compared with the market total to create an Over or Under projection. The record is graded against the publication-time market total.';
    const ml=byTitle('Moneyline');
    if(ml?.querySelector('p')) ml.querySelector('p').textContent='The projection board may show a model-implied moneyline. The record tracker also saves the publication-time market moneyline for reference, but Straight-Up W/L is graded only on whether the projected winner won.';
    const gap=byTitle('Model / market gap') || byTitle('Model / market difference');
    if(gap){
      if(gap.querySelector('h3')) gap.querySelector('h3').textContent='Model / market difference';
      if(gap.querySelector('p')) gap.querySelector('p').textContent='The numerical difference between the independent model and the current market reference. It identifies a projection direction; it is not automatically expected value or a wager instruction.';
    }

    const trendIntro=document.querySelector('#trends .section-heading p:not(.eyebrow)');
    if(trendIntro && /official model record/i.test(trendIntro.textContent)) trendIntro.textContent=trendIntro.textContent.replace(/official model record/i,'official projection-performance record');

    const nflPolicy=document.querySelector('.nfl-policy-note');
    if(nflPolicy) nflPolicy.textContent='NFL alternative-line research targets, moneyline comparisons, thresholds and sizing remain locked until prospective calibration earns them. Model/market differences and win probability are descriptive research outputs.';
    document.querySelectorAll('.nfl-validation-strip div').forEach(box=>{
      const label=box.querySelector('span');
      if(label?.textContent?.trim()==='Recommendation state') label.textContent='Projection state';
    });

    const tracker=document.getElementById('recordTrackerV2');
    if(tracker){
      const weekMeta=[...tracker.querySelectorAll('.rt-meta > span')].find(x=>/^Week graded/i.test(x.textContent||''));
      const weekValue=weekMeta?.querySelector('strong')?.textContent?.trim();
      if(weekValue==='—'){
        const status=tracker.querySelector('.rt-meta .rt-status');
        if(status){status.className='rt-status rt-pending';status.textContent='◷ Awaiting first graded week';}
      }
    } else {
      syncLegacyFallback();
    }
  }

  function syncProductCopy(){
    setText('#topSignalsTitle','Top spread differences');
    const topCopy=document.querySelector('.top-signals-head p');
    if(topCopy) topCopy.textContent='Largest current model/market differences for the loaded week. Ranked by difference only—not by publication readiness.';
    document.querySelectorAll('.top-signal-main b').forEach(el=>{
      const next=el.textContent.replace(/spread gap/gi,'spread difference');
      if(el.textContent!==next) el.textContent=next;
    });
    document.querySelectorAll('.signal-readiness-row small').forEach(el=>{
      const next=el.textContent.replace(/release checks/gi,'readiness checks');
      if(el.textContent!==next) el.textContent=next;
    });
    setText('.model-product-head h3','Projection differences, alternatives & readiness');
    document.querySelectorAll('.readiness-title-row .command-label').forEach(el=>{
      if(/SPREAD RELEASE GATES/i.test(el.textContent)) el.textContent='SPREAD READINESS CHECKS';
    });
    document.querySelectorAll('.readiness-blocker-copy').forEach(el=>{
      let next=el.textContent.replace(/release blockers/gi,'publication blockers');
      next=next.replace(/release state/gi,'publication state');
      if(el.textContent!==next) el.textContent=next;
    });
  }

  function installLanguageSync(){
    syncSharedCopy();syncProductCopy();
    let queued=false;
    const observer=new MutationObserver(()=>{
      if(queued)return;queued=true;
      requestAnimationFrame(()=>{queued=false;syncSharedCopy();syncProductCopy();});
    });
    observer.observe(document.body,{childList:true,subtree:true});
  }

  async function boot(){
    loadCss('slate-navigation.css');
    await loadScript('slate-navigation.js');
    loadCss('site-shell.css');
    await loadScript('site-shell.js');
    installLanguageSync();
    loadCss('record-tracker.css');
    await loadScript('record-tracker.js');
    syncSharedCopy();
    if (league() === 'nfl') {
      console.info('CB Model Projections: CFB live suite disabled for NFL league view.');
      return;
    }
    loadCss('live-suite.css');
    loadCss('live-suite-fixes.css');
    for (const src of ['live-data.js','markets-sportsbooks.js','market-runtime-sync.js','markets-prediction.js','live-graphics.js','game-detail.js','live-ui.js','live-pause-guard.js','live-start.js','live-detail-extensions.js']) {
      await loadScript(src);
    }
    syncSharedCopy();syncProductCopy();
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>boot().catch(console.error),{once:true});
  else boot().catch(console.error);
})();
