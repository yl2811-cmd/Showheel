/* Material grain stays local; a separate world position carries nearby
   registered wet sources across ordinary, instanced and batched geometry. */
(() => {'use strict';
 const MAX_WET=8,time={value:0},wetCount={value:0},wetSources={value:new Float32Array(MAX_WET*4)},wetParams={value:new Float32Array(MAX_WET*2)},carbonRange={value:new Float32Array([-1,-1])};
 const legacy=[[-8.5,6.6,-7.45],[-10.05,4.95,-5.8],[10.15,2.7,1.7],[-4,4.52,5.6],[-6.5,4.52,4.1]].map((p,i)=>({id:'eyrie-drip-'+i,p,radius:.42,strength:.75,drip:true}));
 let sources=legacy,lastEye=null;
 function choose(eye){const p=eye?[eye.x??eye[0],eye.y??eye[1],eye.z??eye[2]]:[0,3,0];if(lastEye&&Math.hypot(...p.map((v,i)=>v-lastEye[i]))<4)return;lastEye=p;
  const selected=sources.map(s=>({s,d:(s.p[0]-p[0])**2+(s.p[1]-p[1])**2+(s.p[2]-p[2])**2})).sort((a,b)=>a.d-b.d).slice(0,MAX_WET).map(q=>q.s);wetCount.value=selected.length;wetSources.value.fill(0);wetParams.value.fill(0);
  selected.forEach((s,i)=>{wetSources.value.set([...s.p,s.radius],i*4);wetParams.value.set([s.strength,s.drip?-1:1],i*2);});
 }
 function configure(manifest={}){const effects=manifest.survey?.groundEffects||[];sources=[...legacy,...effects.filter(e=>(e.type||e.kind)==='wet'&&Number.isFinite(e.y)).map(e=>({id:e.id,p:[e.x??e.position?.[0],e.y,e.z??e.position?.[2]],radius:Math.max(.2,Math.min(3.5,e.radius||.75)),strength:Math.max(0,Math.min(1,e.strength??.65)),drip:e.drip===true})).filter(e=>e.p.every(Number.isFinite))];
  const ids=manifest.materialGroups?.carbon?.indices||manifest.paletteGroups?.carbon||[];carbonRange.value.set(ids.length?[Math.min(...ids),Math.max(...ids)]:[-1,-1]);lastEye=null;choose();
 }
 function apply(material){material.onBeforeCompile=shader=>{
  Object.assign(shader.uniforms,{eyrieTime:time,eyrieWetCount:wetCount,eyrieWetSources:wetSources,eyrieWetParams:wetParams,eyrieCarbonRange:carbonRange});
  shader.vertexShader=shader.vertexShader.replace('#include <common>',`#include <common>
attribute float materialFamily;attribute vec2 voxelSurface;uniform float eyrieTime;
varying float vMaterialFamily;varying vec3 vVoxelPos;varying vec3 vVoxelN;varying vec3 vVoxelWorld;varying vec2 vVoxelSurface;`)
   .replace('#include <begin_vertex>',`#include <begin_vertex>
vMaterialFamily=materialFamily;
#ifdef USE_INSTANCING
if(materialFamily>4.5&&materialFamily<7.5)transformed.x+=sin(eyrieTime*1.2+instanceMatrix[3].x*.15+instanceMatrix[3].z*.21)*.055*smoothstep(.3,1.,position.y);
#endif
vVoxelPos=position;vVoxelN=normal;vVoxelSurface=voxelSurface;`)
   .replace('#include <project_vertex>',`#include <project_vertex>
vec4 eyrieWorldPosition=vec4(transformed,1.0);
#ifdef USE_BATCHING
eyrieWorldPosition=batchingMatrix*eyrieWorldPosition;
#endif
#ifdef USE_INSTANCING
eyrieWorldPosition=instanceMatrix*eyrieWorldPosition;
#endif
vVoxelWorld=(modelMatrix*eyrieWorldPosition).xyz;`);
  shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>
varying float vMaterialFamily;varying vec3 vVoxelPos;varying vec3 vVoxelN;varying vec3 vVoxelWorld;varying vec2 vVoxelSurface;
uniform int eyrieWetCount;uniform vec4 eyrieWetSources[${MAX_WET}];uniform vec2 eyrieWetParams[${MAX_WET}];uniform vec2 eyrieCarbonRange;
float ehash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float enoise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(ehash(i),ehash(i+vec2(1,0)),f.x),mix(ehash(i+vec2(0,1)),ehash(i+vec2(1,1)),f.x),f.y);}
float sourceWet(vec3 p,vec4 s,vec2 prm){vec2 d=p.xz-s.xz;float q=dot(d,d)/(s.w*s.w);float drop=s.y-p.y;
 if(q>5.||abs(drop)>8.)return 0.;
 float vertical=prm.y<0.?step(0.,drop)*exp(-drop*.35):exp(-abs(drop)*3.8);
 return prm.x*exp(-q*1.8)*vertical*(.63+.37*enoise(vec2(p.y*6.,(p.x+p.z)*13.)));}
`)
   .replace('#include <color_fragment>',`#include <color_fragment>
vec3 ep=vVoxelPos;vec3 en=abs(vVoxelN);float em=vVoxelSurface.x,ee=vVoxelSurface.y;
bool wood=vMaterialFamily<.5;bool rock=vMaterialFamily>.5&&vMaterialFamily<1.5;bool plaster=vMaterialFamily>1.5&&vMaterialFamily<2.5;bool metal=vMaterialFamily>2.5&&vMaterialFamily<3.5;
bool ceramic=vMaterialFamily>12.5&&vMaterialFamily<13.5;bool composite=vMaterialFamily>13.5&&vMaterialFamily<14.5;bool glassSurface=vMaterialFamily>8.5&&vMaterialFamily<9.5;
bool carbon=composite&&em>=eyrieCarbonRange.x&&em<=eyrieCarbonRange.y;
vec2 uv=en.y>.5?ep.xz:en.z>.5?ep.xy:ep.zy;
float wet=0.;for(int i=0;i<${MAX_WET};i++){if(i>=eyrieWetCount)break;wet+=sourceWet(vVoxelWorld,eyrieWetSources[i],eyrieWetParams[i]);}wet=clamp(wet,0.,1.);
float macro=enoise(vVoxelWorld.xz*.19+vVoxelWorld.yy*.11);
if(wood){float fiber=enoise(vec2(uv.x*52.+enoise(uv*2.)*1.4,uv.y*.9));float longFiber=enoise(vec2(uv.x*135.,uv.y*2.));diffuseColor.rgb*=.90+.13*fiber+.035*longFiber+.025*macro;diffuseColor.rgb+=vec3(.032,.023,.012)*ee;diffuseColor.rgb*=1.-wet*.28;
 float tabletop=step(.9,vVoxelWorld.y)*(1.-step(1.02,vVoxelWorld.y))*step(vVoxelWorld.x,-1.9)*step(-6.1,vVoxelWorld.x)*en.y;
 float ring=exp(-pow((length(vVoxelWorld.xz-vec2(-3.2,2.05))-.12)*80.,2.))*tabletop;diffuseColor.rgb*=1.-ring*.1;}
if(rock){float patches=enoise(uv*3.5)*.6+enoise(uv*18.)*.4;diffuseColor.rgb*=.81+patches*.23+macro*.045;diffuseColor.rgb+=vec3(.013,.015,.015)*ee;diffuseColor.rgb*=1.-wet*.35;
 float soot=exp(-pow((vVoxelWorld.x+7.25)*1.3,2.)-pow((vVoxelWorld.z+4.5)*2.,2.))*smoothstep(.9,1.7,vVoxelWorld.y)*(1.-smoothstep(3.,4.,vVoxelWorld.y));diffuseColor.rgb*=1.-soot*.38;}
if(plaster){diffuseColor.rgb*=.89+.08*enoise(uv*6.)+.06*macro;diffuseColor.rgb*=1.-wet*.23;}
if(metal){diffuseColor.rgb=mix(diffuseColor.rgb,diffuseColor.rgb*vec3(.67,.92,.82),wet*.55);diffuseColor.rgb+=vec3(.022,.018,.011)*ee;}
if(ceramic){diffuseColor.rgb*=.9+.09*enoise(uv*9.)+.045*macro;diffuseColor.rgb+=vec3(.025,.017,.011)*ee;diffuseColor.rgb*=1.-wet*.19;}
if(composite){float lay=enoise(vec2(uv.x*(carbon?65.:31.),uv.y*2.5));diffuseColor.rgb*=.91+.09*lay+.025*ee;diffuseColor.rgb*=1.-wet*.14;}
`)
   .replace('#include <roughnessmap_fragment>',`#include <roughnessmap_fragment>
roughnessFactor=clamp(roughnessFactor-wet*.27,.42,1.);
if(metal)roughnessFactor=.5+wet*.13;
if(ceramic)roughnessFactor=.76-wet*.16;
if(glassSurface)roughnessFactor=.29-wet*.08;
if(composite)roughnessFactor=(carbon?.66:.8)-wet*.1;`)
   .replace('#include <metalnessmap_fragment>',`#include <metalnessmap_fragment>
if(metal)metalnessFactor=.4+ee*.13;
if(glassSurface)metalnessFactor=.025;
if(ceramic||composite)metalnessFactor=0.;`)
   .replace('#include <emissivemap_fragment>',`#include <emissivemap_fragment>
if(em>32.5&&em<34.5)totalEmissiveRadiance+=vec3(1.,.42,.1)*(em<33.5?1.25:.3);`);
 };material.customProgramCacheKey=()=> 'eyrie-families-v4-ceramic-composite-wet8';}
 function water(material){material.onBeforeCompile=shader=>{shader.uniforms.eyrieTime=time;shader.vertexShader=shader.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 waterPos;').replace('#include <begin_vertex>','#include <begin_vertex>\nwaterPos=position;');shader.fragmentShader=shader.fragmentShader.replace('#include <common>','#include <common>\nuniform float eyrieTime;varying vec3 waterPos;').replace('#include <color_fragment>','#include <color_fragment>\nfloat ripple=sin(waterPos.z*9.0-eyrieTime*2.1+sin(waterPos.x*4.0))*sin(waterPos.x*5.0+eyrieTime*.8);diffuseColor.rgb*=.91+.09*ripple;diffuseColor.rgb+=vec3(.07,.1,.085)*pow(max(0.,ripple),10.);');};material.customProgramCacheKey=()=> 'eyrie-water-v3';}
 configure();window.EYRIE_SURFACES={configure,apply,water,time,tick(t,eye){time.value=t;if(eye)choose(eye);},state(){return{wetSources:sources.length,activeWetSources:wetCount.value};}};
})();
