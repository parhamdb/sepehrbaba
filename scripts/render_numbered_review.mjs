// Render the actual review page into marked/unmarked source comparison boards.
// node scripts/render_numbered_review.mjs PUBLIC_DIRECTORY OUTPUT_DIRECTORY
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { createHash } from 'node:crypto';
const [rootArg, outputArg] = process.argv.slice(2);
if (!rootArg || !outputArg) throw Error('Need public and output directories');
const root = path.resolve(rootArg), output = path.resolve(outputArg);
await fs.mkdir(output, { recursive: true });
const questions = JSON.parse(await fs.readFile(path.join(root, 'numbered-landmark-review/questions.json')));
const server = http.createServer(async (req, res) => {
  try {
    const file = path.resolve(root, '.' + new URL(req.url, 'http://localhost').pathname);
    if (!file.startsWith(root + '/')) return res.writeHead(403).end();
    res.setHeader('Content-Type', file.endsWith('.html') ? 'text/html' : file.endsWith('.json') ? 'application/json' : 'image/jpeg');
    res.end(await fs.readFile(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1300, height: 1000 } });
  await page.goto(`http://127.0.0.1:${server.address().port}/numbered-landmark-review.html`);
  await page.locator('#question option').first().waitFor({ state: 'attached' });
  for (let i = 0; i < questions.questions.length; i++) {
    const id = questions.questions[i].id;
    if (!/^Q\d+$/.test(id)) throw Error('Invalid question ID');
    await page.locator('#question').selectOption(String(i));
    for (const marked of [true, false]) {
      await page.locator('#markers').setChecked(marked);
      await page.waitForTimeout(200);
      await page.locator('.views').screenshot({ path: path.join(output, `${id}-${marked ? 'marked' : 'unmarked'}.png`) });
    }
  }
  const hashes = {};
  for (const name of (await fs.readdir(output)).filter(n => /^Q\d+-(un)?marked\.png$/.test(n))) {
    hashes[name] = createHash('sha256').update(await fs.readFile(path.join(output, name))).digest('hex');
  }
  await fs.writeFile(path.join(output, 'manifest.json'), JSON.stringify({ source: 'Browser screenshots: SVG overlays over unchanged original JPEG pixels', sha256: hashes }, null, 2)+'\n');
  console.log(`Rendered ${Object.keys(hashes).length} comparison boards.`);
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
