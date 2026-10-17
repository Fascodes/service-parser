/* Optional end-to-end QA: npm install --no-save playwright; npx playwright install chromium.
 * Start python serve.py first. Run node tests/browser_check.cjs [base-url].
 * PLAYWRIGHT_MODULE may point at an existing absolute playwright package path.
 * BROWSER_CHANNEL=chrome uses an installed Chrome instead of downloaded Chromium.
 */
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:8000';
const out = path.resolve(__dirname, '..', 'test-results');

(async () => {
  await fs.mkdir(out, {recursive: true});
  const browser = await chromium.launch({headless: true,
    ...(process.env.BROWSER_CHANNEL ? {channel: process.env.BROWSER_CHANNEL} : {})});
  const context = await browser.newContext({viewport: {width: 1440, height: 1100}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const ids = [];
  const timings = [];
  try {
    for (let number = 1; number <= 5; number += 1) {
      const response = await page.goto(`${base}/strona-${number}.html`);
      const source = await response.text();
      assert(!source.includes('class="produkt '), 'Raw HTML must not contain products');
      await page.waitForFunction(() => document.querySelectorAll('.produkt[data-id]').length === 24);
      await page.screenshot({path: path.join(out, `strona-${number}.png`), fullPage: false});
      while (await page.locator('#wczytaj-wiecej').isVisible()) {
        const previous = await page.locator('.produkt[data-id]').count();
        const start = Date.now();
        await page.locator('#wczytaj-wiecej').click();
        await page.waitForFunction((n) => document.querySelectorAll('.produkt[data-id]').length > n, previous);
        timings.push(Date.now() - start);
      }
      assert.equal(await page.locator('.produkt[data-id]').count(), number === 1 ? 80 : 82);
      assert(await page.locator('article.produkt').count() > 0);
      assert(await page.locator('tr.produkt').count() > 0);
      ids.push(...await page.locator('.produkt[data-id]').evaluateAll((nodes) => nodes.map((node) => node.dataset.id)));
      // All twelve list attributes are accessible in every rendered record.
      const complete = await page.locator('.produkt[data-id]').evaluateAll((nodes) => nodes.every((node) =>
        node.dataset.id && node.querySelector('[data-waluta]') &&
        ['nazwa', 'cena', 'kategoria', 'producent', 'dostepnosc', 'ocena', 'liczba_opinii', 'data_dodania', 'gwarancja', 'url']
          .every((key) => node.querySelector(`[data-pole="${key}"]`))));
      assert(complete);
    }
    assert.equal(ids.length, 408);
    assert.equal(new Set(ids).size, 400);
    // Sorting and filtering must update DOM without navigating/reloading.
    const url = page.url();
    await page.locator('#sortowanie').selectOption('cena-rosnaco');
    const prices = await page.locator('[data-pole="cena"]').evaluateAll((nodes) => nodes.map((node) =>
      Number(node.textContent.replace(/[^\d,]/g, '').replace(',', '.')) * (node.dataset.waluta === 'EUR' ? 4.35 : 1)));
    assert(prices.every((value, index) => index === 0 || value >= prices[index - 1]));
    await page.locator('#kategoria').selectOption('Plecaki');
    assert(await page.locator('.produkt[data-id]').count() > 0);
    assert(await page.locator('[data-pole="kategoria"]').evaluateAll((nodes) => nodes.every((node) => node.textContent === 'Plecaki')));
    await page.locator('#szukaj').fill('produkt-ktory-nie-istnieje');
    assert.equal(await page.locator('.produkt[data-id]').count(), 0);
    assert(await page.locator('#brak-wynikow').isVisible());
    await page.locator('#filtry button[type="reset"]').click();
    await page.waitForFunction(() => document.querySelectorAll('.produkt[data-id]').length === 82);
    assert.equal(page.url(), url);
    // Detail values are absent before interaction and present after it.
    const detailResponse = await page.goto(`${base}/produkty/PN-0001.html`);
    assert(!(await detailResponse.text()).includes('data-pole="nazwa"'));
    await page.waitForSelector('.product-detail');
    assert.equal(await page.locator('[data-pole="dostawca"]').count(), 0);
    assert.equal(await page.locator('.produkt [data-pole]').count() + 2, 20); // ID + currency.
    await page.locator('#dodatkowe-informacje summary').click();
    await page.waitForSelector('[data-pole="dostawca"]');
    assert.equal(await page.locator('.produkt [data-pole]').count() + 2, 24);
    await page.screenshot({path: path.join(out, 'szczegoly.png'), fullPage: true});
    // A failed portion must leave data intact and allow retry, without duplicate additions.
    let failed = false;
    await page.route('**/data/strona-1-porcja-2.json', async (route) => {
      if (!failed) { failed = true; await route.fulfill({status: 503, body: 'Test failure'}); }
      else await route.continue();
    });
    await page.goto(base);
    await page.waitForFunction(() => document.querySelectorAll('.produkt[data-id]').length === 24);
    await page.locator('#wczytaj-wiecej').click();
    await page.waitForSelector('#blad:not([hidden])');
    assert.equal(await page.locator('.produkt[data-id]').count(), 24);
    await page.locator('#wczytaj-wiecej').click();
    await page.waitForFunction(() => document.querySelectorAll('.produkt[data-id]').length === 48);
    assert.equal(await page.locator('#blad').isVisible(), false);
    // Small screen: only the intentional scrollable table may overflow internally.
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(base);
    await page.waitForFunction(() => document.querySelectorAll('.produkt[data-id]').length === 24);
    await page.screenshot({path: path.join(out, 'mobile.png'), fullPage: false});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    assert.deepEqual(errors, []);
    assert(timings.every((ms) => ms >= 300), `Unexpectedly short loading delays: ${timings}`);
    console.log(JSON.stringify({rawHTML: 0, domOccurrences: ids.length, uniqueProducts: new Set(ids).size,
      fieldsAfterInteraction: 24, testedPages: 5, observedLoadTimesMs: timings,
      filtering: 'OK', sorting: 'OK', errorRecovery: 'OK', mobile: 'OK', pageErrors: errors}, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {console.error(error); process.exitCode = 1;});
