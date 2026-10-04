// Crop coordinates are native PLY coordinates, before the viewer's 180-degree Z
// conversion. A missing crop keeps existing projects visually unchanged.
export function validateCrop(value) {
  if (value === undefined || value === null) return null;
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      typeof value.enabled !== 'boolean' ||
      !['min','max'].every(k => Array.isArray(value[k]) && value[k].length === 3 && value[k].every(Number.isFinite)) ||
      !value.min.every((v,i) => v < value.max[i]) ||
      !Number.isFinite(value.feather) || value.feather < 0 || value.feather > .25) {
    throw Error('Crop needs finite, ordered XYZ bounds and an edge fade from 0 to 25%.');
  }
  return {enabled:value.enabled,min:[...value.min],max:[...value.max],feather:value.feather};
}

export function cropBounds(data, fraction=0) {
  const min=[],max=[];
  for (const name of ['x','y','z']) {
    const values=Array.from(data.getProp(name)).filter(Number.isFinite).sort((a,b)=>a-b);
    if (!values.length) throw Error('Crop requires finite splat positions.');
    let lo=values[Math.floor((values.length-1)*fraction)],hi=values[Math.ceil((values.length-1)*(1-fraction))];
    const pad=Math.max((hi-lo)*.01,1e-4);lo-=pad;hi+=pad;
    min.push(lo);max.push(hi);
  }
  return {enabled:false,min,max,feather:0};
}

// Unified rendering retains cross-section sorting. Each fragment is clipped at
// its camera-facing Gaussian billboard position, not merely its splat center.
// This clips the displayed extent; it is not a volumetric Gaussian intersection
// or a recovered physical surface. Pinned to the installed PlayCanvas 2.22 API.
export function installCropRenderer({pc,app,camera,entities,scenes,originals}) {
  const params=app.scene.gsplat,material=params.material;
  params.enableIds=true;
  const base=pc.ShaderChunks.get(app.graphicsDevice).get('gsplatVS');
  const anchor='gaussianUV = corner.uv;';
  if (!base?.includes(anchor)) throw Error('Installed splat renderer does not support crop integration.');
  const declarations='\nvarying highp vec3 cropWorldPosition;\nflat varying uint cropSectionId;\n';
  const vertex=declarations+'uniform mat4 cropClipToWorld;\n'+base.replace(anchor,`
    vec4 cropWorld = cropClipToWorld * gl_Position;
    cropWorldPosition = cropWorld.xyz / cropWorld.w;
    cropSectionId = loadPcId().r;
    ${anchor}`);
  let fragment=declarations;
  for (let i=0;i<scenes.length;i++) fragment+=`
    uniform vec3 cropSettings${i};
    uniform mat4 cropInverse${i};
    uniform vec3 cropMin${i};
    uniform vec3 cropMax${i};
    \n`;
  fragment+='void modifySplatColor(vec2 uv, inout vec4 color) {\n';
  for (let i=0;i<scenes.length;i++) fragment+=`
    if (cropSectionId == uint(cropSettings${i}.x) && cropSettings${i}.y > 0.5) {
      vec3 p=(cropInverse${i}*vec4(cropWorldPosition,1.0)).xyz;
      vec3 edge=min(p-cropMin${i},cropMax${i}-p);
      float margin=min(edge.x,min(edge.y,edge.z));
      if (margin < 0.0) discard;
      if (cropSettings${i}.z > 0.0) color.a *= smoothstep(0.0,cropSettings${i}.z,margin);
    }\n`;
  fragment+='}\n';
  material.shaderChunks.glsl.set('gsplatVS',vertex);
  material.shaderChunks.glsl.set('gsplatModifyPS',fragment);
  const clip=new Float32Array(16);material.setParameter('cropClipToWorld',clip);
  const slots=scenes.map((s,i)=>{
    const buffers={settings:new Float32Array(3),inverse:new Float32Array(16),min:new Float32Array(3),max:new Float32Array(3)};
    for(const [key,value] of Object.entries(buffers)) material.setParameter(`crop${key[0].toUpperCase()+key.slice(1)}${i}`,value);
    return buffers;
  });
  material.update();
  let showBox=true;
  const matrix=new pc.Mat4(),inverse=new pc.Mat4();
  function render() {
    matrix.copy(camera.camera.projectionMatrix).invert();
    matrix.mul2(camera.getWorldTransform(),matrix);clip.set(matrix.data);
    scenes.forEach((scene,i)=>{
      const content=entities.get(scene.id)?.children[0],b=slots[i],c=scene.crop;
      if(!content)return;
      b.settings[0]=content.gsplat.id;b.settings[1]=c?.enabled&&!originals.has(scene.id)?1:0;
      if(!c)return;
      inverse.copy(content.getWorldTransform()).invert();b.inverse.set(inverse.data);b.min.set(c.min);b.max.set(c.max);
      b.settings[2]=c.feather*Math.min(...c.max.map((v,j)=>v-c.min[j]));
      if(showBox&&b.settings[1]&&scene.visible){
        const corners=Array.from({length:8},(_,j)=>content.getWorldTransform().transformPoint(new pc.Vec3(...c.min.map((v,k)=>j&(1<<k)?c.max[k]:v))));
        const lines=[];for(let j=0;j<8;j++)for(let k=0;k<3;k++)if(!(j&(1<<k)))lines.push(corners[j],corners[j|(1<<k)]);
        app.drawLines(lines,new pc.Color(.45,1,.65),false);
      }
    });
  }
  app.on('prerender',render);
  return {setShowBox(value){showBox=value;app.renderNextFrame=true;},setScenes(value){scenes=value;}};
}

