// Regression for edits made while a save acknowledgment is delayed.
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {createStitchServer} from '../scripts/stitch-editor-server.mjs';
const root=await mkdtemp(path.join(tmpdir(),'stitch-save-race-'));
const manifestPath=path.join(root,'manifest.json');
await writeFile(manifestPath,JSON.stringify({version:1,scenes:[{id:'scene',asset:'preview.ply',locked:false}]}));
let server,browser,release;
try {
 ({server}=await createStitchServer({manifestPath,assetsRoot:path.resolve(process.env.STITCH_TEST_ASSETS??'public/assets'),stateRoot:path.join(root,'state'),webRoot:path.resolve('dist/stitch-editor')}));
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 const page=await browser.newPage();await page.goto(`http://127.0.0.1:${server.address().port}`);await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:90000});
 const edit=async n=>{await page.locator('#position-0').fill(String(n));await page.locator('#position-0').dispatchEvent('change');};
 let acknowledge;const submitted=new Promise(r=>acknowledge=r);const gate=new Promise(r=>release=r);
 await page.route('**/api/project',async route=>{if(route.request().method()!=='PUT')return route.continue();const response=await route.fetch();acknowledge();await gate;await route.fulfill({response});});
 await edit(.1);await page.locator('#save').click();await submitted;await edit(.2);release();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('newer changes'));
 assert.equal(await page.evaluate(()=>window.stitchEditor.dirty),true);
 let saved=await(await fetch(`http://127.0.0.1:${server.address().port}/api/project`)).json();assert.equal(saved.project.scenes[0].transform.position[0],.1);
 await page.unroute('**/api/project');await page.locator('#save').click();await page.waitForFunction(()=>!window.stitchEditor.dirty);
 saved=await(await fetch(`http://127.0.0.1:${server.address().port}/api/project`)).json();assert.equal(saved.project.scenes[0].transform.position[0],.2);
 console.log('PASS: in-flight edits remain unsaved until separately persisted');
} finally {release?.();await browser?.close();if(server?.listening)await new Promise(r=>server.close(r));await rm(root,{recursive:true,force:true});}
