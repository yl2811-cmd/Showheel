/* Shared, deterministic outlet-rooted drainage; surface conditioning is never implicit erosion. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./orun-core.js'):root.ORUN_CORE);if(typeof module==='object'&&module.exports)module.exports=api;else root.ORUN_DRAINAGE=api;})(typeof self!=='undefined'?self:globalThis,function(C){
'use strict';const OFF=[[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];
function index(g,x,z){return C.clamp(Math.round((z-g.min)/g.step),0,(g.nz||g.n)-1)*g.n+C.clamp(Math.round((x-g.min)/g.step),0,g.n-1);}
function outlets(state,g){const map=new Map();for(const line of state.environment?.waterLines||[]){const pts=line.points;for(let a=1;a<pts.length;a++){const u=pts[a-1],v=pts[a],steps=Math.max(1,Math.ceil(Math.hypot(v[0]-u[0],v[2]-u[2])/g.step));for(let i=0;i<=steps;i++){const t=i/steps,x=C.mix(u[0],v[0],t),z=C.mix(u[2],v[2],t);if(x<g.min||z<g.min||x>g.min+(g.n-1)*g.step||z>g.min+(g.n-1)*g.step)continue;map.set(index(g,x,z),line.id);}}}return map;}
function flood(g,seeds=new Map()){
 const {n,h}=g,rows=g.nz||n,N=h.length,level=Float32Array.from(h),parent=new Int32Array(N).fill(-1),rank=new Int32Array(N),seen=new Uint8Array(N),heap=[];let seq=0;
 const less=(a,b)=>level[a]<level[b]||level[a]===level[b]&&a<b;
 function push(k){let i=heap.length;heap.push(k);while(i){const p=(i-1)>>1;if(!less(k,heap[p]))break;heap[i]=heap[p];i=p;}heap[i]=k;}
 function pop(){const out=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let c=i*2+1;if(c+1<heap.length&&less(heap[c+1],heap[c]))c++;if(!less(heap[c],last))break;heap[i]=heap[c];i=c;}heap[i]=last;}return out;}
 for(let k=0;k<N;k++)if(!Number.isFinite(h[k]))seen[k]=1;
 for(let k=0;k<N;k++)if(!seen[k]&&(k<n||k>=N-n||k%n===0||k%n===n-1||seeds.has(k))){seen[k]=1;push(k);}
 while(heap.length){const k=pop();rank[k]=seq++;const x=k%n,z=Math.floor(k/n);for(const [dx,dz]of[[0,-1],[-1,0],[1,0],[0,1]]){if(x+dx<0||x+dx>=n||z+dz<0||z+dz>=rows)continue;const q=k+dx+dz*n;if(seen[q])continue;seen[q]=1;level[q]=Math.max(h[q],level[k]);parent[q]=k;push(q);}}
 return{level,parent,rank};
}
function route(g,seeds=new Map(),maxLakeDepth=16){const {n,h,step}=g,rows=g.nz||n,N=h.length,f=flood(g,seeds),stage=Float32Array.from(h,(v,k)=>f.level[k]-v<=maxLakeDepth?f.level[k]:v),receiver=new Int32Array(N).fill(-1),order=Uint32Array.from({length:N},(_,i)=>i),area=new Float64Array(N).fill(step*step),slope=new Float32Array(N);
 order.sort((a,b)=>stage[b]-stage[a]||f.rank[b]-f.rank[a]);
 for(const k of order){if(seeds.has(k)||!Number.isFinite(h[k])){if(!Number.isFinite(h[k]))area[k]=0;continue;}const x=k%n,z=Math.floor(k/n);let best=-1,bw=-1,sum=0;const qs=[],ws=[];for(const [dx,dz]of OFF){if(x+dx<0||x+dx>=n||z+dz<0||z+dz>=rows)continue;const q=k+dx+dz*n,drop=stage[k]-stage[q];if(drop<0||drop===0&&f.rank[q]>=f.rank[k])continue;if(dx&&dz){const cross=stage[k+dx]+stage[k+dz*n];if(cross>2*stage[k]+1e-5||cross<2*stage[q]-1e-5)continue;}const sl=Math.max(1e-8,drop/(step*Math.hypot(dx,dz))),w=sl**1.1;qs.push(q);ws.push(w);sum+=w;if(w>bw){bw=w;best=q;}slope[k]=Math.max(slope[k],sl);}receiver[k]=best;for(let i=0;i<qs.length;i++)area[qs[i]]+=area[k]*ws[i]/sum;}
 return{...f,stage,receiver,order,area,slope};
}
function spread(g,dist,carry,maxDistance=Infinity){const {n,step}=g,rows=g.nz||n,N=n*rows;for(const forward of[true,false])for(let a=0;a<N;a++){const k=forward?a:N-1-a,x=k%n,z=Math.floor(k/n);for(const[dx,dz]of(forward?[[-1,0],[0,-1],[-1,-1],[1,-1]]:[[1,0],[0,1],[1,1],[-1,1]])){if(x+dx<0||x+dx>=n||z+dz<0||z+dz>=rows)continue;const q=k+dz*n+dx,d=dist[q]+step*Math.hypot(dx,dz);if(d<dist[k]&&d<maxDistance){dist[k]=d;for(const a of carry)a[k]=a[q];}}}}
return{OFF,index,outlets,flood,route,spread};
});
