// The bounded desktop/mobile acceptance path for connection evidence only.
import {chromium} from '@playwright/test';
import {readFile,writeFile} from 'node:fs/promises';
const base=process.env.CONNECTION_BASE_URL;
if(!base)throw Error('Set CONNECTION_BASE_URL');
const data=JSON.parse(await readFile('public/camera-connections/report.json','utf8'));
const floor=JSON.parse(await readFile('public/camera-connections/floor-summary.json','utf8'));
const browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});
const receipts=[];
try{
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  const page=await browser.newPage({viewport});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);
  await page.waitForFunction(()=>document.querySelectorAll('#connections tr').length===19);
  const rows=await page.locator('#connections tr').allTextContents();
  for(const [i,c] of data.cases.entries()){
   if(!rows[i].includes(c.id)||!rows[i].includes('Unresolved'))throw Error('Missing or misleading verdict');
   const href=await page.locator('#connections tr').nth(i).locator('a').getAttribute('href');
   if(href!==`camera-comparison.html#${c.id}`)throw Error('Wrong comparison link');
  }
  if(!await page.locator('#counts').innerText().then(t=>t.startsWith('0 verified joins')))throw Error('False join count');
  await page.waitForFunction(expected=>document.getElementById('floor-status').textContent===expected,floor.summary);
  await page.locator('summary').click();
  if(!await page.locator('details').getAttribute('open').then(x=>x!==null))throw Error('Explanation cannot open');
  if(!await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1))throw Error('Page overflows');
  if(errors.length)throw Error(errors.join('; '));
  if(process.env.CONNECTION_SCREENSHOTS)await page.screenshot({path:process.env.CONNECTION_SCREENSHOTS+'-'+viewport.width+'.png',fullPage:true});
  receipts.push({viewport,status:'passed',rows:19,comparison_links:19,zero_joins_label:true,floor_result:true,explanation:true,page_errors:errors});
  await page.close();
 }
 const report={receipts};console.log(JSON.stringify(report));
 if(process.env.CONNECTION_RECEIPT)await writeFile(process.env.CONNECTION_RECEIPT,JSON.stringify(report,null,2)+'\n');
}finally{await browser.close()}
