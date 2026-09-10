'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), zlib = require('node:zlib'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const root = path.resolve(process.argv[2] || path.join(__dirname, '..'));
const build = path.resolve(process.argv[3] || path.join(root, 'dist-web'));
const report = JSON.parse(fs.readFileSync(process.argv[4] || path.join(root, 'docs/web-build-report.json')));
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(build, '_packed/manifest.js'), 'utf8'), context);
let packed = 0, copied = 0;
for (const f of report.files) {
  const source = path.join(root, 'wwwroot', f.path), stored = fs.readFileSync(path.join(build, f.stored));
  if (fs.existsSync(source)) assert.equal(hash(fs.readFileSync(source)), f.sourceSha256, 'Source changed: ' + f.path);
  assert.equal(hash(stored), f.sha256, f.path);
  if (f.method === 'gzip') {
    const decoded = zlib.gunzipSync(stored);
    assert.equal(hash(decoded), f.decodedSha256, f.path);
    assert.equal(hash(decoded), f.sourceSha256, 'Model/data changed: ' + f.path);
    assert(!fs.existsSync(path.join(build, f.path)), 'Duplicate uncompressed asset: ' + f.path);
    assert(context.window.SHOWHEEL_PACKED['/' + f.path]);
    if (f.path.endsWith('.js')) new vm.Script(decoded.toString('utf8'), { filename: f.path });
    packed++;
  } else { if (f.path.endsWith('.js')) new vm.Script(stored.toString('utf8'), { filename: f.path }); copied++; }
}
for (const f of report.generatedResources || []) assert.equal(hash(fs.readFileSync(path.join(build, f.path))), f.sha256, f.path);
const available = new Set(report.files.map(f => '/' + f.stored));
for (const name of report.generatedPages) {
  const html = fs.readFileSync(path.join(build, name), 'utf8');
  assert(/<!doctype html>/i.test(html), name);
  for (const match of html.matchAll(/(?:src|href)="(\/[^"#?]*)(?:[?#][^"]*)?"/g)) {
    const url = decodeURIComponent(match[1]);
    if (url === '/' || report.generatedPages.includes(url.slice(1) + '.html')) continue;
    assert(available.has(url), 'Missing page dependency: ' + name + ' -> ' + url);
  }
}
for (const name of ['story.md', 'story-engl.md']) assert.equal(hash(fs.readFileSync(path.join(build, name))), hash(fs.readFileSync(path.join(root, 'wwwroot', name))));
assert(fs.existsSync(path.join(build, 'index.html')));
assert(fs.statSync(path.join(build, 'staticwebapp.config.json')).size < 20000);
console.log(JSON.stringify({ passed: true, packed, copied, pages: report.generatedPages.length, modelHashesUnchanged: true, readerHashesUnchanged: true, totalMB: report.totalBytes / 1e6 }));
