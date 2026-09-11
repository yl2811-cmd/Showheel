/* The waterfall spray uses the same paused clock as the nearby boats and cloth. */
(()=>{'use strict';
 function create({T,root,resources}){const g=new T.BoxGeometry(.22,.22,.22),m=new T.MeshBasicMaterial({color:'#e7f1df',transparent:true,opacity:.32,depthWrite:false}),mesh=new T.InstancedMesh(g,m,180),dummy=new T.Object3D();mesh.name='eyrie-water-spray';mesh.frustumCulled=false;root.add(mesh);resources.push(g,m);
  return{mesh,tick(time){for(let i=0;i<180;i++){const t=(time*.16+i/180)%1,a=i*2.399;dummy.position.set(26.5+Math.cos(a)*(2+t*6),-121.7+Math.sin(t*Math.PI)*(1.4+i%5*.4),38+Math.sin(a)*(3+t*8));dummy.rotation.set(0,0,0);dummy.scale.setScalar(.45+t*1.7);dummy.updateMatrix();mesh.setMatrixAt(i,dummy.matrix);}mesh.instanceMatrix.needsUpdate=true;}};
 }
 function flow(material,time){const base=material.onBeforeCompile;material.onBeforeCompile=s=>{base?.call(material,s);s.uniforms.fallTime=time;s.vertexShader=s.vertexShader.replace('#include <common>','#include <common>\nvarying vec3 fallLocal;').replace('#include <begin_vertex>','#include <begin_vertex>\nfallLocal=position;');s.fragmentShader=s.fragmentShader.replace('#include <common>','#include <common>\nuniform float fallTime;varying vec3 fallLocal;').replace('#include <color_fragment>','#include <color_fragment>\nfloat falling=sin(fallLocal.y*3.4+fallTime*7.0+sin(fallLocal.x*5.0));diffuseColor.rgb*=.88+.12*falling;');};material.customProgramCacheKey=()=> 'eyrie-downward-water-v1';}
 window.EYRIE_WATER_SPRAY={create,flow};
})();
