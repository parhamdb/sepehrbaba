// Bounded comparison viewer acceptance check. No 3D scene is loaded.
import { chromium } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
const base=process.env.COMPARISON_BASE_URL;
if(!base)throw Error('Set COMPARISON_BASE_URL to the comparison page');
const report=JSON.parse(await readFile('public/camera-comparison/report.json','utf8'));
const browser=await chromium.launch({headless:true,...(process.env.COMPARISON_BROWSER?{executablePath:process.env.COMPARISON_BROWSER}:{}),args:['--disable-dev-shm-usage']});
const receipts=[];
try{
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(process.env.COMPARISON_MEDIA_ROOT)await page.route('https://media.githubusercontent.com/**/camera-comparison/*.mp4',async route=>{
   const name=new URL(route.request().url()).pathname.split('/').pop();
   const buffer=await readFile(join(process.env.COMPARISON_MEDIA_ROOT,name));
   const range=route.request().headers().range?.match(/^bytes=(\d+)-(\d*)$/);
   const start=range?Number(range[1]):0,end=range&&range[2]?Number(range[2]):buffer.length-1;
   try{await route.fulfill({status:range?206:200,contentType:'video/mp4',
    headers:{'accept-ranges':'bytes',...(range?{'content-range':`bytes ${start}-${end}/${buffer.length}`}:{})},body:buffer.subarray(start,end+1)});
   }catch(error){if(!page.isClosed())throw error}
  });
  await page.goto(base+'#loss-008');await page.waitForFunction(()=>document.querySelectorAll('#clip option').length===19&&!document.getElementById('clip').disabled);
  await page.waitForFunction(()=>document.getElementById('video').readyState>=2,{},{timeout:45000});
  await page.locator('video').evaluate(v=>v.play());
  await page.waitForFunction(()=>document.getElementById('video').currentTime>.3);
  await page.locator('video').evaluate(v=>{v.pause();v.currentTime=10.5});
  await page.waitForFunction(()=>{const v=document.getElementById('video');return !v.seeking&&Math.abs(v.currentTime-10.5)<.1});
  await page.locator('video').evaluate(v=>{v.preload='none'});
  for(const c of report.cases){
   await page.selectOption('#clip',c.id);
   const values=await page.locator('#results tr').evaluateAll(rows=>rows.map(r=>[...r.children].map(x=>x.textContent)));
   for(const [i,m] of ['colmap','vggt','da3'].entries())if(values[i][1]!==`${c.coverage[m].total} / ${c.source_frames}`)throw Error('Coverage mismatch '+c.id);
   if(!await page.locator('#video').getAttribute('src').then(s=>s.endsWith(c.id+'.mp4')))throw Error('Wrong video source');
  }
  await page.selectOption('#clip','loss-007');
  if(!await page.locator('#support').innerText().then(t=>t.includes('VGGT failed')))throw Error('Failure status missing');
  await page.selectOption('#clip','loss-003');
  if(!await page.locator('#connection').innerText().then(t=>t.includes('cannot establish')))throw Error('Unsupported connection missing');
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1);
  if(!fits)throw Error('Horizontal page overflow');
  await page.selectOption('#clip','loss-008');
  await page.locator('video').evaluate(v=>{v.preload='metadata';v.load()});
  await page.waitForFunction(()=>document.getElementById('video').readyState>=2,{},{timeout:45000});
  if(process.env.COMPARISON_SCREENSHOT_PREFIX)await page.screenshot({path:process.env.COMPARISON_SCREENSHOT_PREFIX+'-'+viewport.width+'.png',fullPage:true});
  if(errors.length)throw Error(errors.join('\n'));
  receipts.push({viewport,case_options:19,coverage_rows_checked:57,playback:'passed',seeking:'passed',missing_pose_semantics:'passed',layout:'passed',page_errors:errors});await page.close();
 }
 console.log(JSON.stringify({page:base,receipts}));
 if(process.env.COMPARISON_RECEIPT)await writeFile(process.env.COMPARISON_RECEIPT,JSON.stringify({receipts},null,2)+'\n');
}finally{await browser.close()}
