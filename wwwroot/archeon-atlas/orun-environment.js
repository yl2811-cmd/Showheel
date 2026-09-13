/* Transactional pipeline: immutable baseline -> climate -> bounded evolution -> hydrology. */
(function(root,factory){const node=typeof module==='object'&&module.exports,api=factory(node?require('./orun-climate.js'):root.ORUN_CLIMATE,node?require('./orun-evolution.js'):root.ORUN_EVOLUTION);if(node)module.exports=api;else root.ORUN_ENVIRONMENT=api;})(typeof self!=='undefined'?self:globalThis,function(CL,E){
'use strict';
function prepare(state,p,progress=()=>{}){let next={...state,parameters:p};const original=state.baseLandforms||state.landforms||state,base=original.seed===state.seed?original:{...original,seed:state.seed};next.baseLandforms=base;if(!p.windwardMode){next.landforms=base;next.climate=null;return next;}if(!state.climate||state.climate.key!==CL.key(base,p))next.climate=CL.deriveClimate(next,p,progress);if(!state.landforms?.evolution||state.landforms.key!==E.key(base,p,next.climate))next.landforms=E.evolveWindwardTerrain(next,p,next.climate,progress);return next;}
function restore(base,manifest,fields){const evolution={...manifest.evolution,delta:fields.delta,sediment:fields.sediment,age:fields.age},h=Float32Array.from(base.h,(v,i)=>v+evolution.delta[i]),g={...base,h,baseKey:base.key,key:evolution.key,evolution};g.levels=E.rebuildLevels(g);return g;}
return{prepare,restore};
});
