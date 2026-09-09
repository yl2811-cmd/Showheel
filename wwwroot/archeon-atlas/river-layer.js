/* Offline, viewport-bounded river detail. Geographic widths stay in metres. */
(()=>{'use strict';
 const NS='http://www.w3.org/2000/svg',receivers=new Map(),cache=new Map();
 window.ATLAS_RIVER_RECEIVE=(key,markup)=>{cache.set(key,markup);receivers.get(key)?.(markup);};
 window.ATLAS_RIVERS={prepare(svg,view){
  const host=svg.querySelector('[data-river-view]');if(!host)return null;
  const meta=JSON.parse(host.dataset.riverManifest),active=new Map();let timer=0,dead=false,latest=null;
  function remove(key,e){receivers.delete(key);e.script?.remove();e.node?.remove();active.delete(key);}
  function refresh(){timer=0;if(dead||!latest)return;const {fit,transform:t,stage,config:c,enabled}=latest;
   if(!enabled){for(const [k,e] of active)remove(k,e);return;}
   const rect=stage.getBoundingClientRect(),px=(rect.width-c.width*fit)/2,py=(rect.height-c.height*fit)/2;
   const bounds=[(-px/fit-t.x)/t.k,(-py/fit-t.y)/t.k,((rect.width-px)/fit-t.x)/t.k,((rect.height-py)/fit-t.y)/t.k];
   const km=meta.kmPerMapUnit/(fit*t.k),visible=tier=>tier===0||km<=meta.tierMaxKmPerPixel[tier];
   const wanted=meta.tiles.filter(tile=>tile.tiers.some(visible)&&tile.bounds[0]<=bounds[2]&&tile.bounds[2]>=bounds[0]&&tile.bounds[1]<=bounds[3]&&tile.bounds[3]>=bounds[1]);
   const keys=new Set(wanted.map(t=>t.key));for(const [k,e] of active)if(!keys.has(k))remove(k,e);
   function show(e){if(e.node)for(const g of e.node.children)g.style.display=visible(Number(g.dataset.hydroTier))?'':'none';}
   for(const tile of wanted){const key=tile.key,full=view+':'+key;if(active.has(key)){show(active.get(key));continue;}
    const entry={node:null,script:null};active.set(key,entry);
    const receive=markup=>{if(dead||active.get(key)!==entry)return;const g=document.createElementNS(NS,'g');g.dataset.riverTile=key;g.innerHTML=markup;entry.node=g;host.appendChild(g);show(entry);};
    if(cache.has(full)){receive(cache.get(full));continue;}
    receivers.set(full,receive);const script=document.createElement('script');entry.script=script;script.src=tile.path;
    const finish=()=>{receivers.delete(full);script.remove();entry.script=null;};script.onload=finish;script.onerror=()=>{finish();active.delete(key);host.dataset.riverLoadError=key;};document.head.appendChild(script);
   }
   host.dataset.kmPerPixel=km.toFixed(4);host.dataset.activeRiverTiles=active.size;
  }
  return {update(state){latest=state;clearTimeout(timer);timer=setTimeout(refresh,90);},destroy(){dead=true;clearTimeout(timer);for(const [k,e] of active)remove(k,e);}};
 }};
})();
