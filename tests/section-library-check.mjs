// Real-assets acceptance: library integrity, every requested splat, pair isolation,
// mobile selection and preserved existing pair. Private paths come from arguments.
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';
import {PNG} from 'pngjs';
import {createSectionLibrary} from '../scripts/section-library-server.mjs';
const [library,output]=process.argv.slice(2);
if(!library||!output)throw Error('Usage: node tests/section-library-check.mjs LIBRARY NEW_OUTPUT');
await mkdir(output,{recursive:false});
const state=await mkdtemp(path.join(os.tmpdir(),'sepehr-library-check-'));
const {server,catalog}=await createSectionLibrary({library,state});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const rows=[],errors=[];
const receipt=async()=>writeFile(path.join(output,'verification.json'),JSON.stringify({rows,errors,counts:Object.fromEntries(['passed','failed','blocked','untested'].map(status=>[status,status==='untested'?catalog.sections.length+4-rows.length:rows.filter(r=>r.status===status).length]))},null,2)+'\n');
async function check(id,action){if(process.env.SKIP_IDS?.split(',').includes(id))return;if(process.env.CHECK_IDS&&!process.env.CHECK_IDS.split(',').includes(id))return;try{const result=await action();rows.push({id,status:'passed',...result});}catch(e){rows.push({id,status:'failed',error:e.message});}await receipt();console.log(id,rows.at(-1).status);}
let browser;
async function launch(){return chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});}
async function open(url,viewport={width:900,height:780}){
 const page=await browser.newPage({viewport});page.on('pageerror',e=>errors.push(e.message));await page.goto(url);return page;
}
async function ready(page){await page.waitForFunction(()=>window.stitchEditor?.ready,null,{timeout:60000});await page.waitForTimeout(200);}
try{
 await check('inventory',async()=>{
  const names=new Set();
  for(const s of catalog.sections){const bytes=await readFile(path.join(library,'assets',s.asset));assert.equal(createHash('sha256').update(bytes).digest('hex'),s.sha256);for(const name of s.frame_names)names.add(name);}
  assert.equal(names.size,catalog.trained_frames);assert.equal(catalog.coverage_bins.reduce((n,b)=>n+b.source_frames,0),catalog.source_frames);assert.equal(catalog.missing_intervals.reduce((n,b)=>n+b.frames,0),catalog.source_frames-catalog.trained_frames);assert.equal(catalog.windows.length,37);assert(catalog.windows.every(w=>w.status==='processed'));
  return {models:catalog.sections.length,frames:names.size};
 });
 browser=await launch();
 const selected=process.env.SECTION_IDS?catalog.sections.filter(s=>process.env.SECTION_IDS.split(',').includes(s.id)):catalog.sections;
 for(const [index,s] of selected.entries()){
  await check(`render-${s.id}`,async()=>{
   const page=await open(`${base}/pair/${s.id}/`);
   try{await ready(page);assert.deepEqual(await page.evaluate(()=>window.stitchEditor.project.scenes.map(s=>s.id)),[s.id]);
    const bytes=await page.locator('canvas').screenshot({path:path.join(output,s.id+'.png')});const png=PNG.sync.read(bytes);let light=0;
    for(let i=0;i<png.data.length;i+=4)if(Math.max(...png.data.subarray(i,i+3))>65)light++;
    assert(light/png.width/png.height>.001,'No visible scene pixels');return {visibleFraction:light/png.width/png.height};
   }finally{await page.close();}
  });
  if((index+1)%12===0){await browser.close();browser=await launch();}
 }
 await check('pair-edit-save-isolation',async()=>{
  const [a,b,c]=catalog.sections.slice(0,3).map(s=>s.id),route=`${base}/pair/${a}/${b}`;
  const page=await open(route+'/');
  try{
   await ready(page);assert.equal(await page.locator('#section-list .section-entry').count(),2);
   await page.selectOption('#scene',b);
   const before=await page.evaluate(()=>window.stitchEditor.project.scenes.find(s=>s.id===window.stitchEditor.selected).transform.position[0]);
   await page.locator('#position-0').fill(String(before+.125));await page.locator('#position-0').dispatchEvent('change');
   await page.locator('#save').click();await page.waitForFunction(()=>!window.stitchEditor.dirty);
   const saved=await(await fetch(route+'/api/project')).json();assert.equal(saved.project.scenes.find(s=>s.id===b).transform.position[0],before+.125);
   await page.reload();await ready(page);assert.deepEqual(await page.evaluate(()=>window.stitchEditor.project),saved.project);
   await page.locator(`[data-only="${b}"]`).click();assert.deepEqual(await page.evaluate(()=>window.stitchEditor.project.scenes.filter(s=>s.visible).map(s=>s.id)),[b]);
   await page.locator('#slider-ratio').evaluate(el=>{el.value='10';el.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await page.evaluate(()=>window.stitchEditor.project.scenes.find(s=>s.id===window.stitchEditor.selected).filters.maxRatio),10);
   const other=await(await fetch(`${base}/pair/${a}/${c}/api/project`)).json();assert.equal(other.project.scenes[0].id,a);assert.equal(other.project.scenes[1].id,c);
   const single=await(await fetch(`${base}/pair/${b}/api/project`)).json();assert.equal(single.project.scenes[0].transform.position[0],before);
   assert.equal((await fetch(`${base}/pair/${a}/${a}/api/project`)).status,404);
   return {exactlyTwo:true,savedReload:true,otherPairAndSingleUnaffected:true};
  }finally{await page.close();}
 });
 await check('mobile-library-selection',async()=>{
  const page=await open(base+'/',{width:390,height:844});
  try{await page.waitForSelector('article');assert.equal(await page.locator('article').count(),catalog.sections.length);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(output,'mobile.png')});await page.locator('#open').click();await ready(page);assert.equal(await page.locator('#section-list .section-entry').count(),2);return {sections:catalog.sections.length,overflow:false};}finally{await page.close();}
 });
 await check('browser-errors',async()=>{assert.deepEqual(errors,[]);return {count:0};});
}finally{if(browser)await browser.close();await new Promise(r=>server.close(r));await receipt();}
if(rows.some(r=>r.status!=='passed'))process.exitCode=1;
