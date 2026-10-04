// Focused original-video linkage checks against a real running LAN library.
import assert from 'node:assert/strict';
import {open,readFile,mkdir,writeFile} from 'node:fs/promises';
import {chromium} from '@playwright/test';
const [base,videoPath,output]=process.argv.slice(2);
if(!base||!videoPath||!output)throw Error('Usage: node tests/section-video-check.mjs BASE_URL VIDEO NEW_OUTPUT');
await mkdir(output,{recursive:false});
const ids=['video-ranges','numbered-editor-metadata','playback-seek-overlap-gap','editor-source-link','mobile-video'],rows=ids.map(id=>({id,status:'untested'}));
async function check(id,fn){if(process.env.CHECK_IDS&&!process.env.CHECK_IDS.split(',').includes(id))return;const row=rows.find(x=>x.id===id);try{await fn();row.status='passed';}catch(e){row.status='failed';row.error=e.message;}await writeFile(output+'/verification.json',JSON.stringify({rows,counts:Object.fromEntries(['passed','failed','blocked','untested'].map(s=>[s,rows.filter(r=>r.status===s).length]))},null,2)+'\n');console.log(id,row.status);}
const catalog=await(await fetch(base+'/api/catalog')).json();
await check('video-ranges',async()=>{
 const file=await open(videoPath),size=(await file.stat()).size;
 try{
  const h=await fetch(base+'/source-video.mp4',{method:'HEAD'});assert.equal(h.status,200);assert.equal(Number(h.headers.get('content-length')),size);assert.equal(h.headers.get('accept-ranges'),'bytes');assert.equal(h.headers.get('content-type'),'video/mp4');
  for(const [range,start,length] of [['bytes=0-99',0,100],['bytes=4096-8191',4096,4096],['bytes=-100',size-100,100],['bytes='+String(size-50)+'-',size-50,50]]){
   const response=await fetch(base+'/source-video.mp4',{headers:{Range:range}});assert.equal(response.status,206);const wanted=Buffer.alloc(length);await file.read(wanted,0,length,start);assert.deepEqual(Buffer.from(await response.arrayBuffer()),wanted);
  }
  for(const range of ['bytes=10-2',`bytes=${size}-`,'bytes=-0','bytes=0-1,4-5'])assert.equal((await fetch(base+'/source-video.mp4',{headers:{Range:range}})).status,416);
 }finally{await file.close();}
});
const a=catalog.sections[34],b=catalog.sections[35];
await check('numbered-editor-metadata',async()=>{
 assert.deepEqual(catalog.sections.map(s=>s.number),Array.from({length:72},(_,i)=>i+1));
 const pair=await(await fetch(`${base}/pair/${a.id}/${b.id}/api/project`)).json();assert(pair.manifest.scenes[0].label.startsWith('#35'));assert(pair.manifest.scenes[1].label.startsWith('#36'));
 for(const [i,s] of [a,b].entries()){const info=pair.manifest.scenes[i].sourceVideo;assert.equal(info.number,s.number);const url=new URL(info.url,base);assert.equal(Number(url.searchParams.get('t')),s.start);assert.equal(url.searchParams.get('section'),s.id);}
});
const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
async function page(viewport={width:1100,height:900}){const p=await browser.newPage({viewport});p.errors=[];p.on('pageerror',e=>p.errors.push(e.message));return p;}
async function ready(p){await p.waitForFunction(()=>document.querySelector('#source-video')?.readyState>=2,null,{timeout:30000});}
async function seek(p,t){await p.locator('#source-video').evaluate((v,t)=>{v.pause();v.currentTime=t;},t);await p.waitForFunction(t=>{const v=document.querySelector('#source-video');return !v.seeking&&Math.abs(v.currentTime-t)<.2},t);await p.waitForTimeout(100);}
try{
 await check('playback-seek-overlap-gap',async()=>{
  const p=await page();try{
   await p.goto(base);await ready(p);assert.equal(await p.locator('#video-jump option').count(),72);
   for(const s of catalog.sections)assert((await p.locator(`#video-jump option[value="${s.id}"]`).textContent()).startsWith('#'+String(s.number).padStart(2,'0')));
   for(const t of [25,365,415.5,730]){
    await seek(p,t);const wanted=catalog.sections.filter(s=>s.start<=t&&t<=s.end).map(s=>`#${String(s.number).padStart(2,'0')}`);const text=await p.locator('#section-overlay').textContent();
    if(wanted.length)for(const n of wanted)assert(text.includes(n),text);else assert(text.includes('No reconstructed section'),text);
    assert.equal(await p.locator('#video-sections a').count(),wanted.length);
   }
   for(const index of [0,34,71]){const s=catalog.sections[index];await p.selectOption('#video-jump',s.id);await p.waitForFunction(t=>Math.abs(document.querySelector('#source-video').currentTime-t)<.2,s.start);assert((await p.locator('#section-overlay').textContent()).includes('#'+String(s.number).padStart(2,'0')));}
   await seek(p,24.5);await p.locator('#source-video').evaluate(v=>{v.muted=true;return v.play();});await p.waitForFunction(()=>document.querySelector('#source-video').currentTime>25.2,null,{timeout:10000});await p.locator('#source-video').evaluate(v=>v.pause());assert((await p.locator('#section-overlay').textContent()).includes('#02'));
   await p.locator('#source').screenshot({path:output+'/desktop-video.png'});assert.deepEqual(p.errors,[]);
  }finally{await p.close();}
 });
 await check('editor-source-link',async()=>{
  const p=await page();try{
   await p.goto(`${base}/pair/${a.id}/${b.id}/`);await p.waitForFunction(()=>window.stitchEditor?.ready,null,{timeout:60000});await p.selectOption('#scene',b.id);assert((await p.locator('#source-video-link').textContent()).includes('#36'));assert.equal(await p.locator('#source-video-link').getAttribute('target'),'_blank');
   const href=await p.locator('#source-video-link').getAttribute('href');await p.goto(new URL(href,base).href);await ready(p);await p.waitForFunction(t=>Math.abs(document.querySelector('#source-video').currentTime-t)<.2,b.start);assert((await p.locator('#section-overlay').textContent()).includes('#36'));assert.deepEqual(p.errors,[]);
  }finally{await p.close();}
 });
 await check('mobile-video',async()=>{
  const p=await page({width:390,height:844});try{
   await p.goto(base);await ready(p);await p.locator(`[data-watch="${b.id}"]`).click();await p.waitForFunction(t=>Math.abs(document.querySelector('#source-video').currentTime-t)<.2,b.start);assert((await p.locator('#section-overlay').textContent()).includes('#36'));assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await p.locator('#source-video').evaluate(v=>v.playsInline));await p.locator('#source').screenshot({path:output+'/mobile-video.png'});assert.deepEqual(p.errors,[]);
  }finally{await p.close();}
 });
}finally{await browser.close();}
if(rows.some(r=>r.status==='failed'))process.exitCode=1;
