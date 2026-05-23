/**
 * Landing page screenshot capture — uses puppeteer-core + system Chrome.
 * Run from the screenshots/ directory: node capture.js
 */
const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL    = 'http://localhost:5500';
const OUT_DIR     = __dirname;

const sections = [
  { name: '01-hero',       selector: null,        scrollTo: 0 },
  { name: '02-features',   selector: '#features', scrollTo: null },
  { name: '03-compliance', selector: '#features', scrollTo: null, offset: 800 },
  { name: '04-pricing',    selector: '#pricing',  scrollTo: null },
  { name: '05-about',      selector: '#about',    scrollTo: null },
  { name: '06-contact',    selector: '#contact',  scrollTo: null },
];

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,900'],
    defaultViewport: { width: 1280, height: 900 },
  });

  const page = await browser.newPage();

  // Load the page once and let all JS/animations initialise
  await page.goto(BASE_URL, { waitUntil: 'networkidle0' });

  // Force all .reveal elements visible (skip entrance animations for screenshots)
  await page.evaluate(() => {
    document.querySelectorAll('.reveal').forEach(el => {
      el.classList.add('visible');
    });
  });

  for (const s of sections) {
    if (s.selector) {
      await page.evaluate((sel, off) => {
        const el = document.querySelector(sel);
        if (el) {
          const y = el.getBoundingClientRect().top + window.scrollY + (off || 0);
          window.scrollTo({ top: y, behavior: 'instant' });
        }
      }, s.selector, s.offset || 0);
    } else {
      await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'instant' }), s.scrollTo || 0);
    }

    // Short pause to let the page settle after scroll
    await new Promise(r => setTimeout(r, 300));

    const outPath = path.join(OUT_DIR, `${s.name}.png`);
    await page.screenshot({ path: outPath });
    console.log(`✓  ${s.name}.png  →  ${outPath}`);
  }

  await browser.close();
  console.log('\nAll screenshots saved to:', OUT_DIR);
})();
