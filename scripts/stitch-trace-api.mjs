import {readFile, mkdir, realpath} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';

export async function traceApi(configPath, assets) {
  if(!configPath)return null;
  const config=JSON.parse(await readFile(configPath,'utf8'));
  await mkdir(config.output,{recursive:true});
  const roots=new Map();
  for(const [id,root] of Object.entries(config.references)){
    if(!assets.has(id))throw Error('Trace scene absent from manifest');
    roots.set(id,await realpath(root));
  }
  const script=fileURLToPath(new URL('./trace_splat_sources.py',import.meta.url));
  const results=new Set();let busy=false;
  return {
    scenes:[...roots.keys()],
    async run(input){
      if(busy)throw Error('A trace is already running. Try again after it finishes.');
      if(!roots.has(input.scene))throw Error('Source frames unavailable for this scene');
      const id=randomUUID();busy=true;
      try{
        const result=await new Promise((resolve,reject)=>{
          const child=execFile(config.python??'python3',[script,'--ply',assets.get(input.scene),'--references',roots.get(input.scene),'--output',path.join(config.output,id)],{timeout:90000,maxBuffer:1024*1024},(error,stdout,stderr)=>{
            if(error)return reject(Error(stderr.split('\n').filter(Boolean).at(-1)??'Trace failed'));
            try{resolve(JSON.parse(stdout));}catch{reject(Error('Invalid trace result'));}
          });
          child.stdin.end(JSON.stringify(input));
        });
        results.add(id);return {...result,trace_id:id};
      }finally{busy=false;}
    },
    file(url){
      const match=/^\/trace-result\/([0-9a-f-]{36})\/(frame_[0-9]+\.jpg|selection\.ply|trace\.json)$/.exec(url);
      if(!match||!results.has(match[1]))return null;
      return path.join(config.output,match[1],match[2]);
    }
  };
}
