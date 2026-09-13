'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const { spawn, spawnSync } = require('node:child_process');
const { once } = require('node:events');
let sharp;
try { sharp = require('sharp'); } catch { sharp = require('./web-build/node_modules/sharp'); }
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const root = path.resolve(option('--root', path.join(__dirname, '..')));
const output = path.resolve(option('--output', path.join(root, 'dist-web')));
const reportPath = path.resolve(option('--report', path.join(root, 'docs/web-build-report.json')));
const quota = Number(option('--quota-mb', process.env.SWA_QUOTA_MB || 250)) * 1000000;
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
const slash = name => name.split(path.sep).join('/');
const write = (relative, data) => { const file = path.join(output, relative); fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, data); };
function replace(text, before, after, label) {
  if (text.split(before).length !== 2) throw Error('Source changed; review adaptation: ' + label);
  return text.replace(before, after);
}
async function exportPages() {
  const artifacts = fs.mkdtempSync(path.join(require('node:os').tmpdir(), 'showheel-web-build-'));
  const built = spawnSync('dotnet', ['build', path.join(root, 'Showheel.csproj'), '--artifacts-path', artifacts, '--nologo'], { cwd: root, encoding: 'utf8', windowsHide: true });
  if (built.status !== 0) throw Error('Page build failed:\n' + built.stdout + built.stderr);
  const dll = path.join(artifacts, 'bin/Showheel/debug/Showheel.dll');
  const server = spawn('dotnet', [dll, '--urls', 'http://127.0.0.1:0'], { cwd: root, windowsHide: true, env: { ...process.env, ASPNETCORE_ENVIRONMENT: 'Development' }, stdio: ['ignore', 'pipe', 'pipe'] });
  let logs = '';
  const address = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Page export server did not start')), 30000);
    const read = chunk => { logs += chunk; const match = logs.match(/Now listening on: (http:\/\/127\.0\.0\.1:\d+)/); if (match) { clearTimeout(timer); resolve(match[1]); } };
    server.stdout.on('data', read); server.stderr.on('data', read);
    server.once('error', error => { clearTimeout(timer); reject(error); });
    server.once('exit', code => { clearTimeout(timer); reject(Error('Page export server exited: ' + code)); });
  });
  const pages = new Map();
  try {
    const base = await address;
    for (const file of fs.readdirSync(path.join(root, 'Pages')).filter(f => f.endsWith('.cshtml') && !f.startsWith('_') && f !== 'Error.cshtml')) {
      const page = file.slice(0, -7), route = page === 'Index' ? '/' : '/' + page;
      const response = await fetch(base + route);
      if (!response.ok) throw Error('Cannot export page ' + route);
      pages.set(page === 'Index' ? 'index.html' : page + '.html', Buffer.from(await response.text()));
    }
  } finally { server.kill(); if (server.exitCode === null) await once(server, 'exit'); }
  return pages;
}
function adapt(relative, source) {
  let text = source.toString('utf8');
  if (/archeon-atlas\/(app|river-layer|space-controller|eyrie-controller|atheria-controller|orun-controller)\.js$/.test(relative)) {
    text = text.replace(/document\.head\.append(?:Child)?\((s|script)\)/g, 'window.SHOWHEEL_ASSETS.attach($1)');
  }
  if (relative === 'archeon-atlas/atheria-region.js') {
    text = replace(text, "async function create({container,", "async function create({container,signal,", relative);
    text = replace(text, "const r=await fetch(assetBase+record.file,{signal:abort.signal});if(!r.ok)throw Error('区域分块未能读取：'+record.file);", "const data=await window.SHOWHEEL_ASSETS.bytes(assetBase+record.file,abort.signal);const r={arrayBuffer:async()=>data};", relative);
    text = replace(text, 'const errors=[];', "const errors=[];if(signal?.aborted)abort.abort();signal?.addEventListener('abort',()=>abort.abort(),{once:true});", relative);
    const cliffHook = text.includes('cliffLook.attach(mesh.geometry,record.file,record.sha256);') ? 'cliffLook.attach(mesh.geometry,record.file,record.sha256);' : '';
    const editorHook = text.includes('if(editor)await editor.onMesh(mesh,record);') ? 'if(editor)await editor.onMesh(mesh,record);' : '';
    text = replace(text, 'mesh.name=record.file;' + cliffHook + editorHook + 'return mesh;', "mesh.name=record.file;" + cliffHook + editorHook + "if(disposed){mesh.geometry.dispose();throw new DOMException('Scene closed','AbortError');}return mesh;", relative);
    text = replace(text, 'await Promise.all(promises);', "try{await Promise.all(promises);}catch(error){disposed=true;abort.abort();for(const m of fixed)m.geometry.dispose();resources.forEach(g=>g.dispose());[material,waterMaterial,cloudMat].forEach(m=>m.dispose());orbit.dispose();renderer.dispose();renderer.forceContextLoss();canvas.remove();throw error;}", relative);
    if (text.includes('async function loadTraffic()')) text = replace(text, "const response=await fetch(assetBase+M.transport.file,{signal:abort.signal});if(!response.ok)throw Error('Traffic data unavailable');trafficData=await response.json();", "trafficData=JSON.parse(new TextDecoder().decode(await window.SHOWHEEL_ASSETS.bytes(assetBase+M.transport.file,abort.signal)));", relative);
  }
  if (relative === 'archeon-atlas/atheria-controller.js') {
    text = replace(text, 'token=0,loaded=null;', 'token=0,loaded=null,sceneAbort=null;', relative);
    text = replace(text, 'const mine=++token;', 'sceneAbort?.abort();sceneAbort=new AbortController();const sceneSignal=sceneAbort.signal;const mine=++token;', relative);
    text = replace(text, "container:$('atheria-stage'),onState:sync", "container:$('atheria-stage'),onState:sync,signal:sceneSignal", relative);
    text = replace(text, '++token;active=false;', '++token;sceneAbort?.abort();active=false;', relative);
  }
  if (relative === 'archeon-atlas/eyrie-controller.js') {
    text = replace(text, 'token=0,loaded=null;', 'token=0,loaded=null,sceneAbort=null;', relative);
    text = replace(text, 'const mine=++token;', 'sceneAbort?.abort();sceneAbort=new AbortController();const sceneSignal=sceneAbort.signal;const mine=++token;', relative);
    text = replace(text, '++token;instance?.dispose();', '++token;sceneAbort?.abort();instance?.dispose();', relative);
    text = replace(text, 'if(!window.EYRIE_GEOMETRY){await script(', '{await script(', relative);
    text = replace(text, 'async function open(){if(active&&instance)return;', 'async function open(){window.ATLAS_ATHERIA_PAGE?.close();if(active&&instance)return;', relative);
  }
  if (/archeon-atlas\/(atheria|eyrie)-controller\.js$/.test(relative)) {
    text = replace(text, 'function load(){if(!loaded)loaded=(async()=>{', 'function load(signal){return (async()=>{const script=src=>window.SHOWHEEL_ASSETS.once(src,signal);', relative);
    text = text.replace(/\}\)\(\)\.catch\(e=>\{loaded=null;throw e;?\}\);return loaded;/, '})();');
    if (text.includes('return loaded;')) throw Error('Controller retry adaptation changed: ' + relative);
    text = replace(text, 'await load();', 'await load(sceneSignal);', relative);
  }
  return Buffer.from(text);
}
async function main() {
  if (!Number.isFinite(quota) || quota <= 0) throw Error('Invalid quota');
  if (output === root || output.startsWith(path.join(root, 'wwwroot') + path.sep) || output === path.join(root, 'wwwroot')) throw Error('Output must be separate from source');
  if (fs.existsSync(output) && fs.readdirSync(output).length) throw Error('Output is not empty; use a new directory: ' + output);
  fs.mkdirSync(output, { recursive: true });
  const generated = await exportPages();
  const imported = JSON.parse(fs.readFileSync(path.join(root, 'docs/archeon-atlas-assets.json')));
  const atlasFiles = new Set(imported.files.map(f => 'archeon-atlas/' + f.path).concat('archeon-atlas/about.html'));
  const inputs = new Map(walk(path.join(root, 'wwwroot')).map(file => [slash(path.relative(path.join(root, 'wwwroot'), file)), file]).filter(([relative]) => !relative.startsWith('archeon-atlas/') || atlasFiles.has(relative)));
  for (const [relative, content] of generated) inputs.set(relative, content);
  const records = {}, files = [];
  const priorReportPath = option('--reuse-report', '');
  const priorOutput = option('--reuse-output', '');
  const prior = priorReportPath ? new Map(JSON.parse(fs.readFileSync(priorReportPath)).files.map(f => [f.path, f])) : new Map();
  let processed = 0;
  for (const [relative, input] of inputs) {
    const original = Buffer.isBuffer(input) ? input : fs.readFileSync(input);
    let data = /\.js$/.test(relative) ? adapt(relative, original) : original;
    let method = data.equals(original) ? 'copy' : 'adapt', stored = relative, imageVerified = false;
    if (/\.png$/i.test(relative)) {
      const previous = prior.get(relative);
      if (previous?.pixelVerified && previous.sourceSha256 === hash(original)) {
        const candidate = fs.readFileSync(path.join(priorOutput, previous.stored));
        if (hash(candidate) !== previous.sha256) throw Error('Reused image changed: ' + relative);
        data = candidate; method = previous.method; stored = previous.stored; imageVerified = true;
      } else {
      const meta = await sharp(original).metadata();
      if (meta.depth === 'uchar' && !meta.pages && !meta.icc) {
        const pixels = await sharp(original).ensureAlpha().raw().toBuffer();
        const optimized = await sharp(original).png({ compressionLevel: 9, adaptiveFiltering: true, palette: false }).toBuffer();
        const decoded = await sharp(optimized).ensureAlpha().raw().toBuffer();
        if (!pixels.equals(decoded)) throw Error('PNG pixel mismatch: ' + relative);
        imageVerified = true;
        if (optimized.length < data.length) { data = optimized; method = 'png-lossless'; }
      }
      }
      if (relative.startsWith('images/') && imageVerified && method !== 'webp-lossless') {
        const webp = await sharp(original).webp({ lossless: true, effort: 4 }).toBuffer();
        if (webp.length < data.length && (await sharp(original).ensureAlpha().raw().toBuffer()).equals(await sharp(webp).ensureAlpha().raw().toBuffer())) {
          data = webp; stored = relative.replace(/\.png$/i, '.webp'); method = 'webp-lossless';
          if (inputs.has(stored)) stored = relative + '.webp';
        }
      }
    }
    if (/^archeon-atlas\/(data\/.*\.(js|json)|(?:atheria|eyrie|orun)-assets\/.*\.(bin|js|json|f32|u8|i32))$/.test(relative)) {
      const packed = zlib.gzipSync(data, { level: 9 });
      if (!zlib.gunzipSync(packed).equals(data)) throw Error('Gzip mismatch: ' + relative);
      stored = '_packed/' + hash(packed) + '.pack';
      records['/' + relative] = { url: '/' + stored, bytes: data.length, sha256: hash(packed) };
      method = 'gzip';
      write(stored, packed);
      files.push({ path: relative, stored, sourceBytes: original.length, bytes: packed.length, sourceSha256: hash(original), decodedSha256: hash(data), sha256: hash(packed), method });
    } else {
      write(stored, data);
      files.push({ path: relative, stored, sourceBytes: original.length, bytes: data.length, sourceSha256: hash(original), sha256: hash(data), method, ...(imageVerified ? { pixelVerified: true } : {}) });
    }
    if (!Buffer.isBuffer(input) && hash(fs.readFileSync(input)) !== hash(original)) throw Error('Source changed during build: ' + relative);
    if (++processed % 500 === 0) console.log('Processed ' + processed + ' resources');
  }
  const imageMoves = files.filter(f => f.method === 'webp-lossless');
  for (const f of files.filter(f => /\.(html|css|js)$/.test(f.stored) && f.method !== 'gzip')) {
    let text = fs.readFileSync(path.join(output, f.stored), 'utf8');
    const before = text;
    for (const move of imageMoves) {
      text = text.replaceAll('/' + move.path, '/' + move.stored).replaceAll('/' + encodeURI(move.path), '/' + encodeURI(move.stored));
      const escaped = name => name.split('/').map(part => encodeURIComponent(part).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase())).join('/');
      text = text.replaceAll('/' + escaped(move.path), '/' + escaped(move.stored));
    }
    if (before !== text) {
      const data = Buffer.from(text); write(f.stored, data); f.bytes = data.length; f.sha256 = hash(data); f.method = 'adapt';
    }
  }
  write('_packed/manifest.js', 'window.SHOWHEEL_PACKED=' + JSON.stringify(records) + ';\n');
  write('_packed/loader.js', fs.readFileSync(path.join(__dirname, 'web-runtime/packed-loader.js')));
  const indexFile = path.join(output, 'archeon-atlas/index.html');
  let index = fs.readFileSync(indexFile, 'utf8');
  const initial = [...index.matchAll(/<script src="([^"]+)"\s*><\/script>/g)].map(m => m[1]);
  index = index.replace(/<script src="[^"]+"\s*><\/script>/g, '');
  index = index.replace('</body>', '<script src="/_packed/manifest.js"></script><script src="/_packed/loader.js"></script><script src="/_packed/start.js"></script></body>');
  write('archeon-atlas/index.html', index);
  const indexEntry = files.find(f => f.path === 'archeon-atlas/index.html');
  indexEntry.sha256 = hash(Buffer.from(index)); indexEntry.bytes = Buffer.byteLength(index); indexEntry.method = 'adapt';
  write('_packed/start.js', '(async()=>{try{for(const src of ' + JSON.stringify(initial) + ')await SHOWHEEL_ASSETS.script(src);}catch(error){const host=document.getElementById("map-stage");host.textContent="地图未能展开，请重新载入页面。";const button=document.createElement("button");button.textContent="重新载入";button.onclick=()=>location.reload();host.append(button);console.error(error);}})();\n');
  const config = inputs.has('staticwebapp.config.json') ? JSON.parse(fs.readFileSync(path.join(root, 'wwwroot/staticwebapp.config.json'))) : {};
  config.routes = [...generated.keys()].filter(p => p !== 'index.html').map(p => ({ route: '/' + p.slice(0, -5), rewrite: '/' + p })).concat(config.routes || []);
  config.routes.push({ route: '/_packed/*.pack', headers: { 'Cache-Control': 'public, max-age=31536000, immutable' } });
  config.mimeTypes = { ...config.mimeTypes, '.pack': 'application/octet-stream' };
  write('staticwebapp.config.json', JSON.stringify(config, null, 2) + '\n');
  const generatedResources = ['_packed/manifest.js', '_packed/loader.js', '_packed/start.js', 'staticwebapp.config.json'].map(name => {
    const data = fs.readFileSync(path.join(output, name)); return { path: name, bytes: data.length, sha256: hash(data) };
  });
  const totalBytes = walk(output).reduce((sum, file) => sum + fs.statSync(file).size, 0);
  const report = { version: 1, generatedPages: [...generated.keys()], generatedResources, quotaConfirmed: !!(args.includes('--quota-mb') || process.env.SWA_QUOTA_MB), quotaBytes: quota, budgetBytes: Math.floor(quota * .9), totalBytes, overBudgetBytes: Math.max(0, totalBytes - Math.floor(quota * .9)), sourceBytes: files.reduce((sum, f) => sum + f.sourceBytes, 0), files };
  fs.mkdirSync(path.dirname(reportPath), { recursive: true }); fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ pages: generated.size, files: files.length, totalMB: totalBytes / 1e6, budgetMB: report.budgetBytes / 1e6, overBudgetMB: report.overBudgetBytes / 1e6, report: reportPath }));
  if (args.includes('--enforce-budget') && report.overBudgetBytes) throw Error('Publish budget exceeded; original assets and quality preserved.');
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
