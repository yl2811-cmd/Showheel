/* Navigation between the accepted geographic atlas and the independent astronomy renderer. */
(() => {
 'use strict';
 const app=window.ATLAS_APP,$=id=>document.getElementById(id),isSpace=()=>activeTab==='system'||activeTab==='federation';
 const localIds=['atheria','marneth','rimstone'];
 const original={search:$('search').oninput,zoomIn:$('zoom-in').onclick,zoomOut:$('zoom-out').onclick,reset:$('reset').onclick,scenic:$('scenic').onclick};
 let activeTab='world',localView='atheria',instance=null,epoch=3094,playing=false,loadToken=0,loaded=null,scenicSnapshot=null,engineType='base',savedFederationState=null,exposure=0,brightness=1;
 let federationMode='canon',researchResult=null;
 const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const sourceLabels={catalog:'真实恒星目录',canon:'正文明确',inferred:'制图推定',derived:'依正文数值推导',model:'制图推定','map-inference':'制图推定'};
 const statusLabels={'homeworld':'太阳系 · 出发之地','collapsed; light in transit':'源区已坍缩；爆发之光仍在途中','remnant':'Sky Fire 遗迹','Axiom destination':'Axiom 的目的地 · 先期居民已抵达','surface unconfirmed':'地表现况未确认 · 旧航线中断','terraform project':'地表与大气改造进行中','CI active':'CI 仍在运作','autonomous':'CI 已退出 · 当地自治','CI withdrawing':'CI 正在逐步退出','atmosphere development':'大气改造阶段','slow maturation':'漫长的地表准备阶段','early residents':'先期住民已抵达','not deployed':'此时尚未部署'};
 function syncInterface(){
  const cosmic=isSpace(),planetary=cosmic&&app.spaceState?.domain==='planetary',systemNode=planetary?window.ATLAS_ASTRONOMY?.nodes.find(n=>n.id===app.spaceState.systemId):null;document.body.classList.toggle('space-mode',cosmic);$('map-stage').hidden=cosmic;$('space-stage').hidden=!cosmic;
  $('living-controls').hidden=activeTab!=='system';$('geography-sidebar').hidden=cosmic;$('astronomy-sidebar').hidden=!cosmic;$('space-back').hidden=!cosmic;$('space-breadcrumbs').hidden=!cosmic;$('space-instructions').hidden=!cosmic;$('local-tabs').hidden=activeTab!=='local';
  document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===activeTab)));
  document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===localView)));
  document.querySelector('.search-label').textContent=cosmic?'寻找一颗星':'寻找一个地方';$('search').placeholder=cosmic?'星名、殖民世界或 HIP 编号…':'地名、河流或航线…';
  document.querySelector('.epoch').innerHTML=cosmic?(activeTab==='system'?'Year 521 <span>·</span> 3094':epoch+' <span>·</span> Federation'):'Year 521 <span>·</span> 3094';
  $('epoch-controls').hidden=activeTab!=='federation';$('system-controls').hidden=activeTab!=='system';$('terraform-controls').hidden=!planetary;$('space-legend').hidden=activeTab!=='federation'||planetary;
  $('space-eyebrow').textContent=planetary?'A FEDERATION WORLD':activeTab==='system'?'ONE STAR · TWO MOONS':'THE NEAR STARS';$('space-heading').textContent=planetary?(systemNode?.name||'Terraform World'):activeTab==='system'?'Archeon System':'Federation';
  $('space-intro').textContent=activeTab==='system'?'一颗温暖的 K2V 恒星，海洋覆盖的 Archeon，与一快一慢的两个月亮。':(epoch===2564?'首轮八个世界与530光年处的Archeon；轨道基地先于开放地表成形。':'八个首轮世界与十六个后续项目仍在往来；Archeon的旧线末端尚未接续。');
  if(planetary)$('space-intro').textContent=systemNode?.terraformPlanet?.description||'在这个恒星系内观察宿主与行星。表面外观属于制图推定。';
  document.querySelectorAll('[data-scene-only]').forEach(n=>n.hidden=n.dataset.sceneOnly==='system'?!(activeTab==='system'||planetary):activeTab!=='federation'||planetary);
  document.querySelector('[data-space-layer="remnant"]').closest('label').hidden=planetary;
  $('nebula-shortcuts').hidden=activeTab!=='federation'||planetary;const nebulae=window.ATLAS_ASTRONOMY?.nebulae||[],nebulaSignature=nebulae.map(n=>n.id).join(',');if($('nebula-links').dataset.signature!==nebulaSignature){$('nebula-links').dataset.signature=nebulaSignature;$('nebula-links').replaceChildren();for(const n of nebulae){const b=document.createElement('button');b.textContent=n.name+' ↗';b.onclick=()=>{instance?.focusObject(n.id);showObject(n);};$('nebula-links').append(b);}}
  document.querySelectorAll('[data-epoch]').forEach(b=>b.setAttribute('aria-pressed',Number(b.dataset.epoch)===epoch?'true':'false'));
  $('epoch-caption').textContent=epoch===2564?'Axiom 出发时的殖民网络。参宿四已在源区坍缩，地球当时尚不知情。':'地球首光重新聚拢关注。坍缩早已得到确认；Archeon 的地表近况仍未确认。';
  const scenic=cosmic?!!scenicSnapshot:app.isScenic();$('scenic').textContent=scenic?'恢复图层':'观景';$('scenic').setAttribute('aria-pressed',String(scenic));
  app.currentTab=activeTab;app.localView=localView;app.epoch=epoch;
  const source=$('space-source');source.innerHTML='J2000 恒星参照 · HYG 4.1<br>600 光年是显示范围，不代表领土边界，也不是完整恒星普查。';
  app.federationMode=federationMode;
  window.ATLAS_COLONIZATION_UI?.update({mode:federationMode,tab:activeTab,epoch,state:app.spaceState});
 }
 function restoreSpaceScenic(){if(!scenicSnapshot)return;for(const [layer,value]of scenicSnapshot){const input=document.querySelector('[data-space-layer="'+layer+'"]');if(input)input.checked=value;instance?.setLayer(layer,value);}scenicSnapshot=null;}
 function onGeography(id){
  ++loadToken;restoreSpaceScenic();instance?.dispose();instance=null;engineType='base';playing=false;$('space-stage').replaceChildren();
  activeTab=localIds.includes(id)?'local':id;if(activeTab==='local')localView=id;
  $('search').value='';$('search-results').replaceChildren();$('space-breadcrumbs').replaceChildren();delete $('space-breadcrumbs').dataset.signature;$('detail').hidden=true;
  app.spaceState=null;syncInterface();
 }
 window.ATLAS_NAV={onGeography};
 function loadScript(src){return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;script.onload=resolve;script.onerror=()=>{script.remove();reject(Error('无法读取本地文件：'+src));};document.head.append(script);});}
 async function loadSpace(){
  if(loaded)return loaded;
  loaded=(async()=>{
   if(!window.ATLAS_ASTRONOMY)await loadScript('data/astronomy.js');
   if(!window.ATLAS_STARS)await loadScript('data/stars-hyg41.js');
   if(!window.ATLAS_SPACE_TEXTURES)await loadScript('data/space-textures.js');
   if(!window.THREE_SPACE)await loadScript('vendor/three-space.bundle.js');
   if(!window.ATLAS_SPACE)await loadScript('space-view.js');
  })().catch(error=>{loaded=null;throw error;});
  return loaded;
 }
 function updateState(state){
  if(!isSpace())return;
  const oldState=app.spaceState;app.spaceState=state;
  if(state.domain==='colonization')window.ATLAS_COLONIZATION_UI?.update({mode:federationMode,tab:activeTab,epoch,state});
  if(['system','federation'].includes(state.scene)&&state.scene!==activeTab){activeTab=state.scene;syncInterface();const expectedEpoch=activeTab==='system'?3094:epoch;if(instance&&state.epoch!==expectedEpoch){instance.setEpoch(expectedEpoch);return;}}
  if(oldState?.domain!==state.domain||oldState?.systemId!==state.systemId)syncInterface();app.currentView=activeTab;app.ready=state.ready!==false;app.loadingView=app.ready?null:activeTab;
  $('space-stage').setAttribute('aria-busy',String(!app.ready));$('view-status').textContent=state.scaleLabel?'距焦点 · '+state.scaleLabel:(activeTab==='system'?'Archeon · AU / km':'Sol · 0–600 ly');$('zoom-status').textContent=state.focusName||state.focusId||'';
  $('load-status').textContent=app.ready?'':'展开星空…';
  document.querySelectorAll('[data-focus]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.focus===state.focusId)));
  const crumbs=Array.isArray(state.breadcrumbs)?state.breadcrumbs:[];
  const signature=JSON.stringify(crumbs);if($('space-breadcrumbs').dataset.signature!==signature){
   $('space-breadcrumbs').dataset.signature=signature;$('space-breadcrumbs').replaceChildren();
   if(!crumbs.length){const b=document.createElement('button');b.textContent=activeTab==='system'?'Archeon System':'Federation · 600 ly';b.onclick=()=>instance?.reset();$('space-breadcrumbs').append(b);}
   for(const item of crumbs){const b=document.createElement('button');b.textContent=typeof item==='string'?item:(item.label||item.name||item.id);b.onclick=()=>{if(item.scene==='federation'&&engineType==='terraform')returnToFederation();else if(item.scene)setTab(item.scene);else if(item.id)instance?.focusObject(item.id);else instance?.back();};$('space-breadcrumbs').append(b);}
  }
 }
 async function setTab(id){
  if(['world','aethelgard'].includes(id))return app.setView(id);
  if(id==='local')return app.setView(localView);
  if(!['system','federation'].includes(id))return;
  const desiredEngine=id==='federation'&&federationMode==='research'?'research':'base';
  const token=++loadToken;restoreSpaceScenic();if(instance&&engineType!==desiredEngine){instance.dispose();instance=null;app.spaceState=null;}engineType=desiredEngine;app.suspend();activeTab=id;playing=false;
  $('search').value='';$('search-results').replaceChildren();$('detail').hidden=true;syncInterface();app.currentView=id;app.ready=false;app.loadingView=id;$('space-stage').setAttribute('aria-busy','true');$('load-status').textContent='展开星空…';
  if(!instance)$('space-stage').innerHTML='<div class="space-loading">正在展开星空…</div>';
  try{
   await loadSpace();if(token!==loadToken)return;
   if(desiredEngine==='research'){
    if(!researchResult)researchResult=await window.ATLAS_COLONIZATION_UI.ensureResult();
    if(!window.ATLAS_COLONIZATION_STARS)await loadScript('data/colonization-stars.js');
    if(!window.ATLAS_COLONIZATION_VIEW)await loadScript('colonization-view.js');
    if(token!==loadToken)return;
   }
   if(!instance){
    $('space-stage').replaceChildren();let candidate=null;
    const engine=desiredEngine==='research'?window.ATLAS_COLONIZATION_VIEW:window.ATLAS_SPACE;
    candidate=await engine.create({container:$('space-stage'),result:researchResult,epoch,onState:s=>{if(token===loadToken||candidate&&instance===candidate)updateState(s);},onSelect:(o,meta)=>{if(token===loadToken||candidate&&instance===candidate){if(meta?.reason==='time'&&$('detail').hidden)return;showObject(o);}},onNavigate:destination=>{if(token!==loadToken&&instance!==candidate)return;if(destination==='surface')app.setView('world');else if(destination==='system'||destination==='federation')setTab(destination);else if(destination?.type==='colony-system')enterColonySystem(destination.id);}});
    if(token!==loadToken){candidate?.dispose();return;}instance=candidate;
   }
   if(token!==loadToken)return;
   instance.setEpoch(id==='system'?3094:epoch);instance.setScene(id);instance.setPlaying(false);$('space-play').textContent='播放轨道';$('space-play').setAttribute('aria-pressed','false');
   document.querySelectorAll('[data-space-layer]').forEach(i=>instance.setLayer(i.dataset.spaceLayer,i.checked));
   if(desiredEngine==='research')document.querySelectorAll('[data-colonization-layer]').forEach(i=>instance.setLayer(i.dataset.colonizationLayer,i.checked));
   instance.setExposure?.(exposure);instance.setBrightness?.(brightness);instance.resize();updateState(instance.getState());window.dispatchEvent(new CustomEvent('atlas-view-ready',{detail:{id}}));
  }catch(error){
   if(token!==loadToken)return;instance?.dispose();instance=null;app.ready=false;app.loadingView=null;app.spaceError=error.message;$('load-status').textContent='三维视图未能展开';$('space-stage').setAttribute('aria-busy','false');
   const nodes=window.ATLAS_ASTRONOMY?.nodes||[];
   $('space-stage').innerHTML='<div class="space-error"><p>当前环境未能建立三维视图。</p><p>'+escape(error.message)+'</p><button id="retry-space">重新展开</button>'+(nodes.length?'<ul>'+nodes.map(n=>'<li>'+escape(n.name)+' · '+Number(n.distanceLy||0).toFixed(1)+' ly</li>').join('')+'</ul>':'')+'<p>地表地图与本地数据仍可浏览。</p></div>';
   $('retry-space').onclick=()=>setTab(activeTab);
  }
 }
 async function enterColonySystem(id){
  if(engineType==='research')return;
  const node=window.ATLAS_ASTRONOMY?.nodes.find(n=>n.id===id);if(id==='archeon'){await setTab('system');instance?.focusObject('archeon');return;}if(!node?.terraformPlanet||node.epochs?.[String(epoch)]?.visible===false)return;
  const token=++loadToken;if(instance&&engineType==='base'&&activeTab==='federation')savedFederationState=instance.getState();
  restoreSpaceScenic();instance?.dispose();instance=null;engineType='terraform';activeTab='federation';app.spaceState=null;app.ready=false;app.loadingView='federation';$('detail').hidden=true;$('space-stage').replaceChildren();$('space-stage').innerHTML='<div class="space-loading">正在靠近 '+escape(node.name)+'…</div>';syncInterface();
  try{
   if(!window.ATLAS_TERRAFORM)await loadScript('terraform-view.js');if(token!==loadToken)return;$('space-stage').replaceChildren();let candidate=null;
   candidate=await window.ATLAS_TERRAFORM.create({container:$('space-stage'),node,epoch,onState:s=>{if(token===loadToken||candidate&&instance===candidate)updateState(s);},onSelect:o=>{if(token===loadToken||candidate&&instance===candidate)showObject(o);},onNavigate:destination=>{if(token!==loadToken&&candidate!==instance)return;if(destination==='federation')returnToFederation();else if(destination==='system')setTab('system');}});
   if(token!==loadToken){candidate?.dispose();return;}instance=candidate;instance.setExposure?.(exposure);instance.setBrightness?.(brightness);document.querySelectorAll('[data-space-layer]').forEach(i=>instance.setLayer(i.dataset.spaceLayer,i.checked));instance.resize();updateState(instance.getState());
  }catch(error){if(token!==loadToken)return;app.loadingView=null;$('load-status').textContent='恒星系未能展开';$('space-stage').innerHTML='<div class="space-error">'+escape(error.message)+'<p><button id="terraform-retry-return">返回星图</button></p></div>';$('terraform-retry-return').onclick=()=>returnToFederation();}
 }
 async function returnToFederation(){const saved=savedFederationState;await setTab('federation');if(instance&&saved){if(instance.restoreState)instance.restoreState(saved);else instance.focusObject(saved.focusId||'sol');}}
 function resolveObject(object){if(typeof object==='string'){const data=window.ATLAS_ASTRONOMY,body=data?.systemBodies.find(n=>n.id===object),node=data?.nodes.find(n=>n.id===object)||data?.nebulae?.find(n=>n.id===object);if(object.startsWith('planet:')){const n=data?.nodes.find(n=>n.id===object.slice(7));if(n)return {...n.terraformPlanet,id:object,name:n.name,systemId:n.id,epochs:n.epochs,kind:'planet'};}if(object.startsWith('host:')){const n=data?.nodes.find(n=>n.id===object.slice(5));if(n)return {...n.hostStar,id:object,name:n.hostStar.name||n.name+' 主星',radiusKm:n.hostStar.radiusSolar*695700,kind:'star'};}return activeTab==='system'?(body||node):(node||body);}return object;}
 function showObject(value){if(engineType==='research'&&activeTab==='federation'){window.ATLAS_COLONIZATION_UI.detail(value);return;}if(value?.geometry){app.showFeature(value.id);return;}
  const object=resolveObject(value);if(!object||!isSpace())return;
  const node=window.ATLAS_ASTRONOMY?.nodes.find(n=>n.id===object.id),body=window.ATLAS_ASTRONOMY?.systemBodies.find(n=>n.id===object.id),o=activeTab==='system'&&body?{...body}:{...(node||body),...object};
  const closeView=activeTab==='system'||app.spaceState?.domain==='planetary',currentEpoch=activeTab==='system'?3094:epoch,info=o.epochs?.[String(currentEpoch)]||{};
  const kind=o.kind==='nebula'?'NEARBY NEBULA':closeView?(o.kind==='star'||o.id==='archeon-star'?'HOST STAR':o.parent==='archeon'?'NATURAL SATELLITE':'PLANET'):(o.kind==='colony'?'FEDERATION · COLONY':o.kind==='project'?'FEDERATION · PROJECT':'STELLAR REFERENCE');
  let html='<div class="kind">'+escape(kind)+'</div><h2>'+escape(o.name||o.id)+'</h2>';
  if(activeTab==='federation'&&Number.isFinite(o.distanceLy))html+='<div class="coords">距太阳 '+o.distanceLy.toLocaleString('en',{maximumFractionDigits:2})+' ly</div>';
  if(closeView&&o.radiusKm)html+='<div class="coords">直径 '+(o.radiusKm*2).toLocaleString('en',{maximumFractionDigits:0})+' km</div>';
  if(info.status)html+='<p>'+escape(statusLabels[info.status]||info.status)+'</p>';if(info.description||o.description)html+='<p>'+escape(info.description||o.description)+'</p>';
  html+='<dl>';
  if(o.kind==='nebula'){html+='<dt>可见形态</dt><dd>'+escape({reflection:'反射星云 · 散射附近恒星光',dark:'暗星云 · 尘埃遮暗背景星',mixed:'反射光与暗尘带交织'}[o.nebulaType]||o.nebulaType)+'</dd><dt>距离与形态依据</dt><dd>'+escape(o.distanceNote||'距离为观测工作值；三维厚度和细部密度为制图推定。')+'</dd>';}
  if(o.hostStar)html+='<dt>宿主恒星</dt><dd>'+escape(o.hostStar.spectralType)+' · '+escape(o.hostStar.massSolar)+' M☉<br>宿主参数为制图推定</dd>';
   const projectNode=window.ATLAS_ASTRONOMY?.nodes.find(n=>n.id===(o.systemId||o.hostNodeId||o.id));
   if(projectNode?.milestones){const m=projectNode.milestones,source=window.ATLAS_ASTRONOMY.nodes.find(n=>n.id===projectNode.sponsorNodeId);if(source)html+='<dt>接续出发地</dt><dd>'+escape(source.name)+'</dd>';for(const [key,title]of [['deploymentYear','设备部署'],['relayReadyYear','中继开始接船'],['surfaceReadyYear','开放地表'],['firstResidentsYear','先期住民抵达'],['phase3Year','开始交接'],['handoverYear','完成交接']]){const year=m[key];if(year&&year<=currentEpoch)html+='<dt>'+title+'</dt><dd>约 '+year+'</dd>'; }if(projectNode.id==='archeon'&&currentEpoch===3094)html+='<dt>旧端点状态</dt><dd>以上为灾前已知记录；当前地表适居与人口状态未确认。</dd>';if(projectNode.deploymentLeg)html+='<dt>接续航段</dt><dd>'+projectNode.deploymentLeg.distanceLy.toFixed(1)+' ly</dd>';}
  if(currentEpoch===3094&&projectNode&&window.ATLAS_ASTRONOMY.federation?.cruiseSpeedC3094){html+='<dt>此时曲速</dt><dd>约500c；以下航时另加停靠与任务时间</dd>';if(projectNode.id==='archeon')html+='<dt>从Earth往返</dt><dd>约2.12年纯航行，单程约1.06年</dd><dt>从中程02往返</dt><dd>约1.32年纯航行，单程约0.66年</dd>';}
   if(projectNode?.surveyHistory&&currentEpoch===3094)html+='<dt>向旧线前方继续勘测</dt><dd>'+escape(projectNode.surveyHistory.result)+'</dd>';
   if(info.phase)html+='<dt>此时的发展阶段</dt><dd>'+escape(info.phase)+'</dd>';
  if(info.population!==undefined&&info.population!==null)html+='<dt>人口</dt><dd>'+escape(typeof info.population==='number'?'约 '+info.population.toLocaleString():info.population)+'</dd>';
  if(info.knowledge)html+='<dt>当时获知的情况</dt><dd>'+escape(info.knowledge)+'</dd>';
  if(closeView&&o.semiMajorKm){const au=o.semiMajorKm/window.ATLAS_ASTRONOMY.constants.auKm;html+='<dt>轨道半长轴</dt><dd>'+escape(au>.05?au.toFixed(3)+' AU':Math.round(o.semiMajorKm).toLocaleString()+' km')+'</dd>';}
  if(closeView&&o.periodEarthDays){html+='<dt>公转周期</dt><dd>'+o.periodEarthDays.toLocaleString('en',{maximumFractionDigits:4})+' 地球日';if(o.parent==='archeon')html+=' · '+(o.periodEarthDays*24/27).toFixed(1)+' 本地日';html+='</dd>';}
  if(o.id==='archeon'&&activeTab==='system')html+='<dt>太阳日与轴倾角</dt><dd>27 地球小时 · 13°</dd><dt>恒星系朝向</dt><dd>轨道平面较旧图旋转60°；行星轴倾角仍为13°。</dd>';
  if(o.id==='betelgeuse')html+='<dt>空间与传播</dt><dd>小说距离 531 ly；源区坍缩 2563，Earth 首光 3094。实体遗迹约 2 ly，与向外传播的光壳分别显示。</dd><dt>此图的时间口径</dt><dd>显示源区的共时制图形态，不是 Earth 当时眼中的样子。3094 的地球刚收到爆发首光；Archeon 看见的是约十年前的源区。</dd>';
  if(o.firstLightYear&&activeTab==='federation'&&o.id!=='betelgeuse')html+='<dt>此地收到参宿四首光</dt><dd>约 '+Math.round(o.firstLightYear)+'</dd>';
  html+='<dt>位置与参数依据</dt><dd>'+escape(sourceLabels[o.sourceCategory]||o.sourceCategory||'真实恒星目录')+'</dd></dl>';
  if(o.id==='archeon'&&(activeTab==='system'||epoch===3094))html+='<p>作者视角 · Year 521 约2,000,000人；Federation所持地表近况仍未确认。</p>';if(o.id==='archeon')html+='<p class="source">当地 Year 521 的世界与 Federation 当时掌握的资料分开呈现；不表示已经重新建立联系。</p>';
  if(o.kind==='nebula')html+='<p class="source">三维外形、光深和散射亮度为可视化模型；并非精确尘埃断层成像。冷暗云不按红外伪彩渲染成自发光气体。</p>';
  html+='<div class="detail-actions"><button class="jump" id="space-detail-focus">靠近观察</button>';
  if(o.id==='archeon'&&activeTab==='federation')html+='<button class="jump" id="space-enter-system">进入恒星系 ↗</button>';
  if(o.terraformPlanet&&activeTab==='federation'&&!closeView)html+='<button class="jump" id="space-enter-colony">进入恒星系 ↗</button>';
  if(o.id==='archeon'&&activeTab==='system')html+='<button class="jump" id="space-surface">打开地表地图 ↗</button>';
  html+='</div>';$('detail-body').innerHTML=html;$('detail').hidden=false;app.selectedFeature=o.id;
  $('space-detail-focus').onclick=()=>{instance?.focusObject(o.id);$('detail').hidden=true;};
  if($('space-enter-system'))$('space-enter-system').onclick=async()=>{await setTab('system');instance?.focusObject('archeon');$('detail').hidden=true;};
  if($('space-enter-colony'))$('space-enter-colony').onclick=()=>enterColonySystem(o.id);
  if($('space-surface'))$('space-surface').onclick=()=>app.setView('world');
 }
 function setEpoch(year){
  year=Number(year);const research=activeTab==='federation'&&federationMode==='research';
  if(!Number.isFinite(year)||(research?(year<2400||year>3094):![2564,3094].includes(year)))return;
  epoch=year;
  if(research){syncInterface();instance?.setEpoch(year);if(!$('detail').hidden&&app.selectedFeature){const selected=instance?.resolveObject?.(app.selectedFeature);if(selected)showObject(selected);else{$('detail').hidden=true;app.selectedFeature=null;}}$('search-results').replaceChildren();return;}
  const data=window.ATLAS_ASTRONOMY,current=data?.nodes.find(n=>n.id===app.spaceState?.systemId);
  if(engineType==='terraform'&&current?.epochs?.[String(epoch)]?.visible===false){savedFederationState=null;$('detail').hidden=true;return setTab('federation');}
  syncInterface();instance?.setEpoch(activeTab==='system'?3094:epoch);const selected=resolveObject(app.selectedFeature||'');
  if(selected?.epochs?.[String(epoch)]?.visible===false){$('detail').hidden=true;app.selectedFeature=null;}else if(!$('detail').hidden&&app.selectedFeature)showObject(app.selectedFeature);$('search-results').replaceChildren();
 }
 async function setFederationMode(mode){
  if(!['canon','research'].includes(mode))return;
  window.ATLAS_COLONIZATION_UI.setPlaying(false);
  if(mode==='research'&&!researchResult)researchResult=await window.ATLAS_COLONIZATION_UI.ensureResult();
  federationMode=mode;
  if(mode==='canon'&&![2564,3094].includes(epoch))epoch=Math.abs(epoch-2564)<Math.abs(epoch-3094)?2564:3094;
  await setTab('federation');
  const params=new URLSearchParams(location.hash.slice(1));params.set('view','federation');params.set('mode',mode);params.set('epoch',String(epoch));history.replaceState(null,'','#'+params.toString());
 }
 async function replaceResearchResult(result){
  researchResult=result;
  if(engineType==='research'&&instance){$('detail').hidden=true;app.selectedFeature=null;instance.setResult(result);instance.setEpoch(epoch);updateState(instance.getState());}
 }
 async function focusSettlement(id,view='globe'){if(view==='map'){await app.setTab('world');return app.selectFeature(id);}await setTab('system');instance?.focusSurface?.(id);return app.showFeature(id);}
 function focusObject(id){if(id.startsWith('planet:')&&engineType!=='terraform')return enterColonySystem(id.slice(7));if(instance){instance.focusObject(id);$('detail').hidden=true;return;}return setTab('system').then(()=>instance?.focusObject(id));}
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
 document.querySelectorAll('[data-focus]').forEach(b=>b.onclick=()=>focusObject(b.dataset.focus));
 document.querySelectorAll('[data-epoch]').forEach(b=>b.onclick=()=>setEpoch(b.dataset.epoch));
 document.querySelectorAll('[data-space-layer]').forEach(i=>i.onchange=()=>instance?.setLayer(i.dataset.spaceLayer,i.checked));
 $('zoom-in').onclick=event=>isSpace()?instance?.zoomBy(1.6):original.zoomIn(event);$('zoom-out').onclick=event=>isSpace()?instance?.zoomBy(1/1.6):original.zoomOut(event);
 $('reset').onclick=event=>{if(isSpace()){instance?.reset();$('detail').hidden=true;}else original.reset(event);};$('space-back').onclick=()=>{instance?.back();$('detail').hidden=true;};
 $('scenic').onclick=event=>{if(!isSpace())return original.scenic(event);const controls=[...document.querySelectorAll('[data-space-layer]')].filter(i=>['labels','orbits','routes','bounds','light-shell','surface-life','inhabited','harbors','assistance'].includes(i.dataset.spaceLayer));if(scenicSnapshot){for(const [layer,value]of scenicSnapshot){const input=controls.find(i=>i.dataset.spaceLayer===layer);input.checked=value;instance?.setLayer(layer,value);}scenicSnapshot=null;}else{scenicSnapshot=controls.map(i=>[i.dataset.spaceLayer,i.checked]);for(const input of controls){input.checked=false;instance?.setLayer(input.dataset.spaceLayer,false);}}syncInterface();};
 $('search').oninput=event=>{if(!isSpace())return original.search(event);const query=event.target.value.trim(),results=$('search-results');results.replaceChildren();if(!query||!instance)return;const localMatches=activeTab==='system'?[...window.ATLAS_LIVING.byId.values()].filter(f=>!f.properties.unnamed&&f.geometry.type==='Point'&&(window.ATLAS_I18N?.searchText(f)||f.properties.name.toLowerCase()).includes(query.toLowerCase())).map(f=>({id:f.id,name:f.properties.name,surface:true})):[];const matches=[...localMatches,...instance.search(query)].slice(0,12);if(!matches.length){results.textContent='没有找到这个名字';return;}for(const result of matches){const b=document.createElement('button');b.textContent=result.name||result.id;b.onclick=()=>{if(result.surface){focusSettlement(result.id);results.replaceChildren();return;}instance.focusObject(result.id);showObject(result);results.replaceChildren();};results.append(b);}};
 $('space-layers-toggle').onclick=()=>{const hidden=!$('space-layers').hidden;$('space-layers').hidden=hidden;$('space-layers-toggle').setAttribute('aria-expanded',String(!hidden));$('space-layers-toggle').querySelector('span').textContent=hidden?'+':'−';};
 $('space-play').onclick=()=>{playing=!playing;instance?.setPlaying(playing);$('space-play').textContent=playing?'暂停轨道':'播放轨道';$('space-play').setAttribute('aria-pressed',String(playing));};
 $('terraform-host').onclick=()=>instance?.focusObject('host:'+app.spaceState?.systemId);$('terraform-planet').onclick=()=>instance?.focusObject('planet:'+app.spaceState?.systemId);$('terraform-return').onclick=()=>returnToFederation();
 $('remnant-focus').onclick=()=>{setEpoch(3094);instance?.focusObject('betelgeuse');$('detail').hidden=true;};
 function setExposure(value){exposure=Math.max(-3,Math.min(3,Number(value)));$('space-exposure').value=exposure;$('exposure-value').textContent=(exposure>0?'+':'')+exposure.toFixed(2)+' EV';instance?.setExposure?.(exposure);}
 function setBrightness(value){brightness=Math.max(.5,Math.min(2,Math.round(Number(value)*10)/10));$('space-brightness').value=brightness;$('brightness-value').textContent=Math.round(brightness*100)+'%';instance?.setBrightness?.(brightness);}
 $('space-exposure').oninput=event=>setExposure(event.target.value);$('space-brightness').oninput=event=>setBrightness(event.target.value);
 $('exposure-down').onclick=()=>setExposure(exposure-.25);$('exposure-up').onclick=()=>setExposure(exposure+.25);$('brightness-down').onclick=()=>setBrightness(brightness-.1);$('brightness-up').onclick=()=>setBrightness(brightness+.1);$('light-reset').onclick=()=>{setExposure(0);setBrightness(1);};
 $('space-capture').onclick=async()=>{if(!instance)return;try{const result=await instance.capturePng(),a=document.createElement('a');a.href=typeof result==='string'?result:URL.createObjectURL(result);a.download='archeon-'+activeTab+'-'+(activeTab==='system'?3094:epoch)+'.png';a.click();if(typeof result!=='string')setTimeout(()=>URL.revokeObjectURL(a.href),1000);}catch(error){$('load-status').textContent='保存失败：'+error.message;}};
 document.querySelectorAll('[data-living-focus]').forEach(b=>b.onclick=()=>focusSettlement(b.dataset.livingFocus));
 Object.assign(app,{focusSettlement,setTab,setEpoch,focusObject,setExposure,setBrightness,enterColonySystem,returnToFederation,setFederationMode,getColonizationResult:()=>researchResult,getSpaceState:()=>instance?.getState()||null,spaceSearch:q=>instance?.search(q)||[],currentTab:activeTab,epoch,localView});
 window.ATLAS_COLONIZATION_UI.init({setMode:setFederationMode,setYear:setEpoch,replaceResult:replaceResearchResult,loadScript,focus:id=>instance?.focusObject(id),openSurface:()=>app.setView('world'),setLayer:(id,value)=>instance?.setLayer(id,value)});
 new ResizeObserver(()=>instance?.resize()).observe($('space-stage'));
 window.addEventListener('atlas-view-ready',event=>{if(!['system','federation'].includes(event.detail?.id)){activeTab=localIds.includes(event.detail.id)?'local':event.detail.id;syncInterface();}});
 if(matchMedia('(max-width:620px)').matches)$('space-layers-toggle').click();
 syncInterface();
 const query=new URLSearchParams(location.hash.slice(1));const initial=query.get('view');if(['system','federation','world','aethelgard','local'].includes(initial)){
  const open=initial==='federation'&&query.get('mode')==='research'?setFederationMode('research'):setTab(initial);
  open.then(()=>{const year=Number(query.get('epoch'));if(year)setEpoch(year);if(query.get('focus'))instance?.focusObject(query.get('focus'));}).catch(error=>{$('load-status').textContent=error.message;});
 }
})();
