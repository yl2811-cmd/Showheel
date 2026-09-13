/* A small closed basin is solved against its connected terrain, evaporation and permeable bed. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./orun-core.js'):root.ORUN_CORE);if(typeof module==='object'&&module.exports)module.exports=api;else root.ORUN_LAKES=api;})(typeof self!=='undefined'?self:globalThis,function(C){
'use strict';
function solveClosedBasin(g,start,inflow,p,seed){const {n,h,step,min}=g,rows=g.nz||n,maxLevel=h[start]+64,queue=[start],seen=new Set([start]),candidates=[],area=step*step;let head=0;
 while(head<queue.length){const k=queue[head++],x=k%n,z=Math.floor(k/n);candidates.push(k);for(const[dx,dz]of[[0,-1],[-1,0],[1,0],[0,1]]){const xx=x+dx,zz=z+dz,q=zz*n+xx;if(xx<0||xx>=n||zz<0||zz>=rows||seen.has(q)||h[q]>=maxLevel)continue;if(Math.hypot(xx-start%n,zz-Math.floor(start/n))*step>2048)continue;seen.add(q);queue.push(q);}}
 // A lower neighbouring hollow cannot receive water before its connecting saddle is flooded.
 const entry=new Map([[start,h[start]]]),pending=[start],queued=new Set([start]);
 for(let pos=0;pos<pending.length;pos++){const k=pending[pos];queued.delete(k);for(const [dx,dz]of[[0,-1],[-1,0],[1,0],[0,1]]){const x=k%n+dx,z=Math.floor(k/n)+dz,q=z*n+x;if(x<0||x>=n||z<0||z>=rows||!seen.has(q))continue;const level=Math.max(entry.get(k),h[q]);if(level<(entry.get(q)??Infinity)){entry.set(q,level);if(!queued.has(q)){pending.push(q);queued.add(q);}}}}
 const conductance=candidates.map(k=>{const lith=C.lithology(h[k],min+k%n*step,min+Math.floor(k/n)*step,p,seed);return area*(lith==='basalt'?5e-5:lith==='pale'?1.5e-5:5e-6);});
 function balance(level,collect=false){let loss=0,evap=0,volume=0,wetArea=0;const cells=[],fractions=[];for(let i=0;i<candidates.length;i++){const k=candidates[i],depth=Math.max(0,level-h[k]),fraction=C.smooth(0,.25,Math.max(0,level-entry.get(k)));if(!fraction)continue;loss+=conductance[i]*fraction*(1+depth/2);evap+=area*fraction*.8/31557600;volume+=area*fraction*depth;wetArea+=area*fraction;if(collect){cells.push(k);fractions.push(fraction);}}return{loss,evap,volume,wetArea,cells,fractions};}
 let low=h[start],high=maxLevel;if(balance(high).loss+balance(high).evap<inflow)throw Error('闭洼储水超出局部湖盆求解范围');for(let i=0;i<32;i++){const mid=(low+high)/2,b=balance(mid);if(b.loss+b.evap>inflow)high=mid;else low=mid;}const level=(low+high)/2,b=balance(level,true);
 return{id:'closed-'+start,kind:'closed-infiltration',level,cells:b.cells,fractions:b.fractions,areaM2:b.wetArea,volumeM3:b.volume,inflow,evaporation:b.evap,infiltrationM3s:b.loss,storageChangeM3s:0,waterBalanceResidual:inflow-b.evap-b.loss,termination:'permeable closed basin; seepage enters the regional deep aquifer',bedConductivityMps:[5e-6,5e-5]};
}
return{solveClosedBasin};
});
