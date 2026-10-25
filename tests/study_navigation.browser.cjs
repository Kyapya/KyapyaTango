'use strict';

// Run with NODE_PATH pointing to Playwright's installation. Set
// PLAYWRIGHT_CHROMIUM_EXECUTABLE if Chromium is installed outside Playwright.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const KEY = 'kyapyatango-study:v1';
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
const server = http.createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const filename = path.resolve(ROOT, '.' + (pathname.endsWith('/') ? pathname + 'index.html' : pathname));
    if (!filename.startsWith(ROOT + path.sep)) throw new Error('Invalid path');
    const body = await fs.readFile(filename);
    response.writeHead(200, { 'Content-Type': MIME[path.extname(filename)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    response.end(body);
  } catch {
    response.writeHead(404);
    response.end('Not found');
  }
});

let browser, base;
const savedState = (page, key = KEY) => page.evaluate(key => localStorage.getItem(key), key);
const paint = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
async function ready(page) {
  await page.waitForFunction(() => {
    const app = document.querySelector('#app');
    return app && !app.hasAttribute('aria-busy') && app.querySelector('#modeSelect, .session-content, .finish-card');
  });
}
async function study(page, mode = 'words') {
  await page.goto(base + '/study.html');
  await ready(page);
  if (mode !== 'words') {
    await page.locator('#modeSelect').selectOption(mode);
    await ready(page);
  }
  await page.locator('#reviewSearch').fill('eliminate');
  assert.equal(await page.locator('#reviewGrid a').first().getAttribute('target'), '_blank', 'Notebook links retain their existing new-tab behavior');
  await page.locator('#studyFiltered').click();
  await page.locator('#reveal').waitFor({ state: 'visible' });
  await ready(page);
  await page.locator('#reveal').click();
  await page.locator('#answer .session-source').waitFor({ state: 'visible' });
}
async function view(page) {
  await paint(page);
  return page.evaluate(() => ({
    word: document.querySelector('.session-content .word')?.textContent,
    sentence: document.querySelector('.sentence-question')?.textContent || null,
    meaning: document.querySelector('#answer .meaning')?.textContent,
    answerVisible: document.querySelector('#answer')?.hidden === false,
    progress: document.querySelector('.session-header > span')?.textContent,
    details: [...document.querySelectorAll('#answer details')].map(detail => detail.open),
    contentScrollTop: document.querySelector('.session-content')?.scrollTop || 0,
    appScrollTop: document.querySelector('#app').scrollTop
  }));
}
async function assertView(page, before) {
  const after = await view(page);
  const { contentScrollTop, appScrollTop, ...expected } = before;
  const { contentScrollTop: actualContent, appScrollTop: actualApp, ...actual } = after;
  assert.deepEqual(actual, expected, 'Back restores the same question, revealed answer and expanded details');
  assert(Math.abs(actualContent - contentScrollTop) <= 2, `Inner scroll restored: ${actualContent} versus ${contentScrollTop}`);
  assert(Math.abs(actualApp - appScrollTop) <= 2, `Fallback scroll restored: ${actualApp} versus ${appScrollTop}`);
}
async function openDictionary(page, link) {
  const tabs = page.context().pages().length;
  assert.notEqual(await link.getAttribute('target'), '_blank', 'Answer dictionary links use the existing browsing context');
  const destination = new URL(await link.getAttribute('href'), page.url()).href;
  await Promise.all([page.waitForURL(destination), link.click()]);
  await page.locator('body[data-word="eliminate"]').waitFor();
  assert.equal(page.context().pages().length, tabs, 'An ordinary answer-link click does not create a child window');
  return destination;
}
async function backToAnswer(page) {
  await page.goBack({ waitUntil: 'domcontentloaded' });
  await page.locator('#answer:not([hidden]) .meaning').waitFor({ state: 'visible' });
  await ready(page);
}
async function touchScroll(page, direction) {
  const session = await page.context().newCDPSession(page);
  const { width, height } = page.viewportSize();
  const x = Math.round(width / 2), start = Math.round(height * (direction < 0 ? .8 : .25));
  await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y: start }] });
  for (let step = 1; step <= 12; step++) {
    await session.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: start + direction * height * .45 * step / 12 }] });
    await page.waitForTimeout(18);
  }
  await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForTimeout(350);
  await session.detach();
}
async function runCase(name, task, init) {
  const context = await browser.newContext({ viewport: { width: 393, height: 700 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  context.setDefaultTimeout(15000);
  await context.addInitScript(() => { window.__studyTestDocumentId = Math.random(); });
  if (init) await context.addInitScript(init);
  try {
    await task(await context.newPage(), context);
    console.log('PASS: ' + name);
  } finally {
    await context.close();
  }
}

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = 'http://127.0.0.1:' + server.address().port;
  browser = await chromium.launch({
    headless: true,
    args: ['--disable-features=BackForwardCache'],
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {})
  });

  await runCase('word answer, native touch scrolling, repeated cold Back/Forward, details/scroll and sense anchor', async page => {
    await study(page);
    for (const summary of await page.locator('#answer details > summary').all()) await summary.click();
    const link = page.locator('#answer .session-source');
    await link.scrollIntoViewIfNeeded();
    const before = await view(page), raw = await savedState(page);
    assert(before.contentScrollTop > 0 || before.appScrollTop > 0, 'The test exercises a nonzero study scroll position');
    const documentId = await page.evaluate(() => window.__studyTestDocumentId);
    await openDictionary(page, link);
    await touchScroll(page, -1);
    const down = await page.evaluate(() => scrollY);
    assert(down > 50, 'A native upward finger gesture scrolls the dictionary down');
    await touchScroll(page, 1);
    assert(await page.evaluate(() => scrollY) < down - 50, 'A native downward finger gesture scrolls the dictionary back up');
    await backToAnswer(page);
    assert.notEqual(await page.evaluate(() => window.__studyTestDocumentId), documentId, 'Back exercises reconstruction without BFCache');
    await assertView(page, before);
    assert.equal(await savedState(page), raw, 'Reading the dictionary does not mutate saved study state');

    const firstReturnDocument = await page.evaluate(() => window.__studyTestDocumentId);
    await page.goForward({ waitUntil: 'domcontentloaded' });
    await page.locator('body[data-word="eliminate"]').waitFor();
    await backToAnswer(page);
    assert.notEqual(await page.evaluate(() => window.__studyTestDocumentId), firstReturnDocument, 'Repeated Back also reconstructs a new document');
    await assertView(page, before);
    assert.equal(await savedState(page), raw, 'Forward followed by another Back still preserves the saved study state');

    const senseLink = page.locator('#answer a[href$="#sense-2"]');
    await senseLink.scrollIntoViewIfNeeded();
    const senseView = await view(page);
    assert.equal(new URL(await openDictionary(page, senseLink)).hash, '#sense-2');
    await backToAnswer(page);
    await assertView(page, senseView);
    assert.equal(await savedState(page), raw, 'Following another sense also leaves learning records unchanged');
  });

  await runCase('example answer returns to its original mode despite another tab changing the preference', async (page, context) => {
    await study(page, 'examples');
    await page.locator('#answer details > summary').click();
    const link = page.locator('#answer .session-source');
    await link.scrollIntoViewIfNeeded();
    const before = await view(page), raw = await savedState(page, KEY + ':examples');
    assert(before.sentence, 'An actual example question is displayed');
    assert.match(new URL(await openDictionary(page, link)).hash, /^#sense-\d+$/);
    const other = await context.newPage();
    await other.goto(base + '/study.html');
    await ready(other);
    await other.locator('#modeSelect').selectOption('words');
    await ready(other);
    assert.equal(await other.evaluate(key => localStorage.getItem(key + ':mode'), KEY), 'words');
    await other.close();
    await backToAnswer(page);
    await assertView(page, before);
    assert.equal(await savedState(page, KEY + ':examples'), raw, 'The mode preference change does not overwrite the example session');
  });

  await runCase('another tab completing the session prevents stale answer restoration', async (page, context) => {
    await study(page);
    await openDictionary(page, page.locator('#answer .session-source'));
    const other = await context.newPage();
    await other.goto(base + '/study.html');
    await ready(other);
    await other.locator('#resume').click();
    await other.locator('#reveal').click();
    await other.locator('[data-rating="remembered"]').click();
    await other.locator('.finish-card').waitFor();
    await ready(other);
    const latest = await savedState(other);
    assert.equal(JSON.parse(latest).session, null);
    assert.equal(JSON.parse(latest).records.eliminate.rating, 'remembered');
    await other.close();
    await page.goBack({ waitUntil: 'domcontentloaded' });
    await page.locator('#modeSelect').waitFor();
    await ready(page);
    assert.equal(await page.locator('.session-content').count(), 0, 'A completed session does not reopen its stale answer');
    assert.equal(await savedState(page), latest, 'The newest rating and session survive Back byte for byte');
  });

  await runCase('explicit middle-click remains a browser new-tab action', async (page, context) => {
    await study(page);
    const url = page.url(), historyState = await page.evaluate(() => JSON.stringify(history.state)), raw = await savedState(page);
    const popupPromise = context.waitForEvent('page');
    await page.locator('#answer .session-source').click({ button: 'middle' });
    const popup = await popupPromise;
    await popup.waitForURL(/\/words\/eliminate\.html$/);
    assert.equal(page.url(), url);
    assert.equal(await page.evaluate(() => JSON.stringify(history.state)), historyState, 'Explicit new-tab gestures are not intercepted');
    assert.equal(await savedState(page), raw);
    await popup.close();
  });

  await runCase('an unsaved session blocks ordinary dictionary navigation', async page => {
    await study(page);
    await page.locator('.save-warning').waitFor({ state: 'visible' });
    const url = page.url();
    await page.locator('#answer .session-source').click();
    await paint(page);
    assert.equal(page.url(), url, 'Unsaved in-memory progress must not be lost by leaving the page');
    assert.equal(page.context().pages().length, 1);
    assert.equal(await page.locator('#answer').isVisible(), true);
    assert.equal(await savedState(page), null);
  }, () => {
    const setItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === 'kyapyatango-study:v1') throw new DOMException('Test storage quota failure', 'QuotaExceededError');
      return setItem.call(this, key, value);
    };
  });
  console.log('These checks use Chromium mobile emulation; Hermit host-app gesture handling requires device verification.');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
}).finally(async () => {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
});
