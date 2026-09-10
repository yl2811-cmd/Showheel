'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:5288';
const output = path.resolve(process.argv[3] || 'web-browser-qa');
fs.mkdirSync(output, { recursive: true });
const result = { pages: [], scenes: [], errors: [], failedResources: [] };
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => { result.errors.push(error.message); console.log('Page error: ' + error.message); });
    page.on('response', response => { if (response.url().startsWith(base) && response.status() >= 400) result.failedResources.push({ url: response.url(), status: response.status() }); });
    for (const route of ['/', '/Archeon', '/Gallery', '/About', '/story-viewer.html', '/story-engl-viewer.html']) {
      assert.equal((await page.goto(base + route)).status(), 200);
      if (route.includes('viewer')) await page.waitForFunction(() => document.querySelector('[data-story-scroll]')?.textContent.length > 100, null, { timeout: 60000 });
      result.pages.push(route);
    }
    await page.goto(base + '/archeon-atlas/index.html');
    await page.waitForFunction(() => window.ATLAS_APP?.ready && window.ATLAS_APP?.openAtheria, null, { timeout: 60000 });
    for (const view of ['world', 'aethelgard', 'marneth', 'rimstone']) {
      await page.evaluate(id => window.ATLAS_APP.setView(id), view);
      await page.waitForFunction(id => window.ATLAS_APP?.ready && window.ATLAS_APP.currentView === id, view, { timeout: 60000 });
      result.scenes.push({ view }); console.log('Verified ' + view);
    }
    await page.evaluate(() => window.ATLAS_I18N.setLocale('en'));
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    await page.evaluate(() => window.ATLAS_I18N.setLocale('zh'));
    await page.evaluate(() => window.ATLAS_APP.openAtheria());
    await page.waitForFunction(() => { const s = window.ATLAS_APP?.getAtheriaState(); return s && s.visibleChunks > 0 && s.pending === 0; }, null, { timeout: 60000 });
    for (const focus of ['overview', 'compounds', 'farmland', 'shelves', 'wide']) {
      await page.evaluate(id => window.ATLAS_APP.atheriaFocus(id), focus);
      await page.waitForFunction(() => { const s = window.ATLAS_APP?.getAtheriaState(); return s && s.visibleChunks > 0 && s.pending === 0; }, null, { timeout: 60000 });
      const state = await page.evaluate(() => window.ATLAS_APP.getAtheriaState());
      assert.equal(state.scopeRadiusM, await page.evaluate(() => window.ATHERIA_REGION_MANIFEST.radiusM)); assert.equal(state.errors.length, 0);
      result.scenes.push({ view: 'atheria', focus, state });
      await page.screenshot({ path: path.join(output, 'atheria-' + focus + '.png') });
      console.log('Verified Atheria ' + focus);
    }
    await page.evaluate(() => window.ATLAS_APP.openEyrie());
    await page.waitForFunction(() => window.ATLAS_APP?.ready && window.ATLAS_APP.currentView === 'eyrie', null, { timeout: 60000 });
    await page.screenshot({ path: path.join(output, 'eyrie.png') });
    result.scenes.push({ view: 'eyrie', state: await page.evaluate(() => window.ATLAS_APP.eyrieState) });
    console.log('Verified Eyrie');
    for (const scene of ['system', 'federation']) {
      await page.locator('[data-tab="' + scene + '"]').click();
      await page.waitForFunction(() => window.ATLAS_APP?.ready, null, { timeout: 60000 });
      result.scenes.push({ view: scene }); console.log('Verified ' + scene);
    }
    await page.evaluate(() => window.ATLAS_APP.openAtheria());
    await page.waitForFunction(() => window.ATLAS_APP.getAtheriaState()?.visibleChunks > 0, null, { timeout: 60000 });
    await page.evaluate(() => window.ATLAS_APP.setView('world'));
    assert.equal(await page.locator('.atheria-canvas').count(), 0);
    await page.evaluate(() => window.ATLAS_APP.openEyrie());
    await page.waitForFunction(() => window.ATLAS_APP?.ready && window.ATLAS_APP.currentView === 'eyrie', null, { timeout: 60000 });
    result.reopenScenes = true;
    result.loading = await page.evaluate(() => window.SHOWHEEL_ASSETS.metrics);
    assert.deepEqual(result.errors, []); assert.deepEqual(result.failedResources, []);
    result.passed = true;
  } finally { fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(result, null, 2)); await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
