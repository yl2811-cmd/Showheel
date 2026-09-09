/* Shared layered floor samples; visible movable objects retain their own collision. */
(()=>{'use strict';
 function create({T,N,isSmallVisible}){
  const o=N?.outdoor,maps=(o?.layerTiles||[o?.tiles||{}]).map(tiles=>new Map(Object.entries(tiles).map(([id,raw])=>{const b=atob(raw),a=new Uint8Array(b.length);for(let i=0;i<b.length;i++)a[i]=b.charCodeAt(i);return[id,new Int16Array(a.buffer)];}))),bins=new Map();
  const hull=pts=>{pts.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);const lo=[],hi=[];for(const p of pts){while(lo.length>1&&cross(lo[lo.length-2],lo[lo.length-1],p)<=0)lo.pop();lo.push(p);}for(const p of [...pts].reverse()){while(hi.length>1&&cross(hi[hi.length-2],hi[hi.length-1],p)<=0)hi.pop();hi.push(p);}lo.pop();hi.pop();return lo.concat(hi);};
  for(const a of o?.props||[]){const c=a.collision,off=c.offset||[0,0,0],q=a.quaternion?new T.Quaternion(...a.quaternion):new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),a.rotation||0),points=[];let y0=Infinity,y1=-Infinity;
   for(const x of[-c.width/2,c.width/2])for(const z of[-c.depth/2,c.depth/2])for(const y of[0,c.height]){const p=new T.Vector3(x+off[0],y+off[1],z+off[2]).applyQuaternion(q).add(new T.Vector3(...a.position));points.push([p.x,p.z]);y0=Math.min(y0,p.y);y1=Math.max(y1,p.y);}const poly=hull(points),xs=points.map(p=>p[0]),zs=points.map(p=>p[1]),v={id:a.id,poly,y0,y1};
   for(let x=Math.floor((Math.min(...xs)-.2)/4);x<=Math.floor((Math.max(...xs)+.2)/4);x++)for(let z=Math.floor((Math.min(...zs)-.2)/4);z<=Math.floor((Math.max(...zs)+.2)/4);z++){const k=x+','+z;if(!bins.has(k))bins.set(k,[]);bins.get(k).push(v);}
  }
  function inside(poly,x,z){let hit=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])hit=!hit;}return hit;}
  function distance(poly,x,z){if(inside(poly,x,z))return 0;let d=Infinity;for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],dx=b[0]-a[0],dz=b[1]-a[1],t=Math.max(0,Math.min(1,((x-a[0])*dx+(z-a[1])*dz)/(dx*dx+dz*dz||1)));d=Math.min(d,Math.hypot(x-a[0]-dx*t,z-a[1]-dz*t));}return d;}
  function blocked(x,y,z){return isSmallVisible()&&(bins.get(Math.floor(x/4)+','+Math.floor(z/4))||[]).some(v=>v.y1>y+.32&&v.y0<y+1.72&&distance(v.poly,x,z)<.18);}
  function outdoor(x,z,old){if(!o)return null;const i=Math.floor((x-o.origin[0])/o.step),j=Math.floor((z-o.origin[1])/o.step);if(i<0||j<0||i>=o.size||j>=o.size)return null;const id=Math.floor(i/o.tileSize)+'_'+Math.floor(j/o.tileSize),index=(j%o.tileSize)*o.tileSize+i%o.tileSize,ys=[];for(const map of maps){const y=map.get(id)?.[index];if(y!==undefined&&y!==-32768&&Math.abs(y/100-old)<=N.maxStep+.2&&!blocked(x,y/100,z))ys.push(y/100);}return ys.length?ys.sort((a,b)=>Math.abs(a-old)-Math.abs(b-old))[0]:null;}
  return{outdoor,blocked};
 }
 window.EYRIE_WALKING={create};
})();
