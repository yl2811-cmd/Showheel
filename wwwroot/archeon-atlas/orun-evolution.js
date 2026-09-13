/* A bounded delta over the frozen young plateau. No repeated historical sculpting. */
(function(root,factory){const node=typeof module==='object'&&module.exports,api=factory(node?require('./orun-core.js'):root.ORUN_CORE,node?require('./orun-climate.js'):root.ORUN_CLIMATE,node?require('./orun-drainage.js'):root.ORUN_DRAINAGE);if(node)module.exports=api;else root.ORUN_EVOLUTION=api;})(typeof self!=='undefined'?self:globalThis,function(C,CL,D){
'use strict';const VERSION='young-wall-v1',K=C.clamp,S=C.smooth;
function key(base,p,climate){return [VERSION,base.key,climate.key,p.evolutionStrength,p.rainfall,521].join(':');}
function rebuildLevels(g){const levels=[{h:g.h,n:g.n,min:g.min,step:g.step}];let src=levels[0];while(src.step<1024){const n=Math.ceil(src.n/2),h=new Float32Array(n*n);for(let j=0;j<n;j++)for(let i=0;i<n;i++){let v=0;for(let dz=-1;dz<=1;dz++)for(let dx=-1;dx<=1;dx++)v+=src.h[K(j*2+dz,0,src.n-1)*src.n+K(i*2+dx,0,src.n-1)]*(dx===0?2:1)*(dz===0?2:1);h[j*n+i]=v/16;}src={h,n,min:src.min,step:src.step*2};levels.push(src);}return levels;}
function evolveWindwardTerrain(state,p,climate,progress=()=>{}){
 const base=state.baseLandforms||state.landforms||state,{n,min,step}=base,N=base.h.length,h=base.h.slice(),delta=new Float32Array(N),sediment=new Float32Array(N),age=new Float32Array(N).fill(521),g={...base,h},seeds=D.outlets(state,g),strength=p.evolutionStrength??1,protect=(k)=>base.lock?.[k]>.8||Math.hypot(min+k%n*step,min+Math.floor(k/n)*step)>49500;
 progress('正在核对浅洼溢口，保留年轻崖壁骨架…');const raw=D.route(g,seeds,0),pits=[];
 for(let k=0;k<N;k++)if(raw.receiver[k]<0&&!seeds.has(k)&&raw.level[k]-h[k]>.05&&raw.level[k]-h[k]<32&&raw.area[k]>.2e6&&!protect(k))pits.push(k);
 pits.sort((a,b)=>raw.area[b]-raw.area[a]);let breaches=0,breachRemoved=0;
 for(const start of ((p.rainfall??1)>0?pits:[])){let k=start,dist=0,valid=true;const path=[],floor=h[start];for(let a=0;a<1800;a++){const q=raw.parent[k];if(q<0||seeds.has(k))break;dist+=step;const target=floor-dist*.00005;if(h[q]<target)break;if(protect(q)||h[q]-target>32*strength||raw.level[start]-floor>32*strength){valid=false;break;}path.push([q,target]);k=q;}if(!valid||!path.length||path.length>=1799)continue;for(const[k,target]of path){const v=Math.max(target,base.h[k]-32*strength);if(v<h[k]){breachRemoved+=(h[k]-v)*step*step;h[k]=v;age[k]=20;}}breaches++;}
 progress('正在按供水、岩性和落差计算有限冲蚀与沉积…');const r=D.route(g,seeds),load=new Float64Array(N);let eroded=breachRemoved,deposited=0,exported=0,stored=0,protectedMaxDelta=0,maxCut=0,maxFill=0,cliffSamples=0,cliffStable=0;const rainGrid=new Float32Array(N),soft=new Uint8Array(N);
 for(let j=0;j<n;j++)for(let i=0;i<n;i++){const k=j*n+i,x=min+i*step,z=min+j*step,c=CL.sample(climate,x,z);rainGrid[k]=c[7]+c[6]*.25;soft[k]=C.lithology(h[k],x,z,p,state.seed)==='basalt'?0:1;}
 // Breach material is entered into its downstream sediment ledger exactly once.
 for(let k=0;k<N;k++)if(base.h[k]>h[k])load[k]+=(base.h[k]-h[k])*step*step;
 for(const k of r.order){const q=r.receiver[k],x=min+k%n*step,z=min+Math.floor(k/n)*step,wet=rainGrid[k],discharge=r.area[k]*wet/CL.YEAR,sl=r.slope[k],drop=q>=0?Math.max(0,h[k]-h[q]):0,allow=!protect(k);
  if(allow&&q>=0&&wet>0&&strength>0){const stream=S(.012,.35,discharge),weather=soft[k]?(1-S(.15,.8,sl))*.25:0,power=Math.sqrt(discharge)*Math.pow(Math.min(4,sl),.8),cut=Math.min(soft[k]?24:8,(power*(soft[k]?9:2.3)+S(16,180,drop)*stream*(soft[k]?8:2)+weather)*strength);const remaining=Math.max(0,(soft[k]?32:16)*strength-(base.h[k]-h[k])),actual=Math.min(cut,remaining);h[k]-=actual;load[k]+=actual*step*step;eroded+=actual*step*step;if(actual>.1)age[k]=Math.max(2,521*Math.exp(-actual/1.8));}
  let material=load[k];if(material<=0)continue;
  if(seeds.has(k)||Math.hypot(x,z)>=C.RADIUS-step){exported+=material;continue;}
  const lower=q>=0?Math.max(0,h[k]-h[q]):0,capacity=allow?Math.min(Math.max(0,base.h[k]+8-h[k]),q<0?8:lower*.25)*step*step:0,fraction=q<0?1:K(.015+(1-S(.015,.15,sl))*.65),put=Math.min(capacity,material*fraction);h[k]+=put/step/step;sediment[k]+=put/step/step;deposited+=put;material-=put;if(put>.1)age[k]=Math.min(age[k],40+481*Math.exp(-put/step/step));if(q>=0)load[q]+=material;else stored+=material;
 }
 for(let k=0;k<N;k++){delta[k]=h[k]-base.h[k];maxCut=Math.max(maxCut,-delta[k]);maxFill=Math.max(maxFill,delta[k]);if(protect(k))protectedMaxDelta=Math.max(protectedMaxDelta,Math.abs(delta[k]));if(r.slope[k]>.65){cliffSamples++;if(Math.abs(delta[k])<=16.001)cliffStable++;}}
 const residual=eroded-deposited-exported-stored;if(protectedMaxDelta>1e-4||maxCut>64.001||(cliffSamples>0&&cliffStable/cliffSamples<.9)||Math.abs(residual)>Math.max(1,eroded*.001))throw Error('迎风侵蚀超出年轻高原或泥沙预算');
 const report={algorithm:VERSION,elapsedEcologicalYears:521,geologicalAge:'young plateau retained; no age inferred',breaches,maxCutM:maxCut,maxFillM:maxFill,protectedMaxDeltaM:protectedMaxDelta,cliffStableFraction:cliffSamples?cliffStable/cliffSamples:1,sediment:{erodedM3:eroded,depositedM3:deposited,exportedM3:exported,storedM3:stored,residualM3:residual},scope:'Bounded process-calibrated evolution delta, not a measured 521-year erosion forecast'};
 g.baseKey=base.key;g.key=key(base,p,climate);g.evolution={algorithm:VERSION,key:g.key,delta,sediment,age,report};g.levels=rebuildLevels(g);return g;
}
return{VERSION,key,rebuildLevels,evolveWindwardTerrain};
});
