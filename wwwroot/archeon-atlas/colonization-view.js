/* Federation research view. Local data, physical light-year coordinates, no light cones. */
(() => {
  'use strict';
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const validPosition = p => Array.isArray(p) && p.length === 3 && p.every(Number.isFinite);
  const stageNames = { home: 'EARTH', deployment: '部署', base: '基地可用', surface: '开放地表', residents: '先期住民', handover: '交接中', autonomous: '交接完成', 'local-civilization': '本地文明延续' };
  const routeColors = { survey: 0x688a9c, seed: 0xf5ca83, history: 0xa39275, service: 0x71d5c5, crosslink: 0xa8bde8 };

  function create({ container, result, epoch = 3094, onState = () => {}, onSelect = () => {}, onNavigate = () => {} }) {
    if (!container || !window.THREE_SPACE || !window.ATLAS_COLONIZATION) throw new Error('殖民推演的本地三维引擎或模型尚未载入。');
    const { THREE: T, OrbitControls } = window.THREE_SPACE;
    const catalogue = window.ATLAS_COLONIZATION_STARS || window.ATLAS_STARS;
    const resources = new Set();
    const own = value => (resources.add(value), value);
    let renderer;
    try { renderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' }); }
    catch (cause) { const error = new Error('殖民推演需要 WebGL。请启用浏览器硬件加速后重新打开星图。'); error.friendlyError = true; error.cause = cause; throw error; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x02080e);
    renderer.outputColorSpace = T.SRGBColorSpace;
    const canvas = renderer.domElement;
    canvas.className = 'colonization-canvas';
    canvas.tabIndex = 0;
    canvas.setAttribute('aria-label', 'Federation 殖民推演。拖动旋转，右键拖动平移，滚轮缩放；点击世界、飞船或航线查看详情。');
    container.classList.add('colonization-stage');
    container.append(canvas);
    const labelsRoot = document.createElement('div'); labelsRoot.className = 'colonization-labels'; container.append(labelsRoot);
    const caption = document.createElement('div'); caption.className = 'colonization-caption';
    const heading = document.createElement('strong'); heading.textContent = 'COLONIZATION STUDY';
    const subtitle = document.createElement('span'); caption.append(heading, subtitle); container.append(caption);
    const hud = document.createElement('div'); hud.className = 'colonization-hud';
    const scale = document.createElement('span'); scale.className = 'colonization-scale';
    const hint = document.createElement('span'); hint.textContent = '拖动旋转 · 滚轮缩放 · 点击世界、飞船或航线';
    hud.append(scale, hint); container.append(hud);
    const reticle = document.createElement('div'); reticle.className = 'colonization-reticle'; reticle.hidden = true; container.append(reticle);

    const scene = new T.Scene();
    const camera = new T.PerspectiveCamera(48, 1, .001, 100000);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = .085;
    controls.rotateSpeed = .58; controls.zoomSpeed = 1.12; controls.screenSpacePanning = true;
    controls.minDistance = .05; controls.maxDistance = Infinity;
    const groups = {};
    for (const id of ['stars', 'colonies', 'ships', 'candidates', 'routes', 'bounds']) { groups[id] = new T.Group(); scene.add(groups[id]); }
    const layers = { stars: true, labels: true, colonies: true, candidates: false, routes: true, survey: true, seed: true, history: true, service: true, crosslink: true, bounds: true };
    const projectObjects = new Map(), shipObjects = new Map(), routeObjects = new Map(), labelObjects = new Map();
    const currentRecords = new Map();
    const namedStars = new Map();
    let taskIndex = new Map((result.tasks || []).map(task => [task.id, task]));
    let epochValue = clamp(Number(epoch) || 3094, 2400, 3094), snapshot;
    let focusId = 'sol', selectedId = null, width = 1, height = 1, exposureEV = 0, brightness = 1;
    let destroyed = false, raf = 0, lastReport = 0, lastLabels = 0, down = null;
    let starCloud = null, starData = null, candidateCloud = null, candidateSignature = '', candidateRecords = [];
    let boundExtent = 0, selectedScreen = null;
    const raycaster = new T.Raycaster();
    const pointer = new T.Vector2();
    const projected = new T.Vector3();

    function releaseObject(object) {
      object.parent?.remove(object);
      object.traverse(child => {
        if (child.geometry) { child.geometry.dispose(); resources.delete(child.geometry); }
        if (child.material) for (const material of Array.isArray(child.material) ? child.material : [child.material]) { material.dispose(); resources.delete(material); }
      });
    }
    function texture(kind) {
      const surface = document.createElement('canvas'); surface.width = surface.height = 128;
      const ctx = surface.getContext('2d');
      if (kind === 'ship') {
        ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.moveTo(104, 64); ctx.lineTo(29, 27); ctx.lineTo(46, 64); ctx.lineTo(29, 101); ctx.closePath(); ctx.fill();
      } else {
        const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 58);
        gradient.addColorStop(0, '#ffffffff'); gradient.addColorStop(.12, '#ffffffee'); gradient.addColorStop(.26, '#ffffff66'); gradient.addColorStop(1, '#ffffff00');
        ctx.fillStyle = gradient; ctx.fillRect(0, 0, 128, 128);
        ctx.strokeStyle = '#ffffffcf'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(64, 64, 39, 0, Math.PI * 2); ctx.stroke();
      }
      return own(new T.CanvasTexture(surface));
    }
    const projectTexture = texture('project'), shipTexture = texture('ship');
    function sprite(record, group, map, color, pixels) {
      const material = own(new T.SpriteMaterial({ map, color, transparent: true, opacity: 1, depthWrite: false, depthTest: false, toneMapped: false }));
      const object = new T.Sprite(material);
      object.position.fromArray(record.positionLy); object.userData = { id: record.id, pixels };
      object.renderOrder = group === groups.ships ? 5 : 4;
      group.add(object); return object;
    }
    function line(from, to, color, opacity, dashed, group = groups.routes) {
      const geometry = own(new T.BufferGeometry().setFromPoints([new T.Vector3(...from), new T.Vector3(...to)]));
      const length = Math.hypot(...from.map((v, i) => v - to[i]));
      const material = own(dashed ? new T.LineDashedMaterial({ color, transparent: true, opacity, depthWrite: false, dashSize: Math.max(1, length / 35), gapSize: Math.max(.8, length / 55) }) : new T.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false }));
      const object = new T.Line(geometry, material); if (dashed) object.computeLineDistances(); group.add(object); return object;
    }
    function normalize(record, kind) {
      const originalKind = record.kind;
      return { ...record, kind, type: originalKind || record.type || kind, ...(kind === 'route' ? { routeKind: originalKind } : {}), ...(kind === 'ship' ? { shipKind: originalKind, task: taskIndex.get(record.taskId) || null } : {}) };
    }
    function label(record, category) {
      let item = labelObjects.get(record.id);
      if (!item) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'colonization-label';
        const name = document.createElement('span'), detail = document.createElement('small'); button.append(name, detail);
        button.addEventListener('pointerdown', event => event.stopPropagation());
        button.addEventListener('click', event => { event.stopPropagation(); select(record.id); });
        button.addEventListener('dblclick', event => { event.stopPropagation(); focusObject(record.id); });
        labelsRoot.append(button);
        item = { element: button, name, detail, record, category, screen: null }; labelObjects.set(record.id, item);
      }
      item.record = record; item.category = category;
      item.name.textContent = record.name || record.id;
      item.detail.textContent = category === 'star' ? 'HYG · 星表参照' : stageNames[record.stage] || record.status || '';
      item.element.dataset.stage = record.stage || category;
      return item;
    }
    function removeLabel(id) { const item = labelObjects.get(id); if (item) item.element.remove(); labelObjects.delete(id); }
    function projectColor(record) {
      if (record.isHome || record.stage === 'home') return 0xffdf99;
      if (record.stage === 'local-civilization') return 0xe0b5a0;
      if (['residents', 'handover', 'autonomous'].includes(record.stage)) return 0x8de1ce;
      if (record.stage === 'surface') return 0xbdd68e;
      if (record.stage === 'base') return 0x9bc8e6;
      return 0xf3c789;
    }
    function starColor(ci) {
      if (ci < 0) return new T.Color(.61, .76, 1);
      if (ci < .6) return new T.Color(.84 + ci * .25, .9, 1 - ci * .25);
      return new T.Color(1, clamp(.89 - (ci - .6) * .2, .45, .89), clamp(.75 - (ci - .6) * .3, .22, .75));
    }
    function catalogueRecord(index) {
      if (!starData || !Number.isInteger(index) || index < 0 || index >= catalogue.count) return null;
      const offset = index * (catalogue.stride || 5), info = catalogue.names?.[String(index)] || {};
      const positionLy = [starData[offset], starData[offset + 1], starData[offset + 2]];
      return { ...info, id: `star:${index}`, name: info.name || info.proper || `HIP ${info.hip || index}`, kind: 'star', type: 'star', positionLy, distanceLy: Math.hypot(...positionLy), absoluteMagnitude: starData[offset + 3], colorIndex: starData[offset + 4], sourceCategory: 'catalog', description: 'HYG v4.1 的 J2000 恒星位置，作为天文参照。目录覆盖范围不代表殖民推演边界；此标记不表示发现了行星或殖民项目。' };
    }
    function buildStars() {
      if (!catalogue?.data) return;
      const binary = atob(catalogue.data), bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      starData = new Float32Array(bytes.buffer);
      const xyz = new Float32Array(catalogue.count * 3), colors = new Float32Array(catalogue.count * 3), intensity = new Float32Array(catalogue.count);
      for (let i = 0; i < catalogue.count; i++) {
        const offset = i * (catalogue.stride || 5);
        xyz.set(starData.subarray(offset, offset + 3), i * 3); colors.set(starColor(starData[offset + 4]).toArray(), i * 3);
        intensity[i] = starData[offset + 3];
      }
      const geometry = own(new T.BufferGeometry());
      geometry.setAttribute('position', new T.BufferAttribute(xyz, 3)); geometry.setAttribute('color', new T.BufferAttribute(colors, 3)); geometry.setAttribute('absoluteMagnitude', new T.BufferAttribute(intensity, 1));
      const material = own(new T.ShaderMaterial({ transparent: true, depthWrite: false, blending: T.AdditiveBlending,
        uniforms: { gain: { value: 1 }, pixelRatio: { value: renderer.getPixelRatio() }, observerLy: { value: new T.Vector3() } },
        vertexShader: 'attribute vec3 color;attribute float absoluteMagnitude;varying vec3 vColor;varying float vIntensity;uniform float pixelRatio;uniform vec3 observerLy;void main(){float distancePc=max(length(position-observerLy)/3.261563777,.00001);float apparentMagnitude=absoluteMagnitude+5.0*log(distancePc)/log(10.0)-5.0;float flux=pow(10.0,-.4*(apparentMagnitude-9.0));float visibility=1.0-smoothstep(12.0,15.0,apparentMagnitude);vColor=color;vIntensity=(1.0-exp(-flux*.65))*visibility*.7;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);gl_PointSize=clamp(1.2+sqrt(max(0.0,15.0-apparentMagnitude))*.75,1.2,7.0)*pixelRatio;}',
        fragmentShader: 'varying vec3 vColor;varying float vIntensity;uniform float gain;void main(){float r=length(gl_PointCoord-.5)*2.;if(r>1.||vIntensity<.0001)discard;gl_FragColor=vec4(vColor,exp(-r*r*4.0)*vIntensity*gain);}' }));
      starCloud = new T.Points(geometry, material); starCloud.frustumCulled = false; groups.stars.add(starCloud);
      for (const index of Object.keys(catalogue.names || {})) {
        const record = catalogueRecord(Number(index));
        if (record?.name && !/^HIP |^HD /i.test(record.name) && (record.absoluteMagnitude < 2 || record.distanceLy < 30)) { namedStars.set(record.id, record); label(record, 'star'); }
      }
    }
    function buildBounds(extent) {
      const required = Math.max(250, extent || 0);
      const exponent = Math.pow(10, Math.floor(Math.log10(required / 3)));
      const step = [1, 2, 5, 10].map(n => n * exponent).find(n => n >= required / 3);
      const nextExtent = Math.ceil(required / step) * step;
      if (boundExtent === nextExtent) return;
      boundExtent = nextExtent;
      for (const object of [...groups.bounds.children]) releaseObject(object);
      for (let radius = step; radius <= nextExtent; radius += step) {
        const points = [];
        for (let n = 0; n <= 192; n++) { const angle = n / 192 * Math.PI * 2; points.push(new T.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0)); }
        const geometry = own(new T.BufferGeometry().setFromPoints(points));
        const material = own(new T.LineBasicMaterial({ color: 0x548493, transparent: true, opacity: .11, depthWrite: false }));
        const ring = new T.Line(geometry, material); ring.userData.radius = radius; groups.bounds.add(ring);
      }
      line([-nextExtent, 0, 0], [nextExtent, 0, 0], 0x548493, .07, false, groups.bounds);
      line([0, -nextExtent, 0], [0, nextExtent, 0], 0x548493, .07, false, groups.bounds);
    }
    function syncCandidates(records, force) {
      candidateRecords = records;
      const signature = records.map(record => record.id).join('|');
      if (!force && candidateSignature === signature) return;
      candidateSignature = signature;
      if (candidateCloud) { releaseObject(candidateCloud); candidateCloud = null; }
      if (!records.length) return;
      const positions = new Float32Array(records.length * 3);
      records.forEach((record, index) => positions.set(record.positionLy, index * 3));
      const geometry = own(new T.BufferGeometry()); geometry.setAttribute('position', new T.BufferAttribute(positions, 3));
      const material = own(new T.PointsMaterial({ color: 0x6b91a6, size: 3, sizeAttenuation: false, transparent: true, opacity: .38, depthWrite: false }));
      candidateCloud = new T.Points(geometry, material); groups.candidates.add(candidateCloud);
    }
    function syncState(force = false) {
      snapshot = window.ATLAS_COLONIZATION.stateAt(result, epochValue);
      currentRecords.clear();
      for (const record of snapshot.projects || []) {
        if (!validPosition(record.positionLy)) continue;
        const normalized = normalize(record, 'project'); currentRecords.set(record.id, normalized);
        let object = projectObjects.get(record.id);
        if (!object) { object = sprite(record, groups.colonies, projectTexture, projectColor(record), record.anchor ? 23 : 19); projectObjects.set(record.id, object); }
        object.position.fromArray(record.positionLy); object.material.color.setHex(projectColor(record));
        label(normalized, 'project');
      }
      for (const [id, object] of projectObjects) if (!currentRecords.has(id)) { releaseObject(object); projectObjects.delete(id); removeLabel(id); }
      const candidates = (snapshot.candidates || []).filter(record => validPosition(record.positionLy));
      for (const record of candidates) currentRecords.set(record.id, normalize(record, 'candidate'));
      syncCandidates(candidates, force);
      const liveRoutes = new Set();
      for (const route of snapshot.routes || []) {
        if (!validPosition(route.fromPositionLy) || !validPosition(route.toPositionLy)) continue;
        const normalized = normalize(route, 'route'); currentRecords.set(route.id, normalized); liveRoutes.add(route.id);
        let object = routeObjects.get(route.id);
        if (!object || object.userData.kind !== route.kind || force) {
          if (object) releaseObject(object);
          object = line(route.fromPositionLy, route.toPositionLy, routeColors[route.kind] || 0x84b7c1, .3, route.kind === 'history' || route.kind === 'survey');
          object.userData = { id: route.id, kind: route.kind }; routeObjects.set(route.id, object);
        }
        const regular = ['service', 'crosslink'].includes(route.kind);
        // Native WebGL line width is usually one pixel; opacity carries actual completed trip counts.
        const opacity = regular ? clamp(.2 + Math.log1p(Math.max(0, route.tripCount || 0)) * .065, .2, .82) : route.kind === 'seed' ? .62 : route.kind === 'survey' ? .22 : .25;
        object.userData.opacity = opacity;
        object.material.opacity = opacity * (route.closedYear != null && epochValue >= route.closedYear ? .38 : 1);
        if (selectedId === route.id) object.material.opacity = 1;
      }
      for (const [id, object] of routeObjects) if (!liveRoutes.has(id)) { releaseObject(object); routeObjects.delete(id); }
      const liveShips = new Set();
      for (const ship of snapshot.ships || []) {
        if (!validPosition(ship.positionLy)) continue;
        const normalized = normalize(ship, 'ship'); currentRecords.set(ship.id, normalized); liveShips.add(ship.id);
        let object = shipObjects.get(ship.id);
        if (!object) { object = sprite(ship, groups.ships, shipTexture, routeColors[ship.routeKind || ship.kind] || 0x97e7de, ship.kind === 'seed' ? 13 : 10); shipObjects.set(ship.id, object); }
        object.position.fromArray(ship.positionLy); object.userData.kind = ship.routeKind || ship.kind;
        object.material.color.setHex(routeColors[ship.routeKind || ship.kind] || 0x97e7de);
        object.userData.pixels = ship.kind === 'seed' ? 13 : 10;
      }
      for (const [id, object] of shipObjects) if (!liveShips.has(id)) { releaseObject(object); shipObjects.delete(id); }
      buildBounds(Math.max(snapshot.stats?.extentLy || 0, ...[...projectObjects.values()].map(object => object.position.length())));
      subtitle.textContent = `${epochValue.toFixed(epochValue % 1 ? 1 : 0)} CE · 上帝视角 · 三维光年坐标`;
      applyLayers(); updateMarkers(); updateLabels();
      if (selectedId) {
        const selected = objectById(selectedId);
        if (!selected) { selectedId = null; reticle.hidden = true; onSelect(null); }
      }
      report(true);
    }
    function objectById(id) { return currentRecords.get(id) || namedStars.get(id) || (String(id).startsWith('star:') ? catalogueRecord(Number(String(id).slice(5))) : null); }
    function recordPosition(record) {
      if (validPosition(record?.positionLy)) return new T.Vector3(...record.positionLy);
      if (validPosition(record?.fromPositionLy) && validPosition(record?.toPositionLy)) return new T.Vector3(...record.fromPositionLy).add(new T.Vector3(...record.toPositionLy)).multiplyScalar(.5);
      return null;
    }
    function screenPoint(position, allowOutside = false) {
      projected.copy(position).project(camera);
      if (projected.z < -1 || projected.z > 1 || (!allowOutside && (Math.abs(projected.x) > 1.03 || Math.abs(projected.y) > 1.03))) return null;
      return { x: (projected.x + 1) * width / 2, y: (1 - projected.y) * height / 2 };
    }
    function applyLayers() {
      groups.stars.visible = layers.stars; groups.colonies.visible = layers.colonies;
      groups.candidates.visible = layers.candidates; groups.routes.visible = layers.routes; groups.bounds.visible = layers.bounds;
      for (const object of routeObjects.values()) object.visible = layers[object.userData.kind] !== false;
      for (const object of shipObjects.values()) object.visible = layers[object.userData.kind] !== false;
    }
    function updateMarkers() {
      if (starCloud) starCloud.material.uniforms.observerLy.value.copy(camera.position);
      const worldPerPixel = 2 * Math.tan(camera.fov * Math.PI / 360) / height;
      for (const object of [...projectObjects.values(), ...shipObjects.values()]) {
        const selected = object.userData.id === selectedId;
        const size = camera.position.distanceTo(object.position) * worldPerPixel * object.userData.pixels * (selected ? 1.35 : 1);
        object.scale.set(size, size, 1);
      }
      for (const [id, object] of shipObjects) {
        const record = currentRecords.get(id), from = objectById(record?.fromId), to = objectById(record?.toId);
        const task = record?.task;
        let fromPosition = from?.positionLy || task?.fromPositionLy, toPosition = to?.positionLy || task?.toPositionLy;
        if (record?.phase === 'return' || record?.phase === 'returning') [fromPosition, toPosition] = [toPosition, fromPosition];
        if (validPosition(fromPosition) && validPosition(toPosition)) {
          const a = screenPoint(new T.Vector3(...fromPosition), true), b = screenPoint(new T.Vector3(...toPosition), true);
          if (a && b) object.material.rotation = Math.atan2(a.y - b.y, b.x - a.x);
        }
      }
      camera.near = Math.max(.00001, camera.position.distanceTo(controls.target) / 100000);
      camera.far = Math.max(10000, camera.position.length() + boundExtent * 4, camera.position.distanceTo(controls.target) * 20);
      camera.updateProjectionMatrix();
    }
    function updateLabels() {
      const occupied = [{ left: 0, top: 0, right: Math.min(width * .8, 470), bottom: 130 }, { left: 0, top: height - 90, right: Math.min(width, 400), bottom: height }];
      const limit = width < 700 ? 13 : 32;
      const sorted = [...labelObjects.values()].sort((a, b) => {
        const score = item => (item.record.id === selectedId ? 1000 : 0) + (item.record.id === focusId ? 500 : 0) + (item.category === 'project' ? 100 : 0) + (item.record.anchor ? 25 : 0) - (recordPosition(item.record)?.distanceTo(camera.position) || 0) / 10000;
        return score(b) - score(a);
      });
      let shown = 0;
      for (const item of sorted) {
        item.screen = null;
        const position = recordPosition(item.record), point = position && screenPoint(position);
        const visible = layers.labels && (item.category === 'star' ? layers.stars && camera.position.distanceTo(controls.target) < 650 : layers.colonies);
        if (!point || !visible || shown >= limit) { item.element.hidden = true; continue; }
        const selected = item.record.id === selectedId;
        const labelWidth = Math.min(width < 700 ? 155 : 205, Math.max(85, (item.record.name || item.record.id).length * 7 + 16));
        const labelHeight = 37;
        let placement = null;
        for (const offset of [[12, -17], [12, 9], [-labelWidth - 12, -17], [-labelWidth - 12, 10], [12, -48]]) {
          const rect = { left: point.x + offset[0], top: point.y + offset[1], right: point.x + offset[0] + labelWidth, bottom: point.y + offset[1] + labelHeight };
          if (rect.left < 5 || rect.right > width - 5 || rect.top < 5 || rect.bottom > height - 5) continue;
          if (!selected && occupied.some(old => rect.left < old.right + 6 && rect.right > old.left - 6 && rect.top < old.bottom + 3 && rect.bottom > old.top - 3)) continue;
          placement = rect; break;
        }
        if (!placement) { item.element.hidden = true; continue; }
        item.screen = { x: placement.left, y: placement.top }; item.element.hidden = false;
        item.element.style.transform = `translate(${placement.left}px,${placement.top}px)`;
        item.element.classList.toggle('is-selected', selected);
        occupied.push(placement); shown++;
      }
      selectedScreen = selectedId ? screenPoint(recordPosition(objectById(selectedId)) || new T.Vector3()) : null;
      reticle.hidden = !selectedScreen;
      if (selectedScreen) reticle.style.transform = `translate(${selectedScreen.x}px,${selectedScreen.y}px)`;
    }
    function getScaleLabel() { return `${camera.position.distanceTo(controls.target).toLocaleString('en', { maximumFractionDigits: 1 })} ly · 镜头距焦点`; }
    function getState() {
      return { scene: 'federation', domain: 'colonization', epoch: epochValue, focusId, focusName: objectById(focusId)?.name || (focusId === 'sol' ? 'Sol / Earth' : focusId), selectedId, ready: true, playing: false, planetClose: false,
        scaleLabel: getScaleLabel(), layers: { ...layers }, stats: { ...(snapshot?.stats || {}) }, starCount: catalogue?.count || 0,
        cameraSnapshot: { position: camera.position.toArray(), target: controls.target.toArray(), origin: [0, 0, 0], unit: 'ly', distance: camera.position.distanceTo(controls.target) },
        photometry: { exposureEV, brightness }, breadcrumbs: [{ id: 'federation', scene: 'federation', label: 'Federation · 殖民推演' }, ...(focusId !== 'sol' ? [{ id: focusId, label: objectById(focusId)?.name || focusId }] : [])], renderer: 'WebGL · 本地 Three.js', physicalScale: true };
    }
    function report(force = false) { if (destroyed) return; const now = performance.now(); if (force || now - lastReport > 180) { lastReport = now; scale.textContent = getScaleLabel(); onState(getState()); } }
    function select(id) {
      const record = objectById(id); if (!record) return;
      if (selectedId && routeObjects.has(selectedId)) { const old = routeObjects.get(selectedId); old.material.opacity = old.userData.opacity; }
      selectedId = id;
      if (routeObjects.has(id)) routeObjects.get(id).material.opacity = 1;
      if (record.kind === 'star' && !labelObjects.has(id)) label(record, 'star');
      updateLabels(); onSelect(record); report(true);
    }
    function segmentDistance(x, y, a, b) {
      const dx = b.x - a.x, dy = b.y - a.y, length = dx * dx + dy * dy;
      const t = length ? clamp(((x - a.x) * dx + (y - a.y) * dy) / length, 0, 1) : 0;
      return Math.hypot(x - a.x - t * dx, y - a.y - t * dy);
    }
    function pick(event) {
      const rect = canvas.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      let bestId = null, bestDistance = Infinity;
      for (const [id, object] of [...shipObjects, ...(layers.colonies ? projectObjects : [])]) {
        if (!object.visible) continue;
        const point = screenPoint(object.position); if (!point) continue;
        const distance = Math.hypot(x - point.x, y - point.y);
        if (distance < Math.max(9, object.userData.pixels * .65) && distance < bestDistance) { bestDistance = distance; bestId = id; }
      }
      if (bestId) return bestId;
      if (layers.routes) for (const [id, object] of routeObjects) {
        if (!object.visible) continue;
        const route = currentRecords.get(id), a = screenPoint(new T.Vector3(...route.fromPositionLy), true), b = screenPoint(new T.Vector3(...route.toPositionLy), true);
        if (!a || !b) continue;
        const distance = segmentDistance(x, y, a, b);
        if (distance < 6 && distance < bestDistance) { bestId = id; bestDistance = distance; }
      }
      if (bestId) return bestId;
      pointer.set(x / width * 2 - 1, 1 - y / height * 2); raycaster.setFromCamera(pointer, camera);
      raycaster.params.Points.threshold = camera.position.distanceTo(controls.target) * Math.tan(camera.fov * Math.PI / 360) * 8 / height;
      if (layers.candidates && candidateCloud) {
        const hits = raycaster.intersectObject(candidateCloud).slice(0, 100);
        for (const hit of hits) { const record = candidateRecords[hit.index], point = record && screenPoint(new T.Vector3(...record.positionLy)); if (point && Math.hypot(x - point.x, y - point.y) < 7) return record.id; }
      }
      if (layers.stars && starCloud) {
        const hits = raycaster.intersectObject(starCloud).slice(0, 100);
        for (const hit of hits) { const record = catalogueRecord(hit.index), point = record && screenPoint(new T.Vector3(...record.positionLy)); if (point && Math.hypot(x - point.x, y - point.y) < 6) return record.id; }
      }
      return null;
    }
    function focusObject(id) {
      const record = objectById(id), position = recordPosition(record); if (!position) return false;
      const offset = camera.position.clone().sub(controls.target);
      const currentDistance = offset.length();
      const targetDistance = record.kind === 'route' ? Math.max(40, (record.distanceLy || 100) * 2.3) : Math.min(currentDistance, Math.max(60, boundExtent * .14));
      offset.normalize().multiplyScalar(targetDistance);
      controls.target.copy(position); camera.position.copy(position).add(offset); focusId = id;
      controls.update(); select(id); return true;
    }
    function setEpoch(value) { const number = Number(value); if (!Number.isFinite(number)) return; const next = clamp(number, 2400, 3094); if (next === epochValue && snapshot) return; epochValue = next; syncState(); }
    function setResult(value) { if (!value) throw new Error('缺少可显示的殖民推演结果。'); result = value; taskIndex = new Map((result.tasks || []).map(task => [task.id, task])); syncState(true); }
    function setLayer(id, enabled) { if (!(id in layers)) return; layers[id] = !!enabled; applyLayers(); updateLabels(); report(true); }
    function setExposure(value) { if (!Number.isFinite(Number(value))) return; exposureEV = clamp(Number(value), -3, 3); if (starCloud) starCloud.material.uniforms.gain.value = Math.pow(2, exposureEV) * brightness; report(true); }
    function setBrightness(value) { if (!Number.isFinite(Number(value))) return; brightness = clamp(Number(value), .5, 2); if (starCloud) starCloud.material.uniforms.gain.value = Math.pow(2, exposureEV) * brightness; renderer.setClearColor(new T.Color(0x02080e).multiplyScalar(brightness)); report(true); }
    function zoomBy(factor) { if (!(Number(factor) > 0)) return; const offset = camera.position.clone().sub(controls.target).multiplyScalar(1 / Number(factor)); if (offset.length() < .05) offset.setLength(.05); camera.position.copy(controls.target).add(offset); controls.update(); updateMarkers(); updateLabels(); report(true); }
    function reset() {
      focusId = 'sol'; selectedId = null; controls.target.set(0, 0, 0);
      const distance = Math.max(650, snapshot?.stats?.extentLy || 0) * (width < 700 ? 3.6 : 2.6);
      camera.position.set(.56, -.86, .73).normalize().multiplyScalar(distance);
      controls.update(); updateMarkers(); updateLabels(); onSelect(null); report(true);
    }
    function search(query) {
      const q = String(query || '').trim().toLowerCase(); if (!q) return [];
      const results = [];
      for (const record of currentRecords.values()) if (['project', 'candidate'].includes(record.kind) && [record.id, record.name, ...(record.aliases || [])].map(v=>String(v||'')+' '+(window.ATLAS_I18N?.english(v)||'')).join(' ').toLowerCase().includes(q)) { results.push(record); if (results.length >= 40) return results; }
      for (const [index, info] of Object.entries(catalogue?.names || {})) if ([info.name, info.proper, info.hip && `HIP ${info.hip}`, info.hd && `HD ${info.hd}`].map(v=>String(v||'')+' '+(window.ATLAS_I18N?.english(v)||'')).join(' ').toLowerCase().includes(q)) { results.push(catalogueRecord(Number(index))); if (results.length >= 40) break; }
      return results;
    }
    function resize() { if (destroyed) return; width = Math.max(1, container.clientWidth); height = Math.max(1, container.clientHeight); renderer.setSize(width, height, false); camera.aspect = width / height; updateMarkers(); updateLabels(); renderer.render(scene, camera); }
    function restoreState(saved) {
      if (!saved) return;
      if (Number.isFinite(Number(saved.epoch))) setEpoch(saved.epoch);
      for (const [id, value] of Object.entries(saved.layers || {})) if (id in layers) layers[id] = !!value;
      if (saved.photometry) { setExposure(saved.photometry.exposureEV); setBrightness(saved.photometry.brightness); }
      if (saved.cameraSnapshot && validPosition(saved.cameraSnapshot.position) && validPosition(saved.cameraSnapshot.target)) {
        controls.enableDamping = false; controls.update();
        const origin = validPosition(saved.cameraSnapshot.origin) ? new T.Vector3(...saved.cameraSnapshot.origin) : new T.Vector3();
        camera.position.fromArray(saved.cameraSnapshot.position).add(origin); controls.target.fromArray(saved.cameraSnapshot.target).add(origin);
        camera.lookAt(controls.target); controls.update(); controls.enableDamping = true;
      }
      focusId = saved.focusId || 'sol'; selectedId = saved.selectedId && objectById(saved.selectedId) ? saved.selectedId : null;
      applyLayers(); updateMarkers(); updateLabels(); report(true);
    }
    function capturePng() {
      if (destroyed) throw new Error('殖民推演视图已经关闭。');
      updateMarkers(); updateLabels(); renderer.render(scene, camera);
      const output = document.createElement('canvas'); output.width = canvas.width; output.height = canvas.height;
      const ctx = output.getContext('2d');const fillTranslated=ctx.fillText.bind(ctx);ctx.fillText=(value,...args)=>fillTranslated(window.ATLAS_I18N?.t(value)??value,...args); ctx.drawImage(canvas, 0, 0); ctx.scale(renderer.getPixelRatio(), renderer.getPixelRatio());
      ctx.shadowColor = '#000'; ctx.shadowBlur = 5; ctx.textBaseline = 'top';
      ctx.fillStyle = '#d9e5e2'; ctx.font = `${width < 700 ? 17 : 21}px system-ui, "Microsoft YaHei", sans-serif`; ctx.fillText(heading.textContent, 23, 22);
      ctx.font = '10px system-ui, "Microsoft YaHei", sans-serif'; ctx.fillStyle = '#83a9b4'; ctx.fillText(subtitle.textContent, 23, 55);
      if (layers.labels) for (const item of labelObjects.values()) if (item.screen && !item.element.hidden) {
        ctx.fillStyle = item.record.id === selectedId ? '#ffffff' : item.category === 'project' ? '#d3e3df' : '#819da8';
        ctx.font = '11px system-ui, "Microsoft YaHei", sans-serif'; ctx.fillText(item.name.textContent, item.screen.x + 3, item.screen.y + 4);
        ctx.font = '9px system-ui, "Microsoft YaHei", sans-serif'; ctx.fillStyle = '#83a1a9'; ctx.fillText(item.detail.textContent, item.screen.x + 3, item.screen.y + 21);
      }
      ctx.font = '10px system-ui, "Microsoft YaHei", sans-serif'; ctx.fillStyle = '#aac4cc'; ctx.fillText(getScaleLabel(), 23, height - 42);
      ctx.fillStyle = '#648591'; ctx.font = `${width < 700 ? 8 : 9}px system-ui`; ctx.fillText('ARCHEON ATLAS · HYG v4.1 / CC BY-SA 4.0 · Model candidates are hypothetical', 23, height - 19);
      return output.toDataURL('image/png');
    }
    function onPointerDown(event) { down = { x: event.clientX, y: event.clientY, time: performance.now(), button: event.button }; }
    function onPointerUp(event) { if (!down) return; const moved = Math.hypot(event.clientX - down.x, event.clientY - down.y); const click = down.button === 0 && moved < 6 && performance.now() - down.time < 650; down = null; if (click) { const id = pick(event); if (id) select(id); } }
    function onDoubleClick(event) { const id = pick(event); if (id) focusObject(id); }
    function onKey(event) { if (event.key === '+' || event.key === '=') zoomBy(1.4); else if (event.key === '-') zoomBy(1 / 1.4); else if (event.key === 'Home') reset(); else if (event.key === 'Escape') { selectedId = null; updateLabels(); onSelect(null); report(true); } else return; event.preventDefault(); }
    function onControlChange() { updateLabels(); report(); }
    function frame(time) { if (destroyed) return; raf = requestAnimationFrame(frame); controls.update(); updateMarkers(); renderer.render(scene, camera); if (time - lastLabels > 75) { updateLabels(); lastLabels = time; } }
    canvas.addEventListener('pointerdown', onPointerDown); canvas.addEventListener('pointerup', onPointerUp); canvas.addEventListener('dblclick', onDoubleClick); canvas.addEventListener('keydown', onKey);
    controls.addEventListener('change', onControlChange);
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null; observer?.observe(container);
    function dispose() {
      if (destroyed) return; destroyed = true; cancelAnimationFrame(raf); observer?.disconnect();
      controls.removeEventListener('change', onControlChange); controls.dispose();
      canvas.removeEventListener('pointerdown', onPointerDown); canvas.removeEventListener('pointerup', onPointerUp); canvas.removeEventListener('dblclick', onDoubleClick); canvas.removeEventListener('keydown', onKey);
      for (const resource of resources) resource.dispose?.(); resources.clear(); renderer.dispose(); renderer.forceContextLoss();
      for (const element of [canvas, labelsRoot, caption, hud, reticle]) element.remove(); container.classList.remove('colonization-stage');
    }
    buildStars(); resize(); syncState(true); reset(); raf = requestAnimationFrame(frame);
    return { setEpoch, setResult, setScene: () => report(true), setPlaying: () => {}, focusObject, zoomBy, reset, back: reset, setLayer, setExposure, setBrightness, resize, dispose, getState, capturePng, search, restoreState, resolveObject: objectById };
  }
  window.ATLAS_COLONIZATION_VIEW = Object.freeze({ create });
})();
