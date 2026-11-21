/* Current-week source-reported records only; no model input or grading changes. */
(()=>{'use strict';
const codeByTitle={'ARI at KC':'2026_11_ARI_KC','BAL at CAR':'2026_11_BAL_CAR','JAX at NYG':'2026_11_JAX_NYG','MIA at BUF':'2026_11_MIA_BUF','NO at CHI':'2026_11_NO_CHI','TB at DET':'2026_11_TB_DET','TEN at DAL':'2026_11_TEN_DAL','NYJ at LAC':'2026_11_NYJ_LAC','LV at DEN':'2026_11_LV_DEN','PIT at PHI':'2026_11_PIT_PHI','MIN vs SF · Mexico City':'2026_11_MIN_SF','CIN at WAS':'2026_11_CIN_WAS'};
async function init(){
 const cards=[...document.querySelectorAll('article.game')];
 try{
  const res=await fetch('nfl_data/site/nfl-trends.json',{cache:'no-store'});if(!res.ok)throw Error('unavailable');const doc=await res.json();if(doc.season!==2026||doc.week!==11)throw Error('wrong week');
  for(const card of cards){const id=codeByTitle[card.querySelector('h2')?.textContent];if(!id)continue;const rows=doc.trends.filter(t=>t.gameId===id);const details=document.createElement('details'), summary=document.createElement('summary');summary.textContent='Team trends · 2026 season';details.appendChild(summary);
   if(!rows.length){const p=document.createElement('p');p.textContent='No verified trend records available.';details.appendChild(p)}
   for(const trend of rows){const p=document.createElement('p');p.textContent=trend.text+' ('+trend.sampleSize+' games)';details.appendChild(p)}
   const foot=document.createElement('p');foot.textContent='Through Week 10; informational, source-reported and not independently graded. No model adjustment. Small samples and source discrepancies limit interpretation. ';const link=document.createElement('a');link.href='https://www.sharpfootballanalysis.com/betting/nfl-ats-records/';link.textContent='Source and methodology';foot.appendChild(link);details.appendChild(foot);card.appendChild(details);
  }
 }catch(e){for(const card of cards){if(!codeByTitle[card.querySelector('h2')?.textContent])continue;const p=document.createElement('p');p.textContent='Week 11 team trends unavailable.';card.appendChild(p)}}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();})();
