'use strict';
// Sparse voxel authoring and exposed-face rectangle meshing. All visible assets
// are made here; the viewer never substitutes smooth primitive geometry.
const fs=require('fs'),path=require('path');
const OUT=path.resolve(__dirname,process.argv.find(a=>a.startsWith('--out='))?.slice(6)||'../eyrie-assets');
const round=Number(process.argv.find(a=>a.startsWith('--round='))?.split('=')[1]||11);
const palette=['#544032','#765137','#916344','#ac8053','#b49466','#c7a779','#443e32','#d0bb91','#bba67c','#697574','#566462','#7c8479','#a7aaa0','#405d58','#638575','#ad8750','#c6a568','#725942','#95996a','#77915d','#55774f','#3e6248','#bdac73','#d1bb84','#a86548','#b78262','#d6b5a0','#e2d0a6','#a4c7c5','#70a5ab','#498b96','#dddac0','#dbb762','#d69253','#a36c7c','#b1aec3','#aeba69','#8a9165','#d8d09a','#354b48'];
const C={beam:1,wood:3,board:4,lightwood:6,dark:7,wall:8,stone:10,iron:14,copper:15,brass:16,soil:18,grass:19,leaf:21,cloth:28,glass:29,water:30,cream:32,fire:34};
palette.push('#947452','#997955','#8c6c4e','#9d7d59','#a0805b');
const parts=[],savedFields=[],walkSurfaces=[],instances=[],interactives=[],motions=[];let voxelTotal=0;
const site=require('./eyrie-site.cjs');
const addColors=(hex)=>{const start=palette.length+1;palette.push(...hex);return hex.map((_,i)=>start+i);};
const P={rock:addColors(['#a48c6d','#b39b7a','#c3ad8a','#cfbc9d','#d9caae','#e2d6bb','#e7ddc5','#eadfc6']),grass:addColors(['#77974b','#87a556','#94ae5d','#658642','#a9b969','#73924d']),soil:addColors(['#846447','#a18055','#b59a70']),flowers:addColors(['#e8c953','#eee6c8','#ad98c7','#d694ad','#6d9bb3','#e8b89f']),wet:addColors(['#617f6e','#849986','#395e57']),wheat:addColors(['#d0ab54','#e2c46c','#bca353','#edcf83']),foam:addColors(['#e0f0df','#afd8d3','#f5f5e4'])};
P.canvas=addColors(['#cd7c38','#db9650','#b76635']);P.metal=addColors(['#68716b','#46524e','#bdbdab']);
const materialRecipes=require('./eyrie-material-profiles.cjs').install({C,P,addColors});
 P.p1Cloth=addColors(['#ae593f','#485879','#c4a34e','#e3d7b8','#858b89','#494b51']);
 P.p1Ceramic=addColors(['#d6c5a4','#73939c']);
 materialRecipes.groups.p1Cloth={family:'cloth',indices:P.p1Cloth};
 materialRecipes.groups.p1Ceramic={family:'ceramic',indices:P.p1Ceramic};
