(function(root,factory){const a=factory();if(typeof module==='object'&&module.exports)module.exports=a;else root.ATHERIA_CANOPY_CORE=a;})(globalThis,function(){
'use strict';const STRIDE=12,clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v)),area=p=>Math.abs(p.reduce((s,a,i)=>{const b=p[(i+1)%p.length];return s+a[0]*b[1]-b[0]*a[1];},0))*.5;
function coverage(base,cap,weight,factor,k){return factor<=1?Math.min(cap,base*factor):Math.min(cap,base+k*weight);}
function calibrate(data,baselineArea,cellArea,factor){if(factor<=1)return 0;let low=0,high=1;const sum=k=>{let n=0;for(let i=0;i<data.length;i+=STRIDE)n+=coverage(data[i],data[i+1],data[i+2],factor,k)*cellArea;return n;};const target=baselineArea*factor;while(high<1e7&&sum(high)<target)high*=2;for(let j=0;j<44;j++){const mid=(low+high)/2;if(sum(mid)<target)low=mid;else high=mid;}return high;}
function field(meta,data){const coefficients=new Map(Object.entries(meta.coefficients||{}).map(([k,v])=>[Number(k),v])),coefficient=f=>{const key=Math.round(clamp(f,0,5)*10)/10;if(!coefficients.has(key))coefficients.set(key,calibrate(data,meta.baselineGroundAreaM2,meta.step**2,key));return coefficients.get(key);};return{meta,data,coefficient,sample(x,z,w,d=w,factor=1.7){let total=0,wood=0,ht=0,base=0,cap=0;const ground=[0,0,0],colour=[0,0,0],k=coefficient(factor);for(let j=Math.max(0,Math.floor((z-meta.min)/meta.step));j<Math.min(meta.n,Math.ceil((z+d-meta.min)/meta.step));j++)for(let i=Math.max(0,Math.floor((x-meta.min)/meta.step));i<Math.min(meta.n,Math.ceil((x+w-meta.min)/meta.step));i++){const xx=meta.min+i*meta.step,zz=meta.min+j*meta.step,a=Math.max(0,Math.min(x+w,xx+meta.step)-Math.max(x,xx))*Math.max(0,Math.min(z+d,zz+meta.step)-Math.max(z,zz)),o=(j*meta.n+i)*STRIDE,c=coverage(data[o],data[o+1],data[o+2],factor,k);if(!a)continue;total+=a;wood+=a*c;ht+=a*c*data[o+9];base+=a*data[o];cap+=a*data[o+1];for(let v=0;v<3;v++){ground[v]+=a*data[o+3+v];colour[v]+=a*c*data[o+6+v];}}return{coverage:wood/Math.max(1,total),height:ht/Math.max(1e-9,wood),base:base/Math.max(1,total),capacity:cap/Math.max(1,total),ground:ground.map(v=>v/Math.max(1,total)),colour:colour.map(v=>v/Math.max(1e-9,wood))};},total(factor=1.7){const k=coefficient(factor);let result=0,maximum=0;for(let i=0;i<data.length;i+=STRIDE){result+=coverage(data[i],data[i+1],data[i+2],factor,k)*meta.step**2;maximum+=data[i+1]*meta.step**2;}return{requested:factor,groundAreaM2:result,groundRatio:result/meta.baselineGroundAreaM2,maximumAreaM2:maximum};}};}
function subtractRect(polys,b){const rect=b.polygon||[[b.x-b.w/2,b.z-b.d/2],[b.x+b.w/2,b.z-b.d/2],[b.x+b.w/2,b.z+b.d/2],[b.x-b.w/2,b.z+b.d/2]],cut=(p,a,b,inside)=>{const side=q=>(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]),out=[];for(let i=0;i<p.length;i++){const u=p[i],v=p[(i+1)%p.length],su=side(u),sv=side(v),ui=inside?su>=0:su<=0,vi=inside?sv>=0:sv<=0;if(ui)out.push(u);if(ui!==vi){const t=su/(su-sv);out.push([u[0]+(v[0]-u[0])*t,u[1]+(v[1]-u[1])*t]);}}return out;};const out=[];for(const p of polys){let left=p;for(let i=0;i<rect.length&&left.length>=3;i++){const a=rect[i],b=rect[(i+1)%rect.length],q=cut(left,a,b,false);if(q.length>=3&&area(q)>.0001)out.push(q);left=cut(left,a,b,true);}}return out;}
function materialTint(x,z){const hash=(x,z)=>{let h=Math.imul(x,374761393)^Math.imul(z,668265263)^9187;h=Math.imul(h^(h>>>13),1274126177);return((h^(h>>>16))>>>0)/4294967295;},noise=(x,z)=>{const i=Math.floor(x),j=Math.floor(z),u=x-i,v=z-j,a=u*u*(3-2*u),b=v*v*(3-2*v);return(hash(i,j)*(1-a)+hash(i+1,j)*a)*(1-b)+(hash(i,j+1)*(1-a)+hash(i+1,j+1)*a)*b;},f=.40*noise(x/140+23,z/140+71)+.30*noise(x/45+149,z/45+61)+.20*noise(x/13+383,z/13+293)+.10*noise(x/4+911,z/4+733),shade=(f-.5)*.10,hue=(noise(x/37+53,z/41+137)-.5)*.02;return[1+shade+hue,1+shade,1+shade-hue];}
function intersectRect(polys,x,z,w,d){const clip=(p,axis,bound,sign)=>{const out=[];for(let i=0;i<p.length;i++){const a=p[i],b=p[(i+1)%p.length],sa=(a[axis]-bound)*sign,sb=(b[axis]-bound)*sign;if(sa>=0)out.push(a);if((sa>=0)!==(sb>=0)){const t=sa/(sa-sb);out.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]);}}return out;};return polys.map(p=>clip(clip(clip(clip(p,0,x,1),0,x+w,-1),1,z,1),1,z+d,-1)).filter(p=>p.length>=3&&area(p)>.000001);}
// Coverage changes crown footprint. Once a crown exists it quickly reaches mature height.
function crownHeight(height,coverage){return clamp(height,4.5,20)*(1-Math.exp(-Math.max(0,coverage)/.008));}
function crownFootprint(polys,target,x,z,step=32){const available=polys.reduce((n,p)=>n+area(p),0);target=Math.min(target,available*.94);if(target<=0)return[];let low=0,high=step*2;for(let i=0;i<22;i++){const side=(low+high)/2,p=intersectRect(polys,x-side/2,z-side/2,side,side);if(p.reduce((n,p)=>n+area(p),0)<target)low=side;else high=side;}return intersectRect(polys,x-high/2,z-high/2,high,high);}
// A narrow clump becomes an area mixture with its planted support. Broad crowns
// keep the full block. Compute this before terrain clipping so steps cannot flip it.
function crownAppearance(crowns,support,height,x,z,step=32){
 const crownArea=crowns.reduce((n,p)=>n+area(p),0),available=support.reduce((n,p)=>n+area(p),0);if(crownArea<=0||available<=0)return{polygons:[],crownArea:0,renderArea:0,coverage:0,height:0,ratio:0,solidBlend:0};
 let left=Infinity,right=-Infinity,back=Infinity,front=-Infinity;for(const p of crowns)for(const [x,z]of p){left=Math.min(left,x);right=Math.max(right,x);back=Math.min(back,z);front=Math.max(front,z);}
 const longSide=Math.max(right-left,front-back),shortSide=Math.min(right-left,front-back,crownArea/Math.max(.000001,longSide)),ratio=shortSide/Math.max(.001,height),u=clamp((ratio-.25)/.75),solidBlend=u*u*u*(u*(u*6-15)+10),target=crownArea+(Math.max(crownArea,available*.94)-crownArea)*(1-solidBlend),polygons=solidBlend===1?crowns:crownFootprint(support,target,x,z,step),renderArea=polygons.reduce((n,p)=>n+area(p),0),coverage=clamp(crownArea/Math.max(.000001,renderArea));
 return{polygons,crownArea,renderArea,coverage,height:height*coverage,ratio,solidBlend};
}
function weakColourCoverage(coverage,pixels){const c=clamp(coverage);return c+(Math.sqrt(c)-c)*smooth(.2,.65,c)*smooth(.75,2.5,pixels);}
function crownColour(ground,leaf,coverage){return leaf.map((v,k)=>ground[k]*(1-coverage)+v*coverage);}

