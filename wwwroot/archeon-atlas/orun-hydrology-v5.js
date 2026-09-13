/* Final-surface water and ecology. This module never changes terrain or legacy geometry inputs. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./orun-core.js'):root.ORUN_CORE);if(typeof module==='object'&&module.exports)module.exports=api;else root.ORUN_HYDROLOGY_V5=api;})(typeof self!=='undefined'?self:globalThis,function(C){
'use strict';
const VERSION='final-water-v1',ECOLOGY='riparian-v2',S=C.smooth,clamp=C.clamp,OFF=[[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];
// Priority-flood supplies spill elevations, not new ground heights. Flat water routes use flood order.
function spillSurface(g){const{n,h}=g,N=h.length,level=Float32Array.from(h),parent=new Int32Array(N).fill(-1),rank=new Int32Array(N),seen=new Uint8Array(N),heap=[];let sequence=0;
 const less=(a,b)=>level[a]<level[b]||level[a]===level[b]&&a<b;
 const push=k=>{let i=heap.length;heap.push(k);while(i){const p=(i-1)>>1;if(!less(k,heap[p]))break;heap[i]=heap[p];i=p;}heap[i]=k;};
 const pop=()=>{const out=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let c=i*2+1;if(c+1<heap.length&&less(heap[c+1],heap[c]))c++;if(!less(heap[c],last))break;heap[i]=heap[c];i=c;}heap[i]=last;}return out;};
 for(let k=0;k<N;k++)if(k<n||k>=N-n||k%n===0||k%n===n-1){seen[k]=1;push(k);}
 // Retain deep regional closed basins. The imported high rim must not flood the entire lower plain.
 const radius=Math.max(1,Math.round(2048/g.step)),horizontal=new Float32Array(N),regional=new Float32Array(N);
 for(const axis of[0,1])for(let line=0;line<n;line++){const src=axis?horizontal:h,dst=axis?regional:horizontal,deque=new Int32Array(n);let head=0,tail=0,next=0;const at=i=>axis?i*n+line:line*n+i;for(let i=0;i<n;i++){const end=Math.min(n-1,i+radius);while(next<=end){while(tail>head&&src[at(deque[tail-1])]>=src[at(next)])tail--;deque[tail++]=next++;}while(deque[head]<i-radius)head++;dst[at(i)]=src[at(deque[head])];}}
 for(let k=0;k<N;k++)if(!seen[k]&&h[k]<=regional[k]+1e-5){seen[k]=1;push(k);}
 while(heap.length){const k=pop();rank[k]=sequence++;const x=k%n,z=Math.floor(k/n);for(const[dx,dz]of OFF){if(dx&&dz)continue;const xx=x+dx,zz=z+dz;if(xx<0||xx>=n||zz<0||zz>=n)continue;const q=zz*n+xx;if(seen[q])continue;seen[q]=1;level[q]=Math.max(h[q],level[k]);parent[q]=k;push(q);}}
 return{level,parent,rank};
}
function heightKey(g){let hash=2166136261;const words=new Uint32Array(g.h.buffer,g.h.byteOffset,g.h.length);for(let i=0;i<words.length;i++)hash=Math.imul(hash^words[i],16777619);return hash>>>0;}
function key(state,p=state.parameters){const g=state.landforms||state;return [VERSION,g.key||'',heightKey(g),state.seed,g.n,g.step,p?.recharge,p?.waterfallDensity].join(':');}
function deriveHydrology(state,progress=()=>{}){
 const g=state.landforms||state,{n,h,step,min}=g,N=h.length,flow=new Float64Array(N).fill(step*step),receiver=new Int32Array(N).fill(-1),order=Uint32Array.from({length:N},(_,i)=>i),slope=new Float32Array(N),seasonal=new Float32Array(N),wetDistance=new Float32Array(N).fill(1e9),seasonDistance=new Float32Array(N).fill(1e9),sourceStrength=new Float32Array(N),waterWidth=new Float32Array(N),waterHeight=new Float32Array(N).fill(-1e9);
 progress('正在沿最终地表连接泉水、沟谷和河流…');const spill=spillSurface(g),routing=spill.level;order.sort((a,b)=>routing[b]-routing[a]||spill.rank[b]-spill.rank[a]);
 const neighbors=(k,fn)=>{const x=k%n,z=Math.floor(k/n);let sum=0,best=0,r=-1;const qs=[],ws=[];for(const[dx,dz]of OFF){if(x+dx<0||x+dx>=n||z+dz<0||z+dz>=n)continue;const q=k+dz*n+dx,drop=routing[k]-routing[q];if(drop<0||drop===0&&spill.rank[q]>=spill.rank[k])continue;if(dx&&dz){const cross=routing[k+dx]+routing[k+dz*n];if(cross-2*routing[k]>1e-5||2*routing[q]-cross>1e-5)continue;}const s=Math.max(1e-7,drop/(step*Math.hypot(dx,dz))),w=s**1.1;qs.push(q);ws.push(w);sum+=w;if(s>best){best=s;r=q;}}if(!qs.length&&spill.parent[k]>=0){qs.push(spill.parent[k]);ws.push(1);sum=1;r=spill.parent[k];}receiver[k]=r;slope[k]=Math.max(0,...qs.map(q=>(h[k]-h[q])/(step*Math.hypot(q%n-x,Math.floor(q/n)-z))));for(let i=0;i<qs.length;i++)fn(qs[i],ws[i]/sum);};
 for(const k of order)neighbors(k,(q,w)=>flow[q]+=flow[k]*w);const rawReceiver=new Int32Array(N).fill(-1);for(let k=0;k<N;k++){const x=k%n,z=Math.floor(k/n);let best=0;for(const[dx,dz]of OFF){if(x+dx<0||x+dx>=n||z+dz<0||z+dz>=n)continue;const q=k+dz*n+dx,drop=h[k]-h[q];if(drop<=0)continue;if(dx&&dz){const cross=h[k+dx]+h[k+dz*n];if(cross>2*h[k]||cross<2*h[q])continue;}const slope=drop/Math.hypot(dx,dz);if(slope>best){best=slope;rawReceiver[k]=q;}}}
 for(let k=0;k<N;k++)if(flow[k]>=1e6&&routing[k]-h[k]<24&&(slope[k]>.00001||routing[k]-h[k]>.01)){seasonal[k]=S(1e6,6e6,flow[k])*.8+.2;seasonDistance[k]=0;}
 const routes=[],sources=[];
 for(const f of state.falls||[])sources.push({id:f.id,x:f.x,z:f.z,width:f.width,discharge:f.dischargeM3s||.3,kind:'spring'});
 const candidates=[],target=Math.round((state.falls?.length||23)*(state.parameters?.waterfallDensity||2.6));
 for(let j=2;j<n-2;j+=6)for(let i=2;i<n-2;i+=6){const k=j*n+i,x=min+i*step,z=min+j*step;if(Math.hypot(x,z)>42000||h[k]<650||h[k]>3050||slope[k]<.18||slope[k]>4||g.lock?.[k]>.8)continue;const score=slope[k]*(1+Math.log1p(flow[k]/(step*step))*.35);candidates.push({k,x,z,score});}
 candidates.sort((a,b)=>b.score-a.score);for(const c of candidates){if(sources.length>=target)break;if(sources.some(s=>Math.hypot(s.x-c.x,s.z-c.z)<650))continue;const q=(.3+Math.min(1.6,flow[c.k]/1e6))*(state.parameters?.recharge||1);sources.push({id:'tributary-'+sources.length,x:c.x,z:c.z,width:12+q*15,discharge:q,kind:'spring'});}
 for(const line of state.environment?.waterLines||[]){const first=line.points.find(p=>Math.hypot(p[0],p[2])<C.RADIUS-100);if(first)sources.push({id:line.id,x:first[0],z:first[2],width:line.widths?.[0]||line.width||60,discharge:Math.max(.5,(line.widths?.[0]||60)/80),kind:'river'});}
 const at=(x,z)=>clamp(Math.round((z-min)/step),0,n-1)*n+clamp(Math.round((x-min)/step),0,n-1),height=(x,z)=>C.L.sampleGrid(g,h,x,z);
 for(const src of sources){let k=at(src.x,src.z),best=k;
  // A spring may have been placed on a coarse lip. Find the descending lip within one original cell.
  if(src.kind==='spring')for(let dz=-2;dz<=2;dz++)for(let dx=-2;dx<=2;dx++){const q=k+dz*n+dx;if(q<0||q>=N||Math.abs(q%n-k%n)>2)continue;if(slope[q]>slope[best]&&Math.abs(h[q]-h[k])<160)best=q;}k=best;
  const path=[],cells=[],seen=new Set();let discharge=src.discharge,termination='infiltration',endHeight=h[k],distance=0;
  while(k>=0&&!seen.has(k)){seen.add(k);cells.push(k);const x=min+k%n*step,z=min+Math.floor(k/n)*step,y=routing[k]-h[k]<=24?routing[k]:h[k];path.push([x,y+1.2,z]);const w=src.width*clamp(Math.sqrt(discharge/src.discharge),.25,1);waterWidth[k]=Math.max(waterWidth[k],w);waterHeight[k]=Math.max(waterHeight[k],y+1.2);sourceStrength[k]=Math.max(sourceStrength[k],clamp(discharge/.15));wetDistance[k]=0;endHeight=y;
   if(Math.hypot(x,z)>=C.RADIUS-step){termination='boundary';break;}const q=routing[k]-h[k]>24?rawReceiver[k]:receiver[k];if(q<0){termination=discharge>.1?'pool':'infiltration';break;}distance+=Math.hypot(q%n-k%n,Math.floor(q/n)-Math.floor(k/n))*step;discharge*=Math.exp(-step/(src.kind==='river'?80000:26000));if(discharge<.025){termination='infiltration';break;}k=q;
  }
  const dense=[];for(let i=1;i<path.length;i++){const a=path[i-1],b=path[i],steps=Math.ceil(Math.hypot(b[0]-a[0],b[2]-a[2])/4);for(let j=0;j<steps;j++){const t=j/steps,x=C.mix(a[0],b[0],t),z=C.mix(a[2],b[2],t);dense.push([x,Math.max(height(x,z)+1.2,C.mix(a[1],b[1],t)),z]);}}dense.push(path.at(-1));
  const start=path[0];routes.push({...src,path:dense,renderPath:path,cells,termination,lengthM:distance,outflow:termination==='boundary'?discharge:0,retained:termination==='pool'?discharge:0,infiltrated:src.discharge-(termination==='boundary'||termination==='pool'?discharge:0),top:start[1],bottom:endHeight,x:start[0],z:start[2],frontZ:path[1]?.[2]??start[2]});
 }
 function spread(dist,carry){for(const forward of[true,false])for(let a=0;a<N;a++){const k=forward?a:N-1-a,x=k%n,z=Math.floor(k/n);for(const[dx,dz]of(forward?[[-1,0],[0,-1],[-1,-1],[1,-1]]:[[1,0],[0,1],[1,1],[-1,1]])){if(x+dx<0||x+dx>=n||z+dz<0||z+dz>=n)continue;const q=k+dz*n+dx,d=dist[q]+step*Math.hypot(dx,dz);if(d<dist[k]){dist[k]=d;for(const a of carry)a[k]=a[q];}}}}
 spread(wetDistance,[sourceStrength,waterWidth,waterHeight]);spread(seasonDistance,[seasonal]);
 const data=new Float32Array(N*7);for(let k=0;k<N;k++)data.set([wetDistance[k],sourceStrength[k],waterWidth[k],waterHeight[k],seasonDistance[k],seasonal[k],slope[k]],k*7);
 const report={algorithm:VERSION,ecology:ECOLOGY,stepM:step,routes:routes.length,seasonalCells:Array.from(seasonDistance).filter(v=>v===0).length,terminations:routes.map(r=>({id:r.id,kind:r.termination,lengthM:r.lengthM})),waterBudget:{input:sources.reduce((a,s)=>a+s.discharge,0),exported:routes.reduce((a,r)=>a+r.outflow,0),retained:routes.reduce((a,r)=>a+r.retained,0),infiltrated:routes.reduce((a,r)=>a+r.infiltrated,0)}};
 return{key:key(state),n,min,step,stride:7,data,routes,report};
}
function sample(h,x,z){const out=[];for(let c=0;c<7;c++)out.push(C.L.sampleGrid(h,h.data,x,z,7,c));return out;}
function active(state,x,z,size,p){const h=state.hydrology;if(!h)return false;const a=sample(h,x+size/2,z+size/2),r=size*.72+h.step*1.5;return a[0]<r+(p.riparianWidth||200)+a[2]/2||a[4]<r+96;}
const linear=h=>[1,3,5].map(i=>{const v=parseInt(h.slice(i,i+2),16)/255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});
const LOW=['#6D7950','#456346','#4B6540','#4D6A44'],HIGH=['#939A72','#687959','#6D7958','#6B805E'];const colors=[LOW,HIGH].map(a=>a.map(linear));
function sampleEcology(state,x,y,z,face,p=state.parameters){const hyd=state.hydrology,weights=new Float64Array(C.names.length),rgb=[0,0,0];if(!hyd)return{weights:Array.from(weights),organic:rgb,bare:1,moisture:0,sustainedWater:0,seasonalWater:0,vegetationCoverage:0,waterCoverage:0};
 const a=sample(hyd,x,z),g=state.landforms||state,ground=C.L.sampleGrid(g,g.h,x,z),high=S(1800,3200,ground),bankWidth=p.riparianWidth||200,shore=Math.max(0,a[0]-a[2]/2),vertical=1-S(16,80,Math.abs(ground-a[3])),perennial=(1-S(0,bankWidth,shore))*a[1]*vertical,retention=state.surface?clamp(C.L.sampleGrid(state.surface,state.surface.data,x,z,state.surface.stride,0)*1.4):.8,season=(1-S(24,96,a[4]))*a[5]*retention*(1-S(.12,.7,a[6]))*(p.seasonalGreen??.5),near=1-S(2,30,Math.abs(y-ground)),flat=1-S(.2,.8,a[6]),wet=clamp(perennial*.85+season*.35),water=(1-S(Math.max(1,a[2]*.3),Math.max(8,a[2]*.65),a[0]))*a[1]*vertical;
 if(face===0){weights[4]=clamp(perennial*.62+S(.20,.50,season)*.58)*flat*(p.topGreen/.65);weights[6]=perennial*.11*flat*(1-high*.8);weights[8]=water*.50*(p.water||1);}else{const damp=perennial*(1-S(0,160,Math.abs(y-a[3])));weights[5]=damp*.26*(p.sideGreen/.75);weights[7]=damp*.07;weights[4]=season*.06*near;}
 let sum=weights.reduce((a,b)=>a+b,0);if(sum>.75){for(let i=0;i<weights.length;i++)weights[i]*=.75/sum;sum=.75;}for(let k=0;k<3;k++){for(let i=4;i<8;i++)rgb[k]+=weights[i]*C.mix(colors[0][i-4][k],colors[1][i-4][k],high);rgb[k]+=weights[8]*C.palette[8][k];}
 return{weights:Array.from(weights),organic:rgb,bare:1-sum,moisture:wet,sustainedWater:perennial,seasonalWater:season,vegetationCoverage:weights[4]+weights[5]+weights[6]+weights[7],waterCoverage:weights[8],highland:high};
}
return{VERSION,ECOLOGY,key,deriveHydrology,sampleEcology,sample,active,spillSurface};
});
