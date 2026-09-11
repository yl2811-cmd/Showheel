/* Deterministic building edits, shared by the preview worker and local export. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.AtheriaEditorCore=api;})(globalThis,function(){
'use strict';
const keys=['smallCount','smallSize','smallHeight','terraceCount','terraceSize','terraceHeight','terraceLevels','splitMinArea','split','scatter','lod'];
const defaults=()=>Object.fromEntries(keys.map(k=>[k,.5]));
const controlRevision="terrace-volume-v5";
const acceptsRevision=revision=>[controlRevision,'fuller-splitting-v4.1','fuller-splitting-v4','split-threshold-v3','expanded-600m2-v2'].includes(revision);
const splitArea=24*20*1.25;
const minimumArea=(v=.5)=>v<=.5?100+1000*v:600+800*(v-.5);
const scaleAt=(v,low,high)=>v<=.5?low+(1-low)*v*2:1+(high-1)*(v-.5)*2;
function factor(key,v){if(key==='smallCount')return scaleAt(v,.3,5);if(key==='terraceCount')return scaleAt(v,.4,2);if(key.endsWith('Size'))return scaleAt(v,.6,2);if(key.endsWith('Height'))return scaleAt(v,.5,2);if(key==='terraceLevels')return Math.round((v-.5)*8);if(key==='split')return Math.max(0,(v-.5)*2);return 1;}
const canSplit=(bs,threshold=splitArea)=>bs.length>0&&unionArea(bs)>threshold;
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const clone=v=>JSON.parse(JSON.stringify(v));
const sum=(a,f)=>a.reduce((n,v)=>n+f(v),0);
function hash(s){let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619);return h>>>0;}
const rank=(a,b)=>hash(a.id)-hash(b.id)||a.id.localeCompare(b.id);
function unionArea(bs){const xs=[...new Set(bs.flatMap(b=>[b.x-b.w/2,b.x+b.w/2]))].sort((a,b)=>a-b);let area=0;for(let i=1;i<xs.length;i++){const a=xs[i-1],b=xs[i];if(b-a<1e-9)continue;const spans=bs.filter(q=>q.x-q.w/2<b-1e-9&&q.x+q.w/2>a+1e-9).map(q=>[q.z-q.d/2,q.z+q.d/2]).sort((a,b)=>a[0]-b[0]);if(!spans.length)continue;let [lo,hi]=spans[0],length=0;for(const p of spans.slice(1)){if(p[0]>hi){length+=hi-lo;lo=p[0];hi=p[1];}else hi=Math.max(hi,p[1]);}length+=hi-lo;area+=(b-a)*length;}return area;}
function volume(bs){const heights=[...new Set([0,...bs.map(b=>b.h)])].sort((a,b)=>a-b);let v=0;for(let i=1;i<heights.length;i++)v+=(heights[i]-heights[i-1])*unionArea(bs.filter(b=>b.h>=heights[i]-1e-7));return v;}
const overlap=(a,b,pad=0)=>Math.abs(a.x-b.x)<(a.w+b.w)/2+pad-1e-6&&Math.abs(a.z-b.z)<(a.d+b.d)/2+pad-1e-6;
function bounds(bs){return {minX:Math.min(...bs.map(b=>b.x-b.w/2)),maxX:Math.max(...bs.map(b=>b.x+b.w/2)),minZ:Math.min(...bs.map(b=>b.z-b.d/2)),maxZ:Math.max(...bs.map(b=>b.z+b.d/2))};}
function center(bs){const total=sum(bs,b=>b.w*b.d);return [sum(bs,b=>b.x*b.w*b.d)/total,sum(bs,b=>b.z*b.w*b.d)/total];}
function components(bs){const pending=new Set(bs),groups=[];while(pending.size){const first=pending.values().next().value;pending.delete(first);const part=[first];for(let i=0;i<part.length;i++)for(const b of pending){const a=part[i],gap=Math.max(.25,Math.min(a.s||a.w,b.s||b.w)*.09),dx=Math.abs(a.x-b.x)-(a.w+b.w)/2,dz=Math.abs(a.z-b.z)-(a.d+b.d)/2;if(dx<=gap&&dz<=gap&&(dx<-.1||dz<-.1)){part.push(b);pending.delete(b);}}groups.push(part);}return groups;}
function levels(bs){return new Set(bs.map(b=>Math.round(b.h/2))).size;}
function params(state,unit){const p={...defaults(),...state.global,...state.units?.[unit.id]};for(const k of keys)if(!Number.isFinite(p[k])||p[k]<0||p[k]>1)throw Error('Invalid parameter '+k);return p;}
function changeLevels(bs,delta){if(!delta)return bs;const out=clone(bs),peak=Math.max(...out.map(b=>b.h)),bands=()=>{const map=new Map();for(const b of out){const key=Math.round(b.h/2);if(!map.has(key))map.set(key,[]);map.get(key).push(b);}return [...map].sort((a,b)=>a[0]-b[0]);};
 for(let k=0;k<Math.abs(delta);k++){const rows=bands();if(delta<0){if(rows.length<=2)break;let best=0;for(let i=1;i<rows.length-1;i++)if(rows[i][1].length<rows[best][1].length)best=i;const target=rows[best+1][1][0].h;rows[best][1].forEach(b=>b.h=target);}else{const candidates=rows.slice(0,-1).map((r,i)=>({r,next:rows[i+1]})).filter(q=>q.r[1].length>=2&&q.next[0]-q.r[0]>=2).sort((a,b)=>b.r[1].length-a.r[1].length);if(!candidates.length)break;const q=candidates[0],high=out.find(b=>b.h===peak),ordered=[...q.r[1]].sort((a,b)=>Math.hypot(a.x-high.x,a.z-high.z)-Math.hypot(b.x-high.x,b.z-high.z)||rank(a,b)),h=(q.r[0]+Math.ceil((q.next[0]-q.r[0])/2))*2;ordered.slice(0,Math.max(1,Math.floor(ordered.length/2))).forEach(b=>b.h=Math.min(peak,h));}}
 return out.map(b=>({...b,top:b.y+b.h}));}
const cutCache=new WeakMap();
const chooseCuts=(options,targetShare)=>[...new Set([...options].sort((a,b)=>Math.abs(a.share-targetShare)-Math.abs(b.share-targetShare)||a.score-b.score).slice(0,12).concat([...options].sort((a,b)=>a.share-b.share||a.score-b.score).slice(0,12)))];
function cutOptions(bs,threshold=splitArea,targetShare=.3){if(!canSplit(bs,threshold))return[];if(cutCache.has(bs))return chooseCuts(cutCache.get(bs),targetShare);const peak=bs.reduce((a,b)=>a.h>b.h?a:b),out=[];for(const axis of ['x','z']){const values=[...new Set(bs.map(b=>b[axis]))].sort((a,b)=>a-b);for(let i=1;i<values.length-1;i++){const line=values[i],width=Math.max(...bs.map(b=>b.s||Math.min(b.w,b.d))),removed=bs.filter(b=>Math.abs(b[axis]-line)<width*.54),kept=bs.filter(b=>!removed.includes(b));if(removed.length<1||removed.length>bs.length*.28||removed.includes(peak))continue;const groups=components(kept);if(groups.length===2&&groups.every(g=>g.length>=Math.min(3,Math.max(1,Math.floor(bs.length/5)))))out.push({removed,kept,groups,score:sum(removed,b=>b.w*b.d)*(1+sum(removed,b=>b.h)/removed.length/15)});}
 for(const side of [-1,1])for(let i=1;i<values.length;i++){const line=(values[i-1]+values[i])/2,removed=bs.filter(b=>(b[axis]-line)*side>0),kept=bs.filter(b=>!removed.includes(b));if(removed.length<1||removed.length>bs.length*.25||removed.includes(peak)||sum(removed,b=>b.h)/removed.length>peak.h*.68)continue;const groups=components(kept);if(groups.length===1&&kept.length>=6)out.push({removed,kept,groups,score:sum(removed,b=>b.w*b.d)*(1.2+sum(removed,b=>b.h)/removed.length/15)});}}
 // Fewer sampled columns and flat detached houses can shed an existing side wing too.
 for(const axis of ['x','z'])for(const side of [-1,1]){const ordered=[...bs].sort((a,b)=>side*(b[axis]-a[axis])||a.h-b.h);for(let n=1;n<=Math.max(1,Math.floor(bs.length*.4));n++){const removed=ordered.slice(0,n),kept=bs.filter(b=>!removed.includes(b));if(!kept.length||removed.includes(peak)||components(kept).length>2)continue;out.push({removed,kept,score:1e8+sum(removed,b=>b.w*b.d)*(1+sum(removed,b=>b.h)/n/15)});}}
 // Clip an edge across any current house or terrace, including narrow single slabs.
 const bb=bounds(bs);for(const axis of ['x','z'])for(const side of [-1,1])for(const fraction of [.15,.25,.35,.45]){const dim=axis==='x'?'w':'d',lo=axis==='x'?bb.minX:bb.minZ,hi=axis==='x'?bb.maxX:bb.maxZ,line=side>0?hi-(hi-lo)*fraction:lo+(hi-lo)*fraction;if((peak[axis]-line)*side>0)continue;const kept=[],removed=[],tag='/edge-'+axis+'-'+side+'-'+fraction;for(const b of bs){const a=b[axis]-b[dim]/2,z=b[axis]+b[dim]/2;for(const move of [false,true]){const upper=(side>0)===move,start=upper?Math.max(a,line):a,end=upper?z:Math.min(z,line);if(end-start<1e-6)continue;const whole=Math.abs(end-start-b[dim])<1e-6,piece={...b,id:whole||!move?b.id:b.id+tag,sourceColumn:b.sourceColumn||b.id,splitFrom:b.splitFrom||b.id,[axis]:(start+end)/2,[dim]:end-start,fragmented:true};(move?removed:kept).push(piece);}}if(!kept.length||!removed.length||removed.some(b=>Math.min(b.w,b.d)<3)||components(kept).length>2)continue;out.push({kept,removed,partial:true,score:1.5e8});}
 // A large single voxel is a sampled house, not a reason to exclude it. Cut one
 // rectangular corner into a detached piece, preserving the exact original union.
 const area=unionArea(bs);for(const b of [...bs].sort((a,b)=>a.h-b.h||b.w*b.d-a.w*a.d).slice(0,8))for(const ratio of [.5,.4])for(const sx of [-1,1])for(const sz of [-1,1]){const w=b.w*ratio,d=b.d*.5;if(Math.min(w,d)<4||w*d<area*.08)continue;const lineage=b.sourceColumn||b.id,key='/corner-'+ratio+'-'+sx+'-'+sz,moved={...b,id:b.id+key+'/moved',sourceColumn:lineage,splitFrom:b.id,x:b.x+sx*(b.w-w)/2,z:b.z+sz*(b.d-d)/2,w,d,fragmented:true};const kept=[...bs.filter(q=>q!==b),{...b,sourceColumn:lineage,splitFrom:b.id,x:b.x-sx*w/2,w:b.w-w,fragmented:true},{...b,id:b.id+key+'/kept',sourceColumn:lineage,splitFrom:b.id,x:moved.x,z:b.z-sz*d/2,w,d:b.d-d,fragmented:true}];if(components(kept).length>2)continue;out.push({removed:[moved],kept,partial:true,score:2e8+w*d*(1+b.h/15)});}
 const options=out.filter(q=>Math.abs(unionArea(q.kept)+sum(q.removed,b=>b.w*b.d)-area)<.001).map(q=>({...q,share:sum(q.removed,b=>b.w*b.d)/area}));cutCache.set(bs,options);return chooseCuts(options,targetShare);}
function smallerPieces(bs,limit){return bs.flatMap(b=>{const nx=Math.ceil(b.w/limit),nz=Math.ceil(b.d/limit);if(nx===1&&nz===1)return[b];const w=b.w/nx,d=b.d/nz,out=[];for(let j=0;j<nz;j++)for(let i=0;i<nx;i++)out.push({...b,id:b.id+'/piece-'+nx+'-'+nz+'-'+i+'-'+j,sourceColumn:b.sourceColumn||b.id,splitFrom:b.splitFrom||b.id,x:b.x-b.w/2+(i+.5)*w,z:b.z-b.d/2+(j+.5)*d,w,d,fragmented:true});return out;});}

// A side peel is measured on the source footprint, before compacting its rooms.
function terraceCuts(bs,threshold,targetShare){
 if(!canSplit(bs,threshold))return [];
 const peak=bs.reduce((a,b)=>a.h>b.h?a:b),area=unionArea(bs),box=bounds(bs),options=[],seen=new Set();
 function clip(axis,side,line,input=bs){
  const dim=axis==='x'?'w':'d',kept=[],removed=[];
  for(const b of input){const lo=b[axis]-b[dim]/2,hi=b[axis]+b[dim]/2;
   for(const move of [false,true]){const upper=(side>0)===move,start=upper?Math.max(lo,line):lo,end=upper?hi:Math.min(hi,line);if(end-start<1e-7)continue;
    const whole=Math.abs(end-start-b[dim])<1e-7;
    (move?removed:kept).push({...b,id:whole||!move?b.id:b.id+'/peel-'+axis+'-'+side+'-'+line.toFixed(6),sourceColumn:b.sourceColumn||b.id,splitFrom:b.splitFrom||b.id,[axis]:(start+end)/2,[dim]:end-start,fragmented:true});
   }
  }return {kept,removed};
 }
 const sides=[['x',-1],['x',1],['z',-1],['z',1]],patterns=[...sides.map(s=>[s]),...[[-1,-1],[-1,1],[1,-1],[1,1]].map(([x,z])=>[['x',x],['z',z]]),sides];
 for(const pattern of patterns){
  function peel(fraction){let kept=bs,removed=[];for(const [axis,side]of pattern){const dim=axis==='x'?'w':'d',boundary=side>0?(axis==='x'?box.maxX:box.maxZ):(axis==='x'?box.minX:box.minZ),inner=peak[axis]+side*peak[dim]/2,q=clip(axis,side,boundary+(inner-boundary)*fraction,kept);kept=q.kept;removed.push(...q.removed);}return {kept,removed};}
  function peeledArea(fraction){let x0=box.minX,x1=box.maxX,z0=box.minZ,z1=box.maxZ;for(const [axis,side]of pattern){const dim=axis==='x'?'w':'d',boundary=side>0?(axis==='x'?box.maxX:box.maxZ):(axis==='x'?box.minX:box.minZ),inner=peak[axis]+side*peak[dim]/2,line=boundary+(inner-boundary)*fraction;if(axis==='x'){if(side>0)x1=line;else x0=line;}else{if(side>0)z1=line;else z0=line;}}return sum(bs,b=>b.w*b.d-Math.max(0,Math.min(x1,b.x+b.w/2)-Math.max(x0,b.x-b.w/2))*Math.max(0,Math.min(z1,b.z+b.d/2)-Math.max(z0,b.z-b.d/2)));}
  // Reuse the same fallback cuts as strength increases; a larger target must not
  // skip a previously feasible, more substantial peel merely due to rounding.
  for(const share of [...new Set([targetShare,.45,.4,.35,.3,.25,.2,.15,.1,.05,.025].filter(s=>s<=targetShare+1e-9))]){
   let a=0,b=1;for(let i=0;i<27;i++){const m=(a+b)/2;if(peeledArea(m)<area*share)a=m;else b=m;}
   const q=peel(b),actual=sum(q.removed,p=>p.w*p.d)/area;
   if(actual<.025-1e-7||!q.removed.length||!q.kept.some(b=>b.id===peak.id&&Math.abs(b.w-peak.w)<1e-6&&Math.abs(b.d-peak.d)<1e-6)||components(q.kept).length!==1||levels(q.kept)<2||q.kept.some(b=>Math.min(b.w,b.d)<1)||actual>targetShare+1e-6)continue;
   const key=q.removed.map(b=>[b.id,b.x,b.z,b.w,b.d,b.h].join(',')).join('|');if(seen.has(key))continue;seen.add(key);
   if(Math.abs(unionArea(q.kept)+sum(q.removed,b=>b.w*b.d)-area)>.001)continue;
   options.push({...q,partial:true,share:actual,score:sum(q.removed,b=>b.w*b.d*b.h)});
  }
 }
 return options.sort((a,b)=>Math.abs(a.share-targetShare)-Math.abs(b.share-targetShare)||a.score-b.score);
}
function stableCubeRoot(value){let lo=0,hi=Math.max(1,value);for(let i=0;i<64;i++){const mid=(lo+hi)/2;if(mid*mid*mid<=value)lo=mid;else hi=mid;}return (lo+hi)/2;}
function compactPieces(bs,limit=24,maxPieces=64){
 limit=Math.min(24,limit);if(!Number.isFinite(limit)||limit<=0)return null;
 const out=[];
 for(const b of bs){
  const V=b.w*b.d*b.h,r=1+.35*hash(b.id+'compact-proportion')/4294967295,n=Math.max(1,Math.ceil(V/(r*limit**3)-1e-12));
  if(out.length+n>maxPieces)return null;
  // Basic IEEE arithmetic gives the same cube root on both browser and Node,
  // including native-root rounding boundaries that decimal rounding cannot fix.
  const w=stableCubeRoot(V/(n*r)),h=r*w;
  for(let i=0;i<n;i++)out.push({...b,id:b.id+'/compact-'+n+'-'+i,sourceColumn:b.sourceColumn||b.id,splitFrom:b.splitFrom||b.id,w,d:w,h,top:b.y+h,fragmented:true,compact:true,sourceVolume:V/n,proportion:r});
 }
 return out;
}
function clusterPieces(bs){
 const columns=Math.ceil(Math.sqrt(bs.length)),rows=[];let z=0;
 for(let i=0;i<bs.length;i+=columns){const row=bs.slice(i,i+columns),depth=Math.max(...row.map(b=>b.d));let x=0;
  for(const b of row){rows.push({...b,x:x+b.w/2,z:z+depth/2});x+=b.w+2;}z+=depth+2;
 }return rows;
}
function conservationPass(q){return q.kind==='split'?Number.isFinite(q.volumeBefore)&&Number.isFinite(q.volumeAfter)&&Math.abs(q.volumeAfter-q.volumeBefore)<=Math.max(.001,q.volumeBefore*1e-9):Math.abs(q.after-q.before)<=Math.max(.02,q.before*.0001);}
function cacheMatches(result,catalog,state){return !!result&&result.controlRevision===controlRevision&&result.baselineHash===catalog.baselineHash&&state.baselineHash===catalog.baselineHash&&state.controlRevision===controlRevision&&JSON.stringify(state.global)===JSON.stringify(result.state.global)&&JSON.stringify(state.units||{})===JSON.stringify(result.state.units||{})&&(state.seed??catalog.seed)===(result.state.seed??catalog.seed);}
function splitSummary(s){return '拆解达到目标 '+s.splitReached+' · 部分完成 '+s.splitPartial+' · 无法安置 '+s.splitUnplaced+'；terrace 实际拆出中位数 '+Math.round((s.terraceSplitMedian||0)*100)+'%';}

class Occupancy{constructor(){this.buckets=new Map();this.units=new Map();}cells(b){const out=[];for(let x=Math.floor((b.x-b.w/2-4)/128);x<=Math.floor((b.x+b.w/2+4)/128);x++)for(let z=Math.floor((b.z-b.d/2-4)/128);z<=Math.floor((b.z+b.d/2+4)/128);z++)out.push(x+','+z);return out;}put(id,bs){this.units.set(id,bs);for(const b of bs)for(const k of this.cells(b)){if(!this.buckets.has(k))this.buckets.set(k,new Set());this.buckets.get(k).add(id);}}remove(id){const bs=this.units.get(id)||[];for(const b of bs)for(const k of this.cells(b))this.buckets.get(k)?.delete(id);this.units.delete(id);}hits(bs,ignore,pad=2){for(const b of bs)for(const k of this.cells(b))for(const id of this.buckets.get(k)||[]){if(id===ignore)continue;if(this.units.get(id).some(q=>overlap(b,q,pad)))return true;}return false;}}
function evaluate(catalog,state){if(state.controlRevision&&!acceptsRevision(state.controlRevision))throw Error("方案使用了旧调节区间，请刷新面板后重新设置");if(state.baselineHash&&state.baselineHash!==catalog.baselineHash)throw Error('方案基线与当前模型不同');const started=typeof performance==='object'?performance.now():Date.now(),ordered=[...catalog.units].sort(rank),units=new Map(ordered.map(u=>[u.id,{...u,blocks:u.blocks,parameters:params(state,u)}])),occupancy=new Occupancy(),changes=[],notices=[],areaChecks=[],fieldUse=new Map(),placedSites=[],removed=new Set(),added=[];for(const u of units.values())occupancy.put(u.id,u.blocks);
 const neutral=p=>keys.every(k=>p[k]===.5);
 function setBlocks(u,bs,why){if(bs.length===u.blocks.length&&bs.every((b,i)=>b.id===u.blocks[i].id&&['x','z','w','d','y','h'].every(k=>Math.abs(b[k]-u.blocks[i][k])<1e-9)))return false;occupancy.remove(u.id);u.blocks=bs;occupancy.put(u.id,bs);u.changed=true;if(!u.reasons)u.reasons=[];u.reasons.push(why);return true;}
 const fieldKey=site=>site.parcel+'@'+site.parcelArea,parcelSites=new Map();
 function candidateFits(bs,site,ignore,spacing=45){const box=bounds(bs),parcel=fieldKey(site);if(box.maxX-box.minX>site.w||box.maxZ-box.minZ>site.d)return false;const area=unionArea(bs),used=fieldUse.get(parcel)||0;if(used+area>site.parcelArea*.15)return false;if((parcelSites.get(parcel)||[]).some(p=>Math.hypot(p.x-site.x,p.z-site.z)<Math.max(spacing,p.spacing??45)))return false;return !occupancy.hits(bs,ignore);}
 function moveTo(bs,site,id,b=bounds(bs)){const cx=(b.minX+b.maxX)/2,cz=(b.minZ+b.maxZ)/2;return bs.map(q=>({...q,x:q.x-cx+site.x,z:q.z-cz+site.z,y:site.y+.04,top:site.y+.04+q.h,tile:site.tile,relocated:true,site:site.id,unit:id}));}
 function fit(bs,u,ignore,extraSites){const p=u.parameters.scatter,list=[...(extraSites||u.sites||[])];list.sort((a,b)=>p>.5?b.distance-a.distance||a.id.localeCompare(b.id):a.neighbour-b.neighbour||a.distance-b.distance||a.id.localeCompare(b.id));const box=bounds(bs),w=box.maxX-box.minX,d=box.maxZ-box.minZ,area=unionArea(bs),spacing=extraSites?Math.max(12,Math.min(24,Math.max(w,d)+6)):45;for(const s of list){const slots=[s];if(u.added&&s.w>=w&&s.d>=d){const nx=Math.floor((s.w-w)/90),nz=Math.floor((s.d-d)/90);for(let j=-nz;j<=nz;j++)for(let i=-nx;i<=nx;i++){if(!i&&!j)continue;const x=s.x+i*45,z=s.z+j*45;slots.push({...s,id:s.id+'/slot-'+i+'-'+j,parentSite:s.id,x,z,w:s.w-Math.abs(i)*90,d:s.d-Math.abs(j)*90,distance:Math.hypot(x-u.center[0],z-u.center[1])});}}for(const slot of slots){const parcel=fieldKey(slot);if(w>slot.w+1e-6||d>slot.d+1e-6||(fieldUse.get(parcel)||0)+area>slot.parcelArea*.15+1e-6||(parcelSites.get(parcel)||[]).some(p=>Math.hypot(p.x-slot.x,p.z-slot.z)<Math.max(spacing,p.spacing??45)))continue;const moved=moveTo(bs,slot,u.id,box);if(moved.every(b=>Math.hypot(b.x-u.center[0],b.z-u.center[1])<=(u.limit||150)+1e-7)&&candidateFits(moved,slot,ignore,extraSites?Math.max(12,Math.min(24,Math.max(w,d)+6)):45))return {blocks:moved,site:extraSites?{...slot,spacing:Math.max(12,Math.min(24,Math.max(w,d)+6))}:slot};}}return null;}
 function reserve(site,bs){const parcel=fieldKey(site);fieldUse.set(parcel,(fieldUse.get(parcel)||0)+unionArea(bs));const record={...site,sourceParcel:site.parcel,parcel,area:unionArea(bs)};placedSites.push(record);if(!parcelSites.has(parcel))parcelSites.set(parcel,[]);parcelSites.get(parcel).push(record);}
 // Counts operate on complete units, with fixed per-settlement order.
 const quantityTargets={small:catalog.metrics.small,terrace:catalog.metrics.terrace};
 const buckets=new Map();for(const u of ordered){if(u.protected)continue;const key=u.settlement+'|'+u.type;if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(units.get(u.id));}
 for(const list of buckets.values()){const type=list[0].type,key=type==='terrace'?'terraceCount':'smallCount',targets=new Map();for(const u of list){const p=u.parameters[key];if(p===.5)continue;const k=p.toFixed(4);if(!targets.has(k))targets.set(k,[]);targets.get(k).push(u);}for(const subset of targets.values()){const p=subset[0].parameters[key],amount=Math.round(subset.length*Math.abs(factor(key,p)-1));quantityTargets[type]+=p<.5?-amount:amount;if(p<.5)for(const u of subset.slice(0,amount)){removed.add(u.id);occupancy.remove(u.id);u.changed=true;u.reasons=['quantity'];u.blocks=[];}else for(let i=0,made=0,lastRoundMade=0;i<subset.length*Math.max(1,Math.ceil(amount/subset.length)+1)&&made<amount;i++){if(i&&i%subset.length===0){if(made===lastRoundMade)break;lastRoundMade=made;}const source=subset[i%subset.length],u={...source,id:source.id+'/added-'+i,blocks:clone(source.blocks),added:true,changed:true,reasons:['quantity']};u.maxScale=2;u.preScale=factor((u.type==='terrace'?'terrace':'small')+'Size',u.parameters[(u.type==='terrace'?'terrace':'small')+'Size']);const origin=center(u.blocks);u.blocks=u.blocks.map((b,j)=>({...b,id:u.id+'/part-'+j,sourceColumn:b.id,x:origin[0]+(b.x-origin[0])*u.preScale,z:origin[1]+(b.z-origin[1])*u.preScale,w:b.w*u.preScale,d:b.d*u.preScale}));const fitResult=fit(u.blocks,u);if(!fitResult){notices.push({id:u.id,reason:'没有足够大的安全田间落点'});continue;}u.blocks=fitResult.blocks;const placementBounds=bounds(u.blocks);u.maxScale=Math.min(u.maxScale||2,fitResult.site.w/(placementBounds.maxX-placementBounds.minX)*u.preScale,fitResult.site.d/(placementBounds.maxZ-placementBounds.minZ)*u.preScale);reserve(fitResult.site,u.blocks);occupancy.put(u.id,u.blocks);units.set(u.id,u);added.push(u.id);made++;}}}
 // Only the latest accepted relocation has a reversible source position.
 for(const record of catalog.returns||[]){const members=[...new Set(record.parts.map(b=>catalog.blockUnits[b.id]))].map(id=>units.get(id));if(members.some(u=>!u||u.protected||removed.has(u.id)))continue;const p=Math.max(...members.map(u=>u.parameters.split));if(p>=.5||record.rank>=1-2*p)continue;const proposals=new Map();for(const item of record.parts){const u=units.get(catalog.blockUnits[item.id]);if(!proposals.has(u.id))proposals.set(u.id,clone(u.blocks));const b=proposals.get(u.id).find(b=>b.id===item.id);if(b){b.x=item.x;b.z=item.z;b.y=item.y;b.top=item.y+b.h;b.tile=item.tile;b.returned=true;}}
 for(const u of members)occupancy.remove(u.id);let valid=true;const local=[];for(const bs of proposals.values()){if(occupancy.hits(bs,undefined,0))valid=false;for(const b of bs)if(local.some(q=>overlap(b,q)))valid=false;local.push(...bs);}if(valid){for(const [id,bs]of proposals)setBlocks(units.get(id),bs,'return');areaChecks.push({id:record.id,kind:'return',before:record.area,after:unionArea(local)});}else notices.push({id:record.id,reason:'原处已被其他调整占用，保留现有拆分'});for(const u of members)if(!occupancy.units.has(u.id))occupancy.put(u.id,u.blocks);}
 // Sizes and roof heights always start from the immutable input for this evaluation.
 for(const u of units.values()){if(u.protected||removed.has(u.id))continue;const p=u.parameters,type=u.type==='terrace'?'terrace':'small',s=factor(type+'Size',p[type+'Size']),v=factor(type+'Height',p[type+'Height']),delta=type==='terrace'?factor('terraceLevels',p.terraceLevels):0;if(s===1&&v===1&&!delta)continue;const effectiveScale=Math.min(s,u.maxScale||2),actualScale=effectiveScale/(u.preScale||1),c=center(u.blocks);let bs=changeLevels(u.blocks,delta).map(b=>({...b,x:c[0]+(b.x-c[0])*actualScale,z:c[1]+(b.z-c[1])*actualScale,w:b.w*actualScale,d:b.d*actualScale,h:b.h*v,top:b.y+b.h*v}));if(effectiveScale!==s)notices.push({id:u.id,reason:'宽深已到安全边界'});if(actualScale!==1&&occupancy.hits(bs,u.id)){bs=changeLevels(u.blocks,delta).map(b=>({...b,h:b.h*v,top:b.y+b.h*v}));notices.push({id:u.id,reason:'相邻建筑限制了宽深调整'});}setBlocks(u,bs,'shape');u.actualScale=effectiveScale;}

 // Preserve the adjusted source volume; reserve the actual compact footprints.
 const splitReports=[];
 const candidates=[...units.values()].filter(u=>!u.protected&&!removed.has(u.id)&&canSplit(u.blocks,minimumArea(u.parameters.splitMinArea))),eligible=candidates.filter(u=>u.parameters.split>.5).sort((a,b)=>(b.type==='terrace')-(a.type==='terrace')||rank(a,b)),splitQuota=Math.round(sum(eligible,u=>factor('split',u.parameters.split)));let splitDone=0;
 for(const u of eligible){
  if(splitDone>=splitQuota)break;
  const before=unionArea(u.blocks),volumeBefore=volume(u.blocks),isTerrace=u.type==='terrace',t=factor('split',u.parameters.split),targetShare=isTerrace?.15+.30*t:.12+.10*t;
  const splitSites=[...(u.sites||[]),...(u.splitSites||[])],maxSize=Math.min(24,Math.max(0,...splitSites.map(s=>Math.min(s.w,s.d)))),sizes=[...new Set([maxSize,18,12,8].filter(s=>s>0&&s<=maxSize))];
  const cuts=splitSites.length?(isTerrace?terraceCuts(u.blocks,minimumArea(u.parameters.splitMinArea),targetShare):cutOptions(u.blocks,minimumArea(u.parameters.splitMinArea),targetShare)):[];
  let chosen=null;const planShapes=new Set();
  for(const cut of cuts){
   for(const size of sizes){
    const pieces=compactPieces(cut.removed,size);if(!pieces)continue;
    const signature=JSON.stringify([cut.kept.map(b=>[b.id,b.x,b.z,b.w,b.d,b.h]),pieces.map(b=>[b.id,b.w,b.d,b.h])]);if(planShapes.has(signature))continue;planShapes.add(signature);
    const moved=[],sites=[],temp=[];occupancy.remove(u.id);occupancy.put(u.id,cut.kept);let valid=true;
    for(let i=0;i<pieces.length;){let found=null,n=0;
     for(const count of new Set([Math.min(16,pieces.length-i),16,12,9,8,6,4,3,2,1])){if(i+count>pieces.length)continue;const bs=clusterPieces(pieces.slice(i,i+count));found=fit(bs,u,undefined,splitSites);if(found){n=count;break;}}
     if(!found){valid=false;break;}
     const id=u.id+'/temporary-'+i;occupancy.put(id,found.blocks);temp.push(id);moved.push(...found.blocks);sites.push(found);reserve(found.site,found.blocks);i+=n;
    }
    for(const id of temp)occupancy.remove(id);occupancy.remove(u.id);occupancy.put(u.id,u.blocks);
    if(valid){const kept=cut.kept.map(b=>({...b,fragmented:true})),bs=[...kept,...moved],volumeAfter=volume(bs),removedArea=unionArea(cut.removed),actualShare=removedArea/before;
     const check={id:u.id,kind:'split',before,after:unionArea(bs),volumeBefore,volumeAfter,removedArea,movedArea:unionArea(moved),movedBlocks:moved.length,targetShare,actualShare};
     if(conservationPass(check)){chosen={bs,check};break;}
    }
    for(const item of sites){fieldUse.set(fieldKey(item.site),fieldUse.get(fieldKey(item.site))-unionArea(item.blocks));const index=placedSites.findIndex(s=>s.id===item.site.id);if(index>=0){const record=placedSites.splice(index,1)[0],bucket=parcelSites.get(record.parcel),local=bucket.indexOf(record);if(local>=0)bucket.splice(local,1);}}
   }
   if(chosen)break;
  }
  if(chosen){setBlocks(u,chosen.bs,'split');u.split=true;splitDone++;areaChecks.push(chosen.check);const status=chosen.check.actualShare+1e-5>=targetShare?'reached':'partial';splitReports.push({id:u.id,type:u.type,status,...chosen.check});if(status==='partial')notices.push({id:u.id,reason:'拆解部分完成：附近空地或核心轮廓限制了外围切口',actualShare:chosen.check.actualShare,targetShare});}
  else{splitReports.push({id:u.id,type:u.type,status:'unplaced',targetShare,actualShare:0,reason:!splitSites.length?'no-sites':!cuts.length?'core-shape':'placement-capacity'});notices.push({id:u.id,reason:!splitSites.length?'拆解附近没有安全落点':!cuts.length?'拆解需保留连通核心和退台层次':'拆解后没有足够安全落点'});}
 }
 // Existing detached houses enter a stable subset rather than being reshuffled.
 for(const u of [...units.values()].sort(rank)){if(u.protected||removed.has(u.id)||u.split||u.reasons?.includes('return')||u.type==='terrace'&&!u.added)continue;const p=u.parameters.scatter;if(p===.5)continue;const field=u.field||u.added,threshold=Math.abs(p-.5)*2*(field?1:.30);if((hash(u.id+'scatter')/4294967296)>=threshold)continue;const before=unionArea(u.blocks),found=fit(u.blocks,u,u.id);if(!found){notices.push({id:u.id,reason:'附近没有符合当前尺寸的落点'});continue;}if(u.added){/* Initial site remains reserved conservatively for this evaluation. */}setBlocks(u,found.blocks,'scatter');reserve(found.site,u.blocks);areaChecks.push({id:u.id,kind:'scatter',before,after:unionArea(u.blocks)});}
 const baselineMap=new Map(catalog.units.map(u=>[u.id,u])),output=[...units.values()];for(const u of output){if(u.changed||u.parameters.lod!==.5&&!u.protected)changes.push({id:u.id,owner:u.owner,type:u.type,added:!!u.added,removed:removed.has(u.id),reasons:u.reasons||['lod'],blocks:u.blocks,parameters:u.parameters,levelsBefore:baselineMap.get(u.id)?.levels||0,levelsAfter:levels(u.blocks)});}
 const active=output.filter(u=>u.blocks.length),beforeArea=catalog.metrics.area;
 function measures(u){if(!u.changed)return [u.area,u.volume];const p=u.parameters,type=u.type==='terrace'?'terrace':'small',delta=type==='terrace'?factor('terraceLevels',p.terraceLevels):0,v=factor(type+'Height',p[type+'Height']),area=unionArea(u.blocks);return [area,delta||u.split?volume(u.blocks):u.volume*(area/u.area)*v];}
 const measured=active.map(measures),afterArea=sum(measured,m=>m[0]),afterVolume=sum(measured,m=>m[1]);
 const terraceShares=splitReports.filter(r=>r.type==='terrace'&&r.status!=='unplaced').map(r=>r.actualShare).sort((a,b)=>a-b);
 return {version:1,controlRevision,baselineHash:catalog.baselineHash,state:{...clone(state),controlRevision},changes,areaChecks,splitReports,sites:placedSites,notices,stats:{small:active.filter(u=>u.type==='small').length,terrace:active.filter(u=>u.type==='terrace').length,blocks:sum(active,u=>u.blocks.length),changed:changes.length,added:added.length,removed:removed.size,split:splitDone,splitReached:splitReports.filter(r=>r.status==='reached').length,splitPartial:splitReports.filter(r=>r.status==='partial').length,splitUnplaced:splitReports.filter(r=>r.status==='unplaced').length,terraceSplit:terraceShares.length,terraceSplitMedian:terraceShares.length?terraceShares[Math.floor(terraceShares.length/2)]:0,splitRequested:splitQuota,splitEligible:eligible.length,splitCandidates:candidates.length,splitThresholdM2:minimumArea(state.global?.splitMinArea),splitThresholdsM2:[...new Set([...units.values()].filter(u=>!u.protected&&!removed.has(u.id)).map(u=>minimumArea(u.parameters.splitMinArea)))].sort((a,b)=>a-b),smallRequested:quantityTargets.small,terraceRequested:quantityTargets.terrace,area:afterArea,areaDelta:afterArea-beforeArea,volume:afterVolume,volumeDelta:afterVolume-catalog.metrics.volume,elapsedMs:(typeof performance==='object'?performance.now():Date.now())-started},neutral:changes.length===0};
}
return {keys,controlRevision,acceptsRevision,defaults,factor,splitArea,minimumArea,canSplit,params,evaluate,unionArea,volume,bounds,center,components,levels,overlap,hash,rank,cutOptions,smallerPieces,terraceCuts,compactPieces,clusterPieces,conservationPass,cacheMatches,splitSummary};
});
