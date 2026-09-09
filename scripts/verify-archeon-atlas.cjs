'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const assets = path.join(root, 'wwwroot/archeon-atlas');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'docs/archeon-atlas-assets.json')));
const files = new Set(manifest.files.map(file => file.path));
const views = ['world', 'aethelgard', 'atheria', 'marneth', 'rimstone'];
const hash = buffer => crypto.createHash('sha256').update(buffer).digest('hex');
const read = relative => fs.readFileSync(path.join(assets, relative), 'utf8');
const exists = relative => assert(files.has(relative), 'Unlisted dependency: ' + relative);

async function main() {
  for (const file of manifest.files) {
    assert.equal(hash(fs.readFileSync(path.join(assets, file.path))), file.sha256, file.path);
    assert(file.bytes < 100 * 1024 * 1024, 'Oversized Git file: ' + file.path);
    if (file.path.endsWith('.js')) new vm.Script(read(file.path), { filename: file.path });
  }
  const context = { window: {} };
  for (const match of read('index.html').matchAll(/(?:href|src)="([^"]+)"/g)) {
    const relative = match[1];
    if (relative === 'about.html') continue;
    if (!relative.startsWith('#') && !/^(?:https?:|data:)/.test(relative)) exists(relative);
  }
  for (const script of ['space-controller.js', 'colonization-ui.js', 'eyrie-controller.js', 'atheria-controller.js']) {
    for (const match of read(script).matchAll(/(?:loadScript|script)\('([^']+)'\)/g)) exists(match[1]);
  }
  vm.runInNewContext(read('atheria-assets/manifest.js'), context);
  function checkRegion(value) {
    if (!value || typeof value !== 'object') return;
    for (const [key, item] of Object.entries(value)) {
      if (key === 'file' && typeof item === 'string') exists('atheria-assets/' + item);
      else checkRegion(item);
    }
  }
  assert(context.window.ATHERIA_REGION_MANIFEST);
  checkRegion(context.window.ATHERIA_REGION_MANIFEST);
  for (const file of ['data/astronomy.js', 'data/stars-hyg41.js', 'data/space-textures.js']) {
    vm.runInNewContext(read(file), context);
  }
  assert(context.window.ATLAS_ASTRONOMY && context.window.ATLAS_STARS);
  assert(context.window.ATLAS_SPACE_TEXTURES.archeon.startsWith('data:image/png;base64,'));
  assert(!read('index.html').includes('../../review/'));
  vm.runInNewContext(read('data/tiles.js'), context);
  for (const meta of Object.values(context.window.ATLAS_TILES)) {
    for (const level of meta.levels) {
      for (let y = 0; y < level.rows; y++) for (let x = 0; x < level.cols; x++) {
        exists(level.path.replace('{x}', x).replace('{y}', y));
      }
    }
  }
  for (const view of views) {
    vm.runInNewContext(read('data/maps-' + view + '.js'), context);
    const markup = context.window.ATLAS_MAPS[view];
    assert(markup.includes('<svg'), 'Missing SVG: ' + view);
    for (const match of markup.matchAll(/(?:href|src)="([^"]+)"/g)) {
      if (!match[1].startsWith('#') && !match[1].startsWith('data:')) exists(match[1]);
    }
    for (const match of markup.matchAll(/data-(?:contour|river)-manifest="([^"]+)"/g)) {
      const contour = JSON.parse(match[1].replaceAll('&quot;', '"').replaceAll('&amp;', '&'));
      for (const tile of contour.tiles) {
        if (Array.isArray(tile)) exists(contour.path.replace('{x}', tile[0]).replace('{y}', tile[1]));
        else exists(tile.path);
      }
    }
  }
  assert(!/download-svg|download-png|exports\//.test(read('index.html') + read('app.js')));
  const base = process.argv[2];
  let httpChecked = 0;
  if (base) {
    const queue = [...files, 'about.html'];
    await Promise.all(Array.from({ length: 8 }, async () => {
      while (queue.length) {
        const relative = queue.pop();
        const response = await fetch(new URL('/archeon-atlas/' + relative, base), { method: 'HEAD' });
        assert.equal(response.status, 200, relative + ' HTTP status');
        assert.equal(Number(response.headers.get('content-length')), fs.statSync(path.join(assets, relative)).size, relative + ' served length');
        httpChecked++;
      }
    }));
    const archeon = await fetch(new URL('/Archeon', base));
    assert.equal(archeon.status, 200);
    assert((await archeon.text()).includes('src="/archeon-atlas/index.html"'));
    const old = await fetch(new URL('/world-atlas.html', base));
    assert.equal(old.status, 200);
    const redirect = await old.text();
    assert(redirect.includes("location.replace('/archeon-atlas/index.html')"));
    assert(!redirect.includes('panel-planet'));
  }
  console.log(JSON.stringify({ passed: true, hashedFiles: files.size, views: views.length, httpChecked, bytes: manifest.files.reduce((sum, file) => sum + file.bytes, 0) }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
