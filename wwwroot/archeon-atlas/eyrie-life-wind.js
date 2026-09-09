/* One pin-weight model drives coloured geometry and its shadow. */
(() => {'use strict';
 const clamp=x=>Math.max(0,Math.min(1,x));
 function weight(p,x,y,z){if(!p)return 0;if(p.mode==='ribbon')return clamp((x-p.pinX)/p.height);if(p.mode==='grass')return clamp((y-p.pinY-.04)/p.height);return clamp((p.pinY-y-.10)/p.height);}
 function attributes(T,g,p){const a=g.getAttribute('position'),data=new Float32Array(a.count*4),w=p.lifeWind;
  if(w)for(let i=0;i<a.count;i++){const family=g.getAttribute('materialFamily')?.getX(i),fixedHardware=w.mode!=='grass'&&family!==undefined&&family!==12,v=fixedHardware?0:weight(w,a.getX(i),a.getY(i),a.getZ(i));data.set([v*w.amplitude,w.phase||0,v,w.frequency],i*4);}
  g.setAttribute('p1Wind',new T.BufferAttribute(data,4));
 }
 const deformation=`
 #ifdef USE_INSTANCING
 if(p1Wind.w>0.0){
   float phase=p1Wind.y+instanceMatrix[3].x*.137+instanceMatrix[3].z*.191+instanceMatrix[3].y*.021+position.x*.65+position.z*.42;
   float swell=sin(eyrieTime*p1Wind.w+phase)*.76+sin(eyrieTime*p1Wind.w*.53+phase*1.7)*.24;
   vec3 windWorld=vec3(.88,0.,.47)*swell*p1Wind.x;
   vec3 windLocal=vec3(dot(instanceMatrix[0].xyz,windWorld),dot(instanceMatrix[1].xyz,windWorld),dot(instanceMatrix[2].xyz,windWorld));
   transformed+=windLocal;
   transformed.y+=sin(eyrieTime*p1Wind.w*1.31+phase)*p1Wind.x*.12;
 }
 #endif
 `;
 function applyMotion(m,time){m.defaultAttributeValues={...(m.defaultAttributeValues||{}),p1Wind:[0,0,0,0]};m.onBeforeCompile=s=>{s.uniforms.eyrieTime=time;s.vertexShader=s.vertexShader.replace('#include <common>','#include <common>\nattribute vec4 p1Wind;uniform float eyrieTime;').replace('#include <begin_vertex>','#include <begin_vertex>\n'+deformation);};m.customProgramCacheKey=()=> 'p1-pinned-motion-2';return m;}
 function depth(T,time){return applyMotion(new T.MeshDepthMaterial({depthPacking:T.RGBADepthPacking}),time);}
 window.EYRIE_LIFE_WIND={attributes,weight,deformation,depth,applyMotion};
})();
