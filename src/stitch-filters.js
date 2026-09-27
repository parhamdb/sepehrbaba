// Shared by the viewer and server. Missing settings preserve legacy projects.
export function validateFilters(value) {
  if(value===undefined)return {minOpacity:0,maxSize:0,maxRatio:0};
  if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Invalid section filters.');
  const {minOpacity,maxSize,maxRatio}=value;
  if(!Number.isFinite(minOpacity)||minOpacity<0||minOpacity>1||
     !Number.isFinite(maxSize)||maxSize<0||maxSize>1000||
     !Number.isFinite(maxRatio)||maxRatio<0||maxRatio>1000||(maxRatio>0&&maxRatio<1))throw Error('Invalid section filter thresholds.');
  return {minOpacity,maxSize,maxRatio};
}
export function filterSummary(data, filters, original=false) {
  const {lengths,ratios,opacities,median}=data;let hidden=0;
  if(!original)for(let i=0;i<lengths.length;i++){
    if(opacities[i]<filters.minOpacity||
       (filters.maxSize>0&&lengths[i]>median*filters.maxSize)||
       (filters.maxRatio>0&&lengths[i]>median&&ratios[i]>filters.maxRatio))hidden++;
  }
  return {hidden,total:lengths.length};
}
export function measureSplats(data) {
  const scales=[0,1,2].map(i=>data.getProp(`scale_${i}`)),opacity=data.getProp('opacity');
  if(scales.some(s=>!s)||!opacity)throw Error('Inspection filters require an uncompressed Gaussian PLY.');
  const lengths=new Float64Array(opacity.length),ratios=new Float64Array(opacity.length),opacities=new Float64Array(opacity.length);
  for(let i=0;i<opacity.length;i++){
    const axes=scales.map(s=>data.activated?s[i]:Math.exp(s[i])).sort((a,b)=>a-b);
    lengths[i]=axes[2];ratios[i]=axes[2]/Math.max(axes[1],1e-30);opacities[i]=data.activated?opacity[i]:1/(1+Math.exp(-opacity[i]));
  }
  const sorted=lengths.slice().sort();const median=sorted[Math.floor(sorted.length/2)];
  return {lengths,ratios,opacities,median};
}
// Local source scales make the thresholds independent of manual alignment scale.
// Compare largest / middle axis: largest / smallest also rejects flat surfaces.
export const filterModifier={glsl:`
uniform float inspectionMinOpacity;
uniform float inspectionMaxSize;
uniform float inspectionMaxRatio;
uniform float inspectionMedian;
void modifySplatCenter(inout vec3 center) {}
void modifySplatRotationScale(vec3 originalCenter, vec3 modifiedCenter, inout vec4 rotation, inout vec3 scale) {}
void modifySplatColor(vec3 center, inout vec4 color) {
    vec3 axes=getScale();
    float longest=max(axes.x,max(axes.y,axes.z));
    float middle=max(min(axes.x,axes.y),min(max(axes.x,axes.y),axes.z));
    bool faint=color.a<inspectionMinOpacity;
    bool large=inspectionMaxSize>0.0 && longest>inspectionMedian*inspectionMaxSize;
    bool needle=inspectionMaxRatio>0.0 && longest>inspectionMedian && longest>middle*inspectionMaxRatio;
    if(faint || large || needle)color.a=0.0;
}`};
