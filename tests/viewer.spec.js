import {test,expect} from '@playwright/test';
import {PNG} from 'pngjs';

async function visibleScene(page) {
  const {width,height}=page.viewportSize();
  const image=PNG.sync.read(await page.screenshot({clip:{x:width*.25,y:height*.25,width:Math.floor(width*.5),height:Math.floor(height*.4)}}));
  const values=[];
  for(let i=0;i<image.data.length;i+=4) values.push((image.data[i]+image.data[i+1]+image.data[i+2])/3);
  const mean=values.reduce((a,b)=>a+b,0)/values.length;
  const deviation=Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/values.length);
  expect(mean,'scene pixels must differ from the empty dark background').toBeGreaterThan(25);
  expect(deviation,'reconstructed surfaces must be visible').toBeGreaterThan(12);
}

test('desktop scene renders and orbit, free movement and reset work',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('./?webgl');
  await expect(page.getByText('A partial preview',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Enter the 3D scene'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-scene-loaded','true',{timeout:60000});
  const position=()=>page.evaluate(()=>window.sceneViewer.app.root.findComponent('camera').entity.getPosition().toArray());
  const authored=await page.evaluate(async()=> (await (await fetch("./scene.json")).json()).camera.position);
  await expect.poll(async()=>Math.hypot(...(await position()).map((v,i)=>v-authored[i])),{timeout:20000}).toBeLessThan(.05);
  const first=await position();
  await visibleScene(page);
  await page.screenshot({path:'test-results/desktop-scene.png'});
  await page.mouse.move(640,360);await page.mouse.down();await page.mouse.move(760,400,{steps:10});await page.mouse.up();
  await page.waitForTimeout(1200);
  expect(await position()).not.toEqual(first);
  await page.getByRole('button',{name:'Move freely',exact:true}).click();
  await expect(page.getByRole('button',{name:'Move freely',exact:true})).toHaveAttribute('aria-pressed','true');
  const forward=page.getByRole('button',{name:'Move forward',exact:true});
  await forward.hover();await page.mouse.down();await page.waitForTimeout(1000);await page.mouse.up();
  const moved=await position();expect(moved).not.toEqual(first);
  await page.keyboard.down('w');await page.waitForTimeout(700);await page.keyboard.up('w');
  expect(await position()).not.toEqual(moved);
  await page.keyboard.press('Escape');
  await expect.poll(()=>page.evaluate(()=>document.pointerLockElement===null)).toBe(true);
  await page.getByRole('button',{name:'Reset view',exact:true}).click();
  await expect.poll(async()=>Math.hypot(...(await position()).map((v,i)=>v-first[i])),{timeout:20000}).toBeLessThan(.15);
  await page.getByRole('button',{name:'Help',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Explore the scene'})).toBeVisible();
  await page.keyboard.press('Escape');await expect(page.locator('#help')).toBeHidden();
  expect(errors).toEqual([]);
});

test('mobile layout renders scene and exposes movement controls',async({browser})=>{
  const context=await browser.newContext({baseURL:process.env.SITE_URL || 'http://127.0.0.1:8088',viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const page=await context.newPage();
  await page.goto('./?webgl');
  await expect(page.getByRole('button',{name:'Enter the 3D scene'})).toBeInViewport();
  await page.getByRole('button',{name:'Enter the 3D scene'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-scene-loaded','true',{timeout:60000});
  await page.waitForTimeout(2200);await visibleScene(page);
  const position=()=>page.evaluate(()=>window.sceneViewer.app.root.findComponent('camera').entity.getPosition().toArray());
  const before=await position();
  const client=await context.newCDPSession(page);
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:180,y:380}]});
  await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:230,y:400}]});
  await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await page.waitForTimeout(1200);expect(await position()).not.toEqual(before);
  await page.getByRole('button',{name:'Move freely',exact:true}).click();
  await expect(page.getByRole('button',{name:'Move forward',exact:true})).toBeInViewport();
  const pad=await page.getByRole('button',{name:'Move forward',exact:true}).boundingBox();
  const movingFrom=await position();
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:pad.x+pad.width/2,y:pad.y+pad.height/2}]});
  await page.waitForTimeout(700);
  await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  expect(await position()).not.toEqual(movingFrom);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({path:'test-results/mobile-scene.png'});
  await context.close();
});

