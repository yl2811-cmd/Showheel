'use strict';
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(process.argv[2] || 'dist-web');
const configFile = path.join(root, 'staticwebapp.config.json');
const mime = { '.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.json':'application/json', '.css':'text/css', '.png':'image/png', '.jpg':'image/jpeg', '.webp':'image/webp', '.svg':'image/svg+xml', '.pack':'application/octet-stream', '.md':'text/plain; charset=utf-8' };
const server = http.createServer((req, res) => {
  let name;
  try { name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); } catch { res.writeHead(400).end(); return; }
  const config = fs.existsSync(configFile) ? JSON.parse(fs.readFileSync(configFile)) : {};
  name = config.routes?.find(r => r.route === name)?.rewrite || name;
  if (name.endsWith('/')) name += 'index.html';
  const file = path.resolve(root, '.' + name);
  if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream', 'Content-Length': fs.statSync(file).size, 'Cache-Control': name.endsWith('.pack') ? 'public, max-age=31536000, immutable' : 'no-cache' });
  if (req.method === 'HEAD') res.end(); else fs.createReadStream(file).pipe(res);
});
server.listen(Number(process.argv[3] || 5288), '127.0.0.1', () => console.log('Preview http://127.0.0.1:' + server.address().port));