const K=16384,O=8192,key=(x,y,z)=>(x+O)*K*K+(y+O)*K+z+O;
function unpack(k){let z=k%K-O;k=Math.floor(k/K);let y=k%K-O;return[Math.floor(k/K)-O,y,z];}
const hash=(x,y,z)=>{let h=Math.imul(x,73856093)^Math.imul(y,19349663)^Math.imul(z,83492791);h=Math.imul(h^(h>>>13),1274126177);return(h>>>0)/4294967296;};
class Field{
 constructor(name,step=.1,layer='structure',level=0){Object.assign(this,{name,step,layer,level,cells:new Map()});}
 set(x,y,z,c){if([x,y,z].some(q=>q < -O || q >= O || !Number.isInteger(q)))throw Error('Voxel coordinate overflow: '+this.name);if(c)this.cells.set(key(x,y,z),c);}
 fill(bounds,predicate,color){const s=this.step,[x0,y0,z0,x1,y1,z1]=bounds.map(v=>Math.floor(v/s));for(let i=x0;i<=x1;i++)for(let j=y0;j<=y1;j++)for(let k=z0;k<=z1;k++){const x=(i+.5)*s,y=(j+.5)*s,z=(k+.5)*s;if(x<bounds[0]||y<bounds[1]||z<bounds[2]||x>bounds[3]||y>bounds[4]||z>bounds[5])continue;if(predicate(x,y,z))this.set(i,j,k,typeof color==='function'?color(x,y,z):color);}}
 box(x,y,z,w,h,d,c){this.fill([x-w/2,y-h/2,z-d/2,x+w/2,y+h/2,z+d/2],(a,b,e)=>Math.abs(a-x)<=w/2&&Math.abs(b-y)<=h/2&&Math.abs(e-z)<=d/2,c);}
 ellipsoid(x,y,z,rx,ry,rz,c,shell=0){this.fill([x-rx,y-ry,z-rz,x+rx,y+ry,z+rz],(a,b,e)=>{const q=((a-x)/rx)**2+((b-y)/ry)**2+((e-z)/rz)**2;return q<=1&&(!shell||q>=(1-shell/Math.min(rx,ry,rz))**2);},c);}
 beam(a,b,r,c){if(this.name==='frame'&&Math.abs(b[1]-a[1])>1&&Math.hypot(b[0]-a[0],b[2]-a[2])>1){primaryBraces.beam(a,b,Math.max(.24,r),c);return;}const v=b.map((q,i)=>q-a[i]),l=v.reduce((n,q)=>n+q*q,0);this.fill([Math.min(a[0],b[0])-r,Math.min(a[1],b[1])-r,Math.min(a[2],b[2])-r,Math.max(a[0],b[0])+r,Math.max(a[1],b[1])+r,Math.max(a[2],b[2])+r],(x,y,z)=>{const p=[x,y,z],t=Math.max(0,Math.min(1,p.reduce((n,q,i)=>n+(q-a[i])*v[i],0)/l));return p.reduce((n,q,i)=>n+(q-a[i]-t*v[i])**2,0)<=r*r;},c);}
 cylinder(x,y,z,r,h,c,wall=0){this.fill([x-r,y-h/2,z-r,x+r,y+h/2,z+r],(a,b,e)=>Math.hypot(a-x,e-z)<=r&&(!wall||Math.hypot(a-x,e-z)>r-wall),c);}
}
function field(name,s,layer,level){return new Field(name,s,layer,level);}
const primaryBraces=field('primary-braces',.25,'structure',0);
function mesh(f){
 if(f.meta?.collisionOnly){savedFields.push(f);voxelTotal+=f.cells.size;return;}
 if(f.name==='frame'){const up=field('frame-upper',f.step,'structure',1);for(const[k,c]of f.cells){if(unpack(k)[1]*f.step>=3.75){up.cells.set(k,c);f.cells.delete(k);}}mesh(up);}
 const planes=new Map(),s=f.step;const axes=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]];
 for(const[k,c]of f.cells){const a=unpack(k);for(let face=0;face<6;face++){const n=axes[face];if(face===2&&f.omitTop?.((a[0]+.5)*s,(a[2]+.5)*s,(a[1]+1)*s))continue;if(f.cells.has(key(a[0]+n[0],a[1]+n[1],a[2]+n[2]))||f.solidAt?.((a[0]+n[0]+.5)*s,(a[1]+n[1]+.5)*s,(a[2]+n[2]+.5)*s))continue;const ax=Math.floor(face/2),uv=ax===0?[1,2]:ax===1?[2,0]:[0,1],depth=a[ax]+(face%2===0?1:0),pk=face+':'+depth;if(!planes.has(pk))planes.set(pk,{face,depth,uv,cells:new Map()});planes.get(pk).cells.set((a[uv[0]]+O)*K+a[uv[1]]+O,f.faceColor?.(a,face,c)||c);}}
 const pos=[],normal=[],color=[],extra=[],indices=[];let count=0;
 for(const p of planes.values()){const cells=p.cells;for(const[k,c]of cells){const u=Math.floor(k/K)-O,v=k%K-O;let w=1;while(cells.get((u+w+O)*K+v+O)===c)w++;let h=1;outer:while(h<16384){for(let i=0;i<w;i++)if(cells.get((u+i+O)*K+v+h+O)!==c)break outer;h++;}for(let i=0;i<w;i++)for(let j=0;j<h;j++)cells.delete((u+i+O)*K+v+j+O);
   const a=Math.floor(p.face/2),n=axes[p.face],verts=[[u,v],[u+w,v],[u+w,v+h],[u,v+h]];if(p.face%2===1)verts.reverse();const hex=palette[c-1]||palette[0],rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(q=>q<=.04045?q/12.92:((q+.055)/1.055)**2.4);
   for(const[q,r]of verts){const xyz=[0,0,0];xyz[a]=p.depth*s;xyz[p.uv[0]]=q*s;xyz[p.uv[1]]=r*s;pos.push(...xyz);normal.push(...n);const cell=[0,0,0];cell[a]=p.depth-(p.face%2===0?1:0);cell[p.uv[0]]=q===u?u:u+w-1;cell[p.uv[1]]=r===v?v:v+h-1;const su=q===u?-1:1,sv=r===v?-1:1;function occupied(du,dv,outside=true){const k=cell.map((c,i)=>c+(outside?n[i]:0));k[p.uv[0]]+=du;k[p.uv[1]]+=dv;return f.cells.has(key(...k))?1:0;}const side1=occupied(su,0),side2=occupied(0,sv),ao=side1&&side2?3:side1+side2+occupied(su,sv),edge=(2-occupied(su,0,false)-occupied(0,sv,false))*.5;extra.push(c,edge);color.push(...rgb.map(c=>c*(1-ao*.14)));}indices.push(count,count+1,count+2,count,count+2,count+3);count+=4;
 }}
 const worldBounds=boundsOf(pos);if(f.meta?.chunk){f.meta.position=[f.meta.chunk[0],0,f.meta.chunk[1]];for(let i=0;i<pos.length;i++)pos[i]-=f.meta.position[i%3];f.meta.worldBounds=worldBounds;}
 const data=Buffer.alloc(16+pos.length*4+normal.length+color.length*4+extra.length*4+indices.length*4);let o=0;data.writeUInt32LE(pos.length/3,o);o+=4;data.writeUInt32LE(indices.length,o);o+=4;data.writeUInt32LE(f.cells.size,o);o+=4;data.writeUInt32LE(2,o);o+=4;for(const a of pos){data.writeFloatLE(a,o);o+=4;}for(const a of normal){data.writeInt8(a,o++);}for(const a of color){data.writeFloatLE(a,o);o+=4;}for(const a of extra){data.writeFloatLE(a,o);o+=4;}for(const a of indices){data.writeUInt32LE(a,o);o+=4;}
 fs.writeFileSync(path.join(OUT,f.name+'.bin'),data);parts.push({id:f.name,layer:f.layer,level:f.level,step:s,voxels:f.cells.size,vertices:pos.length/3,triangles:indices.length/3,file:f.name+'.bin',bounds:boundsOf(pos),...(f.meta||{})});voxelTotal+=f.cells.size;savedFields.push(f);console.log(f.name+': '+f.cells.size+' voxels → '+indices.length/3+' triangles');
}
function boundsOf(a){const b=[Infinity,Infinity,Infinity,-Infinity,-Infinity,-Infinity];for(let i=0;i<a.length;i++){const k=i%3;b[k]=Math.min(b[k],a[i]);b[k+3]=Math.max(b[k+3],a[i]);}return b;}
if(process.argv.includes('--path-finish-only')){require('./eyrie-path-finish.cjs').build({field,mesh,C,P,parts,palette,OUT,site});return;}
if(process.argv.includes('--door-balcony-only')){require('./eyrie-door-balcony.cjs').build({field,mesh,C,P,parts,palette,OUT,site,hash});return;}
if(process.argv.includes('--structure-repair-only')){require('./eyrie-structure-repair.cjs').build({field,mesh,C,P,instances,parts,palette,OUT,hash});return;}
if(process.argv.includes('--solar-only')){require('./eyrie-solar-rebuild.cjs')({field,mesh,C,P,site,instances,parts,palette,OUT,hash});return;}
if(process.argv.includes('--assemblies-only')){require('./eyrie-rebuild-assemblies.cjs')({field,mesh,C,P,site,instances,parts,palette,OUT,round});return;}
const grain=(x,y,z)=>{const plank=Math.floor(x*3.2),end=(z+((plank%3+3)%3)*1.6)%5.2;return Math.abs(end)<.09?3:hash(plank,0,0)>.78?5:4;};
const lower=(x,z)=>(x>-9&&x<5.5&&z>-7.5&&z<2.1)||((x+4)**2/24+(z-2.2)**2/25<1&&z<7.5)||(x>3.2&&x<10&&z>-3&&z<7.2);
const upper=(x,z)=>(x>-7.7&&x<4.4&&z>-6.4&&z<1.8)||((x+4)**2/7.84+(z-2.5)**2/9<1);
const balcony=(x,z)=>(Math.hypot((x+4),z-4.5)<3.6&&z>2.2)||(x>-3&&x<7.6&&z>4.4&&z<6.9)||(x>3.6&&x<7.7&&z>5.2&&z<12.2)||(x>-.4&&x<1.4&&z>1.5&&z<4.7);
const groundDeck=(x,z)=>(Math.hypot((x+4)/1.13,z-3.2)<6.1&&z>2.5)||(x>-.3&&x<10.6&&z>5.9&&z<8.4)||(x>-10.8&&x<-8.8&&z>-7.2&&z<6.8);
const frontOpen=(x,y,z,level)=>{
 if(level===0){if(x>-.3&&x<1.5&&z>1.7&&z<5.1&&y<2.5)return true;if(x>3.4&&z>6.8&&y<2.8)return true;if(x<-8.7&&z>-5.4&&z<-3.8&&y<2.5)return true;const angle=Math.atan2(z-2.2,x+4);if(z>2.4&&y>1.1&&y<2.7&&[.34,1.03,1.73,2.40].some(a=>Math.abs(a-angle)<.13))return true;if(z<-7.1&&y>1.1&&y<2.45&&((x>-6.5&&x<-4.5)||(x>0&&x<2)))return true;if(x>9.5&&y>1&&y<2.6&&z>-.4&&z<3.8)return true;
 }else{if(x<-7.4&&y>4.6&&y<6.15&&((z>-4.85&&z<-3.25)||(z>-1.65&&z<-.05)))return true;if(x>-.4&&x<1.3&&z>1.45&&z<2.15&&y<6.3)return true;if(x>4&&z>-.1&&z<1.5&&y<6.3)return true;const angle=Math.atan2(z-2.5,x+4);if(z>1.2&&y>4.55&&y<6.35&&[.275,1.175,1.625,2.525,2.975].some(a=>Math.abs(a-angle)<.18))return true;if(z<-6&&y>4.5&&y<6.1&&((x>-5.7&&x<-4.3)||(x>-.6&&x<1.1)))return true;}
 return false;
};
fs.mkdirSync(OUT,{recursive:true});
const base=field('rock-root',.3,'structure',0);
base.fill([-10,-2.4,-8,10.6,.05,7.5],(x,y,z)=>lower(x,z)&&(!lower(x+.5,z)||!lower(x-.5,z)||!lower(x,z+.5)||!lower(x,z-.5))&&y> -2.2+.3*Math.sin(x+z),(x,y,z)=>10+Math.floor(hash(Math.floor(x/.8),Math.floor(y/.5),Math.floor(z/.7))*3));mesh(base);
for(const level of [0,1]){
 const shape=level?upper:lower,Y=level?3.8:0,floor=field('floor-'+level,.1,'floor',level);
 floor.fill([-10,Y-.25,-7.5,10,Y,7.5],(x,y,z)=>shape(x,z)&&!(level&&x>1.5&&x<3.4&&z>-5&&z<.4),grain);mesh(floor);
 const walls=field('walls-'+level,.1,'walls',level);
 walls.fill([-10,Y,-7.5,10,Y+(level?2.9:3.5),7.5],(x,y,z)=>shape(x,z)&&(!shape(x+.23,z)||!shape(x-.23,z)||!shape(x,z+.23)||!shape(x,z-.23))&&!frontOpen(x,y,z,level),(x,y,z)=>y<.9?P.basalt[Math.floor(hash(Math.floor(x/.65+Math.floor(y/.3)%2*.35),Math.floor(y/.3),Math.floor(z/.65))*3)]:level&&round>=4?(z<.9?P.weatheredWood[Math.floor(hash(Math.floor(x*1.5)+Math.floor(z*1.5),0,0)*3)]:P.plaster[0]):P.plaster[2]);mesh(walls);
}
const soffit=field('lower-soffit',.1,'ceiling',0);soffit.fill([-9,3.45,-7.5,5.5,3.8,7.5],(x,y,z)=>lower(x,z)&&!upper(x,z)&&!balcony(x,z),grain);mesh(soffit);
const decks=field('terraces',.1,'floor',1);decks.fill([-10,3.55,1.5,8,3.8,12.3],(x,y,z)=>balcony(x,z)&&!upper(x,z),grain);mesh(decks);
const lowerDeck=field('lower-porch',.1,'floor',0);lowerDeck.fill([-11,-.3,-8,11,0,10],(x,y,z)=>groundDeck(x,z)&&!lower(x,z),grain);mesh(lowerDeck);
const frames=field('frame',.1,'structure',0);
for(const[x,z]of[[-8.8,-7.3],[-8.8,1.8],[4.9,-7.3],[4.9,1.8],[9.7,-2.8],[9.7,6.9],[3.4,6.9]])frames.box(x,1.7,z,.32,3.6,.32,C.beam);
for(const z of[-6.25,1.65]){frames.beam([-7.7,3.7,z],[4.4,3.7,z],.2,C.beam);frames.beam([-7.7,6.65,z],[4.4,6.65,z],.2,C.beam);}
for(const x of[-7.6,-4.3,.2,4.25])for(const z of[-6.2,1.5])frames.box(x,5.15,z,.28,3,.28,C.beam);
for(let a=.05;a<Math.PI*1.02;a+=.45){const x=-4+2.8*Math.cos(a),z=2.5+3*Math.sin(a);frames.box(x,5.25,z,.2,2.9,.2,C.wood);}
for(let a=.12;a<Math.PI;a+=.28){const x=-4+3.5*Math.cos(a),z=4.5+3.5*Math.sin(a);frames.box(x,4.32,z,.15,1.04,.15,C.beam);const b=a+.28;frames.beam([x,4.85,z],[-4+3.5*Math.cos(b),4.85,4.5+3.5*Math.sin(b)],.09,C.wood);}
for(const x of[3.75,7.5]){frames.beam([x,4.87,5.5],[x,4.87,6.6],.09,C.wood);for(let z=5.5;z<6.8;z+=1.15)frames.box(x,4.3,z,.14,1.1,.14,C.beam);frames.beam([x,3.45,11.8],[x,-2,4.8],.23,C.beam);frames.box(x,-2,4.8,.8,.65,.8,C.iron);frames.beam([x,3.45,10.8],[x,3.45,2],.22,C.beam);}
for(let a=.25;a<Math.PI;a+=.48){const x=-4+3.5*Math.cos(a),z=4.5+3.5*Math.sin(a);frames.beam([x,3.55,z],[-4+2.5*Math.cos(a),.2,2.5+2.5*Math.sin(a)],.2,C.beam);}
mesh(frames);mesh(primaryBraces);
const homeSaddles=field('eyrie-fiber-saddles',.1,'structure',1);for(const x of[3.75,7.5]){homeSaddles.fill([x-.4,3.02,10.43,x+.4,3.56,11.18],(a,b,c)=>Math.abs(a-x)>.23||b<3.16,P.fiber[1]);for(const z of[10.5,11.1])homeSaddles.box(x,3.12,z,.8,.14,.16,C.brass);}mesh(homeSaddles);
const roofs=field('roof',.2,'roof',2);
const roofY=(x,z)=>6.62+2.88*Math.pow(Math.max(0,1-Math.abs((z+2.3)/5)),.64)+.07*Math.sin(x*.9);
roofs.fill([-8.7,6.2,-7.6,5.4,9.7,3.2],(x,y,z)=>y<roofY(x,z)&&y>roofY(x,z)-.22,(x,y,z)=>round>=2?41+(hash(Math.floor(x*1.3),0,Math.floor(z*2))>.75?1:0):4);
roofs.fill([-7.4,6.1,-.6,-.6,8.2,6],(x,y,z)=>{const r=Math.hypot(x+4,(z-2.5)*.94),top=6.4+1.7*Math.pow(Math.max(0,1-r/3.45),.65);return r<3.45&&y<top&&y>top-.22;},(x,y,z)=>round>=2?41+Math.abs(Math.floor(Math.atan2(z-2.5,x+4)*12))%2:4);
roofs.fill([4.3,3.2,-3.8,10.7,5.6,-.25],(x,y,z)=>{const top=3.4+1.8*(1-(z+3.8)/7.2)**.8;return y<top&&y>top-.2;},41);roofs.fill([6.3,2.8,2,10.7,3.4,7.5],(x,y,z)=>{const top=3.45-.075*(z-2);return y<top&&y>top-.18;},42);mesh(roofs);
// Exterior return stair: each 0.238m riser is modelled, with a broad landing.
const stair=field('stairs',.1,'structure',0);
for(let i=0;i<16;i++){const y=(i+1)*3.8/16,z=7.3-i*.42;stair.box(11.1,y-.12,z,1.55,.24,.44,C.board);stair.beam([11.9,y+1,z],[11.9,y+1+3.8/16,z-.42],.125,C.wood);if(i%3===0)stair.box(11.9,y+.5,z,.2,1.05,.2,C.beam);}
stair.box(8.55,3.68,.6,7,.24,1.6,C.board);stair.box(4.7,3.68,.65,1.3,.24,1.3,C.board);stair.box(5.4,3.68,3,1.2,.24,5.7,C.board);stair.box(10.9,-.12,7.9,2,.24,1.1,C.board);
stair.beam([11.65,-.2,7.8],[11.65,3.4,.4],.18,C.beam);stair.beam([10.55,-.2,7.8],[10.55,3.4,.4],.18,C.beam);mesh(stair);
// Internal stair reaches the upper sleeping floor through a real opening.
const insideStair=field('inside-stair',.1,'structure',0);for(let i=0;i<16;i++)insideStair.box(2.4,(i+1)*.2375-.1,.05-i*.3,1.5,.2,.32,C.board);insideStair.box(2.4,3.68,-4.82,1.65,.24,.64,C.board);mesh(insideStair);
// Place reference figure and winged skiff early so every iteration has scale.
const people=field('people',.05,'people',1);function person(x,y,z,h,c){people.ellipsoid(x,y+h*.9,z,.12*h,.11*h,.11*h,26);people.box(x,y+h*.57,z,.36*h/1.7,h*.35,.25,c);for(const s of[-1,1]){people.beam([x+s*.1,y+h*.4,z],[x+s*.13,y+.04,z+s*.07],.065,C.dark);people.beam([x+s*.2,y+h*.7,z],[x+s*.25,y+h*.4,z+.05],.055,c);}}person(-3.6,3.8,7.15,1.7,25);person(-5,3.8,6.6,1.05,29);mesh(people);
// Terrain, paths and water share one signed solid and surface model.
const cliffEdge=x=>site.edge(x,0);
require('./eyrie-environment.cjs')({field,mesh,C,P,hash,site,instances,interactives,lower,groundDeck});
// Additional craft, lived detail, vegetation and collision maps are added in the
// corresponding review rounds. The basic shell remains the same source model.
if(round>=2){const craft=field('roof-joinery',.1,'roof',2);for(const x of[-7.7,4.4]){craft.fill([x-.14,6.6,-6.7,x+.14,9.5,2.7],(a,b,c)=>b<roofY(a,c)-.2,(a,b,c)=>Math.floor(b*5)%6===0?2:5);for(let z=-7.5;z<2.6;z+=.18)craft.beam([x,roofY(x,z)-.1,z],[x,roofY(x,z+.18)-.1,z+.18],.105,C.beam);}
 for(const z of[-7.4,2.65])craft.beam([-8.5,roofY(-8,z)-.1,z],[5.3,roofY(5,z)-.1,z],.12,C.wood);
 for(let a=0;a<Math.PI*2;a+=.12){const b=a+.12;craft.beam([-4+3.43*Math.cos(a),6.42,2.5+3.65*Math.sin(a)],[-4+3.43*Math.cos(b),6.42,2.5+3.65*Math.sin(b)],.11,C.wood);}
 // A narrow upper window breaks the long eave beside the circular room.
 craft.box(1.8,7.28,2.15,1.85,1.85,1.15,C.wood);craft.box(1.8,7.28,2.76,1.45,1.38,.1,C.glass);craft.box(1.8,7.28,2.84,.1,1.46,.12,C.lightwood);craft.box(1.8,7.26,2.84,1.55,.1,.12,C.lightwood);craft.fill([.55,7.8,1.3,3.05,8.9,3],(x,y,z)=>Math.abs(y-(8.6-Math.abs(x-1.8)*.48))<.13,3);mesh(craft);
 const glazing=field('window-frames',.05,'details',1);for(let a=.3;a<=3.01;a+=.715){const cx=-4+2.86*Math.cos(a),cz=2.5+3.07*Math.sin(a);for(const d of[-.17,.17])glazing.beam([-4+2.86*Math.cos(a+d),4.53,2.5+3.07*Math.sin(a+d)],[-4+2.86*Math.cos(a+d),6.3,2.5+3.07*Math.sin(a+d)],.065,C.wood);for(const y of[4.51,5.48,6.3])glazing.beam([-4+2.91*Math.cos(a-.19),y,2.5+3.1*Math.sin(a-.19)],[-4+2.91*Math.cos(a+.19),y,2.5+3.1*Math.sin(a+.19)],.07,C.wood);glazing.beam([cx,4.54,cz],[cx,6.27,cz],.045,C.lightwood);}}