test('missing scene description shows a recoverable error',async({page})=>{
  await page.route('**/scene.json',route=>route.fulfill({status:404,body:'missing'}));
  await page.goto('./?webgl');
  await page.getByRole('button',{name:'Enter the 3D scene'}).click();
  await expect(page.getByRole('heading',{name:'The scene could not load'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Try again'})).toBeVisible();
});

for (const mobile of [false,true]) {
  test(`expanded scene renders and moves on ${mobile?'mobile':'desktop'}`,async({browser})=>{
    const context=await browser.newContext({baseURL:process.env.SITE_URL || 'http://127.0.0.1:8088',
      viewport:mobile?{width:390,height:844}:{width:1280,height:720},isMobile:mobile,hasTouch:mobile});
    const page=await context.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('./?scene=recovery-71s&webgl');
    await expect(page.getByText('Experimental expanded preview',{exact:true})).toBeVisible();
    await expect(page.locator('#alternate-scene')).toHaveAttribute('href','./');
    await page.getByRole('button',{name:'Enter the 3D scene'}).click();
    await expect(page.locator('body')).toHaveAttribute('data-scene-loaded','true',{timeout:60000});
    const position=()=>page.evaluate(()=>window.sceneViewer.app.root.findComponent('camera').entity.getPosition().toArray());
    const authored=await page.evaluate(async()=> (await (await fetch('./experiments/recovery-71s.json')).json()).camera.position);
    await expect.poll(async()=>Math.hypot(...(await position()).map((v,i)=>v-authored[i])),{timeout:20000}).toBeLessThan(.05);
    await visibleScene(page);
    const up=await page.evaluate(async()=>{
      const scene=await (await fetch('./experiments/recovery-71s.json')).json();
      const n=scene.orientation.floor_normal_before;
      const raw=[-n[0],-n[1],n[2]]; // Undo the viewer's standard COLMAP axis conversion.
      const m=window.sceneViewer.app.root.findComponent('gsplat').entity.getWorldTransform().data;
      return [0,1,2].map(i=>m[i]*raw[0]+m[i+4]*raw[1]+m[i+8]*raw[2]);
    });
    expect(Math.hypot(up[0],up[1]-1,up[2]),'fitted floor must be horizontal in the rendered world').toBeLessThan(1e-5);
    await page.screenshot({path:`test-results/expanded-${mobile?'mobile':'desktop'}.png`});
    if(mobile){
      const client=await context.newCDPSession(page);
      await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:180,y:380}]});
      await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:230,y:365}]});
      await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    }else{
      await page.mouse.move(640,360);await page.mouse.down();
      await page.mouse.move(720,335,{steps:10});await page.mouse.up();
    }
    await page.waitForTimeout(1200);
    expect(Math.hypot(...(await position()).map((v,i)=>v-authored[i]))).toBeGreaterThan(.01);
    await visibleScene(page);
    await page.screenshot({path:`test-results/expanded-${mobile?'mobile':'desktop'}-orbit.png`});
    await page.getByRole('button',{name:'Move freely',exact:true}).click();
    const before=await position();
    const forward=page.getByRole('button',{name:'Move forward',exact:true});
    await expect(forward).toBeInViewport();
    if(mobile){
      const box=await forward.boundingBox();const client=await context.newCDPSession(page);
      await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width/2,y:box.y+box.height/2}]});
      await page.waitForTimeout(700);
      await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    }else{
      await page.keyboard.down('w');await page.waitForTimeout(700);await page.keyboard.up('w');
    }
    expect(await position()).not.toEqual(before);
    await page.screenshot({path:`test-results/expanded-${mobile?'mobile':'desktop'}-moved.png`});
    if(!mobile){
      await page.keyboard.press('Escape');
      await expect.poll(()=>page.evaluate(()=>document.pointerLockElement===null)).toBe(true);
    }
    await page.getByRole('button',{name:'Reset view',exact:true}).click();
    await expect.poll(async()=>Math.hypot(...(await position()).map((v,i)=>v-authored[i])),{timeout:20000}).toBeLessThan(.05);
    expect(errors).toEqual([]);
    await context.close();
  });
}
