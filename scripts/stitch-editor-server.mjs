import http from 'node:http';
import {validateFilters} from '../src/stitch-filters.js';
import { readFile, writeFile, rename, mkdir, stat, realpath } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import {traceApi} from './stitch-trace-api.mjs';

export function validateProject(input, manifest) {
  if (input?.version !== 1 || !Array.isArray(input.scenes) || input.scenes.length !== manifest.scenes.length) throw Error('Project must contain each manifest scene exactly once.');
  const ids = new Set();
  const scenes = input.scenes.map(s => {
    const original = manifest.scenes.find(m => m.id === s.id);
    if (!original || ids.has(s.id)) throw Error('Unknown or duplicate scene.');
    ids.add(s.id);
    const t = s.transform;
    if (!t || !['position', 'rotation'].every(k => Array.isArray(t[k]) && t[k].length === 3 && t[k].every(Number.isFinite)) || !Number.isFinite(t.scale) || t.scale <= 0) throw Error('Transforms require finite XYZ values and positive uniform scale.');
    if (typeof s.visible !== 'boolean' || typeof s.locked !== 'boolean') throw Error('Visibility and lock must be booleans.');
    return { id: s.id, asset: original.asset, transform: { position: [...t.position], rotation: [...t.rotation], scale: t.scale }, visible: s.visible, locked: s.locked, filters: validateFilters(s.filters) };
  });
  return { version: 1, scenes };
}

