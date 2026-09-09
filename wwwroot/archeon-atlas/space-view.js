/* Archeon Atlas — physical 3D scenes, local data and local Three.js only. */
(() => {
  'use strict';
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const radians = x => (Number(x) || 0) * Math.PI / 180;
  const random = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t ^= t + Math.imul(t ^ t >>> 7, 61 | t); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  function create({ container, onState = () => {}, onSelect = () => {}, onNavigate = () => {} }) {
    if (!container) throw new Error('三维视图缺少容器。');
    if (!window.THREE_SPACE || !window.ATLAS_ASTRONOMY) throw new Error('本地三维引擎或天文数据尚未载入。');
    const { THREE: T, OrbitControls } = window.THREE_SPACE;
    const data = window.ATLAS_ASTRONOMY, catalogue = window.ATLAS_STARS;
    const AU = data.constants.auKm, LY = data.constants.lyKm;
    const orientation=data.system.orientation||{rotationAxisJ2000:[1,0,0],rotationDeg:0};
    const systemOrientation=new T.Quaternion().setFromAxisAngle(new T.Vector3(...orientation.rotationAxisJ2000).normalize(),radians(orientation.rotationDeg));
    const nodes = new Map(data.nodes.map(n => [n.id, n]));
    const nebulae=new Map((data.nebulae||[]).map(n=>[n.id,n]));
    const bodies = new Map(data.systemBodies.map(n => [n.id, n]));
    const activeBodies=data.systemBodies;
    const hostId=()=>'archeon-star';
    const systemLocation=()=>nodes.get('archeon').positionLy;
    let renderer;
    try { renderer = new T.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' }); }
    catch (cause) { const e = new Error('浏览器未能启用 WebGL 2。可开启硬件加速后重新展开星空，地表地图仍可使用。'); e.friendlyError = true; e.cause = cause; throw e; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x010308); renderer.outputColorSpace = T.SRGBColorSpace;
    renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.12;
    const canvas = renderer.domElement; canvas.className = 'space-canvas'; canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', '三维星空。拖动旋转，右键拖动平移，滚轮缩放，双击天体靠近。');
    container.classList.add('space-stage'); container.append(canvas);
    const labelsRoot = document.createElement('div'); labelsRoot.className = 'space-labels'; container.append(labelsRoot);
    const reticle = document.createElement('div'); reticle.className = 'space-reticle'; reticle.hidden = true; container.append(reticle);
    const caption = document.createElement('div'); caption.className = 'space-scene-caption';
    const title = document.createElement('strong'), subtitle = document.createElement('span'); caption.append(title, subtitle); container.append(caption);
    const hud = document.createElement('div'); hud.className = 'space-hud';
    const scale = document.createElement('span'); scale.className = 'space-scale';
    const hint = document.createElement('span'); hint.className = 'space-hint'; hint.textContent = '拖动旋转 · 滚轮靠近 · 双击天体'; hud.append(scale, hint); container.append(hud);
    const scene = new T.Scene(), camera = new T.PerspectiveCamera(48, 1, .001, 10000);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = .085; controls.zoomSpeed = 1.12; controls.rotateSpeed = .58;
    controls.screenSpacePanning = true; controls.minDistance = .00004; controls.maxDistance = 2200;
    const sphereGeometry = new T.SphereGeometry(1, 80, 48);
    const resources = new Set([sphereGeometry]);
    const groups = {}; for (const id of ['stars', 'orbits', 'routes', 'colonies', 'nebulae', 'remnant', 'light-shell', 'bounds', 'bodies']) { groups[id] = new T.Group(); scene.add(groups[id]); }
    const layers = { stars: true, labels: true, orbits: true, routes: true, colonies: true, nebulae:true, remnant: true, 'light-shell': false, bounds: true, 'surface-life':true, inhabited:true, harbors:false, seasonal:true, assistance:false };
    const labels = new Map(), markers = new Map(), meshes = new Map(), positions = new Map(), orbitObjects = [], colonyRings=new Map();
    const starPositions = new Map();
    const nebulaVolumes=[];let living=null;const livingLabels=[];
    const dustDefinitions=[...nebulae.values()].slice(0,8).map(n=>{const axes=n.axesLy||[10,10,10],rotation=new T.Euler(...(n.rotationDeg||[0,0,0]).map(radians)),basis=n.orientationBasis,orientation=basis?new T.Matrix4().makeBasis(new T.Vector3(...basis.east),new T.Vector3(...basis.north),new T.Vector3(...basis.radial)):new T.Matrix4();orientation.multiply(new T.Matrix4().makeRotationFromEuler(rotation));const quaternion=new T.Quaternion().setFromRotationMatrix(orientation),physicalAxes=new T.Matrix3().setFromMatrix4(orientation.scale(new T.Vector3(...axes)));return{data:n,center:new T.Vector3(...n.positionLy),axes,inverse:physicalAxes.clone().invert(),physicalAxes,quaternion};});
    const dustGLSL=`
      float dustHash(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
      float dustNoise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(mix(dustHash(i),dustHash(i+vec3(1,0,0)),f.x),mix(dustHash(i+vec3(0,1,0)),dustHash(i+vec3(1,1,0)),f.x),f.y),mix(mix(dustHash(i+vec3(0,0,1)),dustHash(i+vec3(1,0,1)),f.x),mix(dustHash(i+vec3(0,1,1)),dustHash(i+vec3(1,1,1)),f.x),f.y),f.z);}
      float dustFbm(vec3 p){return dustNoise(p)*0.57+dustNoise(p*2.03+vec3(8.4,2.1,4.7))*.28+dustNoise(p*4.17+vec3(1.2,9.6,3.7))*.15;}
      float dustDensity(vec3 p){float edge=1.0-smoothstep(.52,1.0,length(p));vec3 q=p+vec3(sin(dot(p,vec3(4.3,2.1,1.7))),sin(dot(p,vec3(1.3,5.1,2.7))),sin(dot(p,vec3(2.3,1.1,4.7))))*.14;float broad=dustNoise(q*3.7+4.1)*.6+(.5+.5*sin(q.x*3.8+q.y*2.1+sin(q.z*4.7)))*.4;float filament=pow(.5+.5*sin(q.x*13.0+q.y*7.0+sin(q.z*9.0)+3.0*dustNoise(q*2.3)),5.0);return edge*pow(max(0.0,broad-.27)*2.2,1.55)*(.3+filament*.7);}
    `;
    function dustUniforms(){const centers=[],inverse=[],extinction=[];for(let i=0;i<8;i++){const d=dustDefinitions[i];centers.push(d?d.center:new T.Vector3());inverse.push(d?d.inverse:new T.Matrix3());extinction.push(d?(Number(d.data.extinction)||1)*8:0);}return{dustCount:{value:dustDefinitions.length},dustCenters:{value:centers},dustInverse:{value:inverse},dustExtinction:{value:extinction},dustEnabled:{value:layers.nebulae?1:0}};}
    const fract=x=>x-Math.floor(x),mix=(a,b,t)=>a+(b-a)*t;
    function dustHashCPU(x,y,z){return fract(Math.sin(x*127.1+y*311.7+z*74.7)*43758.5453);}
    function dustNoiseCPU(p){const i=p.map(Math.floor),f=p.map((x,k)=>{const q=x-i[k];return q*q*(3-2*q);}),h=(x,y,z)=>dustHashCPU(i[0]+x,i[1]+y,i[2]+z);return mix(mix(mix(h(0,0,0),h(1,0,0),f[0]),mix(h(0,1,0),h(1,1,0),f[0]),f[1]),mix(mix(h(0,0,1),h(1,0,1),f[0]),mix(h(0,1,1),h(1,1,1),f[0]),f[1]),f[2]);}
    function dustFbmCPU(p){return dustNoiseCPU(p)*.57+dustNoiseCPU(p.map((v,i)=>v*2.03+[8.4,2.1,4.7][i]))*.28+dustNoiseCPU(p.map((v,i)=>v*4.17+[1.2,9.6,3.7][i]))*.15;}
    function dustDensityCPU(p){const r=Math.hypot(...p),t=clamp((r-.52)/.48,0,1),edge=1-t*t*(3-2*t);if(!edge)return 0;const q=p.map((v,i)=>v+Math.sin(p.reduce((sum,value,j)=>sum+value*[[4.3,2.1,1.7],[1.3,5.1,2.7],[2.3,1.1,4.7]][i][j],0))*.14),broad=dustNoiseCPU(q.map(v=>v*3.7+4.1))*.6+(.5+.5*Math.sin(q[0]*3.8+q[1]*2.1+Math.sin(q[2]*4.7)))*.4,filament=Math.pow(.5+.5*Math.sin(q[0]*13+q[1]*7+Math.sin(q[2]*9)+3*dustNoiseCPU(q.map(v=>v*2.3))),5);return edge*Math.pow(Math.max(0,broad-.27)*2.2,1.55)*(.3+filament*.7);}
    function dustMagnitudeCPU(observer,star){if(!layers.nebulae)return 0;let total=0;for(const cloud of dustDefinitions){const p=observer.clone().sub(cloud.center).applyMatrix3(cloud.inverse),d=star.clone().sub(observer).applyMatrix3(cloud.inverse),a=d.lengthSq(),b=2*p.dot(d),c=p.lengthSq()-1,det=b*b-4*a*c;if(a<1e-10||det<=0)continue;const start=Math.max(0,(-b-Math.sqrt(det))/(2*a)),end=Math.min(1,(-b+Math.sqrt(det))/(2*a));if(end<=start)continue;let density=0;for(let j=0;j<5;j++){const t=mix(start,end,(j+.5)/5),physical=observer.clone().lerp(star,t);if(physical.length()<=600)density+=dustDensityCPU(p.clone().addScaledVector(d,t).toArray());}total+=(Number(cloud.data.extinction)||1)*8*density*.2*(end-start)*Math.sqrt(a);}return total;}
    const dustAttenuationGLSL=`uniform int dustCount;uniform vec3 dustCenters[8];uniform mat3 dustInverse[8];uniform float dustExtinction[8];uniform float dustEnabled;
      float dustMagnitude(vec3 observer,vec3 star){if(dustEnabled<.5)return 0.0;float total=0.0;for(int i=0;i<8;i++){if(i>=dustCount)break;vec3 p=dustInverse[i]*(observer-dustCenters[i]),d=dustInverse[i]*(star-observer);float a=dot(d,d),b=2.0*dot(p,d),c=dot(p,p)-1.0,det=b*b-4.0*a*c;if(a<1e-10||det<=0.0)continue;float nearT=max(0.0,(-b-sqrt(det))/(2.0*a)),farT=min(1.0,(-b+sqrt(det))/(2.0*a));if(farT<=nearT)continue;float density=0.0;for(int j=0;j<5;j++){float t=mix(nearT,farT,(float(j)+.5)/5.0);vec3 physical=mix(observer,star,t);if(length(physical)<=600.0)density+=dustDensity(p+d*t);}total+=dustExtinction[i]*density*.2*(farT-nearT)*sqrt(a);}return total;}
    `;
    let mode = 'federation', epoch = 3094, focusId = 'sol', playing = false, simulationDays = 0, destroyed = false, planetClose = false;
    let exposureEV=0,brightness=1;const referenceMagnitude=7,limitingMagnitude=()=>9.5+.752575*exposureEV;
    let origin = new T.Vector3(), animation = null, raf = 0, lastTime = performance.now(), lastReport = 0, lastLabels = 0, ready = false;
    let sceneChangedAt = lastTime, changing = false, width = 1, height = 1, allStars = null, starCloud = null;
    const pointer = new T.Vector2(), projected = new T.Vector3(); let down = null;
    const ambient = new T.AmbientLight(0x9eafbd, .12); scene.add(ambient);
    const sunLight = new T.DirectionalLight(0xffecd1, 2.8); scene.add(sunLight); scene.add(sunLight.target);
    function own(resource) { resources.add(resource); return resource; }
    function clearGroup(group) {
      while (group.children.length) { const child = group.children.pop(); child.parent = null; child.traverse(o => { if (o.geometry && o.geometry !== sphereGeometry) { o.geometry.dispose(); resources.delete(o.geometry); } if (o.material) for (const m of Array.isArray(o.material) ? o.material : [o.material]) { m.dispose(); resources.delete(m); } }); }
    }
    function glowTexture() {
      const c = document.createElement('canvas'); c.width = c.height = 128; const ctx = c.getContext('2d');
      const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, '#fff'); g.addColorStop(.035, '#fffffff8'); g.addColorStop(.11, '#ffffffa0'); g.addColorStop(.28, '#ffffff30'); g.addColorStop(.65, '#ffffff08'); g.addColorStop(1, '#ffffff00'); ctx.fillStyle = g; ctx.fillRect(0, 0, 128, 128);
      return own(new T.CanvasTexture(c));
    }
    const glow = glowTexture();
    const ringCanvas=document.createElement('canvas');ringCanvas.width=ringCanvas.height=128;const ringContext=ringCanvas.getContext('2d');ringContext.strokeStyle='#ffffff';ringContext.lineWidth=2;ringContext.beginPath();ringContext.arc(64,64,38,0,Math.PI*2);ringContext.stroke();const colonyRingTexture=own(new T.CanvasTexture(ringCanvas));
    function colorIndex(ci) {
      const c = new T.Color();
      if (ci < 0) c.setRGB(.63, .77, 1); else if (ci < .5) c.setRGB(.85 + .3 * ci, .91 + .12 * ci, 1 - ci * .14); else if (ci < 1.2) c.setRGB(1, .97 - (ci - .5) * .25, .87 - (ci - .5) * .55); else c.setRGB(1, clamp(.79 - (ci - 1.2) * .18, .45, .79), clamp(.48 - (ci - 1.2) * .22, .18, .48));
      return c;
    }
    function decodeStars() {
      if (!catalogue?.data) return;
      const binary = atob(catalogue.data), bytes = new Uint8Array(binary.length); for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      allStars = new Float32Array(bytes.buffer);
    }
    decodeStars();
    function buildStars() {
      if(starCloud){groups.stars.remove(starCloud);starCloud.geometry.dispose();resources.delete(starCloud.geometry);starCloud.material.dispose();resources.delete(starCloud.material);starCloud=null;}if (!allStars) return;
      const count = catalogue.count, stride = catalogue.stride || 5, xyz = new Float32Array(count * 3), physical = new Float32Array(count*3), colors = new Float32Array(count * 3), magnitudes = new Float32Array(count);
      const center = mode === 'system' ? new T.Vector3(...systemLocation()) : origin;
      for (let i = 0; i < count; i++) {
        const off = i * stride, p = new T.Vector3(allStars[off], allStars[off + 1], allStars[off + 2]).sub(center);
        if (mode === 'system') p.multiplyScalar(LY/AU);
        xyz.set(p.toArray(), i * 3);physical.set([allStars[off],allStars[off+1],allStars[off+2]],i*3); const col = colorIndex(allStars[off + 4]); colors.set(col.toArray(), i * 3);
        magnitudes[i] = allStars[off + 3];
      }
      const g = own(new T.BufferGeometry()); g.setAttribute('position', new T.BufferAttribute(xyz, 3));g.setAttribute('physicalPosition',new T.BufferAttribute(physical,3)); g.setAttribute('color', new T.BufferAttribute(colors, 3)); g.setAttribute('absoluteMagnitude', new T.BufferAttribute(magnitudes, 1));
      const m = own(new T.ShaderMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { pixelRatio: { value: renderer.getPixelRatio() }, observerLy:{value:new T.Vector3()}, limitingMagnitude:{value:limitingMagnitude()},exposureEV:{value:exposureEV},brightness:{value:brightness},referenceMagnitude:{value:referenceMagnitude},...dustUniforms() },
        vertexShader: dustGLSL+dustAttenuationGLSL+'attribute vec3 color;attribute vec3 physicalPosition;attribute float absoluteMagnitude;varying vec3 vColor;varying float vIntensity;varying float vCore;uniform vec3 observerLy;uniform float pixelRatio;uniform float limitingMagnitude;uniform float exposureEV;uniform float brightness;uniform float referenceMagnitude;void main(){float distancePc=max(length(physicalPosition-observerLy)/3.261563777,0.00001);float apparentMagnitude=absoluteMagnitude+5.0*log(distancePc)/log(10.0)-5.0+dustMagnitude(observerLy,physicalPosition);float flux=pow(10.0,-0.4*(apparentMagnitude-referenceMagnitude))*pow(2.0,exposureEV);float visibility=1.0-smoothstep(limitingMagnitude-0.65,limitingMagnitude+0.65,apparentMagnitude);vIntensity=pow((1.0-exp(-flux*1.5))*visibility,1.3)*brightness;vCore=clamp(flux*.3,0.0,1.0);vColor=color;vec4 mv=modelViewMatrix*vec4(position,1.0);gl_Position=projectionMatrix*mv;gl_PointSize=clamp((1.4+1.35*sqrt(max(0.0,limitingMagnitude-apparentMagnitude)))*pixelRatio,1.0,18.0);}',
        fragmentShader: 'varying vec3 vColor;varying float vIntensity;varying float vCore;void main(){float r=length(gl_PointCoord-0.5)*2.0;if(r>1.0||vIntensity<0.0002)discard;float core=exp(-r*r*80.0);float a=(exp(-r*r*7.0)*0.55+core*1.3)*vIntensity;gl_FragColor=vec4(mix(vColor,vec3(1.0),core*vCore*.8),a);}' }));
      starCloud = new T.Points(g, m); starCloud.frustumCulled = false; groups.stars.add(starCloud);
    }
    function marker(id, color, group = groups.colonies) {
      const mat = own(new T.SpriteMaterial({ map: glow, color, transparent: true, depthWrite: false, blending: T.AdditiveBlending, opacity: 1,toneMapped:false }));
      const s = new T.Sprite(mat); s.userData.id = id; group.add(s); markers.set(id, s); return s;
    }
    function label(object, extra = '') {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'space-label'; b.textContent = object.name;
      const small = document.createElement('small'); small.textContent = extra; if (extra) b.append(small);
      b.addEventListener('pointerdown', e => e.stopPropagation());
      b.addEventListener('click', e => { e.stopPropagation(); select(object.id); });
      b.addEventListener('dblclick', e => { e.stopPropagation(); focusObject(object.id); });
      const leader=document.createElement('div');leader.className='space-label-leader';labelsRoot.append(leader,b); labels.set(object.id, { element: b, leader, object, screen: null }); return b;
    }
    function line(points, color, opacity, group, dashed = false) {
      const geometry = own(new T.BufferGeometry().setFromPoints(points));
      const material = own(dashed ? new T.LineDashedMaterial({ color, transparent: true, opacity, dashSize: 3, gapSize: 2, depthWrite: false }) : new T.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false }));
      const object = new T.Line(geometry, material); if (dashed) object.computeLineDistances(); group.add(object); return object;
    }
    function ring(radius, center, color, opacity, group, axis = 2) {
      const ps = []; for (let i = 0; i <= 256; i++) { const a = i / 256 * Math.PI * 2, v = axis === 2 ? new T.Vector3(Math.cos(a), Math.sin(a), 0) : axis === 1 ? new T.Vector3(Math.cos(a), 0, Math.sin(a)) : new T.Vector3(0, Math.cos(a), Math.sin(a)); ps.push(v.multiplyScalar(radius).add(center)); } return line(ps, color, opacity, group);
    }
    const nodeVisible = node => !node || node.epochs?.[String(epoch)]?.visible !== false;
    function syncProjectVisibility() {
      for(const node of data.nodes){const visible=nodeVisible(node);const sprite=markers.get(node.id),ring=colonyRings.get(node.id);if(sprite)sprite.visible=visible;if(ring)ring.visible=visible;}
      if(selectedId && nodes.has(selectedId) && !nodeVisible(nodes.get(selectedId)))selectedId=null;
    }
    function statusColor(node) {
      const status = node.epochs?.[String(epoch)]?.status || '';
      return /interrupted|isolated|lost|unknown|silence|unconfirmed/.test(status) ? 0xc39383 : /project|early|survey|seed|atmosphere/.test(status) ? 0xd6bd85 : node.id === 'sol' ? 0xf3e3bd : 0x88cddd;
    }
    function buildRoutes() {
      clearGroup(groups.routes);
      for (const route of data.routes || []) {
        const from = nodes.get(route.from), to = nodes.get(route.to); if (!from || !to || !nodeVisible(from) || !nodeVisible(to) || route.epochs?.[String(epoch)]?.visible===false) continue;
        const ps = (route.pointsLy || [from.positionLy, to.positionLy]).map(p => new T.Vector3(...p).sub(origin));
        const status = route.epochs?.[String(epoch)]?.status || '', interrupted = /interrupted|lost|closed/.test(status);
        line(ps, interrupted ? 0xa56a60 : /planned/.test(status) ? 0x77918e : 0x67959f, interrupted ? .44 : .26, groups.routes, interrupted || /planned|inferred/.test(status) || route.sourceCategory==='inferred');
      }
    }
    function buildRemnant() {
      clearGroup(groups.remnant);
      if (mode === 'federation' && epoch < 2570) return;
      const physicalRadius = data.supernova.remnantRadiusLy || 2;
      const sightline = new T.Vector3(...nodes.get('betelgeuse').positionLy).sub(new T.Vector3(...systemLocation()));
      const center = mode === 'system' ? sightline.clone().multiplyScalar(LY/AU) : new T.Vector3(...nodes.get('betelgeuse').positionLy).sub(origin);
      const r = mode === 'system' ? physicalRadius*LY/AU : physicalRadius;
      // Emitting gas is integrated through a broken, turbulent shell. No orbit-like lines.
      const geometry=own(new T.BoxGeometry(2,2,2)),material=own(new T.ShaderMaterial({transparent:true,depthWrite:false,depthTest:true,side:T.BackSide,blending:T.AdditiveBlending,toneMapped:false,
        uniforms:{cameraLocal:{value:new T.Vector3()},exposureScale:{value:1}},
        vertexShader:'varying vec3 localPoint;void main(){localPoint=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader:dustGLSL+`varying vec3 localPoint;uniform vec3 cameraLocal;uniform float exposureScale;
          vec4 remnantGas(vec3 p){
            float edge=1.0-smoothstep(.80,1.0,length(p));if(edge<=0.0)return vec4(0.0);
            vec3 q=vec3(p.x,p.y/0.77,p.z/0.91);
            q+=.11*vec3(dustNoise(p*4.0+1.9)-.5,dustNoise(p*4.0+9.3)-.5,dustNoise(p*4.0+21.7)-.5);
            q.x+=.07*sin(p.z*4.0);q.y+=.045*sin(p.x*5.0+p.z*2.0);
            float broad=dustFbm(p*4.4+vec3(8.3,2.1,5.6));
            float radius=length(q),shellRadius=.66+.15*(broad-.45);
            float shell=exp(-pow((radius-shellRadius)/(.075+.07*broad),2.0));
            float threads=pow(1.0-abs(2.0*dustNoise(q*18.0+vec3(4.1,7.2,3.5))-1.0),5.0);
            float folds=pow(1.0-abs(2.0*dustNoise(q*9.0+vec3(10.2,1.7,8.2))-1.0),3.0);
            float openings=smoothstep(.24,.54,broad+q.x*.11-q.z*.08);
            float interior=exp(-radius*radius*4.8)*pow(max(0.0,broad-.41)*3.2,1.7)*.18;
            float density=edge*(shell*openings*(.16+.60*threads+.28*folds)+interior);
            float hydrogen=smoothstep(.53,.76,radius+.12*(broad-.5)+q.y*.06);
            vec3 oxygen=vec3(.085,.53,.42),halpha=vec3(.52,.075,.13),violet=vec3(.27,.20,.32);
            vec3 spectrum=mix(oxygen,halpha,hydrogen);spectrum=mix(spectrum,violet,clamp((.42-broad)*2.0+radius*.1,0.0,.55));
            return vec4(spectrum,density);
          }
          void main(){
            vec3 direction=normalize(localPoint-cameraLocal),inv=1.0/(direction+vec3(.0000001));vec3 a=(-vec3(1.0)-cameraLocal)*inv,b=(vec3(1.0)-cameraLocal)*inv,lo=min(a,b),hi=max(a,b);
            float begin=max(0.0,max(lo.x,max(lo.y,lo.z))),end=min(hi.x,min(hi.y,hi.z));if(end<=begin)discard;
            float stepLength=(end-begin)/32.0,transmission=1.0;vec3 radiance=vec3(0.0);
            for(int i=0;i<32;i++){vec3 p=cameraLocal+direction*(begin+(float(i)+.5)*stepLength);vec4 gas=remnantGas(p);float contribution=gas.a*stepLength*3.8;radiance+=gas.rgb*contribution*transmission;transmission*=exp(-contribution*.36);}
            if(dot(radiance,vec3(1.0))<.0003)discard;vec3 color=vec3(1.0)-exp(-radiance*2.4*exposureScale);gl_FragColor=vec4(color,1.0);
          }`
      }));
      const volume=new T.Mesh(geometry,material);volume.position.copy(center);volume.scale.setScalar(r);volume.rotation.set(.17,-.28,.12);groups.remnant.add(volume);
      volume.onBeforeRender=(_renderer,_scene,activeCamera)=>{material.uniforms.cameraLocal.value.copy(volume.worldToLocal(activeCamera.position.clone()));material.uniforms.exposureScale.value=Math.pow(2,exposureEV*.35)*brightness;};
    }
    function buildNebulae(){
      clearGroup(groups.nebulae);nebulaVolumes.length=0;
      const unit=mode==='system'?LY/AU:1,base=mode==='system'?new T.Vector3(...systemLocation()):origin;
      for(const definition of dustDefinitions){
        const n=definition.data,center=definition.center.clone().sub(base).multiplyScalar(unit),dark=n.nebulaType==='dark';
        const material=own(new T.ShaderMaterial({transparent:true,depthWrite:false,depthTest:true,side:T.BackSide,blending:T.AdditiveBlending,toneMapped:false,
          uniforms:{cameraLocal:{value:new T.Vector3()},physicalCenter:{value:definition.center},physicalAxes:{value:definition.physicalAxes},cloudColor:{value:new T.Color(n.colors?.[0]||(dark?'#8b8177':'#719bbb'))},cloudAccent:{value:new T.Color(n.colors?.[1]||(dark?'#524c46':'#bac3ce'))},cloudOpacity:{value:(Number(n.opacity)||.4)*Math.max(0,Number(n.reflectionStrength)||0)*4},exposureScale:{value:Math.pow(2,exposureEV*.35)*brightness}},
          vertexShader:'varying vec3 localPoint;void main(){localPoint=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
          fragmentShader:dustGLSL+`varying vec3 localPoint;uniform vec3 cameraLocal;uniform vec3 physicalCenter;uniform mat3 physicalAxes;uniform vec3 cloudColor;uniform vec3 cloudAccent;uniform float cloudOpacity;uniform float exposureScale;
            void main(){if(cloudOpacity<=0.0)discard;vec3 ray=normalize(localPoint-cameraLocal);vec3 invRay=1.0/(ray+vec3(.0000001));vec3 t1=(-vec3(1.0)-cameraLocal)*invRay,t2=(vec3(1.0)-cameraLocal)*invRay;vec3 lo=min(t1,t2),hi=max(t1,t2);float begin=max(0.0,max(lo.x,max(lo.y,lo.z))),end=min(hi.x,min(hi.y,hi.z));if(end<=begin)discard;float stepLength=(end-begin)/24.0;float alpha=0.0;vec3 light=vec3(0.0);for(int i=0;i<24;i++){vec3 p=cameraLocal+ray*(begin+(float(i)+.5)*stepLength);if(length(physicalCenter+physicalAxes*p)>600.0)continue;float density=dustDensity(p);float shell=dustDensity(p+vec3(.07,-.10,.09));float scatter=max(.1,1.0-(shell-density)*2.5);float a=(1.0-exp(-density*stepLength*1.2))*(1.0-alpha);vec3 tint=mix(cloudColor,cloudAccent,dustNoise(p*7.0+21.0)*.45);light+=tint*a*scatter;alpha+=a;}float glow=cloudOpacity*exposureScale;if(alpha<.002)discard;gl_FragColor=vec4(pow(max(light,vec3(0.0)),vec3(.65))*glow*2.2,1.0);}`
        }));
        const geometry=own(new T.BoxGeometry(2,2,2)),volume=new T.Mesh(geometry,material);volume.position.copy(center);volume.quaternion.copy(definition.quaternion);volume.scale.set(...definition.axes.map(v=>v*unit));volume.userData.nebula=n;volume.updateMatrixWorld();groups.nebulae.add(volume);nebulaVolumes.push(volume);
        if(mode==='federation'){const anchor=marker(n.id,0xb5c3d0,groups.nebulae);anchor.position.copy(center);anchor.material.opacity=0;anchor.userData.nebulaAnchor=true;label(n,n.nebulaType==='dark'?'dark molecular cloud':'dust-scattered light');}
      }
    }
    function buildBoundaries() {
      clearGroup(groups.bounds); clearGroup(groups['light-shell']);
      const earth = origin.clone().negate(); for (const r of [100, 300, 600]) ring(r, earth, 0x36545e, r === 600 ? .2 : .095, groups.bounds, 2);
      ring(600, earth, 0x36545e, .08, groups.bounds, 1);
      const center = new T.Vector3(...nodes.get('betelgeuse').positionLy).sub(origin), r = Math.max(.001, epoch - data.supernova.collapseYear);
      for (let axis = 0; axis < 3; axis++) ring(r, center, 0x779ea7, .25, groups['light-shell'], axis);
    }
    function bodyTexture(body) {
      if (body.id === 'archeon' && window.ATLAS_SPACE_TEXTURES?.archeon) {
        const texture = own(new T.TextureLoader().load(window.ATLAS_SPACE_TEXTURES.archeon, () => { if (!destroyed) renderer.render(scene, camera); }));
        texture.colorSpace = T.SRGBColorSpace; texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); return texture;
      }
      const c = document.createElement('canvas'); c.width = 1024; c.height = 512; const ctx = c.getContext('2d'), rand = random(body.id === 'fast-moon' ? 3721 : body.id === 'slow-moon' ? 8921 : 1731);
      if (body.id === 'outer-planet') {
        for (let y = 0; y < 512; y++) { const f = Math.sin(y * .067) * .2 + Math.sin(y * .21) * .055 + Math.sin(y * .012) * .15; ctx.fillStyle = `rgb(${Math.round(129 + f * 75)},${Math.round(133 + f * 57)},${Math.round(125 + f * 40)})`; ctx.fillRect(0, y, 1024, 1); }
      } else {
        ctx.fillStyle = body.id === 'fast-moon' ? '#aaaeb0' : '#a47454'; ctx.fillRect(0, 0, 1024, 512);
        if (body.id === 'slow-moon') for (let i=0;i<70;i++) { const x=rand()*1024,y=rand()*512,r=12+rand()*70,g=ctx.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,'#44372b75');g.addColorStop(1,'#55413200');ctx.fillStyle=g;ctx.fillRect(x-r,y-r,r*2,r*2); }
        for (let i = 0; i < 2300; i++) { const x = rand() * 1024, y = rand() * 512, r = .45 + Math.pow(rand(), 6) * 23, d = ctx.createRadialGradient(x-r*.16,y-r*.2,0,x,y,r); d.addColorStop(0,'#302f293e'); d.addColorStop(.66,'#45413b2c'); d.addColorStop(.88,'#e8e4d915'); d.addColorStop(1,'#d4d0c800'); ctx.fillStyle = d; ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2);ctx.fill(); }
      }
      const texture = own(new T.CanvasTexture(c)); texture.colorSpace = T.SRGBColorSpace; texture.anisotropy = 4; return texture;
    }
    function atmosphericGlow(body, parentMesh) {
      const mat = own(new T.ShaderMaterial({ transparent: true, depthWrite: false, side: T.BackSide, blending: T.AdditiveBlending,
        vertexShader: 'varying vec3 n;varying vec3 v;void main(){vec4 p=modelViewMatrix*vec4(position,1.0);n=normalize(normalMatrix*normal);v=normalize(-p.xyz);gl_Position=projectionMatrix*p;}',
        fragmentShader: 'varying vec3 n;varying vec3 v;void main(){float rim=pow(1.0-abs(dot(normalize(n),normalize(v))),4.5);gl_FragColor=vec4(0.18,0.49,0.65,rim*0.35);}' }));
      const halo = new T.Mesh(sphereGeometry, mat); halo.scale.setScalar(1.025); parentMesh.add(halo);
    }
    function cloudVeil(parentMesh) {
      const c=document.createElement('canvas');c.width=2048;c.height=1024;const ctx=c.getContext('2d'),rand=random(52191);
      for(let i=0;i<700;i++){const x=rand()*2048,y=100+rand()*820,r=8+rand()*65;const gradient=ctx.createRadialGradient(x,y,0,x,y,r);gradient.addColorStop(0,'rgba(232,242,242,0.20)');gradient.addColorStop(.5,'rgba(232,242,242,0.07)');gradient.addColorStop(1,'rgba(232,242,242,0)');ctx.save();ctx.translate(x,y);ctx.scale(1.8,.42);ctx.translate(-x,-y);ctx.fillStyle=gradient;ctx.fillRect(x-r,y-r,r*2,r*2);ctx.restore();}
      const texture=own(new T.CanvasTexture(c));texture.colorSpace=T.SRGBColorSpace;const material=own(new T.MeshStandardMaterial({map:texture,transparent:true,opacity:.42,roughness:1,depthWrite:false}));const veil=new T.Mesh(sphereGeometry,material);veil.scale.setScalar(1.006);parentMesh.add(veil);
    }
    function updateBodyPositions() {
      for (const body of activeBodies) {
        const parent = body.parent ? positions.get(body.parent) || new T.Vector3() : new T.Vector3();
        const a = radians(body.phaseDeg) + (body.periodEarthDays ? simulationDays / body.periodEarthDays * Math.PI * 2 : 0), r = (body.semiMajorKm || 0) / AU;
        const p = new T.Vector3(Math.cos(a) * r, Math.sin(a) * r * Math.cos(radians(body.inclinationDeg)), Math.sin(a) * r * Math.sin(radians(body.inclinationDeg))).applyQuaternion(systemOrientation).add(parent);
        positions.set(body.id, p);
      }
    }
    function systemOrigin(id) { return (positions.get(id) || positions.get(hostId()) || new T.Vector3()).clone(); }
    function buildSystem() {
      updateBodyPositions(); origin = systemOrigin(focusId);
      for (const body of activeBodies) {
        const star = body.id === hostId(), material = own(star ? new T.MeshBasicMaterial({ color: body.color || '#ffdcad' }) : new T.MeshStandardMaterial({ map: bodyTexture(body), color: 0xffffff, roughness: 1, metalness: 0 }));
        const mesh = new T.Mesh(sphereGeometry, material); mesh.userData.id = body.id; mesh.scale.setScalar(body.radiusKm / AU);
        mesh.userData.orientationBase=systemOrientation.clone().multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),radians(body.axialTiltDeg)).multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),Math.PI/2)));mesh.quaternion.copy(mesh.userData.orientationBase);groups.bodies.add(mesh); meshes.set(body.id, mesh);
        if (body.id === 'archeon') { atmosphericGlow(body, mesh); cloudVeil(mesh);living=window.ATLAS_LIVING?.mountGlobe({T,mesh,own,onSelect});if(living)for(const item of living.labels){const el=document.createElement('button');el.className='space-object-label';el.style.cssText='position:absolute;pointer-events:auto;font-size:11px;color:#ffdda0;background:#081412aa;border:0;padding:2px 4px;white-space:nowrap';el.textContent=item.feature.properties.name;el.onclick=()=>onSelect(item.feature);labelsRoot.append(el);livingLabels.push({...item,element:el});} mesh.rotation.y = radians(170); }
        const s = marker(body.id, body.color || (star ? 0xffce87 : 0xb2d6df), groups.bodies); s.userData.body = body;
        label(body, star ? 'K2V' : body.parent === 'archeon' ? 'moon' : '');
        if (body.semiMajorKm) {
          const points = []; for (let i = 0; i <= 256; i++) { const angle = i / 256 * Math.PI * 2, r = body.semiMajorKm / AU; points.push(new T.Vector3(Math.cos(angle)*r,Math.sin(angle)*r*Math.cos(radians(body.inclinationDeg)),Math.sin(angle)*r*Math.sin(radians(body.inclinationDeg))).applyQuaternion(systemOrientation)); }
          const orbit = line(points, body.parent === 'archeon' ? 0x587c8d : 0x415b68, body.parent === 'archeon' ? .35 : .32, groups.orbits); orbitObjects.push({ object: orbit, parent: body.parent });
        }
      }
      sunLight.visible = ambient.visible = true; buildStars(); buildNebulae(); buildRemnant(); updateSystemObjects();
    }
    function updateSystemObjects() {
      const newOrigin = systemOrigin(focusId), delta = newOrigin.clone().sub(origin); origin.copy(newOrigin);
      // The scene is always rebased to the focused body, keeping sub-km detail stable.
      for (const [id, mesh] of meshes) { const p = positions.get(id).clone().sub(origin); mesh.position.copy(p); markers.get(id).position.copy(p); }
      for (const entry of orbitObjects) entry.object.position.copy((positions.get(entry.parent) || new T.Vector3()).clone().sub(origin));
      const sun = positions.get(hostId()).clone().sub(origin); sunLight.position.copy(sun.lengthSq() > 1e-16 ? sun : new T.Vector3(1, -1, .5)); sunLight.target.position.set(0, 0, 0);
      for (const [id, mesh] of meshes) if (id !== hostId()) {const body=bodies.get(id),sidereal=id==='archeon'?1/(1/(27/24)+1/body.periodEarthDays):(body.rotationEarthDays||body.periodEarthDays||1);const angle=(id==='archeon'?radians(170):0)+simulationDays*Math.PI*2/sidereal;mesh.quaternion.copy(mesh.userData.orientationBase).multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),angle));}
      void delta;
    }
    function clearScene() {
      for (const group of Object.values(groups)) clearGroup(group);
      living=null;livingLabels.length=0;labelsRoot.replaceChildren(); labels.clear(); markers.clear(); meshes.clear(); colonyRings.clear(); orbitObjects.length = 0;nebulaVolumes.length=0;starCloud=null;
    }
    function buildFederation() {
      origin = nodes.has(focusId) ? new T.Vector3(...nodes.get(focusId).positionLy) : nebulae.has(focusId)?new T.Vector3(...nebulae.get(focusId).positionLy):starPositions.get(focusId)?.clone() || new T.Vector3();
      buildStars();
      for (const node of data.nodes) {
        const photometry=node.hostStar||{absoluteMagnitude:node.id==='betelgeuse'?-5.469:4.83,colorIndex:node.id==='betelgeuse'?1.5:.65};
        const star=marker(node.id,colorIndex(photometry.colorIndex),groups.stars);star.position.fromArray(node.positionLy).sub(origin);star.userData.photometry=photometry;
        const rm=own(new T.SpriteMaterial({map:colonyRingTexture,color:statusColor(node),transparent:true,opacity:.72,depthWrite:false})),ring=new T.Sprite(rm);ring.position.copy(star.position);groups.colonies.add(ring);colonyRings.set(node.id,ring);
        label(node, node.id === 'archeon' ? (epoch===2564?'530 ly · Axiom目的地':'530 ly · 联络未复') : node.id === 'sol' ? '0 ly' : '');
      }
      if (starPositions.has(focusId)) { const object = catalogueObject(Number(focusId.slice(5))),sprite=marker(focusId,colorIndex(object.colorIndex),groups.stars);sprite.userData.photometry=object;sprite.userData.catalogueAnchor=true;sprite.material.opacity=0;sprite.position.copy(starPositions.get(focusId)).sub(origin); label(object); }
      syncProjectVisibility(); sunLight.visible = ambient.visible = false; buildRoutes(); buildNebulae(); buildRemnant(); buildBoundaries();
    }
    function applyLayers() {
      if(starCloud)starCloud.material.uniforms.dustEnabled.value=layers.nebulae?1:0;living?.apply(layers);
      for (const [id, group] of Object.entries(groups)) {
        if (id === 'bodies') group.visible = mode === 'system';
        else if (id === 'orbits') group.visible = mode === 'system' && layers.orbits;
        else if (id === 'stars') group.visible = layers.stars;
        else if (id === 'remnant') group.visible = layers.remnant;
        else if(id==='nebulae')group.visible=layers.nebulae;
        else group.visible = mode === 'federation' && !!layers[id];
      }
    }
    function objectById(id) { return mode === 'system' ? bodies.get(id) || nodes.get(id)||nebulae.get(id) : nodes.get(id)||nebulae.get(id) || (id.startsWith('star:') ? catalogueObject(Number(id.slice(5))) : bodies.get(id)); }
    function getScaleLabel() {
      const distance = camera.position.distanceTo(controls.target);
      if (mode === 'federation') return distance >= 1 ? `${distance.toLocaleString('en', { maximumFractionDigits: 1 })} ly` : `${(distance * LY / AU).toLocaleString('en', { maximumFractionDigits: 0 })} AU`;
      return distance >= .04 ? `${distance.toLocaleString('en', { maximumFractionDigits: 3 })} AU` : `${Math.round(distance * AU).toLocaleString('en')} km`;
    }
    function getState() {
      const object = objectById(focusId), crumbs = [{ id: 'federation', scene: 'federation', label: 'Federation · 600 ly' }];
      if (mode === 'system') { crumbs.push({ id: 'archeon-star', label: 'Archeon System' }); if (focusId !== 'archeon-star') crumbs.push({ id: 'archeon', label: 'Archeon · 双月' }); if (focusId !== 'archeon-star' && focusId !== 'archeon') crumbs.push({ id: focusId, label: object?.name || focusId }); }
      else if (focusId !== 'sol') crumbs.push({ id: focusId, label: object?.name || focusId });
      return { scene: mode, epoch: mode === 'system' ? 3094 : epoch, focusId, focusName: object?.name || focusId, scaleLabel: getScaleLabel(), breadcrumbs: crumbs, ready, playing, simulationDays, planetClose, layers: { ...layers }, starCount: catalogue?.count || 0,nebulaCount:nebulae.size,photometry:{exposureEV,brightness,limitingMagnitude:limitingMagnitude(),referenceMagnitude},
        cameraSnapshot: { position: camera.position.toArray(), target: controls.target.toArray(), origin: origin.toArray(), unit: mode === 'system' ? 'AU' : 'ly', distance: camera.position.distanceTo(controls.target) }, systemGeometry:mode==='system'?{rotationDeg:orientation.rotationDeg,orbitalNormal:new T.Vector3(0,0,1).applyQuaternion(systemOrientation).toArray(),archeonPole:meshes.has('archeon')?new T.Vector3(0,1,0).applyQuaternion(meshes.get('archeon').quaternion).toArray():null,bodyPositionsAU:Object.fromEntries([...positions].map(([id,p])=>[id,p.toArray()]))}:null,renderer: 'WebGL 2 · Three.js 0.180.0', physicalScale: true };
    }
    function report(force = false) { const now = performance.now(); if (force || now - lastReport > 180) { lastReport = now; scale.textContent = getScaleLabel(); onState(getState()); } }
    function cameraRange() {
      const d = camera.position.distanceTo(controls.target); camera.near = Math.max(mode === 'system' ? 1e-10 : .000001, d / 100000); camera.far = mode === 'system' ? Math.max(1300*LY/AU, d * 100) : Math.max(4000, d * 5); camera.updateProjectionMatrix();
      controls.minDistance = mode === 'system' ? Math.max((bodies.get(focusId)?.radiusKm || 500) / AU * 1.08, 1e-7) : .000001;
      controls.maxDistance = mode === 'system' ? 100000 : 2500;
    }
    function positionCamera(distance, immediate = true) {
      const direction = camera.position.clone().sub(controls.target); if (direction.lengthSq() < 1e-10) direction.set(.56, -.8, .52); direction.normalize();
      if (immediate) { animation = null; controls.target.set(0, 0, 0); camera.position.copy(direction.multiplyScalar(distance)); }
      else animation = { start: performance.now(), duration: 850, fromPosition: camera.position.clone(), fromTarget: controls.target.clone(), toPosition: direction.multiplyScalar(distance), toTarget: new T.Vector3() };
      cameraRange(); controls.update();
    }
    function setScene(next) {
      if (!['system', 'federation'].includes(next)) return;
      if (mode === next && ready) { applyLayers(); report(true); return; }
      changing = true; mode = next; focusId = mode === 'system' ? 'archeon-star' : 'sol'; planetClose=false; clearScene();
      if (mode === 'system') { buildSystem(); camera.position.set(.42, -.7, .68); positionCamera(Math.max(3.4, (bodies.get('outer-planet')?.semiMajorKm || 4 * AU) / AU * 2.4)); }
      else { buildFederation(); camera.position.set(.62, -.92, .68); positionCamera(1550); }
      title.textContent = mode === 'system' ? 'ARCHEON SYSTEM' : 'THE NEAR STARS';
      subtitle.textContent = mode === 'system' ? 'K2V · ONE WORLD · TWO MOONS\n轨道相位示意' : `SOL-CENTERED · 600 LIGHT-YEARS · ${epoch}`;
      applyLayers(); ready = true; sceneChangedAt = performance.now(); changing = false; resize(); report(true);
    }
    function setEpoch(year) {
      if (![2564, 3094].includes(Number(year))) return; epoch = Number(year);
      const frozenPosition=camera.position.clone(),frozenTarget=controls.target.clone();animation=null;controls.enableDamping=false;controls.update();camera.position.copy(frozenPosition);controls.target.copy(frozenTarget);controls.enableDamping=true;
      if (mode === 'federation' && ready) { syncProjectVisibility(); for (const [id, ring] of colonyRings) ring.material.color.set(statusColor(nodes.get(id)));const archeonNote=labels.get('archeon')?.element.querySelector('small');if(archeonNote)archeonNote.textContent=epoch===2564?'530 ly · Axiom目的地':'530 ly · 联络未复';buildRoutes(); buildRemnant(); buildBoundaries(); subtitle.textContent = `SOL-CENTERED · 600 LIGHT-YEARS · ${epoch}`; applyLayers(); }
      if(mode==='federation'&&nodes.has(focusId)&&!nodeVisible(nodes.get(focusId)))focusObject('sol');
      report(true);
    }
    function select(id) { if (!objectById(id)||!nodeVisible(nodes.get(id))) return; onSelect(objectById(id)); for (const [key, item] of labels) item.element.classList.toggle('is-selected', key === id); selectedId = id; report(true); }
    let selectedId = null;
    function focusObject(id, options = {}) {
      if (destroyed || (nodes.has(id) && !nodeVisible(nodes.get(id)))) return;
      if (id === 'federation') { setScene('federation'); reset(); return; }
      if (id === 'surface') { onNavigate('surface'); return; }
      if (id.startsWith('star:')) {
        const index = Number(id.slice(5)), offset = index * (catalogue?.stride || 5); if (!Number.isInteger(index) || index < 0 || index >= (catalogue?.count || 0)) return;
        starPositions.set(id, new T.Vector3(allStars[offset], allStars[offset+1], allStars[offset+2])); if (mode !== 'federation') setScene('federation');
      } else if (id !== 'archeon' && bodies.has(id) && mode !== 'system') setScene('system');
      else if (!nodes.has(id) && !bodies.has(id)&&!nebulae.has(id)) return;
      // Repeated focus on the stellar Archeon marker moves seamlessly into its system.
      if (mode === 'federation' && id === 'archeon' && focusId === 'archeon') { setScene('system'); focusObject('archeon'); return; }
      const closeArcheon = mode === 'system' && id === 'archeon' && focusId === 'archeon' && !options.overview;
      const oldOrigin = origin.clone(), oldPosition = camera.position.clone(), oldTarget = controls.target.clone(); focusId = id; selectedId = id; planetClose=closeArcheon;
      if (mode === 'system') {
        if (!bodies.has(id)) { setScene('federation'); focusObject(id); return; }
        origin = systemOrigin(id); camera.position.copy(oldPosition.add(oldOrigin).sub(origin)); controls.target.copy(oldTarget.add(oldOrigin).sub(origin)); updateSystemObjects();
        const body = bodies.get(id), moons = data.systemBodies.filter(b => b.parent === 'archeon');
        const d = id === 'archeon-star' ? Math.max(3.4, (bodies.get('outer-planet')?.semiMajorKm || 4 * AU) / AU * 2.4) : id === 'archeon' ? (closeArcheon ? body.radiusKm/AU*6 : Math.max(...moons.map(m => m.semiMajorKm), body.radiusKm * 12) / AU * 3.1) : body.radiusKm / AU * 6;
        positionCamera(d, false);
        if(id==='archeon') { const daylight=positions.get('archeon-star').clone().sub(positions.get('archeon')).normalize(); const lateral=new T.Vector3(-daylight.y,daylight.x,0).multiplyScalar(.45);daylight.add(lateral).add(new T.Vector3(0,0,.3)).normalize();animation.toPosition.copy(daylight.multiplyScalar(d)); }
      } else {
        clearScene(); buildFederation(); camera.position.copy(oldPosition.add(oldOrigin).sub(origin)); controls.target.copy(oldTarget.add(oldOrigin).sub(origin));
        const catalogueDistance=id.startsWith('star:')?clamp(Math.pow(10,(10-objectById(id).absoluteMagnitude)/5)*3.261563777,.03,35):nebulae.has(id)?Math.max(...nebulae.get(id).axesLy)*3.3:35;
        positionCamera(id === 'sol' ? 1550 : id === 'betelgeuse' ? 12 : id === 'archeon' ? 18 : catalogueDistance, false); applyLayers();
      }
      onSelect(objectById(id)); sceneChangedAt = performance.now(); report(true);
    }
    function focusSurface(id){if(mode!=='system')setScene('system');focusObject('archeon',{overview:true});planetClose=true;animation=null;const mesh=meshes.get('archeon');mesh.updateWorldMatrix(true,true);const p=living?.focusPoint(id);if(!p)return;const c=mesh.getWorldPosition(new T.Vector3()),dir=p.clone().sub(c).normalize(),r=bodies.get('archeon').radiusKm/AU;controls.target.copy(c);camera.position.copy(c).addScaledVector(dir,r*3.6);camera.lookAt(c);sceneChangedAt=performance.now();cameraRange();report(true);}
    function zoomBy(factor) {
      if (!Number.isFinite(factor) || factor <= 0) return; animation = null; const d = camera.position.clone().sub(controls.target); d.multiplyScalar(1 / factor); camera.position.copy(controls.target).add(d); cameraRange(); controls.update(); maybeTransition(); report(true);
    }
    function reset() { const next = mode; ready = false; selectedId = null; setScene(next); }
    function back() { if (mode === 'system') { if (focusId === 'fast-moon' || focusId === 'slow-moon' || planetClose) focusObject('archeon',{overview:true}); else if (focusId !== 'archeon-star') focusObject('archeon-star'); else setScene('federation'); } else reset(); }
    function setLayer(id, enabled) { if (!(id in layers)) return; layers[id] = !!enabled;if(id==='nebulae'&&starCloud)starCloud.material.uniforms.dustEnabled.value=enabled?1:0;applyLayers(); updateLabels(); report(true); }
    function setPlaying(value) { playing = !!value; report(true); }
    function setExposure(value){if(!Number.isFinite(Number(value)))return;exposureEV=clamp(Number(value),-3,3);if(starCloud){starCloud.material.uniforms.exposureEV.value=exposureEV;starCloud.material.uniforms.limitingMagnitude.value=limitingMagnitude();}report(true);}
    function setBrightness(value){if(!Number.isFinite(Number(value)))return;brightness=clamp(Number(value),.5,2);renderer.toneMappingExposure=1.12*brightness;if(starCloud)starCloud.material.uniforms.brightness.value=brightness;report(true);}
    function starVisibility(m){const t=clamp((m-(limitingMagnitude()-.65))/1.3,0,1),visibility=1-t*t*(3-2*t),flux=Math.pow(10,-.4*(m-referenceMagnitude))*Math.pow(2,exposureEV);return Math.pow((1-Math.exp(-1.5*flux))*visibility,1.3)*brightness;}
    function resize() { if (destroyed) return; width = Math.max(1, container.clientWidth); height = Math.max(1, container.clientHeight); renderer.setSize(width, height, false); camera.aspect = width / height; cameraRange(); updateLabels(); renderer.render(scene, camera); }
    function catalogueObject(index) {
      const info = catalogue.names?.[String(index)] || {}, offset = index * (catalogue.stride || 5), xyz = [allStars[offset], allStars[offset+1], allStars[offset+2]];
      return { ...info, id: `star:${index}`, name: info.name || info.proper || `HIP ${info.hip || index}`, kind: 'star', positionLy: xyz, distanceLy: Math.hypot(...xyz),absoluteMagnitude:allStars[offset+3],colorIndex:allStars[offset+4], sourceCategory: 'catalog', description: 'HYG v4.1 · J2000 目录位置。属于六百光年内的目录恒星；未标作 Federation 殖民地。' };
    }
    function search(query) {
      const q = String(query || '').trim().toLowerCase(); if (!q) return [];
      const seen = new Set(), result = [], pool = mode === 'system' ? [...data.systemBodies, ...data.nodes,...nebulae.values()] : [...data.nodes,...nebulae.values(), ...data.systemBodies];
      for (const o of pool) if (nodeVisible(o) && !seen.has(o.id) && [o.name, o.id, ...(o.aliases || [])].map(v=>String(v||'')+' '+(window.ATLAS_I18N?.english(v)||'')).join(' ').toLowerCase().includes(q)) { seen.add(o.id); result.push(o); }
      if (catalogue) for (const [key, o] of Object.entries(catalogue.names || {})) { if (result.length >= 40) break; if ([o.name, o.proper, o.hip ? `hip ${o.hip}` : '', o.hd ? `hd ${o.hd}` : ''].map(v=>String(v||'')+' '+(window.ATLAS_I18N?.english(v)||'')).join(' ').toLowerCase().includes(q)) result.push(catalogueObject(Number(key))); }
      return result;
    }
    function visiblePosition(position) {
      projected.copy(position).project(camera); if (projected.z < -1 || projected.z > 1 || Math.abs(projected.x) > 1.08 || Math.abs(projected.y) > 1.08) return null;
      return { x: (projected.x * .5 + .5) * width, y: (-projected.y * .5 + .5) * height, z: projected.z };
    }
    function markerPosition(id) { return meshes.get(id)?.position || markers.get(id)?.position; }
    function updateMarkers() {
      if(starCloud)starCloud.material.uniforms.observerLy.value.copy(mode==='system'?new T.Vector3(...systemLocation()):origin.clone().add(camera.position));
      for(const volume of nebulaVolumes){volume.material.uniforms.cameraLocal.value.copy(volume.worldToLocal(camera.position.clone()));volume.material.uniforms.exposureScale.value=Math.pow(2,exposureEV*.35)*brightness;}
      for (const [id, sprite] of markers) {
        const d = camera.position.distanceTo(sprite.position);
        if(sprite.userData.catalogueAnchor||sprite.userData.nebulaAnchor){sprite.material.opacity=0;continue;}
        if (mode === 'system') { const body = bodies.get(id), radius = body.radiusKm / AU, angular = radius / Math.max(d, 1e-15), star = id === 'archeon-star';
          sprite.scale.setScalar(Math.max(radius * (star ? 15 : 3), d * (star ? .035 : .014))); sprite.material.opacity = star ? .8 : clamp(1 - angular / .012, 0, .9);
        } else {const photometry=sprite.userData.photometry;if(photometry){const m=photometry.absoluteMagnitude+5*Math.log10(Math.max(d/3.261563777,1e-5))-5+dustMagnitudeCPU(origin.clone().add(camera.position),origin.clone().add(sprite.position));sprite.material.opacity=photometry.historicalOnly&&epoch>=data.supernova.collapseYear?0:starVisibility(m);sprite.scale.setScalar(d*clamp((1.4+1.35*Math.sqrt(Math.max(0,limitingMagnitude()-m)))*.006,.005,.07));}else sprite.scale.setScalar(d*.017);const ring=colonyRings.get(id);if(ring)ring.scale.setScalar(d*.019);}
      }
    }
    function updateLivingLabels(){if(!living)return;living.apply(layers);living.updateView?.(camera,renderer);const mesh=meshes.get('archeon'),center=mesh.getWorldPosition(new T.Vector3()),radius=bodies.get('archeon').radiusKm/AU,close=camera.position.distanceTo(center)<radius*14,occupied=[];for(const item of livingLabels){const p=item.object.getWorldPosition(new T.Vector3()),front=p.clone().sub(center).dot(camera.position.clone().sub(p))>0,screen=visiblePosition(p);const show=close&&front&&screen&&layers.labels&&layers['surface-life'];item.element.hidden=!show;if(!show)continue;const collision=occupied.some(q=>Math.abs(q.x-screen.x)<100&&Math.abs(q.y-screen.y)<18);if(collision){item.element.hidden=true;continue;}occupied.push(screen);item.labelScreen=screen;item.element.style.left=screen.x+'px';item.element.style.top=screen.y+'px';}}
    function updateLabels() {updateLivingLabels();
      camera.updateMatrixWorld(); const occupied = [];
      const entries = [...labels.entries()].sort((a,b) => (a[0] === selectedId || a[0] === focusId ? -1 : 0) - (b[0] === selectedId || b[0] === focusId ? -1 : 0));
      for (const [id, item] of entries) {
        const p = markerPosition(id), point = p && visiblePosition(p); item.screen = point;
        let visible = !!point && nodeVisible(item.object) && layers.labels && (nebulae.has(id)?layers.nebulae:(mode === 'system' || layers.colonies));
        let placement=null;
        if(visible){const note=item.element.querySelector('small'),w=Math.min(240,Math.max(100,item.object.name.length*7.3+25,(note?.textContent.length||0)*5.2+18)),h=note?35:24;const offsets=[[11,-12],[11,24],[-w-11,-12],[11,-49],[-w-11,25],[-w-11,-49],[25,61],[-w-25,61],[25,-84],[-w-25,-84],[75,0],[-w-75,0]];let best=Infinity;
          for(const [dx,dy] of offsets){const candidate={x:clamp(point.x+dx,6,Math.max(6,width-w-6)),y:clamp(point.y+dy,6,Math.max(6,height-h-6)),w,h};let overlap=0;for(const other of occupied)overlap+=Math.max(0,Math.min(candidate.x+w,other.x+other.w)-Math.max(candidate.x,other.x))*Math.max(0,Math.min(candidate.y+h,other.y+other.h)-Math.max(candidate.y,other.y));if(overlap<best){best=overlap;placement=candidate;}if(!overlap)break;}
          if(best>0&&!nodes.has(id)&&!nebulae.has(id)&&id!==selectedId&&id!==focusId)visible=false;else occupied.push(placement);
        }
        item.element.hidden = !visible;item.leader.hidden=!visible;
        if (visible) { item.element.style.transform='none';item.element.style.left = `${placement.x}px`; item.element.style.top = `${placement.y}px`;item.labelScreen={x:placement.x+8,y:placement.y+12};const endX=point.x<placement.x?placement.x+4:point.x>placement.x+placement.w?placement.x+placement.w-4:point.x,endY=placement.y+12,dx=endX-point.x,dy=endY-point.y;item.leader.style.left=`${point.x}px`;item.leader.style.top=`${point.y}px`;item.leader.style.width=`${Math.hypot(dx,dy)}px`;item.leader.style.transform=`rotate(${Math.atan2(dy,dx)}rad)`;item.leader.hidden=Math.hypot(dx,dy)<18; }
        item.element.classList.toggle('is-selected', id === selectedId); item.element.dataset.status = item.object.epochs?.[String(epoch)]?.status || '';
      }
      const p = selectedId && markerPosition(selectedId), point = p && visiblePosition(p); reticle.hidden = !point; if (point) { reticle.style.left = `${point.x}px`; reticle.style.top = `${point.y}px`; }
    }
    function pick(event, focus = false) {
      const box = canvas.getBoundingClientRect(), x = event.clientX-box.left, y = event.clientY-box.top;if(mode==='system'&&living&&layers['surface-life']){const ray=new T.Raycaster();ray.setFromCamera(new T.Vector2(x/width*2-1,1-y/height*2),camera);const f=living.pick(ray);if(f){if(focus&&f.geometry.type==='Point')focusSurface(f.id);onSelect(f);return;}} let nearest = null, score = Infinity;
      for (const [id,sprite] of markers) { if(!sprite.visible || (nodes.has(id)&&!nodeVisible(nodes.get(id))))continue;if(sprite.userData.nebulaAnchor&&!layers.nebulae)continue;if (mode === 'federation' && !layers.colonies&&!sprite.userData.nebulaAnchor&&!sprite.userData.catalogueAnchor) continue; const p = markerPosition(id), projected = visiblePosition(p); if (!projected) continue;if(sprite.userData.catalogueAnchor){const m=sprite.userData.photometry.absoluteMagnitude+5*Math.log10(Math.max(camera.position.distanceTo(p)/3.261563777,1e-5))-5+dustMagnitudeCPU(origin.clone().add(camera.position),origin.clone().add(p));if(!layers.stars||starVisibility(m)<.015)continue;} const body = bodies.get(id), projectedRadius = mode === 'system' && body ? body.radiusKm/AU / camera.position.distanceTo(p) * height / (2 * Math.tan(radians(camera.fov/2))) : 0; const d = Math.hypot(projected.x-x,projected.y-y); if (d < Math.max(19,projectedRadius) && d / Math.max(19,projectedRadius) < score) { score = d / Math.max(19,projectedRadius); nearest = id; } }
      if(!nearest&&mode==='federation'&&layers.stars&&allStars){let distance=7;const v=new T.Vector3();for(let i=0;i<catalogue.count;i++){const offset=i*(catalogue.stride||5);v.set(allStars[offset]-origin.x,allStars[offset+1]-origin.y,allStars[offset+2]-origin.z);const apparent=allStars[offset+3]+5*Math.log10(Math.max(v.distanceTo(camera.position)/3.261563777,1e-5))-5;if(starVisibility(apparent)<.015)continue;const point=visiblePosition(v);if(!point)continue;const d=Math.hypot(point.x-x,point.y-y);if(d<distance&&starVisibility(apparent+dustMagnitudeCPU(origin.clone().add(camera.position),origin.clone().add(v)))>=.015){distance=d;nearest=`star:${i}`;}}if(nearest){const index=Number(nearest.slice(5)),offset=index*(catalogue.stride||5);starPositions.set(nearest,new T.Vector3(allStars[offset],allStars[offset+1],allStars[offset+2]));if(!markers.has(nearest)){const object=catalogueObject(index),sprite=marker(nearest,colorIndex(object.colorIndex),groups.stars);sprite.userData.photometry=object;sprite.userData.catalogueAnchor=true;sprite.material.opacity=0;sprite.position.copy(starPositions.get(nearest)).sub(origin);label(object);}}}
      if(!nearest&&mode==='federation'&&layers.nebulae){pointer.set(x/width*2-1,1-y/height*2);const raycaster=new T.Raycaster();raycaster.setFromCamera(pointer,camera);for(const hit of raycaster.intersectObjects(nebulaVolumes,false)){const volume=hit.object,ray=raycaster.ray,along=volume.position.clone().sub(ray.origin).dot(ray.direction);if(along<0)continue;const p=ray.at(along,new T.Vector3());if(p.clone().add(origin).length()>600)continue;if(dustDensityCPU(volume.worldToLocal(p).toArray())>.005){nearest=volume.userData.nebula.id;break;}}}
      if (nearest) { if (focus) focusObject(nearest); else select(nearest); }
    }
    function onPointerDown(e) { down = { x: e.clientX, y: e.clientY, t: performance.now() }; animation = null; }
    function onPointerUp(e) { if (down && Math.hypot(e.clientX-down.x,e.clientY-down.y)<5 && performance.now()-down.t<500) pick(e); down = null; }
    function onDoubleClick(e) { pick(e, true); }
    function onKey(e) { if (e.key === 'Escape') { back(); e.preventDefault(); } else if (e.key === '+' || e.key === '=') { zoomBy(1.6); e.preventDefault(); } else if (e.key === '-') { zoomBy(1/1.6); e.preventDefault(); } else if (e.key === 'Home') { reset(); e.preventDefault(); } }
    function maybeTransition() {
      if (changing || animation || performance.now()-sceneChangedAt<1200) return;
      const distance = camera.position.distanceTo(controls.target);
      if (mode === 'federation' && focusId === 'archeon' && distance < 500*AU/LY) {
        const direction=camera.position.clone().sub(controls.target).normalize(), physical=distance*LY/AU;
        setScene('system');animation=null;camera.position.copy(direction.multiplyScalar(physical));controls.target.set(0,0,0);cameraRange();controls.update();report(true);
      } else if (mode === 'system' && distance > 4000) {
        const direction=camera.position.clone().sub(controls.target).normalize(),physical=distance*AU/LY;
        setScene('federation');focusObject('archeon');animation=null;camera.position.copy(direction.multiplyScalar(physical));controls.target.set(0,0,0);cameraRange();controls.update();report(true);
      }
    }
    const onControlChange = () => { if (!destroyed) { cameraRange(); report(); } };
    controls.addEventListener('change', onControlChange);
    canvas.addEventListener('pointerdown', onPointerDown); canvas.addEventListener('pointerup', onPointerUp); canvas.addEventListener('dblclick', onDoubleClick); canvas.addEventListener('keydown', onKey);
    function frame(time) {
      if (destroyed) return; raf = requestAnimationFrame(frame); const dt = Math.min((time-lastTime)/1000,.05); lastTime = time;
      const wasAnimating=!!animation;
      if (animation) { const t = clamp((time-animation.start)/animation.duration,0,1), ease = 1-Math.pow(1-t,3); camera.position.lerpVectors(animation.fromPosition,animation.toPosition,ease); controls.target.lerpVectors(animation.fromTarget,animation.toTarget,ease); if(t>=1)animation=null; }
      if (mode === 'system' && playing) { simulationDays += dt*3; updateBodyPositions(); updateSystemObjects(); }
      controls.update(); updateMarkers(); cameraRange(); renderer.render(scene,camera);
      if (time-lastLabels>60) { updateLabels(); lastLabels=time; } maybeTransition(); if(wasAnimating&&!animation)report(true);else if (playing || animation) report();
    }
    function capturePng() {
      if (destroyed) throw new Error('三维视图已经关闭。'); updateMarkers(); updateLabels(); renderer.render(scene,camera);
      const out=document.createElement('canvas'); out.width=canvas.width;out.height=canvas.height; const ctx=out.getContext('2d');const fillTranslated=ctx.fillText.bind(ctx);ctx.fillText=(value,...args)=>fillTranslated(window.ATLAS_I18N?.t(value)??value,...args);ctx.drawImage(canvas,0,0);const pr=renderer.getPixelRatio();ctx.scale(pr,pr);ctx.textBaseline='middle';ctx.shadowColor='#000';ctx.shadowBlur=5;
      ctx.fillStyle='#d8e8e9';ctx.font='20px system-ui';ctx.fillText(title.textContent,24,35);ctx.fillStyle='#819eaa';ctx.font='10px system-ui';ctx.fillText(subtitle.textContent.replace(/\n/g,' · '),24,59);
      if(layers.labels)for(const item of livingLabels)if(!item.element.hidden&&item.labelScreen){ctx.fillStyle='#ffdda0';ctx.font='11px system-ui';ctx.fillText(item.feature.properties.name,item.labelScreen.x,item.labelScreen.y);};if(layers.labels)for(const item of labels.values())if(!item.element.hidden&&item.labelScreen){ctx.fillStyle='#bddbe3';ctx.font='11px system-ui';ctx.fillText(item.object.name,item.labelScreen.x,item.labelScreen.y);}
      ctx.fillStyle='#a4bec7';ctx.font='11px system-ui';ctx.fillText(getScaleLabel(),24,height-25);ctx.fillStyle='#63808d';ctx.font='9px system-ui';ctx.fillText('ARCHEON ATLAS · HYG v4.1 / CC BY-SA 4.0 · fictional colony placements',24,height-10);return out.toDataURL('image/png');
    }
    function restoreState(saved){
      if(!saved?.cameraSnapshot)return;const desired=saved.scene==='system'?'system':'federation';setScene(desired);setEpoch(saved.epoch||3094);const id=saved.focusId||(desired==='system'?'archeon-star':'sol');
      if(id.startsWith('star:')){const index=Number(id.slice(5)),offset=index*(catalogue.stride||5);if(index>=0&&index<catalogue.count)starPositions.set(id,new T.Vector3(allStars[offset],allStars[offset+1],allStars[offset+2]));}
      if(id.startsWith('star:')){const index=Number(id.slice(5)),offset=index*(catalogue?.stride||5);if(Number.isInteger(index)&&index>=0&&index<(catalogue?.count||0))starPositions.set(id,new T.Vector3(allStars[offset],allStars[offset+1],allStars[offset+2]));}
      if(id!==focusId){focusId=id;selectedId=id;clearScene();if(desired==='system')buildSystem();else buildFederation();}
      animation=null;playing=!!saved.playing;planetClose=!!saved.planetClose;simulationDays=saved.simulationDays||0;if(desired==='system'){updateBodyPositions();updateSystemObjects();}Object.assign(layers,saved.layers||{});if(saved.photometry){setExposure(saved.photometry.exposureEV);setBrightness(saved.photometry.brightness);}applyLayers();controls.enableDamping=false;controls.update();camera.position.fromArray(saved.cameraSnapshot.position);controls.target.fromArray(saved.cameraSnapshot.target);controls.enableDamping=true;cameraRange();camera.lookAt(controls.target);sceneChangedAt=performance.now();updateLabels();report(true);
    }
    function dispose() {
      if(destroyed)return;destroyed=true;cancelAnimationFrame(raf);controls.removeEventListener('change',onControlChange);controls.dispose();canvas.removeEventListener('pointerdown',onPointerDown);canvas.removeEventListener('pointerup',onPointerUp);canvas.removeEventListener('dblclick',onDoubleClick);canvas.removeEventListener('keydown',onKey);
      for(const r of resources)r.dispose?.();resources.clear();renderer.dispose();renderer.forceContextLoss();for(const el of [canvas,labelsRoot,reticle,caption,hud])el.remove();
    }
    setScene('federation'); raf=requestAnimationFrame(frame);
    return {setScene,setEpoch,focusObject,focusSurface,zoomBy,reset,back,setLayer,setPlaying,resize,dispose,getState,search,capturePng,restoreState,setExposure,setBrightness};
  }
  window.ATLAS_SPACE = Object.freeze({create,version:'1.0.0'});
})();
