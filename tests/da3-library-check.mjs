// Focused acceptance for one real DA3 addition and original-library preservation.
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir,mkdtemp} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {PNG} from 'pngjs';
import {createSectionLibrary} from '../scripts/section-library-server.mjs';
const [base,library,output]=process.argv.slice(2);
if(!output)throw Error('Usage: node tests/da3-library-check.mjs BASE LIBRARY NEW_OUTPUT');
await mkdir(output,{recursive:false});
const rows=['append-only-refresh','old-sections-preserved','new-splat-visible','video-number-link'].map(id=>({id,status:'untested'}));
async function check(id,fn){const row=rows.find(r=>r.id===id);try{await fn();row.status='passed';}catch(e){row.status='failed';row.error=e.message;}await writeFile(output+'/verification.json',JSON.stringify({rows,counts:Object.fromEntries(['passed','failed','blocked','untested'].map(s=>[s,rows.filter(r=>r.status===s).length]))},null,2));console.log(id,row.status);}
const before=JSON.parse(await readFile('evidence/section-library/catalog.json'));
const live=JSON.parse(await readFile(path.join(library,'catalog.json')));
const added=live.sections.find(s=>s.camera_method==='DA3');
await check('append-only-refresh',async()=>{
 const tmp=await mkdtemp(path.join(os.tmpdir(),'da3-refresh-')),catalogPath=path.join(tmp,'catalog.json');
 await writeFile(catalogPath,JSON.stringify(before));
 const {server}=await createSectionLibrary({library:tmp,state:path.join(tmp,'state')});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const url=`http://127.0.0.1:${server.address().port}/api/catalog`;
 try{
  assert.equal((await(await fetch(url)).json()).sections.length,72);
  await writeFile(catalogPath,JSON.stringify(live));assert.equal((await(await fetch(url)).json()).sections.length,live.sections.length);
  const bad=structuredClone(live);bad.sections[0].sha256='changed';await writeFile(catalogPath,JSON.stringify(bad));assert.equal((await fetch(url)).status,400);
 }finally{await new Promise(r=>server.close(r));}
});
await check('old-sections-preserved',async()=>{
 assert.deepEqual(live.sections.slice(0,72),before.sections);
 assert(added);assert.equal(added.number,73);assert.match(added.mask_method,/No exclusion/);
 const c=await(await fetch(base+'/api/catalog')).json();assert.equal(c.sections[72].number,73);
 const represented=new Set(live.sections.flatMap(s=>s.frame_names));assert.equal(represented.size,live.trained_frames);
});
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
try{
 await check('new-splat-visible',async()=>{
  assert(added);const p=await browser.newPage({viewport:{width:1100,height:900}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  try{await p.goto(`${base}/pair/${added.id}/`);await p.waitForFunction(()=>window.stitchEditor?.ready,null,{timeout:60000});
   assert.deepEqual(await p.evaluate(()=>window.stitchEditor.project.scenes.map(s=>s.id)),[added.id]);
   assert.match(await p.locator('#scene').textContent(),/DA3 experimental/);
   const png=PNG.sync.read(await p.locator('canvas').screenshot({path:output+'/pilot-editor.png'}));let light=0;for(let i=0;i<png.data.length;i+=4)if(Math.max(...png.data.subarray(i,i+3))>65)light++;
   assert(light/png.width/png.height>.001,'No visible geometry');assert.deepEqual(errors,[]);
  }finally{await p.close();}
 });
 await check('video-number-link',async()=>{
  assert(added);const p=await browser.newPage({viewport:{width:390,height:844}});
  try{await p.goto(`${base}/?t=${added.start}&section=${added.id}#source`);
   await p.waitForFunction(t=>{const v=document.querySelector('#source-video');return v?.readyState>=2&&!v.seeking&&Math.abs(v.currentTime-t)<.2},added.start,{timeout:30000});
   assert.match(await p.locator('#section-overlay').textContent(),/#73/);
   assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.equal(await p.locator('#video-jump option').count(),live.sections.length);
   await p.locator('#source').screenshot({path:output+'/pilot-video-mobile.png'});
  }finally{await p.close();}
 });
}finally{await browser.close();}
if(rows.some(r=>r.status!=='passed'))process.exitCode=1;