function random(x,z,seed=0){let h=Math.imul(x,374761393)^Math.imul(z,668265263)^Math.imul(seed,2246822519);h=Math.imul(h^(h>>>13),1274126177);return((h^(h>>>16))>>>0)/4294967296;}
function smooth(a,b,v){const t=clamp((v-a)/(b-a));return t*t*(3-2*t);}
// One stable population under every terrain LOD. Sampling cells never become render tiles.
function treeSites(x,z,step=32,kind=1){
 const i=Math.round(x/step),j=Math.round(z/step),group=kind!==0&&random(i,j,803)<.0295,count=group?3+Math.floor(random(i,j,809)*5):1;
 const cx=x+step*(.15+.7*random(i,j,811)),cz=z+step*(.15+.7*random(i,j,821)),phase=random(i,j,823)*Math.PI*2;
 return Array.from({length:count},(_,k)=>{const angle=phase+k*Math.PI*2/count,r=group?step*(.12+.09*random(i,j,827+k)):0;return{x:clamp(cx+Math.cos(angle)*r,x+1,x+step-1),z:clamp(cz+Math.sin(angle)*r,z+1,z+step-1),group,kind,id:i+','+j+'/'+k};});
}
function clipHalfPlane(poly,nx,nz,bound){const out=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],sa=bound-a[0]*nx-a[1]*nz,sb=bound-b[0]*nx-b[1]*nz;if(sa>=0)out.push(a);if((sa>=0)!==(sb>=0)){const t=sa/(sa-sb);out.push([a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]);}}return out;}
function siteCrowns(support,target,sites,step=32){
 if(sites.length===1&&support.length===1&&support[0].length===4){const p=support[0],xs=p.map(v=>v[0]),zs=p.map(v=>v[1]),x=Math.min(...xs),z=Math.min(...zs),w=Math.max(...xs)-x,d=Math.max(...zs)-z;if(Math.abs(area(p)-w*d)<1e-6){const side=Math.sqrt(Math.min(target,w*d*.94));if(side<=Math.min(w,d)){const cx=clamp(sites[0].x,x+side/2,x+w-side/2),cz=clamp(sites[0].z,z+side/2,z+d-side/2);return[{...sites[0],polygons:[[[cx-side/2,cz-side/2],[cx-side/2,cz+side/2],[cx+side/2,cz+side/2],[cx+side/2,cz-side/2]]]}];}}}
 const partitions=sites.map((s,i)=>{let polys=support;for(let j=0;j<sites.length;j++){if(i===j)continue;const q=sites[j],nx=q.x-s.x,nz=q.z-s.z,b=(q.x*q.x+q.z*q.z-s.x*s.x-s.z*s.z)/2;polys=polys.map(p=>clipHalfPlane(p,nx,nz,b)).filter(p=>p.length>=3&&area(p)>1e-6);}return polys;});
 const available=partitions.map(ps=>ps.reduce((a,p)=>a+area(p),0)),total=available.reduce((a,b)=>a+b,0);
 return sites.map((site,i)=>({...site,polygons:crownFootprint(partitions[i],Math.min(target,total*.94)*available[i]/Math.max(1e-9,total),site.x,site.z,step)}));
}
function lodAppearance(coverage,height,projectedPixels){
 const c=clamp(coverage),resolve=smooth(.75,2.5,projectedPixels),relief=clamp(height,4.5,20)*(1-Math.exp(-c/.015));
 return{height:relief,resolve,coverage:c,colourCoverage:c+(1-c)*resolve*smooth(.25,1,Math.sqrt(c))};
}

