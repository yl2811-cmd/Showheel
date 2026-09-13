/* Existing mapped rivers carry their tributaries through the local scene, rather than ending at a handoff. */
(function(root,factory){const node=typeof module==='object'&&module.exports,api=factory(node?require('./orun-core.js'):root.ORUN_CORE,node?require('./orun-drainage.js'):root.ORUN_DRAINAGE);if(node)module.exports=api;else root.ORUN_COLLECTORS=api;})(typeof self!=='undefined'?self:globalThis,function(C,D){
'use strict';
function install(state,ctx){const {g,handoffs,wetDistance,support,width,waterHeight,segments}=ctx,{h,n,step,min}=g,lines=(state.environment?.waterLines||[]).slice().sort((a,b)=>b.points[0][1]-a.points[0][1]),carry=new Map(),pointKey=p=>Math.round(p[0]/16)+','+Math.round(p[2]/16);let count=0,maximumBackwater=0;
 for(const line of lines){const path=[];for(let i=1;i<line.points.length;i++){const a=line.points[i-1],b=line.points[i],steps=Math.max(1,Math.ceil(Math.hypot(b[0]-a[0],b[2]-a[2])/step));for(let j=0;j<steps;j++){const t=j/steps,x=C.mix(a[0],b[0],t),z=C.mix(a[2],b[2],t);if(Math.hypot(x,z)>C.RADIUS+step)continue;path.push([x,C.L.sampleGrid(g,h,x,z)+1.2,z]);}}const last=line.points.at(-1);if(Math.hypot(last[0],last[2])<=C.RADIUS+step)path.push([last[0],C.L.sampleGrid(g,h,last[0],last[2])+1.2,last[2]]);if(path.length<2)continue;
  const original=path.map(p=>p[1]);for(let i=path.length-2;i>=0;i--)path[i][1]=Math.max(path[i][1],path[i+1][1]);for(let i=0;i<path.length;i++)maximumBackwater=Math.max(maximumBackwater,path[i][1]-original[i]);
  const added=new Float64Array(path.length),inputs=handoffs.get(line.id)?.inlets||[];for(const inlet of inputs){let best=0,distance=Infinity;for(let i=0;i<path.length;i++){const p=path[i],d=(p[0]-inlet.x)**2+(p[2]-inlet.z)**2;if(d<distance){distance=d;best=i;}}added[best]+=inlet.dischargeM3s;}
  let q=carry.get(pointKey(line.points[0]))||0;const widths=[],discharges=[];for(let i=0;i<path.length;i++){q+=added[i];discharges.push(q);const w=Math.min(line.widths?.[0]||line.width||240,3+15*Math.sqrt(q));widths.push(w);if(q<=.001)continue;const k=D.index(g,path[i][0],path[i][2]);wetDistance[k]=0;support[k]=C.clamp(q/.10);width[k]=w;waterHeight[k]=path[i][1];}
  if(q<=.001)continue;carry.set(pointKey(line.points.at(-1)),(carry.get(pointKey(line.points.at(-1)))||0)+q);segments.push({id:'orun-v7-collector-'+line.id,atlasId:line.id,kind:'collector',from:'collector-'+line.id,to:'collector-end-'+line.id,path,width:Math.max(...widths),widths,discharges,bankfullWidthM:line.width||Math.max(...(line.widths||[240]))});count++;
 }
 if(maximumBackwater>16)throw Error('区域主河与最终地形不一致，所需回水超过16米');return{count,maximumBackwaterM:maximumBackwater};
}
return{install};
});