if(round>=3)require('./eyrie-details.cjs')({round,field,mesh,C,hash,grain});
if(round>=5)require('./eyrie-garden.cjs')({field,mesh,C,hash,cliffEdge});
require('./eyrie-windows.cjs')({field,mesh,C,P,hash,interactives});
require('./eyrie-interior.cjs')({field,mesh,C,P,hash});
require('./eyrie-terraces.cjs')({field,mesh,C,P,hash,site,instances,motions});
require('./eyrie-lower-terraces.cjs')({field,mesh,C,P,hash,site,instances,motions});
require('./eyrie-expansion-buildings.cjs')({field,mesh,C,P,hash,site,instances,motions});
require('./eyrie-residential-doors.cjs')({field,mesh,C,P,site,instances,parts});
require('./eyrie-float-rail.cjs').build({field,mesh,C,P,site,instances});
require('./eyrie-life.cjs')({field,mesh,C,P,hash,site,motions});require('./eyrie-small-craft.cjs')({field,mesh,C,P,site,motions});
require('./eyrie-skiffs.cjs')({field,mesh,C,P,site,motions});
site.solarIntegrated=true;
const mechanicalSystems=require('./eyrie-mechanics.cjs')({field,mesh,C,P,hash,site,instances,motions});
const livingAssets=require('./eyrie-living-assets.cjs')({field,mesh,C,P,hash,site,instances});
mechanicalSystems.systems.push(...require('./eyrie-expansion-life.cjs')({field,mesh,C,P,hash,site,instances,motions,parts,livingAssets}));
mechanicalSystems.connectedSystems+=20;mechanicalSystems.rotatingParts+=9;
require('./eyrie-dressing-clearance.cjs')({site});

