'use strict';

// Copy only browser dependencies. Never modify the atlas master directory.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = path.resolve(process.argv[2] || 'D:/SKBS/maps/archeon-atlas');
const destination = path.join(root, 'wwwroot/archeon-atlas');
const views = ['world', 'aethelgard', 'atheria', 'marneth', 'rimstone'];
const files = new Set(['index.html', 'app.js', 'atlas.css', 'vendor/d3.v7.min.js',
  'vendor/LICENSE-d3.txt', 'data/atlas.js', 'data/atlas.json', 'data/tiles.js']);
for (const file of ['i18n.css', 'i18n-catalogue.js', 'i18n-content.js', 'i18n.js']) files.add(file);
for (const file of ['living-overlay.js', 'settlement-display.js', 'data/living-atlas.js', 'data/living-atlas.json']) files.add(file);
for (const file of ['space-controller.js', 'space-view.js', 'terraform-view.js',
  'space-ui.css', 'space-view.css', 'data/astronomy.js', 'data/astronomy.json',
  'data/stars-hyg41.js', 'data/space-textures.js', 'vendor/three-space.bundle.js',
  'vendor/LICENSE-three.txt']) files.add(file);
const sourcePath = relative => relative === 'space-assets/physics-humanity-audit.md'
  ? path.resolve(source, '../../review/space-atlas-20260907/physics-humanity-audit.md')
  : path.join(source, relative);
files.add('space-assets/physics-humanity-audit.md');
for (const file of ['colonization-ui.js', 'colonization-model.js', 'colonization-view.js',
  'colonization-ui.css', 'colonization-view.css', 'data/colonization-input.js',
  'data/colonization-input.json', 'data/colonization-stars.js',
  'data/colonization-stars-provenance.json', 'data/colonization-sensitivity.json',
  'data/federation-projects.json']) files.add(file);
for (const file of ['river-layer.js', 'eyrie.css', 'eyrie-controller.js',
  'eyrie-view.js', 'eyrie-materials.js', 'eyrie-motion.js', 'eyrie-batches.js',
  'eyrie-walking.js', 'eyrie-assets/manifest.js', 'eyrie-assets/navigation.js',
  'eyrie-assets/DESIGN.md', 'eyrie-assets/preview.png']) files.add(file);

// Preserve the source geometry exactly while keeping each Git blob below 100 MiB.
const geometrySource = fs.readFileSync(path.join(source, 'eyrie-assets/geometry.js'));
const geometryContext = { window: {} };
vm.runInNewContext(geometrySource.toString('utf8'), geometryContext);
const geometryParts = new Map();
let geometryBatch = {}, geometryBytes = 0;
function flushGeometry() {
  if (!Object.keys(geometryBatch).length) return;
  const name = 'eyrie-assets/geometry-part-' + String(geometryParts.size + 1).padStart(3, '0') + '.js';
  geometryParts.set(name, Buffer.from('window.EYRIE_GEOMETRY=window.EYRIE_GEOMETRY||{};Object.assign(window.EYRIE_GEOMETRY,' + JSON.stringify(geometryBatch) + ');\n'));
  geometryBatch = {}; geometryBytes = 0;
}
for (const [key, value] of Object.entries(geometryContext.window.EYRIE_GEOMETRY)) {
  const bytes = Buffer.byteLength(JSON.stringify({ [key]: value }));
  if (geometryBytes + bytes > 32 * 1024 * 1024) flushGeometry();
  geometryBatch[key] = value; geometryBytes += bytes;
}
flushGeometry();

