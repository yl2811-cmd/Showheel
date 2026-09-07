/* Local, camera-relative planetary systems for the fictional Federation worlds.
 * Catalogue stars are observed from the host's 3D position. Surface geography,
 * materials and phase appearance are explicitly cartographic conjectures.
 * No fetch, runtime import, image service or external texture is used.
 */
(() => {
  'use strict';
  const canvasCache = new Map();
  const clamp = (x,a,b) => Math.max(a,Math.min(b,x));
  const rad = d => Number(d||0)*Math.PI/180;
  const AU = 149597870.7, SOLAR_RADIUS_KM = 695700;
  function seedNumber(value) { let n=2166136261;for(const c of String(value))n=Math.imul(n^c.charCodeAt(0),16777619);return n>>>0; }
  function hash(x,y,z,seed) { let n=Math.imul(x,374761393)^Math.imul(y,668265263)^Math.imul(z,2147483647)^seed;n=Math.imul(n^(n>>>13),1274126177);return((n^(n>>>16))>>>0)/4294967295; }
  const smooth = x=>x*x*(3-2*x), mix=(a,b,t)=>a+(b-a)*t;
  function noise(x,y,z,seed) {
    const ix=Math.floor(x),iy=Math.floor(y),iz=Math.floor(z),fx=smooth(x-ix),fy=smooth(y-iy),fz=smooth(z-iz);
    const a=mix(hash(ix,iy,iz,seed),hash(ix+1,iy,iz,seed),fx),b=mix(hash(ix,iy+1,iz,seed),hash(ix+1,iy+1,iz,seed),fx);
    const c=mix(hash(ix,iy,iz+1,seed),hash(ix+1,iy,iz+1,seed),fx),d=mix(hash(ix,iy+1,iz+1,seed),hash(ix+1,iy+1,iz+1,seed),fx);
    return mix(mix(a,b,fy),mix(c,d,fy),fz);
  }
  function fbm(x,y,z,seed) {let sum=0,amp=.55,scale=1;for(let i=0;i<5;i++){sum+=noise(x*scale,y*scale,z*scale,seed+i*19)*amp;scale*=2.03;amp*=.47;}return sum;}
  function rgb(hex,fallback) {const h=String(hex||fallback).replace('#','');return h.length===6?[parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)]:[65,86,77];}
  function generateSurface(node,planet,year) {
    const visual=planet.visual||{},settings=visual.epochs?.[String(year)]||{},palette=visual.palette||{};
    const key=[node.id,year,JSON.stringify(visual)].join('|');if(canvasCache.has(key))return canvasCache.get(key);
    const width=1024,height=512,seed=seedNumber(visual.seed||node.id);
    const surface=document.createElement('canvas'),relief=document.createElement('canvas'),clouds=document.createElement('canvas');
    for(const c of[surface,relief,clouds]){c.width=width;c.height=height;}
    const sc=surface.getContext('2d'),rc=relief.getContext('2d'),cc=clouds.getContext('2d');
    const si=sc.createImageData(width,height),ri=rc.createImageData(width,height),ci=cc.createImageData(width,height);
    const ocean=rgb(palette.ocean,'#18364b'),land=rgb(palette.land,'#8b7761'),ice=rgb(palette.ice,'#b9cbcb'),cloud=rgb(palette.cloud,'#dbe2d7');
    const oceanFraction=clamp(Number(settings.oceanFraction??.25),0,.9),vegetation=clamp(Number(settings.vegetationFraction??.03),0,1),cover=clamp(Number(settings.cloudCover??.3),0,1);
    const fields=new Float32Array(width*height);const histogram=new Uint32Array(1000);
    // A spherical field keeps the longitude seam and poles continuous.
    for(let y=0;y<height;y++){const lat=(y/(height-1)-.5)*Math.PI,cl=Math.cos(lat),sl=Math.sin(lat);for(let x=0;x<width;x++){
      const lon=x/width*Math.PI*2,px=Math.cos(lon)*cl,py=sl,pz=Math.sin(lon)*cl;
      const value=fbm(px*2.7+3.3,py*2.7-7.2,pz*2.7+4.8,seed);fields[y*width+x]=value;histogram[clamp(Math.floor(value*1000),0,999)]++;
    }}
    // A stable land field in both epochs; changing sea/ice levels are conjectural.
    let target=width*height*oceanFraction,sum=0,threshold=.35;for(let i=0;i<1000;i++){sum+=histogram[i];if(sum>=target){threshold=i/1000;break;}}
    const frozen=Number(settings.iceFraction??(node.id.startsWith('mid')?.46:node.id==='mirren'?.32:node.id==='thessaly'?.3:.12));
    for(let y=0;y<height;y++){const lat=(y/(height-1)-.5)*Math.PI,cl=Math.cos(lat),sl=Math.sin(lat);for(let x=0;x<width;x++){
      const lon=x/width*Math.PI*2,px=Math.cos(lon)*cl,py=sl,pz=Math.sin(lon)*cl,p=y*width+x,j=p*4,n=fields[p];
      const detail=noise(px*43+5,py*43-9,pz*43+2,seed+271),moisture=noise(px*7-2,py*7+11,pz*7+6,seed+881);
      const sea=n<threshold,alt=clamp((n-threshold)/.32,0,1),polar=clamp((Math.abs(sl)-(.94-frozen*.7)+detail*.055)*9,0,1);
      let base=sea?ocean:land,shade=sea?.6+.38*clamp((n-(threshold-.18))/.18,0,1):.8+detail*.3+alt*.18;
      let r=base[0]*shade,g=base[1]*shade,b=base[2]*shade;
      if(!sea){const green=clamp((moisture-(.8-vegetation*.72))*6,0,1)*Math.min(1,vegetation*3.5)*(1-polar)*(1-alt*.65);r=mix(r,39+detail*15,green);g=mix(g,66+detail*36,green);b=mix(b,42+detail*22,green);
        if(node.id==='karen'){const volcanic=Math.pow(clamp((detail-.7)*4,0,1),2)*(.25+alt*.7);r=mix(r,40+detail*40,volcanic);g=mix(g,32,volcanic);b=mix(b,30,volcanic);}
      }
      const frost=sea?polar*.92:Math.max(polar,clamp((alt-.67)*3,0,.65));
      si.data[j]=mix(r,ice[0],frost);si.data[j+1]=mix(g,ice[1],frost);si.data[j+2]=mix(b,ice[2],frost);si.data[j+3]=255;
      const elevation=sea?40:52+alt*145+detail*15;ri.data[j]=ri.data[j+1]=ri.data[j+2]=elevation;ri.data[j+3]=255;
      const wisps=fbm(px*5.4+13+sl*.9,py*5.4+4,pz*5.4-10,seed+1557),alpha=clamp((wisps-(.67-cover*.45))*5,0,1)*.73;
      ci.data[j]=cloud[0];ci.data[j+1]=cloud[1];ci.data[j+2]=cloud[2];ci.data[j+3]=Math.round(alpha*255);
    }}
    sc.putImageData(si,0,0);rc.putImageData(ri,0,0);cc.putImageData(ci,0,0);
    const result={surface,relief,clouds,settings};canvasCache.set(key,result);if(canvasCache.size>6)canvasCache.delete(canvasCache.keys().next().value);return result;
  }
  function create({container,node,epoch:initialEpoch=3094,onState=()=>{},onSelect=()=>{},onNavigate=()=>{}}) {
    if(!container||!node?.hostStar||!node?.terraformPlanet)throw new Error('此殖民世界的恒星系资料尚未载入。');
    if(!window.THREE_SPACE)throw new Error('本地三维引擎尚未载入。');
    const{THREE:T,OrbitControls}=window.THREE_SPACE,host=node.hostStar,planet=node.terraformPlanet;
    const hostId='host:'+node.id,planetId='planet:'+node.id,resources=new Set(),events=[];
    let epoch=Number(initialEpoch)===2564?2564:3094,focusId=planetId,ready=false,destroyed=false,playing=false,simulationDays=0,width=1,height=1,raf=0,lastTime=performance.now(),lastReport=0,animation=null,exposureEV=0,brightness=1;
    const layers={stars:true,labels:true,orbits:true,routes:true,colonies:true,bounds:true,remnant:true,'light-shell':false};
    const own=r=>(resources.add(r),r),listen=(target,event,fn)=>{target.addEventListener(event,fn);events.push([target,event,fn]);};
    const renderer=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true,alpha:false,powerPreference:'high-performance',logarithmicDepthBuffer:true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setClearColor(0x010207);renderer.outputColorSpace=T.SRGBColorSpace;
    renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;renderer.autoClear=false;
    const canvas=renderer.domElement;canvas.className='space-canvas terraform-canvas';canvas.tabIndex=0;canvas.setAttribute('aria-label',node.name+'恒星系；拖动旋转、双指缩放、点击天体、Escape返回。');
    container.classList.add('space-stage');container.append(canvas);
    const caption=document.createElement('div');caption.className='space-scene-caption';const title=document.createElement('strong'),subtitle=document.createElement('span');caption.append(title,subtitle);container.append(caption);
    const hud=document.createElement('div');hud.className='space-hud';const scale=document.createElement('span'),hint=document.createElement('span');scale.className='space-scale';hint.className='space-hint';hint.textContent='拖动环看 · 滚轮靠近 · 双击天体 · Esc 上一级';hud.append(scale,hint);container.append(hud);
    const labelsRoot=document.createElement('div');labelsRoot.className='space-labels';container.append(labelsRoot);
    const scene=new T.Scene(),sky=new T.Scene(),camera=new T.PerspectiveCamera(44,1,1e-8,100),skyCamera=new T.PerspectiveCamera(44,1,.1,30);
    camera.up.set(0,0,1);const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.09;controls.rotateSpeed=.6;controls.zoomSpeed=1.05;controls.screenSpacePanning=true;
    const planetRadius=Math.max(planet.radiusKm||6371,100)/AU,hostRadius=(host.radiusSolar||1)*SOLAR_RADIUS_KM/AU,orbitAU=Number(planet.orbitAU)||planet.semiMajorKm/AU;
    const origin=new T.Vector3(),planetPosition=new T.Vector3(),starPosition=new T.Vector3();
    const geometry=own(new T.SphereGeometry(1,96,64));
    const planetMaterial=own(new T.MeshStandardMaterial({roughness:.83,metalness:.035,bumpScale:planetRadius*.025}));
    const globe=new T.Mesh(geometry,planetMaterial);globe.scale.setScalar(planetRadius);globe.userData.id=planetId;
    const cloudMaterial=own(new T.MeshStandardMaterial({transparent:true,opacity:.78,roughness:1,depthWrite:false,side:T.FrontSide}));
    const cloudMesh=new T.Mesh(geometry,cloudMaterial);cloudMesh.scale.setScalar(planetRadius*1.007);
    const planetGroup=new T.Group();planetGroup.add(globe,cloudMesh);scene.add(planetGroup);
    const atmosphereMaterial=own(new T.ShaderMaterial({transparent:true,depthWrite:false,side:T.BackSide,blending:T.AdditiveBlending,
      uniforms:{tint:{value:new T.Color('#699bbc')},sunDirection:{value:new T.Vector3(-1,0,0)},strength:{value:.42}},
      vertexShader:'#include <common>\n#include <logdepthbuf_pars_vertex>\nvarying vec3 worldNormal; varying vec3 worldPosition; void main(){vec4 p=modelMatrix*vec4(position,1.0);worldPosition=p.xyz;worldNormal=normalize(mat3(modelMatrix)*normal);gl_Position=projectionMatrix*viewMatrix*p;\n#include <logdepthbuf_vertex>\n}',
      fragmentShader:'#include <logdepthbuf_pars_fragment>\nuniform vec3 tint;uniform vec3 sunDirection;uniform float strength;varying vec3 worldNormal;varying vec3 worldPosition;void main(){\n#include <logdepthbuf_fragment>\nvec3 n=normalize(worldNormal);vec3 view=normalize(cameraPosition-worldPosition);float edge=pow(1.0-clamp(abs(dot(n,view)),0.0,1.0),3.7);float daylight=smoothstep(-0.22,0.6,dot(n,normalize(sunDirection)));gl_FragColor=vec4(tint,edge*(0.035+daylight*.65)*strength);}' }));
    const atmosphere=new T.Mesh(geometry,atmosphereMaterial);atmosphere.scale.setScalar(planetRadius*1.026);planetGroup.add(atmosphere);
    function colorIndex(ci){const c=new T.Color();if(ci<0)c.setRGB(.58,.74,1);else if(ci<.5)c.setRGB(.79+ci*.4,.86+ci*.2,1-ci*.12);else if(ci<1.2)c.setRGB(1,.96-(ci-.5)*.28,.88-(ci-.5)*.6);else c.setRGB(1,clamp(.76-(ci-1.2)*.22,.38,.76),clamp(.46-(ci-1.2)*.28,.12,.46));return c;}
    const hostColor=colorIndex(Number(host.colorIndex??.65)),starMaterial=own(new T.MeshBasicMaterial({color:hostColor})),starMesh=new T.Mesh(geometry,starMaterial);starMesh.scale.setScalar(hostRadius);starMesh.userData.id=hostId;scene.add(starMesh);
    const glowCanvas=document.createElement('canvas');glowCanvas.width=glowCanvas.height=128;const gx=glowCanvas.getContext('2d'),grad=gx.createRadialGradient(64,64,0,64,64,64);grad.addColorStop(0,'#ffffffff');grad.addColorStop(.075,'#ffffffe0');grad.addColorStop(.3,'#ffffff3a');grad.addColorStop(1,'#ffffff00');gx.fillStyle=grad;gx.fillRect(0,0,128,128);
    const glow=own(new T.CanvasTexture(glowCanvas)),starSprite=new T.Sprite(own(new T.SpriteMaterial({map:glow,color:hostColor,transparent:true,depthWrite:false,blending:T.AdditiveBlending})));starSprite.userData.id=hostId;scene.add(starSprite);
    const ambient=new T.AmbientLight(0x819aaf,.055);scene.add(ambient);
    const sunlight=new T.DirectionalLight(hostColor,3.15);scene.add(sunlight,sunlight.target);
    const orbitPoints=[];for(let i=0;i<=256;i++){const angle=i/256*Math.PI*2;orbitPoints.push(new T.Vector3(Math.cos(angle)*orbitAU,Math.sin(angle)*orbitAU*Math.cos(rad(planet.inclinationDeg)),Math.sin(angle)*orbitAU*Math.sin(rad(planet.inclinationDeg))));}
    const orbitLine=new T.Line(own(new T.BufferGeometry().setFromPoints(orbitPoints)),own(new T.LineBasicMaterial({color:0x71929d,transparent:true,opacity:.28})));scene.add(orbitLine);
    let textureSet=[];
    function applyEpochTextures(){for(const tex of textureSet){tex.dispose();resources.delete(tex);}textureSet=[];const generated=generateSurface(node,planet,epoch);
      const make=(c,color)=>{const t=own(new T.CanvasTexture(c));if(color)t.colorSpace=T.SRGBColorSpace;t.anisotropy=Math.min(renderer.capabilities.getMaxAnisotropy(),8);t.wrapS=T.RepeatWrapping;textureSet.push(t);return t;};
      planetMaterial.map=make(generated.surface,true);planetMaterial.bumpMap=make(generated.relief,false);planetMaterial.needsUpdate=true;cloudMaterial.map=make(generated.clouds,true);cloudMaterial.needsUpdate=true;
      atmosphereMaterial.uniforms.strength.value=.32+Number(generated.settings.haze??.3)*.5;
      const phase=node.epochs?.[String(epoch)]?.phase||planet.epochs?.[String(epoch)]?.phase||'阶段未登记';title.textContent=node.name+' · '+host.spectralType;
      subtitle.textContent=epoch+' · '+phase+'\n恒星系参数与地表外观：制图推定';
    }
    let starCloud=null;
    function buildSky(){const cat=window.ATLAS_STARS;if(!cat?.data)return;const binary=atob(cat.data),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);const stars=new Float32Array(bytes.buffer),stride=cat.stride||5,xyz=[],colors=[],magnitudes=[];
      const center=node.positionLy||host.positionLy||[0,0,0];
      for(let i=0;i<cat.count;i++){const off=i*stride,dx=stars[off]-center[0],dy=stars[off+1]-center[1],dz=stars[off+2]-center[2],distance=Math.hypot(dx,dy,dz);if(distance<1e-7)continue;
        const m=stars[off+3]+5*Math.log10(distance/3.261563777/10);if(!Number.isFinite(m)||m>12.5)continue;
        xyz.push(dx/distance*10,dy/distance*10,dz/distance*10);colors.push(...colorIndex(stars[off+4]).toArray());magnitudes.push(m);
      }
      const g=own(new T.BufferGeometry());g.setAttribute('position',new T.Float32BufferAttribute(xyz,3));g.setAttribute('tint',new T.Float32BufferAttribute(colors,3));g.setAttribute('apparentMag',new T.Float32BufferAttribute(magnitudes,1));
      const m=own(new T.ShaderMaterial({transparent:true,depthWrite:false,blending:T.AdditiveBlending,toneMapped:false,uniforms:{pixelRatio:{value:renderer.getPixelRatio()},exposureEV:{value:0},brightness:{value:1},limitingMagnitude:{value:9.5}},vertexShader:'attribute vec3 tint;attribute float apparentMag;varying vec3 vTint;varying float vAlpha;uniform float pixelRatio;uniform float exposureEV;uniform float brightness;uniform float limitingMagnitude;void main(){float flux=pow(10.0,-.4*(apparentMag-7.0))*pow(2.0,exposureEV);float visibility=1.0-smoothstep(limitingMagnitude-.65,limitingMagnitude+.65,apparentMag);vTint=tint;vAlpha=pow(clamp((1.0-exp(-1.5*flux))*visibility,0.0,1.0),1.3)*brightness;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);gl_PointSize=clamp(1.1+pow(flux,.22)*.65,1.1,7.8)*pixelRatio;}',fragmentShader:'varying vec3 vTint;varying float vAlpha;void main(){if(vAlpha<.001)discard;float r=length(gl_PointCoord-.5)*2.0;if(r>1.0)discard;float core=exp(-r*r*10.0);gl_FragColor=vec4(vTint,vAlpha*core);}' }));
      starCloud=new T.Points(g,m);starCloud.frustumCulled=false;sky.add(starCloud);
    }
    const labels=new Map();
    function objectFor(id){return id===hostId?{...host,id:hostId,kind:'host-star',systemId:node.id,radiusKm:hostRadius*AU,sourceCategory:'inferred',description:'为此虚构殖民世界新增的主星；位置沿用制图推定。'}:{...node,...planet,id:planetId,kind:'terraform-planet',systemId:node.id,epochs:node.epochs,sourceCategory:'inferred',description:'阶段参照正文；地形、大气外观与详细天体参数为制图推定，不表示已有真实表面测绘。'};}
    function addLabel(id,name){const el=document.createElement('button');el.type='button';el.className='space-label';el.textContent=name;listen(el,'click',()=>{onSelect(objectFor(id));focusObject(id);});labelsRoot.append(el);labels.set(id,{el,screen:null});}
    addLabel(hostId,host.name||node.name+' · 主星');addLabel(planetId,planet.name||node.name);
    const inclination=new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),rad(planet.axialTiltDeg)),pole=new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),Math.PI/2),spin=new T.Quaternion();
    function updateObjects(){const phase=rad(planet.phaseDeg)+simulationDays/(planet.periodEarthDays||365.25)*Math.PI*2;
      planetPosition.set(Math.cos(phase)*orbitAU,Math.sin(phase)*orbitAU*Math.cos(rad(planet.inclinationDeg)),Math.sin(phase)*orbitAU*Math.sin(rad(planet.inclinationDeg)));
      if(focusId===planetId&&!animation)origin.copy(planetPosition);/* origin follows the selected world; local controls stay stable */
      planetGroup.position.copy(planetPosition).sub(origin);starMesh.position.copy(starPosition).sub(origin);starSprite.position.copy(starMesh.position);orbitLine.position.copy(origin).negate();
      spin.setFromAxisAngle(new T.Vector3(0,1,0),rad(32)+simulationDays/(planet.rotationEarthDays||1)*Math.PI*2);globe.quaternion.copy(inclination).multiply(pole).multiply(spin);cloudMesh.quaternion.copy(inclination).multiply(pole).multiply(spin);
      sunlight.position.copy(starMesh.position);sunlight.target.position.copy(planetGroup.position);atmosphereMaterial.uniforms.sunDirection.value.copy(starMesh.position).sub(planetGroup.position).normalize();
      const starDistance=camera.position.distanceTo(starMesh.position),pixelScale=2*Math.tan(rad(camera.fov)/2)*starDistance/Math.max(1,height),diameterPx=hostRadius*2/pixelScale;
      starSprite.scale.setScalar(Math.max(hostRadius*6,pixelScale*10));starSprite.material.opacity=clamp(1.1-diameterPx/90,.12,.95);
      orbitLine.visible=layers.orbits&&camera.position.distanceTo(controls.target)>planetRadius*30;
      if(starCloud)starCloud.visible=layers.stars;
    }
    function scaleLabel(){const d=camera.position.distanceTo(controls.target);return d<.025?Math.round(d*AU).toLocaleString('en')+' km':d.toLocaleString('en',{maximumFractionDigits:3})+' AU';}
    function getState(){return{scene:'federation',domain:'planetary',systemId:node.id,epoch,focusId,focusName:focusId===hostId?(host.name||node.name+'主星'):(planet.name||node.name),scaleLabel:scaleLabel(),breadcrumbs:[{id:'federation',scene:'federation',label:'Federation · 600 ly'},{id:hostId,label:node.name+' 恒星系'},...(focusId===planetId?[{id:planetId,label:planet.name||node.name}]:[])],cameraSnapshot:{position:camera.position.toArray(),target:controls.target.toArray(),origin:origin.toArray(),distance:camera.position.distanceTo(controls.target),unit:'AU'},ready,playing,simulationDays,layers:{...layers},photometry:{exposureEV,brightness,limitingMagnitude:9.5+.752575*exposureEV,band:'V',referenceMagnitude:7,catalogueObserver:'host position',darkResponsePower:1.3},physicalScale:true,renderer:'WebGL 2 · Three.js',surfaceSource:'inferred'};}
    function report(force=false){const now=performance.now();if(force||now-lastReport>180){lastReport=now;scale.textContent=scaleLabel();onState(getState());}}
    function cameraRange(){const d=camera.position.distanceTo(controls.target);controls.minDistance=focusId===planetId?planetRadius*1.07:hostRadius*1.12;controls.maxDistance=1500;camera.near=Math.max(1e-10,Math.min(planetRadius*.03,d/10000));camera.far=Math.max(10,orbitAU*10,d*5);camera.updateProjectionMatrix();}
    function resolveId(id){if([hostId,host.id,node.id+'-star'].includes(id))return hostId;if([node.id,planetId,planet.id,node.id+'-planet'].includes(id))return planetId;return null;}
    function moveFocus(id,immediate=false){focusId=id;animation=null;const newOrigin=(id===planetId?planetPosition:starPosition).clone(),delta=origin.clone().sub(newOrigin);camera.position.add(delta);controls.target.add(delta);origin.copy(newOrigin);
      const distance=id===planetId?planetRadius*6.3:Math.max(orbitAU*2.7,hostRadius*12),direction=(id===planetId?new T.Vector3(-planetPosition.x,-planetPosition.y,orbitAU*.75):new T.Vector3(-.67,-.38,.63)).normalize();
      if(immediate){controls.target.set(0,0,0);camera.position.copy(direction.multiplyScalar(distance));}else{animation={start:performance.now(),fromTarget:controls.target.clone(),fromDirection:camera.position.clone().sub(controls.target).normalize(),fromDistance:Math.max(camera.position.distanceTo(controls.target),1e-8),toDistance:distance,direction};}
      cameraRange();controls.update();updateObjects();report(true);
    }
    function focusObject(id){const resolved=resolveId(id);if(resolved){moveFocus(resolved);return true;}if(id==='federation'||id==='sol'){onNavigate('federation');return true;}if(id==='archeon'||id==='archeon-star'){onNavigate('system');return true;}return false;}
    function setScene(next){if(next==='federation')onNavigate('federation');else if(next==='system'||next==='archeon')onNavigate('system');}
    function setEpoch(year){year=Number(year);if(![2564,3094].includes(year))return;if(year!==epoch){epoch=year;applyEpochTextures();}report(true);}
    function zoomBy(factor){if(!(factor>0))return;animation=null;const offset=camera.position.clone().sub(controls.target);offset.setLength(clamp(offset.length()/factor,controls.minDistance,controls.maxDistance));camera.position.copy(controls.target).add(offset);controls.update();cameraRange();report(true);}
    function reset(){simulationDays=0;updateObjects();moveFocus(hostId);}
    function back(){if(focusId===planetId)moveFocus(hostId);else onNavigate('federation');}
    function setLayer(id,value){if(id in layers){layers[id]=!!value;updateObjects();report(true);}}
    function setPlaying(value){playing=!!value;report(true);}
    function updatePhotometry(){if(starCloud){const u=starCloud.material.uniforms;u.exposureEV.value=exposureEV;u.brightness.value=brightness;u.limitingMagnitude.value=9.5+.752575*exposureEV;}renderer.toneMappingExposure=1.12*brightness*Math.pow(2,exposureEV*.35);report(true);}
    function setExposure(value){const n=Number(value);if(!Number.isFinite(n))return;exposureEV=clamp(n,-3,3);updatePhotometry();}
    function setBrightness(value){const n=Number(value);if(!Number.isFinite(n))return;brightness=clamp(n,.5,2);updatePhotometry();}
    function search(query){const q=String(query||'').trim().toLocaleLowerCase();return[objectFor(hostId),objectFor(planetId)].filter(o=>!q||[o.name,o.id,o.spectralType,node.name].some(v=>String(v||'').toLocaleLowerCase().includes(q)));}
    function resize(){width=Math.max(1,container.clientWidth);height=Math.max(1,container.clientHeight);renderer.setSize(width,height,false);camera.aspect=skyCamera.aspect=width/height;camera.updateProjectionMatrix();skyCamera.updateProjectionMatrix();report(true);}
    const projected=new T.Vector3(),cameraDirection=new T.Vector3();
    function updateLabels(){camera.getWorldDirection(cameraDirection);for(const[id,item]of labels){const position=id===hostId?starMesh.position:planetGroup.position;projected.copy(position).project(camera);const facing=position.clone().sub(camera.position).dot(cameraDirection)>0;
      item.el.hidden=!layers.labels||!facing||projected.z<-1||projected.z>1||Math.abs(projected.x)>1.08||Math.abs(projected.y)>1.08;
      const x=(projected.x*.5+.5)*width,y=(-projected.y*.5+.5)*height;item.screen={x,y};item.el.style.left=x+'px';item.el.style.top=y+'px';item.el.classList.toggle('is-selected',id===focusId);
      if(id===planetId&&focusId===planetId&&camera.position.distanceTo(controls.target)<planetRadius*20)item.el.hidden=true;
    }}
    const raycaster=new T.Raycaster(),pointer=new T.Vector2();let down=null;
    function pick(event){const rect=canvas.getBoundingClientRect();pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObjects([globe,starMesh,starSprite],false).find(h=>h.object.visible);return hit?.object.userData.id;}
    listen(canvas,'pointerdown',e=>{animation=null;down={x:e.clientX,y:e.clientY,t:performance.now()};});
    listen(canvas,'pointerup',e=>{if(down&&Math.hypot(e.clientX-down.x,e.clientY-down.y)<6&&performance.now()-down.t<600){const id=pick(e);if(id)onSelect(objectFor(id));}down=null;});
    listen(canvas,'dblclick',e=>{const id=pick(e);if(id){focusObject(id);onSelect(objectFor(id));}});
    listen(canvas,'wheel',()=>{animation=null;});
    listen(canvas,'keydown',e=>{if(e.key==='Escape'){back();e.preventDefault();}else if(e.key==='Home'){reset();e.preventDefault();}else if(e.key==='+'||e.key==='='){zoomBy(1.6);e.preventDefault();}else if(e.key==='-'){zoomBy(1/1.6);e.preventDefault();}});
    const onChange=()=>{if(!destroyed){cameraRange();report();}};controls.addEventListener('change',onChange);
    function render(){renderer.clear();skyCamera.quaternion.copy(camera.quaternion);skyCamera.position.set(0,0,0);renderer.render(sky,skyCamera);renderer.clearDepth();renderer.render(scene,camera);}
    function frame(time){if(destroyed)return;raf=requestAnimationFrame(frame);const dt=Math.min(.05,(time-lastTime)/1000);lastTime=time;
      if(playing)simulationDays+=dt*.12;
      if(animation){const t=clamp((time-animation.start)/1000,0,1),e=t*t*(3-2*t),target=animation.fromTarget.clone().multiplyScalar(1-e),direction=animation.fromDirection.clone().lerp(animation.direction,e).normalize(),d=Math.exp(mix(Math.log(animation.fromDistance),Math.log(animation.toDistance),e));controls.target.copy(target);camera.position.copy(target).addScaledVector(direction,d);if(t>=1)animation=null;}
      controls.update();updateObjects();cameraRange();render();updateLabels();if(playing||animation)report();
    }
    function capturePng(){if(destroyed)throw new Error('此恒星系已经关闭。');updateObjects();render();updateLabels();const out=document.createElement('canvas');out.width=canvas.width;out.height=canvas.height;const ctx=out.getContext('2d');ctx.drawImage(canvas,0,0);const pr=renderer.getPixelRatio();ctx.scale(pr,pr);ctx.shadowColor='#000';ctx.shadowBlur=6;ctx.fillStyle='#dfedf0';ctx.font='20px system-ui';ctx.fillText(title.textContent,24,38);ctx.fillStyle='#9bb5bc';ctx.font='11px system-ui';ctx.fillText(subtitle.textContent.replace(/\n/g,' · '),24,62,Math.max(100,width-48));
      if(layers.labels)for(const[id,item]of labels)if(!item.el.hidden){ctx.fillStyle='#d0e2e7';ctx.font='11px system-ui';ctx.fillText(id===hostId?(host.name||node.name+'主星'):(planet.name||node.name),item.screen.x+12,item.screen.y);}
      ctx.fillStyle='#b7ced5';ctx.font='11px system-ui';ctx.fillText(scaleLabel()+' · '+epoch+' · EV '+exposureEV.toFixed(1)+' · 亮度 '+brightness.toFixed(2),24,height-30);ctx.fillStyle='#869da7';ctx.font='10px system-ui';ctx.fillText('恒星系与地表：制图推定 · 实际轨道比例 · 背景：HYG v4.1 / CC BY-SA 4.0',24,height-13,Math.max(100,width-48));return out.toDataURL('image/png');}
    const observer=typeof ResizeObserver==='function'?new ResizeObserver(()=>{if(!destroyed)resize();}):null;
    function dispose(){if(destroyed)return;destroyed=true;ready=false;cancelAnimationFrame(raf);observer?.disconnect();controls.removeEventListener('change',onChange);controls.dispose();for(const[target,event,fn]of events)target.removeEventListener(event,fn);for(const resource of resources)resource.dispose?.();resources.clear();renderer.dispose();renderer.forceContextLoss();for(const el of[canvas,caption,hud,labelsRoot])el.remove();}
    applyEpochTextures();buildSky();updateObjects();moveFocus(planetId,true);resize();ready=true;report(true);observer?.observe(container);raf=requestAnimationFrame(frame);
    return{setScene,setEpoch,focusObject,zoomBy,reset,back,setLayer,setPlaying,setExposure,setBrightness,resize,dispose,getState,search,capturePng};
  }
  window.ATLAS_TERRAFORM=Object.freeze({create,version:'1.0.0'});
})();
