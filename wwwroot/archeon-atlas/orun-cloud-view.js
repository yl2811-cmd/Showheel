/* Two-pass weighted transparency; terrain and water are rendered once into the background. */
(() => {'use strict';
function create(T,renderer,scene,camera,onState){
 const cloudScene=new T.Scene(),quadScene=new T.Scene(),quadCamera=new T.OrthographicCamera(-1,1,1,-1,0,1),box=new T.BoxGeometry(1,1,1),uniforms={previousMix:{value:1},opacity:{value:.17},pass:{value:0},resolution:{value:new T.Vector2(1,1)},sceneDepth:{value:null},eye:{value:new T.Vector3()}};
 const vertex=`attribute float cloudDensity;attribute float cloudTone;varying float density;varying float tone;
 #include <common>
 #include <logdepthbuf_pars_vertex>
 void main(){density=cloudDensity;tone=cloudTone;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);
 #include <logdepthbuf_vertex>
 }`;
 const fragment=`uniform sampler2D sceneDepth;uniform vec2 resolution;uniform float opacity;uniform float pass;uniform float generationOpacity;varying float density;varying float tone;
 #include <common>
 #include <logdepthbuf_pars_fragment>
 void main(){
 #include <logdepthbuf_fragment>
 float depth=log2(vFragDepth)*logDepthBufFC*.5;if(depth>texture2D(sceneDepth,gl_FragCoord.xy/resolution).r+.0000001)discard;
 float alpha=opacity*density*generationOpacity;if(alpha<.0001)discard;if(pass>.5){gl_FragColor=vec4(alpha);return;}float weight=clamp(.5+alpha*3.,.5,3.);vec3 color=vec3(.87,.90,.87)*tone;gl_FragColor=vec4(color*alpha*weight,alpha*weight);}`;
 const material=new T.ShaderMaterial({vertexShader:vertex,fragmentShader:fragment,uniforms,transparent:true,depthWrite:false,depthTest:false,side:T.FrontSide,blending:T.CustomBlending,blendSrc:T.OneFactor,blendDst:T.OneFactor,blendEquation:T.AddEquation});
 const background=new T.WebGLRenderTarget(1,1);background.depthTexture=new T.DepthTexture(1,1,T.UnsignedIntType);
 const type=renderer.extensions.has('EXT_color_buffer_float')?T.HalfFloatType:T.UnsignedByteType;
 const accumulation=new T.WebGLRenderTarget(1,1,{type,depthBuffer:false}),reveal=new T.WebGLRenderTarget(1,1,{depthBuffer:false});
 const resolve=new T.ShaderMaterial({uniforms:{background:{value:background.texture},accumulation:{value:accumulation.texture},reveal:{value:reveal.texture}},depthTest:false,depthWrite:false,vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',fragmentShader:`uniform sampler2D background;uniform sampler2D accumulation;uniform sampler2D reveal;varying vec2 vUv;void main(){vec4 a=texture2D(accumulation,vUv);float r=texture2D(reveal,vUv).r;vec3 bg=texture2D(background,vUv).rgb;gl_FragColor=vec4(bg*r+a.rgb/max(a.a,.00001)*(1.-r),1.);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
 }`});
 const quad=new T.Mesh(new T.PlaneGeometry(2,2),resolve);quadScene.add(quad);
 let worker=null,mesh=null,previousMesh=null,terrain=null,params=null,focus=[0,0],quality='auto',busy=false,requestId=0,revision=0,clock=0,nextAt=0,mixStart=0,previous=new Map(),lastStats={},dirty=true,disposed=false,revisionKey='',appliedParams=null,inFlightParams=null,inFlightKey='';
 function boot(state){worker?.terminate();worker=new Worker('orun-cloud-worker.js');terrain=state.landforms||state;worker.postMessage({type:'init',state:{seed:state.seed,landforms:{h:terrain.h,n:terrain.n,min:terrain.min,step:terrain.step}}});worker.onmessage=e=>{if(e.data.id!==requestId||disposed)return;busy=false;if(e.data.error){lastStats={...lastStats,error:e.data.error};onState(lastStats);return;}if(inFlightKey!==revisionKey){dirty=true;return;}install(e.data);};worker.onerror=e=>{busy=false;lastStats={...lastStats,error:e.message};onState(lastStats);};}
 function remove(group){if(!group)return;cloudScene.remove(group);group.traverse(o=>o.geometry?.dispose());group.userData.material?.dispose();}
 function install(field){appliedParams={...inFlightParams};remove(previousMesh);previousMesh=mesh;mesh=new T.Group();const mat=material.clone();mat.uniforms={...uniforms,generationOpacity:{value:0}};mesh.userData.material=mat;for(const c of field.chunks){const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(c.position,3));g.setAttribute('cloudDensity',new T.BufferAttribute(c.density,1));g.setAttribute('cloudTone',new T.BufferAttribute(c.tone,1));g.computeBoundingSphere();mesh.add(new T.Mesh(g,mat));}cloudScene.add(mesh);mixStart=performance.now();revision++;lastStats={...field.stats,revision,pending:false,compositing:'transparent cube faces',floatAccumulation:type===T.HalfFloatType};onState(lastStats);}
 function set(state,p,f,q){if(terrain!==(state.landforms||state))boot(state);const key=JSON.stringify([p.ecologyMode,p.cloudCover,p.cloudBase,p.cloudSpan,p.cloudThickness,p.cloudScale,p.cloudBreakup,p.windDirection,q]);if(key!==revisionKey){dirty=true;revisionKey=key;}params=p;focus=f;quality=q;uniforms.opacity.value=p.cloudOpacity;}
 function render(dt=0,enabled=true){if(disposed||!params){renderer.render(scene,camera);return;}if(!params.cloudPaused)clock+=Math.min(dt,.1);const now=performance.now();if(!busy&&(dirty||!params.cloudPaused&&now>nextAt)){dirty=false;busy=true;nextAt=now+(quality==='low'?20000:12000);inFlightParams={...params};inFlightKey=revisionKey;worker.postMessage({type:'build',id:++requestId,parameters:params,time:clock,focus,quality});}const blend=Math.min(1,(now-mixStart)/1400);if(mesh)mesh.userData.material.uniforms.generationOpacity.value=blend;if(previousMesh){previousMesh.userData.material.uniforms.generationOpacity.value=1-blend;if(blend===1){remove(previousMesh);previousMesh=null;}}uniforms.eye.value.copy(camera.position);
 if(!enabled||!mesh||params.cloudCover===0){renderer.render(scene,camera);return;}const sz=renderer.getDrawingBufferSize(new T.Vector2());if(background.width!==sz.x||background.height!==sz.y){background.setSize(sz.x,sz.y);const ratio=quality==='low'?.5:.75;for(const t of[accumulation,reveal])t.setSize(Math.max(1,Math.round(sz.x*ratio)),Math.max(1,Math.round(sz.y*ratio)));}uniforms.resolution.value.set(accumulation.width,accumulation.height);uniforms.sceneDepth.value=background.depthTexture;
 const oldColor=renderer.getClearColor(new T.Color()),oldAlpha=renderer.getClearAlpha();renderer.setRenderTarget(background);renderer.render(scene,camera);uniforms.pass.value=0;for(const group of[mesh,previousMesh])if(group){group.userData.material.blendSrc=T.OneFactor;group.userData.material.blendDst=T.OneFactor;}renderer.setClearColor(0x000000,0);renderer.setRenderTarget(accumulation);renderer.clear();renderer.render(cloudScene,camera);uniforms.pass.value=1;for(const group of[mesh,previousMesh])if(group){group.userData.material.blendSrc=T.ZeroFactor;group.userData.material.blendDst=T.OneMinusSrcAlphaFactor;}renderer.setClearColor(0xffffff,1);renderer.setRenderTarget(reveal);renderer.clear();renderer.render(cloudScene,camera);renderer.setRenderTarget(null);renderer.render(quadScene,quadCamera);renderer.setClearColor(oldColor,oldAlpha);}
 function cancel(){worker?.terminate();worker=null;terrain=null;busy=false;dirty=false;nextAt=Infinity;if(appliedParams)params={...appliedParams,cloudPaused:1};if(params)uniforms.opacity.value=params.cloudOpacity;return params;}
 function dispose(){disposed=true;worker?.terminate();remove(mesh);remove(previousMesh);box.dispose();material.dispose();quad.geometry.dispose();resolve.dispose();for(const t of[background,accumulation,reveal])t.dispose();}
 return{set,render,cancel,dispose,getState:()=>({...lastStats,pending:busy,time:clock,paused:!!params?.cloudPaused}),setTime:t=>{clock=t;dirty=true;}};
}
window.ATLAS_ORUN_CLOUD_VIEW={create};})();
