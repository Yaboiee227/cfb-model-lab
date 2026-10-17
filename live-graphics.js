(() => {
  const prefersReduced=()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const animationsEnabled=()=>localStorage.getItem('cb-live-animations')!=='0'&&!prefersReduced();
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(v):String(v??'');

  function fieldPosition(game,summary){
    const competition=summary?.header?.competitions?.[0]||{};
    const situation=competition.situation||{};
    let yard=Number(situation.yardLine??game.yardLine);
    if(!Number.isFinite(yard))return null;
    yard=Math.max(0,Math.min(100,yard));
    const possession=String(situation.possession||game.possessionTeamId||'');
    const homeId=String(game.home.id),awayId=String(game.away.id);
    let x=yard;
    if(possession&&possession===homeId)x=100-yard;
    return {x,down:Number(situation.down??game.down)||null,distance:Number(situation.distance??game.distance)||null,possession};
  }

  function renderField(container,game,summary){
    const pos=fieldPosition(game,summary);
    if(!pos){container.innerHTML='<div class="graphic-unavailable">Field position not available for this game.</div>';return;}
    const first=Math.max(0,Math.min(100,pos.x+(pos.possession===String(game.home.id)?-1:1)*(pos.distance||0)));
    container.innerHTML=`<div class="football-field ${animationsEnabled()?'field-animate':''}"><div class="endzone left">${esc(game.away.name)}</div><div class="field-inner"><div class="yard-grid"></div><div class="line-scrimmage" style="left:${pos.x}%"></div>${pos.distance!==null?`<div class="first-down-line" style="left:${first}%"></div>`:''}<div class="ball-marker" style="left:${pos.x}%" title="Ball position"><span>◆</span></div></div><div class="endzone right">${esc(game.home.name)}</div></div><div class="field-caption"><strong>${pos.down?`${ordinal(pos.down)} & ${pos.distance??'—'}`:'Current field position'}</strong><span>${esc(game.lastPlay||'')}</span></div>`;
  }
  const ordinal=n=>n===1?'1st':n===2?'2nd':n===3?'3rd':`${n}th`;

  function renderDrive(container,summary){
    const drive=summary?.drives?.current;
    if(!drive){container.innerHTML='<div class="graphic-unavailable">Current-drive data not available for this game.</div>';return;}
    const plays=drive.plays||[];
    const desc=drive.description||`${plays.length} plays`;
    const start=Number(drive.start?.yardLine),end=Number(drive.end?.yardLine);
    const pct=Number.isFinite(start)&&Number.isFinite(end)?Math.max(4,Math.min(100,Math.abs(end-start))):Math.min(100,plays.length*9);
    container.innerHTML=`<div class="drive-summary"><div><span>Current drive</span><strong>${esc(drive.team?.displayName||'Offense')}</strong></div><div><span>Drive</span><strong>${esc(desc)}</strong></div><div><span>Time</span><strong>${esc(drive.timeElapsed?.displayValue||'—')}</strong></div></div><div class="drive-track"><i style="width:${pct}%"></i></div><div class="drive-plays">${plays.slice(-5).map(p=>`<span>${esc(p.text||p.shortText||'Play')}</span>`).join('')}</div>`;
  }

  function setupCanvas(canvas,height=210){
    const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=Math.max(280,rect.width||600);canvas.width=w*dpr;canvas.height=height*dpr;canvas.style.height=`${height}px`;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);return{ctx,w,h:height};
  }
  function css(name,fallback){return getComputedStyle(document.documentElement).getPropertyValue(name).trim()||fallback;}
  function drawLine(canvas,values,{min=0,max=1,reference=null,label=''}={}){
    if(!canvas||values.length<2)return false;const{ctx,w,h}=setupCanvas(canvas),pad=26,line=css('--accent','#b9ff3f'),muted=css('--muted','#91a2b9'),grid=css('--line','rgba(255,255,255,.1)'),ref=css('--accent-2','#3bd7ff');ctx.clearRect(0,0,w,h);ctx.strokeStyle=grid;ctx.lineWidth=1;for(let i=0;i<5;i++){const y=pad+(h-pad*2)*(i/4);ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-pad,y);ctx.stroke()}if(reference!==null){const y=h-pad-((reference-min)/(max-min))*(h-pad*2);ctx.strokeStyle=ref;ctx.setLineDash([5,5]);ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-pad,y);ctx.stroke();ctx.setLineDash([])}ctx.strokeStyle=line;ctx.lineWidth=2.5;ctx.beginPath();values.forEach((v,i)=>{const x=pad+(w-pad*2)*(i/(values.length-1)),y=h-pad-((v-min)/(max-min))*(h-pad*2);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();ctx.fillStyle=muted;ctx.font='11px system-ui';ctx.fillText(label,pad,15);return true;}

  function renderWinProbability(container,summary,projection){
    const series=(summary?.winprobability||[]).map(p=>Number(p.homeWinPercentage)).filter(Number.isFinite);
    if(series.length<2){container.innerHTML='<div class="graphic-unavailable">Live win probability not available for this game.</div>';return;}
    container.innerHTML='<canvas aria-label="Live home-team win probability"></canvas><div class="chart-key"><span>Live win probability</span><span>Pregame model reference</span></div>';
    const ref=Number(projection?.homeWinProbability)/100;requestAnimationFrame(()=>drawLine(container.querySelector('canvas'),series,{min:0,max:1,reference:Number.isFinite(ref)?ref:null,label:'Home win probability'}));
  }

  function marginSeries(summary){
    const plays=summary?.plays||[];return plays.map(p=>{const h=Number(p.homeScore),a=Number(p.awayScore);return Number.isFinite(h)&&Number.isFinite(a)?h-a:null}).filter(v=>v!==null);
  }
  function renderMomentum(container,summary){
    const series=marginSeries(summary);if(series.length<2){container.innerHTML='<div class="graphic-unavailable">Score-margin timeline not available for this game.</div>';return;}const max=Math.max(7,...series.map(Math.abs));container.innerHTML='<canvas aria-label="Score margin over time"></canvas><div class="chart-key"><span>Home margin above zero</span><span>Away margin below zero</span></div>';requestAnimationFrame(()=>drawLine(container.querySelector('canvas'),series,{min:-max,max,label:'Score margin'}));
  }

  function eventBanner(summary){
    const play=(summary?.plays||[]).slice().reverse().find(p=>p.scoringPlay||/turnover|intercept|fumble|touchdown|field goal/i.test(p.text||''));if(!play)return'';let type='Big play';if(/touchdown/i.test(play.text||''))type='Touchdown';else if(/field goal/i.test(play.text||''))type='Field goal';else if(/turnover|intercept|fumble/i.test(play.text||''))type='Turnover';return`<div class="live-event-banner ${animationsEnabled()?'event-animate':''}"><strong>${type}</strong><span>${esc(play.text||'')}</span></div>`;
  }

  function render(container,{game,summary,projection}){
    if(!container)return;container.innerHTML=`<div class="graphics-toolbar"><span>Live graphics use ESPN fields when available.</span><label><input type="checkbox" id="liveAnimationsToggle" ${animationsEnabled()?'checked':''}> Animations</label></div>${eventBanner(summary)}<div class="live-graphics-grid"><article><div class="graphic-head"><h4>Field position</h4><button class="tooltip-button" type="button" title="Shows approximate ball position, line of scrimmage and first-down line from the current ESPN situation.">?</button></div><div data-live-field></div></article><article><div class="graphic-head"><h4>Current drive</h4><button class="tooltip-button" type="button" title="Tracks current-drive plays, yardage and time when ESPN publishes drive data.">?</button></div><div data-live-drive></div></article><article><div class="graphic-head"><h4>Win probability</h4><button class="tooltip-button" type="button" title="Live ESPN win probability with your pregame model probability shown as a reference line.">?</button></div><div data-live-winprob></div></article><article><div class="graphic-head"><h4>Score margin</h4><button class="tooltip-button" type="button" title="Tracks the home-team score margin across available play snapshots.">?</button></div><div data-live-momentum></div></article></div>`;renderField(container.querySelector('[data-live-field]'),game,summary);renderDrive(container.querySelector('[data-live-drive]'),summary);renderWinProbability(container.querySelector('[data-live-winprob]'),summary,projection);renderMomentum(container.querySelector('[data-live-momentum]'),summary);container.querySelector('#liveAnimationsToggle')?.addEventListener('change',e=>{localStorage.setItem('cb-live-animations',e.target.checked?'1':'0');render(container,{game,summary,projection})});
  }

  window.CBLiveGraphics={render,renderField,renderDrive,renderWinProbability,renderMomentum,animationsEnabled};
})();
