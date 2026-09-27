// Actual Gaussian rendering and touch input; all writes use an isolated project.
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {chromium} from '@playwright/test';
import {createStitchServer} from '../scripts/stitch-editor-server.mjs';
const root=await mkdtemp(path.join(tmpdir(),'stitch-mobile-'));
const manifestPath=path.join(root,'manifest.json');
await writeFile(manifestPath,JSON.stringify({version:1,scenes:[{id:'earlier',asset:'preview.ply',locked:true},{id:'later',asset:'preview.ply',locked:false}]}));
let server,browser;
const results=[];
try {
 ({server}=await createStitchServer({manifestPath,assetsRoot:path.resolve(process.env.STITCH_TEST_ASSETS??'public/assets'),stateRoot:path.join(root,'state'),webRoot:path.resolve(process.env.STITCH_TEST_WEB??'dist/stitch-editor')}));
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${server.address().port}`);await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:120000});
 async function check(name,fn){if(process.env.STITCH_MOBILE_ONLY&&!name.includes(process.env.STITCH_MOBILE_ONLY))return;try{await fn();results.push({name,status:'passed'});}catch(e){results.push({name,status:'failed',error:e.message});}}
 async function fits(selector){const box=await page.locator(selector).boundingBox();const size=page.viewportSize();assert(box&&box.x>=0&&box.y>=0&&box.x+box.width<=size.width+1&&box.y+box.height<=size.height+1,`${selector} not in viewport`);return box;}
 const tab=group=>page.locator(`.panel-tabs [data-panel=${group}]`).tap();
 await check('portrait controls, locked reference and isolated save/reload',async()=>{
  const canvas=await fits('canvas');assert(canvas.height>=280);await fits('#save');await fits('#position-2');
  assert((await fits('[aria-label="Increase position X"]')).width>=44);
  await page.locator('[aria-label="Increase position X"]').tap();assert.equal(await page.evaluate(()=>window.stitchEditor.project.scenes[1].transform.position[0]),.05);
  await tab('rotation');await fits('#rotation-2');await page.locator('[aria-label="Increase rotation Z"]').tap();
  await tab('scale');await fits('#scale');await page.locator('[aria-label="Increase scale "]').tap();
  await page.locator('#save').tap();await page.waitForFunction(()=>!window.stitchEditor.dirty);
  await page.reload();await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:120000});
  const state=await page.evaluate(()=>window.stitchEditor);assert.equal(state.project.scenes[1].transform.position[0],.05);assert.equal(state.project.scenes[1].transform.rotation[2],1);assert.equal(state.project.scenes[1].transform.scale,1.01);
  await tab('more');await page.locator('#previous').tap();assert(await page.locator('#reset-transform').isDisabled());await tab('position');assert(await page.locator('#position-0').isDisabled());await tab('more');await page.locator('#next').tap();await tab('position');
 });
 await check('real one-finger orbit, two-finger pan/pinch and finger-release transition',async()=>{
  const session=await page.context().newCDPSession(page);const box=await fits('canvas');
  const state=await page.evaluate(()=>window.stitchEditor);
  const touch=async(type,points)=>{await session.send('Input.dispatchTouchEvent',{type,touchPoints:points.map(([id,x,y])=>({id,x:box.x+x,y:box.y+y}))});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));};
  await touch('touchStart',[[1,100,100]]);await touch('touchMove',[[1,140,120]]);await touch('touchEnd',[]);
  const orbit=await page.evaluate(()=>window.stitchEditor);assert.notEqual(orbit.camera.yaw,state.camera.yaw);
  await touch('touchStart',[[1,100,100],[2,200,100]]);await touch('touchMove',[[1,70,100],[2,230,100]]);
  const zoom=await page.evaluate(()=>window.stitchEditor);assert(zoom.camera.distance<orbit.camera.distance*.8);assert.equal(zoom.camera.yaw,orbit.camera.yaw);
  await touch('touchMove',[[1,90,130],[2,250,130]]);const pan=await page.evaluate(()=>window.stitchEditor);assert.notDeepEqual(pan.camera.target,zoom.camera.target);assert.equal(pan.camera.yaw,zoom.camera.yaw);
  await touch('touchEnd',[[1,90,130]]);await touch('touchMove',[[1,100,135]]);await touch('touchEnd',[]);
  const end=await page.evaluate(()=>window.stitchEditor);assert(Math.abs(end.camera.yaw-pan.camera.yaw)<=4);assert.deepEqual(end.project,state.project);assert.equal(end.dirty,false);
  await session.detach();
 });
 await check('phone portrait/landscape, narrow phone, tablet and desktop layout',async()=>{
  await mkdir('dist/stitch-editor/mobile-check',{recursive:true});
  for(const [width,height] of [[390,844],[320,568],[844,390],[768,1024],[1280,850]]){
   await page.setViewportSize({width,height});await tabIfVisible();
   await fits('canvas');await fits('#save');const canvas=await page.locator('canvas').boundingBox();assert(canvas.width>=240&&canvas.height>=190);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight));
   await page.screenshot({path:`dist/stitch-editor/mobile-check/${width}x${height}.png`});
  }
  async function tabIfVisible(){if(await page.locator('.panel-tabs').isVisible())await tab('position');}
  await page.setViewportSize({width:390,height:844});const before=await page.locator('canvas').boundingBox();await page.locator('#panel-toggle').tap();const after=await page.locator('canvas').boundingBox();assert(after.height>before.height);await fits('#save');await page.locator('#panel-toggle').tap();await fits('#position-2');
 });
 await check('no browser exceptions',async()=>assert.deepEqual(errors,[]));
 console.log(JSON.stringify(results,null,2));assert(results.every(r=>r.status==='passed'),'Mobile acceptance incomplete');
}finally{await browser?.close();if(server?.listening)await new Promise(r=>server.close(r));await rm(root,{recursive:true,force:true});}
