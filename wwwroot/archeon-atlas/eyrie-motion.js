/* Small kinematic loops. The harvest pass is finite; revisiting a camera never
   restores wheat. A fresh scene owns a fresh clock, geometry and cleanup. */
(() => {
 'use strict';
 function create({T,objects,batches,manifest}){
  const rules=manifest.motions||[],dummy=new T.Object3D(),up=new T.Vector3(0,1,0),a=new T.Vector3(),b=new T.Vector3();
  let elapsed=0,paused=false,harvest=0,front=-Infinity;
  const crop=[];for(const batch of batches)for(const [index,item]of (batch.items||[]).entries())if(item.harvest){crop.push({batch,index,item,cut:false});if(item.harvest.mode==='windrow'){dummy.position.fromArray(item.position);dummy.scale.setScalar(0);dummy.updateMatrix();batch.mesh.setMatrixAt(index,dummy.matrix);batch.mesh.instanceMatrix.needsUpdate=true;}}
  const insects=[];for(const batch of batches)for(const [index,item]of(batch.items||[]).entries())if(item.insect){insects.push({batch,index,item});batch.mesh.frustumCulled=false;}
  const sample=(values,t)=>{const q=Math.max(0,Math.min(values.length-1,t*(values.length-1))),i=Math.floor(q),f=q-i;return values[i]*(1-f)+(values[Math.min(i+1,values.length-1)])*f;};
  const ease=t=>t*t*(3-2*t);
  const railLengths=new Map(rules.filter(r=>r.samples).map(r=>{const d=[0];for(let i=1;i<r.samples.length;i++)d.push(d[i-1]+Math.hypot(...r.samples[i].map((v,k)=>v-r.samples[i-1][k])));return[r.id,d];}));
  function railPose(r,distance){const d=railLengths.get(r.id);let i=0;if(distance>=d.at(-1))i=d.length-2;else if(distance>0){let lo=0,hi=d.length-1;while(hi-lo>1){const m=(lo+hi)>>1;if(d[m]<=distance)lo=m;else hi=m;}i=lo;}const f=(distance-d[i])/(d[i+1]-d[i]),p=r.samples[i],q=r.samples[i+1];return{p:p.map((v,k)=>v+(q[k]-v)*f),yaw:Math.atan2(q[0]-p[0],q[2]-p[2])};}
  function shuttle(r){const cycle=2*(r.travel+r.dwell),time=elapsed%cycle;let u;if(time<r.dwell)u=0;else if(time<r.dwell+r.travel)u=ease((time-r.dwell)/r.travel);else if(time<2*r.dwell+r.travel)u=1;else u=1-ease((time-2*r.dwell-r.travel)/r.travel);return u;}
  function tick(dt,eye){if(!paused)elapsed+=dt;
   for(const r of rules){const o=objects.get(r.id);if(!o)continue;
    if(r.type==='shuttle'||r.type==='rail'){const u=shuttle(r);if(r.samples){const distance=u*railLengths.get(r.id).at(-1),pose=railPose(r,distance);o.position.fromArray(pose.p);o.rotation.y=pose.yaw;for(const bg of r.bogies||[]){const v=objects.get(bg.id);if(!v)continue;const wheel=railPose(r,distance+bg.offset),dx=wheel.p[0]-pose.p[0],dz=wheel.p[2]-pose.p[2],co=Math.cos(pose.yaw),si=Math.sin(pose.yaw);v.position.set(co*dx-si*dz,wheel.p[1]-pose.p[1],si*dx+co*dz);v.rotation.y=wheel.yaw-pose.yaw;}}else{o.position.fromArray(r.a).lerp(b.fromArray(r.b),u);if(r.sag)o.position.y-=r.sag*Math.sin(Math.PI*u);if(r.groundSamples)o.position.y=sample(r.groundSamples,u);}}
    if(r.type==='moored'){o.position.fromArray(r.base);o.position.y+=.12*Math.sin(elapsed*.65);o.rotation.z=.009*Math.sin(elapsed*.48);o.rotation.x=.007*Math.sin(elapsed*.4);}
    if(r.type==='orbit-flight'){const t=elapsed/r.period*Math.PI*2+(r.phase||0),rx=r.radius[0],rz=r.radius[1];o.position.set(r.center[0]+rx*Math.cos(t),r.center[1]+.6*Math.sin(t*2),r.center[2]+rz*Math.sin(t));o.rotation.set(.025*Math.sin(t*2),Math.atan2(-rx*Math.sin(t),rz*Math.cos(t)),(r.bank||.05)*Math.sin(t));}
    if(r.type==='rotor')o.rotation[r.axis]=elapsed*r.speed;
    if(r.type==='harvest'){harvest=Math.min(1,elapsed/r.duration);front=r.z0+(r.z1-r.z0)*harvest+2.5;o.position.set(r.x,sample(r.groundSamples,harvest),r.z0+(r.z1-r.z0)*harvest);}
    if(r.type==='reel')o.rotation[r.axis]=Math.min(elapsed,manifest.motions.find(q=>q.id===r.body)?.duration||55)*r.speed;
    if(r.type==='steam'){const t=(elapsed*.55+r.index/6)%1;o.position.set(.9+t*.4,2.6+t*1.9,-1+t*.15);o.scale.setScalar(.45+t*1.4);o.visible=harvest<1;}
   }
   for(const r of rules)if(r.type==='tether'){const o=objects.get(r.id),body=objects.get(r.body);body.updateWorldMatrix(true,false);a.fromArray(r.anchor);b.fromArray(r.attach);body.localToWorld(b);const length=a.distanceTo(b);o.position.copy(a).add(b).multiplyScalar(.5);o.quaternion.setFromUnitVectors(up,b.sub(a).normalize());o.scale.set(1,length,1);}
   for(const c of crop)if(!c.cut&&c.item.harvest.z<front){c.cut=true;const p=c.item;dummy.position.fromArray(p.position);dummy.rotation.set(0,p.rotation||0,0);dummy.scale.set(p.scale||1,(p.harvest.mode==='windrow'?1:.12)*(p.scale||1),p.scale||1);dummy.updateMatrix();c.batch.mesh.setMatrixAt(c.index,dummy.matrix);c.batch.mesh.instanceMatrix.needsUpdate=true;}
   for(const {batch,index,item}of insects){const r=item.insect,t=elapsed/r.period*Math.PI*2+r.phase,px=r.anchor[0]+r.radius*Math.cos(t),pz=r.anchor[2]+r.radius*.65*Math.sin(t),py=r.anchor[1]+r.height*Math.sin(t*2.3),yaw=Math.atan2(-Math.sin(t),.65*Math.cos(t));dummy.position.set(px,py,pz);dummy.rotation.set(0,yaw,0);if(r.part!=='body'){const side=r.part==='left'?-1:1,frequency=r.species==='butterfly'?8:r.species==='dragonfly'?32:42,flap=Math.sin(elapsed*frequency+r.phase)*(.65+(r.species==='butterfly'?.35:0));if(side<0)dummy.rotateY(Math.PI);dummy.rotateZ(side*flap);dummy.scale.set(1,1,1);}else dummy.scale.set(1,1,1);const d=eye?dummy.position.distanceTo(eye.position||eye):0,fade=Math.max(0,Math.min(1,(r.maxDistance-d)/8));dummy.scale.multiplyScalar(fade);dummy.updateMatrix();batch.mesh.setMatrixAt(index,dummy.matrix);batch.mesh.instanceMatrix.needsUpdate=true;}
  }
  return{tick,setPaused(v){paused=!!v;},state(){return{paused,elapsed,insectInstances:insects.length,harvestProgress:harvest,cutInstances:crop.filter(c=>c.cut).length,vehicles:rules.filter(r=>['shuttle','rail','moored','harvest','orbit-flight'].includes(r.type)).map(r=>({id:r.id,position:objects.get(r.id)?.position.toArray()}))};},dispose(){crop.length=0;insects.length=0;}};
 }
 window.EYRIE_MOTION={create};
})();
