'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const cacheRoot = path.resolve(process.argv[2] || path.join(root, 'obj/showheel-web-assets'));
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
const run = (command, args) => {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit', windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) throw Error('Publish preparation failed; the uncompressed site will not be uploaded.');
};
function fingerprint() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'docs/archeon-atlas-assets.json')));
  const atlas = new Set(manifest.files.map(f => path.resolve(root, 'wwwroot/archeon-atlas', f.path)));
  atlas.add(path.join(root, 'wwwroot/archeon-atlas/about.html'));
  const files = walk(path.join(root, 'wwwroot')).filter(f => !f.startsWith(path.join(root, 'wwwroot/archeon-atlas') + path.sep) || atlas.has(f));
  files.push(...walk(path.join(root, 'Pages')), ...walk(path.join(root, 'scripts/web-runtime')));
  for (const name of ['Program.cs', 'Showheel.csproj', 'docs/archeon-atlas-assets.json', 'scripts/build-web.cjs', 'scripts/prepare-appservice-publish.cjs', 'scripts/web-build/package.json', 'scripts/web-build/package-lock.json']) files.push(path.join(root, name));
  const digest = crypto.createHash('sha256');
  for (const file of files.sort()) digest.update(path.relative(root, file)).update('\0').update(hash(fs.readFileSync(file))).update('\n');
  return digest.digest('hex');
}
function ensureImageTools() {
  try {
    const installed = require('./web-build/node_modules/sharp/package.json');
    const requested = require('./web-build/package.json').dependencies.sharp;
    if (installed.version === requested) return;
  } catch {}
  const npm = [path.join(path.dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js'), path.resolve(path.dirname(process.execPath), '../lib/node_modules/npm/bin/npm-cli.js')].find(p => fs.existsSync(p));
  if (!npm) throw Error('Install the image tools first: npm ci --prefix scripts/web-build --no-audit --no-fund');
  run(process.execPath, [npm, 'ci', '--prefix', path.join(root, 'scripts/web-build'), '--no-audit', '--no-fund']);
}
function main() {
  if (cacheRoot !== path.join(root, 'obj/showheel-web-assets')) throw Error('Unexpected publish cache directory');
  fs.mkdirSync(cacheRoot, { recursive: true });
  const sourceHash = fingerprint();
  const directory = path.join(cacheRoot, sourceHash.slice(0, 20));
  const reportFile = path.join(directory, 'report.json');
  const completeFile = path.join(directory, 'complete.json');
  let reuse = null;
  const activeFile = path.join(cacheRoot, 'active-root.txt');
  if (fs.existsSync(activeFile)) {
    const previous = fs.readFileSync(activeFile, 'utf8').trim();
    if (previous.startsWith(cacheRoot + path.sep) && fs.existsSync(path.join(previous, 'report.json'))) reuse = { report: path.join(previous, 'report.json'), output: path.join(previous, 'assets') };
  }
  if (!reuse && fs.existsSync(path.join(root, 'docs/web-build-report.json')) && fs.existsSync(path.join(root, 'dist-web'))) reuse = { report: path.join(root, 'docs/web-build-report.json'), output: path.join(root, 'dist-web') };
  if (!fs.existsSync(completeFile)) {
    if (fs.existsSync(directory)) throw Error('An incomplete publish cache exists: ' + directory + '. Preserve it for inspection and retry with a clean cache.');
    ensureImageTools();
    const args = [path.join(__dirname, 'build-web.cjs'), '--root', root, '--output', path.join(directory, 'assets'), '--report', reportFile];
    if (reuse) args.push('--reuse-report', reuse.report, '--reuse-output', reuse.output);
    run(process.execPath, args);
    run(process.execPath, [path.join(__dirname, 'verify-web.cjs'), root, path.join(directory, 'assets'), reportFile]);
    if (fingerprint() !== sourceHash) throw Error('Source files changed during publishing; retry after source updates finish.');
    const report = JSON.parse(fs.readFileSync(reportFile));
    const routes = { '/': '/index.html', '/Index': '/index.html' }, packed = {};
    for (const page of report.generatedPages) if (page !== 'index.html') routes['/' + page.slice(0, -5)] = '/' + page;
    for (const file of report.files) {
      if (file.method === 'webp-lossless') routes['/' + file.path] = '/' + file.stored;
      if (file.method === 'gzip') packed['/' + file.path] = { file: '/' + file.stored, contentType: file.path.endsWith('.js') ? 'text/javascript; charset=utf-8' : file.path.endsWith('.json') ? 'application/json' : 'application/octet-stream' };
    }
    fs.writeFileSync(path.join(directory, 'showheel-web-routes.json'), JSON.stringify({ routes, packed }));
    fs.writeFileSync(completeFile, JSON.stringify({ sourceHash }));
  } else {
    if (JSON.parse(fs.readFileSync(completeFile)).sourceHash !== sourceHash) throw Error('Publish cache fingerprint mismatch');
    run(process.execPath, [path.join(__dirname, 'verify-web.cjs'), root, path.join(directory, 'assets'), reportFile]);
  }
  fs.writeFileSync(activeFile, directory + '\n');
  const report = JSON.parse(fs.readFileSync(reportFile));
  console.log('Visual Studio/App Service web assets: ' + (report.totalBytes / 1e6).toFixed(2) + ' MB. Server disk and temporary-storage quotas must be checked separately.');
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
