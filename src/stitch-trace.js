// Source tracing is optional; no training or mask approval happens in the browser.
export function installTrace({pc,app,camera,canvas,entities,selectedScene,originals,applyFilter,status}){
  const $=id=>document.getElementById(id);let armed=false,last=null,overlay=null,hidden=null;
  function restore(){if(overlay){overlay.destroy();overlay=null;}if(hidden){hidden.enabled=true;hidden=null;}app.renderNextFrame=true;}
  async function submit(request){
    $('trace-start').disabled=true;$('trace-again').disabled=true;status('Tracing source frames…');
    try{
      const response=await fetch('/api/trace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});const result=await response.json();if(!response.ok)throw Error(result.error);
      last={request,result};$('trace-candidates').replaceChildren();$('trace-results').replaceChildren();
      for(const row of result.candidates){const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=row.id;box.checked=result.selected_ids.includes(row.id);label.append(box,document.createTextNode(` #${row.id} · contribution ${(100*row.weight).toFixed(1)}% · axis ratio ${row.axis_ratio.toFixed(1)}`));$('trace-candidates').append(label);}
      for(const row of result.frames){const link=document.createElement('a');link.href=`/trace-result/${result.trace_id}/${row.name}.jpg`;link.target='_blank';link.rel='noopener';const image=document.createElement('img');image.src=link.href;image.alt=`${row.timestamp.toFixed(3)} seconds: source, selected footprint, current exclusions`;image.style.cssText='width:100%;height:auto';link.append(document.createTextNode(`${row.timestamp.toFixed(3)}s · ${row.name} — open full image`),image);$('trace-results').append(link);}
      const receipt=document.createElement('a');receipt.href=`/trace-result/${result.trace_id}/trace.json`;receipt.textContent='Download trace receipt';receipt.download='trace.json';$('trace-results').append(receipt);
      $('trace-only').disabled=false;status(`${result.selected_ids.length} splats traced to ${result.frames.length} review frames. Footprints suggest correspondence; they do not prove an originating object.`);
      window.lastSplatTrace=result;
    }catch(e){status(`Trace failed: ${e.message}`);}finally{$('trace-start').disabled=false;$('trace-again').disabled=!last;}
  }
  $('trace-start').onclick=async()=>{
    restore();const s=selectedScene();const available=await(await fetch('/api/trace')).json();if(!available.scenes.includes(s.id)){status('Source tracing is not configured for this version. Select a tracked version.');return;}
    $('solo').click();originals.add(s.id);applyFilter(s);armed=true;status('Tap a ray in the scene. The selected section is shown without display filters.');
  };
  canvas.addEventListener('pointerdown',e=>{
    if(!armed)return;armed=false;e.preventDefault();e.stopImmediatePropagation();restore();const s=selectedScene(),inverse=entities.get(s.id).getWorldTransform().clone().invert();
    const pos=inverse.transformPoint(camera.getPosition()),target=inverse.transformPoint(camera.getPosition().clone().add(camera.forward)),up=inverse.transformVector(camera.up).normalize();const box=canvas.getBoundingClientRect();
    const toArray=v=>[v.x,v.y,v.z];const width=Math.min(960,Math.round(box.width)),height=Math.round(width*box.height/box.width);
    submit({scene:s.id,view:{position:toArray(pos),target:toArray(target),up:toArray(up),fov:camera.camera.fov,width,height},pixel:[(e.clientX-box.x)/box.width,(e.clientY-box.y)/box.height]});
  },true);
  $('trace-again').onclick=()=>{if(last)submit({...last.request,ids:[...$('trace-candidates').querySelectorAll('input:checked')].map(x=>Number(x.value))});};
  $('trace-only').onclick=async()=>{
    if(!last)return;restore();const parent=entities.get(last.request.scene);if(!parent)return;
    try{const asset=await new Promise((resolve,reject)=>app.assets.loadFromUrl(`/trace-result/${last.result.trace_id}/selection.ply`,'gsplat',(e,a)=>e?reject(e):resolve(a)));overlay=new pc.Entity('trace-selection');overlay.setLocalEulerAngles(0,0,180);overlay.addComponent('gsplat',{asset,unified:true});hidden=parent.children[0];hidden.enabled=false;parent.addChild(overlay);app.renderNextFrame=true;status('Showing only the traced splats. Restore scene to see their surroundings.');}catch(e){status(String(e));}
  };
  $('trace-restore').onclick=()=>{armed=false;restore();};
  $('scene').addEventListener('change',restore);
  document.querySelectorAll('[data-only],#previous,#next,#show-all,#inspect-show-all').forEach(e=>e.addEventListener('click',restore));
  fetch('/api/trace').then(r=>r.ok?r.json():{scenes:[]}).then(x=>{$('trace-controls').hidden=!x.scenes.length;}).catch(()=>{$('trace-controls').hidden=true;});
}
