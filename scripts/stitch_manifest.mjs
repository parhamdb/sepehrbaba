// Convert seed-camera gauges into a PlayCanvas editor manifest, without asset edits.
import {readFile,writeFile} from 'node:fs/promises';
import * as pc from 'playcanvas';
const [source,output]=process.argv.slice(2);
if(!source||!output)throw Error('Usage: node scripts/stitch_manifest.mjs SEED_VIEWS.json MANIFEST.json');
const rows=JSON.parse(await readFile(source,'utf8'));
const scenes=rows.map((row,index)=>{
 const R=row.rotation_matrix;
 const m=new pc.Mat4().set([R[0][0],R[1][0],R[2][0],0,R[0][1],R[1][1],R[2][1],0,R[0][2],R[1][2],R[2][2],0,0,0,0,1]);
 const rotation=m.getEulerAngles().toArray();
 const roundtrip=new pc.Mat4().setFromEulerAngles(...rotation);
 if(Math.max(...Array.from(m.data,(v,i)=>Math.abs(v-roundtrip.data[i])))>1e-5)throw Error('Euler conversion differs');
 return {id:row.id,label:`${row.id} section`,asset:`${row.id}-clean.ply`,locked:index===0,
  status:'Selective masks reviewed; provisional reconstruction. Seed-camera starting view, not aligned to other sections.',
  transform:{position:row.translation,rotation,scale:row.scale}};
});
await writeFile(output,JSON.stringify({version:1,camera:{position:[0,0,0],target:[0,0,1]},scenes},null,2)+'\n');