function population(field,exclude,density){
 const {meta,data}=field,cache=new Map(),step=meta.step,cellArea=step*step;
 function cell(i,j,f){const key=i+','+j+':'+f;if(cache.has(key))return cache.get(key);const x=meta.min+i*step,z=meta.min+j*step,o=(j*meta.n+i)*STRIDE,k=field.coefficient(f),c=coverage(data[o],data[o+1],data[o+2],f,k),support=exclude([[[x,z],[x,z+step],[x+step,z+step],[x+step,z]]],x+step/2,z+step/2,step,step),crowns=siteCrowns(support,c*cellArea,treeSites(x,z,step,data[o+10]),step),result={crowns,area:crowns.reduce((n,s)=>n+s.polygons.reduce((a,p)=>a+area(p),0),0)};if(cache.size>24000)cache.delete(cache.keys().next().value);cache.set(key,result);return result;}
 function sample(x,z,w,d=w){let wood=0,ht=0,groundWeight=0;const colour=[0,0,0],ground=[0,0,0];for(let j=Math.max(0,Math.floor((z-meta.min)/step));j<Math.min(meta.n,Math.ceil((z+d-meta.min)/step));j++)for(let i=Math.max(0,Math.floor((x-meta.min)/step));i<Math.min(meta.n,Math.ceil((x+w-meta.min)/step));i++){
  const xx=meta.min+i*step,zz=meta.min+j*step,o=(j*meta.n+i)*STRIDE,a=Math.max(0,Math.min(x+w,xx+step)-Math.max(x,xx))*Math.max(0,Math.min(z+d,zz+step)-Math.max(z,zz));if(!a)continue;groundWeight+=a;for(let v=0;v<3;v++)ground[v]+=a*data[o+3+v];if(data[o+1]<=0)continue;
  const f=density(xx+step/2,zz+step/2),c=coverage(data[o],data[o+1],data[o+2],f,field.coefficient(f));if(c<=0)continue;
  let covered;if(Math.abs(a-cellArea)<1e-5)covered=c*cellArea;else covered=cell(i,j,f).crowns.reduce((n,s)=>n+intersectRect(s.polygons,x,z,w,d).reduce((n,p)=>n+area(p),0),0);
  wood+=covered;ht+=covered*data[o+9];for(let v=0;v<3;v++)colour[v]+=covered*data[o+6+v];
 }
 return{area:wood,coverage:wood/Math.max(1,w*d),height:ht/Math.max(1e-9,wood),colour:colour.map(v=>v/Math.max(1e-9,wood)),ground:ground.map(v=>v/Math.max(1,groundWeight))};}
 return{sample,cell,clear(){cache.clear();},cacheSize:()=>cache.size};
}

return{weakColourCoverage,population,random,smooth,treeSites,siteCrowns,lodAppearance,STRIDE,clamp,area,field,calibrate,subtractRect,materialTint,intersectRect,crownHeight,crownFootprint,crownAppearance,crownColour};
});
