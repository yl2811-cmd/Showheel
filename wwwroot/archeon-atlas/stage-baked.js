/* Local stage images. First two atlas pages never mix legacy overlays into a bake. */
(() => {
 'use strict';
 const supported=new Set(['world','aethelgard']),selected={world:'height',aethelgard:'height'};
 let manifest=null,pending=null,active='world',busy=false;
 const detailOrigin='http://127.0.0.1:8912';
 const localPage=['localhost','127.0.0.1'].includes(location.hostname);
 let detailReady=false,detailTimer=0,detailSequence=0,detailKey='',detailNote='';
 const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
 const en=()=>window.ATLAS_I18N?.locale==='en';
 const host=document.createElement('section');host.id='stage-baked-controls';host.hidden=true;
 document.getElementById('geography-sidebar').prepend(host);
 const supports=id=>supported.has(id);
 function overview(id,row){const im=document.querySelector('#map-stage [data-baked-image]'),c=window.ATLAS_DATA.views.find(v=>v.id===id);if(!im||!c)return;for(const [k,v] of Object.entries({x:0,y:0,width:c.width,height:c.height,href:row.file,preserveAspectRatio:'xMidYMid meet'}))im.setAttribute(k,v);const svg=im.closest('svg'),label=row.name[en()?1:0]+' · '+caption(id);svg?.setAttribute('aria-label',label);const title=svg?.querySelector('title');if(title)title.textContent=label;detailKey='';detailSequence++;}
 function note(value){detailNote=value;const n=document.getElementById('stage-native-detail-note');if(n)n.textContent=value;}
 function maximumZoom(id){return detailReady?256:(id==='world'?16:12)}
 function zoomChanged(){clearTimeout(detailTimer);detailSequence++;detailKey='';detailTimer=setTimeout(detailView,650)}
 async function detailView(){
  const id=window.ATLAS_APP?.currentView;if(!localPage||!detailReady||!supports(id)||!['height','water'].includes(selected[id])||!manifest)return;
  const c=window.ATLAS_DATA.views.find(v=>v.id===id),stage=document.getElementById('map-stage'),t=window.ATLAS_APP.mapTransform();
  if(t.k<1.7){overview(id,layer(id));note('');return;}
  const fit=Math.min(stage.clientWidth/c.width,stage.clientHeight/c.height),padX=(stage.clientWidth-c.width*fit)/2,padY=(stage.clientHeight-c.height*fit)/2;
  const x0=Math.max(0,(-padX/fit-t.x)/t.k),y0=Math.max(0,(-padY/fit-t.y)/t.k),x1=Math.min(c.width,((stage.clientWidth-padX)/fit-t.x)/t.k),y1=Math.min(c.height,((stage.clientHeight-padY)/fit-t.y)/t.k);
  if(x1<=x0||y1<=y0)return;
  const width=x1-x0,height=y1-y0,size=Math.min(1400/(width*fit*t.k),1400/(height*fit*t.k),1),pixels=[Math.round(width*fit*t.k*size),Math.round(height*fit*t.k*size)];if(Math.min(...pixels)<128)return;
  const payload={view:id,layer:selected[id],rect:[x0,y0,width,height],pixels},key=JSON.stringify([manifest.terrainVersion,payload]);if(key===detailKey)return;
  detailKey=key;const token=detailSequence,currentLayer=selected[id];note(en()?'Loading detailed terrain…':'正在读取近景地形…');
  try{
   let r=await fetch(detailOrigin+'/api/detail',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw Error(d.error||'Detail unavailable');
   while(d.state!=='ready'){
    if(token!==detailSequence)return;await new Promise(resolve=>setTimeout(resolve,1500));
    r=await fetch(detailOrigin+'/api/jobs/'+d.id,{cache:'no-store'});d=await r.json();if(!r.ok)throw Error(d.error||'Detail failed');
   }
   if(token!==detailSequence||window.ATLAS_APP.currentView!==id||selected[id]!==currentLayer||d.terrainVersion!==manifest.terrainVersion)return;
   const url=detailOrigin+d.image;await new Promise((resolve,reject)=>{const check=new Image();check.onload=resolve;check.onerror=reject;check.src=url});if(token!==detailSequence)return;
   const im=document.querySelector('#map-stage [data-baked-image]');if(!im)return;
   for(const [k,v] of Object.entries({x:d.rect[0],y:d.rect[1],width:d.rect[2],height:d.rect[3],href:url,preserveAspectRatio:'none'}))im.setAttribute(k,v);
   note(d.detailStepM+' m · '+(d.nativePreview?(en()?'native detail preview':'原生细节预览'):(en()?'selected terrain':'当前选定地形')));
  }catch(error){if(token===detailSequence)note(en()?'Detailed view pending; keeping the labelled image.':'近景暂未就绪，保留已标注的图片。');}
 }
 async function read(force=false){
  if(manifest&&!force)return manifest;if(pending)return pending;
  pending=fetch('stage-baked/manifest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('阶段图片尚未同步');return r.json()}).then(d=>{
   if(d.schemaVersion!==1||!d.views?.world||!d.views?.aethelgard)throw Error('阶段图片清单不完整');
   for(const v of Object.values(d.views))for(const l of Object.values(v.layers))if(l.status==='ready'&&!/^stage-baked\/assets\/[a-f0-9]{64}\/(world|aethelgard)-[a-z]+\.png$/.test(l.file))throw Error('无效图片来源');
   manifest=d;return d;
  }).finally(()=>{pending=null});return pending;
 }
 function layer(id){const v=manifest.views[id];if(v.layers[selected[id]]?.status!=='ready')selected[id]='height';return v.layers[selected[id]]}
 function caption(id){const p=manifest.terrainPhase==='initial-condition'?(en()?'Initial terrain · erosion pending':'地形初态 · 侵蚀尚未完成'):(en()?'Selected terrain stage':'当前地形阶段');return p+' · '+manifest.terrainVersion}
 function sidebar(id){
  const enabled=supports(id);document.body.classList.toggle('stage-baked-mode',enabled);host.hidden=!enabled;if(!enabled||!manifest)return;
  const v=manifest.views[id],l=layer(id);host.replaceChildren();
  const heading=document.createElement('h2');heading.textContent=en()?'Layers':'图层';host.append(heading);
  const phase=document.createElement('p');phase.className='baked-phase';phase.textContent=caption(id);host.append(phase);
  for(const [key,row] of Object.entries(v.layers)){
   const label=document.createElement('label');label.className='baked-option';const radio=document.createElement('input');radio.type='radio';radio.name='baked-layer';radio.value=key;radio.checked=selected[id]===key;radio.disabled=row.status!=='ready';
   const text=document.createElement('span');text.textContent=row.name[en()?1:0];label.append(radio,text);
   if(row.status!=='ready'){const badge=document.createElement('b');badge.textContent='WIP';label.append(badge)}
   radio.onchange=()=>{selected[id]=key;overview(id,row);sidebar(id);zoomChanged()};host.append(label);
  }
  const note=document.createElement('p');note.className='baked-note';note.textContent=(en()?'One image at a time. Wheel to zoom; drag to pan.':'每次显示一张烘焙图。滚轮缩放，拖动查看。');host.append(note);
  if(selected[id]==='height'){const ramp=document.createElement('div');ramp.className='baked-ramp';host.append(ramp);const t=document.createElement('p');t.className='baked-note';t.textContent=en()?'0 — 8,000 m · Colours indicate elevation, not vegetation.':'0 — 8,000 米 · 颜色表示海拔，不表示植被。';host.append(t)}
  const notes={wind:['季节近似诊断风；正式三维风场仍为 WIP。','Approximate diagnostic wind; 3D wind remains WIP.'],rain:['年化降水，0–3000 mm / 地球年。','Annualized rain, 0–3000 mm / Earth year.'],water:['河宽由流量估计，河湖按像素覆盖面积混色；保留季节性湖面。','Discharge-estimated river widths and lake area coverage; colours blend by covered pixel area, including seasonal lakes.']};
  if(notes[selected[id]]){const t=document.createElement('p');t.className='baked-note';t.textContent=notes[selected[id]][en()?1:0];host.append(t)}
  if(l.note){const t=document.createElement('p');t.className='baked-note';t.textContent=l.note[en()?1:0];host.append(t)}
  const status=document.createElement('p');status.id='stage-baked-sync-note';status.className='baked-note';host.append(status);
  const detail=document.createElement('p');detail.id='stage-native-detail-note';detail.className='baked-note';detail.textContent=detailNote;host.append(detail);
  document.getElementById('view-status').textContent=(id==='world'?'Equal Earth':'Lambert')+' · '+l.name[en()?1:0]+' · R 4,750 km';
 }
 async function load(id){await read();active=id;sidebar(id);const l=layer(id),c=window.ATLAS_DATA.views.find(v=>v.id===id);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${c.width}" height="${c.height}" viewBox="0 0 ${c.width} ${c.height}" role="img" aria-label="${esc(l.name[en()?1:0]+' · '+caption(id))}"><title>${esc(caption(id))}</title><image data-baked-image="true" href="${esc(l.file)}" x="0" y="0" width="${c.width}" height="${c.height}" preserveAspectRatio="xMidYMid meet"/></svg>`;
 }
 async function refresh(){if(busy)return;busy=true;try{
  if(localPage){try{const response=await fetch(detailOrigin+'/api/status',{cache:'no-store'});if(response.ok){const status=await response.json();detailReady=status.ready===true;}}catch{detailReady=false;}}
  const previous=manifest?.revision||manifest?.sourceKey;await read(true);const id=window.ATLAS_APP?.currentView;
  if(previous&&previous!==(manifest.revision||manifest.sourceKey)&&supports(id)){const transform=window.ATLAS_APP.mapTransform();await window.ATLAS_APP.setView(id);window.ATLAS_APP.setMapTransform(transform.k,transform.x,transform.y)}
  const r=await fetch('stage-baked/sync-status.json',{cache:'no-store'});if(r.ok){const d=await r.json(),n=document.getElementById('stage-baked-sync-note');if(n)n.textContent=d.stale?(en()?'New stage pending. This image is the labelled previous stage.':'新阶段正在同步；当前图仍是上方标注的上一阶段。'):(en()?'Synced locally · ':'已同步到本地 · ')+new Date(manifest.builtUnix*1000).toLocaleString()}
 }catch(error){const n=document.getElementById('stage-baked-sync-note');if(n)n.textContent=en()?'Stage sync unavailable; showing the labelled saved image.':'阶段同步暂不可用；显示已标注的保存图片。'}finally{busy=false}}
 window.ATLAS_STAGE_BAKES={supports,load,zoomChanged,maximumZoom};
 addEventListener('atlas-view-ready',e=>{active=e.detail.id;sidebar(active);refresh()});
 addEventListener('atlas-language-changed',()=>sidebar(active));setInterval(refresh,15000);
})();
