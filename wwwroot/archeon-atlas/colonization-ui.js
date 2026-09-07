/* Research controls and author-view details. The accepted atlas data remain read-only. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const fmt = (v,n=1) => Number.isFinite(v) ? v.toLocaleString('en',{maximumFractionDigits:n}) : '未登记';
  const yearText=v=>Number(v).toLocaleString('en',{maximumFractionDigits:2,useGrouping:false});
  let hooks, result=null, computing=null, worker=null, playing=false, year=3094, active=false, lastFrame=0, lastPaint=0, frame=0;
  let lastMode='', canonicalLegend='', loadPromise=null;
  const defaultConfig={seed:240024,densityFactor:1,populationTrend:'declining',intentFactor:1,terraformFactor:1};
  const statusNames={deployment:'初始部署',deployed:'初始部署',construction:'基地成形中',relay:'轨道基地可用',terraforming:'地表改造中','atmosphere development':'地表改造中','open-surface':'开放地表',habitable:'开放地表','early residents':'先期住民',residents:'先期住民',handover:'CI交接中','CI withdrawing':'CI交接中',autonomous:'当地自治',isolated:'本地文明延续 · 外联中止',home:'太阳系',homeworld:'太阳系'};
  const kindNames={survey:'无人调查',seed:'蒲公英播种',history:'历史播种关系',service:'定期往返',crosslink:'世界之间的往返'};
  function setPlaying(value){playing=!!value&&active;lastFrame=performance.now();if($('colonization-play')){$('colonization-play').textContent=playing?'暂停演进':'播放演进';$('colonization-play').setAttribute('aria-pressed',String(playing));}}
  function config(){return {seed:Number($('colonization-seed').value),densityFactor:Number($('colonization-density').value),populationTrend:$('colonization-population').value,intentFactor:Number($('colonization-intent').value),terraformFactor:Number($('colonization-terraform').value)};}
  function setConfig(c){for(const[key,id]of Object.entries({seed:'seed',densityFactor:'density',populationTrend:'population',intentFactor:'intent',terraformFactor:'terraform'}))if(c[key]!==undefined)$('colonization-'+id).value=c[key];}
  function download(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function loadModel(){if(!loadPromise)loadPromise=(async()=>{if(!window.ATLAS_COLONIZATION)await hooks.loadScript('colonization-model.js');if(!window.ATLAS_COLONIZATION_INPUT)await hooks.loadScript('data/colonization-input.js');})().catch(e=>{loadPromise=null;throw e;});return loadPromise;}
  async function compute(options){
    if(computing)return computing;
    setPlaying(false);
    computing=(async()=>{
      const button=$('colonization-recompute'),message=$('colonization-compute-status');button.disabled=true;message.textContent='正在计算调查、播种与往返记录…';message.classList.remove('is-error');
      try{
        await loadModel();const chosen={...defaultConfig,...(options||config())};
        if(!Number.isSafeInteger(chosen.seed)||chosen.seed<0||chosen.seed>4294967295)throw Error('种子需为0至4294967295之间的整数。');
        const api=window.ATLAS_COLONIZATION,input=window.ATLAS_COLONIZATION_INPUT;
        let next;
        if(typeof Worker!=='undefined'&&api.createKernel){
          const source='const kernel=('+api.createKernel.toString()+')();self.onmessage=e=>{try{self.postMessage({result:kernel.simulate(e.data.input,e.data.config)})}catch(error){self.postMessage({error:error.message,stack:error.stack})}};';
          const url=URL.createObjectURL(new Blob([source],{type:'application/javascript'}));
          try{next=await new Promise((resolve,reject)=>{worker=new Worker(url);worker.onmessage=e=>e.data.error?reject(Error(e.data.error)):resolve(e.data.result);worker.onerror=e=>reject(Error(e.message||'研究模型计算中断'));worker.postMessage({input,config:chosen});});}
          finally{worker?.terminate();worker=null;URL.revokeObjectURL(url);}
        }else{await new Promise(r=>setTimeout(r,30));next=api.simulate(input,chosen);}
        result=next;setConfig(chosen);await hooks.replaceResult?.(result);message.textContent='计算完成 · 种子 '+chosen.seed+' · 参数已应用';return result;
      }catch(error){message.textContent='计算未完成：'+error.message;message.classList.add('is-error');throw error;}
      finally{button.disabled=false;computing=null;}
    })();return computing;
  }
  function detail(value){
    if(!value){$('detail').hidden=true;window.ATLAS_APP.selectedFeature=null;return;}
    const o=value,kind=o.kind||'project',sub=o.shipKind||o.routeKind||o.type||kind;
    const state=result?window.ATLAS_COLONIZATION.stateAt(result,year):null;
    const original=(state?.projects||[]).find(p=>p.id===o.id);
    const obj=original?{...original,...o}:o.kind==='ship'&&o.task?{...o.task,...o}:o;
    const lookup=id=>result?.projects.find(p=>p.id===id)?.name||result?.candidates.find(p=>p.id===id)?.name||id||'未登记';
    let html='<div class="kind">'+esc(kind==='star'?'真实恒星参照':kind==='ship'?'在途载具':kind==='route'?'星际航段':obj.anchor?'固定故事锚点':'模型假设')+'</div><h2>'+esc(obj.name||kindNames[sub]||obj.id)+'</h2>';
    if(obj.positionLy)html+='<div class="coords">距Earth '+fmt(Math.hypot(...obj.positionLy))+' ly · '+yearText(year)+'</div>';
    const rows=[];const row=(label,v)=>{if(v!==undefined&&v!==null)rows.push('<dt>'+esc(label)+'</dt><dd>'+esc(v)+'</dd>');};
    if(kind==='ship'||kind==='route'){
      row('用途',kindNames[sub]||sub);row('出发地',lookup(obj.fromId));row('目的地',lookup(obj.toId));row('三维航程',fmt(obj.distanceLy,2)+' ly');
      row('出发代际',Number.isFinite(obj.speedC)?obj.speedC+'c':undefined);row('出发',Number.isFinite(obj.departureYear)?yearText(obj.departureYear):undefined);row(obj.arrivalYear>year?'预计抵达':'抵达',Number.isFinite(obj.arrivalYear)?yearText(obj.arrivalYear):undefined);row(obj.returnYear>year?'预计返航完成':'返航完成',Number.isFinite(obj.returnYear)?yearText(obj.returnYear):undefined);
      row('此时位置',obj.phase?({outbound:'去程',return:'返程',returning:'返程',onsite:'现场',unloading:'卸载'}[obj.phase]||obj.phase):undefined);row('已执行船次',obj.tripCount);row('航线形成',Number.isFinite(obj.openedYear)?fmt(obj.openedYear,2):undefined);
      if(obj.taskIds?.length){const tasks=result.tasks.filter(t=>obj.taskIds.includes(t.id)&&t.departureYear<=year);const last=tasks[tasks.length-1];if(last){row('最近一次出发',fmt(last.departureYear,3));row('该载具代际',last.speedC+'c');row('该次抵达／返航',fmt(last.arrivalYear,3)+' / '+fmt(last.returnYear,3));}}
      if(Number.isFinite(obj.closedYear)&&year>=obj.closedYear)row('外联中止',fmt(obj.closedYear));
    }else if(kind==='star'){
      row('依据','HYG 4.1目录参照；不代表周围已有可改造行星');row('目录编号',obj.catalogId||obj.hip||obj.id);
    }else{
      row('此时状态',obj.id==='archeon'&&year>=2573?'本地文明延续 · 外联中止':statusNames[obj.status]||obj.status||obj.stage||'候选世界');
      row('来源基地',obj.sponsorNodeId?lookup(obj.sponsorNodeId):undefined);row('工程条件模板',obj.templateId?lookup(obj.templateId):undefined);row('选择依据',obj.selectionReason);
      if(kind==='candidate'){
        const a=result.projects.find(p=>p.id==='archeon');if(a&&obj.positionLy&&Math.hypot(...obj.positionLy.map((x,i)=>x-a.positionLy[i]))<330)row('立项约束','Archeon周边330光年为故事保留范围；调查不受此条件禁止。');
        row('候选口径','统计生成的工程候选，不是实际发现的行星。');
      }
      const labels={deploymentYear:'设备部署',relayReadyYear:'轨道基地可用',surfaceReadyYear:'开放地表',firstResidentsYear:'先期住民',phase3Year:'开始交接',handoverYear:'完成交接'};
      let upcoming=null;
      for(const[key,label]of Object.entries(labels)){const t=obj.milestones?.[key];if(Number.isFinite(t)){if(t<=year)row(label,yearText(t));else if(!upcoming)upcoming={label,t};}}
      if(!upcoming&&!obj.anchor)for(const[key,label]of Object.entries(labels)){const t=obj.forecastMilestones?.[key];if(Number.isFinite(t)&&t>year){upcoming={label,t};break;}}
      if(upcoming&&!obj.anchor&&obj.milestones?.deploymentYear<=year)row('下一工程目标（预计）',upcoming.label+' · '+yearText(upcoming.t));
      if(Number.isFinite(obj.seedReadyYear)&&obj.seedReadyYear<=year&&!(obj.id==='archeon'&&year>=2573))row('再次播种能力','自 '+fmt(obj.seedReadyYear,2)+' 年具备');
      const seedTask=result.tasks.find(t=>t.kind==='seed'&&t.toId===obj.id&&t.departureYear<=year);if(seedTask){row('实际播种航程',fmt(seedTask.distanceLy,2)+' ly');row('播种载具代际',seedTask.speedC+'c');}
      if(obj.id==='archeon'&&year>=3094)row('本地人口','约2,000,000人');else if(obj.population!==null&&obj.population!==undefined)row('已登记人口',typeof obj.population==='number'?'约 '+fmt(obj.population,0):obj.population);
      const e=obj.engineering;if(e){row('净保留氧',Number.isFinite(e.oxygenRetainedKg)?e.oxygenRetainedKg.toExponential(3)+' kg':undefined);row('制氧相关功率额度',Number.isFinite(e.allocatedMeanPowerTW)?fmt(e.allocatedMeanPowerTW,0)+' TW':undefined);}
    }
    html+='<dl>'+rows.join('')+'</dl><p class="source">殖民推演 · 上帝视角。调查、工程与社会意愿采用所选假设；不构成真实行星预测。</p><div class="detail-actions"><button class="jump" id="colonization-focus">聚焦此处</button>';
    if(obj.id==='archeon')html+='<button class="jump" id="colonization-surface">查看3094地表 ↗</button>';
    html+='</div>';$('detail-body').innerHTML=html;$('detail').hidden=false;window.ATLAS_APP.selectedFeature=obj.id;
    $('colonization-focus').onclick=()=>hooks.focus(obj.id);if($('colonization-surface'))$('colonization-surface').onclick=()=>hooks.openSurface();
  }
  function update({mode,tab,epoch,state}){
    if(!hooks)return;
    active=tab==='federation'&&mode==='research';year=epoch;
    $('colonization-mode').hidden=tab!=='federation';$('colonization-controls').hidden=!active;
    document.body.classList.toggle('colonization-mode',active);
    if(!active)setPlaying(false);
    for(const b of document.querySelectorAll('[data-federation-mode]'))b.setAttribute('aria-pressed',String(b.dataset.federationMode===mode));
    if(lastMode!==String(active)){
      $('space-legend').innerHTML=active?'<span><i class="cr-key cr-world"></i>项目阶段</span><span><i class="cr-key cr-survey"></i>调查</span><span><i class="cr-key cr-seed"></i>播种</span><span><i class="cr-key cr-history"></i>历史来源</span><span><i class="cr-key cr-service"></i>定期往返</span>':canonicalLegend;
      document.querySelector('[data-epoch="3094"] span').textContent=active?'文明截面':'Earth 首光';lastMode=String(active);
    }
    if(!active)return;
    $('colonization-year').value=year;$('colonization-year-value').textContent=yearText(year);$('colonization-play').disabled=!!computing;
    $('space-heading').textContent='殖民推演';$('space-eyebrow').textContent='THE DANDELION VOYAGES';
    $('space-intro').textContent='沿着出发、抵达与再次播种，观察少数世界怎样连成更远的航路。';
    $('epoch-caption').textContent=year<=2564?'2400—2564：固定历史回放。':'2564之后：候选、基地能力与定居意愿共同决定新项目。';
    document.querySelector('.epoch').textContent=yearText(year)+' · Federation';
    $('space-source').textContent='上帝视角 · HYG恒星参照 / 独立统计候选。当前目录不是完整普查；候选与项目不受600光年边界限制。';
    for(const id of ['nebulae','remnant','light-shell','bounds'])document.querySelector('[data-space-layer="'+id+'"]').closest('label').hidden=true;
    $('nebula-shortcuts').hidden=true;
    const s=state?.stats||{};
    const stats=[['已部署项目',s.projectCount],['开放地表',s.openSurfaceCount],['在途载具',s.activeShipCount],['距Earth最远',Number.isFinite(s.extentLy)?fmt(s.extentLy)+' ly':'—']];
    $('colonization-stats').innerHTML=stats.map(([label,v])=>'<div><span>'+label+'</span><strong>'+esc(v??'—')+'</strong></div>').join('');
    $('colonization-physical').textContent=Number.isFinite(s.physicalFraction)?'物理常住比例 '+fmt(s.physicalFraction*100,2)+'% · 意愿余量 '+fmt(s.demandCredit,2):'统计待载入';
  }
  function init(nextHooks){
    hooks=nextHooks;canonicalLegend=$('space-legend').innerHTML;
    const modes=document.createElement('section');modes.id='colonization-mode';modes.hidden=true;modes.innerHTML='<div class="colonization-mode-buttons"><button data-federation-mode="canon" aria-pressed="true">既有设定</button><button data-federation-mode="research" aria-pressed="false">殖民推演</button></div>';$('epoch-controls').before(modes);
    const panel=document.createElement('section');panel.id='colonization-controls';panel.hidden=true;panel.innerHTML=`
      <label class="colonization-year-label" for="colonization-year">年份 <output id="colonization-year-value">3094</output></label>
      <input id="colonization-year" type="range" min="2400" max="3094" step="0.01" value="3094" aria-label="殖民演进年份">
      <div class="colonization-play-row"><button id="colonization-play" aria-pressed="false">播放演进</button><select id="colonization-play-speed" aria-label="播放速度"><option value="1">1年 / 秒</option><option value="5" selected>5年 / 秒</option><option value="20">20年 / 秒</option></select></div>
      <div id="colonization-stats" class="colonization-stats"></div><p id="colonization-physical" class="space-caption"></p>
      <details class="colonization-settings"><summary>模型假设与比较</summary>
      <label>候选密度<select id="colonization-density"><option value="0.25">四分之一</option><option value="1" selected>基准 · 10⁻⁷ / ly³</option><option value="4">四倍</option></select></label>
      <label>物理常住比例<select id="colonization-population"><option value="declining">20%逐渐降至1%</option><option value="slower">下降较慢</option><option value="constant">保持20%</option></select></label>
      <label>立项意愿<select id="colonization-intent"><option value="0.5">基准的一半</option><option value="1" selected>基准</option><option value="2">基准的两倍</option></select></label>
      <label>工程工期<select id="colonization-terraform"><option value="0.7">0.7倍</option><option value="1" selected>模板原工期</option><option value="1.3">1.3倍</option></select></label>
      <label>固定种子<input id="colonization-seed" type="number" min="0" max="4294967295" step="1" value="240024"></label>
      <p class="space-caption">候选是统计假设。Archeon周边330光年不新增改造项目，是保留的故事条件。</p>
      <button id="colonization-recompute">按这些假设重新计算</button><p id="colonization-compute-status" role="status" class="space-caption"></p>
      <button id="colonization-export">导出参数与事件 JSON ↓</button><a href="space-assets/COLONIZATION.md" target="_blank">模型规则与十种种子比较 ↗</a>
      </details>
      <details class="colonization-layers"><summary>航线与载具</summary>
      <label><input data-colonization-layer="candidates" type="checkbox">统计候选</label>
      <label><input data-colonization-layer="survey" type="checkbox" checked>无人调查</label>
      <label><input data-colonization-layer="seed" type="checkbox" checked>正在播种</label>
      <label><input data-colonization-layer="history" type="checkbox" checked>历史播种关系</label>
      <label><input data-colonization-layer="service" type="checkbox" checked>定期往返</label>
      <label><input data-colonization-layer="crosslink" type="checkbox" checked>世界之间的接续</label>
      <label><input data-colonization-layer="bounds" type="checkbox" checked>距离参考圈</label></details>`;
    $('epoch-controls').after(panel);
    for(const b of modes.querySelectorAll('button'))b.onclick=async()=>{try{b.disabled=true;await hooks.setMode(b.dataset.federationMode);}catch(e){$('load-status').textContent=e.message;}finally{b.disabled=false;}};
    $('colonization-year').oninput=e=>{setPlaying(false);hooks.setYear(Number(e.target.value));};
    $('colonization-play').onclick=()=>{if(!playing&&year>=3094)hooks.setYear(2400);setPlaying(!playing);};
    $('colonization-recompute').onclick=()=>compute().catch(()=>{});
    $('colonization-export').onclick=()=>{if(result)download(result,'federation-research-'+result.config.seed+'.json');};
    for(const box of panel.querySelectorAll('[data-colonization-layer]'))box.onchange=()=>hooks.setLayer(box.dataset.colonizationLayer,box.checked);
    document.addEventListener('visibilitychange',()=>{if(document.hidden)setPlaying(false);});
    const tick=now=>{frame=requestAnimationFrame(tick);if(!playing){lastFrame=now;return;}const dt=Math.min(.1,(now-lastFrame)/1000);lastFrame=now;year=Math.min(3094,year+dt*Number($('colonization-play-speed').value));if(now-lastPaint>50||year===3094){lastPaint=now;hooks.setYear(year);}if(year===3094)setPlaying(false);};frame=requestAnimationFrame(tick);
  }
  window.ATLAS_COLONIZATION_UI={init,update,detail,compute,ensureResult:()=>result?Promise.resolve(result):compute(defaultConfig),getResult:()=>result,setPlaying,get playing(){return playing;}};
})();
