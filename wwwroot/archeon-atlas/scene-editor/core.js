/* Shared scene document rules. Metres, Y up; quaternions are [x,y,z,w]. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ArcheonSceneCore=api;})(globalThis,()=>{'use strict';
 const clone=x=>JSON.parse(JSON.stringify(x));
 function key(a){const id=String(a.id||'');return id&&!/^(life-asset-|assembly-\d|garden-\d|repair-life-\d)/.test(id)?id.replace(/-(lod[012]|near|far)$/,''):JSON.stringify([a.owner||'',a.surfaceId||'',a.prototype.replace(/-(lod[012]|near|far)$/,''),a.position.map(n=>Math.round(n*10000)/10000),a.rotation||0]);}
 function empty(catalog,layout){return{format:'archeon-scene',version:1,revision:0,baseBuild:catalog.baseBuild,catalogHash:catalog.hash,layout:layout||null,edits:{},additions:{},groups:clone(catalog.groups),knownGroups:Object.keys(catalog.groups),savedAt:null};}
 function upgrade(doc,catalog){doc=clone(doc);const known=new Set(doc.knownGroups||[...Object.keys(doc.groups||{}),...(catalog.legacyGroupIds||[])]),members=new Set(Object.values(doc.groups||{}).flatMap(g=>g.members));for(const [id,g]of Object.entries(catalog.groups)){if(!known.has(id)&&!g.members.some(n=>members.has(n)))doc.groups[id]=clone(g);known.add(id);}doc.knownGroups=[...known];return doc;}
 function pose(t){return t&&['position','quaternion','scale'].every(k=>Array.isArray(t[k])&&t[k].length===(k==='quaternion'?4:3)&&t[k].every(Number.isFinite))&&t.position.every(x=>Math.abs(x)<100000)&&t.scale.every(x=>x>=.01&&x<=100)&&Math.abs(Math.hypot(...t.quaternion)-1)<.001;}
 function validate(doc,catalog){
  if(!doc||doc.format!=='archeon-scene'||doc.version!==1||!Number.isInteger(doc.revision)||doc.revision<0)throw Error('场景文件格式不匹配');
  const assets=new Map(catalog.assets.map(a=>[a.id,a])),entities=new Map(catalog.entities.map(e=>[e.id,e]));
  for(const field of ['edits','additions','groups'])if(!doc[field]||Array.isArray(doc[field])||typeof doc[field]!=='object')throw Error('场景缺少 '+field);
  if(Object.keys(doc.additions).length>5000||Object.keys(doc.groups).length>15000)throw Error('本次场景对象过多');
  const conflicts=[];
  const validBox=b=>Array.isArray(b)&&b.length===6&&b.every(Number.isFinite)&&b.slice(0,3).every((n,i)=>b[i+3]>n&&b[i+3]-n<=10);
  const validCuts=e=>{if(e.cuts&&(!Array.isArray(e.cuts)||e.cuts.length>256||e.cuts.some(b=>!validBox(b))))throw Error('方块编辑记录无效');if(e.cutBox&&!validBox(e.cutBox))throw Error('方块范围无效');};
  for(const [id,e]of Object.entries(doc.edits)){validCuts(e);const base=entities.get(id);if(!base)conflicts.push({id,reason:'基础对象已不存在'});else if(e.assetVersion!==assets.get(base.assetId)?.version)conflicts.push({id,reason:'基础模型版本发生变化'});if(e.transform&&!pose(e.transform))throw Error('物件变换数值无效：'+id);if(e.name!=null&&(typeof e.name!=='string'||e.name.length>100))throw Error('物件名称过长');}
  for(const [id,e]of Object.entries(doc.additions)){validCuts(e);if(!id.startsWith('user-')||entities.has(id))throw Error('新增物件编号无效');if(!assets.has(e.assetId))conflicts.push({id,reason:'资产库中缺少此模型'});else if(e.assetVersion!==assets.get(e.assetId).version)conflicts.push({id,reason:'新增物件的模型版本发生变化'});if(!pose(e.transform))throw Error('新增物件变换数值无效');if(e.name!=null&&(typeof e.name!=='string'||e.name.length>100))throw Error('物件名称过长');if(e.cutBox&&typeof e.cutFrom!=='string')throw Error('方块缺少来源物件');}
  const members=new Set();for(const g of Object.values(doc.groups)){if(!g||typeof g.name!=='string'||g.name.length>100||!Array.isArray(g.members))throw Error('组合格式无效');for(const id of g.members){if(members.has(id))throw Error('一个物件不能同时属于两个组合');members.add(id);if(!entities.has(id)&&!doc.additions[id])conflicts.push({id,reason:'组合成员已不存在'});}}
  if(doc.layout){if(!doc.layout.global||Object.values(doc.layout.global).some(v=>!Number.isFinite(v)||v<0||v>1))throw Error('屋群参数无效');for(const p of Object.values(doc.layout.units||{}))if(Object.values(p).some(v=>!Number.isFinite(v)||v<0||v>1))throw Error('局部屋群参数无效');}
  return conflicts;
 }
 function resolve(doc,catalog){const conflicts=validate(doc,catalog),bad=new Set(conflicts.map(c=>c.id));return{conflicts,objects:[...catalog.entities.map(e=>({...e,...(!bad.has(e.id)?doc.edits[e.id]:{})})),...Object.entries(doc.additions).filter(([id])=>!bad.has(id)).map(([id,e])=>({id,...e}))]};}
 return{clone,key,empty,upgrade,pose,validate,resolve};
});
