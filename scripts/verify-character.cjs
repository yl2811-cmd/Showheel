'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:5288';
const output = path.resolve(process.argv[3] || 'web-browser-qa/character');
fs.mkdirSync(output, { recursive: true });
const result = { checks: [], pageErrors: [], failedResources: [] };
const check = name => result.checks.push(name);
const expected = [
    ['anna', 'Anna Freedman', '19', '168', '58'],
    ['lia', 'Lia Redwood', '14', '149', '44'],
    ['kassia', 'Kassia Ashcroft', '21', '172', '60']
];
(async () => {
    const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
    try {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
        const page = await context.newPage();
        page.on('pageerror', e => result.pageErrors.push(e.message));
        page.on('response', r => { if (r.url().startsWith(base) && r.status() >= 400) result.failedResources.push({ url: r.url(), status: r.status() }); });
        assert.equal((await page.goto(base + '/Character')).status(), 200);
        assert(!/data-card="character"/.test(await (await context.request.get(base + '/')).text()));
        assert(!/href="\/Character"/.test(await (await context.request.get(base + '/Archeon')).text()));
        check('Standalone reader remains accessible; misplaced home and above-map links are absent');
        assert.equal(await page.locator('html').getAttribute('lang'), 'zh-Hans');
        assert.equal(await page.locator('.character-profile').count(), 3);
        for (const [id] of expected) {
            const img = page.locator('#' + id + ' img');
            await img.scrollIntoViewIfNeeded();
            await img.evaluate(el => el.decode());
        }
        await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
        await page.screenshot({ path: path.join(output, 'desktop-zh.png'), fullPage: true });
        for (const language of ['zh', 'en']) {
            await page.locator(`[data-character-lang="${language}"]`).click();
            assert.equal(await page.locator(`[data-character-lang="${language}"]`).getAttribute('aria-pressed'), 'true');
            for (const [id, name, age, height, weight] of expected) {
                const article = page.locator('#' + id);
                assert.equal(await article.locator('h2').textContent(), name);
                const facts = await article.locator('.character-facts').innerText();
                for (const value of [age, height, weight]) assert(facts.includes(value), name + ': ' + value);
                assert.equal(await article.locator('.character-prose p').count(), 3);
                assert.equal(await article.locator(`.character-prose [data-copy="${language}"]:visible`).count(), 3);
                assert.equal(await article.locator(`.character-prose [data-copy="${language === 'zh' ? 'en' : 'zh'}"]:visible`).count(), 0);
                const prose = await article.locator('.character-prose').innerText();
                assert(!/Ep69|fibrosis|纤维化|台架事故|学校|上班|工头|物流|值守|值班|维修|捎信/.test(prose));
            }
            check(language + ': names, ages, dimensions and three spoiler-light paragraphs');
        }
        await page.reload();
        assert.equal(await page.locator('html').getAttribute('lang'), 'en');
        check('Selected language persists after reload');
        await page.locator('[data-character-lang="zh"]').click();
        await page.evaluate(() => {
            const paragraph = document.querySelector('#lia .character-prose p:nth-child(2)');
            window.scrollTo({ top: paragraph.getBoundingClientRect().top + window.scrollY - 225, behavior: 'instant' });
        });
        const before = await page.locator('#lia .character-prose p:nth-child(2)').evaluate(el => el.getBoundingClientRect().top);
        await page.locator('[data-character-lang="en"]').click();
        const after = await page.locator('#lia .character-prose p:nth-child(2)').evaluate(el => el.getBoundingClientRect().top);
        assert(Math.abs(before - after) < 4, 'Reading position shifted: ' + (after - before));
        check('Switching language keeps the current Lia paragraph in place');
        await page.screenshot({ path: path.join(output, 'desktop-en-lia.png') });
        await page.locator('[data-character-lang="zh"]').focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('html').getAttribute('lang'), 'zh-Hans');
        assert(await page.locator('[data-character-lang="zh"]').evaluate(el => el === document.activeElement));
        check('Keyboard switches language and keeps button focus');
        for (const width of [390, 320]) {
            await page.setViewportSize({ width, height: 844 });
            for (const [id] of expected) {
                await page.locator(`.character-jumps a[href="#${id}"]`).click();
                assert.equal(new URL(page.url()).hash, '#' + id);
                const img = page.locator('#' + id + ' img');
                await img.scrollIntoViewIfNeeded();
                await img.evaluate(async el => { if (!el.complete) await new Promise((resolve, reject) => { el.onload = resolve; el.onerror = reject; }); });
                const geometry = await page.locator('#' + id).evaluate(el => {
                    const image = el.querySelector('img'), r = image.getBoundingClientRect();
                    return { width: r.width, height: r.height, naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight, textTop: el.querySelector('.character-copy').getBoundingClientRect().top, imageBottom: r.bottom, fit: getComputedStyle(image).objectFit, overflow: document.documentElement.scrollWidth - innerWidth };
                });
                assert(geometry.naturalWidth > 0);
                assert(Math.abs(geometry.width / geometry.height - geometry.naturalWidth / geometry.naturalHeight) < .005);
                assert.equal(geometry.fit, 'contain');
                assert(geometry.textTop > geometry.imageBottom);
                assert(geometry.overflow <= 1, 'Horizontal overflow at ' + width);
            }
            check(width + 'px: all anchors, complete images, vertical text order and no overflow');
        }
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: path.join(output, 'mobile-zh.png'), fullPage: true });
        await page.evaluate(() => window.scrollTo({ top: document.querySelector('#lia .character-copy').getBoundingClientRect().top + scrollY - 215, behavior: 'instant' }));
        await page.screenshot({ path: path.join(output, 'mobile-lia-text.png') });
        await page.locator('[data-character-lang="en"]').click();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
        await page.screenshot({ path: path.join(output, 'mobile-en.png'), fullPage: true });
        check('English mobile layout');
        const noScript = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
        const staticPage = await noScript.newPage();
        await staticPage.goto(base + '/Character');
        assert.equal(await staticPage.locator('.character-prose [data-copy="zh"]:visible').count(), 9);
        assert.equal(await staticPage.locator('.character-prose [data-copy="en"]:visible').count(), 0);
        assert.equal(await staticPage.locator('[data-language-controls]:visible').count(), 0);
        check('No JavaScript: all Chinese prose remains readable');
        await noScript.close();
        const blockedStorage = await browser.newContext();
        await blockedStorage.addInitScript(() => { Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Blocked', 'SecurityError'); } }); });
        const storagePage = await blockedStorage.newPage();
        await storagePage.goto(base + '/Character');
        await storagePage.locator('[data-character-lang="en"]').click();
        assert.equal(await storagePage.locator('html').getAttribute('lang'), 'en');
        check('Unavailable storage does not prevent reading or switching');
        await blockedStorage.close();
        assert.deepEqual(result.pageErrors, []);
        assert.deepEqual(result.failedResources, []);
        result.passed = true;
    } finally {
        fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
        await browser.close();
    }
    console.log(JSON.stringify(result));
})().catch(e => { console.error(e); process.exitCode = 1; });