export async function createStitchServer({ manifestPath, assetsRoot, stateRoot, webRoot, traceConfig }) {
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  if (manifest.version !== 1 || !Array.isArray(manifest.scenes) || !manifest.scenes.length) throw Error('Manifest needs version 1 and scenes.');
  const assets = new Map();
  const root = await realpath(assetsRoot);
  for (const scene of manifest.scenes) {
    if (!/^[a-zA-Z0-9_-]+$/.test(scene.id) || assets.has(scene.id) || typeof scene.asset !== 'string' || !scene.asset.toLowerCase().endsWith('.ply')) throw Error('Scene IDs must be unique safe names, with .ply assets.');
    const filename = await realpath(path.resolve(root, scene.asset));
    if (!filename.startsWith(root + path.sep)) throw Error('Asset escapes configured root.');
    if (!(await stat(filename)).isFile()) throw Error('Asset is not a file.');
    assets.set(scene.id, filename);
  }
  const tracer=await traceApi(traceConfig,assets);
  const initial = validateProject({ version: 1, scenes: manifest.scenes.map((s, i) => ({...s, transform: s.transform ?? {position:[0,0,0],rotation:[0,0,0],scale:1}, visible: true, locked: s.locked ?? i === 0})) }, manifest);
  await mkdir(stateRoot, {recursive:true});
  const savePath = path.join(stateRoot, 'project.json');
  let project = initial;
  try {
    const saved = JSON.parse(await readFile(savePath, 'utf8'));
    if (saved.version !== 1 || !Array.isArray(saved.scenes) || saved.scenes.some(s => !manifest.scenes.some(m => m.id === s.id && m.asset === s.asset))) throw Error('Saved scene assets differ from manifest. Use a new state directory for another project.');
    project = validateProject({...saved, scenes: [...saved.scenes, ...initial.scenes.filter(s => !saved.scenes.some(old => old.id === s.id))]}, manifest);
  } catch(e) { if (e.code !== 'ENOENT') throw Error(`Saved project invalid: ${e.message}`); }
  let revision = randomUUID();
  let saving = false;
  const json = (res, code, body) => {res.writeHead(code, {'Content-Type':'application/json','Cache-Control':'no-store'}); res.end(JSON.stringify(body));};
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (url.pathname.startsWith('/api/')) {
        if(req.method==='GET'&&url.pathname==='/api/trace')return json(res,200,{scenes:tracer?.scenes??[]});
        if(req.method==='POST'&&url.pathname==='/api/trace'){
          if(!tracer)return json(res,404,{error:'Source tracing is not configured.'});
          if(req.headers.origin&&req.headers.origin!==`http://${req.headers.host}`)return json(res,403,{error:'Cross-origin writes are not allowed.'});
          if(!(req.headers['content-type']??'').startsWith('application/json'))return json(res,415,{error:'Expected JSON.'});
          let body='';for await(const chunk of req){body+=chunk;if(body.length>16000)return json(res,413,{error:'Selection too large.'});}
          return json(res,200,await tracer.run(JSON.parse(body)));
        }
        if (req.method === 'GET' && url.pathname === '/api/project') return json(res,200,{manifest, project, initial, revision});
        if (req.method === 'PUT' && url.pathname === '/api/project') {
          if (req.headers.origin && req.headers.origin !== `http://${req.headers.host}`) return json(res,403,{error:'Cross-origin writes are not allowed.'});
          if (!(req.headers['content-type'] ?? '').startsWith('application/json')) return json(res,415,{error:'Expected JSON.'});
          let body = ''; for await (const chunk of req) {body += chunk; if(body.length > 1000000) return json(res,413,{error:'Project too large.'});}
          const input = JSON.parse(body);
          if (saving || input.revision !== revision) return json(res,409,{error:'Project changed elsewhere. Reload before saving.'});
          const validated = validateProject(input.project, manifest);
          saving = true;
          try {const temporary = `${savePath}.${randomUUID()}.tmp`; await writeFile(temporary, JSON.stringify(validated,null,2)+'\n', {mode:0o600}); await rename(temporary,savePath); project = validated; revision = randomUUID();} finally {saving = false;}
          return json(res,200,{revision});
        }
        return json(res,404,{error:'Unknown API route.'});
      }
      if (req.method !== 'GET' && req.method !== 'HEAD') return json(res,405,{error:'Read only.'});
      let filename, contentType;
      if(url.pathname.startsWith('/trace-result/')){
        filename=tracer?.file(url.pathname);contentType=url.pathname.endsWith('.jpg')?'image/jpeg':url.pathname.endsWith('.json')?'application/json':'application/octet-stream';
      } else if (url.pathname.startsWith('/assets/')) {
        const id = url.pathname.slice('/assets/'.length).replace(/\.ply$/,''); filename = assets.get(id); contentType = 'application/octet-stream';
      } else {
        const names = {'/':'index.html','/editor.js':'editor.js'};
        const name = names[url.pathname]; if(name) filename = path.join(webRoot,name);
        contentType = url.pathname.endsWith('.js') ? 'text/javascript' : 'text/html';
      }
      if (!filename) return json(res,404,{error:'Not found.'});
      const size = (await stat(filename)).size;
      res.writeHead(200, {'Content-Type':contentType,'Content-Length':size,'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});
      if(req.method === 'HEAD') return res.end();
      const stream = createReadStream(filename); stream.on('error', () => res.destroy()); stream.pipe(res);
    } catch(e) {if(!res.headersSent) json(res,400,{error:e.message}); else res.destroy();}
  });
  return {server, savePath};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2), options = {};
  for(let i=0;i<args.length;i+=2) {if(!args[i]?.startsWith('--') || !args[i+1]) throw Error('Use --manifest FILE --assets DIR --state DIR [--host HOST --port PORT --web DIR]'); options[args[i].slice(2)] = args[i+1];}
  for(const key of ['manifest','assets','state']) if(!options[key]) throw Error(`Missing --${key}`);
  const {server} = await createStitchServer({manifestPath:options.manifest,assetsRoot:options.assets,stateRoot:options.state,webRoot:options.web ?? 'dist/stitch-editor',traceConfig:options['trace-config']});
  const host = options.host ?? '127.0.0.1', port = Number(options.port ?? 8092);
  server.listen(port,host, () => console.log(`Stitch editor listening on http://${host}:${server.address().port}`));
}
