/* Immutable dressing shares a few geometry batches per household and distance. */
(() => {'use strict';
 function create({T,scene,prototypes,instances,material,resources}){
  const groups=new Map(),out=[],dummy=new T.Object3D();
  const flagMaterial=material.clone();flagMaterial.onBeforeCompile=shader=>{material.onBeforeCompile(shader);shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\n#ifdef USE_INSTANCING\nif(materialFamily>11.5&&materialFamily<12.5){float pin=smoothstep(1.15,2.8,position.y);transformed.z+=sin(eyrieTime*2.1+position.x*2.5+instanceMatrix[3].x*.13)*.23*pin;transformed.x+=sin(eyrieTime*1.4+position.y*2.)*.065*pin;}\n#endif');};flagMaterial.customProgramCacheKey=()=>material.customProgramCacheKey()+'-windcloth';resources.push(flagMaterial);
  for(const a of instances){const dressing=a.prototype.startsWith('asset-')&&a.windKind!=='cloth',cs=16,cell=[Math.floor(a.position[0]/cs),Math.floor(a.position[1]/30),Math.floor(a.position[2]/cs)];const k=dressing?'dressing:'+a.owner+':'+a.maxDistance+':'+a.minDistance:a.prototype+':'+(a.lodAnchor?a.lodAnchor.join(','):cell.join(','))+':'+a.maxDistance+':'+a.minDistance;if(!groups.has(k))groups.set(k,{dressing,list:[]});groups.get(k).list.push(a);}
  const matrix=a=>{dummy.position.fromArray(a.position);if(a.quaternion)dummy.quaternion.fromArray(a.quaternion);else dummy.rotation.set(0,a.rotation||0,0);dummy.scale.setScalar(a.scale||1);dummy.updateMatrix();return dummy.matrix;};
  for(const {dressing,list}of groups.values()){
   const source=prototypes.get(list[0].prototype);if(!source)continue;let mesh;
   if(dressing&&T.BatchedMesh){const ids=new Map(),unique=[...new Set(list.map(a=>a.prototype))],nv=unique.reduce((n,id)=>n+prototypes.get(id).g.attributes.position.count,0),ni=unique.reduce((n,id)=>n+prototypes.get(id).g.index.count,0);mesh=new T.BatchedMesh(list.length,nv,ni,material);for(const id of unique)ids.set(id,mesh.addGeometry(prototypes.get(id).g));for(const a of list)mesh.setMatrixAt(mesh.addInstance(ids.get(a.prototype)),matrix(a));resources.push(mesh);}
   else{mesh=new T.InstancedMesh(source.g,list[0].windKind==='cloth'?flagMaterial:material,list.length);list.forEach((a,i)=>mesh.setMatrixAt(i,matrix(a)));mesh.instanceMatrix.needsUpdate=true;}
   mesh.computeBoundingSphere();mesh.castShadow=true;mesh.receiveShadow=true;mesh.userData={layer:source.p.layer,level:0,owner:list[0].owner};scene.add(mesh);const sphere=mesh.boundingSphere;
   out.push({mesh,center:list[0].lodAnchor?new T.Vector3(...list[0].lodAnchor):sphere.center.clone(),radius:list[0].lodAnchor?0:sphere.radius,max:list[0].maxDistance||240,min:list[0].minDistance||0,layer:source.p.layer,items:list,dressing});
  }
  return out;
 }
 window.EYRIE_BATCHES={create};
})();