require('./eyrie-ground.cjs')({field,mesh,C,P,hash,site});
const denseLife=require('./eyrie-dense-life.cjs')({field,mesh,C,P,site,instances,parts});
 const p1Module=require('./eyrie-p1-life.cjs');p1Module.clean({site,instances,parts});
const lifeScenes=p1Module.build({field,mesh,C,P,site,instances,parts});
instances.push({id:'north-drying-roof-pennant',prototype:'annex-flag-2',position:[5.5,10.5,-88.25],owner:'north-drying',surfaceId:'north-drying-deck-3',scale:1.45,rotation:-.35,windKind:'cloth',maxDistance:430,minDistance:0,lodAnchor:[1.5,12,-88.2]});
require('./eyrie-vegetation.cjs')({field,mesh,C,P,hash,site,instances,lower,groundDeck});
require('./eyrie-garden-details.cjs')({field,mesh,C,P,site,instances});

require('./eyrie-dressing-clearance.cjs')({site,instances,denseLife});
require('./eyrie-residential-life.cjs')({field,mesh,C,P,site,instances,parts,motions});
const solarArchitecture=require('./eyrie-solar.cjs').build({M:{survey:site.sceneSnapshot()},field,mesh,C,P,site,instances});
const navigation=round>=4?require('./eyrie-navigation.cjs')({savedFields,key,lower,upper,balcony,groundDeck,site,instances}):null;
const manifest={version:3,residential:site.residentialPlan,solarArchitecture,denseLife,lifeScenes,lowGeometry:site.lowGeometryReport,floatRail:site.floatRailReport,round,buildId:new Date().toISOString(),instances,interactives,motions,livingAssets,mechanicalSystems,materialGroups:materialRecipes.groups,transport:site.transportReport,site:{radius:100,cliffDrop:122,neighbours:8,standaloneHouses:3+site.expansionPlan.compounds.filter(c=>!c.major).length,compounds:site.compounds.filter(c=>c.major!==false).length,buildingSites:3+site.compounds.length,upperCompounds:site.compounds.filter(c=>!c.id.startsWith('lower-')&&c.base>=0||['primary','rear'].includes(c.id)).length,sceneBounds:site.sceneBounds,lowerCompounds:site.compounds.filter(c=>c.base< -100).length,gondolas:site.gondolas.length},survey:site.sceneSnapshot(),nature:site.natureReport,units:'metres',allVisibleGeometry:'sparse-voxels-exposed-face-mesh',dimensions:{width:20,depth:15,upperFloor:3.8,ridge:9.5,projection:5},parts,voxelTotal,palette,canon:{era:'P1 childhood',rock:'Home Shelf south rim; cliff C',mooring:'small mooring canonical; upper position is design addition',skiff:'winged; 30–50% buoyancy; cradle supported; clear downward launch'},views:{home:{position:[27,15,35],target:[0,3,2]},inside:{position:[19,24,27],target:[0,1,0]},upper:{position:[-16,15,27],target:[-2,4.5,2]},dock:{position:[22,12,25],target:[4.5,4,7]},site:{position:[84,53,106],target:[4,-9,-1]},back:{position:[-28,19,-27],target:[-2,3,-2]}}};
Object.assign(manifest.views,{hearth:{position:[-1.5,1.72,3.4],target:[-5.3,1.3,-1.8]},bench:{position:[8.3,1.75,6.55],target:[6.4,1.1,4.55]},window:{position:[-1.95,5.45,3.8],target:[-4.6,4.95,2.1]}});
manifest.views.home={position:[20,12.5,27],target:[0,3.7,2.5]};manifest.version=3;manifest.materialMasks=['voxel-neighbour-AO','convex-edge-wear','anisotropic-wood-grain','mineral-mottling','source-driven-drips','wet-roughness','hearth-soot','table-contact-wear'];

