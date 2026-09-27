import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,rm,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';
import {PNG} from 'pngjs';
import {createStitchServer} from '../scripts/stitch-editor-server.mjs';
import {validateFilters} from '../src/stitch-filters.js';
const root=await mkdtemp(path.join(tmpdir(),'stitch-filters-'));
const assetsRoot=path.resolve('evidence/clean-sections'),manifestPath=path.join(assetsRoot,'sections.json'),webRoot=path.resolve(process.env.STITCH_TEST_WEB??'dist/stitch-editor');
const hash=data=>createHash('sha256').update(data).digest('hex');
const originalHashes=await Promise.all(['earlier','later'].map(async id=>hash(await readFile(path.join(assetsRoot,id+'-clean.ply')))));
const results=[];let browser,server,page;
async function check(name,fn){if(process.env.STITCH_FILTER_ONLY&&!name.includes(process.env.STITCH_FILTER_ONLY))return;try{await fn();results.push({name,status:'passed'});console.log('PASS',name);}catch(e){results.push({name,status:'failed',error:e.message});console.log('FAIL',name,e.message);}}
async function start(){({server}=await createStitchServer({manifestPath,assetsRoot,stateRoot:root,webRoot}));await new Promise(r=>server.listen(0,'127.0.0.1',r));return `http://127.0.0.1:${server.address().port}`;}
try{
 let url=await start();browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto(url);await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:90000});await page.locator('.panel-tabs [data-panel="inspect"]').tap();
 const state=()=>page.evaluate(()=>window.stitchEditor);
 const edit=async(id,value)=>{await page.locator('#'+id).fill(String(value));await page.locator('#'+id).dispatchEvent('change');};
 const shot=async name=>{await page.waitForTimeout(200);const png=await page.locator('canvas').screenshot();await writeFile(`dist/stitch-editor/filter-check/${name}.png`,png);const decoded=PNG.sync.read(png);return hash(decoded.data.subarray(50*decoded.width*4,(decoded.height-55)*decoded.width*4));};
 await mkdir('dist/stitch-editor/filter-check',{recursive:true});
 await check('independent visibility and Only controls without moving alignment',async()=>{
  const before=await state();await page.locator('[data-only="earlier"]').tap();let s=await state();assert.equal(s.selected,'earlier');assert.deepEqual(s.project.scenes.map(s=>s.visible),[true,false]);
  await page.locator('[data-visible="later"]').check();await page.selectOption('#scene','later');s=await state();assert.deepEqual(s.project.scenes.map(s=>s.visible),[true,true]);
  assert.deepEqual(s.project.scenes.map(s=>s.transform),before.project.scenes.map(s=>s.transform));
  await page.locator('[data-visible="earlier"]').uncheck();await page.locator('[data-visible="later"]').uncheck();assert.deepEqual((await state()).project.scenes.map(s=>s.visible),[false,false]);await page.locator('#inspect-show-all').tap();
 });
 await check('three filters change rendering; Original restores pixels; other section unchanged',async()=>{
  await page.locator('[data-only="earlier"]').tap();const earlier=await shot('earlier-original');
  // Edit the hidden later section without altering the current visible earlier image.
  await page.locator('[data-visible="later"]').check();await page.locator('[data-visible="later"]').uncheck();await page.selectOption('#scene','later');
  const before=await state();await edit('filter-opacity',.2);await edit('filter-size',4);await edit('filter-ratio',8);
  assert.deepEqual(await shot('earlier-with-later-filtered'),earlier);assert.equal((await state()).filters.earlier.hidden,0);
  await page.locator('[data-only="later"]').tap();const filtered=await shot('later-filtered');let s=await state();assert(s.filters.later.hidden>0&&s.filters.later.hidden<s.filters.later.total);
  assert.deepEqual(s.project.scenes.map(s=>s.transform),before.project.scenes.map(s=>s.transform));
  await page.locator('#filter-original').check();const original=await shot('later-original');assert.notDeepEqual(filtered,original);assert.equal((await state()).filters.later.hidden,0);
  await page.locator('#filter-original').uncheck();assert.deepEqual(await shot('later-filtered-again'),filtered);
  await page.locator('#filter-reset').tap();assert.deepEqual(await shot('later-reset'),original);
  // Verify each individual filter has a rendered effect, not merely a changed count.
  for(const [id,value] of [['filter-opacity',.2],['filter-size',4],['filter-ratio',8]]){await edit(id,value);assert((await state()).filters.later.hidden>0);assert.notDeepEqual(await shot(id),original);await page.locator('#filter-reset').tap();}
 });
 await check('independent filter settings persist through save, reload, export/import and restart',async()=>{
  await page.locator('[data-only="earlier"]').tap();await edit('filter-ratio',12);assert((await state()).project.scenes[0].locked);
  await page.locator('[data-only="later"]').tap();await edit('filter-opacity',.1);await edit('filter-size',6);await page.locator('#save').tap();await page.waitForFunction(()=>!window.stitchEditor.dirty);
  const saved=(await state()).project;
  await page.locator('#filter-original').check();assert.equal((await state()).dirty,false);
  await page.reload();await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:90000});assert.deepEqual((await state()).project,saved);assert.equal((await state()).filters.later.original,false);
  await page.locator('.panel-tabs [data-panel="more"]').tap();const download=page.waitForEvent('download');await page.locator('#export').tap();const file=await download;const exported=JSON.parse(await readFile(await file.path(),'utf8'));assert.deepEqual(exported,saved);
  await page.locator('#file').setInputFiles({name:'filters.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(exported))});assert.deepEqual((await state()).project,saved);
  page.on('dialog',d=>d.accept());await page.close();await new Promise(r=>server.close(r));url=await start();const receipt=await(await fetch(url+'/api/project')).json();assert.deepEqual(receipt.project,saved);
  page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});await page.goto(url);await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:90000});
 });
 await check('invalid filters rejected; legacy projects default to original',async()=>{
  assert.deepEqual(validateFilters(),{minOpacity:0,maxSize:0,maxRatio:0});
  const receipt=await(await fetch(url+'/api/project')).json();receipt.project.scenes[0].filters={minOpacity:-1,maxSize:0,maxRatio:0};
  const response=await fetch(url+'/api/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:receipt.revision,project:receipt.project})});assert.equal(response.status,400);
  assert.equal((await(await fetch(url+'/api/project')).json()).revision,receipt.revision);
 });
 await check('phone inspection controls and source integrity',async()=>{
  for(const [width,height] of [[320,568],[390,844],[844,390]]){await page.setViewportSize({width,height});await page.locator('.panel-tabs [data-panel="inspect"]').tap();
   for(const selector of ['[data-only="earlier"]','#filter-ratio','#filter-original']){await page.locator(selector).scrollIntoViewIfNeeded();const b=await page.locator(selector).boundingBox();assert(b.x>=0&&b.y>=0&&b.x+b.width<=width+1&&b.y+b.height<=height+1);const canvas=await page.locator('canvas').boundingBox();assert(canvas.width>=240&&canvas.height>=190);}
   await page.screenshot({path:`dist/stitch-editor/filter-check/layout-${width}.png`});
  }
  assert.deepEqual(await Promise.all(['earlier','later'].map(async id=>hash(await readFile(path.join(assetsRoot,id+'-clean.ply'))))),originalHashes);assert.deepEqual(errors,[]);
 });
 console.log(JSON.stringify(results,null,2));assert(results.every(r=>r.status==='passed'),'Section filter acceptance incomplete');
}finally{await browser?.close();if(server?.listening)await new Promise(r=>server.close(r));await rm(root,{recursive:true,force:true});}
