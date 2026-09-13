(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.ATHERIA_SPARSE_CORE=api;})(globalThis,function(){
'use strict';
const defaults={city:.68,fieldMin:.07,fieldMax:.10,heightPower:4,natural:1.7,scales:[180,720]},clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x)),mix=(a,b,t)=>a+(b-a)*t;
function hash(x,z){let h=Math.imul(x,374761393)^Math.imul(z,668265263)^9187;h=Math.imul(h^(h>>>13),1274126177);return((h^(h>>>16))>>>0)/4294967295;}
function noise(x,z){const i=Math.floor(x),j=Math.floor(z),u=x-i,v=z-j,a=u*u*(3-2*u),b=v*v*(3-2*v);return mix(mix(hash(i,j),hash(i+1,j),a),mix(hash(i,j+1),hash(i+1,j+1),a),b);}
function fieldFactor(x,z,p){return mix(p.fieldMin,p.fieldMax,.35*noise(x/p.scales[0]+23,z/p.scales[0]+71)+.65*noise(x/p.scales[1]+149,z/p.scales[1]+61));}
function height(h,p=defaults){return 6+14*Math.pow(clamp((h-6)/14),p.heightPower);}
function validate(p){for(const key of ['city','fieldMin','fieldMax'])if(!Number.isFinite(p[key])||p[key]<0||p[key]>1)throw Error('密度必须在 0–1× 之间');if(p.fieldMin>p.fieldMax)throw Error('田野最小密度不能超过最大密度');if(!Number.isFinite(p.heightPower)||p.heightPower<1||p.heightPower>4)throw Error('高度曲线必须在 1–4 之间');return {...defaults,...p,natural:1.7,scales:[180,720]};}
// Three bytes: city membership, cultivated membership, protected riparian flag.
function weights(mask,k){const o=k*3;if(mask[o+2])return [0,0,1];const c=mask[o]/255,f=(1-c)*mask[o+1]/255;return[c,f,1-c-f];}
function factor(mask,k,x,z,p){const w=weights(mask,k);return w[0]*p.city+w[1]*fieldFactor(x,z,p)+w[2]*p.natural;}
function apply(base,out,mask,meta,p,legacyK){p=validate(p);const area=meta.step**2,stats={city:{area:0,crown:0},field:{area:0,crown:0},natural:{area:0,crown:0},heightBins:[0,0,0],heightCount:0};let total=0;
 for(let k=0;k<meta.n*meta.n;k++){const o=k*12,x=meta.min+(k%meta.n+.5)*meta.step,z=meta.min+(Math.floor(k/meta.n)+.5)*meta.step,w=weights(mask,k),cap=base[o+1],old=Math.min(cap,base[o]+legacyK*base[o+2]),f=fieldFactor(x,z,p),parts=[Math.min(cap,base[o]*p.city),Math.min(cap,base[o]*f),old];out[o]=parts.reduce((s,v,i)=>s+w[i]*v,0);out[o+2]=0;out[o+9]=height(base[o+9],p);total+=out[o]*area;
  for(const [i,key]of ['city','field','natural'].entries()){stats[key].area+=w[i]*area*(cap>0);stats[key].crown+=w[i]*parts[i]*area;}
  if(out[o]>0){stats.heightCount++;stats.heightBins[out[o+9]<=12?0:out[o+9]<=16?1:2]++;}
 }
 return {totalAreaM2:total,zones:stats,parameters:p,method:'fixed-world zoned coverage; no global redistribution'};
}
return {defaults,clamp,noise,fieldFactor,height,validate,weights,factor,apply};
});