Object.assign(manifest.views,{home:{position:[21,11,29],target:[0,2.5,3]},site:{position:[128,28,151],target:[1,-49,12]},left:{position:[-39,7,31],target:[-6,-1,4]},right:{position:[42,9,34],target:[8,-1,3]},cliff:{position:[105,-27,211],target:[0,-55,13]},plain:{position:[58,-108,80],target:[24,-116,42]},river:{position:[37,5,-12],target:[26,-.3,-7]},wheat:{position:[-4,4,-49],target:[-7,.5,-31]},village:{position:[-42,10,-48],target:[-32,1,-20]},back:{position:[-25,13,-32],target:[-2,2,-2]}});
Object.assign(manifest.views,{neighbourFront:{position:[-44,8,-7],target:[-33,2,-22]},villageWide:{position:[-61,37,-86],target:[-8,1,-32]},gondola:{position:[-74,9,36],target:[-48,-5,16]},airship:{position:[93,15,10],target:[77,5,-11]},harvest:{position:[60,6,-28],target:[46.5,1,-42]},rail:{position:[43,5,-63],target:[35,1,-73]},grass:{position:[-17,2,-18],target:[-24,.3,-24]}});
Object.assign(manifest.views,{airships:{position:[91,17,29],target:[67,3,0]},pavilionShip:{position:[-92,12,-16],target:[-77,4,-34]}});
Object.assign(manifest.views,{market:{position:[-47,5,-4],target:[-37,1,-13]}});
Object.assign(manifest.views,require('./eyrie-p1-views.cjs'));
manifest.paletteFamilies=palette.map((_,i)=>{const c=i+1;return P.metal.includes(c)?'metal':P.rock.includes(c)?'rock':P.grass.includes(c)?'leaf':P.soil.includes(c)?'soil':P.flowers.includes(c)?'flower':P.wet.includes(c)?'rock':P.wheat.includes(c)?'wheat':P.foam.includes(c)?'foam':c<8||c>=41&&c<=45?'wood':c<10?'plaster':c<14?'rock':c<18?'metal':c===18?'soil':c>=19&&c<=22||c===37||c===38?'leaf':c===29?'glass':c===30||c===31?'water':c===33||c===34?'light':'cloth';});
for(const group of Object.values(materialRecipes.groups))for(const c of group.indices)manifest.paletteFamilies[c-1]=group.family;
require('./eyrie-resolve-faces.cjs')({parts,OUT});
const finalParts=new Map(parts.map(p=>[p.id,p]));for(const p of denseLife.placements)p.triangles=finalParts.get(p.prototype).triangles;denseLife.highTriangles=denseLife.placements.reduce((n,p)=>n+p.triangles,0)+(finalParts.get('dense-planter-beds')?.triangles||0);
Object.assign(manifest.views,require('./eyrie-scene-views.cjs'));
const solarSystems=solarArchitecture.entries.map(e=>({id:'solar-'+e.owner,type:'solar',owner:e.owner,position:e.terminal,chain:['sealed-glazing','building-frame','insulated-wire','knife-relay','local-lamp']}));
mechanicalSystems.systems.push(...solarSystems);mechanicalSystems.solarTerminals=solarArchitecture.wires.map(w=>({owner:w.owner,position:w.path.at(-1),cabinet:w.terminal}));
for(const report of [site.expansionPlan.lifeReport,livingAssets.expansion]){report.systems=report.systems.filter(s=>s.type!=='solar').concat(solarSystems.filter(s=>site.expansionPlan.compounds.some(c=>c.id===s.owner)));}
if(navigation)navigation.outdoor.props.push(...solarArchitecture.supports.map(a=>({id:a.id,position:a.a,rotation:0,collision:{kind:'prop',width:.25,depth:.25,height:a.b[1]-a.a[1]},layer:'props'})));
const preserveFrom=process.argv.find(a=>a.startsWith('--preserve-from='))?.slice(16);if(preserveFrom)require('./eyrie-residential-preserve.cjs')({manifest,OUT,source:path.resolve(preserveFrom),navigation});
fs.writeFileSync(path.join(OUT,'manifest.json'),JSON.stringify(manifest));fs.writeFileSync(path.join(OUT,'manifest.js'),'window.EYRIE_MANIFEST='+JSON.stringify(manifest)+';');
if(navigation)fs.writeFileSync(path.join(OUT,'navigation.js'),'window.EYRIE_NAVIGATION='+JSON.stringify(navigation)+';');
fs.writeFileSync(path.join(OUT,'geometry.js'),'window.EYRIE_GEOMETRY='+JSON.stringify(Object.fromEntries(parts.map(p=>[p.id,fs.readFileSync(path.join(OUT,p.file)).toString('base64')])) )+';');
console.log(JSON.stringify({round,parts:parts.length,voxels:voxelTotal,triangles:parts.reduce((n,p)=>n+p.triangles,0)}));





// Preserve the authored neighbour comfort and low-poly clothes on a full export.
require('./eyrie-neighbour-comfort.cjs').apply(OUT);
require('./eyrie-structure-repair.cjs').build({field,mesh,C,P,instances,parts,palette,OUT,hash});
require('./eyrie-path-finish.cjs').build({field,mesh,C,P,parts,palette,OUT,site});
require('./eyrie-door-balcony.cjs').build({field,mesh,C,P,parts,palette,OUT,site,hash});
