(() => {
  const loadCss = href => {
    if (document.querySelector(`link[href="${href}"]`)) return;
    const link=document.createElement('link');link.rel='stylesheet';link.href=href;link.dataset.cbLiveSuite='true';document.head.appendChild(link);
  };
  const loadScript = src => new Promise((resolve,reject)=>{
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const script=document.createElement('script');script.src=src;script.async=false;script.dataset.cbLiveSuite='true';script.onload=resolve;script.onerror=()=>reject(new Error(`Could not load ${src}`));document.body.appendChild(script);
  });
  async function boot(){
    loadCss('live-suite.css');
    loadCss('live-suite-fixes.css');
    for (const src of ['live-data.js','markets-sportsbooks.js','markets-prediction.js','live-graphics.js','game-detail.js','live-ui.js','live-start.js']) {
      await loadScript(src);
    }
  }
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>boot().catch(console.error),{once:true});
  else boot().catch(console.error);
})();
