import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const base=process.env.FLOOR_BASE_URL;
if(!base)throw Error('Set FLOOR_BASE_URL');
const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
const results=[];
try{
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.waitForFunction(()=>document.querySelector('#item').options.length===100);
  const loaded=()=>page.waitForFunction(()=>{const i=document.querySelector('#review');return i.complete&&i.naturalWidth>0;});
  await loaded();
  if(!(await page.locator('#status').textContent()).includes('0 accepted joins'))throw Error('Missing zero-joins limitation');
  if(await page.locator('#scale-chart circle').count()!==87)throw Error('Scale chart support mismatch');
  await page.locator('#next').click();await loaded();
  if(await page.locator('#item').inputValue()!=='1')throw Error('Next control failed');
  await page.locator('#item').selectOption('99');await loaded();
  if(!(await page.locator('#caption').textContent()).includes('736.00'))throw Error('Last sample missing');
  await page.locator('#mode').selectOption('nearby');await loaded();
  if(await page.locator('#item option').count()!==1)throw Error('Nearby pair inventory mismatch');
  await page.locator('summary').click();
  if(!(await page.locator('#metrics').textContent()).includes('"withheld_matches": 8'))throw Error('Wrong held-out evidence');
  await page.locator('#mode').selectOption('across-segments');
  if(!(await page.locator('#caption').textContent()).includes('No supported proposals'))throw Error('Empty distant category misleading');
  await page.locator('#mode').selectOption('samples');await loaded();
  if(!await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))throw Error('Mobile overflow');
  const video=await page.evaluate(async()=>{const v=document.createElement('video');v.muted=true;v.src='floor-drift/samples.mp4';document.body.append(v);await new Promise((resolve,reject)=>{v.onloadeddata=resolve;v.onerror=()=>reject(Error('Video failed'));});await v.play();const out={duration:v.duration,width:v.videoWidth,height:v.videoHeight};v.pause();v.remove();return out;});
  if(video.duration!==100||video.width!==540||video.height!==1000)throw Error('Video metadata mismatch');
  if(errors.length)throw Error(errors.join(';'));
  if(process.env.FLOOR_SCREENSHOTS)await page.screenshot({path:process.env.FLOOR_SCREENSHOTS+'-'+viewport.width+'.png',fullPage:true});
  results.push({viewport,status:'passed',samples:100,planes:87,nearby_pairs:1,distant_pairs:0,video,page_errors:errors});await page.close();
 }
 if(process.env.FLOOR_RECEIPT)await writeFile(process.env.FLOOR_RECEIPT,JSON.stringify({results},null,2)+'\n');
 console.log(JSON.stringify({results}));
}finally{await browser.close();}
