// Fresh page per pose, bounded capture, explicit split, local-only asset server.
import {parseArgs} from 'node:util';
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {build} from 'esbuild';
import {chromium} from '@playwright/test';

const {values: args} = parseArgs({options: {
    ply: {type: 'string'}, views: {type: 'string'}, output: {type: 'string'},
    split: {type: 'string'}, only: {type: 'string'}, help: {type: 'boolean'}
}});
if (args.help) {
    console.log('node scripts/render_evaluation.mjs --ply scene.ply --views references/views.json --split train|held-out --output new-directory [--only frame_003139]');
    process.exit(0);
}
if (!args.ply || !args.views || !args.output || !['train', 'held-out'].includes(args.split)) {
    throw Error('Required: --ply, --views, --output and --split train|held-out');
}
const views = JSON.parse(await fs.readFile(args.views, 'utf8')).filter(v =>
    v.split === args.split && (!args.only || v.name === args.only));
if (!views.length) throw Error('No matching views');
for (const v of views) {
    if (!/^[a-zA-Z0-9_-]+$/.test(v.name) || !Number.isInteger(v.width) || !Number.isInteger(v.height)
        || v.width < 1 || v.height < 1 || v.width > 4096 || v.height > 4096) {
        throw Error('Views require safe image stems and integer dimensions <=4096; use prepare_references.py');
    }
}
await fs.access(args.ply);
await fs.mkdir(args.output); // no reuse of stale screenshots or changed assets
const source = fileURLToPath(new URL('./evaluation-renderer.js', import.meta.url));
const bundle = await build({entryPoints: [source], bundle: true, write: false,
    format: 'esm', target: 'es2022', external: ['node:worker_threads']});
const js = bundle.outputFiles[0].contents;
const server = createServer((req, res) => {
    if (req.url === '/scene.ply') {
        res.setHeader('Content-Type', 'application/octet-stream');
        createReadStream(args.ply).on('error', () => res.destroy()).pipe(res);
    } else if (req.url === '/renderer.js') {
        res.setHeader('Content-Type', 'text/javascript'); res.end(js);
    } else if (req.url === '/') {
        res.setHeader('Content-Type', 'text/html');
        res.end('<!doctype html><html><body style="margin:0;background:black"><canvas id="canvas"></canvas><script type="module" src="/renderer.js"></script></body></html>');
    } else { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
const records = [];
const manifest = {split: args.split, requested_views: views.map(v => v.name),
    ply_sha256: createHash('sha256').update(await fs.readFile(args.ply)).digest('hex'),
    views_sha256: createHash('sha256').update(await fs.readFile(args.views)).digest('hex'),
    renderer: 'PlayCanvas 2.22.3 WebGL2 radial CPU sort, AA, black background',
    records, status: 'running'};
const save = () => fs.writeFile(path.join(args.output, 'capture.json'), JSON.stringify(manifest, null, 2)+'\n');
try {
    await save();
    browser = await chromium.launch({headless: true, args: ['--use-angle=swiftshader',
        '--enable-unsafe-swiftshader', '--disable-dev-shm-usage']});
    for (const view of views) {
        const context = await browser.newContext({viewport: {width: view.width, height: view.height}});
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        let timer;
        try {
            await Promise.race([(async () => {
                await page.goto(`http://127.0.0.1:${server.address().port}/`);
                await page.waitForFunction(() => !!window.renderEvaluation);
                const actual = await page.evaluate(v => window.renderEvaluation(v), view);
                // Require repeatable pixels after completed frames. This does not
                // independently certify sorting correctness or scene quality.
                let previous, stable = 0, png;
                for (let attempt = 0; attempt < 15; attempt++) {
                    await page.waitForTimeout(1000);
                    png = await page.evaluate(() => document.getElementById('canvas').toDataURL('image/png'));
                    stable = png === previous ? stable+1 : 0; previous = png;
                    if (stable >= 2) break;
                }
                if (stable < 2 || errors.length) throw Error(`Unstable render or page errors: ${errors.join('; ')}`);
                await fs.writeFile(path.join(args.output, `${view.name}.png`), Buffer.from(png.split(',')[1], 'base64'));
                records.push({name: view.name, actual, status: 'passed', errors});
                await save(); console.log(view.name, 'captured');
            })(), new Promise((_, reject) => {
                timer = setTimeout(() => reject(Error(`Capture timed out: ${view.name}`)), 90000);
            })]);
        } finally { clearTimeout(timer); await context.close(); }
    }
    manifest.status = 'passed'; await save();
} catch (error) {
    manifest.status = 'failed'; manifest.error = String(error); await save(); throw error;
} finally {
    if (browser) await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
}
