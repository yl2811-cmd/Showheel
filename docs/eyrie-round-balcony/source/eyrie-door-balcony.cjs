'use strict';
// Final authored changes are replayed after the accepted shell and path finishes.
const fs=require('fs'),path=require('path'),vm=require('vm');
const {Surface,readSurface}=require('./eyrie-neighbour-comfort.cjs');
function build({field,mesh,C,P,parts,palette,OUT,site:S,hash}){
 const M=JSON.parse(fs.readFileSync(path.join(OUT,'manifest.json')));if(M.doorBalcony?.revision===1)return M;
 if(JSON.stringify(palette)!==JSON.stringify(M.palette))throw Error('Palette changed');
 const first=parts.length,ctx={window:{}};vm.runInNewContext(fs.readFileSync(path.join(OUT,'navigation.js'),'utf8'),ctx);const N=ctx.window.EYRIE_NAVIGATION;
 const report={revision:1,sourceBuild:M.buildId,edited:[],removedInstances:[],removedSolar:[],doors:[],guards:[]};
 const part=id=>{const p=M.parts.find(p=>p.id===id);if(!p)throw Error('Missing '+id);return p;};
 const interpolate=(a,b,t)=>Object.fromEntries(['p','n','c','s'].map(k=>[k,a[k].map((v,i)=>v+(b[k][i]-v)*t)]));
 function split(poly,axis,bound,sign){const inside=[],outside=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],da=(a.p[axis]-bound)*sign,db=(b.p[axis]-bound)*sign,ai=da>=-1e-8,bi=db>=-1e-8;(ai?inside:outside).push(a);if(ai!==bi){const q=interpolate(a,b,da/(da-db));inside.push(q);outside.push(q);}}return{inside,outside};}
 function cut(id,box){const p=part(id),g=readSurface(path.join(OUT,p.file),palette),o=new Surface(palette);let changed=0;
  function emit(poly){for(let i=1;i<poly.length-1;i++){const vs=[poly[0],poly[i],poly[i+1]],a=vs[1].p.map((v,k)=>v-vs[0].p[k]),b=vs[2].p.map((v,k)=>v-vs[0].p[k]);if(Math.hypot(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])<1e-8)continue;for(const v of vs){o.ix.push(o.v.length);o.v.push(v);}}}
  for(let i=0;i<g.ix.length;i+=3){const vs=g.ix.slice(i,i+3).map(k=>g.v[k]);if([0,1,2].some(k=>vs.every(v=>v.p[k]<box[k]-1e-7)||vs.every(v=>v.p[k]>box[k+3]+1e-7))){emit(vs);continue;}let remaining=vs;for(const [axis,bound,sign]of [[0,box[0],1],[0,box[3],-1],[1,box[1],1],[1,box[4],-1],[2,box[2],1],[2,box[5],-1]]){if(remaining.length<3)break;const q=split(remaining,axis,bound,sign);emit(q.outside);remaining=q.inside;}if(remaining.length>=3)changed++;}
  o.write(OUT,p);report.edited.push({id,cut:box,trianglesCut:changed});
 }
 function removeInstance(predicate){const removed=M.instances.filter(predicate);M.instances=M.instances.filter(a=>!predicate(a));report.removedInstances.push(...removed.map(a=>a.id));const ids=new Set(removed.map(a=>a.id));N.outdoor.props=N.outdoor.props.filter(a=>!ids.has(a.id));return removed;}
 // One circular upper deck. The two lower flights keep their original meshes.
 const owner='north-grain',c=M.survey.expansion.compounds.find(c=>c.id===owner),center=[-37.76,-87.72],radius=5.8,Y=10.5;
 cut('exp-north-grain-floors',[-100,7.251,-150,0,30,0]);
 cut('exp-north-grain-supports',[-100,7.0,-150,0,30,0]);
 const removedRails=removeInstance(a=>{
  if(a.owner!==owner||a.lodGroup!==owner+'-rails')return false;
  if(a.position[1]>10.49)return true;
  const q=a.quaternion||[0,0,0,1],tilted=Math.abs(q[0])+Math.abs(q[2])>.015;
  if(tilted&&a.position[1]>8.5)return true;
  const x=a.position[0],z=a.position[2],stairY=7.25+(z+91.5)/5.2*3.25;
  return !tilted&&[-30.82,-28.58].some(v=>Math.abs(v-x)<.015)&&z>=-91.51&&z<=-86.29&&Math.abs(a.position[1]-(stairY+.5))<.015;
 });
 const deck=field('round-upper-balcony',.125,'outdoor-floor',0);deck.meta={compound:owner,collisionSource:true};
 deck.fill([center[0]-radius,Y-.25,center[1]-radius,center[0]+radius,Y,center[1]+radius],(x,y,z)=>Math.hypot(x-center[0],z-center[1])<=radius,(x,y,z)=>P.honeyWood[Math.min(P.honeyWood.length-1,Math.floor(S.noise(x*.17,z*.17)*P.honeyWood.length))]);mesh(deck);
 const rails=field('round-upper-balcony-rails',.0625,'outdoor-solid',0),support=field('round-upper-balcony-knees',.125,'outdoor-solid',0);rails.meta={compound:owner,collisionSource:true};support.meta={compound:owner,collisionSource:true};
 function guard(points,y,label){for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i],len=Math.hypot(b[0]-a[0],b[1]-a[1]);for(const h of[.50,1.1])rails.beam([a[0],y+h,a[1]],[b[0],y+h,b[1]],h>1?.09:.075,h>1?P.weatheredWood[1]:P.fiber[0]);rails.box(a[0],y+.55,a[1],.17,1.1,.17,P.fiber[0]);N.outdoor.props.push({id:'round-guard-'+label+'-'+i,position:[(a[0]+b[0])/2,y,(a[1]+b[1])/2],rotation:Math.atan2(-(b[1]-a[1]),b[0]-a[0]),layer:'outdoor-solid',collision:{kind:'prop',width:len+.1,depth:.18,height:1.1}});}report.guards.push({label,points,y});}
 const ring=Array.from({length:33},(_,i)=>{const a=i*Math.PI/16;return[center[0]+5.63*Math.cos(a),center[1]+5.63*Math.sin(a)];});guard(ring,Y,'circle');
 // Close the obsolete start of the final flight on the lower gallery.
 guard([[-30.89,-91.67],[-28.51,-91.67]],7.25,'old-stair-start');
 for(let i=0;i<12;i++){const a=i*Math.PI/6,point=(r,y)=>[center[0]+r*Math.cos(a),y,center[1]+r*Math.sin(a)];support.beam(point(3.55,8.05),point(5.5,10.15),.15,P.fiber[1]);support.beam(point(3.55,10.12),point(5.5,10.12),.17,P.fiber[0]);}mesh(rails);mesh(support);
 const retiredSurface=id=>id==='north-grain-gallery-3'||id.startsWith('north-grain-stair-3');
 c.stairs=c.stairs.filter(s=>s.id!=='north-grain-stair-3');const poly=ring.slice(0,-1).map(p=>p.map((v,k)=>center[k]+(v-center[k])*radius/5.63));Object.assign(c.decks[3],{polygon:poly,holes:[],shape:'circle',radius,center,access:'room-door-only'});
 for(const key of['surfaces','clearanceVolumes']){M.survey[key]=M.survey[key].filter(s=>!retiredSurface(s.id)&&s.id!=='north-grain-gallery-open-3');if(M.survey.expansion[key])M.survey.expansion[key]=M.survey.expansion[key].filter(s=>!retiredSurface(s.id)&&s.id!=='north-grain-gallery-open-3');}
 for(const list of[M.survey.surfaces,M.survey.expansion.surfaces||[]]){const d=list.find(s=>s.id==='north-grain-deck-3');if(d)Object.assign(d,JSON.parse(JSON.stringify(c.decks[3])));}
 report.balcony={owner,center,radius,y:Y,removedStair:'north-grain-stair-3',retainedStairs:c.stairs.map(s=>s.id),removedRailInstances:removedRails.length};
 // Move the rain barrel and all of its plinth behind the west door.
 require('./eyrie-details.cjs')({round:11,field,mesh:f=>{if(f.name==='water-heat')mesh(f);},C,hash,grain:()=>C.wood});
 const feet=field('repair-cistern-footings',.1,'structure',0),cx=-10.05,cz=-9.1;
 N.outdoor.props=N.outdoor.props.filter(a=>!a.id.startsWith('repair-cistern-pier-'));
 for(const z of[cz-.68,cz+.67]){const ground=S.bare(cx,z);feet.box(cx,(ground+1.54)/2,z,.55,1.54-ground,.55,P.basalt[1]);feet.box(cx,1.64,z,.85,.25,.80,P.basalt[3]);N.outdoor.props.push({id:'repair-cistern-pier-'+z,position:[cx,ground,z],rotation:0,layer:'structure',collision:{kind:'prop',width:.6,depth:.6,height:1.77-ground}});}mesh(feet);
 report.cistern={from:[cx,-5.8],to:[cx,cz],clearanceToWestDoor:2.51};
 // Enlarge the marked front bay door and open the landward rear wall.
 const doors=[{id:'home-bay',position:[6.5,0,7.2],rotation:0,w:3.8,h:2.75,double:true,angles:[1.5,2.35]}, {id:'home-back',position:[7.5,0,-3],rotation:Math.PI,w:1.65,h:2.45,angles:[1.45]}];
 for(const d of doors){const [x,y,z]=d.position;cut('walls-0',[x-d.w/2,-.02,z-.4,x+d.w/2,d.h,z+.4]);}
 cut('repair-door-surrounds',[4.85,-.2,6.9,8.15,3.0,7.5]);
 const oldDoors=new Set(['repair-door-home-bay-0','repair-door-home-bay-1']);removeInstance(a=>oldDoors.has(a.id));M.residential.doors=M.residential.doors.filter(a=>!oldDoors.has(a.id));M.structureRepair.doors=M.structureRepair.doors.filter(a=>!oldDoors.has(a.id));
 // Exact wall reveal strips close the new cut edges without covering the opening.
 const trim=field('entry-door-joinery',.05,'details',0),sill=field('back-door-stones',.0625,'outdoor-floor',0),prototype='residential-door-1.4-2.32-false-0';
 function local(d,x,y,z){const c=Math.cos(d.rotation),s=Math.sin(d.rotation);return[d.position[0]+x*c+z*s,d.position[1]+y,d.position[2]-x*s+z*c];}
 for(const d of doors){for(const x of[-d.w/2-.075,d.w/2+.075]){const p=local(d,x,d.h/2,0);trim.box(...p,.15,d.h+.1,.5,C.beam);}trim.box(...local(d,0,d.h+.075,0),d.w+.40,.18,.50,C.wood);trim.box(...local(d,0,.025,0),d.w+.20,.05,.65,C.board);
  const n=d.double?2:1,w=d.w/n-.045,h=d.h-.1;for(let i=0;i<n;i++){const mirror=i===1,position=local(d,mirror?d.w/2-.025:-d.w/2+.025,0,.02),angle=d.angles[i],rotation=d.rotation+(mirror?Math.PI-angle:angle),id='repair-door-'+d.id+'-'+i,record={id,prototype,position,rotation,scale:1,scale3:[w/1.375,h/2.3125,1],owner:'eyrie-home',residential:true,door:true,maxDistance:430,minDistance:0,collision:{kind:'prop',width:w,depth:.24,height:h,offset:[w/2,0,0]}};M.instances.push(record);N.outdoor.props.push({...record,layer:'outdoor-solid'});const desc={id,owner:'eyrie-home',room:d.id,opening:{position:d.position,normal:[Math.sin(d.rotation),0,Math.cos(d.rotation)],width:d.w,height:d.h,kind:'door'},prototype,position,rotation,state:'inward',angle,width:w,height:h,thickness:.18};M.residential.doors.push(desc);report.doors.push(desc);}
 }
 mesh(trim);
 // Three shallow stones meet the actual turf outside the rear doorway.
 report.rearSteps=[];for(const [i,z]of[-3.25,-3.65,-4.05].entries()){const top=[.1875,.4375,.375][i],bottom=-.125;sill.box(7.5,(top+bottom)/2,z,1.95-i*.1,top-bottom,.55,P.rock[2+i]);report.rearSteps.push({z,top,width:1.95-i*.1});}mesh(sill);
 // All solar-specific meshes include their dedicated posts, glass and wiring.
 const solarIds=new Set(M.parts.filter(p=>p.solar||/^solar-/.test(p.id)).map(p=>p.id));report.removedSolar=[...solarIds];M.parts=M.parts.filter(p=>!solarIds.has(p.id));removeInstance(a=>solarIds.has(a.prototype)||/solar-panel|roof-solar|solar-film/.test(a.prototype));
 // The inset film strips give way to matching roof courses, including the near and far views.
 for(const id of['press-east','herbs-east','linen-east']){const h=M.survey.households.find(h=>h.id===id),v=h.volumes[0],a=M.instances.find(a=>a.id===id+'-near'),f=field('roof-course-'+id,.1,'neighbour',0),mat=P.archProfiles[id];f.meta={prototype:true,owner:id};
  function roof(x,z){let a=(x-v.cx)/(v.w/2+.7),b=(z-v.cz)/(v.d/2+.7);if(v.axis==='z')[a,b]=[b,a];let q=v.roof==='shed'?S.clamp(.55-b*.44,.05,1):v.roof==='barrel'?Math.pow(Math.max(0,1-a*a),.64):v.roof==='hip'?Math.max(0,Math.min(1-Math.abs(a),1-Math.abs(b))):v.roof==='halfhip'?Math.max(0,Math.min(1-Math.abs(a),1.5-Math.abs(b))):1-Math.abs(a);return v.h+Math.max(0,q)*v.rise;}
  f.fill([v.cx,v.h-.3,v.cz-v.d*.34,v.cx+v.w*.46,v.h+v.rise+.3,v.cz+v.d*.34],(x,y,z)=>require('./eyrie-solar.cjs').roofPatchContains(h,v,x,z)&&y>roof(x,z)-.125&&y<roof(x,z)+(id==='linen-east'?0:.14*(1-(z/.6-Math.floor(z/.6)))),(x,y,z)=>mat.roof[Math.min(mat.roof.length-1,Math.floor(S.noise(Math.floor(x/.7)*.37+4,Math.floor(z/.6)*.37+19)*mat.roof.length))]);mesh(f);M.instances.push({id:f.name,prototype:f.name,position:a.position,rotation:a.rotation,scale:1,owner:id,minDistance:0,maxDistance:430});
 }
 N.outdoor.props=N.outdoor.props.filter(a=>!/^solar-post-/.test(a.id));M.survey.occupiedVolumes=M.survey.occupiedVolumes.filter(v=>v.kind!=='solar-post');
 report.previousSolarArea=M.solarArchitecture.netArea;M.solarArchitecture={revision:M.solarArchitecture.revision,disabled:true,reason:'Author removed solar panels from this scene.',entries:[],patches:[],clearPatches:[],supports:[],wires:[],drains:[],netArea:0};
 if(M.mechanicalSystems){M.mechanicalSystems.systems=M.mechanicalSystems.systems.filter(s=>s.type!=='solar');M.mechanicalSystems.solarTerminals=[];}
 for(const r of[M.survey.expansion.lifeReport,M.livingAssets?.expansion].filter(Boolean))if(r.systems)r.systems=r.systems.filter(s=>s.type!=='solar');
 // Shared wall collision rectangles yield to the same openings as the visible wall.
 const newProps=[];for(const a of N.outdoor.props){if(!a.id.startsWith('repair-wall-')){newProps.push(a);continue;}let boxes=[[a.position[0]-a.collision.width/2,a.position[2]-a.collision.depth/2,a.position[0]+a.collision.width/2,a.position[2]+a.collision.depth/2]];for(const d of doors){const x0=d.position[0]-d.w/2,x1=d.position[0]+d.w/2,z0=d.position[2]-.4,z1=d.position[2]+.4;boxes=boxes.flatMap(b=>{const l=Math.max(b[0],x0),r=Math.min(b[2],x1),t=Math.max(b[1],z0),u=Math.min(b[3],z1);if(l>=r||t>=u)return[b];return[[b[0],b[1],l,b[3]],[r,b[1],b[2],b[3]],[l,b[1],r,t],[l,u,r,b[3]]].filter(q=>q[2]-q[0]>.0001&&q[3]-q[1]>.0001);});}for(const [i,b]of boxes.entries())newProps.push({...a,id:a.id+'-entry-'+i,position:[(b[0]+b[2])/2,a.position[1],(b[1]+b[3])/2],collision:{...a.collision,width:b[2]-b[0],depth:b[3]-b[1]}});}N.outdoor.props=newProps;
 for(let j=0;j<N.height;j++)for(let i=0;i<N.width;i++){const x=N.origin[0]+(i+.5)*N.step,z=N.origin[1]+(j+.5)*N.step;if(doors.some(d=>Math.abs(x-d.position[0])<d.w/2-.20&&Math.abs(z-d.position[2])<.7))N.layers[0][j*N.width+i]=0;}
 // Update only the outdoor samples affected by the retired stair, ring and entrances.
 const o=N.outdoor,decode=map=>Object.fromEntries(Object.entries(map).map(([k,s])=>{const b=Buffer.from(s,'base64');return[k,new Int16Array(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength))];})),layers=[decode(o.tiles),...o.layerTiles.map(decode)];
 for(let j=0;j<o.size;j++)for(let i=0;i<o.size;i++){const x=o.origin[0]+(i+.5)*o.step,z=o.origin[1]+(j+.5)*o.step,bal=x>-44.2&&x<-28&&z>-94.8&&z<-81.5,door=doors.find(d=>Math.abs(x-d.position[0])<d.w/2-.18&&Math.abs(z-d.position[2])<.7),west=Math.abs(x+10)<1.15&&z>-7.05&&z<-3.8;if(!bal&&!door&&!west)continue;const id=Math.floor(i/o.tileSize)+'_'+Math.floor(j/o.tileSize),k=j%o.tileSize*o.tileSize+i%o.tileSize;
  for(const l of layers){if(!l[id])continue;const y=l[id][k]/100;if(bal&&y>7.251&&y<=10.51)l[id][k]=-32768;}
  const heights=bal?(Math.hypot(x-center[0],z-center[1])<radius-.18?[10.5]:[]):[door?0:S.ground(x,z)??S.bare(x,z)];
  for(const h of heights){for(const l of layers){if(!l[id]){l[id]=new Int16Array(o.tileSize*o.tileSize);l[id].fill(-32768);}if(l[id][k]===-32768||(!bal&&Math.abs(l[id][k]/100-h)<.5)){l[id][k]=Math.round(h*100);if(l!==layers[0])break;}}}
 }
 const enc=l=>Object.fromEntries(Object.entries(l).map(([k,a])=>[k,Buffer.from(a.buffer).toString('base64')]));o.tiles=enc(layers[0]);o.layerTiles=layers.slice(1).map(enc);o.sampleCounts=layers.slice(1).map(l=>Object.values(l).reduce((n,a)=>n+Array.from(a).filter(v=>v!==-32768).length,0));o.count=o.sampleCounts.reduce((a,b)=>a+b,0);N.counts=N.layers.map(a=>a.filter(v=>v!==null).length);
 for(const p of parts.slice(first)){const i=M.parts.findIndex(q=>q.id===p.id);if(i>=0)M.parts[i]=p;else M.parts.push(p);}
 M.doorBalcony=report;M.buildId=new Date().toISOString();M.voxelTotal=M.parts.reduce((n,p)=>n+(p.voxels||0),0);
 for(const [f,s]of [['manifest.json',JSON.stringify(M)],['manifest.js','window.EYRIE_MANIFEST='+JSON.stringify(M)+';'],['navigation.js','window.EYRIE_NAVIGATION='+JSON.stringify(N)+';'],['geometry.js','window.EYRIE_GEOMETRY='+JSON.stringify(Object.fromEntries(M.parts.map(p=>[p.id,fs.readFileSync(path.join(OUT,p.file)).toString('base64')])))+';']])fs.writeFileSync(path.join(OUT,f),s);
 return M;
}
module.exports={build};
