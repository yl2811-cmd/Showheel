'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto'), zlib = require('node:zlib');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:5289';
const data = Buffer.from('Atheria: preserve every byte.\n'.repeat(100));
const packed = zlib.gzipSync(data);
const sha256 = crypto.createHash('sha256').update(packed).digest('hex');
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const page = await browser.newPage();
    await page.route(base + '/loader-fixture', route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><div id="load-status"></div>' }));
    await page.goto(base + '/loader-fixture');
    await page.evaluate(() => { window.SHOWHEEL_PACKED = {}; });
    await page.addScriptTag({ path: path.join(__dirname, 'web-runtime/packed-loader.js') });
    let calls = 0;
    await page.route('**/fixture-*.pack', async route => {
      calls++;
      if (route.request().url().includes('retry') && calls === 1) return route.fulfill({ status: 503, body: 'temporary' });
      if (route.request().url().includes('corrupt')) return route.fulfill({ body: Buffer.from('bad data') });
      await new Promise(resolve => setTimeout(resolve, 150));
      await route.fulfill({ contentType: 'application/octet-stream', body: packed });
    });
    const register = name => page.evaluate(({ name, bytes, sha256 }) => { window.SHOWHEEL_PACKED['/' + name] = { url: '/fixture-' + name + '.pack', bytes, sha256 }; }, { name, bytes: data.length, sha256 });
    await register('shared');
    const shared = await page.evaluate(async () => {
      const a = new AbortController();
      const one = SHOWHEEL_ASSETS.bytes('/shared', a.signal).then(() => 'unexpected', error => error.name);
      const two = SHOWHEEL_ASSETS.bytes('/shared'); a.abort();
      return [await one, new TextDecoder().decode(await two)];
    });
    assert.equal(shared[0], 'AbortError'); assert.equal(shared[1], data.toString()); assert.equal(calls, 1);
    await page.evaluate(() => SHOWHEEL_ASSETS.bytes('/shared')); assert.equal(calls, 1, 'Warm cache downloaded twice');
    calls = 0; await register('retry');
    await page.evaluate(() => SHOWHEEL_ASSETS.bytes('/retry')); assert.equal(calls, 2);
    calls = 0; await register('corrupt');
    const rejected = await page.evaluate(() => SHOWHEEL_ASSETS.bytes('/corrupt').then(() => false, () => true));
    assert(rejected); assert.equal(calls, 3);
    const metrics = await page.evaluate(() => SHOWHEEL_ASSETS.metrics);
    console.log(JSON.stringify({ passed: true, sharedDownload: true, independentCancellation: true, warmCache: true, retry503: true, corruptDataRejected: true, metrics }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
