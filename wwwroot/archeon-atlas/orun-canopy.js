/* Area samples are fixed in world space; LOD never creates another tree population. */
(function(root,factory){const node=typeof module==='object'&&module.exports,api=factory(node?require('./orun-core.js'):root.ORUN_CORE,node?require('./orun-hydrology.js'):root.ORUN_HYDROLOGY);if(node)module.exports=api;else root.ORUN_CANOPY=api;})(globalThis,function(C,H){
'use strict';
function create(state,p){const cache=new Map();function cell(x,z){const key=x+','+z;if(cache.has(key))return cache.get(key);const y=C.L.sampleGrid(state.landforms,state.landforms.h,x+32,z+32),e=H.sampleEcology(state,x+32,y,z+32,0,p),w=e.biomeWeights,r=w?.[2]||0,s=w?.[7]||0,coverage=w?r+s:e.weights?.[6]||0;const a={coverage,height:coverage?(w?(12*r+6*s)/coverage:9):0};cache.set(key,a);return a;}
return{sample(x,z,size){let area=0,wood=0,height=0;for(let zz=Math.floor(z/64)*64;zz<z+size;zz+=64)for(let xx=Math.floor(x/64)*64;xx<x+size;xx+=64){const a=Math.max(0,Math.min(xx+64,x+size)-Math.max(xx,x))*Math.max(0,Math.min(zz+64,z+size)-Math.max(zz,z)),c=cell(xx,zz);area+=a;wood+=a*c.coverage;height+=a*c.coverage*c.height;}return{coverage:wood/Math.max(1,area),height:height/Math.max(1e-9,wood)};}};
}
return{create};
});