export function installCropControls({selectedScene,defaults,central,apply,changed}) {
  const $=id=>document.getElementById(id);
  const limits=new Map();
  const current=()=>structuredClone(selectedScene().crop??defaults.get(selectedScene().id));
  function set(value){try{selectedScene().crop=validateCrop(value);apply();refresh();changed();}catch(e){$('status').textContent=e.message;refresh();}}
  for(let axis=0;axis<3;axis++)for(const side of ['min','max']){
    const id=`crop-${side}-${axis}`,label=document.createElement('label');label.className='filter-control';label.htmlFor=id;label.textContent=`${'XYZ'[axis]} ${side==='min'?'start':'end'}`;
    const input=document.createElement('input');input.type='number';input.step='any';input.id=id;input.inputMode='decimal';label.append(input);
    const slider=document.createElement('input');slider.type='range';slider.id=id+'-slider';slider.className='crop-slider';slider.setAttribute('aria-label',label.textContent+' crop boundary');
    const update=value=>{const c=current();c.enabled=true;c[side][axis]=Number(value);set(c);};
    input.onchange=()=>update(input.value);slider.oninput=()=>update(slider.value);
    $('crop-fields').append(label,slider);
  }
  $('crop-enabled').onchange=()=>set({...current(),enabled:$('crop-enabled').checked});
  $('crop-fade').oninput=()=>set({...current(),feather:Number($('crop-fade').value)/100});
  $('crop-reset').onclick=()=>{limits.delete(selectedScene().id);set(null);};
  $('crop-central').onclick=()=>set({...structuredClone(central.get(selectedScene().id)),enabled:true});
  function refresh(){
    const s=selectedScene(),c=current(),base=defaults.get(s.id);if(!base)return;
    $('crop-enabled').checked=!!c.enabled;$('crop-fade').value=c.feather*100;$('crop-fade-value').textContent=`${Math.round(c.feather*100)}%`;
    const range=limits.get(s.id)??structuredClone(base);
    for(let k=0;k<3;k++){range.min[k]=Math.min(range.min[k],c.min[k]);range.max[k]=Math.max(range.max[k],c.max[k]);}
    limits.set(s.id,range);
    for(let k=0;k<3;k++)for(const side of ['min','max']){
      const input=$(`crop-${side}-${k}`),slider=$(input.id+'-slider');input.value=c[side][k];
      const gap=(range.max[k]-range.min[k])/10000;
      slider.min=side==='min'?range.min[k]:c.min[k]+gap;slider.max=side==='max'?range.max[k]:c.max[k]-gap;
      slider.step='any';slider.value=c[side][k];
    }
  }
  return {refresh};
}
