// Read-only layout check against the LAN editor. No save or placement actions.
import assert from 'node:assert/strict';
import {mkdir,mkdtemp,rm} from 'node:fs/promises';
import path from 'node:path';
import {createStitchServer} from '../scripts/stitch-editor-server.mjs';
import {chromium} from '@playwright/test';
let url=process.env.STITCH_TEST_URL??'http://127.0.0.1:8092',server,root;
if(process.env.STITCH_TEST_WEB){
  root=await mkdtemp('/tmp/stitch-filter-access-');
  ({server}=await createStitchServer({manifestPath:path.resolve('evidence/clean-sections/sections.json'),assetsRoot:path.resolve('evidence/clean-sections'),stateRoot:root,webRoot:path.resolve(process.env.STITCH_TEST_WEB)}));
  await new Promise(r=>server.listen(0,'127.0.0.1',r));url=`http://127.0.0.1:${server.address().port}`;
}
const before=await(await fetch(url+'/api/project')).json();
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/project',route=>route.request().method()==='GET'?route.continue():route.abort());
 await page.goto(url+'/');await page.waitForFunction(()=>window.stitchEditor?.ready,{},{timeout:90000});
 await mkdir('dist/stitch-editor/filter-access',{recursive:true});
 const results=[];
 for(const [width,height] of [[320,568],[390,844],[844,390],[1280,850]]){
  if(process.env.STITCH_ACCESS_ONLY&&!process.env.STITCH_ACCESS_ONLY.split(',').includes(String(width)))continue;
  try{
   await page.setViewportSize({width,height});const tab=page.getByRole('button',{name:'Filters',exact:true});
   if(await tab.isVisible())await tab.tap();
   // No scrollIntoView/click on the fields: they must be visible immediately.
   const bounds=await page.evaluate(()=>{
    const rect=id=>{const r=document.getElementById(id).getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};};
    return {panel:rect('panel-content'),fields:['filter-opacity','filter-size','filter-ratio','slider-opacity','slider-size','slider-ratio'].map(rect),canvas:rect('canvas')};
   });
   for(const r of bounds.fields){assert(r.left>=0&&r.right<=width+1&&r.top>=0&&r.bottom<=height+1,'Filter outside screen');assert(r.top>=bounds.panel.top-1&&r.bottom<=bounds.panel.bottom+1,'Filter clipped by scroll panel '+JSON.stringify(bounds));}
   assert(bounds.canvas.bottom-bounds.canvas.top>=175,'Scene too small');
   await page.screenshot({path:`dist/stitch-editor/filter-access/${width}x${height}.png`});results.push({width,height,status:'passed'});
  }catch(e){results.push({width,height,status:'failed',error:e.message});}
 }
 if(!process.env.STITCH_ACCESS_ONLY||process.env.STITCH_ACCESS_ONLY.split(',').includes('sliders')){await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Filters',exact:true}).tap();
 const initial=await page.evaluate(()=>window.stitchEditor.project);const selected=await page.evaluate(()=>window.stitchEditor.selected);const index=initial.scenes.findIndex(s=>s.id===selected);
 const box=await page.locator('#slider-opacity').boundingBox();await page.touchscreen.tap(box.x+box.width*.4,box.y+box.height/2);
 await page.waitForFunction(()=>window.stitchEditor.project.scenes.find(s=>s.id===window.stitchEditor.selected).filters.minOpacity>0);
 let edited=await page.evaluate(()=>window.stitchEditor.project);assert.equal(edited.scenes[index].filters.minOpacity,Number(await page.locator('#filter-opacity').inputValue()));
 for(let i=0;i<initial.scenes.length;i++){assert.deepEqual(edited.scenes[i].transform,initial.scenes[i].transform);if(i!==index)assert.deepEqual(edited.scenes[i].filters,initial.scenes[i].filters);}
 await page.locator('#filter-size').fill('75');await page.locator('#filter-size').dispatchEvent('change');assert.equal(await page.locator('#slider-size').inputValue(),'75');assert.equal(await page.locator('#slider-size').getAttribute('max'),'75');
 await page.locator('#slider-size').fill('30');await page.locator('#slider-size').dispatchEvent('input');assert.equal(await page.locator('#slider-size').getAttribute('max'),'75');assert.equal(await page.locator('#filter-size').inputValue(),'30');
 await page.locator('#slider-ratio').fill('12');await page.locator('#slider-ratio').dispatchEvent('input');assert.equal(await page.locator('#filter-ratio').inputValue(),'12');
 results.push({name:'touch slider live update, numeric sync and independent settings',status:'passed'});}
 assert.deepEqual(errors,[]);assert.deepEqual(await(await fetch(url+'/api/project')).json(),before);
 console.log(JSON.stringify({results,projectUnchanged:true,browserErrors:errors},null,2));assert(results.every(r=>r.status==='passed'));
}finally{await browser.close();if(server?.listening)await new Promise(r=>server.close(r));if(root)await rm(root,{recursive:true,force:true});}
