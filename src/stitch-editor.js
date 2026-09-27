import * as pc from 'playcanvas';
import {validateFilters,measureSplats,filterSummary,filterModifier} from './stitch-filters.js';
const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
let project, initial, manifest, revision, selected = 0, dirty = false, soloMode = false;
const entities = new Map(), measurements = new Map(), filterKeys = new Map(), filterCounts = new Map(), originals = new Set();
const canvas = $('canvas'), viewport = $('viewport');
const app = new pc.Application(canvas, {graphicsDeviceOptions:{deviceTypes:['webgl2'],antialias:false,alpha:false}});
app.setCanvasFillMode(pc.FILLMODE_NONE, viewport.clientWidth, viewport.clientHeight);
app.setCanvasResolution(pc.RESOLUTION_AUTO);
app.autoRender = false;
app.systems.gsplat.on('frame:request', () => {app.renderNextFrame=true;});
app.graphicsDevice.maxPixelRatio = Math.min(devicePixelRatio, 1.5);
const camera = new pc.Entity('camera');
camera.addComponent('camera', {clearColor:new pc.Color(.055,.075,.063),nearClip:.01,farClip:10000,fov:60});
app.root.addChild(camera);
let yaw = 0, pitch = 15, distance = 5, target = new pc.Vec3();
function status(text) { $('status').textContent = text; }
function selectedScene() {return project.scenes[selected];}
function markDirty() {dirty=true;status('Unsaved project changes.'); expose();}
function expose() {window.stitchEditor = {ready:entities.size === project.scenes.length, project:clone(project), selected:selectedScene().id, camera:{yaw,pitch,distance,target:[target.x,target.y,target.z]}, filters:Object.fromEntries(project.scenes.map(s=>[s.id,{...(filterCounts.get(s.id)??{hidden:0,total:0}),original:originals.has(s.id)}])), dirty};}
function cameraUpdate() {
  const y=yaw*Math.PI/180,p=pitch*Math.PI/180;
  camera.setPosition(target.x+distance*Math.cos(p)*Math.sin(y),target.y+distance*Math.sin(p),target.z+distance*Math.cos(p)*Math.cos(y));
  camera.lookAt(target); app.renderNextFrame=true; if(project) expose();
}
function apply(scene) {
  const entity=entities.get(scene.id); if(!entity) return;
  const t=scene.transform; entity.setLocalPosition(...t.position); entity.setLocalEulerAngles(...t.rotation); entity.setLocalScale(t.scale,t.scale,t.scale); entity.enabled=scene.visible; applyFilter(scene); app.renderNextFrame=true;
}
function applyFilter(scene) {
  const component=entities.get(scene.id)?.children[0].gsplat, data=measurements.get(scene.id);if(!component||!data)return;
  const f=scene.filters??validateFilters();const bypass=originals.has(scene.id);
  const key=JSON.stringify([f,bypass]);if(filterKeys.get(scene.id)===key)return;filterKeys.set(scene.id,key);filterCounts.set(scene.id,filterSummary(data,f,bypass));
  if(bypass||!(f.minOpacity||f.maxSize||f.maxRatio))component.setWorkBufferModifier(null);
  else {
    component.setParameter('inspectionMinOpacity',f.minOpacity);component.setParameter('inspectionMaxSize',f.maxSize);component.setParameter('inspectionMaxRatio',f.maxRatio);component.setParameter('inspectionMedian',data.median);
    component.setWorkBufferModifier(filterModifier);
  }
  app.renderNextFrame=true;
}
function inspectionControls() {
  const s=selectedScene(),f=s.filters;
  $('filter-heading').textContent=`Filters: ${manifest.scenes.find(m=>m.id===s.id).label??s.id}`;
  $('filter-opacity').value=f.minOpacity;$('filter-size').value=f.maxSize;$('filter-ratio').value=f.maxRatio;$('filter-original').checked=originals.has(s.id);
  const summary=filterCounts.get(s.id);
  $('filter-summary').textContent=`${originals.has(s.id)?'Original preview. ':''}Approximately ${summary.hidden.toLocaleString()} / ${summary.total.toLocaleString()} splats hidden (${(100*summary.hidden/summary.total).toFixed(1)}%).`;
  for(const row of $('section-list').children){const item=project.scenes.find(s=>s.id===row.dataset.scene);row.querySelector('input').checked=item.visible;}
  const filtered=project.scenes.filter(s=>s.visible&&!originals.has(s.id)&&Object.values(s.filters).some(Boolean));
  $('filter-badge').textContent=filtered.length?`Inspection filters active: ${filtered.map(s=>s.id).join(', ')} · originals preserved`:'';
}
function setFilters(filters) {
  try{selectedScene().filters=validateFilters(filters);originals.delete(selectedScene().id);applyFilter(selectedScene());controls();markDirty();}catch(e){status(e.message);inspectionControls();}
}
for(const id of ['filter-opacity','filter-size','filter-ratio'])$(id).onchange=()=>setFilters({minOpacity:Number($('filter-opacity').value),maxSize:Number($('filter-size').value),maxRatio:Number($('filter-ratio').value)});
$('filter-rays').onclick=()=>setFilters({...selectedScene().filters,maxRatio:10});
$('filter-reset').onclick=()=>setFilters(validateFilters());
$('filter-original').onchange=()=>{if($('filter-original').checked)originals.add(selectedScene().id);else originals.delete(selectedScene().id);applyFilter(selectedScene());controls();};
function sectionRows() {
  for(const s of project.scenes){
    const row=document.createElement('div');row.className='section-entry';row.dataset.scene=s.id;
    const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.visible=s.id;input.setAttribute('aria-label',`Show ${s.id}`);
    input.onchange=()=>{soloMode=false;const current=project.scenes.find(item=>item.id===s.id);current.visible=input.checked;apply(current);controls();markDirty();};
    label.append(input,document.createTextNode(manifest.scenes.find(m=>m.id===s.id).label??s.id));
    const only=document.createElement('button');only.textContent='Only';only.dataset.only=s.id;only.setAttribute('aria-label',`Show only ${s.id}`);only.onclick=()=>{selected=project.scenes.findIndex(item=>item.id===s.id);$('solo').click();};row.append(label,only);$('section-list').append(row);
  }
}
function controls() {
  const s=selectedScene(); const definition=manifest.scenes.find(m=>m.id===s.id); $('quality').textContent=definition.status ?? 'Quality not reviewed. Placement is provisional.'; $('scene').value=s.id; $('visible').checked=s.visible; $('locked').checked=s.locked; $('transform').disabled=s.locked; $('reset-transform').disabled=s.locked;
  for(const group of ['position','rotation']) for(let axis=0;axis<3;axis++) $(`${group}-${axis}`).value=s.transform[group][axis];
  $('scale').value=s.transform.scale;
  inspectionControls(); $('previous').disabled=selected===0; $('next').disabled=selected===project.scenes.length-1; expose();
}
function select(index) {selected=index;if(soloMode){for(const s of project.scenes){s.visible=s.id===selectedScene().id;apply(s);}markDirty();}controls();}
function change(group,axis,value) {
  if(selectedScene().locked || !Number.isFinite(value) || (group==='scale' && value<=0)) return controls();
  if(group==='scale') selectedScene().transform.scale=value; else selectedScene().transform[group][axis]=value;
  apply(selectedScene());controls();markDirty();
}
for(const group of ['position','rotation','scale']) {
  const panel=document.createElement('div');panel.className='transform-group'+(group==='position'?' active':'');panel.dataset.group=group;$('fields').append(panel);
  const heading=document.createElement('strong');heading.textContent=group==='position'?'Move XYZ':group==='rotation'?'Rotate XYZ (degrees)':'Uniform scale';panel.append(heading);
  for(let axis=0;axis<(group==='scale'?1:3);axis++) {
    const row=document.createElement('div');row.className='axis';
    const label=document.createElement('label');label.textContent=group==='scale'?'×':'XYZ'[axis];
    const input=document.createElement('input');input.type='number';input.inputMode='decimal';input.step=group==='rotation'?'1':'.01'; input.id=group==='scale'?'scale':`${group}-${axis}`; label.htmlFor=input.id;
    if(group==='scale') input.min='.000001'; input.addEventListener('change',()=>change(group,axis,Number(input.value)));
    row.append(label,input);
    for(const direction of [-1,1]) {const b=document.createElement('button');b.textContent=direction<0?'−':'+';b.type='button';b.setAttribute('aria-label',`${direction<0?'Decrease':'Increase'} ${group} ${group==='scale'?'':'XYZ'[axis]}`);b.addEventListener('click',()=>{
      const t=selectedScene().transform;
      const step=Number($(group==='rotation'?'rotate-step':'move-step').value);
      if(!Number.isFinite(step)||step<=0) return;
      change(group,axis,group==='scale'?t.scale*Math.pow(1.01,direction):t[group][axis]+direction*step);
    });row.append(b);} panel.append(row);
  }
  if(group!=='scale') {
    const label=document.createElement('label');label.className='step';label.textContent=group==='position'?'Move step':'Rotation step °';
    const input=document.createElement('input');input.type='number';input.inputMode='decimal';input.id=group==='position'?'move-step':'rotate-step';input.value=group==='position'?'.05':'1';input.min=group==='position'?'.0001':'.01';input.step=group==='position'?'.01':'1';label.append(input);panel.append(label);
  }
}
for(const button of document.querySelectorAll('.panel-tabs button')) button.onclick=()=>{
  document.querySelector('aside').dataset.panel=button.dataset.panel;
  for(const tab of document.querySelectorAll('.panel-tabs button'))tab.setAttribute('aria-pressed',String(tab===button));
  for(const panel of document.querySelectorAll('.transform-group'))panel.classList.toggle('active',panel.dataset.group===button.dataset.panel);
  $('panel-content').scrollTop=0;
};
$('panel-toggle').onclick=()=>{const collapsed=document.querySelector('aside').classList.toggle('collapsed');$('panel-toggle').textContent=collapsed?'Controls':'Hide';$('panel-toggle').setAttribute('aria-expanded',String(!collapsed));};
function focusSelected() {
  const entity=entities.get(selectedScene().id), child=entity.children[0], local=child.gsplat.resource.aabb;
  const bounds=new pc.BoundingBox();bounds.setFromTransformedAabb(local,child.getWorldTransform());target.copy(bounds.center);distance=Math.max(.1,bounds.halfExtents.length()*1.3);cameraUpdate();
}
$('scene').addEventListener('change',()=>select(project.scenes.findIndex(s=>s.id===$('scene').value)));
$('previous').onclick=()=>select(Math.max(0,selected-1));$('next').onclick=()=>select(Math.min(project.scenes.length-1,selected+1));
$('visible').onchange=()=>{soloMode=false;selectedScene().visible=$('visible').checked;apply(selectedScene());controls();markDirty();};
$('locked').onchange=()=>{selectedScene().locked=$('locked').checked;controls();markDirty();};
$('solo').onclick=()=>{soloMode=true;for(const s of project.scenes){s.visible=s.id===selectedScene().id;apply(s);}controls();markDirty();};
$('show-all').onclick=()=>{soloMode=false;for(const s of project.scenes){s.visible=true;apply(s);}controls();markDirty();};
$('inspect-show-all').onclick=()=>$('show-all').click();
$('reset-transform').onclick=()=>{if(selectedScene().locked)return;selectedScene().transform=clone(initial.scenes.find(s=>s.id===selectedScene().id).transform);apply(selectedScene());controls();markDirty();};
$('focus').onclick=focusSelected;$('top').onclick=()=>{pitch=89;cameraUpdate();};
$('save').onclick=async()=>{const submitted=JSON.stringify(project);$('save').disabled=true;try {const response=await fetch('/api/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,project:JSON.parse(submitted)})});const result=await response.json();if(!response.ok)throw Error(result.error);revision=result.revision;dirty=JSON.stringify(project)!==submitted;status(dirty?'Earlier placement saved; newer changes are still unsaved.':'Saved on this server.');expose();}catch(e){status(`Save failed: ${e.message}`);}finally{$('save').disabled=false;}};
$('reload').onclick=async()=>{if(dirty&&!confirm('Discard unsaved placement changes?'))return;try{const response=await fetch('/api/project');if(!response.ok)throw Error('Could not reload project.');const data=await response.json();project=data.project;for(const s of project.scenes)s.filters=validateFilters(s.filters);originals.clear();revision=data.revision;for(const s of project.scenes)apply(s);dirty=false;controls();status('Reloaded saved placements.');}catch(e){status(e.message);}};
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(project,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='stitch-project.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
$('import').onclick=()=>$('file').click();
$('file').onchange=async()=>{try {const data=JSON.parse(await $('file').files[0].text());if(data.version!==1||!Array.isArray(data.scenes)||data.scenes.length!==project.scenes.length)throw Error('Scene list differs from this project.');const seen=new Set();for(const s of data.scenes){const expected=project.scenes.find(p=>p.id===s.id);if(!expected||s.asset!==expected.asset||seen.has(s.id)||!s.transform||!['position','rotation'].every(k=>Array.isArray(s.transform[k])&&s.transform[k].length===3&&s.transform[k].every(Number.isFinite))||!Number.isFinite(s.transform.scale)||s.transform.scale<=0||typeof s.visible!=='boolean'||typeof s.locked!=='boolean')throw Error('Invalid scene or transform.');s.filters=validateFilters(s.filters);seen.add(s.id);}project=data;originals.clear();for(const s of project.scenes)apply(s);controls();markDirty();}catch(e){status(`Import failed: ${e.message}`);}finally{$('file').value='';}};
// Rebase each event on the current active pointers, so lifting a finger never
// reuses a stale drag origin or accidentally moves the selected Gaussian scene.
const pointers=new Map();
function panCamera(dx,dy) {target.add(camera.right.clone().mulScalar(-dx*distance*.002));target.add(camera.up.clone().mulScalar(dy*distance*.002));}
function zoomCamera(factor) {distance=Math.max(.001,Math.min(100000,distance*factor));}
function pairGeometry() {const [a,b]=[...pointers.values()];return {x:(a.x+b.x)/2,y:(a.y+b.y)/2,span:Math.hypot(a.x-b.x,a.y-b.y)};}
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('pointerdown',e=>{pointers.set(e.pointerId,{x:e.clientX,y:e.clientY,pan:e.button===2||e.shiftKey});canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointermove',e=>{
  const point=pointers.get(e.pointerId);if(!point)return;
  const before=pointers.size===2?pairGeometry():null;
  const dx=e.clientX-point.x,dy=e.clientY-point.y;point.x=e.clientX;point.y=e.clientY;
  if(before){const after=pairGeometry();panCamera(after.x-before.x,after.y-before.y);if(before.span>0&&after.span>0)zoomCamera(before.span/after.span);}
  else if(pointers.size===1){if(point.pan)panCamera(dx,dy);else{yaw-=dx*.3;pitch=Math.max(-89,Math.min(89,pitch+dy*.3));}}
  cameraUpdate();
});
for(const name of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(name,e=>pointers.delete(e.pointerId));
window.addEventListener('blur',()=>pointers.clear());
canvas.addEventListener('wheel',e=>{e.preventDefault();zoomCamera(Math.exp(e.deltaY*.001));cameraUpdate();},{passive:false});
new ResizeObserver(()=>{app.resizeCanvas(viewport.clientWidth,viewport.clientHeight);app.renderNextFrame=true;}).observe(viewport);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
window.addEventListener('pagehide',()=>app.destroy());
try {
  const response=await fetch('/api/project');if(!response.ok)throw Error('Project could not be opened.');
  ({project,initial,manifest,revision}=await response.json());
  for(const s of project.scenes)s.filters=validateFilters(s.filters);
  app.start();
  for(const s of project.scenes) {
    status(`Loading ${manifest.scenes.find(m=>m.id===s.id).label ?? s.id}…`);
    const asset=await new Promise((resolve,reject)=>app.assets.loadFromUrl(`/assets/${s.id}.ply`,'gsplat',(error,asset)=>error?reject(Error(error)):resolve(asset)));
    const entity=new pc.Entity(s.id), content=new pc.Entity(`${s.id}-gaussians`);
    // Match the repository's SuperSplat viewer PLY coordinate convention.
    content.setLocalEulerAngles(0,0,180);content.addComponent('gsplat',{asset,unified:true});entity.addChild(content);app.root.addChild(entity);entities.set(s.id,entity);measurements.set(s.id,measureSplats(asset.resource.gsplatData));apply(s);
    const option=document.createElement('option');option.value=s.id;option.textContent=manifest.scenes.find(m=>m.id===s.id).label ?? s.id;$('scene').append(option);
  }
  sectionRows();
  for(const e of document.querySelectorAll('aside button, aside input, aside select'))e.disabled=false;
  selected=Math.min(1,project.scenes.length-1);controls();
  if(manifest.camera){target.set(...manifest.camera.target);const d=new pc.Vec3(...manifest.camera.position).sub(target);distance=d.length();pitch=Math.asin(d.y/distance)*180/Math.PI;yaw=Math.atan2(d.x,d.z)*180/Math.PI;cameraUpdate();}else focusSelected();
  status(`${project.scenes.length} Gaussian scenes loaded. Select a section to place it.`);
}catch(e){status(`Could not open editor: ${e.message}`);console.error(e);}
