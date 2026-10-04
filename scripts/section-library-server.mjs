#!/usr/bin/env node
// Serve a time-ordered reconstruction library and isolated one/two-section editors.
import http from 'node:http';
import path from 'node:path';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {Mat4, Quat} from 'playcanvas';
import {createStitchServer} from './stitch-editor-server.mjs';

export async function createSectionLibrary({library, state, web = 'dist/stitch-editor', page = 'public/section-library.html'}) {
  const catalog = JSON.parse(await readFile(path.join(library,'catalog.json'),'utf8'));
  const sections = new Map(catalog.sections.map(s=>[s.id,s]));
  if (sections.size !== catalog.sections.length || !sections.size) throw Error('Invalid section inventory');
  for (const s of sections.values()) {
    if (!/^[a-zA-Z0-9_-]+$/.test(s.id) || s.asset !== `${s.id}.ply` || s.preview !== `${s.id}.jpg`) throw Error('Invalid section asset name');
  }
  const pairs = new Map();
  const json = (res,code,body) => {res.writeHead(code,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(body));};
  async function pair(ids) {
    const key = ids.join('--');
    if (!pairs.has(key)) pairs.set(key,(async()=>{
      const dir = path.join(state,key); await mkdir(dir,{recursive:true});
      const scenes = ids.map((id,i)=>{
        const s=sections.get(id),p=s.placement,m=new Mat4();
        for(let c=0;c<3;c++)for(let r=0;r<3;r++)m.data[c*4+r]=p.rotation_matrix[r][c];
        const e=new Quat().setFromMat4(m).getEulerAngles();
        return {id,asset:s.asset,label:`${time(s.start)}–${time(s.end)}`,locked:i===0,
          status:`Independent section; seed-camera display placement is NOT an alignment. ${s.mask_method} ${s.quality}`,
          transform:{position:p.position,rotation:[e.x,e.y,e.z],scale:p.scale}};
      });
      const manifest=path.join(dir,'manifest.json');
      await writeFile(manifest,JSON.stringify({version:1,camera:{position:[0,0,0],target:[0,0,1]},scenes},null,2)+'\n');
      return (await createStitchServer({manifestPath:manifest,assetsRoot:path.join(library,'assets'),stateRoot:dir,webRoot:web})).server;
    })());
    return pairs.get(key);
  }
  const server=http.createServer(async(req,res)=>{
    try {
      const url=new URL(req.url,'http://localhost');
      const match=url.pathname.match(/^\/pair\/([a-zA-Z0-9_-]+)(?:\/([a-zA-Z0-9_-]+))?(\/.*)$/);
      if(match){
        const ids=[match[1],match[2]].filter(Boolean);
        if(new Set(ids).size!==ids.length||ids.some(id=>!sections.has(id)))return json(res,404,{error:'Unknown or duplicate section'});
        const child=await pair(ids);req.url=match[3]+url.search;child.emit('request',req,res);return;
      }
      if(!['GET','HEAD'].includes(req.method))return json(res,405,{error:'Read only'});
      if(url.pathname==='/api/catalog')return json(res,200,catalog);
      if(url.pathname==='/api/trace')return json(res,200,{scenes:[]});
      const preview=url.pathname.match(/^\/previews\/([a-zA-Z0-9_-]+)\.jpg$/);
      let filename,type;
      if(url.pathname==='/'){filename=page;type='text/html';}
      else if(url.pathname==='/editor.js'){filename=path.join(web,'editor.js');type='text/javascript';}
      else if(preview&&sections.has(preview[1])){filename=path.join(library,'previews',preview[1]+'.jpg');type='image/jpeg';}
      else return json(res,404,{error:'Not found'});
      res.writeHead(200,{'Content-Type':type,'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});
      if(req.method==='HEAD')return res.end();
      const stream=createReadStream(filename);stream.on('error',()=>res.destroy());stream.pipe(res);
    } catch(e){if(!res.headersSent)json(res,400,{error:e.message});else res.destroy();}
  });
  return {server,catalog};
}
function time(s){return `${Math.floor(s/60).toString().padStart(2,'0')}:${(s%60).toFixed(1).padStart(4,'0')}`;}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const args=process.argv.slice(2),options={};
  for(let i=0;i<args.length;i+=2)options[args[i].replace(/^--/,'')]=args[i+1];
  if(!options.library||!options.state)throw Error('Use --library DIR --state DIR [--host HOST --port PORT]');
  const {server}=await createSectionLibrary(options);
  server.listen(Number(options.port??8095),options.host??'127.0.0.1',()=>console.log(`Section library listening on port ${server.address().port}`));
}
