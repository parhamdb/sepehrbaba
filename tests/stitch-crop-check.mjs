import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from '@playwright/test';
import {PNG} from 'pngjs';
import {createStitchServer,validateProject} from '../scripts/stitch-editor-server.mjs';
import {validateCrop} from '../src/stitch-crop.js';

// Fixed inventory: contract, rendered extent, transform, independent controls,
// persistence, original bypass, real-assets phone layout, and source integrity.
// Failures retain this temporary directory and its images/result ledger.
const root=await mkdtemp('/tmp/stitch-crop-'),results=[];
const webRoot=path.resolve(process.env.STITCH_TEST_WEB??'dist/stitch-editor');
await mkdir(path.join(root,'assets'));
const header='ply\nformat binary_little_endian 1.0\nelement vertex 1\n'+
 ['x','y','z','f_dc_0','f_dc_1','f_dc_2','opacity','scale_0','scale_1','scale_2','rot_0','rot_1','rot_2','rot_3'].map(n=>`property float ${n}\n`).join('')+'end_header\n';
for(const [id,color] of [['earlier',[1,.1,.1]],['later',[.1,1,.1]]]){
 const values=[0,0,3,...color.map(c=>(c-.5)/.2820947918),6,Math.log(.7),Math.log(.22),Math.log(.1),1,0,0,0];
 const b=Buffer.alloc(values.length*4);values.forEach((v,i)=>b.writeFloatLE(v,i*4));await writeFile(path.join(root,'assets',id+'.ply'),Buffer.concat([Buffer.from(header),b]));
}
const scenes=['earlier','later'].map(id=>({id,label:id,asset:id+'.ply',locked:false,transform:{position:[0,0,0],rotation:[0,0,0],scale:1}}));
const manifest={version:1,camera:{position:[0,0,0],target:[0,0,3]},scenes};
await writeFile(path.join(root,'manifest.json'),JSON.stringify(manifest));
let server,browser,page,url;const errors=[];
async function start(manifestPath=path.join(root,'manifest.json'),assetsRoot=path.join(root,'assets'),stateRoot=path.join(root,'state')){
 ({server}=await createStitchServer({manifestPath,assetsRoot,stateRoot,webRoot}));await new Promise(r=>server.listen(0,'127.0.0.1',r));url=`http://127.0.0.1:${server.address().port}`;
}
async function check(id,fn){if(process.env.CROP_ONLY&&!process.env.CROP_ONLY.split(',').includes(id))return;try{await fn();results.push({id,status:'passed'});}catch(e){results.push({id,status:'failed',error:e.stack});}console.log(id,results.at(-1).status);await writeFile(path.join(root,'results.json'),JSON.stringify(results,null,2));}
const state=()=>page.evaluate(()=>window.stitchEditor);
async function edit(id,value){await page.locator('#'+id).fill(String(value));await page.locator('#'+id).dispatchEvent('change');}
async function image(name){await page.waitForTimeout(500);const b=await page.locator('canvas').screenshot({path:path.join(root,name+'.png')});return PNG.sync.read(b);}
function redCounts(im){let left=0,right=0,top=0,bottom=0,total=0;for(let y=0;y<im.height*.8;y++)for(let x=0;x<im.width;x++){const i=(y*im.width+x)*4;if(im.data[i]>80&&im.data[i]>im.data[i+1]*2){total++;if(x<im.width/2)left++;else right++;if(y<im.height/2)top++;else bottom++;}}return {left,right,top,bottom,total};}
async function importProject(project){await page.locator('#file').setInputFiles({name:'project.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(project))});await page.waitForTimeout(250);}
const crop={enabled:true,min:[-2,-2,2],max:[.05,2,4],feather:0};
let saved;
try{
 await start();browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});page=await browser.newPage({viewport:{width:1000,height:700}});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('dialog',d=>d.accept());
 await page.goto(url);await page.waitForFunction(()=>window.stitchEditor?.ready,null,{timeout:30000});
 await check('C1',async()=>{assert.equal(validateCrop(),null);for(const bad of [{...crop,min:[1,2]}, {...crop,max:[-2,2,4]},{...crop,feather:1},{...crop,enabled:'yes'},{...crop,min:[NaN,0,0]}])assert.throws(()=>validateCrop(bad));const p=(await state()).project;assert(p.scenes.every(s=>s.crop===null));assert.equal(validateProject(p,manifest).scenes.length,2);});
 await check('C2',async()=>{await page.locator('[data-only="earlier"]').click();await page.locator('#crop-box').uncheck();const before=redCounts(await image('full'));assert(before.total>1000);let p=(await state()).project;p.scenes[0].crop=structuredClone(crop);await importProject(p);const after=redCounts(await image('half'));assert(after.total>before.total*.25&&after.total<before.total*.75,JSON.stringify({before,after}));assert(Math.min(after.left,after.right)<Math.max(after.left,after.right)*.2);p.scenes[0].crop.feather=.25;await importProject(p);const faded=redCounts(await image('half-faded'));assert(faded.total<after.total&&faded.total>0,JSON.stringify({after,faded}));});
 await check('C3',async()=>{let p=(await state()).project;p.scenes[0].crop=structuredClone(crop);p.scenes[0].transform.rotation[2]=90;p.scenes[0].transform.scale=1.2;await importProject(p);const half=redCounts(await image('rotated-half'));assert(Math.min(half.top,half.bottom)<Math.max(half.top,half.bottom)*.3,JSON.stringify(half));p.scenes[0].crop=null;await importProject(p);const full=redCounts(await image('rotated-full'));assert(half.total<full.total*.8);p.scenes[0].transform.position[0]=.25;p.scenes[0].crop=structuredClone(crop);await importProject(p);assert((await state()).project.scenes[0].crop.enabled);await image('moved-scaled-crop');});
 await check('C4',async()=>{await page.locator('#scene').selectOption('later');assert.equal(await page.locator('#crop-enabled').isChecked(),false);await page.locator('#crop-central').click();assert((await state()).project.scenes.every(s=>s.crop?.enabled));const valid=(await state()).project.scenes[1].crop;await edit('crop-min-0',valid.max[0]+1);assert.deepEqual((await state()).project.scenes[1].crop,valid);await page.locator('#crop-reset').click();assert.equal((await state()).project.scenes[1].crop,null);assert((await state()).project.scenes[0].crop.enabled);});
 await check('C5',async()=>{await page.locator('#scene').selectOption('earlier');await page.locator('#save').click();await page.waitForFunction(()=>!window.stitchEditor.dirty);saved=(await state()).project;assert.deepEqual(JSON.parse(await readFile(path.join(root,'state/project.json'),'utf8')),saved);await page.reload();await page.waitForFunction(()=>window.stitchEditor?.ready);assert.deepEqual((await state()).project,saved);const bad=structuredClone(saved);bad.scenes[0].crop.max[0]=bad.scenes[0].crop.min[0];const receipt=await(await fetch(url+'/api/project')).json();const response=await fetch(url+'/api/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:receipt.revision,project:bad})});assert.equal(response.status,400);assert.deepEqual((await(await fetch(url+'/api/project')).json()).project,saved);});
 await check('C6',async()=>{await page.locator('[data-only="earlier"]').click();await page.locator('#crop-box').uncheck();let p=(await state()).project;p.scenes[0].transform=scenes[0].transform;p.scenes[0].crop=structuredClone(crop);await importProject(p);const cropped=redCounts(await image('before-bypass'));await page.locator('#filter-original').check();const full=redCounts(await image('bypass'));assert(full.total>cropped.total*1.5);await page.locator('#filter-original').uncheck();const restored=redCounts(await image('after-bypass'));assert(Math.abs(restored.total-cropped.total)<5);});
 await page.close();await new Promise(r=>server.close(r));
 // Render actual source assets with preserved seed poses in an isolated project.
 const assets=path.resolve('evidence/sam31-video-sections');const sourceManifest=JSON.parse(await readFile(path.resolve('evidence/clean-sections/sections.json'),'utf8'));
 sourceManifest.scenes=sourceManifest.scenes.map(s=>({...s,id:s.id+'-tracked',asset:s.id+'-tracked.ply',locked:false}));assert.equal(sourceManifest.scenes.length,2);
 await writeFile(path.join(root,'real.json'),JSON.stringify(sourceManifest));
 const hashes=await Promise.all(sourceManifest.scenes.map(async s=>createHash('sha256').update(await readFile(path.join(assets,s.asset))).digest('hex')));
 await start(path.join(root,'real.json'),assets,path.join(root,'real-state'));page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('dialog',d=>d.accept());
 await page.goto(url);await page.waitForFunction(()=>window.stitchEditor?.ready,null,{timeout:60000});
 await check('C7',async()=>{for(const [width,height] of [[390,844],[320,568],[844,390]]){await page.setViewportSize({width,height});await page.locator('button[data-panel="crop"]').tap();for(const id of ['crop-enabled','crop-min-0-slider','crop-max-2-slider','crop-fade']){await page.locator('#'+id).scrollIntoViewIfNeeded();const b=await page.locator('#'+id).boundingBox();assert(b.x>=0&&b.x+b.width<=width+1&&b.y>=0&&b.y+b.height<=height+1,id);}await page.screenshot({path:path.join(root,`phone-${width}.png`)});}await page.setViewportSize({width:390,height:844});const before=(await state()).project;await page.locator('#crop-central').tap();const changed=(await state()).project;assert.equal(changed.scenes.filter(s=>s.crop?.enabled).length,1);assert.deepEqual(changed.scenes.map(s=>s.transform),before.scenes.map(s=>s.transform));await image('real-crop');await page.locator('#crop-box').uncheck();await page.locator('#crop-fade').fill('15');await page.locator('#crop-fade').dispatchEvent('input');await image('real-fade');});
 await check('C8',async()=>{assert.deepEqual(errors,[]);assert.deepEqual(await Promise.all(sourceManifest.scenes.map(async s=>createHash('sha256').update(await readFile(path.join(assets,s.asset))).digest('hex'))),hashes);});
 console.log(JSON.stringify({root,results},null,2));assert(results.every(r=>r.status==='passed'),'Crop acceptance incomplete; retained '+root);
}finally{await browser?.close();if(server?.listening)await new Promise(r=>server.close(r));console.log('Evidence:',root);}
