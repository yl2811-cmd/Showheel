'use strict';

// Copy only browser dependencies. Never modify the atlas master directory.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const source = path.resolve(process.argv[2] || 'D:/SKBS/maps/archeon-atlas');
const destination = path.join(root, 'wwwroot/archeon-atlas');
const views = ['world', 'aethelgard', 'atheria', 'marneth', 'rimstone'];
const files = new Set(['index.html', 'app.js', 'atlas.css', 'vendor/d3.v7.min.js',
  'vendor/LICENSE-d3.txt', 'data/atlas.js', 'data/atlas.json', 'data/tiles.js']);

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
for (const relative of files) {
  if (!fs.statSync(path.join(source, relative)).isFile()) throw Error('Missing dependency: ' + relative);
}

function replaceOnce(text, pattern, replacement) {
  const matches = text.match(new RegExp(pattern.source, 'g'));
  if (matches?.length !== 1) throw Error('Source changed; review integration: ' + pattern);
  return text.replace(pattern, replacement);
}
function adapt(relative, original) {
  if (relative === 'index.html') {
    let text = original.toString('utf8');
    text = replaceOnce(text, /href="README\.md" target="_blank"/, 'href="about.html"');
    text = replaceOnce(text, /<a id="download-svg"[^]*?<\/a><a id="download-png"[^]*?<\/a>/, '');
    return Buffer.from(text);
  }
  if (relative === 'app.js') {
    const text = replaceOnce(original.toString('utf8'), /document\.getElementById\('download-svg'\)\.href=[^]*?png\.href='exports\/'\+id\+'-12000\.png';/, '');
    return Buffer.from(text);
  }
  return original;
}
const hash = buffer => crypto.createHash('sha256').update(buffer).digest('hex');
const entries = [];
for (const relative of [...files].sort()) {
  const original = fs.readFileSync(path.join(source, relative));
  const deployed = adapt(relative, original);
  const target = path.join(destination, relative);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, deployed);
  const sourceSha256 = hash(original), sha256 = hash(deployed);
  if (hash(fs.readFileSync(target)) !== sha256 || hash(fs.readFileSync(path.join(source, relative))) !== sourceSha256) {
    throw Error('Copy verification failed: ' + relative);
  }
  entries.push({ path: relative, bytes: deployed.length, sourceSha256, sha256 });
}
fs.mkdirSync(path.join(root, 'docs'), { recursive: true });
fs.writeFileSync(path.join(root, 'docs/archeon-atlas-assets.json'), JSON.stringify({
  source: 'SKBS/maps/archeon-atlas', version: 6,
  adaptations: ['index.html: website help link and data-only download', 'app.js: remove export download updates'],
  files: entries
}, null, 2) + '\n');
console.log(JSON.stringify({ files: entries.length, bytes: entries.reduce((total, file) => total + file.bytes, 0), verified: true }));