function addDirectory(relative, extension) {
  for (const entry of fs.readdirSync(path.join(source, relative), { withFileTypes: true })) {
    const name = relative + '/' + entry.name;
    if (entry.isDirectory()) addDirectory(name, extension);
    else if (name.endsWith(extension)) files.add(name);
  }
}
for (const view of views) {
  const relative = 'data/maps-' + view + '.js';
  files.add(relative);
  const script = fs.readFileSync(path.join(source, relative), 'utf8');
  for (const match of script.matchAll(/terrain\/[A-Za-z0-9_.\/-]+\.png/g)) files.add(match[0]);
}
addDirectory('terrain/tiles', '.png');
addDirectory('data/contours', '.js');
addDirectory('data/hydrology', '.js');
addDirectory('space-assets', '.md');
for (const relative of files) {
  if (!fs.statSync(sourcePath(relative)).isFile()) throw Error('Missing dependency: ' + relative);
}

function replaceOnce(text, pattern, replacement) {
  const matches = text.match(new RegExp(pattern.source, 'g'));
  if (matches?.length !== 1) throw Error('Source changed; review integration: ' + pattern);
  return text.replace(pattern, replacement);
}
function adapt(relative, original) {
  if (relative === 'eyrie-controller.js') {
    return Buffer.from(replaceOnce(original.toString('utf8'), /await script\('eyrie-assets\/geometry\.js'\)/,
      '{' + [...geometryParts.keys()].map(name => "await script('" + name + "');").join('') + '}'));
  }
  if (relative === 'index.html') {
    let text = original.toString('utf8');
    text = replaceOnce(text, /href="README\.md" target="_blank"/, 'href="about.html"');
    text = replaceOnce(text, /\.\.\/\.\.\/review\/space-atlas-20260907\/physics-humanity-audit\.md/, 'space-assets/physics-humanity-audit.md');
    text = replaceOnce(text, /<a id="download-svg"[^]*?<\/a><a id="download-png"[^]*?<\/a>/, '');
    return Buffer.from(text);
  }
  if (relative === 'app.js') {
    const text = replaceOnce(original.toString('utf8'), /document\.getElementById\('download-svg'\)\.href=[^;]+;const png=document\.getElementById\('download-png'\);png\.hidden=[^;]+;png\.href='exports\/'[^;]+;/, '');
    return Buffer.from(text);
  }
  return original;
}
const hash = buffer => crypto.createHash('sha256').update(buffer).digest('hex');
const entries = [];
for (const relative of [...files].sort()) {
  const original = fs.readFileSync(sourcePath(relative));
  const deployed = adapt(relative, original);
  const target = path.join(destination, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  if (!fs.existsSync(target) || !fs.readFileSync(target).equals(deployed)) fs.writeFileSync(target, deployed);
  const sourceSha256 = hash(original), sha256 = hash(deployed);
  if (hash(fs.readFileSync(target)) !== sha256 || hash(fs.readFileSync(sourcePath(relative))) !== sourceSha256) {
    throw Error('Copy verification failed: ' + relative);
  }
  entries.push({ path: relative, bytes: deployed.length, sourceSha256, sha256 });
}
fs.mkdirSync(path.join(root, 'docs'), { recursive: true });
for (const [relative, deployed] of geometryParts) {
  const target = path.join(destination, relative);
  fs.writeFileSync(target, deployed);
  if (hash(fs.readFileSync(target)) !== hash(deployed)) throw Error('Geometry copy failed: ' + relative);
  entries.push({ path: relative, bytes: deployed.length, sourcePath: 'eyrie-assets/geometry.js', sourceSha256: hash(geometrySource), sha256: hash(deployed) });
}
if (hash(fs.readFileSync(path.join(source, 'eyrie-assets/geometry.js'))) !== hash(geometrySource)) throw Error('Source geometry changed during import');
fs.writeFileSync(path.join(root, 'docs/archeon-atlas-assets.json'), JSON.stringify({
  source: 'SKBS/maps/archeon-atlas', version: 6,
  adaptations: ['index.html: website help link, local astronomy audit link and data-only download', 'app.js: remove export download updates', 'eyrie-controller.js and geometry parts: split source geometry into lossless chunks below the Git file size limit'],
  files: entries
}, null, 2) + '\n');
console.log(JSON.stringify({ files: entries.length, bytes: entries.reduce((total, file) => total + file.bytes, 0), verified: true }));
