/* Screen-sized labels and symbols; geographic coordinates stay unchanged. */
(() => {
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 function prepare(svg,byId,id){const circles=[],rects=[],texts=[],paths=[],project=window.ATLAS_LIVING.projection(window.ATLAS_DATA.views.find(v=>v.id===id));
  for(const el of svg.querySelectorAll('[data-feature],[data-label]')){const f=byId.get(el.dataset.feature||el.dataset.label);if(!f)continue;const p=f.properties;
   if(p.kind==='settlement'){
    for(const c of (el.tagName.toLowerCase()==='circle'?[el]:el.querySelectorAll('circle')))circles.push({c,id:f.id,small:!!p.modelCommunity,hit:c.getAttribute('fill')==='transparent'});
    for(const r of el.querySelectorAll('rect'))rects.push({r,x:+r.getAttribute('x')+(+r.getAttribute('width'))/2,y:+r.getAttribute('y')+(+r.getAttribute('height'))/2});
   }
   for(const t of el.querySelectorAll('text')){const parentId=el.dataset.feature||el.dataset.label;if(texts.some(x=>x.t===t))continue;texts.push({t,x:+t.getAttribute('x'),y:+t.getAttribute('y'),anchor:f.geometry.type==='Point'?project(f.geometry.coordinates):null,base:+(t.dataset.baseSize||t.getAttribute('font-size')||12),settlement:p.kind==='settlement',id:parentId});}
   if(p.kind==='route')for(const r of (el.tagName.toLowerCase()==='path'?[el]:el.querySelectorAll('path'))){paths.push({r,small:!!p.localBranch,hit:r.getAttribute('stroke')==='transparent'});const prev=r.previousElementSibling;if(prev?.tagName.toLowerCase()==='path'&&prev.getAttribute('d')===r.getAttribute('d')&&!prev.hasAttribute('data-feature'))paths.push({r:prev,casing:true});}
  }
  return {pick(x,y){let chosen=null,best=Infinity;const seen=new Set(),limit=matchMedia('(pointer:coarse)').matches?16:8;for(const {c,id,hit}of circles){if(hit||seen.has(id)||getComputedStyle(c).visibility==='hidden'||!c.getClientRects().length)continue;seen.add(id);const b=c.getBoundingClientRect(),d=Math.hypot(x-b.left-b.width/2,y-b.top-b.height/2);if(d<=limit&&d<best){chosen=id;best=d}}return chosen;},update(fit,k){if(!fit)return;const z=Math.log2(Math.max(k,1));for(const {c,small,hit}of circles){c.setAttribute('r',(hit?(matchMedia('(pointer:coarse)').matches?16:8):small?clamp(1.7-z*.125,1.2,1.7):clamp(4-z*.375,2.5,4))/fit);c.setAttribute('stroke-width',(small?.5:1.1)/fit)}for(const {r,x,y}of rects){r.setAttribute('x',x-6/fit);r.setAttribute('y',y-6/fit);r.setAttribute('width',12/fit);r.setAttribute('height',12/fit);r.setAttribute('stroke-width',1/fit)}for(const {t,x,y,anchor,base,settlement}of texts){t.style.fontSize=(settlement?clamp(14-z*.75,11,14):clamp(base,11,17))/fit+'px';t.style.strokeWidth=1.6/fit+'px';t.setAttribute('x',settlement&&anchor?anchor[0]+6/fit:x);t.setAttribute('y',settlement&&anchor?anchor[1]-5/fit:y)}for(const {r,small,hit,casing}of paths){r.setAttribute('vector-effect','non-scaling-stroke');r.style.strokeWidth=(hit?12:casing?2.8:small?.55:1.2)+'px'}}};
 }
 window.ATLAS_SETTLEMENT_DISPLAY={prepare};
})();
