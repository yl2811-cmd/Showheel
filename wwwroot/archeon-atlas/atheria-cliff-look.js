/* One immutable colour input, one shared live albedo parameter. */
(()=>{'use strict';
 const clamp=v=>Number.isFinite(Number(v))?Math.max(0,Math.min(100,Math.round(Number(v)))):0;
 async function create({T,manifest,assetBase,signal}){
  if(!manifest.cliffLook)throw Error('缺少崖壁调色配置');
  const bytes=async file=>{if(window.SHOWHEEL_ASSETS)return window.SHOWHEEL_ASSETS.bytes(assetBase+file,signal);const r=await fetch(assetBase+file,{signal});if(!r.ok)throw Error('崖壁参数未能读取：'+file);return r.arrayBuffer();};
  const [json,data]=await Promise.all([bytes(manifest.cliffLook.file),bytes(manifest.cliffLook.masks.file)]),config=JSON.parse(new TextDecoder().decode(json));
  if(config.version!==1||config.curveRevision!=='warm-rock-1'||config.scope!=='regional-cliffs-only'||Object.keys(config.records).some(id=>!/^t\d+-[0-3]\.bin$/.test(id)))throw Error('崖壁遮罩需要随当前模型更新');
  const ranges=new DataView(data),uniform={value:clamp(config.defaultValue)/100},storageKey='archeon.atheria.cliff-whiteness',key=config.baselineRevision;
  try{const saved=JSON.parse(localStorage.getItem(storageKey));if(saved?.baselineRevision===key&&Number.isFinite(saved.value))uniform.value=clamp(saved.value)/100;else localStorage.removeItem(storageKey);}catch{}
  function state(){return{value:Math.round(uniform.value*100),defaultValue:clamp(config.defaultValue),baselineRevision:key,curveRevision:config.curveRevision,tone:config.tone,scope:config.scope};}
  function set(value){uniform.value=clamp(value)/100;try{localStorage.setItem(storageKey,JSON.stringify({baselineRevision:key,value:Math.round(uniform.value*100)}));}catch{}return state();}
  function attach(g,id,sourceSha){const record=config.records[id];if(!record)return;
   if(record.vertices!==g.getAttribute('position').count||sourceSha&&sourceSha!==record.sourceSha256)throw Error('崖壁遮罩与模型不一致：'+id);
   const mask=new Uint8Array(record.vertices);for(let i=0;i<record.rangeCount;i++){const p=record.offset+i*8,start=ranges.getUint32(p,true),count=ranges.getUint32(p+4,true);if(start+count>mask.length)throw Error('崖壁遮罩范围无效');mask.fill(255,start,start+count);}
   g.setAttribute('cliffMask',new T.BufferAttribute(mask,1,true));g.userData.cliffMaskId=id;
  }
  function material(mat){
   const original=mat.onBeforeCompile,cacheKey=mat.customProgramCacheKey.bind(mat);mat.defaultAttributeValues={...mat.defaultAttributeValues,cliffMask:[0]};
   mat.onBeforeCompile=function(shader,...args){original?.call(this,shader,...args);shader.uniforms.cliffWhiteness=uniform;
    shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nattribute float cliffMask;varying float vCliffMask;').replace('#include <begin_vertex>','#include <begin_vertex>\nvCliffMask=cliffMask;');
    const c=config.curve,f=n=>Number(n).toFixed(8);
    shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
uniform float cliffWhiteness;varying float vCliffMask;
vec3 cliffAlbedo(vec3 original){
 float t=cliffWhiteness;
 float l=dot(original,vec3(.2126,.7152,.0722));
 vec3 stone=mix(original,l*vec3(${c.warmth.map(f).join(',')}),${f(c.neutralMix)}*t);
 stone=max(vec3(0.),(stone-vec3(${f(c.pivot)}))*(1.+${f(c.contrast-1)}*t)+vec3(${f(c.pivot)}));
 stone*=1.+${f(c.gain-1)}*t;
 float shoulder=${f(c.shoulder)},span=${f(c.ceiling-c.shoulder)};
 vec3 protected=vec3(shoulder)+span*(vec3(1.)-exp(-max(vec3(0.),stone-vec3(shoulder))/span));
 return mix(stone,protected,step(vec3(shoulder),stone));
}`).replace('#include <color_fragment>','#include <color_fragment>\nif(cliffWhiteness>0.0&&vCliffMask>0.0)diffuseColor.rgb=mix(diffuseColor.rgb,cliffAlbedo(diffuseColor.rgb),vCliffMask);');
   };mat.customProgramCacheKey=()=>cacheKey()+'-cliff-white-1';
  }
  return{attach,material,set,state,config};
 }
 window.ATHERIA_CLIFF_LOOK={create};
})();
