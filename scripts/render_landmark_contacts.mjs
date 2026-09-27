// Render contact sheets from original JPEGs; no enhancement or generated pixels.
// node scripts/render_landmark_contacts.mjs INPUT_DIRECTORY OUTPUT_DIRECTORY
import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
const [inputArg, outputArg] = process.argv.slice(2);
if (!inputArg || !outputArg) throw Error('Need input and output directories');
const input = path.resolve(inputArg), output = path.resolve(outputArg);
const selection = JSON.parse(await fs.readFile(path.join(input, 'selection.json')));
await fs.mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1700 } });
  for (let start = 0; start < selection.frames.length; start += 20) {
    const rows = selection.frames.slice(start, start + 20);
    const cards = await Promise.all(rows.map(async f => {
      if (!/^frame_\d+\.jpg$/.test(f.name)) throw Error('Invalid frame name');
      const bytes = await fs.readFile(path.join(input, 'images', f.name));
      if (createHash('sha256').update(bytes).digest('hex') !== selection.image_sha256[f.name]) throw Error('Source hash mismatch');
      const side = ['before', 'gap', 'after'].includes(f.side) ? ` ${f.side}` : '';
      return `<figure><figcaption>${f.name}<br>${f.timestamp.toFixed(3)} s${side}</figcaption><img src="data:image/jpeg;base64,${bytes.toString('base64')}"></figure>`;
    }));
    await page.setContent(`<style>body{margin:0;background:#111;color:white;font:14px monospace;display:grid;grid-template-columns:repeat(5,216px)}figure{margin:0}figcaption{height:38px}img{width:216px;height:384px;display:block}</style>${cards.join('')}`);
    await page.evaluate(() => Promise.all([...document.images].map(im => im.decode())));
    await page.screenshot({ path: path.join(output, `contact-${String(start).padStart(3, '0')}.png`), fullPage: true });
  }
} finally { await browser.close(); }
console.log(`Rendered ${selection.frames.length} hash-verified source frames.`);
