#!/usr/bin/env node
/**
 * HiDPI screenshot capture for the screenshots skill.
 * Self-bootstrapping: installs playwright if not found.
 *
 * Usage:
 *   node capture.js --url URL --out OUTPUT.png [options]
 *
 * Options:
 *   --url       Page URL (required)
 *   --out       Output file path (required)
 *   --width     Viewport width in CSS px (default: 1440)
 *   --height    Viewport height in CSS px (default: 900)
 *   --selector  CSS selector to screenshot (captures that element)
 *   --padding   Padding around selector in px (default: 40)
 *   --scroll-y  Scroll to Y before capturing (default: 0)
 *   --wait      Extra wait ms after page load (default: 500)
 *   --auth-state  Path to Playwright storage state JSON
 *   --dark-mode        Use dark color scheme
 *   --full-page        Capture full scrollable page
 *   --hide CSS,CSS,...  Hide elements (comma-separated selectors, e.g. "nav,header,.cookie-banner")
 */

const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

// ─── Parse args ───────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const get = (flag, def) => {
  const i = args.indexOf(flag);
  return i !== -1 ? args[i + 1] : def;
};
const has = (flag) => args.includes(flag);

const config = {
  url: get('--url', null),
  out: get('--out', null),
  width: parseInt(get('--width', '1440'), 10),
  height: parseInt(get('--height', '900'), 10),
  selector: get('--selector', null),
  padding: parseInt(get('--padding', '40'), 10),
  scrollY: parseInt(get('--scroll-y', '0'), 10),
  wait: parseInt(get('--wait', '500'), 10),
  authState: get('--auth-state', null),
  darkMode: has('--dark-mode'),
  fullPage: has('--full-page'),
  hide: get('--hide', null),  // comma-separated CSS selectors to hide (e.g. "nav,header,.banner")
};

if (!config.url || !config.out) {
  console.error('Usage: node capture.js --url URL --out OUTPUT.png [options]');
  process.exit(1);
}

// ─── Resolve playwright ────────────────────────────────────────────────────────
function resolvePlaywright() {
  // 1. Check cwd node_modules
  const local = path.join(process.cwd(), 'node_modules', 'playwright');
  if (fs.existsSync(local)) return require(local);

  // 2. Check script-dir node_modules
  const scriptDir = path.join(__dirname, 'node_modules', 'playwright');
  if (fs.existsSync(scriptDir)) return require(scriptDir);

  // 3. Try global require
  try { return require('playwright'); } catch (_) {}

  // 4. Install locally into script dir
  console.error('[screenshots] Installing playwright (one-time setup)...');
  const installDir = __dirname;
  const result = spawnSync('npm', ['install', 'playwright', '--prefix', installDir], {
    stdio: 'inherit',
    cwd: installDir,
  });
  if (result.status !== 0) {
    console.error('Failed to install playwright. Please run: npm install playwright');
    process.exit(1);
  }
  // Also install browser
  spawnSync('npx', ['playwright', 'install', 'chromium'], {
    stdio: 'inherit',
    cwd: installDir,
  });
  return require(path.join(installDir, 'node_modules', 'playwright'));
}

const playwright = resolvePlaywright();

// ─── Capture ──────────────────────────────────────────────────────────────────
(async () => {
  const outDir = path.dirname(path.resolve(config.out));
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await playwright.chromium.launch({ headless: true });

  const contextOpts = {
    viewport: { width: config.width, height: config.height },
    deviceScaleFactor: 2,          // true HiDPI / retina output
    colorScheme: config.darkMode ? 'dark' : 'light',
  };
  if (config.authState && fs.existsSync(config.authState)) {
    contextOpts.storageState = config.authState;
  }

  const context = await browser.newContext(contextOpts);
  const page = await context.newPage();

  try {
    await page.goto(config.url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(3000); // extra settle time for lazy-loaded content

    // Hide specified elements (sticky navs, cookie banners, etc.)
    if (config.hide) {
      const selectors = config.hide.split(',').map(s => s.trim()).filter(Boolean);
      await page.addStyleTag({
        content: selectors.map(s => `${s} { display: none !important; }`).join('\n'),
      });
    }

    if (config.wait > 0) {
      await page.waitForTimeout(config.wait);
    }

    if (config.scrollY > 0) {
      await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'instant' }), config.scrollY);
      await page.waitForTimeout(300);
    }

    let screenshotPath = config.out;

    if (config.selector) {
      const locator = page.locator(config.selector).first();
      const count = await page.locator(config.selector).count();

      if (count === 0) {
        console.error(`WARNING: selector "${config.selector}" not found — falling back to viewport`);
        await page.screenshot({ path: screenshotPath, fullPage: config.fullPage });
      } else {
        await locator.scrollIntoViewIfNeeded();
        await page.waitForTimeout(300);

        if (config.padding > 0) {
          const box = await locator.boundingBox();
          if (box) {
            const clip = {
              x: Math.max(0, box.x - config.padding),
              y: Math.max(0, box.y - config.padding),
              width: Math.min(config.width - Math.max(0, box.x - config.padding), box.width + config.padding * 2),
              height: box.height + config.padding * 2,
            };
            await page.screenshot({ path: screenshotPath, clip });
          } else {
            await locator.screenshot({ path: screenshotPath });
          }
        } else {
          await locator.screenshot({ path: screenshotPath });
        }
      }
    } else {
      await page.screenshot({ path: screenshotPath, fullPage: config.fullPage });
    }

    const stat = fs.statSync(screenshotPath);
    const kb = Math.round(stat.size / 1024);
    const realW = config.width * 2;
    const realH = config.height * 2;
    console.log(`OK: ${screenshotPath} (${kb} KB, ~${realW}x${realH} @ 2x)`);
  } catch (err) {
    console.error(`ERROR: ${err.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
