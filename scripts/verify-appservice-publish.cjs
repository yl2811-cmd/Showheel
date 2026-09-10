'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const output = path.resolve(process.argv[2]), report = JSON.parse(fs.readFileSync(process.argv[3]));
const webRoot = path.join(output, 'wwwroot');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const expected = new Map(report.files.map(f => [f.stored, f.sha256]));
for (const f of report.generatedResources) expected.set(f.path, f.sha256);
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
for (const file of walk(webRoot)) {
  const relative = path.relative(webRoot, file).split(path.sep).join('/');
  assert(expected.has(relative), 'Unexpected or stale file in the actual App Service publish directory: ' + relative);
  assert.equal(hash(fs.readFileSync(file)), expected.get(relative), relative);
  expected.delete(relative);
}
assert.equal(expected.size, 0, 'Missing compressed website files');
for (const name of ['docs', 'scripts', 'dist-web']) assert(!fs.existsSync(path.join(output, name)), 'Build-only directory was published: ' + name);
assert(fs.existsSync(path.join(output, 'showheel-web-routes.json')));
assert(fs.existsSync(path.join(output, 'Showheel.dll')));
const totalBytes = walk(output).reduce((s, f) => s + fs.statSync(f).size, 0);
console.log(JSON.stringify({ actualAppServicePublishVerified: true, totalBytes, totalMB: totalBytes / 1e6, optimizedWebMB: report.totalBytes / 1e6, originalGeometryExcluded: true }));
